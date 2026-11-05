"""GitHub 에 올리기 전 점검.

올라갈 파일(그리고 --history 면 기록 전체)에 개인정보·키 꼴이 있는지,
올리면 안 되는 경로가 있는지 보고, 한글 파일의 작성 정보를 목록으로 보여 준다.
문제가 있으면 exit 1. 작성 정보와 커밋 작성자 목록은 사람이 보고 정하는 자료라 실패시키지 않는다.

  python3 -X utf8 scripts/check_upload.py [--staged] [--history]
"""
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ALLOWED_PHONES = {"02-123-4567", "044-200-7752"}
ALLOWED_EMAILS = {"noreply@anthropic.com"}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<![\d\-])0\d{1,2}-\d{3,4}-\d{4}(?!\d)")
RRN_RE = re.compile(r"(?<!\d)\d{6}-[1-4]\d{6}(?!\d)")
KEY_RES = [
    ("API 키 꼴(sk-)", re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_\-]{20,}")),
    ("GitHub 토큰 꼴", re.compile(r"(?<![A-Za-z0-9])(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}")),
    ("GitHub 토큰 꼴", re.compile(r"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{20,}")),
    ("AWS 키 꼴", re.compile(r"(?<![A-Za-z0-9])AKIA[0-9A-Z]{16}")),
    ("Google 키 꼴", re.compile(r"(?<![A-Za-z0-9])AIza[0-9A-Za-z_\-]{35}")),
    ("Slack 토큰 꼴", re.compile(r"(?<![A-Za-z0-9])xox[abprs]-[A-Za-z0-9\-]{10,}")),
]
MASK_ONLY = re.compile(r"^[x*X○●•]+$")

FORBIDDEN_RES = [
    re.compile(r"(^|/)\["),                      # [ 로 시작하는 파일·폴더
    re.compile(r"(^|/)contacts\.json$"),
    re.compile(r"(^|/)reports/contacts/"),
    re.compile(r"(^|/)contacts_report\.py$"),
]


def _shown(kind, value):
    """키는 앞 4자만 보여 준다(점검 결과가 기록에 남아도 키가 새지 않게)."""
    return f"{value[:4]}…" if "키" in kind or "토큰" in kind else value


def scan_text(name, text):
    """글 한 덩어리에서 문제 꼴을 찾아 사람이 읽을 줄 목록으로 돌려준다."""
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        def add(kind, value):
            found.append(f"{name} {n}번째 줄: {kind} {_shown(kind, value)}")
        for m in EMAIL_RE.finditer(line):
            addr = m.group(0)
            if addr.lower() in ALLOWED_EMAILS or MASK_ONLY.match(addr.split("@")[0]):
                continue
            add("메일 주소 꼴", addr)
        for m in PHONE_RE.finditer(line):
            if m.group(0) not in ALLOWED_PHONES:
                add("전화번호 꼴", m.group(0))
        for m in RRN_RE.finditer(line):
            add("주민등록번호 꼴", m.group(0))
        for kind, rx in KEY_RES:
            for m in rx.finditer(line):
                add(kind, m.group(0))
    return found


def forbidden_paths(paths):
    return [p for p in paths if any(rx.search(p) for rx in FORBIDDEN_RES)]


def _looks_binary(data):
    if b"\x00" in data[:8192]:
        return True
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def scan_md_dir(md_dir):
    """내규 변환본(data/md)을 본다. [ 로 시작하는 변환본은 올리지 않으므로 보지 않는다."""
    found = []
    md_dir = Path(md_dir)
    for p in sorted(md_dir.rglob("*.md")):
        if p.name.startswith("["):
            continue
        data = p.read_bytes()
        if _looks_binary(data):
            continue
        found += scan_text(f"{md_dir.name}/{p.relative_to(md_dir).as_posix()}", data.decode("utf-8"))
    return found


# ---------- git ----------
def git(*args, text=True):
    r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=ROOT, capture_output=True)
    if r.returncode != 0:
        raise SystemExit("git 실패: " + r.stderr.decode("utf-8", "replace").strip())
    return r.stdout.decode("utf-8", "replace") if text else r.stdout


def tracked_files():
    return [p for p in git("ls-files", "-z").split("\0") if p]


def read_file(path, staged):
    if staged:
        return git("show", ":" + path, text=False)
    return (ROOT / path).read_bytes()


# ---------- 파일 정보 ----------
def _tag(xml, tag):
    m = re.search(rf"<{tag}[^>]*>([^<]*)</{tag}>", xml)
    return m.group(1).strip() if m else ""


def _hwpx_info(data_path):
    with zipfile.ZipFile(data_path) as z:
        xml = z.read("Contents/content.hpf").decode("utf-8", "replace")
    parts = [("제목", _tag(xml, "opf:title"))]
    for key, label in (("creator", "만든 사람"), ("lastsaveby", "마지막 저장"), ("ModifiedDate", "수정일")):
        m = re.search(rf'<opf:meta name="{key}"[^>]*>([^<]+)</opf:meta>', xml)
        parts.append((label, m.group(1).strip() if m else ""))
    return parts


def _xlsx_info(data_path):
    with zipfile.ZipFile(data_path) as z:
        xml = z.read("docProps/core.xml").decode("utf-8", "replace")
    return [("만든 사람", _tag(xml, "dc:creator")), ("마지막 저장", _tag(xml, "cp:lastModifiedBy")),
            ("수정일", _tag(xml, "dcterms:modified"))]


def _fmt(parts):
    got = [f"{k} {v}" for k, v in parts if v]
    return " · ".join(got) if got else "작성 정보 없음"


def file_infos(paths, staged):
    """한글·엑셀 파일의 작성 정보. 읽지 못하면 그 줄에 그렇게 적고 계속한다. 값은 보여 주기만 한다."""
    kinds = [p for p in paths if p.lower().endswith((".hwp", ".hwpx", ".xlsx"))]
    lines = {}
    with tempfile.TemporaryDirectory() as td:
        local = {}
        for i, p in enumerate(kinds):
            if staged:
                f = Path(td) / f"{i}{Path(p).suffix}"
                try:
                    f.write_bytes(read_file(p, True))
                except SystemExit as e:
                    lines[p] = f"읽지 못함 ({e})"
                    continue
                local[p] = f
            else:
                local[p] = ROOT / p
        hwps = [p for p in local if p.lower().endswith(".hwp")]
        if hwps:
            try:
                r = subprocess.run(["node", str(ROOT / "scripts" / "file_info.cjs"), *[str(local[p]) for p in hwps]],
                                   cwd=ROOT, capture_output=True, timeout=120)
                by_local = {str(local[p]): p for p in hwps}
                if r.returncode != 0:
                    raise RuntimeError(r.stderr.decode("utf-8", "replace").strip() or "node 실행 실패")
                for item in json.loads(r.stdout.decode("utf-8")):
                    p = by_local.get(item["path"])
                    if p is None:
                        continue
                    if "error" in item:
                        lines[p] = "읽지 못함 (" + item["error"] + ")"
                    else:
                        lines[p] = " / ".join(item["strings"]) or item.get("note", "작성 정보 없음")
            except Exception as e:  # node 가 없거나 깨져도 점검은 계속한다
                for p in hwps:
                    lines.setdefault(p, f"읽지 못함 ({e})")
        for p, f in local.items():
            if p in lines or p in hwps:
                continue
            try:
                lines[p] = _fmt(_hwpx_info(f) if p.lower().endswith(".hwpx") else _xlsx_info(f))
            except Exception as e:
                lines[p] = f"읽지 못함 ({e})"
    return [(p, lines.get(p, "읽지 못함")) for p in kinds]


def main(argv):
    staged = "--staged" in argv
    history = "--history" in argv
    problems = []

    files = tracked_files()
    for p in forbidden_paths(files):
        problems.append(f"올리면 안 되는 파일: {p}")
    scanned = skipped = 0
    for p in files:
        try:
            data = read_file(p, staged)
        except (OSError, SystemExit):
            skipped += 1
            continue
        if _looks_binary(data):
            skipped += 1
            continue
        scanned += 1
        problems += scan_text(p, data.decode("utf-8"))
    md_dir = ROOT / "data" / "md"
    if md_dir.is_dir():
        problems += scan_md_dir(md_dir)

    authors = {}
    if history:
        old = sorted({p for p in git("log", "--name-only", "--format=", "HEAD").splitlines() if p.strip()})
        for p in forbidden_paths(old):
            problems.append(f"기록에 남은 올리면 안 되는 파일: {p}")
        problems += scan_text("기록(커밋 글·바뀐 글자)", git("log", "-p", "HEAD", "--format=%B"))
        for line in git("log", "--format=%an <%ae>|%cn <%ce>", "HEAD").splitlines():
            for a in {x.strip() for x in line.split("|") if x.strip()}:
                authors[a] = authors.get(a, 0) + 1

    print(f"점검 대상: {'스테이지에 올린 내용' if staged else '작업 폴더'}의 글 파일 {scanned}개"
          f"(글이 아닌 파일 {skipped}개는 건너뜀), 내규 변환본 폴더 data/md" + (", 기록 전체(HEAD)" if history else ""))
    if problems:
        print(f"\n✗ 걸린 것 {len(problems)}건 — 올리기 전에 사람이 보고 정해야 합니다.")
        for line in problems:
            print("  - " + line)
    else:
        print("\n✓ 걸린 것이 없습니다.")

    if history:
        print("\n커밋 작성자 메일(기록에 남아 공개됩니다. 사람이 보고 정합니다. 이것만으로는 실패시키지 않습니다):")
        for a, n in sorted(authors.items(), key=lambda kv: -kv[1]):
            print(f"  - {a}  (커밋 {n}건)")

    infos = file_infos(files, staged)
    print(f"\n한글·엑셀 파일 작성 정보 {len(infos)}개(보여 주기만 하며 막지 않습니다):")
    for p, line in infos:
        print(f"  - {p}: {line}")
    print(f"\n파일 수: 올라갈 파일 {len(files)}개")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
