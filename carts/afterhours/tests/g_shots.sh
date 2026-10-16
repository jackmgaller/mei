#!/bin/sh
# Agent G's captures of the dash, into tests/shots/: dash_strip.png (scenario 77: a dash in level
# 1's first room, from the tick before the press to the dash ready again; each frame cropped
# round the thief, scaled twice) and dash_caught.png (78: a dash across a narrow fan, stopped
# inside it at the first substep it covers; the freeze), with dash_caught_x3.png. MEIC, RUN and
# WORLDS as for tests/run.sh; needs sips (macOS, through tools/cart_scenario.sh) and Pillow.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
O="$HERE/out/g_shots"
S="$HERE/shots"
rm -rf "$O"
mkdir -p "$O" "$S"
SHOT=1 SEQ="1 56" "$HERE/run.sh" 77 132 "$O/s77" > "$O/s77.log" 2>&1 || { echo "FAILED scenario 77"; tail -5 "$O/s77.log"; exit 1; }
SHOT=1 "$HERE/run.sh" 78 18 "$O/s78" > "$O/s78.log" 2>&1 || { echo "FAILED scenario 78"; tail -5 "$O/s78.log"; exit 1; }
python3 - "$O" "$S" <<'EOF'
import sys
from PIL import Image, ImageDraw
o, s = sys.argv[1], sys.argv[2]
press = 60                       # the frame of the press (scenario 77)
frames = [59, 60, 62, 64, 66, 68, 70, 71, 74, 80, 90, 121]
crops = [Image.open(f"{o}/s77_seq_{f:05d}.png").convert("RGB").crop((80, 30, 250, 150)) for f in frames]
w, h = crops[0].size
cols = 6
strip = Image.new("RGB", (w * cols, h * 2))
for i, c in enumerate(crops):
    strip.paste(c, ((i % cols) * w, (i // cols) * h))
strip = strip.resize((strip.width * 2, strip.height * 2), Image.NEAREST)
d = ImageDraw.Draw(strip)
for i, f in enumerate(frames):
    x, y = (i % cols) * w * 2 + 6, (i // cols) * h * 2 + 4
    d.rectangle((x - 2, y - 1, x + 52, y + 12), fill=(0, 0, 0))
    d.text((x, y), f"tick {f - press:+d}", fill=(255, 255, 255))
strip.save(f"{s}/dash_strip.png")
im = Image.open(f"{o}/s78.png")
im.save(f"{s}/dash_caught.png")
im.resize((960, 720), Image.NEAREST).save(f"{s}/dash_caught_x3.png")
EOF
echo "$S/dash_strip.png"
echo "$S/dash_caught.png"
