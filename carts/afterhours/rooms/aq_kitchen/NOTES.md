# The fish kitchen (room 6): dressing notes

## Questions for J, answered (2026-10-15)

- **The buckets** are the runtime's fragile things, drawn by A (today as stage 2's gift boxes);
  J asks A for a bucket-of-fish mesh for this stage. The floor under each stays plain with a wet
  ring of its radius (0.35 m), and no decorative bucket stands on the floor.
- **The freezer's doorway**: a strip curtain, no door leaf (a leaf swung out would stand in the
  cook's round). Right as it is.
- **The camera over the back door** is gone from the play file; the dressing does not depend on it.

## What it is

Where the keepers make the animals' food: the brightest room in the building, cold steel and pale
tile under fluorescent tubes.

The floor's brightness is held a little below white so that the pale yellow cones still read on
it.

- **The prep island.** Two stainless tables carry:
  - a blue tray heaped with silver capelin and a white board with two mackerel;
  - a green board and a tray of squid;
  - a block of krill thawing pink, a mackerel on a board with a knife;
  - a bowl of chopped fish, a scale with its green display, a stack of trays.

  Boxes of fish (styrofoam with blue lids, cartons with fish pictograms) sit on the shelves under
  the tables.
- **The sinks.** Three basins with taps run along the back wall, with cupboards under them. Above
  them are a tube light and a knife rack. Three blue rubber aprons hang on hooks.
- **The walk-in freezer.** It is cut by the section, so its insulated white walls show in section
  and its frosted floor shows inside. Inside are steel shelves of boxes, blocks of frozen fish
  and a thick doorway frame with a strip curtain.
- **The live feed tank.** Shrimp swarm in blue-lit water, with an airstone's stream and the
  tank's lamp. The blue spills round the tank's stand.
- **The steel rack** on the east wall holds styrofoam boxes and cartons.
- **The floor** is pale non-slip tile. A stainless gutter runs along the sinks, there are two
  floor drains, and wet patches round the island, the sinks and the freezer.
- **The back wall** is white tile to 1.6 m. It carries the feeding chart (four animals by
  pictogram, a week of ticks and a missed dose in red), a clock, the hand-wash pictogram and the
  green sign over the back door.
- **Beyond the doors:**
  - the west door: the service stair going down to the plant;
  - the back door: a landing and two steps up into the dark blue of the tank tops.

Every footprint is the play file's:

- the island, the sinks, the freezer (cut at 1 m), the feed tank and the rack (cut at 1 m) are in
  their boxes;
- the hiding place is clear;
- the buckets' places are clear.

## Recipes and placements (`dressed/`, `aq_kitchen.placements.json`)

| Recipe | Triangles | What | Collision |
|---|---|---|---|
| `ak_room` | 240 | The shell: the painted floor in 4 tiles, the walls, the section, the stairs and the landing beyond, the aprons | `ak_room_col` |
| `ak_props` | 794 | The island and what is on and under it, the sinks, the freezer and its contents, the feed tank's stand, the rack and its stock | `none` |
| `ak_glass` | 12 | The strip curtain (a half-blend cutout), the feed tank's glass and water | `none` |
| **room** | **1,046** | of 2,500 | |
| `ak_room_col` | | The greybox's companion | |

All three recipes pass the Asset Checker in depth mode.

**Textures:** 199,119 bytes of VRAM (205,248 on the grid), in the region's 9 slots. The paintings
share one 8-bit palette.

## How it is made

- `python3 carts/afterhours/rooms/aq_kitchen/dress_aq_kitchen.py` writes the recipes,
  `dressed/art/` and the placements (`--no-placements` leaves the placements alone). It is
  rerunnable, reads `make_aq_kitchen.py`'s `ROOM`, and imports `../aq_quar/aqdress.py`.
- Captures: `python3 carts/afterhours/rooms/aq_quar/capture.py aq_kitchen --build-dir build-ah-R3`.

## Checks

- **World Checker.** It reports 0 hard failures and 0 over thresholds. This cell is 1,046
  triangles with a 252-triangle stand-in. Its game view draws 987 triangles at 168,077 GPU cycles.
- **Capture costs:**

  | Frame | Triangles drawn | CPU cycles | GPU cycles |
  |---|---|---|---|
  | The room alone | 587 | 120,500 | 289,989 |
  | With the thief in the hiding place and the cook | 735 | 150,977 | 312,599 |

## Shots (`shots/`)

| File | What |
|---|---|
| `aq_kitchen_60.png`, `_x3` | The thief in the freezer's doorway, the cook below the island looking east |
| `aq_kitchen_60_room_x3.png` | The room alone |

## What fought me

- **The capelin.** Laid out in rows, they read as lines of text at 24 px a metre, so they are a
  heaped tray now.
- **The floor's brightness.** At its brightest the cones no longer showed on it.
- **Flush faces:** the rack's posts against its shelves, stacked stock, the taps and their spouts,
  and the airstone on the tank's floor.
