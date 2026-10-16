# Quarantine (room 4): dressing notes

## Questions for J, answered (2026-10-15)

- **Sharks**: none here is right (the tank tops own them).
- **The ultraviolet tubes glowing steadily** on both rows is fine. J asks A about switching them
  with their lights later; the floor's two violet boxes are painted at half strength so that the
  runtime's wash shows which is on.
- **AGENTS.md's Generators table** (the three dress scripts, `aqdress.py`, `capture.py`): J passes
  it to the coordinator.

## What it is

The keepers' quarantine behind the public galleries: dark, clinical and violet.

- **Tank rows.** Two rows of five holding tanks on steel stands, bare-bottomed, with violet water.
  Their occupants glow faintly under the ultraviolet:
  - a sick ray with pale patches;
  - a moray in a length of pipe;
  - an octopus under a lid that is weighted shut;
  - a pufferfish, a horseshoe crab and three sea stars;
  - two small shoals;
  - one tank drained for cleaning, with its hose.
- **Tank details.** Each tank has a white card on its glass (a coloured band, an outline and
  dose dots). White tubs with coloured tape sit on the stands' lower shelves.
- **The ultraviolet sterilisers.** One runs along the back of each row, its tube glowing violet.
- **Filter cabinets** stand at the rows' east ends, with louvres, status lamps, a dial and a
  return pipe into the last tank.
- **The keeper's desk** in the front corner holds a log book, a clipboard, a microscope, a rack
  of sample tubes, a thermos and a desk lamp that is off. A stool is tucked under it.
- **The floor** is dark sealed concrete:
  - drain gutters run along the rows, at z 1.0 and −1.8, where the violet boxes meet and begin;
  - there are wet patches, a round drain and a disinfectant footbath at the way in.
- **The back wall** is white tile in the dark. It carries a whiteboard with the ten tanks as
  pictograms and ticks, a clock, the hygiene pictograms by the door, a hose reel and the green
  emergency sign by the stair.
- **The stair door** has a caged bulkhead lamp, the room's only steady light. Beyond it a flight
  of steps goes down toward the plant, darkening as it descends. Beyond the west door is the dim
  staff passage from the ocean gallery.

**What looks lit is lit.** The floor is bright only in the play file's three light boxes:

- `uv_a` and `uv_b` are violet at half strength, their corners rounded inside the boxes, with a
  faint water net beside the tanks;
- `exit` is the stair lamp at full strength.

The rest of the floor is dark. The footbath is a dark tray, not a glow.

Every footprint, wall and doorway is the play file's: the rows, the cabinets and the desk sit
inside their boxes. Everything in play is cut at 1 m.

## Recipes and placements (`dressed/`, `aq_quar.placements.json`)

| Recipe | Triangles | What | Collision |
|---|---|---|---|
| `qt_room` | 142 | the shell: the painted floor in 4 tiles, the walls with their doorways, the front's section, the ways on, the stair lamp | `qt_room_col` |
| `qt_props` | 900 | the stands, the tubs, the rims, the tanks' cards, the sterilisers, the cabinets, the desk | `none` |
| `qt_tanks` | 418 | the glass (quarter blend), the water (quarter, a violet ripple), the bottoms, the occupants | `none` |
| **room** | **1,460** | of 2,500 | |
| `qt_room_col` | | the greybox's companion, made the same way (`aqroom.shell_nodes(collision=True)`) | |

The shell and the furniture are separate recipes so that the shell (with the tanks, 560 in all)
fits the kit's 700-triangle stand-in cap. All three pass the Asset Checker in depth mode.

**Textures:** 181,799 bytes of VRAM (185,440 on the grid), in 7 of the region's 9 slots. The
paintings share one 8-bit palette.

## How it is made

- **Dressing.** `python3 carts/afterhours/rooms/aq_quar/dress_aq_quar.py` writes the recipes,
  `dressed/art/` and the placements (`--no-placements` leaves the placements alone). It reads
  `make_aq_quar.py`'s `ROOM` for every number and is rerunnable: it writes only what changed.
- **Shared helpers.** `aqdress.py` holds what the three rooms share:
  - the collision companion;
  - a floor in cells at two heights, with hand UVs (the plant's);
  - flights of steps beyond an end wall's doorway;
  - painting a light box into a floor;
  - one 8-bit palette per room.

  It builds on `../corridor/s2dress.py` and `../passage/diorama.py`, which are imported, not
  changed.
- **Captures.** `python3 carts/afterhours/rooms/aq_quar/capture.py aq_quar|aq_plant|aq_kitchen
  --build-dir build-ah-R3 [--verify]` draws the room at the game's camera. It is
  `../corridor/capture.py` adapted:
  - it handles the three rooms;
  - in a dark room it draws each light state with the runtime's additive wash over the lights
    that are on.

## Checks

- **Asset Checker.** `tools/mei_assets.py verify` passes for `qt_room`, `qt_props` and
  `qt_tanks`, in depth mode.
- **World Checker.** `make_aquarium.py`, then `make B=build-ah-R3
  build-ah-R3/carts/afterhours.mei`:
  - the aquarium world reports 110 views, 0 hard failures, 0 over thresholds;
  - this cell is 1,460 triangles with a 560-triangle stand-in;
  - its game view draws 807 triangles at 155,213 GPU cycles.
- **Capture costs** (`shots/numbers.json`, at the game's camera):

  | Frame | Triangles drawn | CPU cycles | GPU cycles |
  |---|---|---|---|
  | The room alone | 689 | 162,733 | 317,697 |
  | With the thief, the keeper and two cones | 857–859 | about 198,400 | 397,019–411,767 |

## Shots (`shots/`)

| File | What |
|---|---|
| `aq_quar_60_uv_a.png`, `_x3` | The back row's light on (with the stair lamp, both washed as the runtime does), the thief by the back row's west end and the keeper on the front aisle |
| `aq_quar_60_uv_b.png`, `_x3` | The front row's light on |
| `aq_quar_60_room_x3.png` | The room alone, no washes |

The stand-in cones are drawn whole. The game clips the camera's cone to the lit boxes.

## What fought me

- **The glass.** In half blend the tanks were solid violet slabs. In quarter blend, with dark
  rims, the animals show.
- **Flush faces:**
  - the thermos stood on the desk at the desk top's height;
  - the ray's pale patches lay in its body's plane, so they are 12 mm above it now.
