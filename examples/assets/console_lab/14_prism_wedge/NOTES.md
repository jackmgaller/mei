# 14 Prism Wedge

**Idea.** The console is a raked wedge, low at the front prow and high at the back, cut like a
gem: a shallow ridge down the middle splits the top into two facets, a 45° chamfer runs all
round, and the front comes to a point. A spectrum chevron (six bands, red to violet) wraps over
the top and down both sides. Ahead of it is a gloss-black visor carrying the 明·MEI logo and a
small orange power lamp. Behind it, on the grey deck, sits a chamfered hexagonal cart bay with
a cart in it. To its left are triangular-section "prism" ribs; to its right, hexagonal power
(sun orange, 日) and reset (moon blue, 月) keys. The left front facet holds the two controller
ports and the right front facet the two memory card slots, all recessed into the shell with
light rims. The back has an AV multi-out, a DC jack, vent slits and a MeiNet antenna jack. The
controller uses the same grey and faceting: grips that drop away in triangulated facets, with
the d-pad and the A B X Y on black hexagonal plates and the face buttons in spectrum colours
(A red, B yellow, X blue, Y green). A spectrum chevron with a black panel in front of it
holds Start and Select between the clusters. The analog stick is below the d-pad, with L and R
on the back edge.

**Counts** (from `inspect`):

| Recipe | Triangles | Vertices | Textures |
|---|---|---|---|
| `console.asset.json` | 884 | 480 | logo 96 × 32, cart label 64 × 32, 8-bit, 5,346 VRAM bytes |
| `controller.asset.json` | 562 | 313 | logo 96 × 32, 8-bit, 3,201 VRAM bytes |

Both pass `verify` in depth mode with verification required: 0 failures, only the
surface intersections that depth mode allows, and no T-junctions.

**Scale.** Real metres, not scaled up. The console is 0.300 × 0.244 m and 0.15 m tall with the
cart (0.10 m without). The controller is 0.158 × 0.116 m. Fixed point was no trouble at this
size.

**Files.** `make_prism_wedge.py` writes the art, using Pillow and the macOS fonts Hiragino Sans
GB, Avenir Next and Futura, and both recipes. `prismkit.py` is its polygon builder.
`cameras_*.json` are close views for `preview --cameras`.

**What the kit made hard.**
- There are no booleans or holes. Recessed ports, the cart slot, the stripes and the decals
  are made by cutting the shell's polygons along lines (`prismkit.py`: `cut`, `region`,
  `recess`). The builder then welds vertices, adds every vertex that lies on another face's
  edge to that edge, and triangulates the polygons itself. The kit's triangulator rejects the
  collinear points this leaves.
- A `fit` texture on a sloped facet is rotated, because its "up" is +Y projected onto the
  face, and the ridge tilts the facets sideways. The logos use hand `uvs` in plan instead.
- On the near-black visor, a texel with the visor's own colour draws darker than the untextured
  face: at these values, the 15-bit colour and the shade tint both round down. The logo's
  background is lifted to `#1c1d24` so it matches the visor in renders.
- The `--closeups` eye-level view puts the camera 1.6 m up, which at console size is a speck.
  I used the camera files instead.
