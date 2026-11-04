"""ALIO 확인 루틴이 함께 쓰는 판정 이름과 자료 꼴. 표준 라이브러리만 쓴다."""
from dataclasses import dataclass, field

V_NONE = "변동 없음"
V_DONE = "이미 반영"
V_SAME_TEXT = "글자 변화 없음"
V_PENDING = "배포 대기"
V_OUTSIDE = "조문 밖 변화"
V_SUSPECT = "개정 의심"
V_CHECK = "담당자 확인"
V_NEW = "새 내규"
V_GONE = "목록에서 사라짐"
V_FAIL = "확인 실패"

# 담당자에게 알리는 판정
ATTENTION = {V_PENDING, V_OUTSIDE, V_SUSPECT, V_CHECK, V_NEW, V_GONE, V_FAIL}


@dataclass
class CompareResult:
    changed_units: list
    stale_cards: list
    related_cards: list
    calcs: list
    added_units: list
    before_after: list  # (조문, 이전, 이후)
    outside_diff: list
    whole_same: bool
    error: str | None = None


@dataclass
class Finding:
    name: str
    code: str
    idx: str
    verdict: str
    title: str = ""
    st_date: str = ""
    mod: str = ""
    file_date: str = ""
    ext: str = ""
    values: dict | None = None  # values_of 결과. 확인함에 쓴다
    notes: list = field(default_factory=list)
    compare: CompareResult | None = None
    files: list = field(default_factory=list)
    saved_dir: str = ""
    target_name: str = ""
    days: int | None = None


class WatchFailure(Exception):
    """실행 전체를 확인 실패로 끝내는 사정"""
