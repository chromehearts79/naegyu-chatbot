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

sys.exit(1 if FAIL else 0)
