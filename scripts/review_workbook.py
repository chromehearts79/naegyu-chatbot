"""담당부서 검수표 만들기와 검수 결과 반영.

  python3 scripts/review_workbook.py export   → reports/review/검수표_<분류>.xlsx (내규분류표 분류마다 한 파일)
  python3 scripts/review_workbook.py import reports/review/*.xlsx
      판정이 '정확'이고 검수부서·검수일이 적힌 행 → 카드에 reviewed 기록(화면에 '담당부서 검수 완료 · 날짜 · 부서')
      '수정 필요'·'삭제' 행 → reports/review/수정요청.md 로 모아 관리자가 고친다

검수자 이름은 개인정보라 카드에 넣지 않는다(검수표에만 남는다).
카드 내용(답·근거)이 검수 뒤에 바뀌면 지문이 달라져 화면에서 다시 '검수 전'으로 돌아간다(build_web.py).
"""
import datetime
import glob
import hashlib
import json
import re
import sys
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_knowledge import KNOWLEDGE, ROOT, load_domains  # noqa: E402
import check_changes  # noqa: E402

OUT = ROOT / "reports" / "review"
VERDICTS = ["정확", "수정 필요", "삭제"]
COLS = ["카드 ID", "규정", "제목", "요약", "답변", "근거(항목: 값 — 조문)", "AI 검토 메모", "우선순위",
        "판정", "수정 의견", "검수부서", "검수자", "검수일(YYYY-MM-DD)"]
WIDTH = [22, 16, 24, 40, 70, 60, 40, 10, 11, 40, 14, 10, 16]
# 직원 행동에 바로 영향을 주는 분야(평가단 권고)부터 본다
HIGH = re.compile(r"휴가|휴직|연가|병가|징계|인사위원회|괴롭힘|성희롱|인권|계약직|전문직|기간제|해고|면직")


def card_hash(c):
    """검수한 내용의 지문: 답·요약·근거가 바뀌면 달라진다."""
    body = json.dumps([c.get("summary"), c.get("answer"), [(f["label"], f["value"], f["cite"]) for f in c.get("facts", [])]],
                      ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(body.encode()).hexdigest()[:16]


def rule_of(c):
    """카드의 규정: rule 칸, 없으면 근거에서 가장 많이 인용한 규정(engine.js 의 ruleOfCard 와 같은 규칙)"""
    count = {}
    for f in c.get("facts", []):
        m = re.match(r"^(.+?) (제\d|별표|부칙)", f["cite"])
        if m:
            count[m[1]] = count.get(m[1], 0) + 1
    return max(count, key=count.get) if count else ""


def categories():
    """내규분류표(내규관리세칙 별표 제1호)에서 규정 → 분류."""
    rules = {r["name"]: r for r in json.loads((ROOT / "data" / "rules.json").read_text())["rules"]}
    text = next(a["text"] for a in rules["내규관리세칙"]["annexes"] if "분류표" in a["title"])
    cat, out = "", {}
    for line in text.splitlines():
        cells = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(cells) < 2 or cells[0] in ("분류", "---"):
            continue
        if cells[0]:
            cat = re.sub(r"^[ⅠⅡⅢⅣ\d]+\.\s*", "", cells[0]).replace("및", "").strip() or cat
        name = cells[1].replace("·", "").replace(" ", "")
        if name:
            out[name] = cat
    fix = {"보수": "보수·복리후생", "복리후생": "보수·복리후생"}
    return {n: fix.get(c, c) for n, c in out.items()}, rules


def export():
    OUT.mkdir(parents=True, exist_ok=True)
    cat_of, rules = categories()
    _, cards = load_domains()
    stale = json.loads(check_changes.STALE.read_text())["cards"] if check_changes.STALE.exists() else {}
    groups = {}
    for c in cards:
        rule = c.get("rule") or rule_of(c)
        cat = "상황별 종합" if rule == "여러 규정 종합" else cat_of.get(rule.replace("·", "").replace(" ", ""), "기타")
        groups.setdefault(cat, []).append((rule, c))
    order = list(dict.fromkeys(cat_of.values())) + ["기타"]
    made = []
    for cat in sorted(groups, key=lambda x: order.index(x) if x in order else 99):
        wb = Workbook()
        ws = wb.active
        ws.title = "검수"
        ws.append(COLS)
        for i, w in enumerate(WIDTH):
            ws.column_dimensions[chr(65 + i)].width = w
        for cell in ws[1]:
            cell.font = Font(bold=True)
            cell.fill = PatternFill("solid", fgColor="DDEBE7")
        rows = []
        for rule, c in groups[cat]:
            text = " ".join([c["title"], c["summary"]] + c["answer"])
            prio = "1 높음" if (c["id"] in stale or c.get("check") or HIGH.search(text)) else ("3 개요" if c.get("overview") else "2 보통")
            rows.append([c["id"], rule, c["title"], c["summary"], "\n".join(a.replace("**", "") for a in c["answer"]),
                         "\n".join(f"{f['label']}: {f['value']} — {f['cite']}" for f in c["facts"]),
                         "\n".join(c.get("check") or []) + ("\n[규정 개정 감지] " + ", ".join(x["unit"] for x in stale[c["id"]]) if c["id"] in stale else ""),
                         prio, "", "", "", "", ""])
        rows.sort(key=lambda r: (r[7], r[1], r[0]))
        for r in rows:
            ws.append(r)
        for row in ws.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        dv = DataValidation(type="list", formula1='"' + ",".join(VERDICTS) + '"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"I2:I{ws.max_row}")
        ws.freeze_panes = "D2"
        guide = wb.create_sheet("작성 방법")
        for line in [
            "1. 카드마다 '답변'과 '근거'를 규정 원문과 비교해 '판정' 칸에서 정확 / 수정 필요 / 삭제 중 하나를 고릅니다.",
            "2. '수정 필요'면 '수정 의견'에 무엇을 어떻게 고칠지 적습니다(원문 조항 번호를 함께).",
            "3. 검수부서와 검수일(예: 2026-11-05)을 적습니다. 검수자 이름은 이 표에만 남고 화면에는 나오지 않습니다.",
            "4. 우선순위 '1 높음'(휴가·휴직·징계·괴롭힘·계약직, AI 검토 메모가 있는 카드, 규정 개정 감지 카드)부터 봅니다.",
            "5. 다 쓴 파일을 내규챗봇 관리자에게 보내면 'python3 scripts/review_workbook.py import 파일' 로 반영합니다.",
            "   '정확' 카드는 화면에 '담당부서 검수 완료 · 날짜 · 부서'로 표시되고, 카드 내용이 나중에 바뀌면 다시 '검수 전'이 됩니다.",
        ]:
            guide.append([line])
        guide.column_dimensions["A"].width = 120
        path = OUT / f"검수표_{cat.replace('·', '_')}.xlsx"
        wb.save(path)
        made.append((path.name, len(rows), sum(r[7].startswith("1") for r in rows)))
    for name, n, hi in made:
        print(f"{name}: 카드 {n}장(우선 {hi}장)")


def do_import(paths):
    _, cards = load_domains()
    by_id = {c["id"]: c for c in cards}
    ok, fix, bad = {}, [], []
    for p in paths:
        ws = load_workbook(p, data_only=True)["검수"]
        head = [c.value for c in ws[1]]
        col = {h: i for i, h in enumerate(head)}
        for row in ws.iter_rows(min_row=2, values_only=True):
            cid, verdict = row[col["카드 ID"]], (row[col["판정"]] or "").strip()
            if not cid or not verdict:
                continue
            dept, date = (row[col["검수부서"]] or "").strip(), row[col["검수일(YYYY-MM-DD)"]]
            if isinstance(date, (datetime.date, datetime.datetime)):
                date = date.strftime("%Y-%m-%d")
            date = str(date or "").strip()
            if cid not in by_id:
                bad.append(f"{Path(p).name}: 없는 카드 {cid}")
                continue
            if verdict == "정확":
                if not dept or not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
                    bad.append(f"{Path(p).name}: {cid} 검수부서·검수일(YYYY-MM-DD) 누락")
                    continue
                ok[cid] = {"date": date.replace("-", ".") + ".", "dept": dept, "hash": card_hash(by_id[cid])}
            else:
                fix.append((verdict, cid, by_id[cid]["title"], row[col["수정 의견"]] or "", dept, date))
    # 카드 파일에 기록
    for f in sorted(set(c["_file"] for c in cards if c["id"] in ok)):
        path = KNOWLEDGE / f
        data = json.loads(path.read_text())
        for c in data:
            if c["id"] in ok:
                c["reviewed"] = ok[c["id"]]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    OUT.mkdir(parents=True, exist_ok=True)
    lines = ["# 검수 결과 수정 요청", "", f"반영 {datetime.date.today().isoformat()} · 검수 완료 {len(ok)}장 · 수정·삭제 요청 {len(fix)}장", ""]
    for v, cid, title, note, dept, date in fix:
        lines.append(f"- [{v}] {cid} {title} — {note} ({dept} {date})")
    if bad:
        lines += ["", "## 반영하지 못한 행", ""] + [f"- {b}" for b in bad]
    (OUT / "수정요청.md").write_text("\n".join(lines) + "\n")
    print(f"검수 완료 반영 {len(ok)}장, 수정·삭제 요청 {len(fix)}장, 오류 {len(bad)}건 → reports/review/수정요청.md")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "export":
        export()
    elif len(sys.argv) >= 3 and sys.argv[1] == "import":
        do_import([p for a in sys.argv[2:] for p in glob.glob(a)])
    else:
        sys.exit(__doc__)
