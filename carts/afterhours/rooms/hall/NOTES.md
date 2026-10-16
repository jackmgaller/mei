# The lift hall (6F): dressing notes

1990, the bubble's lift lobby, and the back of house behind the securities house's glass.

**The lift lobby**, in front:

- cream marble slabs with veins, a green border with a brass line, and a brass medallion inlaid
  before the lifts;
- warm downlights, mirrored in the polish;
- three brass lift doors in polished granite (the core's face), with brass sills;
- a lit directory board that skips the ninth floor;
- the reception's marble counter with its lamp and visitors' book;
- an oxblood leather sofa against the front wall, the planter's ficus;
- **Kirisame Securities** (fictional) in gold leaf on the west glass screen, in Belleza. The
  screens have brass mullions every 1.5 m.

**The back of house**, behind the glass, half lit by tubes:

- grey-green vinyl tiles with mop arcs;
- the cleaners' stacked boxes, and their trolley (yellow bucket, bin bag, mop);
- pipes along the back wall, an alarm bell, an extinguisher, the cleaners' rota;
- the fire stair's doorway in the core's west face, its door wedged back with folded cardboard,
  under a green exit pictogram;
- the goods lift's padded car beyond the east doorway, in hard light;
- the trading floor's warm light beyond the west doorway.

**The core**, cut at 1 m, shows its plan in section: three lift shafts with the cars far below
(the middle one, his, a little lighter), the fire stair's flights behind them landing at the west
door, risers and a duct at the east end. The roof's motor room shows the same shafts' machines
over them. The ninth floor's builder may want the same plan (walled-up lift doors) for the core
to match.

## Files (mine)

| File | What |
|---|---|
| `dress_hall.py` | Writes `dressed/*.asset.json` and `dressed/art/*.png`; with `--placements`, `hall.placements.json`. Imports `make_hall.py` for its numbers only, and `../corridor/s2dress.py` (my shared shell and painting code) |
| `dressed/` | **The recipe folder for `levels/tower/make_tower.py`'s `ROOMS`**, in place of `rooms/hall/greybox` |

Captures: `python3 carts/afterhours/rooms/corridor/capture.py hall --verify` (the store's
capture, with the tower's rooms added).

## Signature props (once in the stage)

- **The brass lift doors and the directory with no ninth floor.**
- **The marble medallion.**
- **The securities house's gold name on glass.**
- **The reception counter and lamp.**
- **The leather sofa.**
- **The ficus in its planter** (a plant: the trading floor and ninth floor should not repeat it).
- **The cleaners' trolley and boxes.**
- **The wedged fire door.**

## Numbers

| Recipe | Triangles |
|---|---|
| `lh_room`, refinement included (cap 260) | 506 |
| `lh_glass`: the two screens and the gold name, unlit, collision `none` | 14 |
| **Room** (of 2,500) | **520** |

Collision: `lh_room_col` is the greybox's own, under a new name.

- **Asset Checker:** both recipes pass in depth mode.
- **Textures:** 155,712 bytes, in slots 16–22 (the room's set is 16–31).
- **Room alone at 60°, panned west / middle / east:**

  | Pan | Triangles | CPU cycles | GPU cycles |
  |---|---|---|---|
  | west | 284 | 60,181 | 267,832 |
  | middle | 287 | 60,465 | 267,690 |
  | east | 292 | 60,947 | 260,704 |

- **With the stand-ins and their cones:** up to 553 triangles, 112,233 CPU and 307,612 GPU
  cycles.
- **In the cart** (scenario 91, worst frame of each leg):

  | | Triangles | CPU cycles | GPU cycles |
  |---|---|---|---|
  | Leg 2 | 511 | 199,344 | 303,629 |
  | Leg 6 | 517 | 137,961 | 308,543 |
  | Greybox, both legs | 305 | — | 218,103 at most |

  Leg 2's 199,344 CPU cycles are the same in the greybox: they are the room's loading frame.

**Checks:**

- The World Checker passes.
- `levels/tower/solutions.py --check` clears all six legs.
- Scenarios 91 and 92 pass on a private build of the tower with the hall and the roof dressed.

## For the level lead

- **`ROOMS`:** `rooms/hall/dressed`. `hall.placements.json` names only `lh_room` and `lh_glass`.
  Until `ROOMS` changes, rerunning `make_tower.py` breaks the build.
- **The glass screens** are glass to the 1 m cut, with brass mullions 0.06 m wide and a 0.08 m
  base: nothing on them blocks sight. The gold name is on the lobby side of the west screen,
  between 0.42 and 0.72 m.
- **The fire stair's door:** its doorway is a 0.35 m recess in the core's west face
  (z 1.1 … 2.3). The cardboard wedge lies on the floor in front, x −5.3 … −5.04, z 1.15 … 1.4:
  low, and the thief walks over it.

## What fought me

- **Too dark behind the glass** at first. With the cleaners' tubes brighter and one more tube, the
  far half reads through the glass, as the plan intends.
- **Coplanar faces**: the sofa's seat met its arms, and the trolley's handle met its body.
