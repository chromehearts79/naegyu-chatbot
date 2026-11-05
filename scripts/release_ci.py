"""새 판 만들기와 판 번호 검사(GitHub Actions 용).

  python3 -X utf8 scripts/release_ci.py check-number <기준_커밋>   # 문답·원본이 바뀌었는데 판 번호가 그대로면 실패
  python3 -X utf8 scripts/release_ci.py publish <이전_커밋>        # 새 판이면 GitHub Release 를 만든다(이미 있는 판은 절대 덮어쓰지 않는다)

판 번호는 knowledge/site.json 의 release.no, 이미 낸 판은 git 태그 v<번호> 로 안다.
"""
import io
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

NOT_CONTENT = ("knowledge/alio_seen.json", "knowledge/site.json")
ZERO = re.compile(r"^0+$")


def tag_of(no: int) -> str:
    return f"v{no}"


def _numbers(tags) -> list:
    return [int(t[1:]) for t in tags if re.fullmatch(r"v\d+", t.strip())]


def should_release(no: int, tags: list) -> bool:
    """이미 낸 판보다 번호가 커야 새 판이다."""
    nums = _numbers(tags)
    return not nums or no > max(nums)


def _is_content(path: str) -> bool:
    p = path.replace("\\", "/")
    if p.startswith("원본/"):
        return True
    return p.startswith("knowledge/") and p.endswith(".json") and p not in NOT_CONTENT


def number_problem(changed: list, no: int, tags: list):
    nums = _numbers(tags)
    if not nums or not any(_is_content(p) for p in changed):
        return None
    if no > max(nums):
        return None
    return (f"문답이나 내규 원본이 바뀌었는데 판 번호가 제{no}판 그대로입니다(이미 낸 가장 높은 판은 제{max(nums)}판). "
            f"Claude 웹에 \"판 번호를 올려 줘\"라고 말해 knowledge/site.json 의 release.no 를 {max(nums) + 1} 이상으로 올린 뒤 다시 올려 주세요.")


def decide(no: int, tags: list, changed: list) -> str:
    if number_problem(changed, no, tags):
        return "warn"
    return "publish" if should_release(no, tags) else "skip"


def _zip_files(files, out_path: Path) -> None:
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, f.name)


def assets(no: int, dist: Path, reports: Path, out: Path) -> list:
    """새 판에 붙일 파일을 out 에 모은다. 하나라도 없으면 FileNotFoundError."""
    dist, reports, out = Path(dist), Path(reports), Path(out)
    need = [dist / "index.html", dist / "artifact.html", reports / "change_report.md"]
    gpts = sorted(p for p in (dist / "gpts").glob("*") if p.is_file()) if (dist / "gpts").is_dir() else []
    review = sorted((reports / "review").glob("*.xlsx")) if (reports / "review").is_dir() else []
    missing = [str(p) for p in need if not p.is_file()]
    if not gpts:
        missing.append(str(dist / "gpts"))
    if not review:
        missing.append(str(reports / "review" / "*.xlsx"))
    if missing:
        raise FileNotFoundError("새 판에 필요한 파일이 없습니다: " + ", ".join(missing))
    out.mkdir(parents=True, exist_ok=True)
    made = []
    for src, name in ((need[0], f"내규챗봇_제{no}판.html"), (need[1], f"내규챗봇_제{no}판_artifact.html"), (need[2], f"바뀐_내용_제{no}판.md")):
        dst = out / name
        dst.write_bytes(src.read_bytes())
        made.append(dst)
    for files, name in ((gpts, f"GPTs_제{no}판.zip"), (review, f"검수표_제{no}판.zip")):
        dst = out / name
        _zip_files(files, dst)
        made.append(dst)
    return made


def notes(no: int, summary: str) -> str:
    return "\n".join([
        f"# 내규챗봇 제{no}판",
        "",
        "## 이번에 바뀐 것",
        "",
        (summary or "").strip() or "(합치기 설명이 없습니다)",
        "",
        "## 어떤 파일을 받아 가나",
        "",
        f"- 직원에게 보여 줄 챗봇은 `내규챗봇_제{no}판.html` 한 파일입니다. 이 파일을 받아 망연계로 내부망에 옮겨 주세요.",
        f"- `내규챗봇_제{no}판_artifact.html` 은 Claude 화면(artifact)용, `GPTs_제{no}판.zip` 은 GPTs에 올리는 지식 묶음입니다.",
        f"- `검수표_제{no}판.zip` 은 내규 검수표(엑셀)입니다. 규정 검토 담당자가 바뀐 답을 확인하는 데 씁니다.",
        f"- `바뀐_내용_제{no}판.md` 은 이번에 바뀐 조문을 정리한 글입니다.",
        "",
        "받는 방법: 아래 Assets 에서 파일 이름을 누르면 내려받아집니다.",
    ]) + "\n"


# ---------- 명령 ----------

def _git(*args) -> str:
    r = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:2])} 실패: {r.stderr.strip()[:300]}")
    return r.stdout


def _no() -> int:
    return int(json.loads((ROOT / "knowledge" / "site.json").read_text(encoding="utf-8"))["release"]["no"])


def _tags() -> list:
    return [t for t in _git("tag", "--list", "v*").split() if t]


def _changed(before: str) -> list:
    """before 이후 바뀐 파일. before 가 없거나 모르는 커밋이면 추적하는 모든 파일을 바뀐 것으로 본다."""
    def all_files():
        return [p for p in _git("-c", "core.quotepath=false", "ls-files").splitlines() if p]
    if not before or ZERO.match(before):
        return all_files()
    try:
        return [p for p in _git("-c", "core.quotepath=false", "diff", "--name-only", before, "HEAD").splitlines() if p]
    except RuntimeError:
        return all_files()


def check_number(base: str) -> int:
    msg = number_problem(_changed(base), _no(), _tags())
    if msg:
        print(msg)
        return 1
    print("판 번호 검사 통과")
    return 0


def _gh(args, stdin=None) -> str:
    import watch_ci
    return watch_ci.gh_default(args, stdin)


def _report(reason: str) -> None:
    import watch_ci
    try:
        today = watch_ci.datetime.datetime.now(watch_ci.KST).strftime("%Y-%m-%d")
        import os
        assignees = [x.strip() for x in os.environ.get("NAEGYU_ASSIGNEES", "").split(",") if x.strip()]
        watch_ci.apply_actions(watch_ci.failure_actions(reason, watch_ci._list_open(_gh), today, assignees, "release"), _gh)
    except Exception as e:  # noqa: BLE001 - 알리지 못해도 작업은 실패로 끝난다
        print(f"실패 이슈를 쓰지 못했습니다: {e}", file=sys.stderr)


def _close_release_issues() -> None:
    import watch_ci
    mark = watch_ci._fail_marker("release")
    try:
        for iss in watch_ci._list_open(_gh):
            if mark in (iss.get("body") or ""):
                _gh(["issue", "comment", str(iss["number"]), "--body-file", "-"], "새 판이 만들어져 이 이슈를 닫습니다.")
                _gh(["issue", "close", str(iss["number"])], None)
    except Exception as e:  # noqa: BLE001 - 닫지 못해도 판은 이미 나갔다
        print(f"새 판 실패 이슈를 닫지 못했습니다: {e}", file=sys.stderr)


def publish(before: str) -> int:
    no, tags = _no(), _tags()
    action = decide(no, tags, _changed(before))
    if action == "skip":
        print(f"새 판을 만들지 않습니다(제{no}판은 이미 있거나 판에 들어갈 변경이 없습니다).")
        return 0
    if action == "warn":
        reason = (f"같은 판 번호(제{no}판)로 문답이나 내규 원본이 또 합쳐져 새 판을 만들지 않았습니다. 이미 나간 판은 건드리지 않았습니다. "
                  f"Claude 웹에 \"판 번호를 올려 줘\"라고 말해 판 번호를 올린 뒤 다시 합쳐 주세요.")
        print(reason)
        _report(reason)
        return 1
    head = _git("rev-parse", "HEAD").strip()
    summary = _git("log", "-1", "--format=%B", "HEAD").replace("[skip ci]", "").strip()
    out = ROOT / "dist" / "release_assets"
    files = assets(no, ROOT / "dist", ROOT / "reports", out)
    _gh(["release", "create", tag_of(no), *map(str, files), "--title", f"내규챗봇 제{no}판", "--notes-file", "-", "--target", head], notes(no, summary))
    print(f"제{no}판을 만들었습니다.")
    _close_release_issues()
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) == 2 and argv[0] == "check-number":
        return check_number(argv[1])
    if len(argv) == 2 and argv[0] == "publish":
        return publish(argv[1])
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main())
