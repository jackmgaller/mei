# 08 Akihabara Silver

The idea: a 1997 spec-sheet machine in an electric-town shop window. A brushed-silver body sits on
a recessed gunmetal plinth. The rear half of the top is a gunmetal heat-sink deck with ten silver
fins on each side of the raised cart slot, and a cart ("NEON MOON") stands in the slot. A gunmetal
chamfer runs along the front edge, printed `64-BIT RISC · PRISM ENGINE 3D · 64MB CARTRIDGE ·
MEINET`, with the port numbers 1 and 2 above the ports. The top front has a smoked 明 MEI badge,
a holographic 64-BIT sticker, and two round buttons: power is the sun (orange ring) and reset is
the moon (pale blue crescent). The front has two controller sockets, each with its memory card
slit above it, a smoked LED window (orange POWER, blue MEINET) and painted ribs. Vent louvres run
along the sides, and the rear has DC IN, AV MULTI OUT, ANT IN · MEINET and a model sticker. The
controller uses the same colours: a silver top shell over a gunmetal lower shell, ribbed gunmetal
grips, and a gunmetal centre spine like the console's deck (logo, Select/Start, the analog stick).
The d-pad is on the left, A B X Y on the right as gunmetal caps with an orange A and a blue B, and
L and R are on the shoulders.

| Model | Triangles | Vertices | Size (m) | VRAM |
|---|---|---|---|---|
| `console.asset.json` | 500 | 376 | 0.300 × 0.117 (cart top; body 0.062) × 0.234 | 57,520 B |
| `controller.asset.json` | 720 | 439 | 0.158 × 0.055 (stick top) × 0.110 | 16,083 B |

- Scale: real size in metres, not scaled up. The 16.16 coordinates were precise enough. Parts
  that sit on a surface are sunk 1–2 mm into it, and the flush-contact count is 0 for both.
- Both pass `verify` with the policy in the recipe (`required`, `depth`, `perspective`):
  console "PASS (depth mode); 422 findings allowed", controller "PASS (depth mode); 309 findings
  allowed". The allowed findings are surface intersections and T-junctions.
- Facing: the console's front is −Z. The controller's grips point to −Z, toward the player in
  front of the TV, so the `front` view is the player's view and the `top` view reads upright. The
  controller is lifted so that its grips rest on y = 0.
- `make_akihabara.py` writes every PNG in `art/` (Pillow, the Hiragino and DIN system fonts) and
  both recipes. Nearly all geometry is explicit `mesh` nodes built by small helpers (ring lofts,
  slabs, prisms) with `face_materials`, so each painted face (top, front, chamfer, sides, rear,
  badge, cart label, controller face) is a single polygon with its own `fit` texture. The body
  gets its detail from texture, not triangles. The console leaves about 700 triangles of its
  budget unused.

What the kit made hard:

- `fit` covers each source polygon's bounding rectangle. To place printed details I had to work
  out every polygon's rectangle and paint in world coordinates mapped into it. A loft or extrude
  could not do this, because it gives all its faces one material, which is why the helpers build
  explicit meshes.
- My helpers first rounded vertices to 1 µm after testing whether a quad was planar. On the
  inset controller rings that rounding made some quads fail the kit's planarity check ("Polygon
  is not planar"). The helpers now round first and then test, and split a quad into two
  triangles when it is not planar.
- At the start of the session `build-console/mei-asset-probe` was an empty file, so `preview`
  failed with "Exec format error". I compiled a private probe in my scratchpad from
  `tools/assetkit_probe.c` and `build-console/libmeicore.a`. The shared probe was rebuilt later,
  and the final `verify` and preview runs used the tools in `build-console/`.
- The `--closeups` `eye_level` view puts the camera 1.6 units above the asset, so it shows an
  object this small as a speck. Close views need `--cameras`.
