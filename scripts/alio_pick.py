"""ALIO 첨부에서 가장 최근 일자의 현행 묶음을 고른다. 파일 이름의 날짜만 읽고 내용은 열지 않는다.

예외를 내지 않는다. 고르지 못한 사정은 Bundle.problems 에 담아 사람 확인으로 넘긴다.
"""
import io
import lzma
import re
import zipfile
import zlib
from dataclasses import dataclass, field

MAX_ZIP_MEMBERS = 2000
MAX_TOTAL_BYTES = 300_000_000
MAX_ZIP_DEPTH = 2

READABLE = (".hwp", ".hwpx", ".xlsx")
HANGUL = (".hwp", ".hwpx")
DATE_RE = re.compile(r"((?:19|20)?\d{2})\s*년도?\s*(\d{1,2})\s*월(?:\s*(\d{1,2})\s*일)?")


@dataclass
class Bundle:
    date: tuple | None
    files: list = field(default_factory=list)
    problems: list = field(default_factory=list)


def base_name(name):
    return re.split(r"[/\\]", name)[-1]


def read_date(name):
    """파일 이름 끝쪽의 날짜를 (년, 월, 일) 로 읽는다. 일이 없으면 0, 날짜가 없으면 None."""
    found = DATE_RE.findall(base_name(name))
    if not found:
        return None
    y, m, d = found[-1]
    y = int(y)
    return (y + 2000 if y < 100 else y, int(m), int(d or 0))


def format_date(d):
    y, m, day = d
    return f"{y}.{m:02d}.{day:02d}" if day else f"{y}.{m:02d}"


def date_matches(d, st_date):
    """목록 날짜(2026.08.12 꼴)와 맞는지. 파일 이름에 일이 없으면 월까지만 본다."""
    return st_date.replace("-", ".")[: len(format_date(d))] == format_date(d)


class _Collector:
    def __init__(self):
        self.cands = {}  # (이름, 내용) -> 몇 번째 첨부에서 왔는지. 같은 것은 하나로
        self.problems = []
        self.total = 0
        self.order = 0

    def add(self, name, data):
        self.total += len(data)
        if self.total > MAX_TOTAL_BYTES:
            raise ValueError("크기 상한을 넘었습니다")
        self.cands[(name, data)] = self.order

    def feed(self, name, data, depth):
        ext = "." + base_name(name).lower().rsplit(".", 1)[-1]
        if ext == ".zip":
            self.read_zip(name, data, depth)
        elif ext in READABLE:
            self.add(base_name(name), data)

    def read_zip(self, name, data, depth):
        if depth > MAX_ZIP_DEPTH:
            self.problems.append(f"ZIP 안에 ZIP이 너무 깊습니다: {base_name(name)}")
            return
        try:
            with zipfile.ZipFile(io.BytesIO(data), metadata_encoding="cp949") as z:
                infos = [i for i in z.infolist() if not i.is_dir()]
                if len(infos) > MAX_ZIP_MEMBERS:
                    raise ValueError("ZIP 안 파일이 너무 많습니다")
                for info in infos:
                    if self.total + info.file_size > MAX_TOTAL_BYTES:
                        raise ValueError("크기 상한을 넘었습니다")
                    with z.open(info) as f:
                        body = f.read(MAX_TOTAL_BYTES - self.total + 1)
                    self.feed(info.filename, body, depth + 1)
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError, ValueError, EOFError, OSError,
                zlib.error, lzma.LZMAError) as e:
            self.problems.append(f"ZIP을 읽지 못했습니다({base_name(name)}): {type(e).__name__} {e}")


def _from_last_attachment(cands):
    """같은 일자 파일이 여러 첨부에 있으면 가장 나중에 올린 첨부의 것만 남긴다."""
    if not cands:
        return []
    last = max(order for _, _, order in cands)
    return [c for c in cands if c[2] == last]


def pick_bundle(attachments, st_date):
    """attachments 는 올린 순서(첨부 번호 오름차순)로 받는다."""
    c = _Collector()
    try:
        for order, (name, data) in enumerate(attachments):
            c.order = order
            c.feed(name, data, 1)
    except ValueError as e:
        c.problems.append(str(e))
    problems = list(c.problems)
    cands = list(c.cands)
    if not cands:
        problems.append("읽을 수 있는 한글·엑셀 파일이 없습니다")
        return Bundle(None, [], problems)
    undated = [n for n, _ in cands if read_date(n) is None]
    if undated:
        problems.append("이름에 날짜가 없는 파일이 있습니다: " + ", ".join(sorted({n for n in undated})))
    dated = [(read_date(n), n, d) for n, d in cands if read_date(n)]
    if not dated:
        return Bundle(None, [], problems)
    newest = max(t[0] for t in dated)
    latest = [(n, d, c.cands[(n, d)]) for t, n, d in dated if t == newest]
    # 파일 이름이 월까지만 있으면 한 달에 두 번 개정한 판이 같은 일자로 보인다. 첨부 번호가 큰 쪽이 나중 판이다.
    chosen = (_from_last_attachment([x for x in latest if x[0].lower().endswith(HANGUL)])
              + _from_last_attachment([x for x in latest if not x[0].lower().endswith(HANGUL)]))
    files = sorted(((n, d) for n, d, _ in chosen), key=lambda x: x[0])
    if sum(n.lower().endswith(HANGUL) for n, _ in files) > 1:  # 한 ZIP 안에서 겹치면 올린 순서를 알 수 없다
        problems.append(f"{format_date(newest)} 일자 한글 문서가 둘 이상입니다")
    if not date_matches(newest, st_date):
        problems.append(f"목록 날짜({st_date})와 파일 이름 날짜({format_date(newest)})가 다릅니다")
    return Bundle(newest, files, problems)
