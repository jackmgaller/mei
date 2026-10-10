# 13 Sakura Pastel

A Japan-only spring colour run: a soft, pillowy box in two pinks (a deeper sakura lower shell, a
pale blush lid) with a mint seam set in a groove, mint trim and a cream foot. The lid carries a
tone-on-tone petal print and a few printed blossoms drifting across it; the power button is a
mint five-petal sakura with a rose centre, and reset is a round rose button. The 明 MEI badge (日
orange, 月 pale blue, white MEI, "SAKURA" under it) sits front left. A white cart stands in the
mint slot housing, its label a sakura branch under the sun and the moon ("HARU MEI"). Front:
controller ports 1 and 2, memory card slots 1 and 2 at the ends, a pink power lamp and a blue
MeiNet lamp, a cream さくら plate. Back: DC in, AV out, ANT in. The controller matches it:
sakura-pink top with the same petal print, cream underside, cream d-pad and mint stick on mint
plates, pastel A B X Y (rose, lemon, sky, mint) with their letters, cream Start and Select, a 明
badge, curved mint L and R bumpers along the shoulder edge, and a mint blossom on the right grip.

| Model | Triangles | Vertices | Textures |
|---|---|---|---|
| `console.asset.json` | 1,158 | 656 | 7,663 bytes VRAM, 2 windows, 0 split faces |
| `controller.asset.json` | 794 | 441 | 1,726 bytes VRAM, 1 window |

Both pass `verify` (depth mode, required by the recipes): 0 failures; the allowed findings are
surface intersections and T-junctions where parts are sunk into the shells.

**Scale:** real metres, no scale-up needed. Console 0.272 × 0.133 (to the cart's top) ×
0.225 m; controller 0.147 × 0.042 (to the stick's top) × 0.112 m. Both face −Z.

**Files:** `make_art.py` draws `art/sakura_sheet.png` (Pillow, macOS Hiragino and Arial Rounded);
`make_recipes.py` writes both recipes. `preview_*_cameras.png` are extra close views at world
scale (two columns: hero and front, high and rear, two close-ups; controller: hero, top, front,
back).

**What the kit made hard:**

- A loft's caps are both on or both off, so stacked shells bury caps inside each other and one
  material covers every band. The bodies are written instead as one explicit mesh from the loft
  sections (`loft_mesh`): a material per band (foot, shell, mint groove, lid), only the bottom
  and the printed top as caps. Inset sections make the side quads non-planar, so they go in as
  triangles.
- No booleans: sockets, card slots and the cart mouth are printed faces on plates standing 1–3
  mm proud, with plain sides through `face_materials`.
- The blossom prints are cutout quads 1.2 mm above the lid (they report `open_surface`, which
  is intended); a slab would show its rectangular sides around the petals.
- 明 at 19 texels: in the bold weight the 日 and 月 strokes touch, so the art splits the halves on
  a thin weight's connected strokes and colours each bold texel by its nearest thin one.
- Pastels turn grey on walls the light misses; ambient 0.62 and a more frontal light keep them
  pastel.
- At the start `build-console/mei-asset-probe` was an empty file, so the work used a private
  copy compiled from `tools/assetkit_probe.c`; the final `verify` runs used build-console's own
  probe, rebuilt by then.
