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

# 압축 자료가 깨진 ZIP: 목차는 멀쩡하고 안쪽 압축만 망가진 경우도 예외 없이 문제로 넘긴다
bad_name = "규정(2026년도 2월 4일 개정).hwp"
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.writestr(bad_name, bytes(range(256)) * 40)
raw = bytearray(buf.getvalue())
start = 30 + len(bad_name.encode("utf-8"))
for i in range(start, start + 40):
    raw[i] ^= 0xFF
try:
    broken = pick_bundle([("규정(2026년도 2월 4일 개정).zip", bytes(raw))], "2026.02.04")
    ok(bool(broken.problems), "압축 자료가 깨진 ZIP은 예외 없이 문제로 넘긴다")
except Exception as e:  # noqa: BLE001
    ok(False, f"압축 자료가 깨진 ZIP에서 예외가 났다: {type(e).__name__} {e}")

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

def list_with(**kw):
    d = {"result": [ROW], "page": {"totalPage": 1, "totalCount": 1}}
    d.update(kw)
    return lambda p, b: (json.dumps({"data": d}).encode(), "application/json")


ok(raises(lambda: fetch_list(lambda p, b: (json.dumps({"data": {"result": [ROW]}}).encode(), ""))), "data.page 가 없으면 실패")
ok(raises(lambda: fetch_list(list_with(page={"totalPage": 1}))), "totalCount 가 없으면 실패")
ok(raises(lambda: fetch_list(list_with(result=[None]))), "행이 dict 가 아니면 AlioError")
ok(raises(lambda: fetch_list(list_with(result=["x"]))), "행이 문자열이어도 AlioError")
ok(raises(lambda: fetch_list(list_with(result=[{"title": "a"}]))), "idx 없는 행은 실패")

sys.exit(1 if FAIL else 0)
