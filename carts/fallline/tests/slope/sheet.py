#!/usr/bin/env python3
"""Makes a contact sheet (every 4th frame, 6 across, with tick labels) and an animated GIF (every
frame, 30 fps, doubled) from the f_*.ppm frames in DIR, as OUT.png and OUT.gif; then deletes the
PPMs. Usage: sheet.py DIR OUT"""
import glob, os, sys
from PIL import Image, ImageDraw

d, out = sys.argv[1], sys.argv[2]
files = sorted(glob.glob(os.path.join(d, 'f_*.ppm')))
frames = [Image.open(f).convert('RGB') for f in files]
ticks = [int(os.path.basename(f)[2:-4]) for f in files]
pick = list(range(0, len(frames), 4))
cols = 6
w, h = frames[0].size
rows = (len(pick) + cols - 1) // cols
sheet = Image.new('RGB', (cols * w, rows * h), (0, 0, 0))
dr = ImageDraw.Draw(sheet)
for n, i in enumerate(pick):
    x, y = (n % cols) * w, (n // cols) * h
    sheet.paste(frames[i], (x, y))
    dr.rectangle([x, y, x + 34, y + 10], fill=(0, 0, 0))
    dr.text((x + 2, y), str(ticks[i]), fill=(255, 255, 0))
sheet.save(out + '.png')
big = [f.resize((w * 2, h * 2), Image.NEAREST).quantize(colors=255, method=Image.Quantize.MEDIANCUT) for f in frames]
big[0].save(out + '.gif', save_all=True, append_images=big[1:], duration=33, loop=0, optimize=False)
for f in files:
    os.remove(f)
print(f'{out}.png ({len(pick)} frames), {out}.gif ({len(frames)} frames)')
