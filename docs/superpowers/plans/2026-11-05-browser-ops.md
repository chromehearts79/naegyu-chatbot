# 브라우저 운영 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 담당자가 브라우저(GitHub, 메일, Claude 웹)만으로 매주 확인부터 새 판 받기까지 하게 만든다.

**Architecture:** 저장소가 원본과 문답과 프로그램을 모두 담는다. GitHub Actions가 ALIO 확인·알림·시험·새 판을 맡고, Claude 클라우드 세션이 저장소의 스킬로 문답을 고쳐 Pull Request를 연다. 사람은 이슈를 읽고 PR을 합친다. 1번 과제의 판정(`watch_alio.judge`)과 원문 비교(`alio_compare`)를 그대로 쓰고 결과를 내는 쪽만 새로 만든다.

**Tech Stack:** Python 3.11+, Node.js 22, kordoc 4.24.1(고정), GitHub Actions, `gh` CLI, Claude Code 클라우드 세션.

**Spec:** `docs/superpowers/specs/2026-11-05-browser-ops-design.md`

## Global Constraints

- 갈래 `browser-ops` 에서 작업한다. main 합치기와 GitHub 올리기는 사용자가 허락할 때만 한다. 저장소 주소: `https://github.com/chromehearts79/naegyu-chatbot`(공개, 지금 비어 있음).
- 커밋은 파일을 지정해 올린다. `git add -A` 금지. `knowledge/contacts.json`, `reports/contacts/`, `scripts/contacts_report.py` 와 `[` 로 시작하는 파일은 절대 올리지 않는다. 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- kordoc 판은 `4.24.1`. 바꾸지 않는다.
- 지문(`knowledge/source_snapshot.json`)을 저절로 다시 찍지 않는다. 바뀐 단위가 0이 아니면 멈추고 보고한다.
- 판정 이름은 `alio_types.py` 의 상수를 쓴다. 판정 규칙(`judge`)과 재확인 비교 규칙(`compare`)을 바꾸지 않는다.
- 새 코드는 `encoding="utf-8"`. Python 3.11 호환(f-string 식 안에 역슬래시·같은 따옴표 금지).
- 화면과 이슈와 안내의 글은 비개발자가 읽는 쉬운 한국어. GitHub 화면의 영어 버튼은 그대로 적어 준다.
- ALIO에 접속하는 일은 Actions에서만 한다. Claude 클라우드 세션에서는 막혀 있다.
- 공개 저장소다. 이슈와 로그에 사람 이름을 적지 않는다. 포크 PR에 쓰기 권한과 비밀값을 주지 않는다(`pull_request_target` 금지). 이슈·댓글의 글자는 워크플로 `env:` 로만 넘기고 `run:` 안에 `${{ }}` 로 넣지 않는다.
- 시험 실행: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`. 통과는 `✗` 없음과 `exit=0`. 새 영역은 `scripts/test_browser_ops.py` 에 같은 방식(`ok(cond, msg)`)으로 쓰고, 파일 끝 `sys.exit(1 if FAIL else 0)` 은 맨 끝에 둔다. 시험 코드는 작업 순서대로 그 앞에 더한다.
- 이 맥에서도 `update_rules.py` 와 모든 시험이 계속 돌아야 한다.

## Review Focus

1. **같은 날 매주 확인을 두 번 돌림(손 실행, 합친 뒤 판정):** 이슈와 댓글이 겹치지 않는다. 메일이 두 번 가지 않는다. Task 5에 시험.
2. **ALIO 제목·파일 이름에 `@누군가`, 역따옴표, `<script>`, 줄바꿈이 들어옴:** 이슈 글이 깨지지 않고 다른 사람에게 알림이 가지 않는다. Task 5에 시험.
3. **개정 전·후 글이 아주 김(별표 전체가 바뀜):** GitHub 이슈 글 한도(65,536자)를 넘지 않고 잘렸다고 알린다. Task 5에 시험.
4. **PR 두 개가 같은 판 번호로 연달아 합쳐짐:** 뒤의 것이 기존 Release를 덮어쓰지 않고, 새 판이 안 만들어졌다고 알린다. Task 7에 시험.
5. **외부인이 이슈에 `확인함: 아무거나` 댓글을 닮:** 아무 일도 일어나지 않는다. Task 6에 시험.

---

### Task 1: kordoc 판 고정과 원본 옮기기

**Files:**
- Create: `package.json`, `package-lock.json`, `requirements.txt`, `.gitattributes`, `scripts/kordoc_tool.py`, `scripts/test_browser_ops.py`, `원본/`(72개)
- Modify: `.gitignore`, `scripts/update_rules.py:25,125`, `scripts/cut_forms.cjs:9`, `scripts/convert.sh:5,10`, `scripts/alio_compare.py:23,29`, `scripts/test_watch_alio.py:318`
- 함께 커밋: `docs/superpowers/specs/2026-11-04-windows-move-design.md`, `docs/superpowers/specs/2026-11-05-browser-ops-design.md`, 이 계획

**Interfaces:**
- Produces: `kordoc_tool.KORDOC_VERSION`(package.json에서 읽음), `kordoc_tool.KORDOC`(`"kordoc@4.24.1"`), `kordoc_tool.kordoc_cmd() -> list[str]`(저장소 `node_modules/.bin` 먼저, 없으면 `[npx, "-y", KORDOC]`), 원본 기본 경로 `<저장소>/원본`.

- [ ] **Step 1: 갈래를 만들고 문서를 커밋한다**

문서에 개인 메일이 없는지 먼저 본다.

```bash
cd ~/Projects/naegyu-chatbot && git checkout -b browser-ops
grep -n '@gmail' docs/superpowers/specs/2026-11-04-windows-move-design.md docs/superpowers/specs/2026-11-05-browser-ops-design.md
git add docs/superpowers/specs/2026-11-04-windows-move-design.md docs/superpowers/specs/2026-11-05-browser-ops-design.md docs/superpowers/plans/2026-11-05-browser-ops.md
git commit -m "브라우저 운영 설계와 계획"
```

Expected: `grep` 결과 없음.

- [ ] **Step 2: 실패하는 시험을 쓴다**

`scripts/test_browser_ops.py` 를 새로 만든다.

```python
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

sys.exit(1 if FAIL else 0)
```

- [ ] **Step 3: 시험이 실패하는지 확인한다**

Run: `python3 -X utf8 scripts/test_browser_ops.py; echo exit=$?`
Expected: `ModuleNotFoundError: No module named 'kordoc_tool'`

- [ ] **Step 4: 고친다**

- `package.json`: `"private": true`, 의존성 `kordoc` `4.24.1`, `jsdom` `24.1.3`, `cfb` `1.2.2`(앞에 `^` 없음). `npm install` 로 `package-lock.json` 을 만든다.
- `requirements.txt`: `openpyxl==3.1.5` 한 줄. 형태소 분석기는 지금 있는 `scripts/requirements-bounds.txt` 를 그대로 쓴다. `fontTools` 는 `make_fonts.py` 에만 쓰여 넣지 않는다.
- `update_rules.py` 의 `kiwi_python` 은 그대로 둔다. 형태소 분석기가 없을 때의 안내 문구만 "`python3 -X utf8 scripts/setup_project.py --full` 을 실행해 주세요"로 고친다.
- `.gitattributes`: 첫 줄 `* -text`.
- `.gitignore`: `원본/[[]*` 과 `대기/**/[[]*` 를 더하고, `data/` 위의 설명을 "변환본은 준비 스크립트로 다시 만든다"로 고친다.
- `kordoc_tool.py`: `alio_compare.kordoc_cmd` 를 옮긴다. `alio_compare` 는 이것을 import 하고 `KORDOC`, `kordoc_cmd` 를 그대로 내보낸다. `C.shutil` 은 같은 모듈 객체라 바꿔 끼우는 시험은 그대로 통과한다.
- `test_watch_alio.py:318` 의 값 두 곳만 `kordoc@4.24.1` 로 고친다.
- `update_rules.py:125`: `run(*kordoc_cmd(), "--jobs", "4", "-d", ...)`.
- `update_rules.py:25`: `SRC = Path(os.environ.get("NAEGYU_SRC") or ROOT / "원본")`. `cut_forms.cjs:9` 와 `convert.sh` 도 같다. `convert.sh` 는 `node_modules/.bin/kordoc` 를 먼저 쓰고 없으면 `npx -y kordoc@4.24.1` 을 쓴다.
- 원본 72개를 복사한다(iCloud의 원본은 그대로 둔다).

```bash
mkdir -p 원본 && find "$HOME/Library/Mobile Documents/com~apple~CloudDocs/내규챗봇" -maxdepth 1 -type f \( -name '*.hwp' -o -name '*.hwpx' -o -name '*.xlsx' \) ! -name '\[*' -print0 | xargs -0 -I{} cp {} 원본/
```

- [ ] **Step 5: 시험이 통과하고 지금 자료와 같은지 확인한다**

Run: `python3 -X utf8 scripts/test_browser_ops.py; echo exit=$?; python3 -X utf8 scripts/test_watch_alio.py >/dev/null; echo watch=$?; python3 scripts/update_rules.py status | tail -1`
Expected: `exit=0`, `watch=0`, `바뀐 파일이 없습니다`

스크래치 폴더에서 `node_modules/.bin/kordoc --jobs 4 -d <임시> 원본/*` 를 돌려 `data/md` 와 비교한다.
Expected: 72개 모두 글자까지 같음. `data/md` 의 `[개정근거]` 변환본 2개와 `images/` 는 비교에서 뺀다.

- [ ] **Step 6: 복무세칙 직전 판을 다시 잰다**

ALIO 복무세칙 ZIP(`mcp__alio__alio_download_rule` 또는 `alio_client`)에서 2025.10.30 판 hwp 를 스크래치 폴더로 받아 `alio_compare.compare_rule("복무세칙", "Ⅲ-3-1", [(이름, 내용)])` 을 돌린다. 다음 넷을 지금 값(`docs/superpowers/specs/2026-11-04-alio-watch-design.md:92`: 7/20/14/4)과 비교한다: `changed_units`, `stale_cards`, `related_cards`, `calcs` 의 개수. 다르면 그 설계의 숫자를 고치고 보고서에 적는다. `git status` 로 실제 자료가 그대로인지 확인한다.

- [ ] **Step 7: 커밋한다**

```bash
git add package.json package-lock.json requirements.txt .gitattributes .gitignore scripts/kordoc_tool.py scripts/test_browser_ops.py scripts/test_watch_alio.py scripts/update_rules.py scripts/cut_forms.cjs scripts/convert.sh scripts/alio_compare.py docs/superpowers/specs/2026-11-04-alio-watch-design.md 원본
git commit -m "kordoc 판 고정, 원본을 저장소로 옮김"
```

### Task 2: 준비 스크립트

**Files:**
- Create: `scripts/setup_project.py`, `.claude/settings.json`
- Modify: `scripts/test_browser_ops.py`

**Interfaces:**
- Consumes: `kordoc_tool.kordoc_cmd`, `check_changes.load_rules(path)`, `check_changes.compare(rules, snap, cards) -> (changes, eff, stale, related)`, `check_changes.take(rules, None, snap, {}) -> (snap, texts)`, `check_changes.SNAPSHOT/TEXTS/RULES`, `check_knowledge.load_domains(tolerant=True)`
- Produces:
  - `baseline_problems(changes: dict, stale: dict) -> list[str]`(비면 통과). `changes` 키는 `(규정, 단위)`.
  - `setup_stamp(src_dir: Path) -> str`(원본 파일 지문과 kordoc 판으로 만든 값)
  - 명령: `python3 -X utf8 scripts/setup_project.py [--full] [--no-install] [--allow-changes]`. 실패하면 쉬운 말과 `exit 1`.

- [ ] **Step 1: 실패하는 시험을 더한다**

```python
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
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `python3 -X utf8 scripts/test_browser_ops.py; echo exit=$?`
Expected: `ModuleNotFoundError: No module named 'setup_project'`

- [ ] **Step 3: 만든다**

순서:
1. 패키지 설치(`--no-install` 이면 건너뜀): `npm ci`, `sys.executable -m pip install -r requirements.txt`. `--full` 이면 `scripts/requirements-bounds.txt` 도 설치한다. pip 가 시스템 파이썬이라 거부하면 `--break-system-packages` 를 붙여 한 번 더 한다.
2. `data/.setup_stamp` 가 `setup_stamp` 값과 같으면 끝.
3. `원본/*` 변환(`kordoc_cmd`), `scripts/build_db.py`.
4. 바뀐 단위·다시 확인 문답 계산(`check_changes.py` 를 부르지 않고 `compare` 를 직접 쓴다. 지문·`stale_cards.json` 을 건드리지 않는다).
5. `baseline_problems` 가 있으면 내용을 보여 주고 `exit 1`. `--allow-changes` 면 보여 주기만 하고 `snapshot_texts.json` 을 쓰지 않은 채 계속한다(이어 하는 중에는 옛 글이 저장소에 없다. 개정 전 글자는 앞 세션이 커밋한 `reports/change_report.md` 에 있다).
6. `take` 의 `texts` 만 `data/snapshot_texts.json` 에 쓴다.
7. 표지를 쓴다.

`.claude/settings.json` 의 `hooks.SessionStart`:
`[ "$CLAUDE_CODE_REMOTE" = "true" ] && python3 -X utf8 scripts/setup_project.py --full --allow-changes || true`. 실패해도 세션은 뜬다. 스킬이 첫 단계에서 다시 확인한다(Task 8).

- [ ] **Step 4: 시험 통과를 확인하고 커밋한다**

Run: `python3 -X utf8 scripts/test_browser_ops.py; echo exit=$?`
Expected: `exit=0`

```bash
git add scripts/setup_project.py .claude/settings.json scripts/test_browser_ops.py
git commit -m "저장소 준비 스크립트: 변환하고 지문과 같은지 확인"
```

- [ ] **Step 5: 빈 복사본에서 끝까지 돌린다**

커밋한 뒤에 복사해야 스크립트가 복사본에 들어간다. 맥의 전역 파이썬에 패키지를 깔지 않도록 스크래치 폴더의 가상 환경으로 돌린다.

Run: `git clone -q . <스크래치>/r && cd <스크래치>/r && python3 -m venv <스크래치>/v && <스크래치>/v/bin/python -X utf8 scripts/setup_project.py --full; echo exit=$?; git status --short`
Expected: `exit=0`, 바뀐 단위 0개, 다시 확인 문답 0장, `git status` 비어 있음. 두 번째 실행은 금방 끝남. 다르면 지문을 다시 찍지 말고 보고한다. 지금 맥 저장소는 그대로다. 스크립트를 고쳤으면 다시 커밋한다. 형태소 분석기가 이 파이썬 판에 설치되지 않으면 저장소 `.venv` 와 같은 판의 파이썬으로 가상 환경을 만든다.

### Task 3: 올리기 전 점검

**Files:**
- Create: `scripts/check_upload.py`, `scripts/file_info.cjs`
- Modify: `scripts/test_browser_ops.py`

**Interfaces:**
- Produces:
  - `ALLOWED_PHONES = {"02-123-4567", "044-200-7752"}`, `ALLOWED_EMAILS = {"noreply@anthropic.com"}`
  - `scan_text(name: str, text: str) -> list[str]`
  - `forbidden_paths(paths: list[str]) -> list[str]`
  - `scan_md_dir(md_dir: Path) -> list[str]`(`[` 로 시작하는 변환본은 올리지 않으므로 보지 않는다)
  - 명령: `python3 -X utf8 scripts/check_upload.py [--staged] [--history]`. 문제가 있으면 `exit 1`, 끝에 파일 수와 파일 정보 목록을 쓴다. `--history` 는 main 기록에 나온 모든 경로와 바뀐 글자를 함께 보고, 커밋 작성자 메일을 목록으로 보여 준다(메일 목록만으로는 실패시키지 않는다. 사용자가 정할 일이다).

- [ ] **Step 1: 실패하는 시험을 더한다**

시험 파일 자체가 점검에 걸리지 않게 값을 나눠 적는다.

```python
import check_upload as CU  # noqa: E402
ok(CU.scan_text("a", "연락처 hong" + "@example.go.kr") and CU.scan_text("a", "010-" + "1234-5678") and CU.scan_text("a", "900101-" + "1234567"), "메일·전화·주민번호 꼴을 잡는다")
ok(not CU.scan_text("a", "예시 02-123-4567") and not CU.scan_text("a", "신고 044-200-7752"), "알려진 공개 번호는 통과")
ok(CU.scan_text("a", "02-2610-" + "6000"), "그 밖의 전화번호는 잡는다")
ok(CU.scan_text("a", "sk-" + "a" * 30) and CU.scan_text("a", "ghp_" + "a" * 30) and CU.scan_text("a", "AKIA" + "A" * 16), "API 키 꼴을 잡는다")
ok(not CU.scan_text("a", "noreply@anthropic.com") and not CU.scan_text("a", "담당자 이메일 : ○○○○○○@posid.or.kr"), "커밋 꼬리표와 가린 주소는 통과")
ok(CU.forbidden_paths(["원본/[개정근거] 시행문.hwp", "knowledge/contacts.json", "reports/contacts/x.md", "scripts/contacts_report.py", "원본/Ⅰ. 정관.hwpx"]) == ["원본/[개정근거] 시행문.hwp", "knowledge/contacts.json", "reports/contacts/x.md", "scripts/contacts_report.py"], "올리면 안 되는 경로를 잡는다")
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    (td / "[개정근거] 시행문.md").write_text("hong" + "@example.go.kr", encoding="utf-8")
    ok(CU.scan_md_dir(td) == [], "올리지 않는 [ 변환본은 보지 않는다")
    (td / "복무세칙.md").write_text("hong" + "@example.go.kr", encoding="utf-8")
    ok(len(CU.scan_md_dir(td)) == 1, "올라갈 내규 변환본은 본다")
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `python3 -X utf8 scripts/test_browser_ops.py; echo exit=$?`
Expected: `ModuleNotFoundError: No module named 'check_upload'`

- [ ] **Step 3: 만든다**

대상은 `git ls-files`(`--staged` 면 인덱스 기준)의 글 파일과 `scan_md_dir(data/md)`. 파일 경로도 `forbidden_paths` 로 본다. `file_info.cjs` 는 `cfb` 로 `.hwp` 의 `\x05HwpSummaryInformation`, zip으로 `.hwpx` 의 `Contents/content.hpf` 를 읽어 파일 정보를 JSON으로 낸다. 값은 그대로 보여 주기만 하고 막지 않는다. 사람 판단 자료다. 메일 꼴에서 `○`, `*`, `x` 로 가린 주소는 잡지 않는다.

- [ ] **Step 4: 실제로 돌린다**

Run: `python3 -X utf8 scripts/test_browser_ops.py; echo exit=$?; python3 -X utf8 scripts/check_upload.py; echo check=$?; python3 -X utf8 scripts/check_upload.py --history; echo history=$?`
Expected: `exit=0`, `check=0`, `history=0`. 작성자 메일 목록에 개인 메일 1건이 보인다. 잡힌 것이 있으면 그대로 보고한다. 예외 목록을 임의로 늘리지 않는다.

- [ ] **Step 5: 커밋한다**

```bash
git add scripts/check_upload.py scripts/file_info.cjs scripts/test_browser_ops.py
git commit -m "올리기 전 점검: 개인정보·키 꼴, 올리면 안 되는 경로, 파일 정보 목록"
```

### Task 4: AI 재확인을 파일로 나누기

**Files:**
- Modify: `scripts/blind_check.py`, `scripts/test_browser_ops.py`

**Interfaces:**
- Produces(작업 파일은 `reports/blind_work/`, 작업 갈래에 커밋해 이어 간다. 모듈 변수 `WORK`):
  - `prepare(card_ids: list[str]) -> Path`: `questions.json`. 항목: `card`, `question`, `labels`, `context`, `prompt`. 카드 값(`value`), `quote` 를 넣지 않는다. 이미 있으면 지금 대상과 합친다.
  - `remaining() -> list[str]`: 답을 아직 받지 않은 카드.
  - `first_pass(answers: dict[str, list[str]], ai_name: str) -> tuple[list[dict], Path | None]`: 받은 카드만 지금 `compare` 로 판정해 작업 파일에 쌓고 이번 행을 돌려준다. 지금까지 '판정 필요'가 있으면 `judge_questions.json`(항목: `key`, `label`, `value`, `context`, `prompt`)을 쓰고 경로를 돌려준다.
  - `finish(judge_answers: dict[str, dict], ai_name: str) -> dict`: `remaining()` 이 남았거나 2차 답이 빠지면 `ValueError`. 지금 규칙(`"예"` 면 `판정 통과`, 그 밖은 `확인 필요`)으로 판정하고, 고르지 않은 카드는 그대로 두고 `reports/blind_check.md/.json` 을 쓰고 작업 파일을 지운다. 돌려주는 값은 판정별 개수. 행마다 `ai` 를 남긴다.
  - `sample_cards(n: int, seed: int = 20261105) -> list[str]`: 분야를 고르게 섞어 고른다.
  - 명령: `blind_check.py prepare <id…>`, `first <answers.json> --ai 이름`, `finish <judge_answers.json> --ai 이름`, `sample 20`, `remaining`.
- 로컬 모델 호출(`ask`, `judge`, `urllib`, `MODEL`)을 없앤다. 프롬프트 문장은 그대로 파일에 옮긴다. `compare`, `bigrams`, `key_numbers`, `scope_of`, `around` 는 고치지 않는다.

- [ ] **Step 1: 실패하는 시험을 더한다**

```python
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
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `python3 -X utf8 scripts/test_browser_ops.py; echo exit=$?`
Expected: `AttributeError` 또는 `✗`, `exit=1`

- [ ] **Step 3: 고친다**

`main` 을 위 단계로 나눈다. 보고서 모양을 유지하고, 제목의 모델 이름을 답한 AI 이름으로 바꾼다. 걸린 시간 칸은 뺀다.

- [ ] **Step 4: 시험 통과를 확인하고 커밋한다**

Run: `python3 -X utf8 scripts/test_browser_ops.py; echo exit=$?`
Expected: `exit=0`

```bash
git add scripts/blind_check.py scripts/test_browser_ops.py
git commit -m "AI 재확인: 문제·답을 파일로 나누고 로컬 모델 호출 없앰"
```

### Task 5: 매주 확인(결과 내기)

**Files:**
- Create: `scripts/watch_ci.py`
- Modify: `scripts/test_browser_ops.py`

**Interfaces:**
- Consumes: `watch_alio.judge(rows, attachments, release, None, fetch_file, compare, "full")`, `watch_alio.check_sanity`, `alio_release.build_release/load_seen/_rules/_load_sources/_release_no`, `alio_client.fetch_list/fetch_attachments/fetch_file/AlioError`, `alio_compare.compare_rule`, `alio_report.save_bundle/safe_name/elapsed_days/LATE_DAYS`, `alio_types`
- Produces:
  - `kst_date(iso: str) -> str`: GitHub 시각(UTC)을 한국 날짜로. 이 파일의 `today` 와 `lastCommentDate` 는 모두 한국 날짜.
  - `clean_md(s: str) -> str`: 줄바꿈을 공백으로, `@`·역따옴표·`<`·`>`·`|`·`[`·`]` 를 무해하게 바꾼다.
  - `marker(idx: str) -> str`: `<!-- naegyu-idx:IDX -->`
  - `issue_title(f) -> str`: `"<판정>: <내규명>"`
  - `issue_body(f, today: str, limit: int = 60000) -> str`
  - `week_comment(f, today: str) -> str`
  - `plan_actions(findings, open_issues: list[dict], today: str, assignees: list[str], weekly: bool = True) -> list[dict]`: 이슈 행동 목록. `open_issues` 항목: `number`, `title`, `body`, `createdAt`, `lastCommentDate`. 행동 `kind`: `create`, `edit`, `comment`, `close`. idx 표지가 없는 이슈는 건드리지 않는다. 표지가 있는데 findings에 없거나 `ATTENTION` 밖이면 닫는다. `weekly=False` 면 댓글을 달지 않는다.
  - `heartbeat_text(findings, today: str) -> str`
  - `heartbeat_actions(findings, pinned: dict | None, today: str) -> list[dict]`: 없으면 `create`, 그날 댓글이 있으면 `[]`, 아니면 `comment`.
  - `failure_actions(reason: str, open_issues, today, assignees, kind: str = "watch") -> list[dict]`: 표지 `<!-- naegyu-fail:<kind> -->`. 이미 열려 있으면 `comment` 만. `kind="release"` 제목은 "새 판 실패".
  - `apply_actions(actions, gh) -> None`: 담당자 지정 때문에 만들기가 실패하면 지정 없이 다시 만들고 글에 적는다.
  - `save_wait(f, root: Path) -> str`: `drop_wait` 로 같은 내규의 옛 폴더를 지운 뒤 `alio_report.save_bundle(root / "대기", f)`. 돌려주는 값은 `/` 로 쓴 저장소 기준 경로.
  - `drop_wait(name: str, root: Path) -> int`: `<safe_name(이름)>_<숫자>` 가 정확히 맞는 폴더만 지운다.
  - `run_ci(http, gh, compare, now, root: Path, weekly: bool = True, tries: int = 2, wait: int = 300, sleep=time.sleep) -> int`(0 또는 1). 예외를 밖으로 내지 않는다. `gh(args: list[str], stdin: str | None) -> str` 를 주입받는다.
  - 명령: `python3 -X utf8 scripts/watch_ci.py [--no-weekly]`, `watch_ci.py --report-failure "<사유>" [--kind release]`. `--report-failure` 는 패키지 설치가 실패해도 돌아야 하므로 파일 맨 위 import 는 표준 라이브러리, `alio_types`, `alio_report`, `alio_client` 까지만 쓰고 나머지는 `run_ci` 안에서 부른다.
  - 쓰는 파일: `reports/alio_watch/latest.json`(`{"today", "findings"}`, `files` 를 뺀 `dataclasses.asdict`), `reports/alio_watch/last_run.json`(날짜·판정 수·성공 여부 `ok`). 커밋은 워크플로가 한다.
- 고정 이름: 라벨 `개정 의심`, 기록 이슈 제목 `매주 확인 기록`. 저장소 변수 `NAEGYU_ASSIGNEES`(쉼표로 나눈 GitHub 아이디).

- [ ] **Step 1: 실패하는 시험을 더한다**

```python
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
F2 = T.Finding(name=dirty, code="", idx="1", verdict=T.V_NEW, title=dirty, st_date="2026.11.02", mod="2026.11.09")
b2 = WC.issue_body(F2, "2026-11-09")
ok("@홍" not in b2 and "<script" not in b2 and "@" not in WC.issue_title(F2), "지저분한 이름도 글을 깨지 않고 알림을 보내지 않는다")
F3 = T.Finding(name="큰 내규", code="X", idx="2", verdict=T.V_SUSPECT, title="큰 내규", compare=cmp_res(changed_units=["별표"], before_after=[("별표", "옛" * 50000, "새" * 50000)]))
b3 = WC.issue_body(F3, "2026-11-09")
ok(len(b3) <= 60000 and "잘렸" in b3 and WC.marker("2") in b3, "긴 글은 한도 안으로 자르고 알린다")

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
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `python3 -X utf8 scripts/test_browser_ops.py; echo exit=$?`
Expected: `ModuleNotFoundError: No module named 'watch_ci'`

- [ ] **Step 3: 만든다**

`run_ci` 순서:
1. `gh label create "개정 의심" --force`.
2. 모으기: `build_release`(`data/rules.json`, `원본/`, `alio_seen.json`) → `fetch_list` → `check_sanity` → 전체 `fetch_attachments`(하나라도 실패하면 전체 실패) → `judge`. 실패하면 `wait` 초 뒤 한 번 더. 그래도 실패하면 `failure_actions`, `last_run.json`, `1`.
3. `ATTENTION` 은 `save_wait`.
4. 열린 이슈 읽기(`gh issue list --state open --limit 200 --json number,title,body,createdAt,comments`), `lastCommentDate` 계산.
5. `days`: `elapsed_days(f.mod, 그 이슈의 createdAt 또는 None, today)`.
6. `plan_actions`, `apply_actions`. 닫는 이슈의 내규는 `drop_wait`. 닫을 때 말고는 `대기/` 를 지우지 않는다(담당자가 직접 올린 파일이 있을 수 있다).
7. `weekly` 면 `heartbeat_actions`. 처음 만들 때 `gh issue pin`.
8. 열린 `naegyu-fail:watch` 이슈를 닫는다. `latest.json`, `last_run.json` 쓰기. `0`.

어느 단계든 예외는 실패 처리로 넘기고, 실패 처리 자체가 실패해도 `1` 을 돌려준다. `gh` 기본값은 `subprocess.run(["gh", *args], input=stdin, text=True, capture_output=True, check=True)`, 글은 `--body-file -` 로 넘긴다. 긴 글은 개정 전·후 글을 먼저 자르고 "잘렸습니다"를 적는다. 다음 할 일에는 `https://claude.ai/code` 와 "내규 개정 반영이라고 말합니다"를 적는다.

- [ ] **Step 4: 시험 통과를 확인하고 커밋한다**

Run: `python3 -X utf8 scripts/test_browser_ops.py; echo exit=$?`
Expected: `exit=0`

```bash
git add scripts/watch_ci.py scripts/test_browser_ops.py
git commit -m "매주 확인: 판정 결과를 이슈·대기 폴더·기록으로 내기"
```

### Task 6: 확인함 댓글

**Files:**
- Create: `scripts/confirm_ci.py`
- Modify: `scripts/test_browser_ops.py`

**Interfaces:**
- Consumes: `alio_confirm.apply_confirm(item, reason, today, seen_path, rebuild)`, `watch_ci.marker/drop_wait/kst_date`, `reports/alio_watch/latest.json`
- Produces:
  - `parse_reason(comment: str) -> str | None`: `확인함: 사유`(앞뒤 공백, `확인함 : 사유` 허용). 아니면 `None`. 사유가 비면 `""`.
  - `allowed(association: str) -> bool`: `OWNER`, `MEMBER`, `COLLABORATOR` 만.
  - `idx_of(issue_body: str) -> str | None`
  - `handle(comment, association, issue_body, today, latest: dict, seen_path, gh, issue_number, root: Path) -> str`: `"무시"`, `"다시 요청"`, `"기록함"`, `"대상 없음"`.
  - 명령: 환경 변수 `COMMENT_BODY`, `ASSOCIATION`, `ISSUE_BODY`, `ISSUE_NUMBER` 를 읽는다.

- [ ] **Step 1: 실패하는 시험을 더한다**

```python
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
    ok(call("확인함:", "OWNER", g) == "다시 요청" and json.loads(sp.read_text(encoding="utf-8"))["rules"]["9387"]["mod"] == "m1" and "comment" in g.calls[-1], "사유가 비면 다시 적어 달라고 답한다")
    g = FakeGh()
    r = call("확인함: 재게시", "OWNER", g)
    s = json.loads(sp.read_text(encoding="utf-8"))["rules"]["9387"]
    ok(r == "기록함" and s["mod"] == "m2" and s["confirmed"]["reason"] == "재게시" and any("close" in c for c in g.calls), "기록하고 이슈를 닫는다")
    ok(not (td / "대기" / "복무세칙_20261102").exists(), "대기 폴더도 지운다")
    ok(call("확인함: 사유", "OWNER", FakeGh(), WC.marker("555")) == "대상 없음", "최근 결과에 없는 내규는 기록하지 않는다")
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `python3 -X utf8 scripts/test_browser_ops.py; echo exit=$?`
Expected: `ModuleNotFoundError: No module named 'confirm_ci'`

- [ ] **Step 3: 만든다**

`apply_confirm(..., rebuild=lambda: None)` 을 쓴다. `dist/` 는 저장소 밖이다. 판 번호는 건드리지 않는다. 결과를 쉬운 말로 이슈 댓글로 남긴다(`대상 없음` 일 때도 알린다).

- [ ] **Step 4: 시험 통과를 확인하고 커밋한다**

Run: `python3 -X utf8 scripts/test_browser_ops.py; echo exit=$?`
Expected: `exit=0`

```bash
git add scripts/confirm_ci.py scripts/test_browser_ops.py
git commit -m "확인함: 이슈 댓글로 알림 끝내기"
```

### Task 7: 시험과 새 판 워크플로

**Files:**
- Create: `scripts/release_ci.py`, `.github/actions/setup/action.yml`, `.github/actions/checks/action.yml`, `.github/workflows/watch.yml`, `confirm.yml`, `check.yml`, `release.yml`
- Modify: `scripts/update_rules.py`, `scripts/test_browser_ops.py`

**Interfaces:**
- Produces:
  - `update_rules.build_all()`: `finish` 에서 판 번호·지문·원본 기록을 뺀 부분(`check_approval_table`, 낱말 경계, 양식 떼기·검사, `build_web`, `export_gpts`, `review_workbook export`). `finish` 가 이것을 부른다. 명령 `update_rules.py build`.
  - `update_rules.refresh_alio` 의 경고: `ALIO 기록 갱신 실패` 는 그대로 두고 "합친 뒤 GitHub이 자동으로 다시 합니다. Claude 웹에서는 늘 이렇게 나오니 그대로 넘어가세요"로 고친다.
  - `release_ci.tag_of(no: int) -> str`(`"v12"`), `should_release(no: int, tags: list[str]) -> bool`
  - `release_ci.number_problem(changed: list[str], no: int, tags: list[str]) -> str | None`: `원본/` 이나 `knowledge/**/*.json`(`alio_seen.json`, `site.json` 제외)이 바뀌었는데 `no` 가 태그 최댓값보다 크지 않으면 쉬운 말. 태그가 없으면 `None`.
  - `release_ci.decide(no: int, tags: list[str], changed: list[str]) -> str`: `"publish"`, `"skip"`, `"warn"`.
  - `release_ci.assets(no: int, dist: Path, reports: Path, out: Path) -> list[Path]`: `내규챗봇_제N판.html`, `내규챗봇_제N판_artifact.html`, `GPTs_제N판.zip`, `검수표_제N판.zip`, `바뀐_내용_제N판.md`. 하나라도 없으면 `FileNotFoundError`.
  - `release_ci.notes(no: int, summary: str) -> str`: 새 판 안내(망연계로 옮기는 법 포함). `summary` 는 이번 합치기의 커밋 메시지.
  - 명령 `release_ci.py check-number <base_sha>`, `release_ci.py publish <before_sha>`. 태그는 `git tag --list 'v*'`.

- [ ] **Step 1: 실패하는 시험을 더한다**

```python
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
wf = {n: (ROOT / ".github" / "workflows" / n).read_text(encoding="utf-8") for n in ("watch.yml", "confirm.yml", "check.yml", "release.yml")}
ok(not any("pull_request_target" in t for t in wf.values()), "pull_request_target 을 쓰지 않는다")
ok(all("permissions:" in t for t in wf.values()), "권한을 적어 둔다")
ok("schedule:" in wf["watch.yml"] and "workflow_dispatch" in wf["watch.yml"] and "cron: '0 0 * * 1'" in wf["watch.yml"], "월요일 아침(한국 시간 9시)에 돌고 손으로도 돌릴 수 있다")
ok(all("github.event.repository.fork != true" in wf[n] for n in ("watch.yml", "confirm.yml", "release.yml")), "포크에서는 돌지 않는다(저장소 이름을 박아 두지 않아 넘겨도 된다)")
ok("contents: read" in wf["check.yml"] and "issue_comment" in wf["confirm.yml"], "PR 시험은 읽기 권한만, 확인함은 댓글에 반응")
ok(all(ln.strip().startswith(("COMMENT_BODY:", "ISSUE_BODY:", "if:")) for ln in wf["confirm.yml"].splitlines() if "comment.body" in ln or "issue.body" in ln), "댓글 글자는 환경 변수로만 넘긴다")
ok(all("naegyu-write" in wf[n] for n in ("watch.yml", "confirm.yml", "release.yml")), "커밋하는 작업이 겹치지 않는다")
ok("--no-weekly" in wf["release.yml"] and "test_browser_ops.py" in (ROOT / ".github" / "actions" / "checks" / "action.yml").read_text(encoding="utf-8"), "합친 뒤 판정은 댓글 없이, 시험 묶음에 새 시험 포함")
src = (ROOT / "scripts" / "update_rules.py").read_text(encoding="utf-8")
ok("def build_all" in src and "합친 뒤 GitHub" in src, "화면 만들기를 나누고 ALIO 경고를 쉬운 말로 고친다")
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `python3 -X utf8 scripts/test_browser_ops.py; echo exit=$?`
Expected: `ModuleNotFoundError: No module named 'release_ci'`

- [ ] **Step 3: 만든다**

- `setup/action.yml`(composite): Python 3.12, Node 22, npm·pip 캐시, `setup_project.py --full`. `PYTHONUTF8=1`.
- `checks/action.yml`(composite): `check_knowledge.py`, `test_watch_alio.py`, `test_browser_ops.py`, `test_forms.py`, `node scripts/test_engine.js`, `update_rules.py build`, `node --max-old-space-size=8192 scripts/ui_test.js dist/index.html`.
- 저장소에 커밋하는 단계는 모두 `git pull --rebase` 뒤 올리고, 파일을 지정해 `git add` 하고, 메시지 끝에 `[skip ci]`. `GH_TOKEN: ${{ github.token }}`. `actions/checkout` 은 `fetch-depth: 0`(태그와 비교용).
- `watch.yml`: `schedule`, `workflow_dispatch`. `contents: write`, `issues: write`. 준비 → `watch_ci.py` → (`if: always()`) `대기/`, `reports/alio_watch/` 커밋. 준비가 실패하면 마지막 단계(`if: failure()`)에서 `watch_ci.py --report-failure "준비 실패"`.
- `confirm.yml`: `issue_comment` 의 `created`. `if` 로 `contains(github.event.comment.body, '확인함')` 과 `OWNER·MEMBER·COLLABORATOR` 만. 파이썬만 설정한다(패키지 설치 불필요). `confirm_ci.py` → `knowledge/alio_seen.json`, `대기/` 커밋. 댓글·이슈 글자는 `env:` 로 넘긴다.
- `check.yml`: `pull_request`. `contents: read`, `pull-requests: write`. 준비 → 시험 묶음 → `release_ci.py check-number ${{ github.event.pull_request.base.sha }}`. 실패하면(포크가 아닐 때만) "합치지 말고 Claude 웹에 이 글을 보여 주세요" 댓글.
- `release.yml`: `push` to main, `paths-ignore` 로 `대기/**`, `reports/alio_watch/**`. `contents: write`, `issues: write`. 준비 → 시험 묶음 → `alio_release.py refresh` 와 `watch_ci.py --no-weekly`(둘 다 `continue-on-error`. ALIO가 막혀도 새 판은 만든다. 다음 주 판정이 스스로 맞춘다) → `knowledge/alio_seen.json`, `대기/`, `reports/alio_watch/` 커밋 → `release_ci.py publish ${{ github.event.before }}`. `decide` 가 `warn` 이면 Release를 건드리지 않고 `watch_ci.py --report-failure "..." --kind release`. 어느 단계든 실패하면(`if: failure()`) 같은 명령으로 알린다. 재시험에 실패한 판은 올라가지 않는다.
- 저장소에 커밋하는 세 워크플로는 `concurrency: naegyu-write` 로 묶는다.
- 포크 막기: 위 세 워크플로의 작업 `if` 에 `github.event.repository.fork != true`.

- [ ] **Step 4: 시험 통과와 맥 동작을 확인한다**

Run: `python3 -X utf8 scripts/test_browser_ops.py; echo exit=$?; python3 -X utf8 scripts/test_watch_alio.py >/dev/null; echo watch=$?; python3 -X utf8 scripts/update_rules.py build | tail -2; git status --short | cut -c1-60`
Expected: `exit=0`, `watch=0`, 빌드 성공, 판 번호 그대로. `build` 로 바뀐 추적 파일(`knowledge/word_bounds.json`, 검수표 등)이 있으면 커밋하지 말고 무엇이 왜 바뀌는지 보고서에 적은 뒤, 그 파일만 `git restore` 로 되돌린다. 다른 작업의 파일은 건드리지 않는다.

워크플로 실제 동작은 Task 9에서 확인한다.

- [ ] **Step 5: 커밋한다**

```bash
git add scripts/release_ci.py scripts/update_rules.py scripts/test_browser_ops.py .github
git commit -m "GitHub 시험과 새 판 워크플로"
```

### Task 8: 스킬과 안내 문서

**Files:**
- Create: `CLAUDE.md`, `.claude/skills/naegyu-update/SKILL.md`, `docs/담당자_시작_안내.md`
- Modify: `docs/유지보수_안내.md`, `README.md`, `scripts/test_browser_ops.py`
- Delete: `skills/naegyu-update/SKILL.md`(저장소 안 이전)

**Interfaces:** 설계 6.6, 6.9를 따른다. 시험은 문구 존재만 본다.

- [ ] **Step 1: 실패하는 시험을 더한다**

```python
sk = (ROOT / ".claude" / "skills" / "naegyu-update" / "SKILL.md").read_text(encoding="utf-8")
ok(sk.startswith("---\nname: naegyu-update") and "대기/" in sk and "원본/" in sk and "update_rules.py finish" in sk and "Pull Request" in sk and "개정 반영 이어서" in sk and "setup_project.py" in sk and "--allow-changes" in sk and "Library/Mobile" not in sk and "~/Projects" not in sk, "스킬이 클라우드 흐름을 따른다")
ok("합치지 않" in sk, "Claude가 직접 합치지 않는다고 적혀 있다")
ok("blind_check.py prepare" in sk and "새 Claude 웹 세션" in sk, "재확인 단계와 대안이 있다")
cl = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
ok(all(w in cl for w in ("쉬운 한국어", "ZIP", "4.24.1", "git add -A", "ALIO", "시험 질문")), "프로젝트 설명서에 주의점이 있다")
guide = (ROOT / "docs" / "유지보수_안내.md").read_text(encoding="utf-8")
ok(all(w in guide for w in ("확인함:", "매주 확인 기록", "미반영 공지", "대기/", "Release")) and "이 맥 1대" not in guide, "유지보수 안내가 브라우저 흐름이다")
start = (ROOT / "docs" / "담당자_시작_안내.md").read_text(encoding="utf-8")
ok(all(w in start for w in ("github.com", "claude.ai/code", "Merge pull request", "알림")), "담당자 시작 안내")
ok(not (ROOT / "skills" / "naegyu-update" / "SKILL.md").exists(), "옛 스킬 위치를 없앤다")
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `python3 -X utf8 scripts/test_browser_ops.py; echo exit=$?`
Expected: `FileNotFoundError`

- [ ] **Step 3: 쓴다**

- **스킬:** 5단계를 설계 6.6대로 고친다. 첫 단계는 `setup_project.py --full`(처음 시작) 또는 `--full --allow-changes`(이어 하기)로 준비를 확인한다. 한도에 걸렸을 때, ALIO 접속이 막혀 있는 점을 적는다. `finish` 의 ALIO 경고는 정상이라고 적는다. 재확인은 6.7 순서(`prepare` → 하위 작업이 답 → `first` → 2차 → `finish`). 하위 작업에 카드 파일을 읽지 말라고 적는다. 버튼 도구가 없으면 다음 할 말을 글로 알려 준다. 계산기 끄기 절은 그대로 둔다.
- **`CLAUDE.md`:** 설계 6.9의 목록. 만든 사람의 기억 파일에 있던 주의점을 담당자용으로 옮긴다(시험 질문을 프롬프트에 넣지 않기, 카드 전문 단어 등). kordoc 판을 올리는 절차도 적는다. 맥에서도 갈래와 PR을 쓴다.
- **`docs/담당자_시작_안내.md`:** 비개발자가 처음 한 번 할 일. 누를 영어 버튼 이름을 그대로 쓴다.
- **`docs/유지보수_안내.md`:** 브라우저 흐름으로 고친다. 메일이 안 오면 할 일, 사용 한도, 내규관리부서에서 먼저 받은 파일 올리기, 인계 할 일(기관 문서 문구 포함, 설계 6.9).
- **`README.md`:** 폴더 역할, 시작하는 법, `install_watch.py` 는 예비.

- [ ] **Step 4: 시험 통과를 확인하고 커밋한다**

Run: `python3 -X utf8 scripts/test_browser_ops.py; echo exit=$?`
Expected: `exit=0`

```bash
git rm -q skills/naegyu-update/SKILL.md
git add CLAUDE.md .claude/skills/naegyu-update/SKILL.md docs/담당자_시작_안내.md docs/유지보수_안내.md README.md scripts/test_browser_ops.py
git commit -m "저장소 안의 스킬과 프로젝트 설명서, 담당자 안내"
```

### Task 9: 올리기와 실제 시험(통제자가 직접)

하위 작업에 맡기지 않는다. **Step 1~2는 사용자 허락이 있어야 넘어간다.**

- [ ] **Step 1: 올리기 전 점검을 돌리고 사용자에게 묻는다**

`check_upload.py` 와 `--history` 결과, 파일 목록, 공개로 올라갈 내부 자료(설계 6.2)를 보여 주고 묻는다. 커밋 작성자 메일을 noreply로 바꿀지, 내부 자료를 올릴지 뺄지. **허락 없이 넘어가지 않는다.**

- [ ] **Step 2: 답대로 정리하고 올린다**

메일을 바꾸기로 하면 고치기 전에 `git bundle` 로 전체를 백업하고, 올릴 기록만 고친다(원격이 없어 안전. 커밋 번호가 바뀌니 기억 파일의 번호도 고친다). 내부 자료를 빼기로 하면 `.gitignore` 와 스킬 경로를 맞춘다. main에 합치고 올린다: `git remote add origin https://github.com/chromehearts79/naegyu-chatbot.git`, `git push -u origin main`. `gh api "repos/chromehearts79/naegyu-chatbot/git/trees/main?recursive=1"` 로 `[개정근거]`, `contacts` 가 없는지 확인한다.

- [ ] **Step 3: 실제 워크플로를 확인한다**

- 저장소 변수 `NAEGYU_ASSIGNEES` 를 `chromehearts79` 로 둔다(담당자가 정해지면 바꾼다).
- `release.yml` 실행: 원본 72개 **바뀐 단위 0개, 다시 확인 문답 0장**, 첫 Release `v<N>` 생성, 파일 내려받아 카드 수 확인.
- `watch.yml` 손 실행: "이번 주 변동 없음" 댓글과 메일, `last_run.json` 커밋.
- 이슈 라벨 생성 확인. 각 작업의 소요 시간을 잰다.

- [ ] **Step 4: 연습 한 바퀴**

임시 공개 복사 저장소에서: 문답이 적은 내규 하나의 `alio_seen.json` 값을 옛 값으로 되돌려 `watch.yml` → 이슈 → 클라우드 세션 "내규 개정 반영" → PR → 합치기 → Release. 확인함 댓글, 일부러 시험을 실패시켜 Release가 안 만들어지는 것, 같은 번호 PR까지 확인한다. 끝나면 사용자 허락을 받아 지운다.

- [ ] **Step 5: AI 재확인 20장 시험**

`blind_check.py sample 20` 으로 고른 문답을 클라우드 세션에서 돌린다. 하위 작업이 되는지 확인한다. '판정 필요' 비율을 지금 결과와 비교해 보고한다. 하위 작업이 안 되면 새 세션 방식으로 스킬을 고치고 커밋한다.

- [ ] **Step 6: 마무리**

- 이 맥의 `~/.claude/skills/naegyu-update` 를 지우고 알린다.
- 맥 시험 전체 통과, `update_rules.py status`, 화면 파일 카드 수가 옮기기 전과 같은지 확인.
- 소요 시간과 사용 한도 측정값을 `docs/유지보수_안내.md` 에 적는다.
- 담당자 인수 시험 항목(설계 8장)을 사용자에게 넘긴다.
