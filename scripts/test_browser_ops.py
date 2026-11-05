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
    return [{"number": 4, "title": "개정 의심: 옛규정", "body": WC.marker("5"), "createdAt": "2026-11-02T00:00:00Z", "comments": []},
            {"number": 3, "title": "확인 실패: ALIO 매주 확인", "body": WC._fail_marker("watch"), "createdAt": "2026-11-02T00:00:00Z", "comments": []},
            {"number": 1, "title": "매주 확인 기록", "body": "", "createdAt": "2026-11-02T00:00:00Z", "comments": []}]


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
    ok(call("확인함: 사유", "OWNER", g, "표시 없음") == "무시" and g.calls == [], "내규 표시가 없는 이슈는 답 없이 무시한다")
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
    ok(names == sorted(["내규챗봇_제12판.html", "내규챗봇_제12판_artifact.html", "GPTs_제12판.zip", "검수표_제12판.zip", "바뀐_내용_제12판.md"]), "새 판 파일을 모은다")
    (td / "dist" / "index.html").unlink()
    try:
        RC.assets(12, td / "dist", td / "reports", td / "out2")
        ok(False, "빠진 파일이 있으면 새 판을 만들지 않는다")
    except FileNotFoundError:
        ok(True, "빠진 파일이 있으면 새 판을 만들지 않는다")
ok("12" in RC.notes(12, "요약") and "망연계" in RC.notes(12, "요약") and "검수표" in RC.notes(12, "요약") and "요약" in RC.notes(12, "요약"), "새 판 안내에 판 번호·망연계·검수표·요약이 있다")
wf = {n: (ROOT / ".github" / "workflows" / n).read_text(encoding="utf-8") for n in ("watch.yml", "confirm.yml", "check.yml", "release.yml")}
ok(not any("pull_request_target" in t for t in wf.values()), "pull_request_target 을 쓰지 않는다")
ok(all("permissions:" in t for t in wf.values()), "권한을 적어 둔다")
ok("schedule:" in wf["watch.yml"] and "workflow_dispatch" in wf["watch.yml"] and "cron: '0 0 * * 1'" in wf["watch.yml"], "월요일 아침(한국 시간 9시)에 돌고 손으로도 돌릴 수 있다")
ok(all("github.event.repository.fork != true" in wf[n] for n in ("watch.yml", "confirm.yml", "release.yml")), "포크에서는 돌지 않는다(저장소 이름을 박아 두지 않아 넘겨도 된다)")
ok("contents: read" in wf["check.yml"] and "issue_comment" in wf["confirm.yml"], "PR 시험은 읽기 권한만, 확인함은 댓글에 반응")
ok(all(ln.strip().startswith(("COMMENT_BODY:", "ISSUE_BODY:", "if:")) for ln in wf["confirm.yml"].splitlines() if "comment.body" in ln or "issue.body" in ln), "댓글 글자는 환경 변수로만 넘긴다")
ok(all("naegyu-write" in wf[n] for n in ("watch.yml", "confirm.yml", "release.yml")), "커밋하는 작업이 겹치지 않는다")
chk = (ROOT / ".github" / "actions" / "checks" / "action.yml").read_text(encoding="utf-8")
ok("--no-weekly" in wf["release.yml"] and "test_browser_ops.py" in chk, "합친 뒤 판정은 댓글 없이, 시험 묶음에 새 시험 포함")
ok(chk.index("update_rules.py build") < chk.index("test_forms.py"), "양식 시험은 양식을 뗀 뒤에 돈다")
src = (ROOT / "scripts" / "update_rules.py").read_text(encoding="utf-8")
ok("def build_all" in src and "합친 뒤 GitHub" in src, "화면 만들기를 나누고 ALIO 경고를 쉬운 말로 고친다")

sys.exit(1 if FAIL else 0)
