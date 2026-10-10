# 01 Hinomaru Grey

The launch model: a low, two-tone slab in warm light grey (`#cbc6bb` over a `#b5b0a5` lower
shell, the upper shell lapping over it at a dark seam), a raised cartridge bay on the rear half
of the deck with a launch cart standing in it, and one red disc on a white ring as the power
button: the hinomaru that names it, the only saturated colour on the machine. A charcoal 明 MEI
badge sits front left; two small lamps on the front bevel, sun orange (power) and moon blue
(MeiNet), are emissive palette entries. The front is a raised port panel: memory card slots 1
and 2 above the two controller ports, each port in a dark collar. The back has the MeiNet aerial
jack (brass), AV out and DC in over printed names. The controller matches: the same grey,
charcoal d-pad, A in hinomaru red, B charcoal, X and Y mid grey, Start and Select pills, the
analog stick on the inner left grip, L and R on the far edge, the badge top centre.

| Model | Triangles | Vertices | Size (m) | Asset Checker |
|---|---|---|---|---|
| `console.asset.json` | 748 | 444 | 0.291 × 0.120 (0.077 without the cart) × 0.239 (with the rear jacks) | PASS, depth mode, 0 wrong pixels, 0 coverage errors |
| `controller.asset.json` | 778 | 458 | 0.153 × 0.039 × 0.126 (with the cable's strain relief) | PASS, depth mode, 0 wrong pixels, 0 coverage errors |

- **Scale:** metres at real size. 16.16 fixed point was no trouble at this size (the smallest
  offsets are 0.6–1 mm). Both face −Z: the console's ports, the controller's grips.
- **Textures:** one 8-bit sheet, `art/hinomaru_sheet.png` (drawn by `make_art.py` with Hiragino
  and Avenir Next): the badge, the port panel, the rear printing, the cart label, the controller
  badge, the four button tops (`disc`) and the Start/Select labels; the deck vents are a `stripes`
  pattern (the console's one texture window). The recipes are written by `make_recipes.py`.
- **Lighting:** the default directional bake, not `vertical`: on a pale, boxy object the faces
  only read apart with a light direction. A game placing the console at other yaws would want
  `vertical` and accept flatter walls.
- **What the kit made hard:** no per-face materials on boxes and cylinders, so printed faces
  (badge, port panel, rear panel) are hand-built `mesh` slabs with `face_materials`, and the
  button tops use `disc` on the whole cylinder (the sides take the texture's rim colour). Loft
  caps are flat, so the controller's top is one flat plane rather than grips that fall away.
  The controller's 800-triangle budget set the segment counts (8-segment buttons, 10-segment
  wells). `build-console/mei-asset-probe` was an empty file; the checks were run with a probe
  compiled from `tools/assetkit_probe.c` against `build-console/libmeicore.a` in a scratch
  directory (`--probe`), make not run.
