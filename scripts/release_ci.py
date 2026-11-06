"""새 판 만들기와 판 번호 검사(GitHub Actions 용).

  python3 -X utf8 scripts/release_ci.py check-number <기준_커밋>   # 문답·원본이 바뀌었는데 판 번호가 그대로면 실패
  python3 -X utf8 scripts/release_ci.py publish                   # 새 판이면 GitHub Release 를 만든다(GITHUB_SHA 기준, 이미 있는 판은 절대 덮어쓰지 않는다)
  python3 -X utf8 scripts/release_ci.py check-pending             # 지금 판 번호의 새 판이 아직 없으면 알린다

판 번호는 knowledge/site.json 의 release.no, 이미 낸 판은 git 태그 v<번호> 로 안다.
"""
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


def asset_names(no: int) -> dict:
    """올리는 파일 이름(영문)과 화면에 보일 한글 이름표. GitHub이 한글 파일 이름을 깨뜨리기 때문에 이름은 영문으로 한다."""
    return {
        f"naegyu-chatbot-v{no}.html": f"내규챗봇_제{no}판.html",
        f"naegyu-chatbot-v{no}-artifact.html": f"내규챗봇_제{no}판_artifact.html",
        f"gpts-v{no}.zip": f"GPTs_제{no}판.zip",
        f"review-workbooks-v{no}.zip": f"검수표_제{no}판.zip",
        f"changes-v{no}.md": f"바뀐_내용_제{no}판.md",
    }


def asset_args(no: int, files) -> list:
    """gh release create 에 넘길 `경로#이름표` 목록."""
    labels = asset_names(no)
    return [f"{f}#{labels[Path(f).name]}" for f in files]


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
    n = list(asset_names(no))
    made = []
    for src, name in ((need[0], n[0]), (need[1], n[1]), (need[2], n[4])):
        dst = out / name
        dst.write_bytes(src.read_bytes())
        made.append(dst)
    for files, name in ((gpts, n[2]), (review, n[3])):
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
        f"- 직원에게 보여 줄 챗봇은 `내규챗봇_제{no}판.html` 한 파일입니다. 내려받은 파일의 실제 이름은 `naegyu-chatbot-v{no}.html` 입니다(GitHub이 한글 파일 이름을 깨뜨려서 영문 이름으로 올립니다). 이 파일을 망연계로 내부망에 옮겨 주세요.",
        f"- `내규챗봇_제{no}판_artifact.html` 은 Claude 화면(artifact)용, `GPTs_제{no}판.zip` 은 GPTs에 올리는 지식 묶음입니다.",
        f"- `검수표_제{no}판.zip` 은 규정 검수표(엑셀)입니다. 규정 검토 담당자가 바뀐 답을 확인하는 데 씁니다.",
        f"- `바뀐_내용_제{no}판.md` 은 이번에 바뀐 조문을 정리한 글입니다.",
        "",
        "받는 방법: 아래 Assets 에서 파일 이름을 누르면 내려받아집니다.",
    ]) + "\n"


def pending_edition(no: int, tags: list) -> bool:
    """판 번호 이상인 태그가 하나도 없으면 아직 이 판을 만들지 못한 것이다."""
    return not any(n >= no for n in _numbers(tags))


# ---------- 명령 ----------

def _git(*args) -> str:
    r = subprocess.run(["git", "-c", "core.quotepath=false", *args], capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:2])} 실패: {r.stderr.strip()[:300]}")
    return r.stdout


def _no(git=_git, rev: str = "HEAD") -> int:
    """그 커밋(기본 HEAD)의 knowledge/site.json 에서 판 번호를 읽는다."""
    return int(json.loads(git("show", f"{rev}:knowledge/site.json"))["release"]["no"])


def _tags(git=_git) -> list:
    return [t for t in git("tag", "--list", "v*").split() if t]


def _all_files(git) -> list:
    return [p for p in git("ls-files").splitlines() if p]


def _changed(before: str, git=_git, head: str = "HEAD") -> list:
    """before 이후 바뀐 파일. before 가 없거나 모르는 커밋이면 추적하는 모든 파일을 바뀐 것으로 본다."""
    if not before or ZERO.match(before):
        return _all_files(git)
    try:
        return [p for p in git("diff", "--name-only", before, head).splitlines() if p]
    except RuntimeError:
        return _all_files(git)


def _changed_since_last_edition(tags: list, git, head: str) -> list:
    nums = _numbers(tags)
    return _changed(tag_of(max(nums)), git, head) if nums else _all_files(git)


def check_number(base: str, git=_git) -> int:
    msg = number_problem(_changed(base, git), _no(git), _tags(git))
    if msg:
        print(msg)
        return 1
    print("판 번호 검사 통과")
    return 0


def _gh(args, stdin=None) -> str:
    import watch_ci
    return watch_ci.gh_default(args, stdin)


def _report(reason: str, gh=_gh, env=None) -> None:
    import datetime
    import os
    import watch_ci
    env = os.environ if env is None else env
    try:
        today = datetime.datetime.now(watch_ci.KST).strftime("%Y-%m-%d")
        assignees = [x.strip() for x in env.get("NAEGYU_ASSIGNEES", "").split(",") if x.strip()]
        watch_ci.apply_actions(watch_ci.failure_actions(reason, watch_ci._list_open(gh), today, assignees, "release"), gh)
    except Exception as e:  # noqa: BLE001 - 알리지 못해도 작업은 실패로 끝난다
        print(f"실패 이슈를 쓰지 못했습니다: {e}", file=sys.stderr)


def _close_release_issues(gh=_gh) -> None:
    import watch_ci
    mark = watch_ci._fail_marker("release")
    try:
        for iss in watch_ci._list_open(gh):
            if mark in (iss.get("body") or ""):
                gh(["issue", "comment", str(iss["number"]), "--body-file", "-"], "새 판이 만들어져 이 이슈를 닫습니다.")
                gh(["issue", "close", str(iss["number"])], None)
    except Exception as e:  # noqa: BLE001 - 닫지 못해도 판은 이미 나갔다
        print(f"새 판 실패 이슈를 닫지 못했습니다: {e}", file=sys.stderr)


def publish(env=None, git=_git, gh=_gh, report=None, make_assets=None) -> int:
    """GITHUB_SHA(시험을 통과한 커밋)로 새 판을 만든다. 번호·설명·대상 커밋이 모두 그 커밋에서 나온다."""
    import os
    env = os.environ if env is None else env
    make_assets = make_assets or (lambda no, out: assets(no, ROOT / "dist", ROOT / "reports", out))
    report = report or (lambda reason: _report(reason, gh, env))
    sha = (env.get("GITHUB_SHA") or "").strip() or git("rev-parse", "HEAD").strip()
    no, tags = _no(git, sha), _tags(git)
    action = decide(no, tags, _changed_since_last_edition(tags, git, sha))
    if action == "skip":
        print(f"새 판을 만들지 않습니다(제{no}판은 이미 있거나 판에 들어갈 변경이 없습니다).")
        return 0
    if action == "warn":
        reason = (f"판 번호(제{no}판)를 올리지 않은 채 문답이나 내규 원본이 합쳐져 새 판을 만들지 않았습니다. 이미 나간 판은 건드리지 않았습니다. "
                  f"Claude 웹에 \"판 번호를 올려 줘\"라고 말해 판 번호를 올린 뒤 다시 합쳐 주세요.")
        print(reason)
        report(reason)
        return 1
    summary = git("log", "-1", "--format=%B", sha).replace("[skip ci]", "").strip()
    files = make_assets(no, ROOT / "dist" / "release_assets")
    gh(["release", "create", tag_of(no), *asset_args(no, files), "--title", f"내규챗봇 제{no}판", "--notes-file", "-", "--target", sha], notes(no, summary))
    print(f"제{no}판을 만들었습니다.")
    _close_release_issues(gh)
    return 0


def check_pending(git=_git, gh=_gh, report=None, env=None) -> int:
    """지금 판 번호의 새 판이 아직 안 만들어졌으면 알린다(알림만 하고 실패로 끝내지 않는다)."""
    import os
    env = os.environ if env is None else env
    report = report or (lambda reason: _report(reason, gh, env))
    no = _no(git)
    if pending_edition(no, _tags(git)):
        reason = (f"제{no}판이 아직 만들어지지 않았습니다. GitHub의 Actions 탭에서 '새 판 만들기'를 고르고 Run workflow 버튼을 눌러 주세요.")
        print(reason)
        report(reason)
    else:
        print(f"제{no}판은 이미 만들어져 있습니다.")
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) == 2 and argv[0] == "check-number":
        return check_number(argv[1])
    if len(argv) == 1 and argv[0] == "publish":
        return publish()
    if len(argv) == 1 and argv[0] == "check-pending":
        return check_pending()
    sys.exit(__doc__)


if __name__ == "__main__":
    sys.exit(main())
