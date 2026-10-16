# The entrance hall (aquarium, room 0): dressing notes

R1's notes. The plan, the play file and the greybox are J's (`PLAN.md`, `make_aq_hall.py`).

## Decided with J (2026-10-15)

1. **The welcome tank rises through both floors as glass:** `shots/aq_hall_tank_compare.png`,
   the left version.
   - Semi-transparent from its plinth to the mezzanine, then a faint glass parapet to 1 m over
     the deck. Nothing opaque stands over 1 m on the floor, and the glass hides nothing on either
     level's routes.
   - `AH_TANK_CUT=1` (or `TANK_CUT` in `dress_aq_hall.py`) still cuts it at 1 m, for comparison.
2. **The stand-ins:** each of my cells is two placements, the shell first (`ah_room`, 246
   triangles). The kit's stand-in is made from the shell under the 700 cap, and the World Checker
   reports no `standin_missing`. Raising the cap is not needed for this room.
3. **Open:** is a deck of timber slats right for "slatted or grated where it overhangs"?
   - The whole mezzanine is slats with 8 cm gaps, about 40% open, so a thief under it shows
     through.
   - At the game's camera, a thief on the floor loses his head behind the deck's edge from
     z ≈ 2.15 and is fully behind it from z ≈ 3.15.

## What the room is

The front of house after closing: hushed, dark, lit only by the welcome tank.

- **The welcome tank** is a cylinder of sea (r 1.36, round inside its box) on a black granite
  plinth that fills the box.
  - A sardine school turns inside it, with a few gold and blue fish, rock and coral on its floor,
    and light falling through the water.
  - Its open top in the mezzanine is ringed in steel and glass.
- **The floor** is polished black granite in 1.2 m slabs, with a brass ring set round the tank.
  - The tank's blue lies on it, netted with caustics, exactly in the play file's three tank boxes
    and down to the front wall.
  - The great tank's blue comes in through the east door, in its box.
  - Everything else is dark: it is painted at the room's ambient only.
- **The main doors** are on the west wall, with an entrance mat inside and the street beyond.
- **The ticket gates** are three cabinets with red stop lamps, closed flaps between them and a low
  glass screen running on to the back wall.
- **The information desk** has a lit map of the building (shapes, no words) and leaflet racks.
- **Two pillars**, cut at 1 m, carry lit fish posters: a moon jelly, and a sunfish among
  sardines.
- **The restaurant's mezzanine** (+3.2 m):
  - a deck of timber slats, with the floor showing through the gaps;
  - a glass railing with steel posts and a handrail at 1 m;
  - two small tables laid with white cloths in each table footprint, a chair tucked behind each;
  - two plum velvet booths (the hiding places), their backs cut at 1 m;
  - on the back wall, dark panelling under a long window on the night bay: the far shore's
    towers, lit windows, red beacons, light streaking the water.
- **Beyond the doorways:** the street (west, floor), the great tank's blue (east, floor), the
  catwalk (east, upper) and the pedestrian deck (west, upper).

## Files (mine)

| File | What |
|---|---|
| `dress_aq_hall.py` | Writes `dressed/*.asset.json` and `dressed/art/*.png`; `--placements` also writes `aq_hall.placements.json`. It imports `make_aq_hall.py` for its numbers only. It is deterministic: a rerun writes nothing |
| `aqdress.py` | Shared with `../aq_jelly/dress_aq_jelly.py`: the shell on one or two levels (walls as grid meshes with every level's doorways, the section, the floor tiles, the ways on), the light boxes painted as masks, and one shared 8-bit palette a room (`quantise_together`). It builds on `../arrival/dresskit.py`, and on J's `aqroom.shell_nodes()` for the collision companion |
| `capture.py` | `python3 carts/afterhours/rooms/aq_hall/capture.py aq_hall\|aq_jelly [--verify] [--build-dir build-ah-R1]`. Adapted from `rooms/corridor/capture.py` for dark rooms and two levels: the framing takes the walkway's back edge, the runtime's wash is drawn over the lights that are on, and dark-eyed fans are clipped to the lights |
| `dressed/` | The recipes. `make_aquarium.py` already lists `rooms/aq_hall/*` |

## Recipes and placements

| Placement | Recipe | Triangles | Collision | What |
|---|---|---|---|---|
| `ah_room` | `ah_room` | 246 | `ah_room_col` | The shell: painted floor (8 tiles), the front wall in section, the end walls with both levels' doorways, the back wall (the window over the deck), the ways on, the mezzanine's slatted deck, the coping round the tank top and the fascia |
| `ah_props` | `ah_props` | 1,134 | `none` | The tank, gates, desk, pillars, railing, tables and booths, lit by four point lights (tank, tank top, great tank door, street) with refinement capped at 200 |
| **room** | | **1,380** | | of 2,500 |

- **The split** lets the World Kit make the cell's stand-in from `ah_room` alone (246 triangles,
  cap 700). One placement over 700 triangles would leave the cell without a stand-in: the
  World Checker's `standin_missing`.
- **Collision:** `ah_room_col` is J's greybox collision (`aqroom.shell_nodes(collision=True)`),
  renamed.
- **Asset Checker:** both recipes pass in depth mode.
- **Textures:** 131,443 bytes of VRAM (147,584 allocated), in the region's slots 13-9 and 16-19.
  They take one 8-bit palette (31) and 4-bit palettes 3-6. Slot 7 and palettes 250-251 are not
  used.

## Checks

- **World Checker:** `python3 carts/afterhours/levels/aquarium/make_aquarium.py`, then
  `make B=build-ah-R1 build-ah-R1/carts/afterhours.mei`.
  - The whole stage, every room as its builder has it: 110 views, 0 hard failures, 0 over
    thresholds.
  - The game's views of the hall: 1,078-1,092 triangles, 227,701-229,004 draw CPU and
    180,976-183,724 GPU cycles.
- **Scenario 85**, J's ten legs as one run, played on this build: DONE, 32 checks, 8,693 ticks.
  - Its worst frame is in leg 2, the great tank: 781,868 CPU cycles as a release build. With my
    two rooms back on their greyboxes the same frame is 776,779 cycles, so the frame is not this
    room's.
- **`capture.py`**, the room alone at the game's camera (pans west, middle, east):
  - 932-950 triangles drawn, 187,576-189,303 CPU and 378,987-381,121 GPU cycles;
  - with the stand-ins, fans and washes: up to 1,137 triangles, 226,745 CPU and 441,438 GPU.

## Shots (`shots/`)

| File | What |
|---|---|
| `aq_hall_floor*.png` | Leg 0 at the game's camera (`capture.py`): the thief waits at the front wall, and the desk guard's fan shows only where the tank's light is |
| `aq_hall_mezz*.png` | Leg 9: the torch guard walking west on the mezzanine, the camera's fan clipped to the tank top's light, the thief at the east booth |
| `*_pan_x3.png` | The same panned west, middle and east |
| `aq_hall_level_floor*.png`, `aq_hall_level_mezz*.png` | The room in the built cart: scenario 85 frames 300 and 8100 (`SHOT=1 SEQ=50`), HUD included |
| `aq_hall_tank_compare.png` | The tank rising (left) and cut at 1 m (right) |
| `numbers.json` | `capture.py`'s figures |

## Notes for later

- **Footprints, light boxes and the mezzanine** are where the play file has them.
  - The lit floor is exactly the play file's boxes (`lit_mask()`), their edges softened over
    7 cm and the outer corners a little round.
  - The deck's lit patch is the `tank_top` box. Under the mezzanine's front edge the floor is a
    little darker, where the tank boxes stop.
- **The tank's top on the mezzanine is round inside the play file's water box.** A steel-coloured
  coping fills the box's corners, so they read as not deck.
- **What is drawn beyond the doorways** is mostly off the picture at the game's framing: the
  camera pans only ±1.65 m.
- **The back wall above the deck** shows about 1.3 m in the picture. Only the window's lower
  part reads: the far shore and its lights.
- **No shop shutter or ticket windows.** The play file gives them no footprint, and the end walls
  are seen almost edge on.
