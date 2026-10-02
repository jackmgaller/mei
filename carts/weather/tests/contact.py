#!/usr/bin/env python3
"""Contact sheets of Mei Weather screenshots: a grid of frames, each with a caption.

    python3 tests/contact.py OUT.png COLS SCALE "file.png=Caption" ...

SCALE is the whole-pixel enlargement of each 320 x 240 frame (nearest neighbour, so the
console's pixels stay crisp)."""
import sys
from PIL import Image, ImageDraw, ImageFont

out, cols, scale = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
items = []
for a in sys.argv[4:]:
    path, _, cap = a.partition('=')
    items.append((path, cap))
W, H = 320 * scale, 240 * scale
CAP = 22 if scale > 1 else 16
PAD = 10
rows = (len(items) + cols - 1) // cols
sheet = Image.new('RGB', (PAD + cols * (W + PAD), PAD + rows * (H + CAP + PAD)), (24, 26, 40))
d = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype('/System/Library/Fonts/Avenir Next.ttc', 15 if scale > 1 else 11, index=0)
except OSError:
    font = ImageFont.load_default()
for k, (path, cap) in enumerate(items):
    r, c = divmod(k, cols)
    x = PAD + c * (W + PAD)
    y = PAD + r * (H + CAP + PAD)
    im = Image.open(path).convert('RGB').resize((W, H), Image.NEAREST)
    sheet.paste(im, (x, y))
    d.text((x + 2, y + H + 3), cap, fill=(220, 226, 240), font=font)
sheet.save(out)
print(out, sheet.size)
