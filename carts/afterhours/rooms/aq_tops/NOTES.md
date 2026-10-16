# The tank tops, dressed (R2)

No questions for J: every wall, doorway, water edge, housing and light box is where
`make_aq_tops.py` puts them.

## What it is

The floor over the big tanks, where the public never goes: wet concrete walkways between two
sheets of black water, under a dark roof that the section cuts away.

- **Walkways:**
  - Wet concrete slab bays with dark wet patches, a drain channel along the back and yellow
    edge lines a hand in from every water edge.
  - A hose snaking along the back walkway, buckets by the housings and a mat at the kitchen
    door.
  - The four lamps' warm pools are painted exactly over the light boxes. The puddles catch the
    light only inside them.
- **The shark tank (west):**
  - Near-black water, a half-blended surface with fine ripples, the lamps' glints and wakes.
  - Three sharks just under the surface, their pale dorsal fins out of it.
  - A keeper's skiff tied up in the north-west corner.
  - The grated bridge, railed both sides. Its lamp is on a cycle, so its patch is painted at half
    strength.
- **The turtle pool (east):** shallower and greener. A haul-out rock with a turtle on it,
  another swimming.
- **Life-support housings:** louvred, cut at 1 m with the pump's motor showing, each with a
  standpipe into its tank.
- **Lamps:** clamp lamps on posts at the tanks' edges (the middle, the bridge and the front
  walkway), at 0.87–1.0 m, and a bracket lamp on the back wall over the back walkway.
- **The back wall (2.4 m):** grimy white glazed tile to 1.2 m, concrete above, a water main
  with red valves, nets on poles, hoses on hooks, a rack of poles, and the back lamp's glow.
- **Beyond the doors:** the kitchen's lit landing (east), and four steps down to the great
  tank's catwalk (west).

## Recipes and placements (`aq_tops.placements.json`)

| Placement | Recipe | Triangles | Textures (stored / allocated) | Collision |
|---|---|---|---|---|
| `at_room` | `dressed/at_room.asset.json` (walkways and tank walls, shell, bridge and rails, housings, pipes, lamps, skiff) | 308 | 78,524 / 86,144 B | `at_room_col` |
| `at_water` | `dressed/at_water.asset.json` (depths, surfaces, sharks, turtles, rock) | 144 | 30,368 / 33,472 B | none |
| | `dressed/at_room_col.asset.json`: `aqroom.shell_nodes(collision=True)` from `make_aq_tops.ROOM`, the same as the greybox's `at_shell_col` | | | |
| **Room** | | **452** of 2,500 | **108,892 / 119,616 B** of about 280 KB | |

- Both recipes pass the Asset Checker in depth mode.
- Textures are in slots `2-0,25-31`; no slot 7 and no palettes 250-251.
- No fonts and no words.
- Signature props: the sharks and the turtles.
- The water's surface is 0.25 m below the walkways; the tanks' walls go down to −1.3 m.

## How it is made

- `dress_aq_tops.py` writes `dressed/`, `dressed/art/` and the placements. It is rerunnable and
  uses the great tank's helpers (`../aq_great/dress_aq_great.py`).
- `capture.py` runs `../aq_great/capture.py` for this room. The room is 9.5 m deep, so there is
  no z pan; it pans 2.65 m either way in x.

## World Checker

- **The aquarium world:** 0 hard failures, 2 over thresholds. Both are `standin_missing` in R1's
  rooms, cells (0, 0) and (2, 0); see `../aq_great/NOTES.md`.
- **This cell (7, 0):** 2 placements, 452 triangles, a stand-in of 452.
- **The game's vantage points:** 260–361 triangles, 64,413–81,218 draw-CPU cycles and
  132,391–138,777 GPU cycles.

## Shots (`shots/`)

| File | What |
|---|---|
| `aq_tops_tops_60.png`, `_x3`, `_pan_x3` | Leg 7. The thief in the middle walkway's lamp, the keeper with his torch on the west walk |
| `numbers.json` | Costs per view |

The middle pan with stand-ins draws 458 triangles, 98,806 CPU cycles and 380,175 GPU cycles.

## Not done

- No roof trusses: they would be above the section's cut.
- The hung work lamps are drawn as clamp lamps on posts at the cut height, for the same reason.
- The skiff is mostly under the keeper's cone in the capture.
