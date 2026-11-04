# ALIO 확인 루틴 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 매주 ALIO를 자동으로 확인해, 개정이 잡히면 파일을 대기 폴더에 받고 바뀐 조문·고칠 문답·계산기 수까지 담당자 PC에 알리는 프로그램을 만든다.

**Architecture:** 파이썬 표준 라이브러리만 쓰는 작은 모듈들로 나눈다. 통신(`alio_client`), 현행 파일 고르기(`alio_pick`), 지문과 배포판 목록(`alio_release`), 판정과 실행(`watch_alio`), 원문 비교(`alio_compare`, 정 담당 PC 전용), 결과 화면(`alio_report`), 설치(`install_watch`). 기준값은 PC가 아니라 저장소의 `knowledge/alio_seen.json` 과 배포된 `release.json` 에 둔다.

**Tech Stack:** Python 3.11+(표준 라이브러리만), kordoc 4.24.42(원문 비교 때만), 윈도우 작업 스케줄러. 시험은 저장소 방식(`ok(cond, msg)` 평문 스크립트).

**Spec:** `docs/superpowers/specs/2026-11-04-alio-watch-design.md`

## Global Constraints

- 파이썬 3.11 이상. `alio_compare`·`alio_confirm` 을 뺀 모듈은 표준 라이브러리와 서로만 import 한다(부 담당 PC에는 저장소가 없다).
- 새 코드는 파일을 열 때 `encoding="utf-8"` 을 쓴다. 저장소 기존 스크립트를 부를 때는 `-X utf8` 을 붙인다.
- 판정 이름은 설계 6.4 그대로: `변동 없음`, `이미 반영`, `글자 변화 없음`, `배포 대기`, `조문 밖 변화`, `개정 의심`, `담당자 확인`, `새 내규`, `목록에서 사라짐`, `확인 실패`.
- 원문 비교는 실제 `data/`·`knowledge/` 를 바꾸지 않는다. 내규 원본 폴더는 읽기만 한다.
- AI를 쓰지 않는다. 접속은 `https://www.alio.go.kr` 과 `release_url` 뿐이다. 개인 메일을 요청에 넣지 않는다.
- 받은 파일은 hwp·hwpx·xlsx·zip 만 읽고 실행하지 않는다. ZIP 경로는 파일 이름만 쓴다.
- 화면 문구는 쉬운 한국어. 화면에 넣는 ALIO·파일 글자는 `html.escape` 한다.
- 시험 실행: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`. 통과는 `✗` 없음과 `exit=0`. 파일 끝의 `sys.exit(1 if FAIL else 0)` 은 항상 맨 끝에 두고, 태스크마다 그 앞에 시험을 더한다.
- `alio-watch` 갈래에서만 커밋한다. main 합치기와 밀어 올리기는 사용자가 말할 때만 한다. 커밋은 파일을 지정해 올리고 `knowledge/contacts.json`, `reports/contacts/`, `scripts/contacts_report.py` 는 건드리지 않는다. 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- 맥 자동 실행은 만들지 않는다. 실제 운영은 윈도우 이전 과제 뒤에 시작한다(설계 13장).

## Review Focus

1. **첨부 목록 71건 중 1건만 시간 초과:** 일부 결과로 "변동 없음"을 내지 않고 실행 전체가 `확인 실패`가 된다. Task 7에 시험.
2. **담당자가 `기록.csv` 를 엑셀로 열어 둔 상태(쓰기 실패):** 결과 화면은 그대로 나오고 "기록을 쓰지 못했다"고 표시한다. Task 6에 시험.
3. **PC 강제 종료로 잠금 파일이 남은 경우:** 오래된 잠금(2시간 초과)은 무시하고 돈다. 조용히 영원히 멈추면 안 된다. Task 7에 시험.
4. **손상되거나 암호 걸린 ZIP:** 그 내규만 `담당자 확인`이 되고 나머지는 계속 판정한다. Task 1·4에 시험.
5. **내규·파일 이름에 윈도우 경로에 못 쓰는 글자(`:`, `/`, `?`)나 지나치게 긴 이름:** 대기 폴더 저장이 실패하지 않는다. Task 6에 시험.

---

### Task 1: 현행 묶음 고르기

**Files:**
- Create: `scripts/alio_pick.py`, `scripts/test_watch_alio.py`
- 함께 커밋: 설계 문서, 이 계획, `README.md`, `reports/governance/위험평가_운영관리방안.md`, `.hwpx`

**Interfaces:**
- Produces:
  - `read_date(name: str) -> tuple[int, int, int] | None` (파일 이름만 읽음. 일이 없으면 일 자리 0)
  - `format_date(d) -> str` (`"2026.08.12"`, 일이 없으면 `"2024.01"`)
  - `date_matches(d, st_date: str) -> bool` (일이 있으면 일까지, 없으면 월까지)
  - `Bundle(date, files: list[tuple[str, bytes]], problems: list[str])` 데이터클래스
  - `pick_bundle(attachments: list[tuple[str, bytes]], st_date: str) -> Bundle` (예외를 내지 않음)
  - 상수 `MAX_ZIP_MEMBERS = 2000`, `MAX_TOTAL_BYTES = 300_000_000`, `MAX_ZIP_DEPTH = 2`

- [ ] **Step 1: 갈래를 만들고 지금까지의 문서를 커밋한다**

```bash
cd ~/Projects/naegyu-chatbot && git checkout -b alio-watch
git add docs/superpowers README.md "reports/governance/위험평가_운영관리방안.md" "reports/governance/위험평가_운영관리방안.hwpx"
git commit -m "ALIO 확인 루틴 설계·계획, ALIO 위임전결 관련 잘못된 문장 정정"
```

- [ ] **Step 2: 실패하는 시험을 쓴다**

```python
"""ALIO 확인 루틴 시험.

  python3 -X utf8 scripts/test_watch_alio.py
"""
import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alio_pick  # noqa: E402
from alio_pick import date_matches, format_date, pick_bundle, read_date  # noqa: E402

FAIL = []


def ok(cond, msg):
    print(("✓ " if cond else "✗ ") + msg)
    if not cond:
        FAIL.append(msg)


class Cp949Info(zipfile.ZipInfo):  # ALIO ZIP처럼 UTF-8 표시 없이 cp949 이름을 쓴다
    def _encodeFilenameFlags(self):
        return self.filename.encode("cp949"), self.flag_bits & ~0x800


def mkzip(items, cp949=False):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in items:
            z.writestr(Cp949Info(name) if cp949 else name, data)
    return buf.getvalue()


# 날짜 읽기: ALIO 실제 이름 표기
for name, want in [
    ("복무세칙(2026년도 8월 12일 개정).hwp", (2026, 8, 12)),
    ("예산성과금운영지침(2025년 9월1일 제정).hwp", (2025, 9, 1)),
    ("이사회운영규정(2026년도 8월26일 개정).hwpx", (2026, 8, 26)),
    ("직제운영세칙(2021년도 10월 개정)_1.hwp", (2021, 10, 0)),
    ("정보공개운영세칙(2025년도 10월 21일 개정.hwp", (2025, 10, 21)),
    ("(별표)위임전결기준(2026년도 7월 9일 개정).xlsx", (2026, 7, 9)),
    ("감사운영세칙(2024년도 1월 개정).hwp", (2024, 1, 0)),
    ("규정(22년 10월 개정).hwp", (2022, 10, 0)),
    ("위임전결세칙(2026년도 7월 9일 개정)/위임전결세칙(2021년도 10월 개정).hwp", (2021, 10, 0)),
    ("붙임 서식.hwp", None),
]:
    ok(read_date(name) == want, f"날짜 읽기: {name} → {want}")
ok(format_date((2026, 8, 12)) == "2026.08.12" and format_date((2024, 1, 0)) == "2024.01", "날짜 표기")
ok(date_matches((2026, 8, 12), "2026.08.12") and not date_matches((2026, 8, 12), "2026.08.13"), "일이 있으면 일까지 비교")
ok(date_matches((2024, 1, 0), "2024.01.24") and not date_matches((2024, 1, 0), "2024.02.24"), "월까지만 있으면 월까지 비교")

# 고르기
b = pick_bundle([("규정(2025년도 1월 3일 개정).hwp", b"old"), ("규정(2026년도 2월 4일 개정).hwp", b"new")], "2026.02.04")
ok(b.files == [("규정(2026년도 2월 4일 개정).hwp", b"new")] and not b.problems, "첨부가 여럿이면 최근 일자")

folder = "복무세칙(2026년도 8월 12일 개정)/"
z = mkzip([(folder + "복무세칙(2021년도 8월 개정).hwp", b"old"), (folder + "복무세칙(2026년도 8월 12일 개정).hwp", b"new")], cp949=True)
b = pick_bundle([("복무세칙(2026년도 8월 12일 개정).zip", z)], "2026.08.12")
ok([d for _, d in b.files] == [b"new"] and not b.problems, "ZIP: 폴더 이름의 날짜에 속지 않고 cp949 이름을 읽어 최근 일자를 고른다")

inner = mkzip([("(별표)위임전결기준(2026년도 7월 9일 개정).xlsx", b"x"), ("위임전결세칙(2026년도 7월 9일 개정).hwp", b"h")], cp949=True)
outer = mkzip([("위임전결세칙(2026년도 7월 9일 개정)/위임전결세칙(2021년도 10월 개정).hwp", b"old"),
               ("위임전결세칙(2026년도 7월 9일 개정)/위임전결세칙(2026년도 7월 9일 개정).zip", inner)], cp949=True)
b = pick_bundle([("위임전결세칙(2026년도 7월 9일 개정).zip", outer)], "2026.07.09")
ok(sorted(d for _, d in b.files) == [b"h", b"x"] and not b.problems, "ZIP 안 ZIP: 같은 날짜 한글·엑셀을 묶음으로 읽는다")

b = pick_bundle([("규정(2024년도 12월 개정_1).hwp", b"a"), ("규정(2024년도 12월 개정_2).hwp", b"b")], "2024.12.09")
ok(b.problems, "최신 날짜에 한글 문서가 둘이면 문제로 넘긴다")
b = pick_bundle([("규정(2026년도 2월 4일 개정).hwp", b"s"), ("규정(2026년도 2월 4일 개정).hwp", b"s")], "2026.02.04")
ok(not b.problems and len(b.files) == 1, "이름과 내용이 같은 파일은 하나로 친다")
ok(pick_bundle([("규정(2026년도 2월 4일 개정).hwp", b"s"), ("서식.hwp", b"f")], "2026.02.04").problems, "날짜 없는 이름이 있으면 문제로 넘긴다")
ok(pick_bundle([("규정(2026년도 2월 4일 개정).hwp", b"s")], "2026.03.04").problems, "목록 날짜와 다르면 문제로 넘긴다")
ok(pick_bundle([("규정(2026년도 2월 4일 개정).pdf", b"s")], "2026.02.04").problems, "읽을 수 있는 파일이 없으면 문제로 넘긴다")
ok(pick_bundle([("규정(2026년도 2월 4일 개정).zip", b"PK broken")], "2026.02.04").problems, "손상된 ZIP은 예외 없이 문제로 넘긴다")

evil = mkzip([("../../규정(2026년도 2월 4일 개정).hwp", b"e")])
b = pick_bundle([("규정(2026년도 2월 4일 개정).zip", evil)], "2026.02.04")
ok(b.files and "/" not in b.files[0][0] and ".." not in b.files[0][0], "ZIP 경로는 파일 이름만 쓴다")
deep = mkzip([("a(2026년도 2월 4일 개정).zip", mkzip([("b(2026년도 2월 4일 개정).zip", mkzip([("c(2026년도 2월 4일 개정).hwp", b"x")]))]))])
ok(pick_bundle([("d(2026년도 2월 4일 개정).zip", deep)], "2026.02.04").problems, "ZIP이 2단계를 넘으면 문제로 넘긴다")
alio_pick.MAX_TOTAL_BYTES, keep = 10, alio_pick.MAX_TOTAL_BYTES
ok(pick_bundle([("규정(2026년도 2월 4일 개정).zip", mkzip([("규정(2026년도 2월 4일 개정).hwp", b"x" * 100)]))], "2026.02.04").problems, "크기 상한을 넘으면 문제로 넘긴다")
alio_pick.MAX_TOTAL_BYTES = keep

sys.exit(1 if FAIL else 0)
```

- [ ] **Step 3: 시험이 실패하는지 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`
Expected: `ModuleNotFoundError: No module named 'alio_pick'`, `exit=1`

- [ ] **Step 4: `scripts/alio_pick.py` 를 만든다**

날짜 정규식은 `((?:19|20)?\d{2})\s*년도?\s*(\d{1,2})\s*월(?:\s*(\d{1,2})\s*일)?` 이고, 경로를 뗀 파일 이름의 **마지막** 일치를 쓴다(두 자리 연도는 2000을 더함). ZIP은 `zipfile.ZipFile(..., metadata_encoding="cp949")` 로 열고 확장자로만 판단한다(`.hwpx` 는 열지 않는다). 후보를 모아 `problems` 로 넘기는 경우: 날짜 없는 후보, 후보 없음, 최신 날짜의 한글 문서(hwp·hwpx)가 둘 이상, 목록 날짜 불일치, `BadZipFile`·암호(`RuntimeError`)·`NotImplementedError`, 개수·크기·깊이 상한 초과. 이름과 내용이 같은 후보는 하나로 친다.

- [ ] **Step 5: 시험이 통과하는지 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`
Expected: `✗` 없음, `exit=0`

- [ ] **Step 6: 커밋한다**

```bash
git add scripts/alio_pick.py scripts/test_watch_alio.py
git commit -m "ALIO 파일에서 가장 최근 일자의 현행 묶음 고르기"
```

### Task 2: ALIO 통신

**Files:**
- Create: `scripts/alio_client.py`
- Modify: `scripts/test_watch_alio.py`

**Interfaces:**
- Produces:
  - `AlioError(Exception)`
  - `default_http(path: str, body: dict | None) -> tuple[bytes, str]` (응답 내용, Content-Type. 15초 제한, 3번 시도)
  - `fetch_list(http=default_http) -> list[dict]` 키: `idx, title, st_date, mod, category, table_name, idx_name`
  - `fetch_attachments(row: dict, http=default_http) -> list[dict]` 키: `file_no, name`
  - `fetch_file(file_no: str, http=default_http) -> bytes`
  - 상수 `RETRY_SLEEP = 0.5`, `DELAY = 0.06`

- [ ] **Step 1: 실패하는 시험을 더한다**

```python
import json  # noqa: E402
import urllib.error  # noqa: E402
import alio_client  # noqa: E402
from alio_client import AlioError, fetch_attachments, fetch_file, fetch_list  # noqa: E402

alio_client.RETRY_SLEEP = alio_client.DELAY = 0


def raises(fn, exc=AlioError):
    try:
        fn()
    except exc:
        return True
    return False


ROW = {"title": " 복무세칙 ", "stDate": "2026.08.12", "idate": "2026.08.19", "idx": "9387", "bidType": "K1100", "tableName": "COMM_RULE", "idxName": "RULE_NO"}
sent = []


def http_list(path, body):
    sent.append((path, body))
    return json.dumps({"data": {"result": [ROW], "page": {"totalPage": 1, "totalCount": 1}}}).encode(), "application/json"


rows = fetch_list(http_list)
ok(rows == [{"idx": "9387", "title": "복무세칙", "st_date": "2026.08.12", "mod": "2026.08.19", "category": "K1100", "table_name": "COMM_RULE", "idx_name": "RULE_NO"}], "목록을 읽는다")
ok(sent[0][0] == "/item/itemReportListSusi.json" and sent[0][1]["apbaId"] == "C0352" and sent[0][1]["apbaType"] == "A2004" and sent[0][1]["reportFormRootNo"] == "21110" and sent[0][1]["search_word"] == "" and sent[0][1]["search_flag"] == "title" and sent[0][1]["pageNo"] == 1, "목록 요청 값")
pages = lambda path, body: (json.dumps({"data": {"result": [ROW], "page": {"totalPage": 2, "totalCount": 2}}}).encode(), "application/json")  # noqa: E731
ok(len(fetch_list(pages)) == 2, "여러 쪽을 합친다")
ok(raises(lambda: fetch_list(lambda p, b: (json.dumps({"data": {"result": [ROW], "page": {"totalPage": 1, "totalCount": 5}}}).encode(), ""))), "받은 건수가 totalCount보다 적으면 실패")
ok(raises(lambda: fetch_list(lambda p, b: (b"<html>", "text/html"))), "JSON이 아니면 실패")
ok(raises(lambda: fetch_list(lambda p, b: (b'{"data":{}}', "application/json"))), "data.result가 없으면 실패")

html = """<a href="/download/rulefiledown.json?fileNo=11">a&amp;b(2026년도 1월 개정).hwp</a>
<span onclick="previewAjax('12','c(2026년도 2월 개정).hwp')">미리보기</span>"""
atts = fetch_attachments({"idx": "9387", "category": "K1100", "table_name": "COMM_RULE", "idx_name": "RULE_NO"}, lambda p, b: (html.encode(), "text/html"))
ok(atts == [{"file_no": "11", "name": "a&b(2026년도 1월 개정).hwp"}, {"file_no": "12", "name": "c(2026년도 2월 개정).hwp"}], "첨부 목록: 두 표기를 모두 읽는다")
ok(fetch_attachments({"idx": "1", "category": "", "table_name": "", "idx_name": ""}, lambda p, b: (b"<html></html>", "text/html")) == [], "첨부가 없으면 빈 목록")
ok(raises(lambda: fetch_attachments({"idx": "1", "category": "", "table_name": "", "idx_name": ""}, lambda p, b: (b"downRuleFile(3)", "text/html"))), "첨부 흔적은 있는데 못 읽으면 실패(사이트 개편 의심)")
ok(fetch_file("11", lambda p, b: (b"data", "application/octet-stream")) == b"data", "파일을 받는다")
ok(raises(lambda: fetch_file("11", lambda p, b: (b"<html>", "text/html"))), "파일 대신 웹 페이지가 오면 실패")

calls = []


def flaky(req, timeout=None):
    calls.append(req)
    raise urllib.error.URLError("down")


keep = alio_client.urlopen
alio_client.urlopen = flaky
ok(raises(lambda: alio_client.default_http("/x", None)) and len(calls) == 3, "접속 실패는 3번 시도 뒤 실패")
alio_client.urlopen = keep
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`
Expected: `ModuleNotFoundError: No module named 'alio_client'`

- [ ] **Step 3: `scripts/alio_client.py` 를 만든다**

`from urllib.request import Request, urlopen` 로 받아 쓴다(시험에서 바꿔 끼운다). `OSError`·`http.client.HTTPException` 은 다시 시도한 뒤 `AlioError` 로 바꾼다. 기준 주소 `https://www.alio.go.kr`. 모든 요청 머리에 일반 브라우저 `User-Agent`, `Referer: https://www.alio.go.kr/item/itemOrganList.do?reportFormRootNo=21110`, `Origin` 을 넣는다. 목록 본문은 `{"pageNo", "apbaId": "C0352", "apbaType": "A2004", "reportFormRootNo": "21110", "search_word": "", "search_flag": "title", "bid_type": "", "enfc_istt": ""}` 를 JSON으로 POST 한다. 첨부 목록은 `GET /item/itemBoard21110.do?disclosureNo=null&apbaId=C0352&nowcode=21110&reportFormNo=21110&table_name=..&idx_name=..&idx=..&reportGbn=N&bid_type=..` 이고, 다음 두 정규식으로 읽어 `html.unescape` 한다(`table_name` 이 비면 `COMM_RULE`, `idx_name` 이 비면 `RULE_NO`).

```python
r'<a\b[^>]*href="[^"]*rulefiledown\.json\?fileNo=(\d+)"[^>]*>([^<]*)</a>'
r"previewAjax\(\s*'(\d+)'\s*,\s*'([^']*)'"
```

아무것도 못 읽었는데 `fileNo=\d+|downRuleFile\(` 가 보이면 `AlioError`. 파일은 `GET /download/rulefiledown.json?fileNo=..` 이고 Content-Type이 `text/html`·`application/json` 이면 `AlioError`.

- [ ] **Step 4: 시험이 통과하는지 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`
Expected: `✗` 없음, `exit=0`

- [ ] **Step 5: 실제 사이트로 한 번 확인한다**

Run: `python3 -X utf8 -c "import sys; sys.path.insert(0,'scripts'); import alio_client as a; r=a.fetch_list(); print(len(r), r[0]['title'], len(a.fetch_attachments(r[0])))"`
Expected: 첫 숫자가 `71`(그 사이 내규가 늘었으면 그 수), 첨부 수 1 이상

- [ ] **Step 6: 커밋한다**

```bash
git add scripts/alio_client.py scripts/test_watch_alio.py
git commit -m "ALIO 목록·첨부·파일 받기"
```

### Task 3: 지문과 배포판 목록

**Files:**
- Create: `scripts/alio_release.py`, `knowledge/alio_seen.json`(실행 결과), `reports/alio_seed_report.md`(실행 결과)
- Modify: `scripts/test_watch_alio.py`

**Interfaces:**
- Consumes: `pick_bundle`, `format_date`, `fetch_list`, `fetch_attachments`, `fetch_file`
- Produces:
  - `file_digest(data: bytes) -> str` (SHA-1 앞 16자리)
  - `xlsx_digest(data: bytes) -> str` (칸 값으로 만든 지문: 시트 이름 없이 `(시트 파일, 칸 주소, 공백 정리한 값)` 을 정렬해 SHA-1 앞 16자리)
  - `digest_of(name: str, data: bytes) -> str` (`.xlsx` 면 칸 지문, 아니면 파일 지문)
  - `bundle_digests(files) -> list[str]`
  - `same_as(digests: list[str], entry_files: list[str]) -> bool` (비어 있지 않고 모두 포함)
  - `norm_title(s: str) -> str` (NFC, 공백·`·ㆍ.` 제거)
  - `values_of(row: dict, attachments: list[dict]) -> dict` (`{"mod", "st_date", "file_no"}`, `file_no` 는 번호 최대, 없으면 `""`)
  - `source_entries(sources: dict[str, bytes]) -> dict[str, dict]` (코드 → `{"digests": [...], "ext": ".hwp"}`. 파일 이름 앞의 코드로 묶어 위임전결 엑셀을 같은 내규에 넣는다. `ext` 는 한글 문서 확장자)
  - `build_release(rules: list[dict], sources: dict[str, bytes], seen: dict, release_no: int, built: str) -> dict`
  - `confirm(seen: dict, row: dict, values: dict, file_date: str, reason: str, today: str, gone: bool = False) -> None`
  - `refresh_seen(seen, rows, attachments, fetch, entries, same_text, rules) -> list[str]` (기록을 고치고 경고 목록을 돌려줌)
  - `same_text` 인자는 `same_text(name, code, files) -> bool`, `refresh_seen` 의 `fetch` 는 `fetch(file_no) -> bytes`, `rules` 는 `[{"code", "name"}]`
  - `load_seen(path=SEEN) -> dict`, `write_release() -> dict` (실제 원본·`data/rules.json`·`knowledge/site.json` 으로 `dist/release.json` 을 씀. 판 번호는 그대로)
  - `SEEN = ROOT/"knowledge"/"alio_seen.json"`, `RELEASE = ROOT/"dist"/"release.json"`, `SCHEMA = 1`
  - 명령: `python3 -X utf8 scripts/alio_release.py seed [--force]`, `... refresh`

`knowledge/alio_seen.json` 형식: `{"taken": "YYYY-MM-DD", "rules": {"<idx>": {"name", "title", "mod", "st_date", "file_no", "file_date", "confirmed"?: {"date", "reason", "gone"?}}}}`

`release.json` 형식: `{"schema": 1, "release_no", "built", "rules": [{"name", "code", "idx", "ext", "mod", "st_date", "file_no", "file_date", "files": [...], "confirmed"?}]}`. `alio_seen` 에만 있고 내규에 없는 항목(넣지 않기로 한 새 내규)도 `code: ""`, `files: []` 로 싣는다. 반대로 내규에는 있는데 `alio_seen` 에 없으면 ALIO 값을 빈 문자열로 실어 다음 확인 때 잡히게 한다.

- [ ] **Step 1: 실패하는 시험을 더한다**

```python
import alio_release as AR  # noqa: E402


def xlsx_bytes(value, comment=""):
    buf = io.BytesIO()
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/sharedStrings.xml", f'<sst {ns}><si><t>{value}</t></si></sst>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet {ns}><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c></row></sheetData></worksheet>')
        z.writestr("docProps/core.xml", f"<c>{comment}</c>")
    return buf.getvalue()


ok(AR.file_digest(b"abc") == "a9993e364706816a", "파일 지문은 SHA-1 앞 16자리(source_files.json과 같음)")
ok(AR.xlsx_digest(xlsx_bytes("전결", "a")) == AR.xlsx_digest(xlsx_bytes("전결", "b")), "엑셀: 칸 값이 같으면 파일이 달라도 지문이 같다")
ok(AR.xlsx_digest(xlsx_bytes("전결")) != AR.xlsx_digest(xlsx_bytes("대결")), "엑셀: 칸 값이 바뀌면 지문이 다르다")
ok(AR.same_as(["a"], ["a", "b"]) and not AR.same_as(["a", "c"], ["a", "b"]) and not AR.same_as([], ["a"]), "지문 비교")
ok(AR.norm_title("부정청구등 신고자보호 운영지침") == AR.norm_title("부정청구등 신고자 보호 운영지침") and AR.norm_title("전임·전문직원관리세칙") == AR.norm_title("전임전문직원관리세칙"), "이름 맞추기: 공백·가운뎃점 무시")
ok(AR.values_of({"mod": "m", "st_date": "s"}, [{"file_no": "9", "name": ""}, {"file_no": "10", "name": ""}])["file_no"] == "10", "최신 첨부 번호는 숫자로 비교")

X = xlsx_bytes("전결")
srcs = {"Ⅲ-3-1. 복무세칙.hwp": b"bok", "Ⅲ-7-1. 위임전결세칙.hwp": b"wi", "Ⅲ-7-1._위임전결세칙_(별표)위임전결기준(1).xlsx": X}
ent = AR.source_entries(srcs)
ok(ent["Ⅲ-7-1"]["ext"] == ".hwp" and set(ent["Ⅲ-7-1"]["digests"]) == {AR.file_digest(b"wi"), AR.xlsx_digest(X)}, "엑셀 별표는 같은 코드 내규에 묶인다")
seen = {"taken": "2026-11-04", "rules": {"9387": {"name": "복무세칙", "title": "복무세칙", "mod": "2026.08.19", "st_date": "2026.08.12", "file_no": "100", "file_date": "2026.08.12"},
                                          "777": {"name": "넣지 않은 지침", "title": "넣지 않은 지침", "mod": "2026.10.01", "st_date": "2026.09.30", "file_no": "5", "file_date": "2026.09.30", "confirmed": {"date": "2026-11-09", "reason": "챗봇 범위 밖"}}}}
rel = AR.build_release([{"code": "Ⅲ-3-1", "name": "복무세칙"}], srcs, seen, 7, "2026-11-04")
e = next(x for x in rel["rules"] if x["idx"] == "9387")
ok(rel["schema"] == 1 and rel["release_no"] == 7 and e["name"] == "복무세칙" and e["code"] == "Ⅲ-3-1" and e["mod"] == "2026.08.19" and e["files"] == [AR.file_digest(b"bok")] and e["ext"] == ".hwp", "배포판 목록: 내규 항목")
ok(next(x for x in rel["rules"] if x["idx"] == "777")["files"] == [], "넣지 않기로 한 내규도 기록을 싣는다")

R1 = {"idx": "9387", "title": "복무세칙", "st_date": "2026.11.02", "mod": "2026.11.09"}
A1 = {"9387": [{"file_no": "101", "name": "복무세칙(2026년도 11월 2일 개정).hwp"}]}


def seen1():
    return {"taken": "x", "rules": {"9387": dict(seen["rules"]["9387"])}}


s = seen1()
w = AR.refresh_seen(s, [R1], A1, {"101": b"bok"}.__getitem__, ent, lambda *a: False, [{"code": "Ⅲ-3-1", "name": "복무세칙"}])
ok(s["rules"]["9387"]["mod"] == "2026.11.09" and s["rules"]["9387"]["file_no"] == "101" and s["rules"]["9387"]["file_date"] == "2026.11.02" and not w, "새 원본과 지문이 같으면 기록을 올린다")
s = seen1()
w = AR.refresh_seen(s, [R1], A1, {"101": b"other"}.__getitem__, ent, lambda *a: False, [{"code": "Ⅲ-3-1", "name": "복무세칙"}])
ok(s["rules"]["9387"]["mod"] == "2026.08.19" and any("이 내규는 ALIO 파일과 달라 다음 확인 때 다시 잡힘" in x for x in w), "지문이 다르면 옛 기록을 두고 알린다")
s = seen1()
w = AR.refresh_seen(s, [R1], A1, {"101": b"other"}.__getitem__, ent, lambda *a: True, [{"code": "Ⅲ-3-1", "name": "복무세칙"}])
ok(s["rules"]["9387"]["mod"] == "2026.11.09" and not w, "지문이 달라도 전체 글자가 같으면(재게시) 기록을 올린다")
s = seen1()
AR.confirm(s, R1, {"mod": "2026.11.09", "st_date": "2026.11.02", "file_no": "101"}, "2026.11.02", "내부 파일로 반영", "2026-11-16")
ok(s["rules"]["9387"]["file_no"] == "101" and s["rules"]["9387"]["confirmed"] == {"date": "2026-11-16", "reason": "내부 파일로 반영"}, "확인함: 지금 값과 사유를 남긴다")
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`
Expected: `ModuleNotFoundError: No module named 'alio_release'`

- [ ] **Step 3: `scripts/alio_release.py` 를 만든다**

`CODE = r"^([ⅠⅡⅢⅣ][\d\-]*)\.\s*(.+)$"` 로 파일 이름의 코드를 읽는다(파일 이름은 NFC로 맞춘 뒤). 엑셀 칸은 표준 `zipfile`·`xml.etree` 로 읽는다(공유 문자열 포함, 값의 공백은 `re.sub(r"\s+", " ", v).strip()`). 시험 대상이 되는 함수는 파일을 읽지 않는 순수 함수로 둔다. `update_rules` 는 CLI 함수 안에서만 import 한다(부 담당 PC에는 없다).

`seed` 명령: ALIO 목록과 첨부 전체를 받아 내규마다 `pick_bundle` 을 돌리고, `data/rules.json` 이름과 `norm_title` 로 맞춘다. 다음 중 하나라도 어긋나면 파일을 쓰지 않고 까닭을 출력하고 `exit 1`: 대응 안 되는 내규가 있음, `pick_bundle` 문제가 있음, `st_date >= "2025.10"` 인 내규 중 지문이 다른 것이 있음, 지문이 다른 수가 `EXPECT_DIFF = 24` 가 아님. 통과하면 `knowledge/alio_seen.json`, `dist/release.json`, `reports/alio_seed_report.md`(지문이 다른 24건 목록, 내규관리부서 확인용)를 쓴다. 이미 `alio_seen.json` 이 있으면 `--force` 없이는 거부한다. 판 번호는 `knowledge/site.json` 의 `release.no`.

`refresh` 명령: 받기에 실패하면 경고를 출력하고 옛 기록으로 `dist/release.json` 만 쓰고 `exit 0`. `same_text` 는 `alio_compare.compare_rule(...).whole_same` 를 쓴다(Task 5). 함수 안에서 import 한다.

- [ ] **Step 4: 시험이 통과하는지 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`
Expected: `✗` 없음, `exit=0`

- [ ] **Step 5: 처음 기록을 실제로 만든다**

Run: `python3 -X utf8 scripts/alio_release.py seed; echo exit=$?`
Expected: `규정 71건`, `2025.10 이후 지문 같음 26건`, `지문 다름 24건`, `exit=0`. 위임전결세칙은 '지문 같음' 쪽이어야 한다. 수치가 다르면(그 사이 ALIO에 새 개정이 올라왔을 수 있음) 고치지 말고 멈춰서 사용자에게 알린다.

- [ ] **Step 6: 커밋한다**

```bash
git add scripts/alio_release.py scripts/test_watch_alio.py knowledge/alio_seen.json reports/alio_seed_report.md
git commit -m "내규 파일 지문과 배포판 목록, ALIO 기록 처음 만들기"
```

### Task 4: 판정

**Files:**
- Create: `scripts/alio_types.py`, `scripts/watch_alio.py`
- Modify: `scripts/test_watch_alio.py`

**Interfaces:**
- Consumes: `pick_bundle`, `format_date`, `bundle_digests`, `same_as`, `norm_title`, `values_of`
- Produces (`alio_types.py`):
  - 상수 `V_NONE, V_DONE, V_SAME_TEXT, V_PENDING, V_OUTSIDE, V_SUSPECT, V_CHECK, V_NEW, V_GONE, V_FAIL` (값은 Global Constraints의 판정 이름)
  - `ATTENTION = {V_PENDING, V_OUTSIDE, V_SUSPECT, V_CHECK, V_NEW, V_GONE, V_FAIL}`
  - `CompareResult(changed_units: list[str], stale_cards: list[str], related_cards: list[str], calcs: list[str], added_units: list[str], before_after: list[tuple[str, str, str]], outside_diff: list[str], whole_same: bool, error: str | None = None)`
  - `Finding(name, code, idx, verdict, title="", st_date="", mod="", file_date="", ext="", values=None, notes=[], compare=None, files=[], saved_dir="", target_name="", days=None)` (`values` 는 `values_of` 결과. 확인함에 쓴다)
  - `WatchFailure(Exception)`
- Produces (`watch_alio.py`):
  - `judge(rows, attachments, release, local_release, fetch_file, compare, mode) -> list[Finding]`. `mode` 는 `"full"`·`"alert"`. `compare(name, code, files) -> CompareResult`. 첨부 내려받기 실패는 그대로 던진다.
  - `check_sanity(rows, release) -> None` (`WatchFailure`)

- [ ] **Step 1: 실패하는 시험을 더한다**

```python
import alio_types as T  # noqa: E402
import watch_alio as W  # noqa: E402

OLD, NEW = b"old file", b"new file"
ENTRY = {"name": "복무세칙", "code": "Ⅲ-3-1", "idx": "9387", "ext": ".hwp", "mod": "2026.08.19", "st_date": "2026.08.12", "file_no": "100", "file_date": "2026.08.12", "files": [AR.file_digest(OLD)]}
ROW_SAME = {"idx": "9387", "title": "복무세칙", "st_date": "2026.08.12", "mod": "2026.08.19"}
ROW_NEW = {"idx": "9387", "title": "복무세칙", "st_date": "2026.11.02", "mod": "2026.11.09"}
ATT_SAME = {"9387": [{"file_no": "100", "name": "복무세칙(2026년도 8월 12일 개정).hwp"}]}
ATT_NEW = {"9387": [{"file_no": "101", "name": "복무세칙(2026년도 11월 2일 개정).hwp"}]}


def rel_of(*entries):
    return {"schema": 1, "release_no": 7, "built": "2026-11-04", "rules": list(entries)}


def cmp_res(**kw):
    base = dict(changed_units=[], stale_cards=[], related_cards=[], calcs=[], added_units=[], before_after=[], outside_diff=[], whole_same=False)
    base.update(kw)
    return T.CompareResult(**base)


def one(rows, atts, rel, data=None, compare=None, mode="full", local=None):
    res = W.judge(rows, atts, rel, local, (data or {}).__getitem__, compare or (lambda *a: cmp_res(changed_units=["제1조"])), mode)
    return res[0] if res else None


ok(one([ROW_SAME], ATT_SAME, rel_of(ENTRY)).verdict == T.V_NONE, "ALIO 값이 그대로면 변동 없음(파일을 받지 않음)")
ok(one([ROW_SAME], {"9387": [{"file_no": "101", "name": "복무세칙(2026년도 8월 12일 개정).hwp"}]}, rel_of(ENTRY), {"101": NEW}).verdict == T.V_SUSPECT, "게시일이 그대로여도 첨부 번호가 바뀌면 잡는다")
ok(one([ROW_NEW], ATT_NEW, rel_of(ENTRY), {"101": OLD}).verdict == T.V_DONE, "지문이 배포판과 같으면 이미 반영")
local = rel_of(dict(ENTRY, files=[AR.file_digest(NEW)]))
f = one([ROW_NEW], ATT_NEW, rel_of(ENTRY), {"101": NEW}, local=local)
ok(f.verdict == T.V_PENDING and any("새 판을 올리면 끝남" in n for n in f.notes), "저장소 새 판과 같으면 배포 대기(비교 기준이 이미 새 판이라 비교보다 먼저)")
local = rel_of(dict(ENTRY, mod=ROW_NEW["mod"], st_date=ROW_NEW["st_date"], file_no="101"))
ok(one([ROW_NEW], ATT_NEW, rel_of(ENTRY), {"101": NEW}, local=local).verdict == T.V_PENDING, "저장소 기록에 확인함이 남아 있으면 배포 대기")
ok(one([ROW_NEW], ATT_NEW, rel_of(ENTRY), {"101": NEW}, compare=lambda *a: cmp_res(whole_same=True)).verdict == T.V_SAME_TEXT, "전체 글자가 같으면 글자 변화 없음")
ok(one([ROW_NEW], ATT_NEW, rel_of(ENTRY), {"101": NEW}, compare=lambda *a: cmp_res(outside_diff=["별지"])).verdict == T.V_OUTSIDE, "조문은 같고 전체 글자가 다르면 조문 밖 변화(별지만 바뀐 경우)")
f = one([ROW_NEW], ATT_NEW, rel_of(ENTRY), {"101": NEW}, compare=lambda *a: cmp_res(changed_units=["제19조"], stale_cards=["a"]))
ok(f.verdict == T.V_SUSPECT and f.compare.stale_cards == ["a"] and f.files and f.target_name == "Ⅲ-3-1. 복무세칙.hwp" and f.days is None, "개정 의심: 비교 결과와 원본 폴더에 넣을 이름")
ok(f.values == {"mod": "2026.11.09", "st_date": "2026.11.02", "file_no": "101"} and f.title == "복무세칙" and f.file_date == "2026.11.02", "확인함에 쓸 ALIO 값을 함께 둔다")
called = []
f = one([ROW_NEW], ATT_NEW, rel_of(ENTRY), {"101": NEW}, compare=lambda *a: called.append(a), mode="alert")
ok(f.verdict == T.V_SUSPECT and not called and any("정 담당 PC에서 비교" in n for n in f.notes), "부 담당 PC는 비교하지 않고 개정 의심으로 알린다")
f = one([ROW_NEW], ATT_NEW, rel_of(ENTRY), {"101": NEW}, compare=lambda *a: cmp_res(error="변환 실패"))
ok(f.verdict == T.V_SUSPECT and any("변환 실패" in n for n in f.notes), "비교가 실패해도 개정 의심은 그대로 알리고 사유를 적는다")
f = one([ROW_NEW], {"9387": [{"file_no": "101", "name": "복무세칙(2026년도 8월 12일 개정).hwpx"}]}, rel_of(ENTRY), {"101": NEW}, compare=lambda *a: cmp_res(changed_units=["제1조"]))
ok(f.verdict == T.V_CHECK, "목록 날짜와 파일 날짜가 다르면 담당자 확인")
row_repost = dict(ROW_NEW, st_date="2026.08.12")
f = one([row_repost], ATT_SAME | {"9387": [{"file_no": "101", "name": "복무세칙(2026년도 8월 12일 개정).hwpx"}]}, rel_of(ENTRY), {"101": NEW})
ok(any("날짜가 그대로라 재게시일 수 있음" in n for n in f.notes) and any("형식이 달라 차이가 과장될 수 있음" in n for n in f.notes), "재게시·형식 차이 안내")
ok(one([ROW_NEW], {"9387": [{"file_no": "101", "name": "복무세칙(2026년도 11월 2일 개정).zip"}]}, rel_of(ENTRY), {"101": b"broken"}).verdict == T.V_CHECK, "손상된 ZIP은 그 내규만 담당자 확인")
res = W.judge([ROW_NEW, dict(ROW_SAME, idx="2", title="다른 세칙")], {"9387": [{"file_no": "101", "name": "복무세칙(2026년도 11월 2일 개정).zip"}], "2": []}, rel_of(ENTRY, dict(ENTRY, idx="2", name="다른 세칙", file_no="")), {"101": b"broken"}.__getitem__, lambda *a: None, "full")
ok([x.verdict for x in res] == [T.V_CHECK, T.V_NONE], "손상된 ZIP이 있어도 나머지 내규는 계속 판정한다")
f = one([{"idx": "555", "title": "새 지침", "st_date": "2026.11.02", "mod": "2026.11.09"}], {"555": [{"file_no": "9", "name": "새 지침(2026년도 11월 2일 제정).hwp"}]}, rel_of(), {"9": NEW}, compare=lambda *a: cmp_res(added_units=["제1조", "제2조"]))
ok(f.verdict == T.V_NEW and len(f.compare.added_units) == 2, "배포판에 없으면 새 내규(조문 수)")
res = W.judge([], {}, rel_of(ENTRY), {}.__getitem__, lambda *a: None, "full")
ok([x.verdict for x in res] == [T.V_GONE], "배포판에 있는데 목록에 없으면 목록에서 사라짐")
ok(W.judge([], {}, rel_of(dict(ENTRY, confirmed={"date": "d", "reason": "유효", "gone": True})), {}.__getitem__, lambda *a: None, "full") == [], "사라짐을 확인함으로 끝냈으면 다시 알리지 않는다")
res = W.judge([dict(ROW_NEW, idx="42")], {"42": ATT_NEW["9387"]}, rel_of(ENTRY), {"101": NEW}.__getitem__, lambda *a: cmp_res(changed_units=["제1조"]), "full")
ok([x.verdict for x in res] == [T.V_SUSPECT], "idx가 바뀌어도 이름으로 맞추고 사라짐을 함께 내지 않는다")
ok(raises(lambda: W.check_sanity([], rel_of(ENTRY, ENTRY)), T.WatchFailure) and raises(lambda: W.check_sanity([ROW_SAME], rel_of(ENTRY, ENTRY, ENTRY)), T.WatchFailure), "받은 목록이 배포판의 절반 미만이면 확인 실패")
W.check_sanity([ROW_SAME], rel_of(ENTRY, ENTRY))
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`
Expected: `ModuleNotFoundError: No module named 'alio_types'`

- [ ] **Step 3: `alio_types.py` 와 `watch_alio.py` 의 `judge`·`check_sanity` 를 만든다**

내규별 순서: 배포판 항목을 `idx`, 없으면 `norm_title` 로 찾음 → ALIO 값 셋 비교(같으면 `V_NONE`, 파일 받지 않음) → 모든 첨부를 받아 `pick_bundle`(`problems` 면 `V_CHECK`, 까닭을 notes에) → 항목이 없으면 `V_NEW`(full 모드는 compare 결과를 붙임) → `same_as` 면 `V_DONE` → full 모드에서 `local_release` 항목의 지문이 같거나 ALIO 값 셋이 같으면 `V_PENDING` → alert 모드는 `V_SUSPECT` + `"정 담당 PC에서 비교"` → full 모드는 compare: `error` 면 `V_SUSPECT` + 사유, `whole_same` 면 `V_SAME_TEXT`, 바뀐·새 단위가 없으면 `V_OUTSIDE`, 아니면 `V_SUSPECT`. 안내 문구: 파일 날짜가 `file_date` 와 같으면 `"날짜가 그대로라 재게시일 수 있음"`, 한글 문서 확장자가 항목 `ext` 와 다르면 `"형식이 달라 차이가 과장될 수 있음"`, 배포 대기는 `"새 판을 올리면 끝남"`. `target_name` 은 `f"{code}. {name}{ext}"`(현행본 확장자). 끝으로 쓰이지 않은 항목은 `confirmed.gone` 이 아니면 `V_GONE`.

- [ ] **Step 4: 시험이 통과하는지 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`
Expected: `✗` 없음, `exit=0`

- [ ] **Step 5: 커밋한다**

```bash
git add scripts/alio_types.py scripts/watch_alio.py scripts/test_watch_alio.py
git commit -m "ALIO 확인 판정"
```

### Task 5: 미리 원문 비교

**Files:**
- Create: `scripts/alio_compare.py`
- Modify: `scripts/test_watch_alio.py`

**Interfaces:**
- Consumes: `check_changes.load_rules, units_of, compare, calc_stale, SNAPSHOT, TEXTS`, `check_knowledge.load_domains`, `CompareResult`, `read_date`
- Produces:
  - `KORDOC = "kordoc@4.24.42"`
  - `kordoc_cmd() -> list[str]` (`[shutil.which("npx"), "-y", KORDOC]`. 윈도우에서는 `which` 가 `npx.cmd` 를 찾는다)
  - `compare_md(code: str, name: str, new_md: dict[str, str]) -> CompareResult` (`new_md`: 원래 파일 이름 → 변환 글)
  - `compare_rule(name: str, code: str, files: list[tuple[str, bytes]]) -> CompareResult` (변환 + `compare_md`. 예외를 내지 않고 `error` 에 적음)

- [ ] **Step 1: 실패하는 시험을 더한다**

```python
import hashlib  # noqa: E402
import unicodedata  # noqa: E402
ROOT = Path(__file__).resolve().parent.parent
MD_DIR = ROOT / "data" / "md"


def tree_sig():
    files = [ROOT / "data" / "rules.json", ROOT / "knowledge" / "stale_cards.json", ROOT / "knowledge" / "source_snapshot.json", ROOT / "data" / "snapshot_texts.json"] + sorted(MD_DIR.glob("*.md"))
    return [(p.name, hashlib.sha1(p.read_bytes()).hexdigest()) for p in files]


if MD_DIR.exists():
    import alio_compare as C  # noqa: E402
    ok(C.KORDOC == "kordoc@4.24.42" and C.kordoc_cmd()[1:] == ["-y", "kordoc@4.24.42"], "kordoc 판을 고정한다")
    p = next(x for x in MD_DIR.glob("*.md") if unicodedata.normalize("NFC", x.name) == "Ⅲ-3-1. 복무세칙.md")
    md = p.read_text(encoding="utf-8")
    fname = "복무세칙(2026년도 11월 2일 개정).hwp"
    before = tree_sig()
    lines = md.split("\n")
    i = next(n for n, x in enumerate(lines) if "제4조(" in x)
    lines[i] += " 다만, 시험 문구를 더한다."
    r = C.compare_md("Ⅲ-3-1", "복무세칙", {fname: "\n".join(lines)})
    ok("제4조" in r.changed_units and not r.whole_same and not r.error and r.before_after, f"조문이 바뀌면 잡고 전·후 글자를 준다({r.changed_units[:3]})")
    ok(not any(u.endswith("항") and "조제" in u for u in r.changed_units), "바뀐 조문 수에 항 단위를 겹쳐 세지 않는다")
    r = C.compare_md("Ⅲ-3-1", "복무세칙", {fname: md.replace("\n", "\n\n")})
    ok(r.whole_same and not r.changed_units, "빈 줄만 달라지면 전체 글자가 같다")
    r = C.compare_md("Ⅲ-3-1", "복무세칙", {fname: md + "\n\n[별지 제99호 서식]\n\n시험 양식 본문\n"})
    ok(not r.changed_units and not r.whole_same and r.outside_diff, "별지만 바뀌면 조문 변화 0이어도 전체 글자가 다르다")
    r = C.compare_md("Ⅳ-99", "새 시험 지침", {"새 시험 지침(2026년도 11월 2일 제정).hwp": "제1조(목적) 이 지침은 시험이다.\n\n제2조(적용) 전 직원에 적용한다.\n\n부 칙\n\n이 지침은 2026년 11월 2일부터 시행한다.\n"})
    ok("제1조" in r.added_units and "제2조" in r.added_units and not r.error, "새 내규는 새 조문으로 나온다")
    p2 = next(x for x in MD_DIR.glob("*.md") if "위임전결기준" in unicodedata.normalize("NFC", x.name))
    r = C.compare_md("Ⅲ-7-1", "위임전결세칙", {"(별표)위임전결기준(2026년도 11월 2일 개정).xlsx": p2.read_text(encoding="utf-8") + "\n| 시험 | 칸 |\n"})
    ok(any("별표" in u for u in r.changed_units), "별표 엑셀은 별표 변환본 자리에 들어간다")
    ok(tree_sig() == before, "실제 data·knowledge는 바뀌지 않는다")
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`
Expected: `ModuleNotFoundError: No module named 'alio_compare'`

- [ ] **Step 3: `scripts/alio_compare.py` 를 만든다**

`tempfile.TemporaryDirectory` 에 `scripts/build_db.py` 와 `data/md/*.md`(이미지 빼고)만 복사한다. 자리 찾기는 파일 이름을 NFC로 맞춰 코드가 같은 변환본을 찾는다. `.xlsx` 는 이름에 `위임전결기준` 또는 `별표` 가 든 변환본, 그 밖은 그것이 없는 변환본이다. 없으면 `f"{code}. {name}.md"` 로 새로 만든다. `[sys.executable, "-X", "utf8", tmp/scripts/build_db.py]` 를 돌린 뒤 `check_changes.load_rules(tmp/data/rules.json)` 를 읽어 실제 스냅숏·카드(`load_domains(tolerant=True)`)와 `compare`·`calc_stale` 로 비교하고, **그 내규 것만** 남긴다. 바뀐 조문은 `v != "added"` 이고 항 단위(`"항" in u and "조제" in u`)가 아닌 것, 계산기는 `cites[].cite` 가 `name + " "` 로 시작하는 것의 `title`. `before_after` 는 `data/snapshot_texts.json` 의 옛 글과 `units_of` 새 글로 최대 20개. `whole_same` 은 NFKC로 맞추고 `\s`·`*|-:<>/·ㆍ` 를 지운 글자 비교(묶음의 모든 파일). 다르면 `outside_diff` 는 `difflib.unified_diff` 최대 40줄. `compare_rule` 은 파일을 `f{i}{ext}` 이름으로 임시 저장해 `kordoc_cmd() + ["-d", out, path]` 로 변환하고(`shell=False`), 실패·예외는 모두 `error` 에 적는다. `npx` 가 없으면 `error`.

- [ ] **Step 4: 시험이 통과하는지 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`
Expected: `✗` 없음, `exit=0`

- [ ] **Step 5: 복무세칙 직전 판으로 실제 변환까지 확인한다**

설계 5장의 시험을 다시 돌린다. ALIO `복무세칙` ZIP에서 `복무세칙(2025년도 10월 30일 개정).hwp` 를 꺼내 `compare_rule("복무세칙", "Ⅲ-3-1", [(이름, 내용)])` 를 부른다.

Expected: `changed_units` 7개, `stale_cards` 20장, `related_cards` 14장, `calcs` 4종(배우자 출산휴가, 유산·사산휴가, 가족돌봄휴가, 자녀 나이), `error` 없음. `git status` 에 실제 자료 변화 없음. 카드가 그 사이 바뀌어 수가 다르면 까닭을 확인해 사용자에게 알린다.

- [ ] **Step 6: 커밋한다**

```bash
git add scripts/alio_compare.py scripts/test_watch_alio.py
git commit -m "개정 파일 미리 원문 비교(임시 사본)"
```

### Task 6: 결과 화면·기록·알림

**Files:**
- Create: `scripts/alio_report.py`
- Modify: `scripts/test_watch_alio.py`

**Interfaces:**
- Consumes: `Finding`, `ATTENTION`, 판정 상수
- Produces:
  - `safe_name(s: str, limit: int = 80) -> str`
  - `save_bundle(wait_dir: Path, finding: Finding) -> str` (저장한 폴더 경로)
  - `update_history(csv_path: Path, findings: list[Finding], today: str) -> tuple[dict[str, str], str | None]` (`idx → 처음 잡힌 날`, 실패 사유. 예외를 내지 않음)
  - `elapsed_days(mod: str, first_seen: str | None, today: str) -> int` (게시일과 처음 잡은 날 중 이른 날부터)
  - `render_html(findings, meta: dict) -> str`. `meta` 키: `today, last_success, release_no, release_built, source_note, failure, history_error, mode`
  - `write_outputs(out_dir: Path, html: str, findings, today: str) -> None` (`이번 주 결과.html`, `기록/YYYY-MM-DD.html`, `최근 결과.json`. JSON에 `files` 는 넣지 않음)
  - `notify(title: str, body: str, run=subprocess.run, system: str | None = None) -> bool`
  - `open_page(path: Path) -> None`

- [ ] **Step 1: 실패하는 시험을 더한다**

```python
import datetime  # noqa: E402
import tempfile  # noqa: E402
import alio_report as RP  # noqa: E402

ok(RP.safe_name('a:b/c?*"<>|\\d. ') == "a_b_c_______d" and len(RP.safe_name("가" * 300)) <= 80, "경로에 못 쓰는 글자와 긴 이름을 정리한다")
F = T.Finding(name="복무세칙", code="Ⅲ-3-1", idx="9387", verdict=T.V_SUSPECT, st_date="2026.11.02", mod="2026.11.09", file_date="2026.11.02", ext=".hwp", files=[("복무:세칙(2026).hwp", b"x")], target_name="Ⅲ-3-1. 복무세칙.hwp",
              compare=cmp_res(changed_units=["제19조"], stale_cards=["a", "b"], related_cards=["c"], calcs=["가족수당"], before_after=[("제19조", "옛 <글>", "새 글")]))
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    saved = RP.save_bundle(td / "대기", F)
    ok(Path(saved).parent == td / "대기" and any(Path(saved).iterdir()), "이름에 못 쓰는 글자가 있어도 대기 폴더에 저장한다")
    F2 = T.Finding(name="평가:세칙/?", code="", idx="1", verdict=T.V_SUSPECT, file_date="2026.11", files=[("가" * 300 + ".hwp", b"y")])
    ok(any(Path(RP.save_bundle(td / "대기", F2)).iterdir()), "지나치게 긴 파일 이름도 저장한다")

    csv_path = td / "기록.csv"
    first, err = RP.update_history(csv_path, [F], "2026-11-09")
    ok(first["9387"] == "2026-11-09" and not err and csv_path.read_bytes().startswith(b"\xef\xbb\xbf"), "처음 잡힌 날을 적는다(엑셀용 BOM)")
    first, err = RP.update_history(csv_path, [F], "2026-11-16")
    ok(first["9387"] == "2026-11-09", "다음 주에도 처음 잡힌 날을 유지한다")
    RP.update_history(csv_path, [], "2026-11-23")
    text = csv_path.read_text(encoding="utf-8-sig")
    ok("2026-11-09" in text and "2026-11-23" in text, "해소되면 해소된 날을 적는다")
    bad = td / "열림.csv"
    bad.mkdir()
    first, err = RP.update_history(bad, [F], "2026-11-09")
    ok(err and first == {}, "기록 파일을 쓸 수 없어도(엑셀로 열림) 예외 없이 사유를 돌려준다")

    meta = {"today": "2026-11-09", "last_success": "2026-10-17", "release_no": 7, "release_built": "2026-11-04", "source_note": "", "failure": None, "history_error": "기록.csv를 쓰지 못했습니다", "mode": "full"}
    F.days, F.saved_dir = 15, "C:\\대기\\복무세칙"
    page = RP.render_html([F, T.Finding(name="<b>x</b>", code="", idx="2", verdict=T.V_DONE)], meta)
    ok("마지막 확인: 23일 전" in page and "제7판" in page, "맨 위에 마지막 확인과 판 번호")
    ok("복무세칙" in page and "제19조" in page and "2장" in page and "가족수당" in page and "C:\\대기\\복무세칙" in page and "Ⅲ-3-1. 복무세칙.hwp" in page, "개정 의심: 조문·문답·계산기·파일 위치·넣을 이름")
    ok("정 담당 확인, 부재면 게시판에 미반영 공지" in page and 'class="late"' in page, "14일이 넘으면 빨간 표시와 안내")
    ok("<b>x</b>" not in page and "옛 &lt;글&gt;" in page, "ALIO 글자는 이스케이프한다")
    ok("기록.csv를 쓰지 못했습니다" in page, "기록 실패를 화면에 알린다")
    F.days = 13
    ok('class="late"' not in RP.render_html([F], meta), "14일 전에는 빨간 표시가 없다")
    page = RP.render_html([], dict(meta, last_success=None, failure="ALIO 응답이 이상합니다", history_error=None))
    ok("확인 실패" in page and "ALIO 응답이 이상합니다" in page and "이번 주 변동 없음" not in page, "확인 실패가 변동 없음으로 보이지 않는다")
    page = RP.render_html([], dict(meta, source_note="배포판을 읽지 못해 이 PC의 마지막 빌드와 비교함", history_error=None))
    ok("이번 주 변동 없음" in page and "배포판을 읽지 못해 이 PC의 마지막 빌드와 비교함" in page, "변동 없음과 기준 안내")

    RP.write_outputs(td, "<html>결과</html>", [F], "2026-11-09")
    ok((td / "이번 주 결과.html").exists() and (td / "기록" / "2026-11-09.html").exists(), "이번 주 결과와 보관본을 쓴다")
    saved_json = json.loads((td / "최근 결과.json").read_text(encoding="utf-8"))
    ok(saved_json["findings"][0]["name"] == "복무세칙" and "files" not in saved_json["findings"][0] and saved_json["findings"][0]["values"] is None, "최근 결과에 파일 내용을 넣지 않는다")

ok(RP.elapsed_days("2026.10.20", "2026-11-09", "2026-11-09") == 20, "경과일은 게시일부터")
ok(RP.elapsed_days("2026.11.09", "2026-10-20", "2026-11-09") == 20, "게시일이 밀려도 처음 잡은 날부터")
seen_call = {}


def fake_run(cmd, **kw):
    seen_call.update(cmd=cmd, env=kw.get("env"))


ok(RP.notify("제목", "복무세칙 알림", run=fake_run, system="Windows") and seen_call["cmd"][0] == "powershell" and "복무세칙" not in " ".join(seen_call["cmd"]) and seen_call["env"]["NAEGYU_TOAST_BODY"] == "복무세칙 알림", "윈도우 알림: 글자는 환경 변수로 넘긴다")


def boom(*a, **k):
    raise OSError("no")


ok(RP.notify("t", "b", run=boom, system="Windows") is False and RP.notify("t", "b", run=boom, system="Darwin") is False, "알림 실패는 예외 없이 False")
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`
Expected: `ModuleNotFoundError: No module named 'alio_report'`

- [ ] **Step 3: `scripts/alio_report.py` 를 만든다**

`safe_name`: `<>:"/\|?*` 와 제어 글자를 `_` 로 바꾸고 끝의 점·공백을 지우고 자른다(확장자는 호출하는 쪽에서 살린다). 대기 폴더는 `대기/<safe_name(내규명)>_<파일 날짜 숫자>/`. `기록.csv` 열은 `내규,idx,판정,처음 잡힌 날,해소된 날`, 인코딩 `utf-8-sig`. `ATTENTION` 판정만 적는다. HTML은 한 파일이고 외부 자원이 없다. 새 내규의 조문 수는 `added_units` 중 `제` 로 시작하는 것의 수로 보여 준다. 판정 순서는 `ATTENTION` 먼저, 이미 반영·글자 변화 없음은 건수만 쓴다. 빨간 표시는 `days >= 14` 일 때 행에 `class="late"` 를 달고 `"정 담당 확인, 부재면 게시판에 미반영 공지"` 를 쓴다. 맨 위 문구는 `마지막 확인: N일 전`(없으면 `처음 확인`). 윈도우 알림은 `powershell -NoProfile -ExecutionPolicy Bypass -Command <고정 스크립트>` 로 띄운다. 스크립트는 `$env:NAEGYU_TOAST_TITLE`, `$env:NAEGYU_TOAST_BODY` 를 읽어 `Windows.UI.Notifications.ToastNotificationManager` 로 띄우고, AppId는 `{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe`. 윈도우가 아니면 `False`. `open_page` 는 `webbrowser.open(path.as_uri())`.

- [ ] **Step 4: 시험이 통과하는지 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`
Expected: `✗` 없음, `exit=0`

- [ ] **Step 5: 커밋한다**

```bash
git add scripts/alio_report.py scripts/test_watch_alio.py
git commit -m "ALIO 확인 결과 화면·기록·알림"
```

### Task 7: 한 번 돌리기(실행 전체)

**Files:**
- Modify: `scripts/watch_alio.py`, `scripts/test_watch_alio.py`

**Interfaces:**
- Consumes: `fetch_list`, `fetch_attachments`, `fetch_file`, `judge`, `check_sanity`, `alio_report` 함수들, `compare_rule`(full 모드에서만 함수 안에서 import)
- Produces:
  - `monday_nine(now: datetime) -> datetime` (가장 최근 월요일 9시)
  - `is_due(now: datetime, last_success: str | None) -> bool`
  - `acquire_lock(path: Path, now: float | None = None) -> bool` (2시간 넘은 잠금은 무시), `release_lock(path)`
  - `load_config(path: Path) -> dict` 키: `mode, repo, release_url, release_path, docs_dir`
  - `load_release(cfg: dict, get_url=None) -> tuple[dict, str]` (목록, 기준 안내. 못 읽으면 `WatchFailure`)
  - `run_watch(cfg: dict, now: datetime, http=None, get_url=None, notify=None, open_page=None, compare=None, force: bool = False) -> int` (0 또는 1)
  - 명령: `python -X utf8 scripts/watch_alio.py --config PATH [--force]`
  - 상태 파일(`docs_dir` 안): `.last_success`, `.last_fail_notice`, `.lock`, `실행기록.log`

- [ ] **Step 1: 실패하는 시험을 더한다**

```python
D = datetime.datetime
ok(W.monday_nine(D(2026, 11, 9, 8, 59)) == D(2026, 11, 2, 9, 0) and W.monday_nine(D(2026, 11, 9, 9, 0)) == D(2026, 11, 9, 9, 0) and W.monday_nine(D(2026, 11, 12, 14, 0)) == D(2026, 11, 9, 9, 0), "가장 최근 월요일 9시")
ok(W.is_due(D(2026, 11, 9, 9, 0), "2026-11-02T09:00:00") and not W.is_due(D(2026, 11, 10, 9, 0), "2026-11-09T09:30:00"), "이번 주 성공 기록이 있으면 돌지 않는다")
ok(W.is_due(D(2026, 11, 25, 9, 0), "2026-11-02T09:00:00") and W.is_due(D(2026, 11, 9, 9, 0), None) and W.is_due(D(2026, 11, 9, 9, 0), "깨진 값"), "몇 주 건너뛰거나 기록이 없거나 깨졌으면 돈다")


class Net:
    """가짜 ALIO. rows·attachments·files 를 바꿔 가며 쓴다."""

    def __init__(self, rows, atts, files):
        self.rows, self.atts, self.files, self.fail_idx, self.down = rows, atts, files, None, False
        self.calls = []

    def __call__(self, path, body):
        self.calls.append(path)
        if self.down:
            raise AlioError("접속 실패")
        if path == "/item/itemReportListSusi.json":
            res = [{"title": r["title"], "stDate": r["st_date"], "idate": r["mod"], "idx": r["idx"], "bidType": "K", "tableName": "COMM_RULE", "idxName": "RULE_NO"} for r in self.rows]
            return json.dumps({"data": {"result": res, "page": {"totalPage": 1, "totalCount": len(res)}}}).encode(), "application/json"
        if "itemBoard21110" in path:
            idx = path.split("&idx=")[1].split("&")[0]
            if idx == self.fail_idx:
                raise AlioError("시간 초과")
            return "".join(f'<a href="/download/rulefiledown.json?fileNo={a["file_no"]}">{a["name"]}</a>' for a in self.atts[idx]).encode(), "text/html"
        return self.files[path.split("fileNo=")[1]], "application/octet-stream"


with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    rel_path = td / "release.json"
    rel_path.write_text(json.dumps(rel_of(ENTRY)), encoding="utf-8")
    cfg = {"mode": "alert", "repo": "", "release_url": "", "release_path": str(rel_path), "docs_dir": str(td / "out")}
    notes, opened = [], []
    NOW = D(2026, 11, 9, 9, 5)
    go = lambda net, now=NOW, **k: W.run_watch(cfg, now, http=net, notify=lambda t, b: notes.append(b) or True, open_page=opened.append, **k)  # noqa: E731

    net = Net([ROW_SAME], ATT_SAME, {})
    ok(go(net) == 0 and notes[-1] == "이번 주 변동 없음" and not opened, "변동 없으면 알림만 띄우고 화면은 열지 않는다")
    ok(not any("fileNo" in c for c in net.calls) and any("itemBoard" in c for c in net.calls), "첨부 목록은 보고 파일은 받지 않는다")
    n = len(net.calls)
    ok(go(net, NOW + datetime.timedelta(hours=1)) == 0 and len(net.calls) == n, "이번 주에 성공했으면 조용히 끝난다")

    net = Net([ROW_NEW], ATT_NEW, {"101": NEW})
    ok(go(net, D(2026, 11, 16, 9, 5)) == 0 and opened and "복무세칙" in notes[-1], "개정 의심이면 알리고 결과 화면을 연다")
    ok(any((td / "out" / "대기").iterdir()), "받은 파일을 대기 폴더에 둔다")
    ok((td / "out" / "이번 주 결과.html").exists() and (td / "out" / "기록.csv").exists(), "결과와 기록을 남긴다")

    # 1건만 시간 초과: 전체 실패
    notes.clear()
    net = Net([ROW_SAME, dict(ROW_SAME, idx="2", title="다른 세칙")], {"9387": ATT_SAME["9387"], "2": []}, {})
    net.fail_idx = "2"
    last = (td / "out" / ".last_success").read_text(encoding="utf-8")
    ok(go(net, D(2026, 11, 23, 9, 5)) == 1, "첨부 목록 1건만 실패해도 실행 전체가 실패한다")
    page = (td / "out" / "이번 주 결과.html").read_text(encoding="utf-8")
    ok("확인 실패" in page and "이번 주 변동 없음" not in page and notes and notes[-1] != "이번 주 변동 없음", "실패가 변동 없음으로 보이지 않는다")
    ok((td / "out" / ".last_success").read_text(encoding="utf-8") == last, "실패하면 성공 기록을 남기지 않아 다음 로그인 때 다시 돈다")
    notes.clear()
    ok(go(net, D(2026, 11, 23, 10, 5)) == 1 and not notes, "같은 날 다시 실패하면 알림을 또 띄우지 않는다")
    net.fail_idx = None
    net.rows, net.atts = [ROW_SAME], ATT_SAME
    ok(go(net, D(2026, 11, 25, 9, 0)) == 0, "다음에 접속되면 밀린 확인을 한다")

    # 잠금
    lock = td / "out" / ".lock"
    lock.write_text("x", encoding="utf-8")
    net = Net([ROW_SAME], ATT_SAME, {})
    ok(go(net, D(2026, 11, 30, 9, 5)) == 0 and not net.calls, "다른 실행이 돌고 있으면 그냥 끝난다")
    lock.write_text("x", encoding="utf-8")
    ok(W.acquire_lock(lock, now=lock.stat().st_mtime + 7201) is True, "2시간 넘은 잠금은 무시한다")
    W.release_lock(lock)

    # 배포판 못 읽음
    bad_cfg = dict(cfg, release_path=str(td / "없음.json"))
    ok(raises(lambda: W.load_release(bad_cfg), T.WatchFailure), "배포판 목록을 못 읽으면 확인 실패")
    (td / "옛형식.json").write_text('{"schema": 99, "rules": []}', encoding="utf-8")
    ok(raises(lambda: W.load_release(dict(cfg, release_path=str(td / "옛형식.json"))), T.WatchFailure), "형식이 다른 배포판 목록은 확인 실패")
    (td / "깨짐.json").write_text("{", encoding="utf-8")
    ok(raises(lambda: W.load_release(dict(cfg, release_path=str(td / "깨짐.json"))), T.WatchFailure), "깨진 배포판 목록은 확인 실패")
    rel2, note = W.load_release(dict(cfg, release_url="https://x/release.json"), get_url=lambda u: (_ for _ in ()).throw(OSError("down")))
    ok(rel2["release_no"] == 7 and note == "배포판을 읽지 못해 이 PC의 마지막 빌드와 비교함", "주소를 못 읽으면 이 PC 빌드로 비교하고 알린다")
    rel3, note = W.load_release(dict(cfg, release_url="https://x/release.json"), get_url=lambda u: json.dumps(rel_of(ENTRY)).encode())
    ok(rel3["rules"] and note == "", "주소를 먼저 읽는다")
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`
Expected: `AttributeError: module 'watch_alio' has no attribute 'monday_nine'`

- [ ] **Step 3: `scripts/watch_alio.py` 에 실행 부분을 더한다**

순서는 설계 6.1 그대로다. 잠금 → `is_due`(`force` 면 건너뜀) → `load_release` → `fetch_list` → `check_sanity` → 내규 전체 `fetch_attachments`(하나라도 실패하면 `AlioError` 로 전체 실패) → `judge` → 첨부 대상 `save_bundle` → `update_history` → `days` 채우기 → `render_html` → `write_outputs` → `.last_success`(ISO 시각) → 알림. 알림은 `ATTENTION` 이 있으면 내규 이름을 넣은 문구와 `open_page`, 없으면 `"이번 주 변동 없음"` 만. 실패(`WatchFailure`, `AlioError`, 그 밖의 모든 `Exception`)는 `V_FAIL` 까닭으로 결과 화면을 쓰고 `실행기록.log` 에 traceback을 남기고 `1` 을 돌려준다. 실패 알림은 `.last_fail_notice` 로 하루 한 번만 띄우지만 화면 열기·재시도는 막지 않는다. `.last_success` 는 건드리지 않는다. 경과일은 `elapsed_days`. full 모드의 `local_release` 는 `repo/dist/release.json`(없으면 `None`), `compare` 기본값은 함수 안에서 `sys.path` 에 저장소 `scripts` 를 넣고 import 한 `alio_compare.compare_rule`. `load_release` 는 `release_url` 에 `?t=<시각>` 을 붙여 받고, `schema != 1`·JSON 오류·빈 `rules`(`rules` 가 비었으면 실패)면 다음 곳으로 넘어가며, 모두 안 되면 `WatchFailure`. CLI는 `pythonw` 로 돌 수 있도록 표준 출력에 의존하지 않는다.

- [ ] **Step 4: 시험이 통과하는지 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`
Expected: `✗` 없음, `exit=0`

- [ ] **Step 5: 실제 자료로 한 번 돌린다**

임시 폴더에 full 모드 설정(`repo` 는 이 저장소, `release_path` 는 `dist/release.json`, `docs_dir` 는 스크래치 폴더)을 만들고 `python3 -X utf8 scripts/watch_alio.py --config <설정> --force; echo exit=$?` 를 실행한다.

Expected: `exit=0`, 결과 화면에 `이번 주 변동 없음`, 받은 파일 없음, `git status` 에 실제 자료 변화 없음. 약 1~2분 걸린다. 다르면(새 개정이 실제로 올라온 경우 포함) 결과를 사용자에게 보여 준다.

- [ ] **Step 6: 커밋한다**

```bash
git add scripts/watch_alio.py scripts/test_watch_alio.py
git commit -m "ALIO 확인 한 번 돌리기: 돌 차례, 잠금, 실패 처리"
```

### Task 8: 새 판 만들 때 기록 올리기와 '확인함'

**Files:**
- Create: `scripts/alio_confirm.py`
- Modify: `scripts/update_rules.py`(`finish` 끝), `scripts/test_watch_alio.py`

**Interfaces:**
- Consumes: `confirm`, `build_release`, `load_seen`, `SEEN`, `RELEASE`, `최근 결과.json`
- Produces:
  - `pending_of(result_json: dict) -> list[dict]` (`ATTENTION` 판정 중 `V_PENDING`·`V_FAIL` 을 뺀 것)
  - `apply_confirm(item: dict, reason: str, today: str, seen_path: Path, rebuild) -> None`. 사유가 비면 `ValueError`. `V_GONE` 이면 `gone=True`
  - 명령: `python -X utf8 scripts/alio_confirm.py --config PATH` (번호로 고르고 사유를 입력)
- `finish` 는 마지막에 `alio_release.py refresh` 를 부르고, 실패해도 `finish` 를 멈추지 않는다.

- [ ] **Step 1: 실패하는 시험을 더한다**

```python
if MD_DIR.exists():
    import alio_confirm as CF  # noqa: E402
    items = [{"name": "복무세칙", "idx": "9387", "title": "복무세칙", "verdict": T.V_SUSPECT, "values": {"mod": "2026.11.09", "st_date": "2026.11.02", "file_no": "101"}, "file_date": "2026.11.02"},
             {"name": "a", "idx": "2", "verdict": T.V_PENDING}, {"name": "b", "idx": "3", "verdict": T.V_DONE}, {"name": "c", "idx": "4", "title": "c", "verdict": T.V_GONE, "values": None, "file_date": ""}]
    ok([x["idx"] for x in CF.pending_of({"findings": items})] == ["9387", "4"], "확인함 대상: 해소할 수 있는 알림만")
    with tempfile.TemporaryDirectory() as td:
        sp = Path(td) / "seen.json"
        sp.write_text(json.dumps({"taken": "x", "rules": {"9387": {"name": "복무세칙", "title": "복무세칙", "mod": "old", "st_date": "old", "file_no": "100", "file_date": "old"}, "4": {"name": "c", "title": "c", "mod": "m", "st_date": "s", "file_no": "1", "file_date": "f"}}}), encoding="utf-8")
        rebuilt = []
        ok(raises(lambda: CF.apply_confirm(items[0], "  ", "2026-11-16", sp, lambda: rebuilt.append(1)), ValueError) and not rebuilt, "사유는 꼭 적어야 한다")
        CF.apply_confirm(items[0], "내부 파일로 반영", "2026-11-16", sp, lambda: rebuilt.append(1))
        s = json.loads(sp.read_text(encoding="utf-8"))["rules"]
        ok(s["9387"]["mod"] == "2026.11.09" and s["9387"]["confirmed"]["reason"] == "내부 파일로 반영" and rebuilt == [1], "확인함: 값과 사유를 기록하고 release.json을 다시 만든다")
        CF.apply_confirm(items[3], "유효한 내규", "2026-11-16", sp, lambda: None)
        s = json.loads(sp.read_text(encoding="utf-8"))["rules"]
        ok(s["4"]["confirmed"]["gone"] is True and s["4"]["mod"] == "m", "목록에서 사라짐을 확인함으로 끝내면 값은 그대로 둔다")
        new_item = {"name": "새 지침", "idx": "555", "title": "새 지침", "verdict": T.V_NEW, "values": {"mod": "2026.11.09", "st_date": "2026.11.02", "file_no": "9"}, "file_date": "2026.11.02"}
        CF.apply_confirm(new_item, "챗봇 범위 밖", "2026-11-16", sp, lambda: None)
        s = json.loads(sp.read_text(encoding="utf-8"))["rules"]
        ok(s["555"]["name"] == "새 지침" and s["555"]["file_no"] == "9" and s["555"]["confirmed"]["reason"] == "챗봇 범위 밖", "넣지 않기로 한 새 내규도 확인함으로 끝낸다")
    ok(one([dict(ROW_NEW)], ATT_NEW, rel_of(dict(ENTRY, mod=ROW_NEW["mod"], st_date=ROW_NEW["st_date"], file_no="101", confirmed={"date": "d", "reason": "r"}))).verdict == T.V_NONE, "확인함을 올린 뒤에는 변동 없음")
    row_again = dict(ROW_NEW, mod="2026.12.01")
    ok(one([row_again], {"9387": [{"file_no": "102", "name": "복무세칙(2026년도 11월 2일 개정).hwp"}]}, rel_of(dict(ENTRY, mod=ROW_NEW["mod"], st_date=ROW_NEW["st_date"], file_no="101", confirmed={"date": "d", "reason": "r"})), {"102": NEW}).verdict == T.V_SUSPECT, "확인함 뒤 ALIO 값이 다시 바뀌면 다시 잡는다")
    src = (ROOT / "scripts" / "update_rules.py").read_text(encoding="utf-8")
    ok('"scripts/alio_release.py", "refresh"' in src and src.index("원본 파일 기록 갱신") < src.index('"scripts/alio_release.py", "refresh"'), "finish 끝에서 ALIO 기록을 올리고 release.json을 만든다")
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`
Expected: `ModuleNotFoundError: No module named 'alio_confirm'`

- [ ] **Step 3: `scripts/alio_confirm.py` 를 만들고 `update_rules.py` 를 고친다**

`update_rules.finish` 의 `원본 파일 기록 갱신` 출력 뒤에 `print(run(sys.executable, "scripts/alio_release.py", "refresh", check=False).strip())` 를 더한다. `alio_confirm` 의 `main` 은 `최근 결과.json` 을 읽어 번호와 이름을 보여 주고 `input()` 으로 번호와 사유를 받는다. 끝나면 "확인함을 기록했습니다. 다음 배포 때 함께 올라갑니다."를 출력한다. `rebuild` 기본값은 `alio_release` 의 `write_release()`(판 번호는 그대로, `knowledge/site.json` 의 `release.no`, Task 3에서 이 함수를 CLI와 함께 둔다). 새 내규(`V_NEW`)를 확인함으로 끝내면 `alio_seen.json` 에 새 항목을 만든다.

- [ ] **Step 4: 시험이 통과하는지 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`
Expected: `✗` 없음, `exit=0`

- [ ] **Step 5: refresh를 실제로 돌린다**

Run: `python3 -X utf8 scripts/alio_release.py refresh; echo exit=$?; git status --short knowledge/alio_seen.json; ls -la dist/release.json`
Expected: `exit=0`, 바뀐 내규 0건이면 `alio_seen.json` 변화 없음, `dist/release.json` 생성. `finish` 자체는 판 번호를 올리므로 실제로 돌리지 않는다.

- [ ] **Step 6: 커밋한다**

```bash
git add scripts/alio_confirm.py scripts/update_rules.py scripts/test_watch_alio.py
git commit -m "새 판을 만들 때 ALIO 기록 올리기, 담당자 확인함"
```

### Task 9: 설치 프로그램과 안내 문서

**Files:**
- Create: `scripts/install_watch.py`
- Modify: `scripts/test_watch_alio.py`, `docs/유지보수_안내.md`, `skills/naegyu-update/SKILL.md`, `README.md`

**Interfaces:**
- Produces:
  - `TASK_NAME = "내규챗봇 ALIO 확인"`
  - `task_xml(python_exe: str, script: str, config: str, start: str = "2026-01-05T09:00:00") -> str`
  - `confirm_bat(python_exe: str, script: str, config: str) -> str`
  - `pack(out: Path) -> list[str]` (부 담당용 ZIP. `alio_types, alio_client, alio_pick, alio_release, alio_report, watch_alio, install_watch`)
  - `install(mode, repo, url, path, docs_dir, dry_run=False) -> dict`
  - 명령: `python -X utf8 scripts/install_watch.py --mode full|alert [--repo PATH] [--url URL] [--docs PATH] [--dry-run]`, `--pack out.zip`

- [ ] **Step 1: 실패하는 시험을 더한다**

```python
import subprocess  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402
import install_watch as IW  # noqa: E402

xml = IW.task_xml("C:\\Python\\pythonw.exe", "C:\\내규\\watch_alio.py", "C:\\내규 확인\\config.json")
ns = {"t": "http://schemas.microsoft.com/windows/2004/02/mit/task"}
root = ET.fromstring(xml)
ok(root.find(".//t:CalendarTrigger/t:ScheduleByWeek/t:DaysOfWeek/t:Monday", ns) is not None and "T09:00:00" in root.find(".//t:CalendarTrigger/t:StartBoundary", ns).text, "매주 월요일 9시")
ok(root.find(".//t:LogonTrigger", ns) is not None, "로그인할 때도 돈다")
ok(root.find(".//t:LogonType", ns).text == "InteractiveToken", "로그인해 있을 때만(알림과 화면을 띄우므로)")
ok(root.find(".//t:StartWhenAvailable", ns).text == "true" and root.find(".//t:DisallowStartIfOnBatteries", ns).text == "false" and root.find(".//t:StopIfGoingOnBatteries", ns).text == "false", "놓치면 바로 돌고 배터리여도 돈다")
ok(root.find(".//t:RestartOnFailure/t:Interval", ns).text == "PT1H" and root.find(".//t:RestartOnFailure/t:Count", ns).text == "3", "실패 시 1시간 간격 3번")
ok(root.find(".//t:MultipleInstancesPolicy", ns).text == "IgnoreNew", "겹쳐 돌지 않는다")
args = root.find(".//t:Exec/t:Arguments", ns).text
ok(root.find(".//t:Exec/t:Command", ns).text == "C:\\Python\\pythonw.exe" and "-X utf8" in args and '"C:\\내규\\watch_alio.py"' in args and '"C:\\내규 확인\\config.json"' in args, "utf8로 돌고 경로를 따옴표로 묶는다")
ok("chcp 65001" in IW.confirm_bat("p", "s", "c") and "-X utf8" in IW.confirm_bat("p", "s", "c"), "확인함 실행 파일: 한글 경로와 utf8")
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    names = IW.pack(td / "부담당.zip")
    ok(set(names) == {f"{m}.py" for m in ("alio_types", "alio_client", "alio_pick", "alio_release", "alio_report", "watch_alio", "install_watch")}, "부 담당 묶음에 필요한 파일만 넣는다")
    with zipfile.ZipFile(td / "부담당.zip") as z:
        z.extractall(td / "x")
    r = subprocess.run([sys.executable, "-X", "utf8", str(td / "x" / "watch_alio.py"), "--help"], capture_output=True, text=True, cwd=td / "x")
    ok(r.returncode == 0, f"저장소 없이도 프로그램이 뜬다 {r.stderr[-200:]}")
    r = subprocess.run([sys.executable, "-X", "utf8", str(td / "x" / "install_watch.py"), "--mode", "alert", "--url", "https://x/release.json", "--docs", str(td / "out"), "--dry-run"], capture_output=True, text=True, cwd=td / "x")
    cfg_w = json.loads((td / "out" / "config.json").read_text(encoding="utf-8"))
    ok(r.returncode == 0 and cfg_w["mode"] == "alert" and cfg_w["release_url"] == "https://x/release.json" and (td / "out" / "내규챗봇 ALIO 확인.xml").read_bytes()[:2] in (b"\xff\xfe", b"\xfe\xff"), "미리 보기: 설정과 UTF-16 작업 파일을 쓰고 등록은 하지 않는다")
```

- [ ] **Step 2: 시험이 실패하는지 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`
Expected: `ModuleNotFoundError: No module named 'install_watch'`

- [ ] **Step 3: `scripts/install_watch.py` 를 만든다**

`python_exe` 는 `sys.executable` 옆의 `pythonw.exe` 가 있으면 그것, 없으면 `sys.executable`. 기본 `docs_dir` 은 `Path.home()/"Documents"/"내규챗봇 ALIO 확인"`. 작업 파일은 UTF-16으로 저장하고, 윈도우에서는 `schtasks /create /tn <TASK_NAME> /xml <파일> /f` 로 등록한다(`--dry-run` 또는 윈도우가 아니면 파일만 쓰고 등록하지 않는다). full 모드는 `release_path` 를 `<repo>/dist/release.json` 으로 두고 `확인함.bat` 도 만든다. 파이썬이 3.11 미만이면 설치를 거부한다. XML은 작업 스케줄러 스키마 1.2 형식이고 `Enabled=true`, `RunOnlyIfNetworkAvailable=false`(접속 실패는 프로그램이 `확인 실패`로 처리), `ExecutionTimeLimit=PT1H`.

- [ ] **Step 4: 시험이 통과하는지 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?`
Expected: `✗` 없음, `exit=0`

- [ ] **Step 5: 안내 문서를 고친다**

- `docs/유지보수_안내.md`: '매주 ALIO 확인' 절을 더한다. 결과 보는 곳, 판정별 할 일(설계 6.4·6.4.1 표를 쉬운 말로), 대기 폴더의 파일을 원본 폴더에 넣는 법(화면에 적힌 이름으로), `확인함.bat`, 14일 빨간 표시와 미반영 공지, 설치 방법, "실제 운영은 윈도우 이전 뒤 시작"을 적는다.
- `skills/naegyu-update/SKILL.md`: 1단계에 "ALIO 확인 결과의 대기 폴더 파일을 받는 경로"를, 4단계에 "`finish` 가 ALIO 기록을 올리고 `dist/release.json` 을 만든다. '다음 확인 때 다시 잡힘' 경고가 나오면 사용자에게 알린다"를 더한다. `~/.claude/skills/naegyu-update/SKILL.md` 와 같은 내용인지 `diff` 로 확인하고, 같으면 함께 고친다. 다르면 고치지 말고 알린다.
- `README.md`: 새 스크립트 목록과 `knowledge/alio_seen.json`, `dist/release.json` 설명을 더한다.

- [ ] **Step 6: 전체를 다시 확인한다**

Run: `python3 -X utf8 scripts/test_watch_alio.py; echo exit=$?; python3 scripts/test_forms.py | tail -1; echo forms=$?; python3 scripts/update_rules.py status | tail -1; git status --short`
Expected: `exit=0`, `forms=0`, `바뀐 파일이 없습니다`, 실제 자료 변화 없음(contacts 관련 파일은 원래 있던 것).

- [ ] **Step 7: 커밋한다**

```bash
git add scripts/install_watch.py scripts/test_watch_alio.py docs/유지보수_안내.md skills/naegyu-update/SKILL.md README.md
git commit -m "ALIO 확인 설치 프로그램과 안내 문서"
```

## 이 계획으로 끝나지 않는 것

- **담당자 PC 인수 시험(설계 9장):** 윈도우 예약 실행, 알림, 외부망 환경. 윈도우 이전 과제 뒤에 한다. 이 맥에서는 시험할 수 없다.
- 설계 13장의 나머지 과제.
