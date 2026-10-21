#!/bin/sh
# 내규 원본(hwp·hwpx·xlsx)을 data/md 아래 마크다운으로 바꾼다.
# 원본 폴더는 첫 인자로 바꿀 수 있다.
set -e
SRC="${1:-$HOME/Library/Mobile Documents/com~apple~CloudDocs/내규챗봇}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/data/md"
rm -rf "$OUT" && mkdir -p "$OUT"
find "$SRC" -type f \( -name '*.hwp' -o -name '*.hwpx' -o -name '*.xlsx' \) -print0 \
  | xargs -0 npx -y kordoc --jobs 6 -d "$OUT" > "$ROOT/data/convert.log" 2>&1
echo "변환 $(ls "$OUT"/*.md | wc -l | tr -d ' ')개 → $OUT"
