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
    r = C.compare_md("Ⅲ-3-1", "복무세칙", {fname: md, "복무세칙(2026년도 11월 2일 개정)_1.hwpx": md})
    ok(r.error and "둘 이상" in r.error and not r.changed_units, "한글 파일이 둘이면 비교하지 않고 error")
    real_which = C.shutil.which
    C.shutil.which = lambda *a, **k: None
    try:
        r = C.compare_rule("복무세칙", "Ⅲ-3-1", [(fname, b"x")])
    finally:
        C.shutil.which = real_which
    ok(isinstance(r, C.CompareResult) and r.error and "npx" in r.error, "npx 가 없으면 예외 없이 error")
    ok(tree_sig() == before, "실제 data·knowledge는 바뀌지 않는다")

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
    NEWF = T.Finding(name="새 지침", code="", idx="5", verdict=T.V_NEW, compare=cmp_res(added_units=["제1조", "제2조", "부칙"], error="kordoc 실패"))
    page = RP.render_html([NEWF], meta)
    ok("조문 2개" in page and "kordoc 실패" in page and "0개" not in page, "새 내규는 조문 수를 보이고 비교 실패는 메모로 남긴다")

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

with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    F3 = T.Finding(name="겹침", code="", idx="3", verdict=T.V_SUSPECT, file_date="2026.11.02",
                   files=[("가" * 70 + "A.hwp", b"first"), ("sub/" + "가" * 70 + "B.hwp", b"second"), ("dir/", b"zzz"), ("x\\", b"zzz"), ("ok.hwp", b"third")])
    got = sorted(p.read_bytes() for p in Path(RP.save_bundle(td / "대기", F3)).iterdir())
    ok(got == [b"first", b"second", b"third"], "앞 60자가 같은 긴 이름도 둘 다 남기고, 빈 이름은 건너뛴다")
    page = RP.render_html([T.Finding(name="대기건", code="", idx="4", verdict=T.V_PENDING, notes=["새 판을 올리면 끝남"])], {"today": "2026-11-09", "last_success": None, "mode": "full"})
    ok("새 판을 올리면 끝남" in page, "비교 결과가 없는 배포 대기도 안내 메모를 보인다")


import csv  # noqa: E402
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
    with open(td / "out" / "기록.csv", encoding="utf-8-sig", newline="") as fh:
        hist = list(csv.DictReader(fh))
    ok(hist and all(not r["해소된 날"] for r in hist), "실패한 실행은 열린 항목을 해소로 바꾸지 않는다")
    notes.clear()
    ok(go(net, D(2026, 11, 23, 10, 5)) == 1 and not notes, "같은 날 다시 실패하면 알림을 또 띄우지 않는다")
    net.fail_idx = None
    net.rows, net.atts = [ROW_SAME], ATT_SAME
    ok(go(net, D(2026, 11, 25, 9, 0)) == 0, "다음에 접속되면 밀린 확인을 한다")
    with open(td / "out" / "기록.csv", encoding="utf-8-sig", newline="") as fh:
        ok(all(r["해소된 날"] for r in csv.DictReader(fh)), "변동이 사라지면 해소된 날이 적힌다")

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

# 대기 폴더를 못 만들어도(파일이 막고 있음) 그 건에 메모만 달고 계속한다
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    rel_path = td / "release.json"
    rel_path.write_text(json.dumps(rel_of(ENTRY)), encoding="utf-8")
    cfg2 = {"mode": "alert", "repo": "", "release_url": "", "release_path": str(rel_path), "docs_dir": str(td / "out")}
    (td / "out").mkdir()
    (td / "out" / "대기").write_text("파일", encoding="utf-8")
    notes, opened = [], []
    code2 = W.run_watch(cfg2, D(2026, 11, 16, 9, 5), http=Net([ROW_NEW], ATT_NEW, {"101": NEW}), notify=lambda t, b: notes.append(b) or True, open_page=opened.append)
    page = (td / "out" / "이번 주 결과.html").read_text(encoding="utf-8")
    ok(code2 == 0 and "파일을 저장하지 못함" in page and "개정 의심" in page, "파일을 저장하지 못해도 판정은 그대로 두고 메모를 단다")
    ok(notes and "복무세칙" in notes[-1] and opened, "저장에 실패해도 알림과 화면 열기는 한다")

# 알릴 판정이 먼저, 같은 판정은 붙어서 나온다
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    e2 = dict(ENTRY, name="다른 세칙", idx="2", code="Ⅲ-3-2", mod="2026.08.19", st_date="2026.08.12", file_no="200")
    rel_path = td / "release.json"
    rel_path.write_text(json.dumps(rel_of(ENTRY, e2)), encoding="utf-8")
    cfg3 = {"mode": "alert", "repo": "", "release_url": "", "release_path": str(rel_path), "docs_dir": str(td / "out")}
    row2 = {"idx": "2", "title": "다른 세칙", "st_date": "2026.08.12", "mod": "2026.08.19"}
    net = Net([row2, ROW_NEW], dict(ATT_NEW, **{"2": [{"file_no": "200", "name": "다른 세칙(2026년도 8월 12일 개정).hwp"}]}), {"101": NEW})
    W.run_watch(cfg3, D(2026, 11, 16, 9, 5), http=net, notify=lambda t, b: True, open_page=lambda p: None)
    got = [x["verdict"] for x in json.loads((td / "out" / "최근 결과.json").read_text(encoding="utf-8"))["findings"]]
    ok(got == [T.V_SUSPECT, T.V_NONE], "알릴 판정이 먼저 나온다")


# 결과 화면을 쓰지 못하면(지난주 화면이 남음) 실패로 끝낸다. 실패 알림·화면 열기는 하루 한 번
with tempfile.TemporaryDirectory() as td:
    td = Path(td)
    rel_path = td / "release.json"
    rel_path.write_text(json.dumps(rel_of(ENTRY)), encoding="utf-8")
    cfg4 = {"mode": "alert", "repo": "", "release_url": "", "release_path": str(rel_path), "docs_dir": str(td / "out")}
    notes, opened = [], []
    go4 = lambda now: W.run_watch(cfg4, now, http=Net([ROW_SAME], ATT_SAME, {}), notify=lambda t, b: notes.append(b) or True, open_page=opened.append)  # noqa: E731
    real_write = RP.write_outputs
    calls = []

    def bad_write(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise OSError("쓰기 실패")
        return real_write(*a, **k)

    RP.write_outputs = bad_write
    try:
        ok(go4(D(2026, 11, 9, 9, 5)) == 1 and not (td / "out" / ".last_success").exists(), "결과 화면을 쓰지 못하면 실패로 끝나고 성공 기록을 남기지 않는다")
    finally:
        RP.write_outputs = real_write
    ok(notes and notes[-1].startswith("확인 실패") and len(opened) == 1, "결과 화면을 쓰지 못했다는 실패 알림을 띄운다")
    ok("OSError" in (td / "out" / "실행기록.log").read_text(encoding="utf-8"), "쓰지 못한 까닭을 실행기록에 남긴다")
    # 같은 날 또 실패: 알림도 화면 열기도 없음 / 다음 날: 둘 다 함
    net_down = Net([], {}, {})
    net_down.down = True
    n0, o0 = len(notes), len(opened)
    W.run_watch(cfg4, D(2026, 11, 9, 10, 5), http=net_down, notify=lambda t, b: notes.append(b) or True, open_page=opened.append)
    ok(len(notes) == n0 and len(opened) == o0, "같은 날 다시 실패하면 알림도 화면 열기도 하지 않는다")
    code4 = W.run_watch(cfg4, D(2026, 11, 10, 9, 5), http=net_down, notify=lambda t, b: notes.append(b) or True, open_page=opened.append)
    ok(code4 == 1 and len(notes) == n0 + 1 and len(opened) == o0 + 1, "다음 날 실패하면 알림과 화면 열기를 다시 한다")


sys.exit(1 if FAIL else 0)
