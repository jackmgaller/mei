"""Draws the air-conditioner's front: a fan grille behind a round guard. Run: python3 draw_art.py"""
import math, pathlib
from PIL import Image, ImageDraw

out = pathlib.Path(__file__).parent
W, H = 40, 28
im = Image.new("RGBA", (W, H), "#eceae4")
d = ImageDraw.Draw(im)
d.rectangle([0, 0, W - 1, H - 1], outline="#c8c4b8")
d.rectangle([1, H - 6, W - 2, H - 2], fill="#dedcd4")          # lower vent slot band
for x in range(3, W - 3, 3):
    d.line([x, H - 5, x, H - 3], fill="#8e887c")
cx, cy, R = 15, 12, 10
d.ellipse([cx - R, cy - R, cx + R, cy + R], fill="#3a3c40")      # fan opening
for r in (4, 7, 10):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline="#9a9ca0")
for a in range(0, 360, 45):                                     # guard spokes
    d.line([cx, cy, cx + R * math.cos(math.radians(a)), cy + R * math.sin(math.radians(a))], fill="#9a9ca0")
d.ellipse([cx - 2, cy - 2, cx + 2, cy + 2], fill="#c8c4b8")      # hub
d.rectangle([29, 5, 36, 6], fill="#8e887c")                      # louvres at the right
d.rectangle([29, 9, 36, 10], fill="#8e887c")
d.rectangle([30, 15, 32, 17], fill="#d8462a")                    # tiny lamp
im.save(out / "aircon_front.png")
