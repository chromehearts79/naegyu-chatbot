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

sys.exit(1 if FAIL else 0)
