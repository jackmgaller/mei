# 15 Pocket Cube

**Idea.** The small one: a 20 × 20 × 17.6 cm rounded cube, a smaller footprint than a
paperback stack. It is in three layers, like a stacked lunchbox. A charcoal plinth holds the two
controller ports. The walls are ramune teal, and the top is cream. The cartridge stands
upright in a raised charcoal collar on top, with its label facing the player. That makes the
running game the tallest thing on the machine (25.6 cm overall). Power is a big sun-orange
button and reset a small moon-blue one, at the front corners of the top. A slider beside the
slot ejects the cart. Each player column on the front has a dot (sun for player 1, moon for
player 2), a memory card slot and a controller port. The 明 MEI badge sits centred above them.
The back has the DC in, AV out and MeiNet antenna socket, a printed strip, and vents. The sides
have vents as well. The controller carries the same three layers (charcoal underside, teal
sides, cream top). Its shape is a dogbone, and the grips swell downward toward the hands. It
has a d-pad in a dish, one centre stick, A (sun), B (moon), X (cream) and Y (slate) with
printed letters, Start and Select under a small logo, and L/R on the back edge.

**Triangles.** Console 1,180 (730 vertices; budget 1,200). Controller 782 (485 vertices;
budget 800). Textures come from one sheet, `art/pocket_sheet.png`, drawn by the generator: the
logo, the cart label, the button letters and the small print, all 8-bit `fit`. The vents use a
4-bit stripes tile. VRAM is 8,213 bytes for the console and 4,951 for the controller.

**Verify.** Both pass with verification required, in depth mode with perspective. The only
allowed findings are deliberate surface intersections, where parts are sunk 1–2 mm into the
body. There are no flush contacts.

**Scale.** Real metres, 1:1. The console's base is at y = 0 and it faces −Z. The controller
rests on its grips at y = 0, with the player on its −Z side. 16.16 fixed point had no trouble
at this size. Raised details stand 0.6–2.5 mm proud and are sunk 1–2 mm below the surface;
they are not floated on it. At game distances, the thinnest of them (the printed strips,
0.6 mm) are the first that could tie in the depth buffer.

**Files.** `make_pocket_cube.py` writes the sheet and both recipes. Run it again rather than
editing the JSON. `cameras_*.json` hold close views at world scale, for
`preview --cameras`.

**What the kit made hard.**
- Every part is a `mesh` node built in Python: outlines stacked into prisms, and rims around
  shallow wells. That gave control of the triangle counts and kept details from sitting flush.
- Quads on sloped chamfers fail "not planar" after rounding, so the generator splits every
  polygon that is not axis-aligned into triangles.
- Without holes in faces, the slots and ports are raised rims around a dark floor rather than
  real openings.
- `fit` puts the whole texture on every source polygon. So a textured button top needs its own
  material, separate from its sides, and the badge's plate is split into a frame plus a logo
  face.
- The budget set the detail level. The first pass came to 1,930 triangles for the console and
  1,232 for the controller, before the segment counts and bevels were cut.
- `build-console/mei-asset-probe` was an empty file (0 bytes), so `verify` and `preview` failed
  with "Exec format error". I compiled the probe from `tools/assetkit_probe.c` against
  `build-console/libmeicore.a` into my scratch directory and passed it with `--probe`. I did not
  run make or change `build-console/`.
