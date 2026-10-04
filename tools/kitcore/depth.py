"""Depth mode for the checkers' verification carts (docs/RENDERING.md): what a cart imports and
calls to draw as a game that turned the depth buffer and perspective texturing on, and the
tolerance both checkers judge depth order with in that mode.

The standard library's `stdlib/depth.akr` provides render_depth(on) and render_perspective(on).
Until it is merged, the carts compile against a stand-in with the same API in tests/depth_shim/
(the depth prototype's face loops), passed to meic with -I. shim_dirs() picks the stand-in only
while the standard library meic compiles with has no render_depth(), so the real one takes over
by itself; then delete tests/depth_shim/ and the shim's lines here (SHIM, uses_shim() and
depth_shim_reserve() in cart_lines()).
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SHIM = ROOT/'tests'/'depth_shim'

# A pixel's depth order is judged only where the nearer face is nearer than the other by more
# than KEY_STEPS steps of the GPU's 16-bit depth key: a step is at most 1/4,096 of 1/w, so two
# faces whose 1/w differ by less than that can share a key, and the tie goes to the later packet
# (RENDERING.md, "The depth test"). Two steps cover the key's rounding and the interpolation's
# floor. In w: the farther face must be more than KEY_TOLERANCE of the nearer's depth farther.
KEY_STEPS = 2
KEY_TOLERANCE = KEY_STEPS/4096
# The World Checker's reference projects vertices exactly, the console to whole pixels, so a
# face's plane of 1/w is off by up to half a pixel's worth of its slope (RENDERING.md,
# "Precision": a floor at 11 degrees needs about ten key steps). The Asset Checker rasterises from
# the console's own projected vertices and needs no such allowance.
SNAP_PIXELS = 0.5


def stdlib_dir(compiler):
    """The standard library meic compiles with: $MEI_STDLIB, else <meic's folder>/../stdlib."""
    env = os.environ.get('MEI_STDLIB')
    return Path(env) if env else Path(compiler).resolve().parent/'..'/'stdlib'


def uses_shim(compiler):
    """Whether the stand-in is needed: the standard library has no render_depth() yet."""
    real = stdlib_dir(compiler)/'depth.akr'
    try:
        return 'fn render_depth' not in real.read_text()
    except OSError:
        return True


def include_args(compiler, depth, perspective):
    """meic's arguments for a cart drawn in this mode: -I the stand-in, when it is needed."""
    return ['-I', str(SHIM)] if (depth or perspective) and uses_shim(compiler) else []


def cart_import(depth, perspective):
    return 'import "depth.akr"\n' if depth or perspective else ''


def cart_lines(compiler, depth, perspective, max_faces, indent='    '):
    """The lines a verification cart runs at the start of each draw(), after cls()."""
    lines = []
    if depth:
        lines.append('render_depth(true)')
    if perspective:
        lines.append('render_perspective(true)')
    if (depth or perspective) and uses_shim(compiler):
        lines.append(f'depth_shim_reserve({int(max_faces)})')
    return ''.join(indent+line+'\n' for line in lines)
