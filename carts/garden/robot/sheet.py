#!/usr/bin/env python3
"""The robot's pose sheet: builds robot/poses.akr with the garden's world, runs it headless,
and lays the last frame of each pose out in a contact sheet (needs Pillow).

    python3 carts/garden/robot/sheet.py OUT_DIR [--behind] [--build build]

Writes OUT_DIR/poses.png (and poses_behind.png with --behind, the game's view) and prints the
robot's cycles per pose. The world must be built first (make builds it with the garden).
MEIC and RUN name the compiler and player (default BUILD/meic, BUILD/mei-headless).
"""
import argparse
import os
import re
import subprocess
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--behind", action="store_true", help="from behind, as the game's camera")
    ap.add_argument("--build", default="build", help="the build directory (default build)")
    a = ap.parse_args()
    build = os.path.join(ROOT, a.build)
    meic = os.environ.get("MEIC", os.path.join(build, "meic"))
    run = os.environ.get("RUN", os.path.join(build, "mei-headless"))
    worlds = os.path.join(build, "cart-worlds", "garden")
    os.makedirs(a.out, exist_ok=True)
    out = os.path.abspath(a.out)

    src = open(os.path.join(HERE, "poses.akr")).read()
    hold = int(re.search(r"const HOLD = (\d+)", src).group(1))
    names = re.findall(r'PoseShot \{ name: "([^"]+)"', src)
    view = 1 if a.behind else 0
    wrapper = os.path.join(HERE, f"_poses_{os.getpid()}.akr")
    with open(wrapper, "w") as f:
        f.write(f'cart "Robot Poses"\nconst VIEW = {view}\nimport "poses.akr"\n')
    cart = os.path.join(out, "poses.mei")
    try:
        subprocess.run([meic, "-I", worlds, wrapper, "-o", cart], check=True)
    finally:
        os.remove(wrapper)
    seq = os.path.join(out, "f")
    r = subprocess.run([run, cart, "--frames", str(hold * len(names)), "--dump-every", str(hold),
                        seq, "--dump-from", str(hold - 2)], capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        sys.exit(r.returncode)

    tiles = []
    for k, name in enumerate(names):
        p = f"{seq}_{k * hold + hold - 2:05d}.ppm"
        im = Image.open(p).convert("RGB")
        os.remove(p)
        # the middle of the frame, where the robot is
        w, h = im.size
        im = im.crop((w // 2 - 100, h // 2 - 100, w // 2 + 100, h // 2 + 88)).resize((320, 300), Image.NEAREST)
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, 320, 18), fill=(0, 0, 0))
        d.text((6, 3), name, fill=(255, 255, 255))
        tiles.append(im)
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 320 + (cols - 1) * 4, rows * 300 + (rows - 1) * 4), (20, 20, 24))
    for k, t in enumerate(tiles):
        sheet.paste(t, ((k % cols) * 324, (k // cols) * 304))
    name = "poses_behind.png" if a.behind else "poses.png"
    sheet.save(os.path.join(out, name))
    os.remove(cart)
    print("wrote", os.path.join(out, name))


if __name__ == "__main__":
    main()
