# 12 Moon-viewing Lacquer

**The idea.** A collector's edition built like a lacquered document box. The body is urushi
black over a vermilion (shu) base, like negoro ware. There is a vermilion line where the lid
meets the box, and gold kanagu fittings wrap the four lid corners. The hanafuda August card,
*susuki ni tsuki*, is set into the lid as an inlay: a vermilion sky, the full moon, and a black
hill with susuki grass worked in gold. Three gold geese, the August card's other bird, fly
across the lid, and gold susuki is drawn along both sides. The power button is a vermilion
seal and the power lamp is a small moon. The controller is a black lacquer top over a vermilion
under-shell. Each grip has a clump of gold susuki whose stalks bow toward the stick, and the
stick's cap is the moon. A B X Y are pearl (raden) with vermilion letters. The d-pad, L and R,
and Select and Start are gold.

**Sizes.** Real size in metres, not scaled. Fixed-point precision caused no problems at this
size.

- Console: 0.302 × 0.124 × 0.224 m (W × H × D). The cart in the slot counts in the height; the
  lid surface is 0.070 m high, and the cart slot's collar rises to 0.0775 m.
- Controller: 0.151 × 0.047 × 0.117 m.

**Counts.**

| Model | Triangles | Vertices | Textured triangles | Texel VRAM |
|---|---|---|---|---|
| Console | 848 | 540 | 44 | 25,975 bytes |
| Controller | 776 | 420 | 178 | 12,877 bytes |

**Checks.** Both recipes require the Asset Checker in depth mode with perspective. `verify`
reports PASS for both, with no failures. The allowed findings are crossings and T-junctions:
586 on the console and 311 on the controller.

**How it is made.** `make_moon_lacquer.py` draws `art/moon_lacquer.png` and its sheet.json with
Pillow, using Hiragino and Avenir Next. It then writes both recipes. Run it again after any
change. Most of the geometry is explicit `mesh` nodes computed in the script.

- The controller's outline is a signed-distance shape (a rounded body and two grip capsules)
  sampled into 36 points.
- The shell is a single mesh made of rings with per-face materials, so the black-over-vermilion
  split has no coplanar seam.
- The grips hang 12 mm lower than the body, so the underside is non-planar and the script
  triangulates it itself.
- `console.cameras.json` and `controller.cameras.json` hold the close views used while
  iterating: `--cameras`.

**What the kit made hard.**

- A `fit` texture spans each source polygon. The controller's top face has collinear points
  along its straight back edge, and the kit rejects a polygon with collinear points. Splitting
  the face into triangles would give each triangle its own copy of the texture. The fix is to
  triangulate the face in the script and give it hand UVs over the face's bounding rectangle.
- A raised plate with a lacquer-coloured ground looks slightly lighter than the lacquer it sits
  on: a textured face's tint and a baked vertex colour do not quite match. So the geese and the
  side grass are cutout decals 1 mm off the surface, not plates.
- The lid's top cap is a separate textured polygon, so it can carry a soft window-reflection
  gloss with a faint nashiji gold dust. For that the body loft has `caps: false` and gets its own
  underside polygon.
