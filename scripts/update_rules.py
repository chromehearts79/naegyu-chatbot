"""내규 개정·신설 반영 도우미. 원본 폴더에 개정본·신설 내규 파일을 넣은 뒤 단계별로 쓴다.

  python3 scripts/update_rules.py status    # 1단계: 바뀐 파일·새 파일·사라진 파일 찾기
  python3 scripts/update_rules.py convert   # 2단계: 그 파일만 변환 → 규정 DB 다시 만들기 → 개정 감지 보고서
  (3단계: 카드 고치기 — 사람 또는 AI가 reports/change_report.md 를 보고 카드를 고친다)
  python3 scripts/update_rules.py finish 복무세칙 [규정명 …]   # 4단계: 확인한 규정을 승인하고 시범본·지식 묶음 다시 만들기
  python3 scripts/update_rules.py init      # 처음 한 번: 지금 원본 파일들을 기준으로 기록

원본 폴더: iCloud 내규챗봇 폴더(파일 이름 '코드. 규정명.hwp', 예: 'Ⅲ-3-1. 복무세칙.hwp').
같은 규정의 옛 파일은 '지난판' 폴더로 옮겨 두면 된다(이 폴더와 '['로 시작하는 참고 파일은 읽지 않는다).
결과 요약은 reports/update/status.json, reports/update/summary.md 에 남는다.
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 시험할 때는 NAEGYU_SRC 로 다른 폴더를 줄 수 있다
SRC = Path(os.environ.get("NAEGYU_SRC") or Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "내규챗봇")
MD = ROOT / "data" / "md"
MANIFEST = ROOT / "knowledge" / "source_files.json"
OUT = ROOT / "reports" / "update"
EXT = (".hwp", ".hwpx", ".xlsx")
CODE = re.compile(r"^([ⅠⅡⅢⅣ][\d\-]*)\.\s*(.+)$")


def run(*cmd, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if check and r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-2000:])
        sys.exit(f"실패: {' '.join(map(str, cmd))}")
    return r.stdout


def sources():
    """원본 폴더의 내규 파일(지난판·참고 파일 제외) → {파일명: 경로}"""
    out = {}
    for p in sorted(SRC.iterdir()):
        if p.is_file() and p.suffix.lower() in EXT and not p.name.startswith("[") and not p.name.startswith("."):
            out[p.name] = p
    return out


def sha(p):
    return hashlib.sha1(p.read_bytes()).hexdigest()[:16]


def code_of(name):
    m = CODE.match(Path(name).stem)
    return m.group(1) if m else None


def diff_files():
    old = json.loads(MANIFEST.read_text())["files"] if MANIFEST.exists() else {}
    cur = {n: sha(p) for n, p in sources().items()}
    changed = [n for n in cur if n in old and cur[n] != old[n]]
    new = [n for n in cur if n not in old]
    gone = [n for n in old if n not in cur]
    # 같은 코드의 파일이 둘 이상이면(옛 파일을 안 치운 경우) 알려 준다. 위임전결기준 엑셀은 별표라 예외
    by_code = {}
    for n in cur:
        c = code_of(n)
        if c and not n.lower().endswith(".xlsx"):
            by_code.setdefault(c, []).append(n)
    dup = {c: ns for c, ns in by_code.items() if len(ns) > 1}
    noname = [n for n in new if not code_of(n)]
    # 이름만 바뀐 파일(같은 코드의 옛 파일이 사라지고 새 파일이 생김)은 '바뀐 파일'로 본다
    renamed = {}
    for n in list(new):
        c = code_of(n)
        olds = [g for g in gone if c and code_of(g) == c and Path(g).suffix.lower() != ".xlsx"]
        if olds:
            renamed[n] = olds[0]
            new.remove(n)
            gone.remove(olds[0])
    return {"changed": changed, "renamed": renamed, "new": new, "gone": gone, "dup": dup, "noname": noname, "cur": cur}


def status():
    d = diff_files()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "status.json").write_text(json.dumps({k: v for k, v in d.items() if k != "cur"}, ensure_ascii=False, indent=1))
    lines = [f"원본 폴더: {SRC}", ""]
    lines += [f"- 바뀐 파일: {n}" for n in d["changed"]]
    lines += [f"- 이름이 바뀐 파일: {o} → {n}" for n, o in d["renamed"].items()]
    lines += [f"- 새 파일: {n}" for n in d["new"]]
    lines += [f"- 사라진 파일: {n}" for n in d["gone"]]
    for c, ns in d["dup"].items():
        lines.append(f"- [확인 필요] 같은 코드 {c} 파일이 {len(ns)}개: {', '.join(ns)} → 옛 파일을 '지난판' 폴더로 옮겨 주세요")
    for n in d["noname"]:
        lines.append(f"- [확인 필요] '{n}' 은 이름이 '코드. 규정명' 형식이 아님(예: 'Ⅳ-30. ○○지침.hwp') → 이름을 바꿔 주세요")
    if not any(d[k] for k in ("changed", "renamed", "new", "gone")):
        lines.append("- 바뀐 파일이 없습니다.")
    print("\n".join(lines))
    return d


def convert():
    d = status()
    if d["dup"] or d["noname"]:
        sys.exit("\n위 [확인 필요]를 먼저 정리해 주세요.")
    todo = d["changed"] + list(d["renamed"]) + d["new"]
    if not todo and not d["gone"]:
        sys.exit("\n변환할 파일이 없습니다.")
    MD.mkdir(parents=True, exist_ok=True)
    # 이름이 바뀌었거나 사라진 파일의 옛 변환본은 지운다
    for old in list(d["renamed"].values()) + d["gone"]:
        (MD / (Path(old).stem + ".md")).unlink(missing_ok=True)
    if todo:
        print(f"\n변환 중: {len(todo)}개 …")
        run("npx", "-y", "kordoc", "--jobs", "4", "-d", str(MD), *[str(SRC / n) for n in todo])
    print(run(sys.executable, "scripts/build_db.py").strip())
    out = run(sys.executable, "scripts/check_changes.py").strip()
    print(out)
    chk = run(sys.executable, "scripts/check_knowledge.py", check=False)
    errs = re.search(r"오류 (\d+)건", chk)
    stale_all = json.loads((ROOT / "knowledge" / "stale_cards.json").read_text())
    stale, calcs = stale_all["cards"], stale_all.get("calcs", {})
    rules = json.loads((ROOT / "data" / "rules.json").read_text())["rules"]
    card_rules = set()
    for f in (ROOT / "knowledge").glob("*/[!_]*.json"):
        for c in json.loads(f.read_text()):
            card_rules.add(c.get("rule") or "")
            for x in c.get("facts", []):
                m = re.match(r"^(.+?) (제\d|별표|부칙)", x["cite"])
                if m:
                    card_rules.add(m[1])
    no_cards = [r["name"] for r in rules if r["name"] not in card_rules]
    summary = {
        "date": datetime.date.today().isoformat(), "files": todo, "gone": d["gone"],
        "stale_cards": len(stale), "stale_rules": sorted({x["rule"] for v in stale.values() for x in v}),
        "rules_without_cards": no_cards, "check_errors": int(errs[1]) if errs else None,
        "stale_calcs": {k: v["title"] for k, v in calcs.items()},
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    lines = ["", "## 비교 결과",
             f"- 다시 확인할 카드: {len(stale)}장 (규정: {', '.join(summary['stale_rules']) or '없음'})",
             f"- 다시 확인할 계산기: {len(calcs)}종 ({', '.join(v['title'] for v in calcs.values()) or '없음'})",
             f"- 카드가 아직 없는 규정(새 내규): {', '.join(no_cards) or '없음'}",
             f"- 카드 검사 오류(조문이 없어지거나 번호가 바뀐 인용): {summary['check_errors']}건",
             "- 자세한 내용: reports/change_report.md (바뀐 조문의 개정 전·후 글자)"]
    print("\n".join(lines))


def finish(accept):
    chk = run(sys.executable, "scripts/check_knowledge.py", check=False)
    if "오류 0건" not in chk:
        print(chk[-1500:])
        sys.exit("카드 검사 오류가 남아 있어 마무리하지 않습니다.")
    if accept:
        print(run(sys.executable, "scripts/check_changes.py", "--accept", *accept).strip())
    # 새로 배포할 판 번호(옛 사본과 구별하려고 화면 위쪽에 '제N판'으로 보인다)
    site_path = ROOT / "knowledge" / "site.json"
    site = json.loads(site_path.read_text())
    site.setdefault("release", {"no": 0, "where": ""})["no"] += 1
    site_path.write_text(json.dumps(site, ensure_ascii=False, indent=2) + "\n")
    print(f"판 번호: 제{site['release']['no']}판")
    print(run(sys.executable, "scripts/check_changes.py").strip())
    print(run(sys.executable, "scripts/check_approval_table.py").strip())
    print(run(sys.executable, "scripts/build_web.py").strip())
    print(run(sys.executable, "scripts/export_gpts.py").strip())
    print(run(sys.executable, "scripts/review_workbook.py", "export").strip().splitlines()[-1])
    # 원본 파일 기록 갱신(다음 개정 때 바뀐 파일만 고르기 위해)
    cur = {n: sha(p) for n, p in sources().items()}
    MANIFEST.write_text(json.dumps({"taken": datetime.date.today().isoformat(), "files": cur}, ensure_ascii=False, indent=1) + "\n")
    print(f"원본 파일 기록 갱신: {len(cur)}개 ({MANIFEST.relative_to(ROOT)})")


def init():
    cur = {n: sha(p) for n, p in sources().items()}
    MANIFEST.write_text(json.dumps({"taken": datetime.date.today().isoformat(), "files": cur}, ensure_ascii=False, indent=1) + "\n")
    print(f"지금 원본 파일 {len(cur)}개를 기준으로 기록했습니다 → {MANIFEST.relative_to(ROOT)}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "status":
        status()
    elif cmd == "convert":
        convert()
    elif cmd == "finish":
        finish(sys.argv[2:])
    elif cmd == "init":
        init()
    else:
        sys.exit(__doc__)
