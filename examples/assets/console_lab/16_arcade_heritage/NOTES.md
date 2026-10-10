# 16 Arcade Heritage

The Mei as a maker of arcade boards would build it: a candy-cabinet console in cream, pink and
mint. Seen from the side, the console is a small cabinet. Two side panels with pink T-molding
frame a sloped control panel carrying 30 mm and 24 mm Sanwa-style buttons (power pink, reset
mint) and a backlit 明 MEI marquee, with a hood above holding the cart slot between two speaker
grilles. On the kickplate, 1P and 2P ports flank a coin-door plate that holds the two memory card
slots. The controller follows the same idea: a mini ball-top lever as the analog stick, A B X Y
as dome-plunger buttons in a two-row stagger on a plum plate, lit rectangular START and SELECT
like a cabinet's 1P/2P start, and a pink band around its edge for the T-molding. The cart in
the slot is "Star Rally".

| | Triangles | Vertices | Size (m) | Textures |
|---|---|---|---|---|
| `console.asset.json` | 892 | 518 | 0.300 × 0.161 (with cart; body 0.118) × 0.246 | 10 fit textures, 40,544 B in slots 12–14 |
| `controller.asset.json` | 866 | 523 | 0.160 × 0.056 (stick) × 0.128 (with cord) | 5 fit textures, 12,405 B in slot 14 |

- Real size in metres, no scale-up. The 16.16 fixed point had no trouble at this size: the
  smallest offsets are 0.4–1.5 mm (decals, the slot mouth), well above its 0.015 mm step.
- Both pass the Asset Checker in depth mode (`"verification": {"required": true, "depth": true,
  "perspective": true}`): 0 wrong pixels and 0 coverage errors. The console was judged over 33
  views, the controller over 16.
- The controller is 866 triangles, a little over the ~800 guide. Most of that is the shell's
  six rings of 28 points with the face and underside (332). The rest is 50 a button, 48 for the
  ball-top and 30 for its washer.
- Everything comes from `make_arcade.py`, which needs Pillow. It draws `art/arcade_sheet.png`
  (named cells in `arcade_sheet.sheet.json`, with the 明 drawn by hand in pixels and a 3×5
  pixel font for the printing) and writes both recipes. Run it with `python3 make_arcade.py`.

What the kit made hard:

- `build-console/mei-asset-probe` was an empty file, so preview and verify ran with
  `--probe` pointing at a copy of a probe another agent had built in the shared scratchpad.
- A `loft` section may not have collinear points. An outline sampled evenly along a straight
  edge fails, so the controller's outline is a superellipse (no straight edges) blended into
  two grip circles. Its outline is traced along the contour and offset along the normals. In
  the end the shell is a `mesh` (quads split into triangles, since the rings are not coplanar),
  so the pink band could be its own material.
- `fit` gives each plane of an `extrude` or `box` the whole texture. Every textured surface
  (marquee, deck, kickplate, hood, rear, side panels, port and coin-door faces) is therefore a
  `mesh` node with `face_materials`.
- `flip: "u"` mirrors the logo along with the stripes, so the left side panel has its own cell.
- A sheet cell that falls outside the PNG is read as transparent, which makes it a cutout. The
  kit gave no error: the controller's face simply disappeared until the sheet was made taller.
