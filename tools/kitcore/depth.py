"""Depth mode for the checkers' verification carts (docs/RENDERING.md): what a cart imports and
calls to draw as a game that turned the depth buffer and perspective texturing on
(stdlib/depth.akr: render_depth(), render_perspective()), and the tolerance both checkers judge
depth order with in that mode.
"""

# A pixel's depth order is judged only where the nearest face is nearer than the other by more
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


def cart_import(depth, perspective):
    return 'import "depth.akr"\n' if depth or perspective else ''


def cart_lines(depth, perspective, indent='    '):
    """The lines a verification cart runs at the start of each draw(), after cls(). With
    render_depth(true) mesh*() draws every face with depth, so textures are perspective-correct
    whatever render_perspective() says (stdlib/depth.akr)."""
    lines = []
    if depth:
        lines.append('render_depth(true)')
    if perspective:
        lines.append('render_perspective(true)')
    return ''.join(indent+line+'\n' for line in lines)
