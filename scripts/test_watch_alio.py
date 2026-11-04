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
res = W.judge([ROW_NEW, dict(ROW_SAME, idx="2", title="다른 세칙")], {"9387": [{"file_no": "101", "name": "복무세칙(2026년도 11월 2일 개정).zip"}], "2": []}, rel_of(ENTRY, dict(ENTRY, idx="2", name="다른 세칙", file_no="")), None, {"101": b"broken"}.__getitem__, lambda *a: None, "full")
ok([x.verdict for x in res] == [T.V_CHECK, T.V_NONE], "손상된 ZIP이 있어도 나머지 내규는 계속 판정한다")
f = one([{"idx": "555", "title": "새 지침", "st_date": "2026.11.02", "mod": "2026.11.09"}], {"555": [{"file_no": "9", "name": "새 지침(2026년도 11월 2일 제정).hwp"}]}, rel_of(), {"9": NEW}, compare=lambda *a: cmp_res(added_units=["제1조", "제2조"]))
ok(f.verdict == T.V_NEW and len(f.compare.added_units) == 2, "배포판에 없으면 새 내규(조문 수)")
res = W.judge([], {}, rel_of(ENTRY), None, {}.__getitem__, lambda *a: None, "full")
ok([x.verdict for x in res] == [T.V_GONE], "배포판에 있는데 목록에 없으면 목록에서 사라짐")
ok(W.judge([], {}, rel_of(dict(ENTRY, confirmed={"date": "d", "reason": "유효", "gone": True})), None, {}.__getitem__, lambda *a: None, "full") == [], "사라짐을 확인함으로 끝냈으면 다시 알리지 않는다")
res = W.judge([dict(ROW_NEW, idx="42")], {"42": ATT_NEW["9387"]}, rel_of(ENTRY), None, {"101": NEW}.__getitem__, lambda *a: cmp_res(changed_units=["제1조"]), "full")
ok([x.verdict for x in res] == [T.V_SUSPECT], "idx가 바뀌어도 이름으로 맞추고 사라짐을 함께 내지 않는다")
ok(raises(lambda: W.check_sanity([], rel_of(ENTRY, ENTRY)), T.WatchFailure) and raises(lambda: W.check_sanity([ROW_SAME], rel_of(ENTRY, ENTRY, ENTRY)), T.WatchFailure), "받은 목록이 배포판의 절반 미만이면 확인 실패")
W.check_sanity([ROW_SAME], rel_of(ENTRY, ENTRY))

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
    new_text = "제1조(목적) 이 지침은 시험이다.\n\n제2조(적용) 전 직원에 적용한다.\n\n부 칙\n\n이 지침은 2026년 11월 2일부터 시행한다.\n"
    r = C.compare_md("Ⅳ-99", "새 시험 지침", {"새 시험 지침(2026년도 11월 2일 제정).hwp": new_text})
    ok("제1조" in r.added_units and "제2조" in r.added_units and not r.error, "새 내규는 새 조문으로 나온다")
    r = C.compare_md("", "새 시험 지침", {"새 시험 지침(2026년도 11월 2일 제정).hwp": new_text})
    ok("제1조" in r.added_units and not r.error, "분류 코드가 없는 새 내규도 임시 코드로 비교한다")
    p2 = next(x for x in MD_DIR.glob("*.md") if "위임전결기준" in unicodedata.normalize("NFC", x.name))
    r = C.compare_md("Ⅲ-7-1", "위임전결세칙", {"(별표)위임전결기준(2026년도 11월 2일 개정).xlsx": p2.read_text(encoding="utf-8") + "\n| 시험 | 칸 |\n"})
    ok(any("별표" in u for u in r.changed_units), "별표 엑셀은 별표 변환본 자리에 들어간다")
    ok(tree_sig() == before, "실제 data·knowledge는 바뀌지 않는다")


sys.exit(1 if FAIL else 0)
