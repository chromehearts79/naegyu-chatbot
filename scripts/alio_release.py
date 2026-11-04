"""내규 파일 지문과 배포판 목록(dist/release.json), ALIO 기록(knowledge/alio_seen.json).

  python3 -X utf8 scripts/alio_release.py seed [--force]   처음 기록을 만든다(1회)
  python3 -X utf8 scripts/alio_release.py refresh          ALIO 값을 다시 받아 기록과 배포판 목록을 고친다

순수 함수는 파일을 읽지 않는다. 저장소의 update_rules 는 명령 함수 안에서만 가져온다(부 담당 PC에는 저장소가 없다).
"""
import hashlib
import io
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alio_client import AlioError, fetch_attachments, fetch_file, fetch_list  # noqa: E402
from alio_pick import format_date, pick_bundle  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SEEN = ROOT / "knowledge" / "alio_seen.json"
RELEASE = ROOT / "dist" / "release.json"
REPORT = ROOT / "reports" / "alio_seed_report.md"
SCHEMA = 1
EXPECT_DIFF = 23  # 처음 기록 때 내부 원본과 지문이 다른 내규 수(설계 5장 실측, 아래 두 건 제외)
# 오래된 내규인데 같은 달 한글 첨부가 둘이다. 지문 비교는 못 하지만 ALIO 값은 기록할 수 있고, 다음 개정은 날짜가 달라 겹치지 않는다
KNOWN_TIES = {"상품권 구매 및 사용지침", "좋은일자리위원회 설치 및 운영지침"}
TIE_MSG = "일자 한글 문서가 둘 이상입니다"
NEW_SINCE = "2025.10"  # 이 달 이후 개정분은 모두 지문이 같아야 한다
CODE = re.compile(r"^([ⅠⅡⅢⅣ][\d\-]*)\.\s*(.+)$")
HANGUL = (".hwp", ".hwpx")


def file_digest(data):
    """source_files.json 과 같은 방식: SHA-1 앞 16자리"""
    return hashlib.sha1(data).hexdigest()[:16]


def _iter(root, tag):
    """이름공간과 상관없이 태그 이름으로 찾는다"""
    return (e for e in root.iter() if e.tag.rsplit("}", 1)[-1] == tag)


def _cells(data):
    """엑셀의 (시트 파일, 칸 주소, 공백 정리한 값) 목록"""
    out = []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in _iter(ET.fromstring(z.read("xl/sharedStrings.xml")), "si"):
                shared.append("".join(t.text or "" for t in _iter(si, "t")))
        for name in sorted(n for n in z.namelist() if re.fullmatch(r"xl/worksheets/[^/]+\.xml", n)):
            for c in _iter(ET.fromstring(z.read(name)), "c"):
                kind, v = c.get("t"), next(_iter(c, "v"), None)
                if kind == "inlineStr":
                    val = "".join(t.text or "" for t in _iter(c, "t"))
                elif v is None:
                    continue
                elif kind == "s":
                    val = shared[int(v.text)]
                else:
                    val = v.text or ""
                out.append((name, c.get("r") or "", re.sub(r"\s+", " ", val).strip()))
    return out


def xlsx_digest(data):
    """칸 값으로 만든 지문. 시트 이름·문서 속성은 보지 않으므로 같은 표를 다시 저장해도 같다."""
    cells = sorted(_cells(data))
    return hashlib.sha1(json.dumps(cells, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def digest_of(name, data):
    if name.lower().endswith(".xlsx"):
        try:
            return xlsx_digest(data)
        except (zipfile.BadZipFile, ET.ParseError, KeyError, ValueError, IndexError):
            pass  # 열 수 없는 엑셀은 파일 지문으로 비교한다
    return file_digest(data)


def bundle_digests(files):
    return [digest_of(n, d) for n, d in files]


def same_as(digests, entry_files):
    return bool(digests) and all(d in entry_files for d in digests)


def norm_title(s):
    return re.sub(r"[\s·ㆍ.]", "", unicodedata.normalize("NFC", s))


def values_of(row, attachments):
    nos = [a["file_no"] for a in attachments if str(a["file_no"]).isdigit()]
    return {"mod": row["mod"], "st_date": row["st_date"], "file_no": str(max(nos, key=int)) if nos else ""}


def source_entries(sources):
    """원본 파일 이름 앞의 코드로 묶는다 → {코드: {"digests": [...], "ext": 한글 문서 확장자}}"""
    out = {}
    for name in sorted(sources):
        nfc = unicodedata.normalize("NFC", name)
        m = CODE.match(Path(nfc).stem)
        if not m:
            continue
        e = out.setdefault(m.group(1), {"digests": [], "ext": ""})
        e["digests"].append(digest_of(nfc, sources[name]))
        if nfc.lower().endswith(HANGUL):
            e["ext"] = Path(nfc).suffix.lower()
    return out


def build_release(rules, sources, seen, release_no, built):
    entries = source_entries(sources)
    by_name = {}
    for k, v in seen.get("rules", {}).items():  # 규정명이 바뀌어도 띄어쓰기·가운뎃점만 달라도 같은 내규로 본다
        by_name.setdefault(norm_title(v["name"]), (k, v))
    out, used = [], set()
    for r in rules:
        idx, s = by_name.get(norm_title(r["name"]), ("", {}))
        used.add(idx)
        e = entries.get(r["code"], {"digests": [], "ext": ""})
        item = {"name": r["name"], "code": r["code"], "idx": idx, "ext": e["ext"],
                "mod": s.get("mod", ""), "st_date": s.get("st_date", ""), "file_no": s.get("file_no", ""),
                "file_date": s.get("file_date", ""), "files": list(e["digests"])}
        if s.get("confirmed"):
            item["confirmed"] = s["confirmed"]
        out.append(item)
    for idx, s in seen.get("rules", {}).items():
        if idx in used:
            continue
        item = {"name": s["name"], "code": "", "idx": idx, "ext": "", "mod": s["mod"], "st_date": s["st_date"],
                "file_no": s["file_no"], "file_date": s["file_date"], "files": []}
        if s.get("confirmed"):
            item["confirmed"] = s["confirmed"]
        out.append(item)
    return {"schema": SCHEMA, "release_no": release_no, "built": built, "rules": out}


def confirm(seen, row, values, file_date, reason, today, gone=False):
    """담당자 확인: 지금 ALIO 값과 사유를 기록한다."""
    e = seen["rules"].setdefault(row["idx"], {"name": row["title"]})
    e.update({"title": row["title"], "mod": values["mod"], "st_date": values["st_date"],
              "file_no": values["file_no"], "file_date": file_date})
    e["confirmed"] = {"date": today, "reason": reason}
    if gone:
        e["confirmed"]["gone"] = True


def refresh_seen(seen, rows, attachments, fetch, entries, same_text, rules):
    """값이 달라진 내규는 현행 묶음이 새 원본과 같을 때만 기록을 올린다. 경고 목록을 돌려준다."""
    warns = []
    by_title = {norm_title(r["name"]): r for r in rules}
    for row in rows:
        e = seen["rules"].get(row["idx"])
        if e is None:
            continue  # 새 내규는 확인 때 잡힌다
        atts = attachments.get(row["idx"], [])
        v = values_of(row, atts)
        if all(e.get(k) == v[k] for k in v):
            continue
        name = e["name"]
        try:
            bundle = pick_bundle([(a["name"], fetch(a["file_no"])) for a in atts], row["st_date"])
        except AlioError as ex:
            warns.append(f"{name}: ALIO 파일을 받지 못해 옛 기록을 둠({ex})")
            continue
        rule = by_title.get(norm_title(row["title"])) or by_title.get(norm_title(name))  # 규정명이 바뀌었으면 ALIO 제목으로 먼저 찾는다
        code = rule["code"] if rule else None
        if bundle.problems or bundle.date is None or not code or code not in entries:
            warns.append(f"{name}: 이 내규는 ALIO 파일과 달라 다음 확인 때 다시 잡힘")
            continue
        if same_as(bundle_digests(bundle.files), entries[code]["digests"]) or same_text(name, code, bundle.files):
            e.update({"name": rule["name"], "title": row["title"], "mod": v["mod"], "st_date": v["st_date"], "file_no": v["file_no"],
                      "file_date": format_date(bundle.date)})
            e.pop("confirmed", None)
        else:
            warns.append(f"{name}: 이 내규는 ALIO 파일과 달라 다음 확인 때 다시 잡힘")
    return warns


def load_seen(path=SEEN):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_seen(seen, before_rules, path=SEEN, today=None):
    """기록이 달라졌을 때만 taken 을 고쳐 쓴다(안 바뀌었는데 쓰면 git 에 변경이 뜬다). 썼으면 True."""
    if seen["rules"] == before_rules:
        return False
    seen["taken"] = today or date.today().isoformat()
    _save_json(path, seen)
    return True


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _load_sources():
    import update_rules as U  # 저장소가 있는 PC에서만 부른다
    return {n: p.read_bytes() for n, p in U.sources().items()}


def _rules():
    return json.loads((ROOT / "data" / "rules.json").read_text(encoding="utf-8"))["rules"]


def _release_no():
    return json.loads((ROOT / "knowledge" / "site.json").read_text(encoding="utf-8"))["release"]["no"]


def write_release():
    """실제 원본·data/rules.json·knowledge/site.json 으로 dist/release.json 을 쓴다. 판 번호는 그대로."""
    rel = build_release(_rules(), _load_sources(), load_seen(), _release_no(), date.today().isoformat())
    _save_json(RELEASE, rel)
    return rel


def fetch_all():
    rows = fetch_list()
    atts = {r["idx"]: fetch_attachments(r) for r in rows}
    return rows, atts


def seed(force=False):
    if SEEN.exists() and not force:
        print(f"{SEEN.name} 이 이미 있습니다. 다시 만들려면 --force 를 붙이세요.")
        return 1
    rules, sources = _rules(), _load_sources()
    entries = source_entries(sources)
    try:
        rows, atts = fetch_all()
    except AlioError as e:
        print(f"ALIO 확인 실패: {e}")
        return 1
    by_title = {norm_title(r["name"]): r for r in rules}
    problems, diff, same_new, seen_rules, ties = [], [], 0, {}, []
    print(f"규정 {len(rows)}건")
    matched = set()
    for row in rows:
        rule = by_title.get(norm_title(row["title"]))
        if rule is None:
            problems.append(f"내규에 없는 ALIO 항목: {row['title']}")
            continue
        matched.add(rule["code"])
        try:
            files = [(a["name"], fetch_file(a["file_no"])) for a in atts[row["idx"]]]
        except AlioError as e:
            problems.append(f"{row['title']}: 파일을 받지 못함({e})")
            continue
        bundle = pick_bundle(files, row["st_date"])
        tie_only = (rule["name"] in KNOWN_TIES and bundle.date is not None and len(bundle.problems) == 1
                    and TIE_MSG in bundle.problems[0])
        if (bundle.problems and not tie_only) or bundle.date is None:
            problems.append(f"{row['title']}: " + " / ".join(bundle.problems or ["현행 묶음을 고르지 못함"]))
            continue
        v = values_of(row, atts[row["idx"]])
        if tie_only:
            seen_rules[row["idx"]] = {"name": rule["name"], "title": row["title"], "mod": v["mod"], "st_date": v["st_date"],
                                      "file_no": v["file_no"], "file_date": format_date(bundle.date)}
            ties.append((rule, row, bundle))
            continue
        same = same_as(bundle_digests(bundle.files), entries.get(rule["code"], {"digests": []})["digests"])
        seen_rules[row["idx"]] = {"name": rule["name"], "title": row["title"], "mod": v["mod"], "st_date": v["st_date"],
                                  "file_no": v["file_no"], "file_date": format_date(bundle.date)}
        if same:
            same_new += row["st_date"] >= NEW_SINCE
        else:
            diff.append((rule, row, bundle))
            if row["st_date"] >= NEW_SINCE:
                problems.append(f"{NEW_SINCE} 이후 개정인데 지문이 다름: {row['title']}")
    for r in rules:
        if r["code"] not in matched:
            problems.append(f"ALIO에 없는 내규: {r['name']}")
    new_total = sum(r["st_date"] >= NEW_SINCE for r in rows)
    print(f"{NEW_SINCE} 이후 지문 같음 {same_new}건 (이 기간 {new_total}건)")
    print(f"지문 다름 {len(diff)}건")
    print(f"담당자 확인 {len(ties)}건")
    if len(diff) != EXPECT_DIFF:
        problems.append(f"지문이 다른 수가 {EXPECT_DIFF}건이 아님({len(diff)}건)")
    if problems:
        print("멈춥니다. 파일을 쓰지 않았습니다.")
        for p in problems:
            print(" -", p)
        return 1
    lines = ["# ALIO 처음 기록 보고서", "",
             f"작성일 {date.today().isoformat()}. 내부 원본과 ALIO 현행 파일의 지문이 다른 내규 {len(diff)}건입니다.",
             "내규관리부서에서 ALIO에 올린 파일이 내부 원본과 같은 개정본인지 확인해 주세요.", "",
             "| 내규 | 코드 | ALIO 목록 날짜 | ALIO 파일 일자 | ALIO 파일 | 내부 원본 |", "|---|---|---|---|---|---|"]
    for rule, row, bundle in diff:
        names = ", ".join(n for n, _ in bundle.files)
        lines.append(f"| {rule['name']} | {rule['code']} | {row['st_date']} | {format_date(bundle.date)} | {names} | {entries.get(rule['code'], {}).get('ext', '')} |")
    lines += ["", "## 같은 달 첨부가 둘이라 지문을 비교하지 못함", "",
              "| 내규 | 코드 | ALIO 목록 날짜 | ALIO 파일 |", "|---|---|---|---|"]
    for rule, row, bundle in ties:
        lines.append(f"| {rule['name']} | {rule['code']} | {row['st_date']} | {', '.join(n for n, _ in bundle.files)} |")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _save_json(SEEN, {"taken": date.today().isoformat(), "rules": seen_rules})
    write_release()
    jeon = next((r for r in rules if "위임전결" in r["name"]), None)
    if jeon and all(d[0] is not jeon for d in diff) and all(t[0] is not jeon for t in ties):
        print(f"{jeon['name']}: 지문 같음")
    print(f"기록 {len(seen_rules)}건을 썼습니다: {SEEN.relative_to(ROOT)}, {RELEASE.relative_to(ROOT)}, {REPORT.relative_to(ROOT)}")
    return 0


def refresh():
    seen = load_seen()
    try:
        rows, atts = fetch_all()
    except AlioError as e:
        print(f"경고: ALIO 접속 실패로 옛 기록을 그대로 둡니다({e})")
        write_release()
        return 0

    def same_text(name, code, files):
        try:
            import alio_compare  # 저장소가 있는 PC에서만
            return bool(alio_compare.compare_rule(name, code, files).whole_same)
        except ImportError:
            return False

    entries = source_entries(_load_sources())
    before = json.dumps(seen["rules"], sort_keys=True)
    before_rules = json.loads(before)
    warns = refresh_seen(seen, rows, atts, fetch_file, entries, same_text, _rules())
    save_seen(seen, before_rules)
    write_release()
    for w in warns:
        print("경고:", w)
    changed = sum(1 for k, v in seen["rules"].items() if before_rules.get(k) != v)
    print(f"ALIO 기록: 바뀐 내규 {changed}건, 경고 {len(warns)}건")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "seed":
        sys.exit(seed("--force" in sys.argv))
    if cmd == "refresh":
        sys.exit(refresh())
    sys.exit("사용법: alio_release.py seed [--force] | refresh")
