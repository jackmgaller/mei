# Level 1: the route

After Hours' first level: five rooms from the last train, three floors underground, up to the
aquarium on a tower's roof. One new idea a room, no tools, gentle watchers early. Every room is
dressed and plays; each has a solution tape that clears it in the cart. The level is built from
the dressed rooms: `rooms/arrival/dressed`, `rooms/gates/dressed`, `rooms/passage`,
`rooms/lobby` and `rooms/aquarium` (the builders' placements and recipes). The rooms' floor
plans for their builders are each room's `PLAN.md`.

## The route and the curve

| # | Room | Folder | Teaches | Watchers | Floor | Size (m) | The tape clears it in |
|---|---|---|---|---|---|---|---|
| 1 | **The last train**: the end of a side platform | `rooms/arrival/` | What a cone is, and timing one | One posted guard by the stair, looking up the platform 4 s, then at the timetable | B3, y −16 | 13.5 × 8.25 | 6.4 s |
| 2 | **The ticket gates** and the station office | `rooms/gates/` | Hiding | One patrol guard: out of the office, through the gates, a look at the lockers, back | B2, y −11 | 13.5 × 9 | 25 s |
| 3 | **The passage** under the street, shutters down | `rooms/passage/` | Pillars cast sight shadows | One camera at the far end sweeping the whole length | B1, y −6 | 22.5 × 7.3 (pans) | 15.6 s |
| 4 | **The lobby** of the tower, a stopped escalator up | `rooms/lobby/` | Two routes crossing | Two patrols: one along the back before the escalator, one up and down the west side | ground, y 0 | 14.5 × 10 | 19.7 s |
| 5 | **The aquarium** on the roof | `rooms/aquarium/` (its builder's) | Glass: cones pass it, you don't; and the four before | A watchman at the window (the fish, then the room), a keeper round the coral cube | roof, y 40 | 12.1 × 8 | 12.8 s |

How the curve goes up: room 1 is one wait; room 2 adds the A button (hide, wait, go); room 3 is
two waits, the second in a shadow; room 4 is two waits on two guards who move independently;
room 5 is two waits on two guards, with glass that does not hide you and a pillar that does.
The difficulty rises by how many things move at once, not by harder watchers: all of level 1's
walk at 0.8–0.9 m/s, see 4.5–5.5 m and turn their heads at 180° a second (the Gate 1 platform's
walk 1.0–1.2 m/s, see 6 m and turn at 240°). Every room starts its thief out of every cone.

**Why these five** (DESIGN.md's proposal, kept): they go up through the complex in real space,
station to street to roof, each is a place worth dressing, and each carries one idea. Changes
from the proposal: room 1 is a side platform, not Gate 1's island one (a single track at the
back, so the departing train is scenery, not a puzzle); room 4's two guards walk lines that cross
(rather than two loops), which reads better at 60°; the aquarium keeps its sketch's plan with two
changes (`rooms/aquarium/PLAN.md`).

**Gate 1's hard platform** stays a world of its own, `platform` (`rooms/platform/`), for a later
level: the same station on the way home, with its tools. Its tapes are re-recorded for the new
rules.

## How the rooms join (the World Kit)

**One world for the level** (`level1.world.json`, written by `make_level1.py`):

- The reader keeps one pack open (`wp_pack`), so a level is one world: the next room is already
  open when the thief goes through a door, and for the pull-back (Gate 2) the neighbouring rooms
  are in the same pack.
- **Each room in its own 32 m cell**, side by side along x in the order they are played (room k
  at x from 32k), each at its floor's height: the section through the complex unfolded, rising
  left to right. A cell holds one room only, so drawing a room draws nothing of its neighbours
  (32 m away, off the screen); the pull-back can draw them by moving the camera back.
- **One region per room**, so a room's textures and palettes load with it (the aquarium's
  61 KB of textures are its own).
- **Stand-ins** made by the kit from each room (`standins`, at most 700 triangles a cell, 800 for the aquarium; 609–695 today) for the
  pull-back.
- **Rooms in their own frame**: each room's files are written around the middle of its own floor;
  `make_level1.py` only moves them. A room is three files: `NAME.placements.json` (what is drawn;
  the builder's), `NAME.play.json` (what is played: entities and the wall map; the level lead's),
  and its recipes.
- **Order**: the room entities are chained by `next`, the first is marked `first`. The runtime
  (agent A's `dr_world.akr`) loads room k from the entities inside its box.
- The World Checker runs on every build, with the game's camera over each room as vantage points.
  Today: 5 cells, 1,004,696 bytes, 0 warnings, 0 hard failures, 0 over thresholds in 81 views
  (cell budget 2,500 triangles; cells 652–1,657; peak view 1,310).

What a room builder must not break is in each `PLAN.md`; the short form: keep everything listed
under "Must stay" where it is (the wall map is written from those numbers), keep the 1 m cut,
stay within the triangle budget, and the room's solution tape must still clear.

## Commands

```sh
python3 carts/dorobo/rooms/arrival/make_arrival.py          # each room's play file and greybox (and gates, passage, lobby);
                                                            # the greybox placements go to greybox/, the builder's are kept
python3 carts/dorobo/levels/level1/aquarium/make_aquarium_play.py
python3 carts/dorobo/levels/level1/make_level1.py           # the level's world
python3 carts/dorobo/levels/level1/solutions.py             # the rooms' plans, played; the tapes
python3 carts/dorobo/levels/level1/solutions.py --check --pictures /tmp/l1   # a room's plan from above
make B=build-mine build-mine/carts/dorobo.mei               # builds the world (World Checker) and the cart
```
