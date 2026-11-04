"""ALIO 내규 확인 루틴의 판정. 표준 라이브러리와 alio_* 모듈만 쓴다(부 담당 PC에는 저장소가 없다)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alio_types as T  # noqa: E402
from alio_pick import HANGUL, format_date, pick_bundle  # noqa: E402
from alio_release import bundle_digests, norm_title, same_as, values_of  # noqa: E402

KEYS = ("mod", "st_date", "file_no")


def _index(release):
    rules = release["rules"]
    by_idx = {r["idx"]: i for i, r in enumerate(rules) if r.get("idx")}
    by_name = {norm_title(r["name"]): i for i, r in enumerate(rules)}
    return rules, by_idx, by_name


def _find(row, rules, by_idx, by_name):
    i = by_idx.get(row["idx"])
    if i is None:
        i = by_name.get(norm_title(row["title"]))
    return i, (rules[i] if i is not None else None)


def _same_values(entry, values):
    return all(entry.get(k, "") == values[k] for k in KEYS)


def judge(rows, attachments, release, local_release, fetch_file, compare, mode):
    rules, by_idx, by_name = _index(release)
    local = _index(local_release) if local_release else None
    used, out = set(), []
    for row in rows:
        i, entry = _find(row, rules, by_idx, by_name)
        if i is not None:
            used.add(i)
        atts = attachments.get(row["idx"], [])
        values = values_of(row, atts)
        name = entry["name"] if entry else row["title"]
        f = T.Finding(name=name, code=entry["code"] if entry else "", idx=row["idx"], verdict=T.V_NONE,
                      title=row["title"], st_date=row["st_date"], mod=row["mod"], values=values)
        out.append(f)
        if entry and _same_values(entry, values):
            continue  # 파일을 받지 않는다
        bundle = pick_bundle([(a["name"], fetch_file(a["file_no"])) for a in atts], row["st_date"])
        f.files = bundle.files
        if bundle.date:
            f.file_date = format_date(bundle.date)
        hangul = next((n for n, _ in bundle.files if n.lower().endswith(HANGUL)), "")
        f.ext = ("." + hangul.lower().rsplit(".", 1)[-1]) if hangul else (entry["ext"] if entry else "")
        if bundle.problems or bundle.date is None:
            f.verdict = T.V_CHECK
            f.notes = list(bundle.problems) or ["현행 묶음을 고르지 못했습니다"]
            continue
        if entry is None:
            f.verdict = T.V_NEW
            f.target_name = f"{name}{f.ext}"
            if mode == "full":
                f.compare = compare(name, "", bundle.files)
            continue
        f.target_name = f"{entry['code']}. {name}{f.ext}" if entry["code"] else f"{name}{f.ext}"
        if same_as(bundle_digests(bundle.files), entry["files"]):
            f.verdict = T.V_DONE
            continue
        if mode == "full" and local:
            _, lby_idx, lby_name = local
            _, lentry = _find(row, local[0], lby_idx, lby_name)
            if lentry and (same_as(bundle_digests(bundle.files), lentry["files"]) or _same_values(lentry, values)):
                f.verdict = T.V_PENDING
                f.notes = ["새 판을 올리면 끝남"]
                continue
        f.verdict = T.V_SUSPECT
        if entry.get("file_date") and entry["file_date"] == f.file_date:
            f.notes.append("날짜가 그대로라 재게시일 수 있음")
        if entry["ext"] and f.ext and f.ext != entry["ext"]:
            f.notes.append("형식이 달라 차이가 과장될 수 있음")
        if mode != "full":
            f.notes.append("정 담당 PC에서 비교")
            continue
        f.compare = compare(name, entry["code"], bundle.files)
        if f.compare.error:
            f.notes.append(f"비교하지 못함: {f.compare.error}")
        elif f.compare.whole_same:
            f.verdict = T.V_SAME_TEXT
        elif not f.compare.changed_units and not f.compare.added_units:
            f.verdict = T.V_OUTSIDE
    for i, entry in enumerate(rules):
        if i not in used and not (entry.get("confirmed") or {}).get("gone"):
            out.append(T.Finding(name=entry["name"], code=entry["code"], idx=entry["idx"], verdict=T.V_GONE,
                                 title=entry["name"], st_date=entry["st_date"], mod=entry["mod"]))
    return out


def check_sanity(rows, release):
    """받은 목록이 배포판의 절반 미만이면 중간에 끊긴 것으로 본다."""
    if len(rows) * 2 < len(release["rules"]):
        raise T.WatchFailure(f"받은 ALIO 목록이 {len(rows)}건뿐입니다(배포판 {len(release['rules'])}건)")
