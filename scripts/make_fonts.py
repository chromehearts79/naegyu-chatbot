"""에이투지체 한글 글꼴(TTF)을 화면 파일에 넣을 WOFF2로 바꾼다. 글꼴을 바꿀 때만 한 번 쓴다.

  python3 scripts/make_fonts.py ~/Downloads/에이투지체-ttf-v1

fonttools·brotli 가 필요하다(pip install fonttools brotli). 글자를 빼지 않고 형식만 바꾸므로
저작권·사용 조건 표시(글꼴 안의 name 표)가 그대로 남는다. 화면에 쓰는 굵기(400·500·600·700)만 만든다.
결과(web/fonts/a2z-*.woff2)는 build_web.py 가 화면 파일 안에 넣는다.
"""
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "web" / "fonts"
WEIGHTS = {400: "4Regular", 500: "5Medium", 600: "6SemiBold", 700: "7Bold"}


def main(src):
    OUT.mkdir(parents=True, exist_ok=True)
    for w, name in WEIGHTS.items():
        f = TTFont(Path(src).expanduser() / f"에이투지체-{name}.ttf")
        f.flavor = "woff2"
        out = OUT / f"a2z-{w}.woff2"
        f.save(out)
        print(f"{out.relative_to(ROOT)} {out.stat().st_size // 1024}KB")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
