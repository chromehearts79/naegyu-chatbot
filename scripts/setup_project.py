"""빈 저장소(GitHub Actions, Claude 클라우드 세션)를 쓸 수 있게 준비한다.

  python3 -X utf8 scripts/setup_project.py [--full] [--no-install] [--allow-changes]

패키지를 설치하고, 원본/ 의 한글 파일을 data/ 로 다시 변환하고, 저장된 지문(knowledge/source_snapshot.json)과
같은지 확인한다. 지문과 stale_cards.json 은 절대 고치지 않는다.
무거운 패키지는 함수 안에서만 불러서, 패키지가 없어도 import 할 수 있다.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
SRC = ROOT / "원본"
DATA = ROOT / "data"
STAMP = DATA / ".setup_stamp"
EXT = (".hwp", ".hwpx", ".xlsx")


def source_files(src_dir):
    """원본 폴더의 내규 파일(지난판·참고 파일 제외)."""
    return sorted(p for p in Path(src_dir).iterdir()
                  if p.is_file() and p.suffix.lower() in EXT and not p.name.startswith(("[", ".")))


def setup_stamp(src_dir):
    """원본 파일 내용과 kordoc 판으로 만든 값. 달라지면 변환을 다시 한다."""
    from kordoc_tool import KORDOC
    h = hashlib.sha1(KORDOC.encode("utf-8"))
    for p in source_files(src_dir):
        h.update(p.name.encode("utf-8") + b"\0" + hashlib.sha1(p.read_bytes()).digest())
    return h.hexdigest()


def unit_text(name, unit):
    if unit.startswith("별표:"):
        return f"{name} {unit[3:]}"
    if unit.startswith("부칙:"):
        return f"{name} 부칙({unit[3:]})"
    return f"{name} {unit}"


def baseline_problems(changes, stale):
    """지문과 다른 곳이 있으면 쉬운 말로 알린다. 비면 통과."""
    out = []
    if changes:
        kinds = {"changed": "바뀜", "removed": "없어짐", "added": "새로 생김"}
        items = [f"{unit_text(n, u)}({kinds.get(k, k)})" for (n, u), k in sorted(changes.items())]
        out.append(f"저장된 지문과 다른 조문이 {len(items)}곳 있습니다: " + ", ".join(items))
    if stale:
        out.append(f"다시 확인해야 할 문답이 {len(stale)}장 있습니다.")
    return out


def run(cmd, what):
    r = subprocess.run([str(c) for c in cmd], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print((r.stdout or "")[-1500:], (r.stderr or "")[-1500:])
        sys.exit(f"준비 실패: {what}")
    return r.stdout


def install(full):
    npm = shutil.which("npm")
    if not npm:
        sys.exit("준비 실패: npm 이 없습니다(Node.js 가 필요합니다).")
    run([npm, "ci", "--ignore-scripts"], "npm 패키지 설치")
    reqs = ["requirements.txt"] + (["scripts/requirements-bounds.txt"] if full else [])
    cmd = [sys.executable, "-m", "pip", "install", "-q"]
    for r in reqs:
        cmd += ["-r", r]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0 and "externally-managed" in (p.stderr or ""):
        p = subprocess.run(cmd + ["--break-system-packages"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print(p.stdout[-1500:], p.stderr[-1500:])
        sys.exit("준비 실패: 파이썬 패키지 설치")


def convert():
    from kordoc_tool import kordoc_cmd
    md = DATA / "md"
    if md.exists():
        shutil.rmtree(md)
    md.mkdir(parents=True)
    files = source_files(SRC)
    if not files:
        sys.exit("준비 실패: 원본/ 에 변환할 파일이 없습니다.")
    run([*kordoc_cmd(), "--jobs", "4", "-d", md, *files], "한글 파일 변환")
    print(run([sys.executable, "scripts/build_db.py"], "규정 DB 만들기").strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="형태소 분석기까지 설치")
    ap.add_argument("--no-install", action="store_true")
    ap.add_argument("--allow-changes", action="store_true", help="지문과 달라도 멈추지 않고 보여 주기만 한다(이어 하는 중)")
    args = ap.parse_args()

    if not args.no_install:
        install(args.full)
    stamp = setup_stamp(SRC)
    if STAMP.exists() and STAMP.read_text(encoding="utf-8").strip() == stamp and (DATA / "snapshot_texts.json").exists():
        print("이미 준비되어 있습니다.")
        return
    convert()

    import check_changes as CC
    from check_knowledge import load_domains
    rules = CC.load_rules(CC.RULES)
    if not CC.SNAPSHOT.exists():
        sys.exit("준비 실패: 저장된 지문(knowledge/source_snapshot.json)이 없습니다.")
    snap = json.loads(CC.SNAPSHOT.read_text(encoding="utf-8"))
    _, cards = load_domains(tolerant=True)
    changes, _eff, stale, _rel = CC.compare(rules, snap, cards)
    problems = baseline_problems(changes, stale)
    for x in problems:
        print(x)
    if problems and not args.allow_changes:
        sys.exit(1)
    if not problems:
        _, texts = CC.take(rules, None, snap, {})
        CC.TEXTS.write_text(json.dumps(texts, ensure_ascii=False), encoding="utf-8")
    if not problems:  # 문제가 있었으면 표지를 남기지 않아, 그냥 다시 돌리면 늘 다시 확인한다
        STAMP.write_text(stamp + "\n", encoding="utf-8")
    print(f"준비 끝: 규정 {len(rules)}개, 지문과 같음." if not problems else "준비 끝(지문과 다른 곳이 있습니다).")


if __name__ == "__main__":
    main()
