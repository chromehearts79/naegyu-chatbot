"""이슈 댓글 '확인함: 사유' 로 ALIO 알림을 끝낸다. Actions 에서만 돌고, 표준 라이브러리만 쓴다.

환경 변수: COMMENT_BODY, ASSOCIATION, ISSUE_BODY, ISSUE_NUMBER
"""
import datetime
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import watch_ci  # noqa: E402
from alio_confirm import apply_confirm, pending_of  # noqa: E402
from alio_release import SEEN  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = {"OWNER", "MEMBER", "COLLABORATOR"}


def parse_reason(comment: str):
    """'확인함' 으로 시작하는 댓글이면 사유(없으면 ""), 아니면 None.
    '확인함: 사유', '확인함 사유', '확인함' 모두 읽는다. 글 중간에 낀 '확인함' 은 읽지 않는다."""
    m = re.fullmatch(r"\s*확인함(?:\s*[:：]\s*|\s+|(?=\s*$))(.*?)\s*", comment or "", re.S)
    return m.group(1) if m else None


def allowed(association: str) -> bool:
    return association in ALLOWED


def idx_of(issue_body: str):
    m = re.search(r"<!-- naegyu-idx:([0-9A-Za-z_-]+) -->", issue_body or "")
    return m.group(1) if m else None


def _say(gh, number, text: str) -> None:
    gh(["issue", "comment", str(number), "--body-file", "-"], text)


def handle(comment, association, issue_body, today, latest, seen_path, gh, issue_number, root: Path) -> str:
    if not allowed(association):
        return "무시"
    reason = parse_reason(comment)
    if reason is None:
        return "무시"
    idx = idx_of(issue_body)
    if idx is None:
        _say(gh, issue_number, "이 이슈는 내규 알림이 아니라서 기록하지 않았습니다. 내규 알림 이슈(제목이 '개정 의심' 등으로 시작하는 글)에 `확인함: 사유` 로 댓글을 남겨 주세요.")
        return "대상 없음"
    if not reason:
        _say(gh, issue_number, "사유가 비어 있어 기록하지 않았습니다. `확인함: 재게시` 처럼 사유를 함께 적어 다시 댓글을 남겨 주세요.")
        return "다시 요청"
    item = next((f for f in pending_of(latest) if str(f.get("idx")) == idx), None)
    if item is None:
        _say(gh, issue_number, "이 내규는 최근 확인 결과에 처리할 알림이 없어 기록하지 않았습니다. 이미 처리됐거나 다음 확인에서 다시 알려 드립니다.")
        return "대상 없음"
    apply_confirm(item, reason, today, seen_path, rebuild=lambda: None)
    watch_ci.drop_wait(item["name"], root)
    _say(gh, issue_number, f"확인함으로 기록했습니다. 사유: {watch_ci.clean_md(reason)}\n\n챗봇 판 번호는 바뀌지 않습니다. 이 이슈를 닫습니다.")
    gh(["issue", "close", str(issue_number)], None)
    return "기록함"


def main() -> int:
    try:
        latest = json.loads((ROOT / "reports" / "alio_watch" / "latest.json").read_text(encoding="utf-8"))
        if not isinstance(latest, dict):
            latest = {}
    except (OSError, ValueError):
        latest = {}
    today = datetime.datetime.now(watch_ci.KST).strftime("%Y-%m-%d")
    env = os.environ
    r = handle(env.get("COMMENT_BODY", ""), env.get("ASSOCIATION", ""), env.get("ISSUE_BODY", ""), today, latest,
               SEEN, watch_ci.gh_default, env["ISSUE_NUMBER"], ROOT)
    print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
