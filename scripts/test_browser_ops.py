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
ok("원본/**/[[]*" in ign, "[ 로 시작하는 원본은 올리지 않는다")
names = sorted(p.name for p in (ROOT / "원본").iterdir() if p.is_file() and not p.name.startswith("."))
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
    import subprocess  # noqa: E402
    wdir = ROOT / "reports" / "blind_work"
    before = sorted(x.name for x in wdir.iterdir()) if wdir.exists() else None
    bad = subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts" / "blind_check.py"), "prepare", cards[0]["id"], "없는카드이름"], capture_output=True, text=True, encoding="utf-8")
    after = sorted(x.name for x in wdir.iterdir()) if wdir.exists() else None
    ok(bad.returncode != 0 and "없는카드이름" in (bad.stderr + bad.stdout) and before == after, "prepare 에 맞지 않는 인자가 있으면 오류로 멈추고 작업 파일을 건드리지 않는다")

import datetime  # noqa: E402
import alio_report as RP  # noqa: E402
import alio_types as T  # noqa: E402
import watch_ci as WC  # noqa: E402


def cmp_res(**kw):
    base = dict(changed_units=[], stale_cards=[], related_cards=[], calcs=[], added_units=[], before_after=[], outside_diff=[], whole_same=False)
    base.update(kw)
    return T.CompareResult(**base)


ok(WC.kst_date("2026-11-08T16:00:00Z") == "2026-11-09", "GitHub 시각을 한국 날짜로 바꾼다")
F = T.Finding(name="복무세칙", code="Ⅲ-3-1", idx="9387", verdict=T.V_SUSPECT, title="복무세칙", st_date="2026.11.02", mod="2026.11.09", file_date="2026.11.02", ext=".hwp", values={"mod": "2026.11.09", "st_date": "2026.11.02", "file_no": "101"}, target_name="Ⅲ-3-1. 복무세칙.hwp", saved_dir="대기/복무세칙_20261102", days=3, notes=["날짜가 그대로라 재게시일 수 있음"],
              compare=cmp_res(changed_units=["제19조"], stale_cards=["a", "b"], related_cards=["c"], calcs=["가족수당"], before_after=[("제19조", "옛 글", "새 글")]))
body = WC.issue_body(F, "2026-11-09")
ok(WC.marker("9387") in body and "제19조" in body and "2장" in body and "가족수당" in body and "대기/복무세칙_20261102" in body and "Ⅲ-3-1. 복무세칙.hwp" in body and "claude.ai/code" in body and "재게시" in body, "이슈 글: 조문·문답·계산기·파일 위치·넣을 이름·참고·다음 할 일")
ok("확인함:" in body, "이슈 글에 확인함 방법이 있다")
ok(WC.issue_title(F) == "개정 의심: 복무세칙", "이슈 제목")
dirty = "복무@홍길동 `코드` <script>\n줄바꿈 | [링크](x)"
c = WC.clean_md(dirty)
ok("@홍" not in c and "`" not in c and "<script" not in c and "\n" not in c and "](" not in c, "ALIO 글자를 무해하게 만든다")
ok(WC.clean_md("대기/복무_세칙.v-2") == "대기/복무_세칙.v-2", "경로에 쓰는 글자는 그대로 둔다")
F2 = T.Finding(name=dirty, code="", idx="1", verdict=T.V_NEW, title=dirty, st_date="2026.11.02", mod="2026.11.09")
b2 = WC.issue_body(F2, "2026-11-09")
ok("@홍" not in b2 and "<script" not in b2 and "@" not in WC.issue_title(F2), "지저분한 이름도 글을 깨지 않고 알림을 보내지 않는다")
F3 = T.Finding(name="큰 내규", code="X", idx="2", verdict=T.V_SUSPECT, title="큰 내규", compare=cmp_res(changed_units=["별표"], before_after=[("별표", "옛" * 50000, "새" * 50000)]))
b3 = WC.issue_body(F3, "2026-11-09")
ok(len(b3) <= 60000 and "잘렸" in b3 and WC.marker("2") in b3 and "다음에 할 일" in b3, "긴 글은 한도 안으로 자르고 알린다")
b4 = WC.issue_body(F3, "2026-11-09", limit=800)
ok(len(b4) <= 800 and WC.marker("2") in b4 and "다음에 할 일" in b4 and "claude.ai/code" in b4, "아주 작은 한도에서도 표지와 다음 할 일은 남는다")

OPEN = {"number": 7, "title": "개정 의심: 복무세칙", "body": WC.marker("9387"), "createdAt": "2026-11-02T00:00:00Z", "lastCommentDate": "2026-11-02"}
none = T.Finding(name="복무세칙", code="Ⅲ-3-1", idx="9387", verdict=T.V_NONE, title="복무세칙")
acts = WC.plan_actions([F], [], "2026-11-09", ["담당"])
ok([a["kind"] for a in acts] == ["create"] and acts[0]["assignees"] == ["담당"] and acts[0]["labels"] == ["개정 의심"], "새 개정 의심은 이슈를 만들고 담당자를 지정한다")
kinds = [a["kind"] for a in WC.plan_actions([F], [OPEN], "2026-11-09", [])]
ok(kinds == ["edit", "comment"], "그대로면 글을 고치고 매주 댓글을 단다")
ok([a["kind"] for a in WC.plan_actions([F], [dict(OPEN, lastCommentDate="2026-11-09")], "2026-11-09", [])] == ["edit"], "같은 날 다시 돌려도 댓글이 겹치지 않는다")
ok([a["kind"] for a in WC.plan_actions([F], [OPEN], "2026-11-09", [], weekly=False)] == ["edit"], "합친 뒤 판정에서는 댓글을 달지 않는다")
ok([a["kind"] for a in WC.plan_actions([none], [OPEN], "2026-11-09", [])] == ["close"], "해소되면 닫는다")
ok([a["kind"] for a in WC.plan_actions([], [OPEN], "2026-11-09", [])] == ["close"], "목록에서 없어진 내규의 이슈도 닫는다")
ok(WC.plan_actions([none], [{"number": 9, "title": "다른 글", "body": "안녕", "createdAt": "2026-11-02T00:00:00Z", "lastCommentDate": ""}], "2026-11-09", []) == [], "사람이 쓴 다른 이슈는 건드리지 않는다")
ok(WC.plan_actions([none], [], "2026-11-09", []) == [], "변동 없으면 이슈 일이 없다")
for v in (T.V_DONE, T.V_SAME_TEXT):
    ok(WC.plan_actions([T.Finding(name="a", code="", idx="5", verdict=v)], [], "2026-11-09", []) == [], f"{v} 는 이슈를 만들지 않는다")
ok("미반영 공지" in WC.week_comment(T.Finding(name="a", code="", idx="5", verdict=T.V_SUSPECT, days=RP.LATE_DAYS + 1), "2026-11-09") and "미반영 공지" not in WC.week_comment(T.Finding(name="a", code="", idx="5", verdict=T.V_SUSPECT, days=RP.LATE_DAYS - 1), "2026-11-09"), "14일이 넘으면 미반영 공지를 안내한다")
ok("이번 주 변동 없음" in WC.heartbeat_text([none], "2026-11-09") and "복무세칙" in WC.heartbeat_text([F, none], "2026-11-09"), "매주 기록 문구")
ok([a["kind"] for a in WC.heartbeat_actions([none], None, "2026-11-09")] == ["create"], "기록 이슈가 없으면 만든다")
PIN = {"number": 1, "title": "매주 확인 기록", "body": "", "createdAt": "2026-11-02T00:00:00Z", "lastCommentDate": "2026-11-02"}
ok([a["kind"] for a in WC.heartbeat_actions([none], PIN, "2026-11-09")] == ["comment"] and WC.heartbeat_actions([none], dict(PIN, lastCommentDate="2026-11-09"), "2026-11-09") == [], "기록 댓글은 하루 한 번")
fa = WC.failure_actions("ALIO 접속 실패", [], "2026-11-09", ["담당"])
ok(fa[0]["kind"] == "create" and "확인 실패" in fa[0]["title"] and "ALIO 접속 실패" in fa[0]["body"], "실패하면 실패 이슈를 만든다")
ok([a["kind"] for a in WC.failure_actions("또 실패", [{"number": 3, "title": "확인 실패", "body": fa[0]["body"], "createdAt": "2026-11-02T00:00:00Z", "lastCommentDate": "2026-11-02"}], "2026-11-09", [])] == ["comment"], "실패 이슈를 겹쳐 만들지 않는다")
ok("새 판" in WC.failure_actions("시험 실패", [], "2026-11-09", [], kind="release")[0]["title"], "새 판 실패는 따로 알린다")
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    F.files = [("복무:세칙(2026).hwp", b"x")]
    p = WC.save_wait(F, td)
    ok(p.startswith("대기/") and any((td / p).iterdir()), "받은 파일을 대기 폴더에 두고 저장소 기준 경로를 돌려준다")
    (td / "대기" / "복무세칙_시행_20261102").mkdir()
    F.file_date = "2026.11.09"
    p2 = WC.save_wait(F, td)
    names = sorted(x.name for x in (td / "대기").iterdir())
    ok(names == ["복무세칙_20261109", "복무세칙_시행_20261102"] and p2.endswith("복무세칙_20261109"), "같은 내규의 옛 폴더만 지운다")
    ok(WC.drop_wait("복무세칙", td) == 1 and [x.name for x in (td / "대기").iterdir()] == ["복무세칙_시행_20261102"], "해소되면 그 내규 폴더만 지운다")
    F.file_date = "2026.11.02"
    F.files = []


class FakeGh:
    def __init__(self, issues=None, broken=False, no_assign=False):
        self.calls, self.issues, self.broken, self.no_assign, self.stdin = [], issues or [], broken, no_assign, []

    def __call__(self, args, stdin=None):
        self.calls.append(args)
        self.stdin.append(stdin)
        if self.broken or (self.no_assign and "--assignee" in args):
            raise RuntimeError("gh 실패")
        return json.dumps(self.issues) if args[:2] == ["issue", "list"] else ""


g = FakeGh(no_assign=True)
WC.apply_actions(WC.plan_actions([F], [], "2026-11-09", ["없는아이디"]), g)
ok(len(g.calls) == 2 and "--assignee" not in g.calls[-1] and "담당자 지정" in (g.stdin[-1] or ""), "담당자 지정이 안 돼도 이슈는 만들고 글에 적는다")
g = FakeGh()
WC.apply_actions([{"kind": "create", "title": "t", "body": "b", "labels": [], "assignees": []}, {"kind": "edit", "number": 4, "title": "t", "body": "b"}, {"kind": "comment", "number": 4, "body": "c"}, {"kind": "close", "number": 4}], g)
ok(g.calls == [["issue", "create", "--title", "t", "--body-file", "-"], ["issue", "edit", "4", "--title", "t", "--body-file", "-"], ["issue", "comment", "4", "--body-file", "-"], ["issue", "close", "4"]], "gh 명령 모양")
try:
    WC.apply_actions([{"kind": "create", "title": "t", "body": "b", "labels": [], "assignees": []}], FakeGh(broken=True))
    ok(False, "담당자 없이 만들기가 실패하면 알린다")
except RuntimeError:
    ok(True, "담당자 없이 만들기가 실패하면 알린다")


def fake_http_down(path, body):
    raise WC.AlioError("접속 실패")


with tempfile.TemporaryDirectory() as td:
    g, sleeps = FakeGh(), []
    rc = WC.run_ci(fake_http_down, g, None, datetime.datetime(2026, 11, 9, 9, 0), Path(td), sleep=sleeps.append)
    joined = json.dumps(g.calls, ensure_ascii=False)
    ok(rc == 1 and "확인 실패" in joined and "이번 주 변동 없음" not in joined, "ALIO 접속 실패는 변동 없음으로 끝나지 않는다")
    ok(sleeps == [300], "실패하면 5분 뒤 한 번 더 돌린다")
    ok(json.loads((Path(td) / "reports" / "alio_watch" / "last_run.json").read_text(encoding="utf-8"))["ok"] is False, "실패해도 실행 기록을 남긴다")
    ok(WC.run_ci(fake_http_down, FakeGh(broken=True), None, datetime.datetime(2026, 11, 9, 9, 0), Path(td), sleep=lambda s: None) == 1, "이슈까지 못 쓰면 작업을 실패로 끝낸다")

# ---- 고침 1회차: 대기 폴더 보호, 실패 댓글 겹침, 성공 경로, 설정 실패 ----
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    (td / "대기" / "복무세칙").mkdir(parents=True)
    (td / "대기" / "복무세칙_20260101").mkdir()
    ok(WC.drop_wait("복무세칙", td) == 1 and [x.name for x in (td / "대기").iterdir()] == ["복무세칙"], "이름만 있는 사람이 만든 폴더는 지우지 않는다(drop_wait)")
    SW = T.Finding(name="복무세칙", code="", idx="1", verdict=T.V_SUSPECT, file_date="2026.11.02", files=[("a.hwp", b"x")])
    WC.save_wait(SW, td)
    ok(sorted(x.name for x in (td / "대기").iterdir()) == ["복무세칙", "복무세칙_20261102"], "이름만 있는 폴더는 save_wait 에도 남는다")
FAILISS = {"number": 3, "title": "확인 실패: ALIO 매주 확인", "body": WC._fail_marker("watch"), "createdAt": "2026-11-02T00:00:00Z", "lastCommentDate": "2026-11-09"}
ok(WC.failure_actions("또 실패", [FAILISS], "2026-11-09", []) == [], "같은 날 실패 댓글을 겹쳐 달지 않는다")
ok([a["kind"] for a in WC.failure_actions("또 실패", [dict(FAILISS, lastCommentDate="2026-11-02")], "2026-11-09", [])] == ["comment"], "다른 날이면 실패 댓글을 단다")

NOW = datetime.datetime(2026, 11, 9, 9, 0)


BOT = {"is_bot": True, "login": "app/github-actions"}


class StateGh(FakeGh):
    """이슈 목록과 댓글 날짜를 기억하는 가짜 gh"""
    def __init__(self, issues, fail_on=None):
        super().__init__(issues)
        self.fail_on = fail_on

    def __call__(self, args, stdin=None):
        if self.fail_on and args[:2] == ["issue", self.fail_on]:
            self.calls.append(args)
            raise RuntimeError("gh 실패")
        out = super().__call__(args, stdin)
        if args[:2] == ["issue", "comment"]:
            for i in self.issues:
                if str(i["number"]) == args[2]:
                    i.setdefault("comments", []).append({"createdAt": "2026-11-09T01:00:00Z"})
        if args[:2] == ["issue", "create"]:
            return "https://github.com/x/y/issues/12"
        return out


def stub_collect(findings):
    real = WC._collect
    WC._collect = lambda h, c, t: findings()
    return real


def mk_issues():
    return [{"number": 4, "title": "개정 의심: 옛규정", "body": WC.marker("5"), "createdAt": "2026-11-02T00:00:00Z", "comments": [], "author": BOT},
            {"number": 3, "title": "확인 실패: ALIO 매주 확인", "body": WC._fail_marker("watch"), "createdAt": "2026-11-02T00:00:00Z", "comments": [], "author": BOT},
            {"number": 1, "title": "매주 확인 기록", "body": "", "createdAt": "2026-11-02T00:00:00Z", "comments": [], "author": BOT}]


def mk_findings():
    return [T.Finding(name="복무세칙", code="Ⅲ-3-1", idx="9387", verdict=T.V_SUSPECT, mod="2026.11.02", file_date="2026.11.02", files=[("a.hwp", b"x")]),
            T.Finding(name="옛규정", code="", idx="5", verdict=T.V_NONE)]


real_collect = stub_collect(mk_findings)
try:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "대기" / "옛규정_20261001").mkdir(parents=True)
        (td / "대기" / "옛규정").mkdir()
        g = StateGh(mk_issues())
        rc = WC.run_ci(None, g, None, NOW, td, assignees=["담당"])
        closes = [c[2] for c in g.calls if c[:2] == ["issue", "close"]]
        lr = json.loads((td / "reports" / "alio_watch" / "last_run.json").read_text(encoding="utf-8"))
        ok(rc == 0 and lr["ok"] is True and lr["today"] == "2026-11-09", "성공하면 0 과 ok:true 기록")
        ok(sorted(closes) == ["3", "4"], "해소된 이슈와 열린 확인 실패 이슈를 닫는다")
        ok(sorted(x.name for x in (td / "대기").iterdir()) == ["복무세칙_20261102", "옛규정"], "닫힌 내규의 날짜 폴더만 지우고 새로 받은 폴더를 둔다")
        ok((td / "reports" / "alio_watch" / "latest.json").exists() and "a.hwp" not in (td / "reports" / "alio_watch" / "latest.json").read_text(encoding="utf-8"), "latest.json 에는 파일 내용이 없다")
        rc2 = WC.run_ci(None, g, None, NOW, td, assignees=["담당"])
        rec = [c for c in g.calls if c[:3] == ["issue", "comment", "1"]]
        ok(rc2 == 0 and len(rec) == 1, "같은 날 두 번 돌아도 기록 댓글은 한 번")
    with tempfile.TemporaryDirectory() as td:
        g = StateGh(mk_issues(), fail_on="create")
        rc = WC.run_ci(None, g, None, NOW, Path(td), assignees=[])
        lr = json.loads((Path(td) / "reports" / "alio_watch" / "last_run.json").read_text(encoding="utf-8"))
        ok(rc == 1 and lr["ok"] is False, "이슈 일부를 못 쓰면 ok:false 와 1")
    # 설정 실패(비교 모듈을 못 불러옴)도 실패 이슈와 기록으로 끝난다
    WC._collect = lambda h, c, t: c("x", "", [])
    saved = (WC.gh_default, WC.default_http, WC.ROOT, WC.time.sleep, sys.modules.get("alio_compare", "none"))
    with tempfile.TemporaryDirectory() as td:
        g = StateGh([])
        WC.gh_default, WC.default_http, WC.ROOT = g, None, Path(td)
        WC.time.sleep = lambda s: None
        sys.modules["alio_compare"] = None
        try:
            rc = WC.main([])
        finally:
            WC.gh_default, WC.default_http, WC.ROOT, WC.time.sleep = saved[:4]
            if saved[4] == "none":
                sys.modules.pop("alio_compare", None)
            else:
                sys.modules["alio_compare"] = saved[4]
        lr = json.loads((Path(td) / "reports" / "alio_watch" / "last_run.json").read_text(encoding="utf-8"))
        ok(rc == 1 and lr["ok"] is False and any(c[:2] == ["issue", "create"] and "확인 실패" in c[3] for c in g.calls), "비교 모듈을 못 불러와도 확인 실패 이슈를 만들고 1 로 끝난다")
finally:
    WC._collect = real_collect

# ---------- 확인함 댓글 ----------
import confirm_ci as CC2  # noqa: E402
ok(CC2.parse_reason("확인함: 재게시입니다") == "재게시입니다" and CC2.parse_reason(" 확인함 : 사유 ") == "사유" and CC2.parse_reason("확인함:") == "" and CC2.parse_reason("좋아요") is None, "확인함 댓글을 읽는다")
ok(CC2.allowed("OWNER") and CC2.allowed("COLLABORATOR") and CC2.allowed("MEMBER") and not CC2.allowed("NONE") and not CC2.allowed("CONTRIBUTOR"), "쓰기 권한이 있는 사람만")
ok(CC2.idx_of("x " + WC.marker("9387")) == "9387" and CC2.idx_of("없음") is None, "이슈에서 내규를 찾는다")
latest = {"findings": [{"name": "복무세칙", "idx": "9387", "title": "복무세칙", "verdict": T.V_SUSPECT, "values": {"mod": "m2", "st_date": "s2", "file_no": "2"}, "file_date": "f2"}]}
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    sp = td / "seen.json"
    sp.write_text(json.dumps({"taken": "x", "rules": {"9387": {"name": "복무세칙", "title": "복무세칙", "mod": "m1", "st_date": "s1", "file_no": "1", "file_date": "f1"}}}), encoding="utf-8")
    (td / "대기" / "복무세칙_20261102").mkdir(parents=True)
    body = WC.marker("9387")

    def call(comment, who, g, b=body):
        return CC2.handle(comment, who, b, "2026-11-16", latest, sp, g, 7, td)

    g = FakeGh()
    ok(call("확인함: 아무거나", "NONE", g) == "무시" and g.calls == [] and json.loads(sp.read_text(encoding="utf-8"))["rules"]["9387"]["mod"] == "m1", "외부인 댓글에는 아무 일도 없다")
    ok(call("좋아요", "OWNER", g) == "무시" and g.calls == [], "다른 댓글은 무시한다")
    ok(call("확인함: 사유", "OWNER", g, "표시 없음") == "대상 없음" and len(g.calls) == 1 and "알림이 아니라서" in g.stdin[0] and not any("close" in c for c in g.calls), "내규 표시가 없는 이슈에는 알림 글이 아니라고 답한다")
    ok(call("확인함:", "OWNER", g) == "다시 요청" and json.loads(sp.read_text(encoding="utf-8"))["rules"]["9387"]["mod"] == "m1" and "comment" in g.calls[-1], "사유가 비면 다시 적어 달라고 답한다")
    g = FakeGh()
    r = call("확인함: 재게시", "OWNER", g)
    s = json.loads(sp.read_text(encoding="utf-8"))["rules"]["9387"]
    ok(r == "기록함" and s["mod"] == "m2" and s["confirmed"]["reason"] == "재게시" and any("close" in c for c in g.calls), "기록하고 이슈를 닫는다")
    ok(g.calls[0] == ["issue", "comment", "7", "--body-file", "-"] and "재게시" in g.stdin[0] and g.calls[-1] == ["issue", "close", "7"], "댓글을 먼저 달고 마지막에 닫는다")
    ok(not (td / "대기" / "복무세칙_20261102").exists(), "대기 폴더도 지운다")
    g = FakeGh()
    ok(call("확인함: 사유", "OWNER", g, WC.marker("555")) == "대상 없음" and "comment" in g.calls[-1] and not any("close" in c for c in g.calls), "최근 결과에 없는 내규는 기록하지 않는다")

import release_ci as RC  # noqa: E402
ok(RC.tag_of(12) == "v12" and RC.should_release(12, ["v11"]) and not RC.should_release(12, ["v11", "v12"]), "같은 판 번호로 다시 만들지 않는다")
ok(RC.should_release(1, []), "첫 판은 만든다")
ok(RC.number_problem(["knowledge/service/a.json"], 12, ["v12"]) and RC.number_problem(["원본/Ⅰ. 정관.hwpx"], 12, ["v12"]), "문답이 바뀌었는데 번호가 그대로면 실패")
ok(RC.number_problem(["knowledge/service/a.json", "knowledge/site.json"], 13, ["v12"]) is None, "번호를 올렸으면 통과")
ok(RC.number_problem(["docs/유지보수_안내.md", "scripts/x.py"], 12, ["v12"]) is None, "문서·코드만 바꾸면 번호 검사가 없다")
ok(RC.number_problem(["knowledge/alio_seen.json"], 12, ["v12"]) is None, "ALIO 기록만 바뀐 것은 문답 변경이 아니다")
ok(RC.number_problem(["knowledge/service/a.json"], 12, []) is None, "태그가 없으면 번호 검사가 없다")
ok(RC.decide(13, ["v12"], ["knowledge/service/a.json"]) == "publish" and RC.decide(12, [], []) == "publish", "새 번호면 새 판을 만든다")
ok(RC.decide(12, ["v12"], ["docs/x.md"]) == "skip", "문서만 고쳤으면 그냥 지나간다")
ok(RC.decide(12, ["v12"], ["knowledge/service/a.json"]) == "warn", "같은 번호로 문답이 또 합쳐지면 덮어쓰지 않고 알린다")
ok(RC.decide(11, ["v12"], ["knowledge/service/a.json"]) == "warn", "번호가 뒤로 가도 알린다")
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    (td / "dist" / "gpts").mkdir(parents=True); (td / "reports" / "review").mkdir(parents=True)
    (td / "dist" / "index.html").write_text("a", encoding="utf-8"); (td / "dist" / "artifact.html").write_text("b", encoding="utf-8")
    (td / "dist" / "gpts" / "지시문.md").write_text("c", encoding="utf-8")
    (td / "reports" / "review" / "검수표_x.xlsx").write_bytes(b"d"); (td / "reports" / "change_report.md").write_text("e", encoding="utf-8")
    names = sorted(p.name for p in RC.assets(12, td / "dist", td / "reports", td / "out"))
    ok(names == sorted(["naegyu-chatbot-v12.html", "naegyu-chatbot-v12-artifact.html", "gpts-v12.zip", "review-workbooks-v12.zip", "changes-v12.md"]), "새 판 파일은 영문 이름으로 모은다(GitHub이 한글 이름을 깨뜨린다)")
    lab = RC.asset_args(12, [td / "out" / n for n in names])
    ok(len(lab) == 5 and any(a.endswith("naegyu-chatbot-v12.html#내규챗봇_제12판.html") for a in lab) and any(a.endswith("review-workbooks-v12.zip#검수표_제12판.zip") for a in lab) and any(a.endswith("changes-v12.md#바뀐_내용_제12판.md") for a in lab), "한글 이름표를 `파일#이름표` 로 붙인다")
    (td / "dist" / "index.html").unlink()
    try:
        RC.assets(12, td / "dist", td / "reports", td / "out2")
        ok(False, "빠진 파일이 있으면 새 판을 만들지 않는다")
    except FileNotFoundError:
        ok(True, "빠진 파일이 있으면 새 판을 만들지 않는다")
ok("12" in RC.notes(12, "요약") and "망연계" in RC.notes(12, "요약") and "검수표" in RC.notes(12, "요약") and "요약" in RC.notes(12, "요약"), "새 판 안내에 판 번호·망연계·검수표·요약이 있다")

class FakeGit:
    """git 호출을 흉내 낸다: tags, site.json(커밋별), 태그 이후 바뀐 파일, 커밋 메시지."""
    def __init__(self, no, tags, changed, msg="합치기 설명", head="HEADSHA"):
        self.no, self.tags, self.changed, self.msg, self.head, self.calls = no, tags, changed, msg, head, []

    def __call__(self, *a):
        self.calls.append(a)
        if a[0] == "tag":
            return "\n".join(self.tags)
        if a[0] == "show":
            return json.dumps({"release": {"no": self.no}})
        if a[0] in ("diff", "ls-files"):
            return "\n".join(self.changed)
        if a[0] == "log":
            return self.msg + " [skip ci]\n"
        if a[0] == "rev-parse":
            return self.head + "\n"
        raise AssertionError(a)


class FakeGh2:
    def __init__(self, issues=()):
        self.calls, self.issues = [], list(issues)

    def __call__(self, args, stdin=None):
        self.calls.append((list(args), stdin))
        if args[:2] == ["issue", "list"]:
            return json.dumps(self.issues)
        return ""


def pub(no, tags, changed, env=None, issues=()):
    g, gh, reports = FakeGit(no, tags, changed), FakeGh2(issues), []
    made = lambda n, out: [Path("/x") / f for f in RC.asset_names(n)]  # noqa: E731
    rc = RC.publish({"GITHUB_SHA": "TESTEDSHA"} if env is None else env, g, gh, reports.append, made)
    return rc, g, gh, reports


def created(gh):
    return [c for c in gh.calls if c[0][:2] == ["release", "create"]]


import watch_ci as WCI  # noqa: E402
rc, g, gh, rep = pub(6, ["v5"], ["knowledge/service/a.json", "knowledge/site.json"])
cre = created(gh)
ok(rc == 0 and len(cre) == 1 and cre[0][0][2] == "v6" and cre[0][0][cre[0][0].index("--target") + 1] == "TESTEDSHA", "새 판의 번호와 대상 커밋은 시험한 커밋(GITHUB_SHA)에서 나온다")
ok(("show", "TESTEDSHA:knowledge/site.json") in g.calls and ("log", "-1", "--format=%B", "TESTEDSHA") in g.calls and ("diff", "--name-only", "v5", "TESTEDSHA") in g.calls, "번호·설명·바뀐 파일을 시험한 커밋 기준으로 읽는다")
ok("합치기 설명" in cre[0][1] and "[skip ci]" not in cre[0][1] and "naegyu-chatbot-v6.html" in cre[0][1], "새 판 안내에 그 커밋의 설명과 실제 파일 이름이 있다")
ok(any(a.endswith("naegyu-chatbot-v6.html#내규챗봇_제6판.html") for a in cre[0][0]), "한글 이름표를 붙여 올린다")
rc, g, gh, rep = pub(6, ["v5", "v6"], ["knowledge/alio_seen.json", "reports/alio_watch/latest.json", "대기/x/a.txt"])
ok(rc == 0 and not created(gh) and not rep, "태그가 생긴 뒤 다시 돌리면(기록 파일만 바뀜) 그냥 지나간다")
rc, g, gh, rep = pub(6, ["v5", "v6"], ["knowledge/service/a.json"])
ok(rc == 1 and not created(gh) and len(rep) == 1 and "판 번호" in rep[0], "번호를 안 올린 문답 변경은 Release 를 건드리지 않고 알린다")
rc, g, gh, rep = pub(1, [], [])
ok(rc == 0 and len(created(gh)) == 1, "첫 판은 만든다")
rc, g, gh, rep = pub(7, ["v6"], ["knowledge/service/a.json"], env={}, issues=[{"number": 9, "title": "t", "body": WCI._fail_marker("release"), "createdAt": "2026-11-01T00:00:00Z", "author": BOT}])
ok(("rev-parse", "HEAD") in g.calls and any(c[0] == ["issue", "close", "9"] for c in gh.calls), "성공하면 열린 새 판 실패 이슈를 닫는다(GITHUB_SHA 가 없으면 HEAD)")
rc, g, gh, rep = pub(7, ["v6"], ["knowledge/service/a.json"], issues=[{"number": 4, "title": "t", "body": "다른 이슈", "createdAt": "2026-11-01T00:00:00Z", "author": BOT}])
ok(not any(c[0][:2] == ["issue", "close"] for c in gh.calls), "다른 이슈는 닫지 않는다")
ok(RC.pending_edition(6, ["v5"]) and RC.pending_edition(1, []) and not RC.pending_edition(6, ["v5", "v6"]) and not RC.pending_edition(5, ["v6"]), "아직 못 만든 판을 알아본다")
reps = []
RC.check_pending(FakeGit(6, ["v5"], []), FakeGh2(), reps.append, {})
RC.check_pending(FakeGit(6, ["v6"], []), FakeGh2(), reps.append, {})
ok(len(reps) == 1 and "제6판" in reps[0] and "Run workflow" in reps[0], "check-pending 은 못 만든 판만 알린다")
fg = FakeGit(5, ["v5"], ["knowledge/service/a.json"])
ok(RC.check_number("BASE", fg) == 1 and ("diff", "--name-only", "BASE", "HEAD") in fg.calls, "check-number 는 기준 커밋과 비교한다")

wf = {n: (ROOT / ".github" / "workflows" / n).read_text(encoding="utf-8") for n in ("watch.yml", "confirm.yml", "check.yml", "release.yml")}
ok(not any("pull_request_target" in t for t in wf.values()), "pull_request_target 을 쓰지 않는다")
ok(all("permissions:" in t for t in wf.values()), "권한을 적어 둔다")
ok("schedule:" in wf["watch.yml"] and "workflow_dispatch" in wf["watch.yml"] and "cron: '17 0 * * 1'" in wf["watch.yml"] and "cron: '0 0 " not in wf["watch.yml"], "월요일 아침(한국 시간 9시 17분경, 정각 피함)에 돌고 손으로도 돌릴 수 있다")
ok(all("github.event.repository.fork != true" in wf[n] for n in ("watch.yml", "confirm.yml", "release.yml")), "포크에서는 돌지 않는다(저장소 이름을 박아 두지 않아 넘겨도 된다)")
ok("contents: read" in wf["check.yml"] and "issue_comment" in wf["confirm.yml"], "PR 시험은 읽기 권한만, 확인함은 댓글에 반응")
ok(all(ln.strip().startswith(("COMMENT_BODY:", "ISSUE_BODY:", "if:")) for ln in wf["confirm.yml"].splitlines() if "comment.body" in ln or "issue.body" in ln), "댓글 글자는 환경 변수로만 넘긴다")
ok(all("naegyu-write" in wf[n] for n in ("watch.yml", "confirm.yml", "release.yml")), "커밋하는 작업이 겹치지 않는다")
chk = (ROOT / ".github" / "actions" / "checks" / "action.yml").read_text(encoding="utf-8")
ok("--no-weekly" in wf["release.yml"] and "test_browser_ops.py" in chk, "합친 뒤 판정은 댓글 없이, 시험 묶음에 새 시험 포함")
ok(chk.index("update_rules.py build") < chk.index("test_forms.py"), "양식 시험은 양식을 뗀 뒤에 돈다")
ok(all("queue: max" in wf[n] for n in ("watch.yml", "confirm.yml", "release.yml")), "밀린 실행이 조용히 취소되지 않게 queue: max")
ok("refs/heads/main" in wf["watch.yml"] and "refs/heads/main" in wf["release.yml"], "main 이 아닌 갈래에서는 새 판·매주 확인이 돌지 않는다")
ok("ref: main" in wf["watch.yml"] and "ref: main" in wf["confirm.yml"], "매주 확인과 확인함은 늘 main 끝에서 시작한다")
rel = wf["release.yml"]
ok(rel.index("release_ci.py publish") < rel.index("alio_release.py refresh") and "BEFORE" not in rel and "check-pending" in wf["watch.yml"], "새 판은 기록 작업보다 먼저 올리고, 매주 확인이 못 만든 판을 알린다")
ok(rel.count("--report-failure") == 1 and "::warning::" in rel, "ALIO 기록 갱신 실패는 경고 표시만 한다")
ok(all("concurrency:" in wf[n].split("jobs:", 1)[1] for n in ("watch.yml", "confirm.yml", "release.yml")), "겹침 방지는 작업 단위로 건다")
ok(all("failure() || cancelled()" in wf[n] for n in ("watch.yml", "release.yml")), "시간 초과나 취소도 이슈로 알린다")
src = (ROOT / "scripts" / "update_rules.py").read_text(encoding="utf-8")
ok("def build_all" in src and "합친 뒤 GitHub" in src, "화면 만들기를 나누고 ALIO 경고를 쉬운 말로 고친다")

sk = (ROOT / ".claude" / "skills" / "naegyu-update" / "SKILL.md").read_text(encoding="utf-8")
ok(sk.startswith("---\nname: naegyu-update") and "대기/" in sk and "원본/" in sk and "update_rules.py finish" in sk and "Pull Request" in sk and "개정 반영 이어서" in sk and "setup_project.py" in sk and "--allow-changes" in sk and "Library/Mobile" not in sk and "~/Projects" not in sk, "스킬이 클라우드 흐름을 따른다")
ok("합치지 않" in sk, "Claude가 직접 합치지 않는다고 적혀 있다")
ok("blind_check.py prepare" in sk and "새 Claude 웹 세션" in sk, "재확인 단계와 대안이 있다")
ok("_직접" in sk and "ALIO 기록 갱신 실패" in sk and "Create PR" in sk and "ollama" not in sk, "스킬에 직접 올리기, 정상 경고, PR 버튼 안내가 있다")
cl = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
ok(all(w in cl for w in ("쉬운 한국어", "ZIP", "4.24.1", "git add -A", "ALIO", "시험 질문")), "프로젝트 설명서에 주의점이 있다")
guide = (ROOT / "docs" / "유지보수_안내.md").read_text(encoding="utf-8")
ok(all(w in guide for w in ("확인함:", "매주 확인 기록", "미반영 공지", "대기/", "Release")) and "이 맥 1대" not in guide, "유지보수 안내가 브라우저 흐름이다")
start = (ROOT / "docs" / "담당자_시작_안내.md").read_text(encoding="utf-8")
ok(all(w in start for w in ("github.com", "claude.ai/code", "Merge pull request", "알림")), "담당자 시작 안내")
ok(not (ROOT / "skills" / "naegyu-update" / "SKILL.md").exists(), "옛 스킬 위치를 없앤다")
rd = (ROOT / "README.md").read_text(encoding="utf-8")
ok("convert.sh" not in rd.split("만드는 순서", 1)[1].split("```", 2)[1] and "ollama" not in rd and "예비" in rd, "README 가 로컬 모델과 맥 전용 단계를 요구하지 않는다")

# ====================== 마지막 검토 고침 ======================
import contextlib  # noqa: E402
import io  # noqa: E402
import subprocess  # noqa: E402

# ---- C1. 내규 수를 박아 두지 않는다 ----
import export_gpts as EG  # noqa: E402
ok("내규 72개를" in EG.instructions(72) and "내규 71개" not in EG.instructions(72) and "{N}" not in EG.instructions(72), "C1: GPTs 첫 인사의 내규 수는 지금 내규 수로 채운다")
uit = (ROOT / "scripts" / "ui_test.js").read_text(encoding="utf-8")
ok("/내규 \\d+개 원문/" in uit and "내규 71개" not in uit, "C1: 화면 시험이 내규 수를 박아 두지 않는다")
hard = [f.name for f in list((ROOT / "scripts").glob("*.py")) + list((ROOT / "scripts").glob("*.js")) + list((ROOT / "web").glob("*")) if f.is_file() and not f.name.startswith("test_") and re.search(r"내규 ?\d{2}개", f.read_text(encoding="utf-8", errors="ignore"))]
ok(not hard, "C1: scripts·web 에 내규 수를 박아 둔 곳이 없다 " + ",".join(hard))

# ---- C2. 직접 올리기 점검 ----
cu = (ROOT / "scripts" / "check_upload.py").read_text(encoding="utf-8")
CU = ROOT / "scripts" / "check_upload.py"


def paths_only(files):
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        subprocess.run(["git", "init", "-q"], cwd=td, check=True)
        for rel, text in files.items():
            (td / rel).parent.mkdir(parents=True, exist_ok=True)
            (td / rel).write_text(text, encoding="utf-8")
        subprocess.run(["git", "add", "-f", "."], cwd=td, check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=" + "t" + "@" + "example.invalid", "commit", "-q", "-m", "t"], cwd=td, check=True)
        r = subprocess.run([sys.executable, "-X", "utf8", str(CU), "--paths-only"], cwd=td, capture_output=True, text=True, encoding="utf-8")
        return r.returncode, r.stdout


rc, out = paths_only({"대기/복무세칙_직접/Ⅲ-3-1. 복무세칙.hwp": "x", "knowledge/note.md": "문의 " + "kim" + "@" + "example.com"})
ok(rc == 0, "C2: --paths-only 는 이름만 보고 글 내용은 읽지 않는다")
rc, out = paths_only({"대기/복무세칙_직접/[개정근거] 복무세칙.hwp": "x"})
ok(rc == 1 and "[개정근거]" in out, "C2: --paths-only 는 [ 로 시작하는 파일이 올라가면 실패한다")
rc, out = paths_only({"knowledge/contacts.json": "{}"})
ok(rc == 1, "C2: --paths-only 는 연락처 파일이 올라가면 실패한다")
ok("import" in cu and "paths_only" in cu and not re.search(r"^import (node|kordoc)", cu, re.M), "C2: --paths-only 는 표준 라이브러리만 쓴다")
ug = (ROOT / ".github" / "workflows" / "upload_guard.yml").read_text(encoding="utf-8")
ok(re.search(r"push:\s*\n\s+branches: \[main\]\s*\n\s+paths: \['대기/\*\*'\]", ug), "C2: 공개 점검은 main 에 push 되고 대기/ 가 바뀔 때만 돈다")
ok("contents: read" in ug and "issues: write" in ug and "contents: write" not in ug and "pull_request_target" not in ug, "C2: 공개 점검은 읽기와 이슈 쓰기 권한만")
ok("github.event.repository.fork != true" in ug and "check_upload.py --paths-only" in ug and "setup-python" not in ug and "setup-node" not in ug and "npm" not in ug, "C2: 공개 점검은 포크에서 안 돌고 설치 없이 이름만 본다")
ok(re.search(r"if: failure\(\)\s*\n\s+run: python3 -X utf8 scripts/watch_ci.py --report-failure \"[^\"]*정보보안담당관[^\"]*\" --kind upload", ug), "C2: 걸리면 쉬운 말로 알리는 이슈를 만든다")
ok("${{" not in ug.replace("${{ github.token }}", "").replace("${{ vars.NAEGYU_ASSIGNEES }}", ""), "C2: 공개 점검 run 안에 ${{ }} 를 넣지 않는다")
fu = WC.failure_actions("올라감", [], "2026-11-09", ["담당"], kind="upload")
ok(fu[0]["kind"] == "create" and fu[0]["title"] == "공개 점검 실패" and WC._fail_marker("upload") in fu[0]["body"] and "naegyu-fail:watch" not in fu[0]["body"] and "저절로 닫힙니다" not in fu[0]["body"].split("다음에 할 일")[1], "C2: 공개 점검 실패 이슈는 제목과 표지가 따로이고 저절로 닫힌다고 하지 않는다")
UPISS = {"number": 21, "title": "공개 점검 실패", "body": fu[0]["body"], "createdAt": "2026-11-02T00:00:00Z", "comments": [], "author": BOT}
rc_g = StateGh(mk_issues() + [UPISS])
real_collect = stub_collect(mk_findings)
try:
    with tempfile.TemporaryDirectory() as td:
        rcw = WC.run_ci(None, rc_g, None, NOW, Path(td))
finally:
    WC._collect = real_collect
ok(rcw == 0 and not any(c[:3] == ["issue", "close", "21"] for c in rc_g.calls) and any(c[:3] == ["issue", "close", "3"] for c in rc_g.calls), "C2: 매주 확인이 성공해도 공개 점검 실패 이슈는 닫지 않는다")
rg = FakeGh2([UPISS])
RC._close_release_issues(rg)
ok(not any(c[0][:2] == ["issue", "close"] for c in rg.calls), "C2: 새 판이 만들어져도 공개 점검 실패 이슈는 닫지 않는다")
ok(WC.failure_actions("또", [dict(UPISS, lastCommentDate="2026-11-09")], "2026-11-09", [], kind="upload") == [] and [a["kind"] for a in WC.failure_actions("또", [UPISS], "2026-11-09", [], kind="upload")] == ["comment"], "C2: 공개 점검 실패도 같은 날 겹쳐 만들지 않는다")
ok(re.search(r"^\s+if: .*github\.event\.issue\.user\.login == 'github-actions\[bot\]'", wf["confirm.yml"], re.M) is not None, "I3: 확인함은 우리 봇이 만든 이슈에서만 돈다(job if 한 줄)")
guide = (ROOT / "docs" / "유지보수_안내.md").read_text(encoding="utf-8")
up = guide.split("## ALIO 보다 먼저 받은 파일 올리기", 1)[1].split("## 메일이 안 올 때", 1)[0]
ok(up.index("공개") < up.index("Add file") and all(w in up for w in ("시행문", "[", "직원 이름", "History", "정보보안담당관", "저장소 관리자")), "C2: 직접 올리기 앞머리에 공개 저장소 경고가 있다")
ok("정보보안담당관이 답하기 전에는" in up and "ALIO 에 아직 올라오지 않은 내규" in up, "C2: ALIO 에 없는 내규는 정보보안담당관 답 전에는 올리지 않는다고 적혀 있다")
design = (ROOT / "docs" / "superpowers" / "specs" / "2026-11-05-browser-ops-design.md").read_text(encoding="utf-8")
ok("정보보안담당관이 답하기 전에는" in design.split("### 6.6", 1)[1].split("### 6.7", 1)[0], "C2: 설계 문서 6.6 1번에도 같은 문장이 있다")
ok("공개 점검 실패" in guide, "C2: 안내 표에 공개 점검 실패가 있다")

# ---- I1. 새 판에 붙는 바뀐 내용 ----
import update_rules as UR  # noqa: E402
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    (td / "knowledge").mkdir(); (td / "reports").mkdir()
    (td / "knowledge" / "site.json").write_text(json.dumps({"release": {"no": 5, "where": ""}}), encoding="utf-8")
    (td / "reports" / "change_report.md").write_text("진짜 바뀐 조문", encoding="utf-8")
    saved_ur = (UR.ROOT, UR.run, UR.build_all, UR.sources, UR.refresh_alio, UR.MANIFEST)

    def fake_run(*cmd, check=True):
        if any("check_changes.py" in str(c) for c in cmd):
            (td / "reports" / "change_report.md").write_text("바뀐 것 없음", encoding="utf-8")
            return "비교 끝"
        return "오류 0건"
    UR.ROOT, UR.run, UR.build_all, UR.sources, UR.refresh_alio, UR.MANIFEST = td, fake_run, lambda: None, lambda: {}, lambda: None, td / "knowledge" / "source_files.json"
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            UR.finish(["복무세칙"])
    finally:
        UR.ROOT, UR.run, UR.build_all, UR.sources, UR.refresh_alio, UR.MANIFEST = saved_ur
    ok((td / "reports" / "release_changes.md").read_text(encoding="utf-8") == "진짜 바뀐 조문" and (td / "reports" / "change_report.md").read_text(encoding="utf-8") == "바뀐 것 없음", "I1: finish 는 승인으로 보고서가 덮어쓰이기 전에 release_changes.md 로 따로 둔다")
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    (td / "dist" / "gpts").mkdir(parents=True); (td / "reports" / "review").mkdir(parents=True)
    (td / "dist" / "index.html").write_text("a", encoding="utf-8"); (td / "dist" / "artifact.html").write_text("b", encoding="utf-8")
    (td / "dist" / "gpts" / "지시문.md").write_text("c", encoding="utf-8")
    (td / "reports" / "review" / "검수표_x.xlsx").write_bytes(b"d"); (td / "reports" / "change_report.md").write_text("바뀐 것 없음", encoding="utf-8")
    RC.assets(12, td / "dist", td / "reports", td / "out1")
    ok((td / "out1" / "changes-v12.md").read_text(encoding="utf-8") == "바뀐 것 없음", "I1: release_changes.md 가 없으면(첫 판) change_report.md 를 붙인다")
    (td / "reports" / "release_changes.md").write_text("진짜 바뀐 조문", encoding="utf-8")
    RC.assets(12, td / "dist", td / "reports", td / "out2")
    ok((td / "out2" / "changes-v12.md").read_text(encoding="utf-8") == "진짜 바뀐 조문", "I1: release_changes.md 가 있으면 그것을 붙인다")
sk = (ROOT / ".claude" / "skills" / "naegyu-update" / "SKILL.md").read_text(encoding="utf-8")
ok("reports/release_changes.md" in sk.split("## 5단계", 1)[1], "I1: 스킬 커밋 목록에 release_changes.md 가 있다")

# ---- I2. 합쳤지만 ALIO 목록에 아직 없는 내규 ----
def gone_findings():
    return [T.Finding(name="복무세칙", code="Ⅲ-3-1", idx="9387", verdict=T.V_SUSPECT, mod="2026.11.02", file_date="2026.11.02"),
            T.Finding(name="새로합친내규", code="Ⅶ-9", idx="", verdict=T.V_GONE, title="새로합친내규")]


ht = WC.heartbeat_text(gone_findings()[:1], "2026-11-09", ["새로합친내규"])
ok("아직 ALIO 목록에 없는 내규: 새로합친내규" in ht and "새로합친내규: 목록" not in ht, "I2: 매주 기록 댓글에 아직 ALIO 목록에 없는 내규를 적는다")
ok("아직 ALIO 목록에 없는 내규" in WC.heartbeat_text([none], "2026-11-09", ["가"]) and "아직 ALIO" not in WC.heartbeat_text([none], "2026-11-09"), "I2: 변동이 없는 주에도 적고, 없으면 적지 않는다")
real_collect = stub_collect(gone_findings)
try:
    with tempfile.TemporaryDirectory() as td:
        g = StateGh(mk_issues())
        WC.run_ci(None, g, None, NOW, Path(td))
        WC.run_ci(None, g, None, NOW, Path(td))
        joined = json.dumps(g.calls, ensure_ascii=False)
        ok("목록에서 사라짐" not in joined and "naegyu-idx: -->" not in joined and "naegyu-idx:-->" not in joined, "I2: idx 가 없는 사라짐 판정은 이슈를 만들지 않는다(몇 번 돌아도)")
        rec = [(c, st) for c, st in zip(g.calls, g.stdin) if c[:3] == ["issue", "comment", "1"]]
        ok(len(rec) == 1 and "새로합친내규" in rec[0][1] and "아직 ALIO 목록에 없는 내규" in rec[0][1], "I2: 기록 댓글에 그 내규 이름이 있다")
finally:
    WC._collect = real_collect

# ---- I3. 낯선 사람의 이슈를 믿지 않는다 ----
STRANGER = {"is_bot": False, "login": "spammer"}
FAKEBOT = {"is_bot": False, "login": "github-actions"}
OTHERBOT = {"is_bot": True, "login": "app/dependabot"}
sp_issues = [
    {"number": 4, "title": "개정 의심: 옛규정", "body": WC.marker("5"), "createdAt": "2026-11-02T00:00:00Z", "comments": [], "author": BOT},
    {"number": 50, "title": "개정 의심: 복무세칙", "body": WC.marker("9387"), "createdAt": "2026-11-02T00:00:00Z", "comments": [], "author": STRANGER},
    {"number": 51, "title": "매주 확인 기록", "body": "스팸", "createdAt": "2026-11-02T00:00:00Z", "comments": [], "author": STRANGER},
    {"number": 52, "title": "확인 실패: ALIO 매주 확인", "body": WC._fail_marker("watch"), "createdAt": "2026-11-02T00:00:00Z", "comments": [], "author": FAKEBOT},
    {"number": 53, "title": "x", "body": WC._fail_marker("watch"), "createdAt": "2026-11-02T00:00:00Z", "comments": [], "author": OTHERBOT},
    {"number": 54, "title": "x", "body": WC.marker("5"), "createdAt": "2026-11-02T00:00:00Z", "comments": []},
]
nums = [i["number"] for i in WC._list_open(FakeGh(sp_issues))]
ok(nums == [4], "I3: 목록은 GitHub Actions 봇이 만든 이슈만 남긴다(사람, 이름만 비슷한 사람, 다른 봇, 작성자 없음 제외)")
lg = FakeGh(sp_issues)
WC._list_open(lg)
ok("author" in lg.calls[0][lg.calls[0].index("--json") + 1], "I3: gh 에 작성자도 달라고 한다")
real_collect = stub_collect(mk_findings)
try:
    with tempfile.TemporaryDirectory() as td:
        g = StateGh([dict(i) for i in sp_issues] + [{"number": 1, "title": "매주 확인 기록", "body": "", "createdAt": "2026-11-02T00:00:00Z", "comments": [], "author": BOT}])
        WC.run_ci(None, g, None, NOW, Path(td))
    touched = {c[2] for c in g.calls if c[:2] in (["issue", "edit"], ["issue", "comment"], ["issue", "close"])}
    ok(touched.isdisjoint({"50", "51", "52", "53", "54"}) and "1" in touched, "I3: 낯선 사람의 이슈는 고치거나 댓글을 달거나 닫지 않고, 진짜 기록 이슈에 댓글을 단다")
    ok(any(c[:2] == ["issue", "create"] and "개정 의심" in c[3] for c in g.calls), "I3: 낯선 사람이 표지를 베껴도 진짜 이슈를 따로 만든다")
finally:
    WC._collect = real_collect
with tempfile.TemporaryDirectory() as td:
    g = StateGh([dict(i) for i in sp_issues])
    WC.run_ci(fake_http_down, g, None, NOW, Path(td), sleep=lambda s: None)
    ok(any(c[:2] == ["issue", "create"] and "확인 실패" in c[3] for c in g.calls) and not any(c[:2] == ["issue", "comment"] and c[2] in ("52", "53") for c in g.calls), "I3: 낯선 사람이 실패 표지를 베껴도 실패 알림이 새로 만들어진다")

# ---- I4. .gitignore ----
def ignored(path):
    return subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT).returncode == 0


ok(all(ignored(x) for x in ("knowledge/contacts.json", "reports/contacts/a.md", "scripts/contacts_report.py", "원본/[개정근거] a.hwp", "원본/하위/[참고] a.hwp", "대기/복무세칙_직접/[시행문] a.hwp")), "I4: 연락처 파일과 [ 로 시작하는 파일은 하위 폴더에서도 올라가지 않는다")
ok(not ignored("원본/Ⅲ-3-1. 복무세칙.hwp") and not ignored("knowledge/site.json"), "I4: 보통 파일은 막지 않는다")

# ---- I5. 스킬의 blind_work 정리 ----
ok("git add -u" in sk and "git ls-files reports/blind_work" in sk and "`git add -A` 는 쓰지 않는다" in sk and "결과 파일만 커밋한다" not in sk, "I5: blind_work 삭제를 커밋에 반영하고 PR 전에 없어졌는지 본다")

# ---- I6. 확인함 읽기 ----
ok(CC2.parse_reason("확인함") == "" and CC2.parse_reason("  확인함  ") == "" and CC2.parse_reason("확인함 재게시") == "재게시" and CC2.parse_reason("확인함: 재게시") == "재게시" and CC2.parse_reason("확인함：재게시") == "재게시", "I6: 쌍점이 없어도 확인함으로 시작하면 읽는다")
ok(CC2.parse_reason("이미 확인함: 재게시") is None and CC2.parse_reason("확인함으로 기록했습니다") is None and CC2.parse_reason("메모\n확인함: x") is None, "I6: 글 중간에 낀 확인함은 읽지 않는다")
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    sp = td / "seen.json"
    sp.write_text(json.dumps({"taken": "x", "rules": {"9387": {"name": "복무세칙", "title": "복무세칙", "mod": "m1", "st_date": "s1", "file_no": "1", "file_date": "f1"}}}), encoding="utf-8")
    g = FakeGh()
    r = CC2.handle("확인함", "OWNER", WC.marker("9387"), "2026-11-16", latest, sp, g, 7, td)
    ok(r == "다시 요청" and len(g.calls) == 1 and "사유" in g.stdin[0] and json.loads(sp.read_text(encoding="utf-8"))["rules"]["9387"]["mod"] == "m1", "I6: 사유 없이 확인함만 쓰면 사유를 적어 달라고 답하고 기록하지 않는다")
    g = FakeGh()
    ok(CC2.handle("확인함 재게시", "OWNER", WC.marker("9387"), "2026-11-16", latest, sp, g, 7, td) == "기록함" and json.loads(sp.read_text(encoding="utf-8"))["rules"]["9387"]["confirmed"]["reason"] == "재게시", "I6: 쌍점 없는 확인함 사유도 기록한다")
    g = FakeGh()
    ok(CC2.handle("확인함", "NONE", "표시 없음", "2026-11-16", latest, sp, g, 7, td) == "무시" and g.calls == [], "I6: 권한이 없는 사람에게는 어떤 답도 하지 않는다")
    g = FakeGh()
    ok(CC2.handle("지나가는 말", "OWNER", "표시 없음", "2026-11-16", latest, sp, g, 7, td) == "무시" and g.calls == [], "I6: 확인함이 아닌 댓글은 표시 없는 이슈에서도 답하지 않는다")

# ---- 작은 것들 ----
spj = (ROOT / "scripts" / "setup_project.py").read_text(encoding="utf-8")
ok('[npm, "ci", "--ignore-scripts"]' in spj, "작은것: npm ci 는 --ignore-scripts 로 한다")
# 문제가 있으면 표지를 남기지 않는다(그래야 그냥 다시 돌렸을 때 늘 다시 확인한다)
import check_changes as CCH  # noqa: E402
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    keep = (SP.STAMP, SP.DATA, SP.convert, SP.setup_stamp, SP.baseline_problems, CCH.TEXTS, sys.argv)
    SP.STAMP, SP.DATA, SP.convert, SP.setup_stamp, CCH.TEXTS = td / ".setup_stamp", td, lambda: None, lambda d: "STAMPVALUE", td / "snapshot_texts.json"
    try:
        for probs, expect in ((["문제"], False), ([], True)):
            SP.baseline_problems = lambda c, s, p=probs: p
            sys.argv = ["setup_project.py", "--no-install", "--allow-changes"]
            with contextlib.redirect_stdout(io.StringIO()):
                SP.main()
            ok((td / ".setup_stamp").exists() == expect, f"작은것: 지문과 다른 곳이 {'있으면 준비 표지를 남기지 않는다' if not expect else '없으면 준비 표지를 남긴다'}")
            (td / ".setup_stamp").unlink(missing_ok=True)
            (td / "snapshot_texts.json").unlink(missing_ok=True)
    finally:
        SP.STAMP, SP.DATA, SP.convert, SP.setup_stamp, SP.baseline_problems, CCH.TEXTS, sys.argv = keep
ok(re.search(r"- name: 못 만든 새 판이 있는지 확인\n\s+if: always\(\)\n\s+continue-on-error: true\n\s+run: python3 -X utf8 scripts/release_ci.py check-pending", wf["watch.yml"]) is not None, "작은것: 알림 단계(check-pending)가 실패해도 본 확인은 계속한다")
cfg = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
ok(cfg["hooks"]["SessionStart"][0].get("matcher") == "startup|resume", "작은것: 시작 훅은 새로 열 때와 이어 열 때만 돈다(compact·clear 제외)")
ok("9시" in wf["watch.yml"] and "오전" in guide, "작은것: 매주 확인 시각 설명이 남아 있다")
urs = (ROOT / "scripts" / "update_rules.py").read_text(encoding="utf-8")
ok("'지난판' 폴더로 옮겨" not in urs and "옛 파일은 지워 주세요" in urs and "iCloud" not in urs.split('"""', 2)[1] and "summary.md" not in urs, "작은것: update_rules 는 옛 파일을 지우라고 안내하고 낡은 설명이 없다")
import alio_release as AR  # noqa: E402
keep_ar = (AR.fetch_all, AR.write_release, AR.load_seen)
AR.fetch_all = lambda: (_ for _ in ()).throw(AR.AlioError("막힘"))
AR.write_release, AR.load_seen = lambda: None, lambda: {"rules": {}}
buf = io.StringIO()
try:
    with contextlib.redirect_stdout(buf):
        AR.refresh()
finally:
    AR.fetch_all, AR.write_release, AR.load_seen = keep_ar
ok("접속 실패" in buf.getvalue() and "Claude 웹" in buf.getvalue() and "정상" in buf.getvalue() and "GitHub" in buf.getvalue(), "작은것: ALIO 가 막힌 클라우드 세션에서 정상이며 합친 뒤 GitHub 가 다시 한다고 알린다")
OD = T.Finding(name="별지내규", code="", idx="8", verdict=T.V_OUTSIDE, compare=cmp_res(outside_diff=["--- 이전", "+++ 이후", "@@ -1 +1 @@", "-옛 별지", "+새 별지"]))
bo = WC.issue_body(OD, "2026-11-09")
ok("조문 밖에서 달라진 글자" in bo and "-옛 별지" in bo and "+새 별지" in bo and "--- 이전" not in bo and "+++ 이후" not in bo and "@@" not in bo, "작은것: 조문 밖 변화는 달라진 글자만 보이고 diff 머리 줄은 뺀다")
SU = T.Finding(name="일반내규", code="", idx="9", verdict=T.V_SUSPECT, compare=cmp_res(changed_units=["제1조"], outside_diff=["-옛", "+새"]))
ok("조문 밖에서 달라진 글자" not in WC.issue_body(SU, "2026-11-09"), "작은것: 조문 밖 변화가 아닌 판정에는 그 줄을 쓰지 않는다")
start = (ROOT / "docs" / "담당자_시작_안내.md").read_text(encoding="utf-8")
prac = start.split("## 4. 연습", 1)[1].split("## 5.", 1)[0]
ok("임시" in prac and "실제 저장소에서는 하지 않습니다" in prac and "함께" in prac, "작은것: 연습은 인계하는 분과 임시 사본에서 하고 실제 저장소에서는 하지 않는다")
fail_sec = guide.split("### 새 판 실패", 1)[1].split("## ALIO 보다", 1)[0]
ok("직접 닫습니다" not in fail_sec and "저절로 닫힙니다" in fail_sec and "직접 닫아" not in WC.failure_actions("x", [], "2026-11-09", [], kind="release")[0]["body"], "작은것: 새 판 실패 이슈는 저절로 닫힌다고 안내한다(손으로 닫으라는 말 없음)")
ok("확인함 사유" in guide and "알림 글이 아니다" in guide, "작은것: 안내에 쌍점 없는 확인함과 알림 아닌 글의 답이 적혀 있다")


sys.exit(1 if FAIL else 0)
