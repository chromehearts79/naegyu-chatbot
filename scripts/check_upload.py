"""GitHub 에 올리기 전 점검.

올라갈 파일(그리고 --history 면 기록 전체)에 개인정보·키 꼴이 있는지,
올리면 안 되는 경로가 있는지 보고, 한글 파일의 작성 정보를 목록으로 보여 준다.
문제가 있으면 exit 1. 작성 정보와 커밋 작성자 목록은 사람이 보고 정하는 자료라 실패시키지 않는다.

  python3 -X utf8 scripts/check_upload.py [--staged] [--history]
  python3 -X utf8 scripts/check_upload.py --paths-only   # 올리면 안 되는 이름의 파일이 있는지만 본다(GitHub 에서 직접 올린 뒤 자동 점검용, 표준 라이브러리만 씀)
"""
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO = Path.cwd()  # main() 이 명령을 실행한 곳의 저장소로 바꾼다
TEXT_EXTS = {".md", ".json", ".py", ".txt", ".yml", ".yaml", ".cjs", ".js", ".html", ".csv"}

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
    """내규 변환본(data/md)을 본다. [ 로 시작하는 변환본은 올리지 않으므로 보지 않는다.
    읽지 못한 변환본은 점검하지 못한 것이므로 문제로 알린다."""
    found = []
    md_dir = Path(md_dir)
    for p in sorted(md_dir.rglob("*.md")):
        if p.name.startswith("["):
            continue
        name = f"{md_dir.name}/{p.relative_to(md_dir).as_posix()}"
        try:
            data = p.read_bytes()
        except OSError as e:
            found.append(f"{name}: 읽지 못해 점검하지 못함 ({e})")
            continue
        if _looks_binary(data):
            found.append(f"{name}: 글 파일인데 UTF-8 글로 읽지 못해 점검하지 못함")
            continue
        found += scan_text(name, data.decode("utf-8"))
    return found


# ---------- git ----------
def git(*args, text=True):
    r = subprocess.run(["git", "-c", "core.quotepath=false", *args], cwd=REPO, capture_output=True)
    if r.returncode != 0:
        raise SystemExit("git 실패: " + r.stderr.decode("utf-8", "replace").strip())
    return r.stdout.decode("utf-8", "replace") if text else r.stdout


def tracked_files(staged):
    """올라갈 파일 목록. 기본은 HEAD(올리면 나가는 것), --staged 면 인덱스."""
    if staged:
        return [p for p in git("ls-files", "-z").split("\0") if p]
    return [p for p in git("ls-tree", "-r", "-z", "--name-only", "HEAD").split("\0") if p]


def read_file(path, staged):
    return git("show", (":" if staged else "HEAD:") + path, text=False)


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
            f = Path(td) / f"{i}{Path(p).suffix}"
            try:
                f.write_bytes(read_file(p, staged))
            except (OSError, SystemExit) as e:
                lines[p] = f"읽지 못함 ({e})"
                continue
            local[p] = f
        hwps = [p for p in local if p.lower().endswith(".hwp")]
        if hwps:
            try:
                r = subprocess.run(["node", str(SCRIPTS / "file_info.cjs"), *[str(local[p]) for p in hwps]],
                                   cwd=SCRIPTS, capture_output=True, timeout=120)
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


def paths_only():
    """HEAD 에 올리면 안 되는 이름의 파일이 있는지만 본다. 글 내용은 읽지 않는다(node 도 필요 없다)."""
    global REPO
    try:
        REPO = Path(git("rev-parse", "--show-toplevel").strip())
        bad = forbidden_paths(tracked_files(False))
    except SystemExit as e:
        print(f"✗ 점검하지 못했습니다: {e}")
        return 1
    if bad:
        print(f"✗ 올리면 안 되는 이름의 파일 {len(bad)}개가 올라갔습니다:")
        for p in bad:
            print("  - " + p)
        return 1
    print("✓ 올리면 안 되는 이름의 파일이 없습니다.")
    return 0


def main(argv):
    global REPO
    if "--paths-only" in argv:
        return paths_only()
    staged = "--staged" in argv
    history = "--history" in argv
    problems = []
    try:
        REPO = Path(git("rev-parse", "--show-toplevel").strip())
        files = tracked_files(staged)
    except SystemExit as e:
        print(f"✗ 점검하지 못했습니다: {e}")
        return 1
    warnings = []
    if not staged:
        dirty = [ln[3:] for ln in git("status", "--porcelain", "--untracked-files=no").splitlines()]
        if dirty:
            warnings.append(f"저장하지 않은(커밋 전) 바뀐 파일 {len(dirty)}개가 있습니다. 이 점검은 HEAD(올라갈 내용)를 봤으므로 이 바뀐 내용은 보지 않았습니다: "
                            + ", ".join(dirty[:5]) + (" …" if len(dirty) > 5 else ""))

    for p in forbidden_paths(files):
        problems.append(f"올리면 안 되는 파일: {p}")
    scanned = 0
    skipped = {}  # 확장자 -> 경로들
    for p in files:
        try:
            data = read_file(p, staged)
        except (OSError, SystemExit) as e:
            problems.append(f"{p}: 읽지 못해 점검하지 못함 ({e})")
            continue
        if _looks_binary(data):
            ext = Path(p).suffix.lower()
            if ext in TEXT_EXTS:
                problems.append(f"{p}: 글 파일인데 UTF-8 글로 읽지 못해 점검하지 못함")
            else:
                skipped.setdefault(ext or "(확장자 없음)", []).append(p)
            continue
        scanned += 1
        problems += scan_text(p, data.decode("utf-8"))
    md_dir = REPO / "data" / "md"
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

    print(f"점검 대상: {'스테이지에 올린 내용' if staged else 'HEAD(올라갈 내용)'}의 글 파일 {scanned}개, 내규 변환본 폴더 data/md"
          + (", 기록 전체(HEAD)" if history else ""))
    for w in warnings:
        print("\n! 주의: " + w)
    nskip = sum(len(v) for v in skipped.values())
    if nskip:
        print(f"\n글 내용을 보지 않은 글 아닌 파일 {nskip}개(확장자별). 한글·엑셀은 아래 작성 정보로만 봅니다:")
        for ext, ps in sorted(skipped.items()):
            shown = ", ".join(ps[:3]) + (f" 외 {len(ps) - 3}개" if len(ps) > 3 else "")
            print(f"  - {ext} {len(ps)}개: {shown}")
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
    notes = []
    for p, line in infos:
        line = line.encode("utf-8", "replace").decode("utf-8")  # 깨진 글자(짝 없는 서로게이트)가 있어도 출력이 멈추지 않게
        print(f"  - {p}: {line}")
        notes += scan_text(p + " 작성 정보", line)
    if notes:
        print("\n! 참고: 작성 정보 안에 개인정보·키 꼴이 있습니다(실패로 치지 않으니 사람이 보고 정하세요):")
        for n in notes:
            print("  - " + n)
    print(f"\n파일 수: 올라갈 파일 {len(files)}개")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
