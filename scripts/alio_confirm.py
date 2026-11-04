"""담당자 '확인함': ALIO에서 바뀐 값을 보고 챗봇에 넣지 않기로 했거나 이미 반영된 것으로 끝낸다.

  python3 -X utf8 scripts/alio_confirm.py --config 설정.json

최근 결과에서 해소할 수 있는 알림을 골라 사유를 적으면 knowledge/alio_seen.json 에 지금 ALIO 값과 사유가 기록된다.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alio_release import SEEN, confirm, load_seen, _save_json  # noqa: E402
from alio_types import ATTENTION, V_FAIL, V_GONE, V_PENDING  # noqa: E402

# 배포 대기는 새 판을 내면 저절로 풀리고, 확인 실패는 값을 믿을 수 없어 확인함 대상이 아니다
SKIP = {V_PENDING, V_FAIL}


def pending_of(result_json):
    return [f for f in result_json.get("findings", []) if f.get("verdict") in ATTENTION and f["verdict"] not in SKIP]


def _default_rebuild():
    import alio_release  # 저장소가 있는 PC에서만 부른다
    alio_release.write_release()


def apply_confirm(item, reason, today, seen_path=SEEN, rebuild=_default_rebuild):
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("사유를 적어 주세요")
    seen = load_seen(seen_path)
    gone = item["verdict"] == V_GONE
    old = seen["rules"].get(item["idx"])
    values = item.get("values")
    if gone or not values:
        # 사라진 내규는 기록해 둔 값을 그대로 둔다
        values = {k: (old or {}).get(k, "") for k in ("mod", "st_date", "file_no")}
    if old is None:
        seen["rules"][item["idx"]] = {"name": item.get("name") or item.get("title", "")}
    file_date = (old or {}).get("file_date", "") if gone else item.get("file_date", "")
    confirm(seen, {"idx": item["idx"], "title": item.get("title") or item.get("name", "")}, values, file_date, reason, today, gone=gone)
    _save_json(Path(seen_path), seen)
    rebuild()


def _ask(text):
    try:
        return input(text).strip()
    except EOFError:
        return ""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args(argv)
    import datetime
    from watch_alio import load_config
    cfg = load_config(args.config)
    path = Path(cfg["docs_dir"]) / "최근 결과.json"
    if not path.exists():
        print("최근 결과가 없습니다. 먼저 ALIO 확인을 한 번 실행해 주세요.")
        return 0
    try:
        items = pending_of(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, OSError):
        print("최근 결과를 읽지 못했습니다. ALIO 확인을 다시 실행해 주세요.")
        return 1
    if not items:
        print("확인함으로 끝낼 항목이 없습니다.")
        return 0
    print("확인함으로 끝낼 항목")
    for n, it in enumerate(items, 1):
        print(f" {n}. {it.get('name') or it.get('title', '')}  ({it['verdict']})")
    done = 0
    while True:
        pick = _ask("번호를 입력하세요(끝내려면 그냥 엔터): ")
        if not pick:
            break
        if not pick.isdigit() or not 1 <= int(pick) <= len(items):
            print("목록에 있는 번호를 입력해 주세요.")
            continue
        it = items[int(pick) - 1]
        reason = _ask("사유를 한 줄로 적어 주세요(예: 내부 파일로 반영함): ")
        try:
            apply_confirm(it, reason, datetime.date.today().isoformat())
        except ValueError as e:
            print(e)
            continue
        except Exception as e:  # noqa: BLE001  새 판 목록을 다시 만들지 못해도 기록은 이미 저장됐다
            print(f"기록은 저장했지만 배포 목록을 다시 만들지 못했습니다({e}). 담당 개발자에게 알려 주세요.")
            return 1
        done += 1
        print(f"'{it.get('name') or it.get('title', '')}' 을(를) 확인함으로 기록했습니다.")
    if done:
        print("확인함을 기록했습니다. 다음 배포 때 함께 올라갑니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
