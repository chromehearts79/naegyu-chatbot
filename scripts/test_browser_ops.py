"""브라우저 운영 시험.

  python3 -X utf8 scripts/test_browser_ops.py
"""
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
FAIL = []


def ok(cond, msg):
    print(("✓ " if cond else "✗ ") + msg)
    if not cond:
        FAIL.append(msg)


import kordoc_tool as K  # noqa: E402
ok(K.KORDOC == "kordoc@4.24.1", "kordoc 판은 4.24.1")
pkg = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
ok(pkg["dependencies"]["kordoc"] == "4.24.1" and pkg["dependencies"]["jsdom"] == "24.1.3" and pkg["dependencies"]["cfb"] == "1.2.2", "패키지 판을 고정한다(^ 없음)")
for rel in ("scripts/update_rules.py", "scripts/convert.sh", "scripts/alio_compare.py"):
    text = (ROOT / rel).read_text(encoding="utf-8")
    ok("npx -y kordoc " not in text and not re.search(r'"-y",\s*"kordoc"', text) and "kordoc@4.24.42" not in text, f"{rel}: 판 없는 kordoc 호출이 없다")
for rel in ("scripts/update_rules.py", "scripts/cut_forms.cjs", "scripts/convert.sh"):
    ok("CloudDocs" not in (ROOT / rel).read_text(encoding="utf-8"), f"{rel}: iCloud 경로가 없다")
ok((ROOT / ".gitattributes").read_text(encoding="utf-8").strip().startswith("* -text"), "줄바꿈 변환을 끈다")
ign = (ROOT / ".gitignore").read_text(encoding="utf-8")
ok("원본/[[]*" in ign, "[ 로 시작하는 원본은 올리지 않는다")
names = sorted(p.name for p in (ROOT / "원본").iterdir() if p.is_file())
manifest = json.loads((ROOT / "knowledge" / "source_files.json").read_text(encoding="utf-8"))["files"]
ok(names == sorted(manifest) and not any(n.startswith("[") for n in names), "원본이 원본 기록과 같고 [ 파일이 없다(새 내규가 늘어도 이 시험은 그대로 통과한다)")

import setup_project as SP  # noqa: E402
ok(SP.baseline_problems({}, {}) == [], "바뀐 곳이 없으면 통과")
pr = SP.baseline_problems({("복무세칙", "제4조"): "changed", ("복무세칙", "제4조제1항"): "changed"}, {"card-a": [{}]})
ok(len(pr) >= 1 and any("복무세칙 제4조" in x for x in pr) and any("1장" in x for x in pr), "바뀐 조문과 다시 확인 문답 수를 알린다")
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    (td / "s").mkdir(); (td / "s" / "r.hwp").write_bytes(b"1")
    a = SP.setup_stamp(td / "s")
    (td / "s" / "r.hwp").write_bytes(b"2")
    ok(a != SP.setup_stamp(td / "s"), "원본이 바뀌면 준비를 다시 한다")
hook = json.dumps(json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")), ensure_ascii=False)
ok("setup_project.py" in hook and "CLAUDE_CODE_REMOTE" in hook and "--allow-changes" in hook, "클라우드 세션 시작 때만 준비를 돌리고, 이어 하는 중이면 막지 않는다")

import check_upload as CU  # noqa: E402
ok(CU.scan_text("a", "연락처 hong" + "@example.go.kr") and CU.scan_text("a", "010-" + "1234-5678") and CU.scan_text("a", "900101-" + "1234567"), "메일·전화·주민번호 꼴을 잡는다")
ok(not CU.scan_text("a", "예시 02-123-4567") and not CU.scan_text("a", "신고 044-200-7752"), "알려진 공개 번호는 통과")
ok(CU.scan_text("a", "02-2610-" + "6000"), "그 밖의 전화번호는 잡는다")
ok(CU.scan_text("a", "sk-" + "a" * 30) and CU.scan_text("a", "ghp_" + "a" * 30) and CU.scan_text("a", "AKIA" + "A" * 16), "API 키 꼴을 잡는다")
ok(not CU.scan_text("a", "noreply@anthropic.com") and not CU.scan_text("a", "담당자 이메일 : ○○○○○○@posid.or.kr"), "커밋 꼬리표와 가린 주소는 통과")
ok(not CU.scan_text("a", "xxxx" + "@posid.or.kr") and not CU.scan_text("a", "나머지 ****" + "@posid.or.kr"), "x·* 로 가린 주소도 통과")
ok(CU.forbidden_paths(["원본/[개정근거] 시행문.hwp", "knowledge/contacts.json", "reports/contacts/x.md", "scripts/contacts_report.py", "원본/Ⅰ. 정관.hwpx"]) == ["원본/[개정근거] 시행문.hwp", "knowledge/contacts.json", "reports/contacts/x.md", "scripts/contacts_report.py"], "올리면 안 되는 경로를 잡는다")
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    (td / "[개정근거] 시행문.md").write_text("hong" + "@example.go.kr", encoding="utf-8")
    ok(CU.scan_md_dir(td) == [], "올리지 않는 [ 변환본은 보지 않는다")
    (td / "복무세칙.md").write_text("hong" + "@example.go.kr", encoding="utf-8")
    ok(len(CU.scan_md_dir(td)) == 1, "올라갈 내규 변환본은 본다")

import subprocess  # noqa: E402


def run_check(repo, *flags):
    r = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts" / "check_upload.py"), *flags], cwd=repo, capture_output=True)
    return r.returncode, r.stdout.decode("utf-8", "replace")


def git_in(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t" + "@example.invalid", *args], cwd=repo, check=True, capture_output=True)


def make_repo(td, files):
    td = Path(td)
    git_in(td, "init", "-q")
    for rel, data in files.items():
        f = td / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)
    git_in(td, "add", "-f", "--", *files)
    git_in(td, "commit", "-q", "-m", "t")
    return td


addr = ("hong" + "@example.go.kr").encode()
with tempfile.TemporaryDirectory() as td:
    r = make_repo(td, {"a.txt": "깨끗".encode()})
    code, out = run_check(r)
    ok(code == 0 and "✓" in out, "깨끗한 저장소는 통과한다")
with tempfile.TemporaryDirectory() as td:
    r = make_repo(td, {"a.md": b"mail " + addr})
    code, out = run_check(r)
    ok(code == 1 and "a.md 1번째 줄" in out, "올라간 파일에 메일 꼴이 있으면 실패하고 파일과 줄을 알린다")
with tempfile.TemporaryDirectory() as td:
    r = make_repo(td, {"docs/[x]/b.md": b"ok"})
    code, out = run_check(r)
    ok(code == 1 and "docs/[x]/b.md" in out, "안쪽 폴더의 [ 파일도 실패")
with tempfile.TemporaryDirectory() as td:
    r = make_repo(td, {"c.txt": "연락처 ".encode("cp949") + addr})
    code, out = run_check(r)
    ok(code == 1 and "c.txt" in out and "점검하지 못함" in out, "UTF-8이 아닌 글 파일은 건너뛰지 않고 실패")
with tempfile.TemporaryDirectory() as td:
    r = make_repo(td, {"d.bin": b"\x00\x01\x02", "e.zzz": b"\x00\x01"})
    code, out = run_check(r)
    ok(code == 0 and "d.bin" in out and "e.zzz" in out and ".bin 1개" in out, "글 아닌 알 수 없는 파일은 통과하되 건너뛴 목록에 이름이 나온다")
with tempfile.TemporaryDirectory() as td:
    r = make_repo(td, {"f.md": b"clean"})
    (r / "f.md").write_bytes(b"mail " + addr)
    code, out = run_check(r)
    ok(code == 0 and "주의" in out and "f.md" in out, "작업 폴더에서만 고친 내용은 HEAD 를 보므로 통과하되 경고한다")
    git_in(r, "add", "f.md")
    code, out = run_check(r, "--staged")
    ok(code == 1 and "f.md 1번째 줄" in out, "--staged 는 인덱스를 본다")
with tempfile.TemporaryDirectory() as td:
    r = make_repo(td, {"g.md": b"mail " + addr})
    (r / "g.md").write_bytes(b"clean")
    git_in(r, "commit", "-qam", "fix")
    code, out = run_check(r)
    ok(code == 0, "지금 내용이 깨끗하면 기본 점검은 통과")
    code, out = run_check(r, "--history")
    ok(code == 1 and "기록" in out and "t" + "@example.invalid" in out, "--history 는 지난 기록의 메일 꼴을 잡고 작성자 목록을 보인다")
with tempfile.TemporaryDirectory() as td:
    r = make_repo(td, {"h.md": b"x"})
    (r / "data" / "md").mkdir(parents=True)
    (r / "data" / "md" / "i.md").write_bytes("깨".encode("cp949") * 3 + b"\xff")
    code, out = run_check(r)
    ok(code == 1 and "i.md" in out, "읽지 못한 내규 변환본도 문제로 알린다")
with tempfile.TemporaryDirectory() as td:
    code, out = run_check(td)
    ok(code == 1 and "점검하지 못했습니다" in out, "git 저장소가 아니면 통과시키지 않는다")

if (ROOT / "data" / "rules.json").exists():
    import blind_check as B  # noqa: E402
    from check_knowledge import load_domains  # noqa: E402
    cards = load_domains()[1]
    usable = [c for c in cards if len(c["facts"]) >= 2 and all(len(str(f["value"])) >= 4 for f in c["facts"])]
    card, card2 = usable[0], usable[1]
    keep = (B.WORK, B.OUT_MD, B.OUT_JSON)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        B.WORK, B.OUT_MD, B.OUT_JSON = td / "work", td / "b.md", td / "b.json"
        B.OUT_JSON.write_text(json.dumps([{"card": cards[-1]["id"], "label": "옛", "mine": "a", "theirs": "a", "cite": "x", "step1": "일치", "step1_note": "", "verdict": "일치"}], ensure_ascii=False), encoding="utf-8")
        q = json.loads(B.prepare([card["id"], card2["id"]]).read_text(encoding="utf-8"))
        raw = json.dumps(q, ensure_ascii=False)
        ok(q[0]["card"] == card["id"] and "prompt" in q[0], "문제 파일을 만든다")
        ok(all(str(f["value"]) not in raw for c in (card, card2) for f in c["facts"] if len(str(f["value"])) >= 6 and not any(str(f["value"]) in x["context"] for x in q)), "문제 파일에 문답의 답이 들어가지 않는다")
        right = [f["value"] for f in card["facts"]]
        rows, jq = B.first_pass({card["id"]: right}, "시험AI")
        ok(all(r["step1"] == B.compare(r["mine"], r["theirs"])[0] == "일치" for r in rows) and jq is None, "답이 같으면 지금 규칙대로 일치")
        ok(B.remaining() == [card2["id"]], "끝난 만큼 쌓고 남은 카드를 안다")
        try:
            B.finish({}, "시험AI")
            ok(False, "남은 카드가 있으면 마무리하지 않는다")
        except ValueError:
            ok(True, "남은 카드가 있으면 마무리하지 않는다")
        B.first_pass({card2["id"]: [f["value"] for f in card2["facts"]]}, "시험AI")
        res = B.finish({}, "시험AI")
        out = json.loads(B.OUT_JSON.read_text(encoding="utf-8"))
        ok(any(r["card"] == card["id"] and r["ai"] == "시험AI" for r in out) and res["일치"] >= 1 and not (td / "work").exists(), "채점 결과에 AI 이름을 남기고 작업 파일을 지운다")
        ok(any(r["card"] == cards[-1]["id"] for r in out), "고르지 않은 카드의 지난 결과를 그대로 둔다")
        B.prepare([card["id"]])
        rows, jq = B.first_pass({card["id"]: ["없음"] * len(card["facts"])}, "시험AI")
        ok(jq is not None and json.loads(jq.read_text(encoding="utf-8")) and all(r["step1"] == "판정 필요" for r in rows), "어긋나면 2차 문제를 만든다")
        keys = [x["key"] for x in json.loads(jq.read_text(encoding="utf-8"))]
        B.finish({k: {"판정": "아니오", "이유": "시험"} for k in keys}, "시험AI")
        out = json.loads(B.OUT_JSON.read_text(encoding="utf-8"))
        ok(any(r["card"] == card["id"] and r["verdict"] == "확인 필요" for r in out), "2차에서 아니오면 확인 필요")
    B.WORK, B.OUT_MD, B.OUT_JSON = keep
    s1, s2 = B.sample_cards(20), B.sample_cards(20)
    doms = {c["id"]: c["domain"] for c in cards}
    ok(s1 == s2 and len(s1) == 20 and len({doms[i] for i in s1}) >= 2, "고정 시드로 분야를 섞어 고른다")
    ok("11434" not in (ROOT / "scripts" / "blind_check.py").read_text(encoding="utf-8"), "로컬 모델 호출이 없다")

sys.exit(1 if FAIL else 0)
