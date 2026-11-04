"""새로 올라온 내규 파일을 저장소 자료와 미리 비교한다(실제 data·knowledge 는 바꾸지 않는다).

임시 폴더에 build_db.py 와 변환본(data/md)만 복사해 새 글을 끼워 넣고 다시 쪼갠 뒤,
기존 감지 도구(check_changes)로 바뀐 조문·다시 확인할 카드·계산기를 찾는다.
정 담당 PC(저장소가 있는 PC)에서만 쓴다.
"""
import difflib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alio_types import CompareResult  # noqa: E402
import check_changes as cc  # noqa: E402
from check_knowledge import load_domains  # noqa: E402

KORDOC = "kordoc@4.24.42"
NEW_CODE = "Ⅳ-99"  # 분류 코드가 아직 없는 새 내규의 임시 파일 이름용
HERE = Path(__file__).resolve().parent
MD_DIR = cc.ROOT / "data" / "md"


def kordoc_cmd():
    """윈도우에서는 which 가 npx.cmd 를 찾는다. npx 가 없으면 None 이 들어간다."""
    return [shutil.which("npx"), "-y", KORDOC]


def nfc(s):
    return unicodedata.normalize("NFC", s)


def squash(text):
    """공백·표 모양 글자를 지운 비교용 글자"""
    return re.sub(r"[\s*|\-:<>/·ㆍ]", "", unicodedata.normalize("NFKC", text))


def is_annex_md(name):
    return "위임전결기준" in name or "별표" in name


def place(code, name, fname, existing):
    """새 파일이 들어갈 변환본 이름. existing 은 {NFC 이름: 실제 이름}"""
    xlsx = fname.lower().endswith(".xlsx")
    for n, real in sorted(existing.items()):
        if n.startswith("[") or not n.startswith(code + ".") or n.endswith("/"):
            continue
        if is_annex_md(n) == xlsx:
            return real
    return None if xlsx else f"{code}. {name}.md"


def compare_md(code, name, new_md):
    """new_md: 원래 파일 이름 → 변환 글. 임시 사본에서 다시 쪼개 비교한다."""
    code = code or NEW_CODE
    res = CompareResult([], [], [], [], [], [], [], False)
    try:
        existing = {nfc(p.name): p.name for p in MD_DIR.glob("*.md")}
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            (tmp / "scripts").mkdir()
            (tmp / "data" / "md").mkdir(parents=True)
            shutil.copy(HERE / "build_db.py", tmp / "scripts" / "build_db.py")
            for p in MD_DIR.glob("*.md"):
                shutil.copy(p, tmp / "data" / "md" / p.name)
            old_all, new_all, found, used = [], [], True, set()
            for fname, text in new_md.items():
                target = place(code, name, fname, existing)
                if target in used:  # 같은 자리에 둘이 들어가면 하나만 비교하게 되므로 비교하지 않는다
                    res.error = f"같은 종류의 파일이 둘 이상이라 비교하지 않습니다({fname})"
                    return res
                used.add(target)
                if target is None:
                    res.error = f"별표 변환본을 둘 자리가 없습니다({fname})"
                    return res
                path = tmp / "data" / "md" / target
                if target in existing.values():
                    old_all.append((MD_DIR / target).read_text(encoding="utf-8"))
                else:
                    found = False
                new_all.append(text)
                path.write_text(text, encoding="utf-8")
            run = subprocess.run([sys.executable, "-X", "utf8", str(tmp / "scripts" / "build_db.py")], capture_output=True, text=True, encoding="utf-8")
            if run.returncode:
                res.error = "조문 나누기 실패: " + (run.stderr or run.stdout)[-300:]
                return res
            new_rules = cc.load_rules(tmp / "data" / "rules.json")
        if name not in new_rules:
            res.error = f"나눈 결과에 '{name}' 이(가) 없습니다"
            return res
        snap = json.loads(cc.SNAPSHOT.read_text(encoding="utf-8"))
        _, cards = load_domains(tolerant=True)
        changes, _, stale, related = cc.compare(new_rules, snap, cards)
        mine = {k[1]: v for k, v in changes.items() if k[0] == name}
        is_para = lambda u: "항" in u and "조제" in u  # noqa: E731
        res.changed_units = [u for u, v in mine.items() if v != "added" and not is_para(u)]
        res.added_units = [u for u, v in mine.items() if v == "added" and not is_para(u)]
        res.stale_cards = [c for c, items in stale.items() if any(i["rule"] == name for i in items)]
        res.related_cards = [c for c, items in related.items() if any(i["rule"] == name for i in items)]
        res.calcs = [v["title"] for v in cc.calc_stale(changes, new_rules).values() if any(x["cite"].startswith(name + " ") for x in v["cites"])]
        texts = json.loads(cc.TEXTS.read_text(encoding="utf-8")).get(name, {}) if cc.TEXTS.exists() else {}
        new_units = cc.units_of(new_rules[name])
        res.before_after = [(u, texts.get(u, ""), new_units.get(u, "")) for u in res.changed_units[:20]]
        res.whole_same = bool(found and old_all) and squash("\n".join(old_all)) == squash("\n".join(new_all))
        if not res.whole_same:
            diff = difflib.unified_diff("\n".join(old_all).splitlines(), "\n".join(new_all).splitlines(), "이전", "이후", lineterm="", n=0)
            res.outside_diff = list(diff)[:40]
    except Exception as e:  # 비교 실패가 실행 전체를 멈추지 않게 한다
        res.error = f"{type(e).__name__}: {e}"
    return res


def convert(files, out):
    """파일들을 kordoc 으로 변환해 {원래 이름: 글}. 실패하면 예외."""
    cmd = kordoc_cmd()
    if not cmd[0]:
        raise RuntimeError("npx 를 찾지 못했습니다(Node.js 필요)")
    src = Path(out) / "in"
    dst = Path(out) / "md"
    src.mkdir()
    dst.mkdir()
    md = {}
    for i, (fname, data) in enumerate(files):
        ext = Path(fname).suffix.lower()
        path = src / f"f{i}{ext}"
        path.write_bytes(data)
        run = subprocess.run(cmd + ["-d", str(dst), str(path)], capture_output=True, text=True, encoding="utf-8", timeout=300)
        got = dst / f"f{i}.md"
        if run.returncode or not got.exists():
            raise RuntimeError(f"변환 실패({fname}): " + (run.stderr or run.stdout)[-200:])
        md[fname] = got.read_text(encoding="utf-8")
    return md


def compare_rule(name, code, files):
    """files: [(파일 이름, 내용)]. 변환 뒤 compare_md. 예외를 내지 않고 error 에 적는다."""
    try:
        with tempfile.TemporaryDirectory() as td:
            return compare_md(code, name, convert(files, td))
    except Exception as e:
        return CompareResult([], [], [], [], [], [], [], False, error=f"{type(e).__name__}: {e}")
