"""kordoc(한글·엑셀 → 마크다운 변환기) 호출을 한 곳에 모은다. 판은 package.json 에서 읽는다."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KORDOC_VERSION = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["dependencies"]["kordoc"]
KORDOC = f"kordoc@{KORDOC_VERSION}"


def kordoc_cmd():
    """저장소에 kordoc 이 깔려 있으면 그것을(바깥 접속 없음), 없으면 npx 로 받아 쓴다.
    윈도우에서는 which 가 .cmd 를 찾는다. npx 가 없으면 None 이 들어간다."""
    local = shutil.which("kordoc", path=str(ROOT / "node_modules" / ".bin"))
    if local:
        return [local]
    return [shutil.which("npx"), "-y", KORDOC]
