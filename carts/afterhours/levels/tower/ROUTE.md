# Stage 2, the tower: the route

After Hours' second stage: one place, an office tower of the bubble (DESIGN.md, "The premise"),
played as a stage of doors (the store's rules, `levels/store/ROUTE.md`, without keycards). Its
lobby on the street; the lift hall on the sixth floor round the building's core; the securities
house's trading floor beside it; the ninth floor the directory leaves out (the chairman's,
undeclared: the assessor's find); and the roof with the chairman's helipad. The lobby is level
1's room, dressed, with its puzzle and plan unchanged; the other four rooms are new and dressed
(each room's `NOTES.md`).
The owner approved the layout sheet (`sketch.png`, `sketch.py`) on 2026-10-15, after a first
sheet (four rooms in a line) came back "richer first". The rooms' floor plans for their builders
are each room's `PLAN.md`.

## The building

One core of lifts and stairs stands in the same place on every floor (x -5 ... 3 in the rooms'
frames): the lifts on its south face, the fire stair in its west face, the lift motor room and
the stair house on the roof. The lifts skip the ninth floor and the core's doors there are
walled up. The ways onto the ninth are the securities house's own service stair, from the back
office behind the trading floor, and the chairman's private stair from his helipad. The fire
stair's doors are locked from the stair on every floor but the sixth, where the cleaners wedge
one open; from the sixth the goods lift goes down to the loading bay.

## The route and the curve

| Leg | Room | In by → out by | What it asks | Watchers | Model ticks |
|---|---|---|---|---|---|
| 0 | **The lobby** (1F, `rooms/lobby/`) | the street → the escalator to the lifts | two routes crossing | two patrols | 1,181 |
| 1 | **The lift hall** (6F, `rooms/hall/`), the lift lobby | the lifts → the trading floor | behind a planter, then behind the night guard | the night guard; the cleaner behind the glass | 725 |
| 2 | **The trading floor** (6F, `rooms/trading/`) | the lift hall → the service stair | round the glass meeting room behind the floor guard; a camera across the back office | floor guard, office camera | 1,208 |
| 3 | **The ninth floor** (9F, `rooms/ninth/`) | the service stair → the private stair | hide in the coat cupboard; the glass boardroom hides nothing; a camera on the stair door | guard round the boardroom, office camera | 1,310 |
| 4 | **The roof** (`rooms/roof/`) | the chairman's stair → the fire stair | shadow to shadow from a narrow searchlight beam, then a guard | searchlight, guard | 1,719 |
| 5 | **The lift hall**, round the back | the fire stair → the goods lift (the end) | the far side of the glass from leg 1: behind the cleaner | the cleaner; the night guard behind the glass | 828 |

The stage is 6,971 ticks on the model (116 s) played perfectly: after the station (47 s), before
the aquarium (J's, aiming at 142 s) and the store (170 s). At most two watchers to a side of a
room, slow (0.8-1.0 m/s); no tools; the dash (agent G's) is never needed. The closest any
watcher comes on the solution is 0.52 m.

**The lift hall** is two halves of one room: the lift lobby in front, the back of house round
the core, and between them the securities house's glass screens, which stop the thief and not
the cones. No door joins the halves, so the stage cannot be cut short: from the lift lobby he
sees the goods lift he will leave by, out of reach. **The searchlight** is a beam 10 degrees wide
and 12 m long that takes 6 s to cross the roof; the plant, the skylight and the motor room cast
its shadows. Run straight across, the roof clears from about one start time in six.

## The graph

```
              roof ──(fire stair, down the core)──┐
               │ (private stair)                  │
           ninth floor                            │
               │ (service stair)                  ▼
 start ▶ lobby ──(escalator, lifts)──▶ [lift hall: lift lobby | glass | back of house] ──(goods lift)──▶ end
                                          │
                                   trading floor
```

The lift hall's lifts are a way in only (the door `lh_door_lifts` has no `to`). Every other door
leads both ways: he can go back down the service stair or the private stair, or back up the fire
stair, and come into a room again at its clock 0 by that door.

## How it sits in the World Kit

One world, `tower` (`levels/tower/tower.world.json`, written by `make_tower.py` through
`levels/assemble.py`): each room in its own 32 m cell side by side along x in the `next` order
(lobby, lift hall, trading floor, ninth floor, roof), at its floor's height (4 m a floor; the
roof over the eleventh); one region per room, from the dressed rooms' folders (`rooms/lobby`,
`rooms/hall/dressed`, `rooms/trading`, `rooms/ninth`, `rooms/roof/dressed`). The doors join the
rooms; `next` only orders them. Stand-ins: 700 triangles a cell, 1,400 for the trading floor and
1,500 for the ninth floor, whose main recipes are 1,285 and 1,402 (a cap takes whole
placements; the lobby's leaves out its escalator, 218).
The lobby's exit is made a door (`EXIT_DOORS`, `assemble.exit_to_door()`) so its play file stays
level 1's. Rooms a door joins take disjoint texture slot sets (`13-8,6-0` for the lobby, the
trading floor and the roof; `16-31` for the lift hall and the ninth floor); texture slot 7 and
4-bit palettes 250-251 are left to the front end's fonts.

## Commands

```sh
python3 carts/afterhours/rooms/hall/make_hall.py         # each new room's play file and greybox
python3 carts/afterhours/levels/tower/make_tower.py      # the stage's world
python3 carts/afterhours/levels/tower/solutions.py       # the legs, played; tests/tapes/tower_solution.akr
python3 carts/afterhours/levels/tower/solutions.py --check --pictures /tmp/tower
python3 carts/afterhours/levels/tower/sketch.py          # the layout sheet, sketch.png
make B=build-mine build-mine/carts/afterhours.mei        # the worlds (World Checker) and the cart
```

## Rules for every room

As `levels/store/ROUTE.md`, "Rules for every room": the 1 m cut, doorways open and framed with a
way on beyond, 2,500 triangles, recipes verified in depth mode with collision companions,
placements in the room's `NAME.placements.json` (never overwritten by its `make_*.py`), the recipe
folders reported for `make_tower.py`'s `ROOMS`.
