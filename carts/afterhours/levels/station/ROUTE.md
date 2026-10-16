# Stage 1, the station: the route

After Hours' first stage, and its gentlest: one place, the station (DESIGN.md, "The premise":
each stage is one property to assess). The assessor gets off the last train three floors down and
goes up through the station to the street: the platform, the ticket gates, the passage. One new
idea a room, no tools, slow watchers. The rooms are level 1's first three, dressed, with the same
puzzles and tapes; what changed is where the passage leads (below). The rooms' floor plans for
their builders are each room's `PLAN.md`.

## The route and the curve

| # | Room | Folder | Teaches | Watchers | Floor | Size (m) | Model ticks |
|---|---|---|---|---|---|---|---|
| 1 | **The last train**: the end of a side platform | `rooms/arrival/` | What a cone is, and timing one | One posted guard by the stair, looking up the platform 4 s, then at the timetable | B3, y −16 | 13.5 × 8.25 | 384 |
| 2 | **The ticket gates** and the station office | `rooms/gates/` | Hiding | One patrol guard: out of the office, through the gates, a look at the lockers, back | B2, y −11 | 13.5 × 9 | 1,507 |
| 3 | **The passage** under the street, shutters down | `rooms/passage/` | Pillars cast sight shadows | One camera at the far end sweeping the whole length | B1, y −6 | 22.5 × 7.3 (pans) | 936 |

The stage is 2,830 ticks on the model (2,835 in the cart: 47 s) played perfectly. Room 1 is one
wait; room 2 adds the A button; room 3 is two waits, the second in a shadow. Every watcher walks
at 0.8–0.9 m/s, sees 4.5–5.5 m and turns at 180° a second.

**What the split changed.** The passage's way out, in the east wall at the front, was the stair up
to the tower's lobby. It is now **the station's own exit: its stairs up to the street** (the exit
pictogram over it, the street's light coming down), so the stage ends inside the station. Nothing
moved: the exit box, the camera and the tape are as they were; the passage's builder redresses what
is seen beyond the doorway (`rooms/passage/PLAN.md`, "Stage change"). The station ending in its own
street stair also gives the stage a clean end line: the assessor out in the night air.

**Why not a fourth room.** The station is the introduction; three rooms of one idea each are what
the owner liked about level 1's start. The tower (stage 2) steps up from here.

## How it sits in the World Kit

One world, `station` (`levels/station/station.world.json`, written by `make_station.py` through
`levels/assemble.py`): each room in its own 32 m cell side by side along x in the order played, at
its floor's height; one region per room; kit-made stand-ins (609–695 triangles); the rooms
chained by `next`, the first marked `first`, the last with no `next` (its exit ends the stage).
Texture slot 7 and 4-bit palettes 250–251 are left to the front end's fonts. World Checker: 3
cells, 0 warnings, 0 hard failures and 0 over thresholds in 53 views; cells 695, 652 and 855
triangles.

## Commands

```sh
python3 carts/afterhours/levels/station/make_station.py      # the stage's world
python3 carts/afterhours/levels/station/solutions.py         # the plans, played; tests/tapes/station_solution.akr
python3 carts/afterhours/levels/station/solutions.py --check --pictures /tmp/station
make B=build-mine build-mine/carts/afterhours.mei            # the worlds (World Checker) and the cart
```

The rooms' scripts (`rooms/arrival/make_arrival.py` and the others) write each room's play file
and greybox; rerunning one never overwrites its builder's placements.
