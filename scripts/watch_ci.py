"""매주 확인(GitHub Actions)의 결과 내기: 이슈·대기 폴더·실행 기록.

판정은 watch_alio.judge 가 한다. 여기서는 그 결과를 쉬운 한국어 이슈로 옮기고
대기/ 폴더와 reports/alio_watch/ 기록을 남긴다.

  python3 -X utf8 scripts/watch_ci.py [--no-weekly]
  python3 -X utf8 scripts/watch_ci.py --report-failure "<사유>" [--kind release]

--report-failure 는 패키지 설치가 실패해도 돌아야 하므로, 맨 위 import 는
표준 라이브러리와 alio_types·alio_report·alio_client 까지만 쓴다.
"""
import argparse
import dataclasses
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import alio_report as RP  # noqa: E402
import alio_types as T  # noqa: E402
from alio_client import AlioError, default_http, fetch_attachments, fetch_file, fetch_list  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LABEL = "개정 의심"
RECORD_TITLE = "매주 확인 기록"
KST = datetime.timezone(datetime.timedelta(hours=9))
CLAUDE_URL = "https://claude.ai/code"
CUT_NOTE = "※ 글이 너무 길어 일부가 잘렸습니다. 전체 내용은 ALIO 게시판의 파일에서 확인해 주세요."
_CLEAN = str.maketrans({"@": "＠", "`": "'", "<": "＜", ">": "＞", "|": "／", "[": "［", "]": "］"})
_IDX_RE = re.compile(r"<!-- naegyu-idx:([^ >]+) -->")


# ---------- 글자 다루기 ----------

def kst_date(iso: str) -> str:
    """GitHub 시각(UTC)을 한국 날짜(YYYY-MM-DD)로. 읽지 못하면 빈 글자."""
    try:
        t = datetime.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return ""
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    return t.astimezone(KST).strftime("%Y-%m-%d")


def clean_md(s: str) -> str:
    """ALIO 에서 온 글자가 이슈 마크다운을 깨거나 알림을 보내지 않게, 비슷하게 생긴 글자로 바꾼다."""
    return re.sub(r"[\r\n]+", " ", str(s)).translate(_CLEAN)


def marker(idx: str) -> str:
    return f"<!-- naegyu-idx:{re.sub(r'[^0-9A-Za-z_-]', '', str(idx))} -->"


def _fail_marker(kind: str) -> str:
    return f"<!-- naegyu-fail:{kind} -->"


def _cut(s, n: int, flag: list) -> str:
    s = str(s)
    if len(s) > n:
        flag.append(1)
        s = s[:n] + "…"
    return clean_md(s)


# ---------- 이슈 글 ----------

def issue_title(f) -> str:
    return f"{f.verdict}: {clean_md(f.name)}"


def _late_line(days) -> str:
    if days is not None and days >= RP.LATE_DAYS:
        return f"{RP.LATE_DAYS}일이 넘었습니다. 정 담당 확인, 부재면 게시판에 미반영 공지를 올려 주세요."
    return ""


def _compare_lines(f, n: int, flag: list) -> list:
    c = f.compare
    out = []
    if c is None:
        return out
    if f.verdict == T.V_NEW:
        count = sum(1 for u in c.added_units if str(u).startswith("제"))
        out.append(f"- 새 내규의 조문: {count}개")
    if c.changed_units:
        out.append("- 바뀐 조문: " + ", ".join(clean_md(u) for u in c.changed_units[:60]))
    if c.stale_cards:
        out.append(f"- 다시 확인할 문답: {len(c.stale_cards)}장 ({', '.join(clean_md(x) for x in c.stale_cards[:30])})")
    if c.related_cards:
        out.append(f"- 참고할 문답: {len(c.related_cards)}장 ({', '.join(clean_md(x) for x in c.related_cards[:30])})")
    if c.calcs:
        out.append("- 확인할 계산기: " + ", ".join(clean_md(x) for x in c.calcs[:30]))
    if f.verdict == T.V_OUTSIDE:
        shown = [x for x in c.outside_diff if not str(x).startswith(("---", "+++", "@@"))]
        if shown:
            out.append("- 조문 밖에서 달라진 글자: " + "; ".join(_cut(x, 200, flag) for x in shown[:5]))
    if c.error:
        out.append("- 비교하지 못했습니다: " + clean_md(c.error))
    if c.before_after:
        if n <= 0:
            flag.append(1)
            out += ["", "개정 전·후 글은 너무 길어 생략했습니다."]
        else:
            out += ["", "### 개정 전·후 글(일부)"]
            for u, a, b in c.before_after[:5]:
                out += [f"**{clean_md(u)}**", f"- 이전: {_cut(a, n, flag)}", f"- 이후: {_cut(b, n, flag)}", ""]
    return out


def issue_body(f, today: str, limit: int = 60000) -> str:
    head = marker(f.idx) + "\n"
    next_steps = "\n".join([
        "## 다음에 할 일",
        f"1. {CLAUDE_URL} 에서 이 저장소를 열고 \"내규 개정 반영\"이라고 말합니다.",
        "2. 새 판으로 반영할 필요가 없는 알림(예: 같은 내용을 다시 게시한 경우)이면, 이 이슈에 `확인함: 사유` 라고 댓글을 달면 끝납니다. (GitHub 화면의 Comment 버튼)",
        "3. 문제가 해소되면 이 이슈는 저절로 닫힙니다.",
    ]) + "\n"

    def details(n, flag):
        lines = [f"## {f.verdict}: {clean_md(f.name)}", ""]
        if f.code:
            lines.append(f"- 분류 코드: {clean_md(f.code)}")
        lines.append(f"- 확인한 날: {today}")
        if f.st_date:
            lines.append(f"- 목록 날짜: {clean_md(f.st_date)}")
        if f.mod:
            lines.append(f"- 게시일: {clean_md(f.mod)}")
        if f.days is not None:
            lines.append(f"- 경과일: {f.days}일")
            if _late_line(f.days):
                lines.append(f"- **{_late_line(f.days)}**")
        for note in f.notes:
            lines.append(f"- 참고: {clean_md(note)}")
        cmp_lines = _compare_lines(f, n, flag)
        if cmp_lines:
            lines += ["", "## 비교 결과", ""] + cmp_lines
        if f.saved_dir or f.target_name:
            lines += ["", "## 받아 둔 파일", ""]
            if f.saved_dir:
                lines.append(f"- 받은 파일 위치: {clean_md(f.saved_dir)}")
            if f.target_name:
                lines.append(f"- 원본 폴더에 넣을 이름: {clean_md(f.target_name)}")
        return "\n".join(lines) + "\n"

    body, mid = "", ""
    for n in (1500, 600, 200, 0):
        flag = []
        mid = details(n, flag)
        if flag:
            mid += "\n" + CUT_NOTE + "\n"
        body = head + "\n" + mid + "\n" + next_steps
        if len(body) <= limit:
            return body
    room = max(limit - len(head) - len(next_steps) - len(CUT_NOTE) - 8, 0)
    return head + "\n" + mid[:room] + "…\n\n" + CUT_NOTE + "\n\n" + next_steps


def week_comment(f, today: str) -> str:
    lines = [f"{today} 확인: 아직 '{f.verdict}' 상태입니다."]
    if f.days is not None:
        lines.append(f"게시일부터 {f.days}일이 지났습니다.")
    if _late_line(f.days):
        lines.append(_late_line(f.days))
    return "\n\n".join(lines)


# ---------- 이슈 행동 계획 ----------

def _name_from_title(title: str) -> str:
    return title.partition(": ")[2] or title


def plan_actions(findings, open_issues: list, today: str, assignees: list, weekly: bool = True) -> list:
    by_idx = {f.idx: f for f in findings}
    actions, seen = [], set()
    for iss in open_issues:
        m = _IDX_RE.search(iss.get("body") or "")
        if not m:
            continue  # 우리가 만든 내규 이슈가 아니면 건드리지 않는다
        idx, n = m.group(1), iss["number"]
        f = by_idx.get(idx)
        if f is None or f.verdict not in T.ATTENTION or idx in seen:
            actions.append({"kind": "close", "number": n, "idx": idx, "name": f.name if f else _name_from_title(iss.get("title", ""))})
            continue
        seen.add(idx)
        actions.append({"kind": "edit", "number": n, "title": issue_title(f), "body": issue_body(f, today)})
        last, created = iss.get("lastCommentDate", ""), kst_date(iss.get("createdAt", ""))
        if weekly and last != today and created != today:
            actions.append({"kind": "comment", "number": n, "body": week_comment(f, today)})
    for f in findings:
        if f.verdict in T.ATTENTION and f.idx not in seen:
            seen.add(f.idx)
            actions.append({"kind": "create", "title": issue_title(f), "body": issue_body(f, today), "labels": [LABEL], "assignees": list(assignees)})
    return actions


def heartbeat_text(findings, today: str, unlisted: list | None = None) -> str:
    attn = [f for f in findings if f.verdict in T.ATTENTION]
    if not attn:
        lines = [f"{today} 확인 완료: 이번 주 변동 없음"]
    else:
        lines = [f"{today} 확인 완료: 확인할 내규 {len(attn)}건"]
        lines += [f"- {clean_md(f.name)}: {f.verdict}" for f in attn[:50]]
    if unlisted:
        lines.append("아직 ALIO 목록에 없는 내규: " + ", ".join(clean_md(n) for n in unlisted[:50]))
    return "\n".join(lines)


def heartbeat_actions(findings, pinned, today: str, assignees: list | None = None, unlisted: list | None = None) -> list:
    text = heartbeat_text(findings, today, unlisted)
    if pinned is None:
        body = "이 이슈에는 매주 월요일 확인이 끝날 때마다 댓글이 달립니다. 댓글 메일이 오지 않는 주는 확인이 멈춘 것입니다.\n\n" + text
        return [{"kind": "create", "title": RECORD_TITLE, "body": body, "labels": [], "assignees": list(assignees or []), "pin": True}]
    if pinned.get("lastCommentDate", "") == today or kst_date(pinned.get("createdAt", "")) == today:
        return []
    return [{"kind": "comment", "number": pinned["number"], "body": text}]


def failure_actions(reason: str, open_issues, today: str, assignees: list, kind: str = "watch") -> list:
    mark = _fail_marker(kind)
    reason = clean_md(reason)[:2000]
    for iss in open_issues:
        if mark in (iss.get("body") or ""):
            if iss.get("lastCommentDate", "") == today or kst_date(iss.get("createdAt", "")) == today:
                return []  # 같은 날 다시 돌아도 같은 알림을 겹쳐 달지 않는다
            return [{"kind": "comment", "number": iss["number"], "body": f"{today} 다시 확인했지만 또 실패했습니다.\n\n사유: {reason}"}]
    if kind == "release":
        title = "새 판 실패: 새 판 만들기"
        what = "새 판 만들기가 끝까지 되지 않았습니다. 챗봇 화면은 이전 판 그대로입니다."
        follow = "원인을 해결한 뒤 다시 새 판을 만들면, 새 판이 만들어질 때 이 이슈는 저절로 닫힙니다."
    elif kind == "upload":
        title = "공개 점검 실패"
        what = "공개 저장소에 올라가면 안 되는 이름의 파일이 올라갔을 수 있습니다."
        follow = "처리가 끝난 뒤 이 이슈를 직접 닫아 주세요(Close issue 버튼). 이 이슈는 다음 주 확인이 성공해도 저절로 닫히지 않습니다."
    else:
        title = "확인 실패: ALIO 매주 확인"
        what = "이번 주 ALIO 확인이 끝까지 되지 않았습니다. 변동이 없다는 뜻이 아니라, 알 수 없다는 뜻입니다."
        follow = "다음 주 확인이 성공하면 이 이슈는 저절로 닫힙니다."
    body = "\n".join([mark, "", f"## {title}", "", what, "", f"- 날짜: {today}", f"- 사유: {reason}", "", "## 다음에 할 일", "",
                      f"1. {follow}", f"2. 계속 실패하면 {CLAUDE_URL} 에서 이 저장소를 열고 \"{title.split(':')[0]} 이슈를 봐 줘\"라고 말합니다."]) + "\n"
    return [{"kind": "create", "title": title, "body": body, "labels": [], "assignees": list(assignees)}]


def apply_actions(actions: list, gh) -> None:
    """행동을 gh 로 하나씩 한다. 하나가 실패해도 나머지를 하고, 끝에 실패가 있었으면 알린다."""
    errors = []
    for a in actions:
        try:
            _apply_one(a, gh)
        except Exception as e:  # noqa: BLE001 - 이슈 하나 실패가 나머지를 막지 않게
            errors.append(f"{a['kind']}: {e}")
    if errors:
        raise RuntimeError("이슈를 쓰지 못함: " + "; ".join(errors)[:500])


def _create_args(a, with_assignees: bool) -> list:
    args = ["issue", "create", "--title", a["title"], "--body-file", "-"]
    for lab in a.get("labels") or []:
        args += ["--label", lab]
    if with_assignees and a.get("assignees"):
        args += ["--assignee", ",".join(a["assignees"])]
    return args


def _apply_one(a, gh) -> None:
    kind, n = a["kind"], str(a.get("number", ""))
    if kind == "create":
        try:
            out = gh(_create_args(a, True), a["body"])
        except Exception:
            if not a.get("assignees"):
                raise
            note = "\n\n※ 담당자 지정을 하지 못했습니다. 저장소 변수 NAEGYU_ASSIGNEES 의 GitHub 아이디를 확인해 주세요.\n"
            out = gh(_create_args(a, False), a["body"] + note)
        if a.get("pin"):
            num = (out or "").strip().rsplit("/", 1)[-1]
            if num.isdigit():
                try:
                    gh(["issue", "pin", num], None)
                except Exception:  # noqa: BLE001 - 고정은 못 해도 기록은 남는다
                    pass
    elif kind == "edit":
        gh(["issue", "edit", n, "--title", a["title"], "--body-file", "-"], a["body"])
    elif kind == "comment":
        gh(["issue", "comment", n, "--body-file", "-"], a["body"])
    elif kind == "close":
        gh(["issue", "close", n], None)


# ---------- 대기 폴더 ----------

def drop_wait(name: str, root: Path) -> int:
    """대기/ 에서 이 내규의 폴더(<이름>_<숫자>)만 지운다. 지운 개수를 돌려준다."""
    wait = Path(root) / "대기"
    if not wait.is_dir():
        return 0
    n = 0
    for d in wait.iterdir():
        if not d.is_dir() or d.is_symlink():
            continue
        m = re.fullmatch(r"(.*)_(\d+)", d.name)
        if (m and RP.safe_name(f"{name}_{m.group(2)}", 60) == d.name):
            shutil.rmtree(d)
            n += 1
    return n


def save_wait(f, root: Path) -> str:
    """같은 내규의 옛 폴더를 지우고 현행 묶음을 대기/ 에 둔다. 저장소 기준 경로를 '/' 로 돌려준다."""
    drop_wait(f.name, root)
    folder = RP.save_bundle(Path(root) / "대기", f)
    return Path(folder).relative_to(root).as_posix()


# ---------- 실행 ----------

def gh_default(args, stdin=None) -> str:
    try:
        r = subprocess.run(["gh", *args], input=stdin, text=True, encoding="utf-8", capture_output=True, check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"gh {' '.join(args[:2])} 실패: {(e.stderr or '').strip()[:300]}") from None
    return r.stdout


def _ours(author) -> bool:
    """이 도구(GitHub Actions)가 만든 이슈만 우리 것으로 본다."""
    a = author if isinstance(author, dict) else {}
    return bool(a.get("is_bot")) and "github-actions" in str(a.get("login") or "")


def _list_open(gh) -> list:
    raw = gh(["issue", "list", "--state", "open", "--limit", "200", "--json", "number,title,body,createdAt,comments,author"], None)
    out = []
    for i in json.loads(raw or "[]"):
        d = dict(i)
        if not _ours(d.pop("author", None)):
            continue  # 공개 저장소라 낯선 사람이 쓴 이슈는 우리 이슈로 믿지 않는다
        if "comments" in d:
            cs = d.pop("comments") or []
            d["lastCommentDate"] = kst_date(max(c.get("createdAt", "") for c in cs)) if cs else ""
        out.append(d)
    return out


def _collect(http, compare, today):
    import alio_release as R  # 패키지가 있어야 하는 것들은 여기서만 부른다
    import watch_alio as W
    release = R.build_release(R._rules(), R._load_sources(), R.load_seen(), R._release_no(), today)
    rows = fetch_list(http)
    W.check_sanity(rows, release)
    atts = {row["idx"]: fetch_attachments(row, http) for row in rows}  # 하나라도 실패하면 전체 실패
    return W.judge(rows, atts, release, None, lambda n: fetch_file(n, http), compare, "full")


def _why(e) -> str:
    if isinstance(e, (AlioError, T.WatchFailure)):
        return str(e)
    return f"{type(e).__name__}: {e}"[:300]


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _succeed(judged, gh, today, root, out, weekly, assignees) -> None:
    # 합쳤는데 아직 ALIO 목록에 안 보이는 새 내규(idx 가 없음)는 이슈 표지가 맞지 않으므로 이슈로 다루지 않고 기록에만 적는다
    unlisted = [f.name for f in judged if f.verdict == T.V_GONE and not f.idx]
    findings = [f for f in judged if not (f.verdict == T.V_GONE and not f.idx)]
    for f in findings:
        if f.files and f.verdict in T.ATTENTION:
            try:
                f.saved_dir = save_wait(f, root)
            except OSError as e:
                f.notes.append(f"파일을 저장하지 못함({type(e).__name__}). 대기 폴더를 확인해 주세요.")
    issues = _list_open(gh)
    created = {m.group(1): kst_date(i.get("createdAt", "")) for i in issues for m in [_IDX_RE.search(i.get("body") or "")] if m}
    for f in findings:
        if f.verdict in T.ATTENTION:
            f.days = RP.elapsed_days(f.mod, created.get(f.idx) or None, today)
    _write_json(out / "latest.json", {"today": today, "findings": [dataclasses.asdict(dataclasses.replace(f, files=[])) for f in findings], "unlisted": unlisted})
    actions = plan_actions(findings, issues, today, assignees, weekly)
    active = {f.idx for f in findings if f.verdict in T.ATTENTION}
    for a in actions:
        if a["kind"] == "close" and a["idx"] not in active:
            drop_wait(a["name"], root)  # 해소된 내규의 폴더만 지운다
    if weekly:
        pinned = next((i for i in issues if i.get("title") == RECORD_TITLE), None)
        actions += heartbeat_actions(findings, pinned, today, assignees, unlisted)
    actions += [{"kind": "close", "number": i["number"]} for i in issues if _fail_marker("watch") in (i.get("body") or "")]
    apply_actions(actions, gh)
    counts = {}
    for f in judged:
        counts[f.verdict] = counts.get(f.verdict, 0) + 1
    _write_json(out / "last_run.json", {"today": today, "ok": True, "counts": counts, "total": len(judged)})


def run_ci(http, gh, compare, now, root: Path, weekly: bool = True, tries: int = 2, wait: int = 300, sleep=None, assignees: list | None = None) -> int:
    """매주 확인을 한 번 돈다. 0 이면 성공, 1 이면 확인 실패. 예외를 밖으로 내지 않는다."""
    sleep = sleep or time.sleep
    try:
        root, assignees = Path(root), list(assignees or [])
        today, out = now.strftime("%Y-%m-%d"), Path(root) / "reports" / "alio_watch"
        reason, findings = "", None
        try:
            gh(["label", "create", LABEL, "--force"], None)
        except Exception:  # noqa: BLE001 - 라벨이 없으면 이슈를 만들 때 드러난다
            pass
        try:
            for attempt in range(max(tries, 1)):
                try:
                    findings = _collect(http, compare, today)
                    break
                except Exception as e:  # noqa: BLE001
                    reason = _why(e)
                    if attempt < tries - 1:
                        sleep(wait)
            if findings is not None:
                _succeed(findings, gh, today, root, out, weekly, assignees)
                return 0
        except Exception as e:  # noqa: BLE001
            reason = _why(e)
        _fail(gh, today, out, reason, assignees)
        return 1
    except Exception:  # noqa: BLE001
        return 1


def _fail(gh, today, out, reason, assignees, kind="watch") -> None:
    try:
        _write_json(out / "last_run.json", {"today": today, "ok": False, "error": reason})
    except OSError:
        pass
    try:
        apply_actions(failure_actions(reason, _list_open(gh), today, assignees, kind), gh)
    except Exception:  # noqa: BLE001 - 알릴 수 없어도 작업은 실패로 끝난다
        pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ALIO 매주 확인 결과 내기")
    ap.add_argument("--no-weekly", action="store_true", help="매주 기록 댓글과 미해소 댓글을 달지 않음")
    ap.add_argument("--report-failure", metavar="사유", help="실패 이슈만 만들거나 고침")
    ap.add_argument("--kind", choices=("watch", "release", "upload"), default="watch")
    args = ap.parse_args(argv)
    assignees = [x.strip() for x in os.environ.get("NAEGYU_ASSIGNEES", "").split(",") if x.strip()]
    now = datetime.datetime.now(KST)
    if args.report_failure is not None:
        today = now.strftime("%Y-%m-%d")
        try:
            apply_actions(failure_actions(args.report_failure, _list_open(gh_default), today, assignees, args.kind), gh_default)
        except Exception as e:  # noqa: BLE001
            print(f"실패 이슈를 쓰지 못했습니다: {e}", file=sys.stderr)
            return 1
        return 0

    def compare(*a):  # 불러오기 실패도 run_ci 의 실패 처리(이슈·기록)로 가게 늦게 부른다
        from alio_compare import compare_rule
        return compare_rule(*a)
    return run_ci(default_http, gh_default, compare, now, ROOT, weekly=not args.no_weekly, assignees=assignees)


if __name__ == "__main__":
    sys.exit(main())
