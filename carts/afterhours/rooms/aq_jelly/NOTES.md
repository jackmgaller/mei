# The jellyfish gallery (aquarium, room 2): dressing notes

R1's notes. The plan, the play file and the greybox are J's (`PLAN.md`, `make_aq_jelly.py`).

## Decided with J (2026-10-15)

1. **The four glass columns rise to 2.3 m** under a slim steel rim.
   - The plinths and lamps are opaque and 0.25 m tall; everything above is semi-transparent.
   - The glow is steady and baked; the runtime's wash shows the cycle.
2. **A proposal for A**, not needed: the columns' `lamp_K` and `water_K` materials made
   palette-backed and brightened with their bay's clock (`palette_lerp`), so the wave would run
   through the glass too.
3. **The stand-in** is made from the shell placement (`aj_room`, 116 triangles), under the
   700 cap.

## What the room is

A narrow, almost black gallery: slow, hypnotic, with a wave of colour running down it.

- **Four slender glass columns** of jellyfish stand down its middle. Each is round inside its
  1 m square, on a low black lacquered plinth with a round lamp set in its top.
  - The bays' hues, west to east: blue, violet, pink and pale aqua.
  - Each column's water is brightest over its lamp and fades up into the dark. A soft beam rises
    inside it.
  - Each holds four jellies: bells and trailing arms in the lamp's pale hue, adding light.
- **The floor** is polished black stone in 0.8 m slabs, with thin brass lines where one bay meets
  the next.
  - Each bay is painted in its lamp's hue at half strength, as PLAN.md says: brightest round its
    column, with a ring of light round the plinth and the column's reflection running toward the
    camera.
  - With the runtime's wash on, a bay reads lit; without it, dim. The ends beyond x ±6 are never
    lit.
- **Along the back** is a band of seven small wall tanks over a dark cabinet, in the wall tanks'
  footprint and cut at 1 m: moon jellies, seahorses, garden eels, upside-down jellies and
  anemones, each tank in its own pale water.
  - The back wall above is dark panelling with each bay's hue spilling faintly up it.
- **Beyond the doorways:** the great tank's blue to the west, the ocean gallery's lit cyan to the
  east.

## Files (mine)

| File | What |
|---|---|
| `dress_aq_jelly.py` | Writes `dressed/*.asset.json` and `dressed/art/*.png`; `--placements` also writes `aq_jelly.placements.json`. It imports `make_aq_jelly.py` for its numbers only. It is deterministic. It uses `../aq_hall/aqdress.py` |
| captures | `python3 carts/afterhours/rooms/aq_hall/capture.py aq_jelly [--verify]` (the hall's script serves both rooms) |

## Recipes and placements

| Placement | Recipe | Triangles | Collision | What |
|---|---|---|---|---|
| `aj_room` | `aj_room` | 116 | `aj_room_col` | The shell: painted floor (6 tiles), the front wall in section, the end walls with their doorways, the painted back wall, the wall tanks' band, the ways on |
| `aj_columns` | `aj_columns` | 992 | `none` | The four columns: plinths, lamps, glass, beams, water surfaces, rims, jellies |
| **room** | | **1,108** | | of 2,500 |

- **Lighting:** emissive, plus the kit's directional light alone. There are no point lights and
  no refinement.
- **The split** is the hall's reason: a stand-in from `aj_room`, 116 triangles.
- **Collision:** `aj_room_col` is J's greybox collision, renamed.
- **Asset Checker:** both recipes pass in depth mode.
- **Textures:** 108,816 bytes of VRAM (121,536 allocated), in slots 13-9 and 16-19.
  - The eight 8-bit paintings share 8-bit palette 27.
  - The four glass gradients, the section and the ripple take 4-bit palettes 26-31.

## Checks

- **World Checker:** the whole stage has 0 hard failures and 0 over thresholds (110 views). The
  game's views of the gallery: 889-896 triangles, 197,850-198,612 draw CPU and
  157,613-159,287 GPU cycles.
- **Scenario 85**, the ten legs as one run: DONE. Leg 2 (this room) clears in 814 ticks, as on
  the greybox.
- **`capture.py`** at the game's camera:
  - the room alone: 786-799 triangles drawn, 162,314-163,701 CPU and 325,498-326,610 GPU cycles;
  - with the stand-ins, fans and two washes: up to 1,140 triangles, 227,437 CPU and 424,080 GPU.

## Shots (`shots/`)

| File | What |
|---|---|
| `aq_jelly_wave*.png` | Bays 1 and 2 on (washes drawn), the end guard's fan clipped to them, the keeper on the back aisle, the thief waiting in the dark bay 0 |
| `aq_jelly_dark*.png` | Every lamp off: the four hues at half strength, the ends dark |
| `*_pan_x3.png` | Panned west, middle and east |
| `aq_jelly_level*.png` | The room in the built cart: scenario 85 frame 1800, HUD included |
| `numbers.json` | `capture.py`'s figures |

## Notes for later

- **No bench.** The play file gives it no footprint.
- **At 24 px a metre the jellies are bright dots** in their columns. Their colour and the glass
  carry the room more than their shapes do.
