#!/bin/sh
# 내규 원본(hwp·hwpx·xlsx)을 data/md 아래 마크다운으로 바꾼다.
# 원본 폴더는 첫 인자로 바꿀 수 있다.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${1:-$ROOT/원본}"
if [ -x "$ROOT/node_modules/.bin/kordoc" ]; then KORDOC="$ROOT/node_modules/.bin/kordoc"; else KORDOC="npx -y kordoc@4.24.1"; fi
OUT="$ROOT/data/md"
rm -rf "$OUT" && mkdir -p "$OUT"
find "$SRC" -type f \( -name '*.hwp' -o -name '*.hwpx' -o -name '*.xlsx' \) -print0 \
  | xargs -0 $KORDOC --jobs 6 -d "$OUT" > "$ROOT/data/convert.log" 2>&1
echo "변환 $(ls "$OUT"/*.md | wc -l | tr -d ' ')개 → $OUT"
