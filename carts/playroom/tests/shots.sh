#!/bin/sh
# Takes the Playroom's screenshots: tests/shots.sh [SHOT...] (all of them by default).
# Each scene builds tests/_shot.akr (SHOT and an import of shots.akr), runs it headless and
# writes screenshots/NAME.png, then a contact sheet of them all (needs python3 with PIL).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
OUT="$HERE/../screenshots"
mkdir -p "$OUT"
TMP="${TMPDIR:-/tmp}/playroom_shots"
mkdir -p "$TMP"
NAMES="title follow jump orbit eyes corner rail lift chest pool tidy costs"
FRAMES="90 150 120 120 150 140 160 230 230 120 200 130"
set -- ${@:-1 2 3 4 5 6 7 8 9 10 11 12}
for n in "$@"; do
    name=$(echo $NAMES | cut -d' ' -f"$n")
    frames=$(echo $FRAMES | cut -d' ' -f"$n")
    printf 'const SHOT = %s\nimport "shots.akr"\n' "$n" > "$HERE/_shot.akr"
    "$ROOT/build/meic" "$HERE/_shot.akr" -o "$TMP/shot.mei"
    "$ROOT/build/mei-headless" "$TMP/shot.mei" --frames "$frames" --dump "$TMP/$name.ppm" --quiet
    sips -s format png "$TMP/$name.ppm" --out "$OUT/$name.png" >/dev/null
    echo "$OUT/$name.png"
done
rm -f "$HERE/_shot.akr"
python3 - "$OUT" <<'EOF'
import os, sys
from PIL import Image, ImageDraw
out = sys.argv[1]
names = "title follow jump orbit eyes corner rail lift chest pool tidy costs".split()
ims = [(n, Image.open(os.path.join(out, n + '.png')).convert('RGB')) for n in names if os.path.exists(os.path.join(out, n + '.png'))]
cols, w, h = 4, 320, 240
rows = (len(ims) + cols - 1) // cols
sheet = Image.new('RGB', (cols * (w + 6) + 6, rows * (h + 20) + 6), (34, 28, 30))
d = ImageDraw.Draw(sheet)
for i, (n, im) in enumerate(ims):
    x, y = 6 + (i % cols) * (w + 6), 6 + (i // cols) * (h + 20)
    sheet.paste(im, (x, y))
    d.text((x + 2, y + h + 4), n, fill=(240, 230, 210))
sheet.save(os.path.join(out, 'contact_sheet.png'))
print(os.path.join(out, 'contact_sheet.png'))
EOF
