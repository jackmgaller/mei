# Agent B's notes (the complex; the level lead)

What B has landed, what B asks of A, and B's decisions. A's side is in `NOTES_A.md`. Newest
first in each section.

## Stage 2: keycards and backtracking (2026-10-15, in the worktree `afterhours-next`)

**Dressed (phase 2)**: `make_level2.py` takes the cinema, the booth and the corridor from their
`dressed/` folders and the shop floor and the food hall from their own folders
(`rooms/shopfloor`, `rooms/foodhall`). `level2` builds clean: 5 cells, 1,282,228 bytes, 0
warnings, World Checker 0 hard failures and 0 over thresholds in 57 views (peaks 1,385 triangles,
CPU 314,412, GPU 363,081 cycles). Cells: cinema 717, booth 334, corridor 639, shop floor 1,556,
food hall 1,327 triangles.

- **Stand-ins**: a cap takes whole placements, and three dressed rooms draw their shell and most
  of the room as one recipe (cinema 715, shop floor 830, food hall 1,183). At the old 700 cap the
  cinema's stand-in was its beam alone (2 triangles), the food hall's its cases (144) and the shop
  floor's its escalators (498). The caps are now 720, 1,600 and 1,400 for those three (the
  `standin_triangles` threshold 1,600), so every stand-in is its whole room. E's scenario 66 (the
  transitions through stage 2) stays in budget: worst CPU 604,534, GPU 448,577. If the select or
  the transition grows heavy, the builders could split their shell from their props, so that a
  smaller cap still keeps the shell.
- **The wall map gained what the dressing stands in play** (in each `make_*.py`'s `DRESSED`, not in
  `ROOM`, which the dress scripts read):
  - the cinema's curtains at the screen's ends (they block, as the screen does) and the speakers
    behind it;
  - the booth's lenses (solid, cones pass);
  - the shop floor's table of knits and bag shelves (solid, cones pass);
  - the food hall's back counters and the cleaner's parked cart (solid, cones pass).

  None of these is on a route. The eight legs replay on the model with the same ticks and margins
  (0.41 m corridor, 0.44 m shop floor).
- **Gift boxes**: A draws them at the three `fragile` entities (a pink box with a gold ribbon).
- **Checks** (`build-ah-B`): `tests/check.sh` passes all 32 of A's scenarios and E's 7. In
  scenario 63, the eight legs clear in 10,216 ticks as before. The debug build's worst frame of the
  run is CPU 641,370, on the shop floor (272k in greybox), and GPU 418,247.

**State**: the stage is in greybox and clears end to end in the cart. Five rooms of a department
store (cinema, projection booth, staff corridor, shop floor, food hall) joined by doors as a
graph, a blue and a red card, eight legs. `level2` is in `worlds.txt` (between level1 and the
platform) and builds clean in `build-ah-B`: 5 cells, 110,920 bytes, 0 warnings, World Checker 0
hard failures and 0 over thresholds in 69 views; cells 98-160 triangles. The route, the graph,
the rules and the World Kit layout are in `levels/level2/ROUTE.md`; each room's floor plan for
its builder is its `PLAN.md` (`rooms/cinema/`, `rooms/booth/`, `rooms/corridor/`,
`rooms/shopfloor/`, `rooms/foodhall/`). The room builders can start.

| Leg | Room, in → out | Tape (`tests/tapes/level2_solution.akr`) | Model / cart ticks |
|---|---|---|---|
| 0 | cinema: the screen → corridor | `SOLUTION_S2_LEG_0` | 1,280 / 1,281 |
| 1 | corridor: cinema → stair | `_1` | 1,237 / 1,238 |
| 2 | shop floor: stair → stair, the blue card | `_2` | 1,752 / 1,753 |
| 3 | corridor: stair → blue door | `_3` | 924 / 926 |
| 4 | booth: door → door, the red card | `_4` | 1,380 / 1,383 |
| 5 | corridor: blue door → stair | `_5` | 1,235 / 1,229 |
| 6 | shop floor: stair → red door (the lift) | `_6` | 1,401 / 1,402 |
| 7 | food hall: lift → the way out | `_7` | 1,002 / 1,004 |

A's scenario 63 plays them in order with the cards and doors carried: 10,216 ticks (2 min 50 s),
never caught. `tests/check.sh` (`build-ah-B`): all 31 After Hours scenarios and E's 6 pass.
Nearest margins on the model: 0.41 m (the corridor's office guard, legs 1, 3, 5), 0.44 m (the
shop floor's camera); the rest 0.75 m or more. Legs 3-5 drift a few ticks between the model and
the cart (A's numbers above), so recheck in the cart after any change.

**Decided with A** (NOTES_A.md has the runtime's side):

- Schema v4 (`afterhours.game.mochi`): `room.name` (a World Kit name, `the_cinema`, shown THE
  CINEMA; required, so level 1's and the platform's rooms have one too), `room.exit` optional,
  `door { size, spawn, to, end, card }`, `keycard { colour }`. `next` only orders rooms in a
  stage of doors. A room with no doors works as before.
- The rules: ROUTE.md, "The rules". One change from A's proposal: a card or a door is the run's
  only when he leaves the room; caught or START puts the room back as it was when he came in. The
  card rooms are dead ends, so keeping a card taken in a caught attempt would make getting caught
  a free way out.
- My model follows A's tick order (`rules_model.py`'s `keys_update`: cards strictly within 0.5 m
  after the move, shut doors opening strictly within 0.38 m of his centre, open from that tick,
  passable from the next; the exit, then doors in entity order).
- A draws the staff doors' leaves (in the card's colour, shut or open) and the cards; the
  builders leave the doorways open and framed.
- Stage order: level1, level2, platform (A's `dr_levels.akr`; E's `STAGES_3`, "AFTER CLOSING").

**How the stage sits in the World Kit**: as level 1: one world, a room a 32 m cell side by side
in x at its floor's height, a region each, kit-made stand-ins. The cells' x order is the
building's section (cinema 8F, booth 9F over it, corridor 8F, shop floor 7F, food hall B1), so
every door joins rooms at most two cells apart and the pull-back between them holds both. E's
section reads the doors for its route lines and `room.name` for the captions (done, in
`dr_section.akr`).

**Tools**: none, as for level 1. Stage 2's new ideas are the cards and going back; a tool would
compete with them. The food hall's gift boxes (fragile, a noise) are the only new hazard.

**How it was built**: `levels/s2room.py` turns a short room description (walls with doorways,
props by kind, doors, cards, watchers) into the greybox recipes, the placements and the play
file, so the wall map and the drawn room come from the same numbers. `levels/level2/solutions.py`
plays the eight legs on the model with the run's state carried and writes the tapes with
`S2_LEGS`, `S2_LEG_ROOM` and `S2_LEG_DOOR`.

**Commands** (ROUTE.md, "Commands"), and the cart's check of the stage:

```sh
MEIC=build-ah-B/meic RUN=build-ah-B/mei-headless WORLDS=build-ah-B/cart-worlds/afterhours carts/afterhours/tests/run.sh 63 12000 /tmp/s2run
```

## Level 1 (2026-10-15, B is the level lead)

**State (phase 3)**: level 1 is **built from the dressed rooms**. `levels/level1/make_level1.py`
takes room 1 from `rooms/arrival/dressed`, room 2 from `rooms/gates/dressed`, rooms 3 and 4 from
`rooms/passage` and `rooms/lobby`, and the aquarium from `rooms/aquarium/aquarium.placements.json`
(with my collision in `levels/level1/aquarium/collision`). `level1` is in `worlds.txt` (with
`platform` after it) and builds clean: 5 cells, 1,004,696 bytes, 0 warnings, World Checker 0
hard failures and 0 over thresholds in 81 views (peaks 1,310 triangles, CPU 420,194, GPU 419,338
cycles). Cell triangles: arrival 695, gates 652, passage 855, lobby 909, aquarium 1,657. The
route, the curve and the World Kit decision are in `levels/level1/ROUTE.md`; each room's floor
plan is its `PLAN.md` (`rooms/arrival/`, `rooms/gates/`, `rooms/passage/`, `rooms/lobby/`,
`rooms/aquarium/`).

| Room (run index) | Tape (`tests/tapes/level1_solution.akr`) | Clears in the model on tick |
|---|---|---|
| 0 `r1_room`, the last train | `SOLUTION_L1_ARRIVAL` | 384 |
| 1 `r2_room`, the ticket gates | `SOLUTION_L1_GATES` | 1,507 |
| 2 `r3_room`, the passage | `SOLUTION_L1_PASSAGE` | 936 |
| 3 `r4_room`, the lobby | `SOLUTION_L1_LOBBY` | 1,180 |
| 4 `r5_room`, the aquarium | `SOLUTION_L1_AQUARIUM` | 768 |

**Checks on the dressed level** (`build-dr-B/`): `python3 levels/level1/solutions.py --check`
clears all five rooms; `rooms/platform/solutions.py` clears its three (2,165, 2,164, 2,047); A's
`tests/check.sh` passes **all 25 scenarios**, nothing PENDING, among them 41-45 (each room's
tape), 46 (the five in one run: 4,786 ticks, worst frame CPU 516,558 in the aquarium, GPU
420,882) and 47 (framing).

**What the dressing changed about the puzzles: nothing.** The dressed rooms keep the plans'
footprints, and the tapes are byte-identical to phase 2's. The wall map gained, from the
dressing (in the rooms' `make_*.py`):

- Room 1: the bins, the timetable box and the ashtray as low walls (`blocks: false`, solid);
  the bench walls are 0.82 m high, the dressed benches' backs (were lower). All off the route.
- Room 2: the stairwell's wall runs 0.12 m past the well on its two open sides
  (`RAIL_OUT`), where the dressed railings stand. The route from the spawn to the lockers
  passes it with about 0.06 m to spare and still clears. `STAIRWELL` itself is unchanged
  (the builder's dress script imports it).

Also in phase 3:

- `levels/greybox.py`'s `write_room` writes the greybox placements to
  `greybox/NAME.placements.json` always and to `NAME.placements.json` only when there is none,
  so rerunning a room's `make_*.py` no longer overwrites the builder's placements.
- `levels/rules_model.py`'s `turn_toward()` has A's tie: a turn within 0.001 rad of 180° goes
  to his right, clockwise from above. (The rooms still have no exact reversals.)
- Stand-ins: the cap is 700 triangles a cell (800 for the aquarium), up from 300, so the
  dressed rooms' main recipes are in them (at 300 the gates' stand-in was 20 triangles). It
  raised the World Checker's peak view to 1,310 triangles; still 0 over thresholds.

**Decided for the level** (reasons in ROUTE.md): one world per level, each room in its own 32 m
cell side by side along x at its own floor height, one region per room, kit-made stand-ins for
the pull-back; rooms written in their own frame and moved into place by
`levels/level1/make_level1.py`; a room is placements (the builder's), a play file (the lead's) and
its recipes.

## Gate 1: status (the platform, now a later level)

| Item | State |
|---|---|
| `afterhours.game.mochi` | **v3 in**, parses (level 1: `room.next`, `room.first`, `guard.turn_rate`; `worlds level1, platform`). Types: room, spawn, exit, waypoint, guard, train, hide_spot, fragile, wall |
| The platform world | **builds cleanly**: 1 cell, 0 warnings; World Checker 0 hard failures, 0 over thresholds in 55 views (52 sampled, 3 from the game's camera) |
| `worlds.txt` | **in**. Plain `make` builds the world into `$(B)/worlds/carts/afterhours/rooms/platform/` and compiles the cart with `-I $(B)/cart-worlds/afterhours` |
| The puzzle, timetables, watchers | **in**: `rooms/platform/PUZZLE.md` |
| Solution tapes | `tests/tapes/platform_solution.akr` (written by `rooms/platform/solutions.py`), **re-recorded for level 1's rules** (2026-10-15): scenarios 1, 14 and 15 print `DONE`. The room changed for them: train A has two doors a car and stands 12 s, the camera reaches 8.2 m (PUZZLE.md) |

To check after a change:

```sh
python3 carts/afterhours/rooms/platform/make_platform.py        # the world and its assets
python3 carts/afterhours/rooms/platform/solutions.py            # replays the plans, rewrites the tapes
make B=build-dr-B build-dr-B/carts/afterhours.mei
MEIC=build-dr-B/meic RUN=build-dr-B/mei-headless WORLDS=build-dr-B/cart-worlds/afterhours \
  carts/afterhours/tests/run.sh 1 4000 /tmp/sol
```

## Gate 1: for A (the platform world)

- **The tapes file holds three consts**: `SOLUTION_PLATFORM` (scenario 1), and
  `SOLUTION_PLATFORM_ON_FOOT` and `SOLUTION_PLATFORM_BELL`, the room's other two solutions. If you
  like, scenario 1 could play all three (one attempt each), so a rule change that closes one of
  them shows; that is your call.
- **The tapes are drafted on a model of your rules** (`levels/rules_model.py`, shared with
  level 1, a float copy of `dr_train`, `dr_watch`, `dr_sight`, `dr_thief` and `dr_game`'s tick).
  If you change a rule's number (speeds, the turn rate, hearing, the toy or the bell), tell me
  here, or change the same constant at the top of `rules_model.py` and run `solutions.py`. The
  plans wait on what the room does (a guard past a point, a train's doors), not on fixed times,
  so most changes only need the rerun.
- **Patrols' starting heading** is the entity's yaw (your `dr_world.akr`): the world now sets it
  to face the first waypoint (270 for the platform patrol, 90 for the walkway's).
- **The world**: `platform`, `import "platform.akr"`, `world_platform_load()`; drawn with
  `wp_draw()` in depth mode. 10 placements, 486 triangles in the pack; 256–261 drawn from the
  game's camera (the World Checker's vantage views: about 59,000 CPU and 125,000 GPU cycles,
  at the checker's own field of view, which is wider than the game's).
- **Entities** (39): `room`; `spawn`; `staff_door` (exit); `guard_platform` (patrol) with
  waypoints `p1_*`; `guard_walkway` (patrol) with `p2_*`; `guard_kiosk` (posted); `camera_far`
  (camera; the lens at y = 2.3 on the back wall); `train_a`, `train_b` (paths `track_a`,
  `track_b`; each entity stands where its head stops); `hide_kiosk`, `hide_cupboard`;
  `fragile_papers`, `fragile_bucket`; 25 `wall` boxes, all at yaw 0. None has a mesh.
- **The plan** (x right, z away from the camera, the platform's top y = 0): front wall z
  0.75–1.0 cut at 1 m; track A z 1.0–3.4; island platform z 3.4–7.6, x 1–31; track B z 7.6–10.0;
  walkway z 10.0–11.2, x 1–31; back wall z 11.2–11.45, 2.4 m, the cupboard set into it to z 12.0.
  The room entity's `size` is 30.5 × 2.4 × 11.5 about (16, 0, 6.5). Tracks are 2.4 m wide
  (`width` 2.4); paths run between the end walls' outer faces (x 0.75–31.25, 30.5 m).

## The schema: what each type means to the runtime

The comments in `afterhours.game.mochi` are the contract; this is the short form. Units: metres, ticks
(60 a second, the room's clock), degrees as a placement's yaw (0 faces +z, away from the camera;
90 faces +x, right on the screen).

- **room** (one per room; a world holds a level's rooms): `entry` (a spawn), `exit` (an exit box),
  `size` (the room's extent about the entity's position: the camera's pan, and which entities are
  the room's), `next` (the room the exit leads to), `first`, `toys`, `bells`. Its y is the floor.
- **spawn**: the thief's start and restart; `yaw`.
- **exit**: a box (`size`); the room clears when the thief's centre is in it.
- **waypoint**: `next` (ref?), `wait` (ticks), `look` (degrees while waiting).
- **guard**: `kind` patrol | posted | camera; `route` (first waypoint, patrol); `sight`, `fov`;
  `speed` (patrol); `look_a`, `look_b`, `hold`, `turn`, `phase` (posted and camera); `hear`;
  `turn_rate` (degrees a second, a patrol's head; v3).
- **train**: on the World Kit path `path`; `period`, `offset`, `arrive`, `stop`, `dwell`,
  `leave`; `cars` × `car_length`, `width`, `doors` per carriage per side, `door_width`, `sides`
  left | right | both (of the way it travels).
- **hide_spot**: a box. **fragile**: `radius`, `noise`.
- **wall**: a box in plan, `blocks` (cuts cones), `solid` (stops the thief and the guards).

## Answers to A

1. No platform-edge walls: done; the tracks are the trains' bands.
2. World `platform`, `world_platform_load()`: yes.
3. Wall boxes turned by the entity's yaw, centred in x and z: yes; all at yaw 0. No `glass`
   type: a wall with `blocks: false` is glass.
4. You draw the trains and the fragile things: agreed; the world has no meshes for them.
5. Angles: degrees, heading h faces (sin h, cos h): yes.

## Decisions

- **The puzzle** (PUZZLE.md): every run ends through train B (the only way onto the walkway,
  doors on both sides) and past the walkway guard, using the cupboard or a tool. Train A is a
  corridor no cone enters; train B also blinds the camera while it stands. Three solutions are
  tapes (the trains; on foot with the kiosk; the bell); a toy lure and train B's next stop are
  further ones, untaped.
- **The camera's foot closes the walkway**: a camera's fan starts at the lens, so on the narrow
  walkway under it the sweeping wedge cannot be passed, walking or running (checked on the model
  over a whole cycle). It is used as a wall: it makes the walkway's west half a dead end, so the
  door the thief takes out of train B matters.
- **One `wall` type with `blocks` and `solid`**; no `glass` type, no edge walls.
- **Everything in the play area is cut at 1 m** (the front wall, the pillars, the kiosk, their
  cut tops drawn light). Only the back wall, the end walls and the stair stand 2.4 m. At 60° a
  2.4 m pillar hides 1.4 m of floor behind it and the thief with it; at 1 m it hides 0.6 m and
  never him. *Proposal for DESIGN.md*, "The look": extend the section rule from "the walls
  nearest the camera" to "anything inside the play area", with the cut drawn as a light top.
- **The room's depth fits the screen**: 10.5 m from the front wall to the back wall (the first
  draft, 11.4 m, did not fit at 24 px a metre).
- **Collision is authored apart** for the station box and the kiosk (`pf_shell_col`,
  `pf_kiosk_col`: floors, and walls without tops), since the drawn walls' tops met in
  T-junctions that the World Checker failed as `edge_mismatch`.
- **The game's camera is in the World Checker** as three vantage points (west, middle, east).

## The World Kit for rooms: how it fitted

It worked: one cell, recipes and entities from one script, 0 warnings, a clean World Checker,
and `make` and `-I` brought it into the cart without any glue. Where it fought the room, and what
I did:

1. **Sight needs a plan of the walls, and the kit has none.** The cones are 2D, against the
   room's walls; the kit's collision is triangles in 3D, built for a body walking. So the room
   carries its walls twice: as Asset Kit geometry (drawn and collided) and as 25 `wall` entities
   (the plan A tests). Both come from the same numbers in `make_platform.py`, so they cannot
   drift here, but a room built by hand could. *Proposal*: the kit exports a per-cell plan of
   each placement's collision (its outline at a height, as boxes or segments, with the placement's
   tag), which a top-down game reads instead of wall entities.
2. **Collision is mostly for the checker.** A uses the wall map, not `wp_push`/`wp_floor`, for
   movement. The world's collision still has to be right, because the World Checker checks it:
   the drawn walls' tops met in T-junctions (`edge_mismatch` hard failures, two of them), and the
   walkway's floor had to be split in three so its edges met the cupboard floor's end to end.
   The fix was the kit's own (separate collision assets), but it is work only the checker sees.
3. **The World Checker samples for a platformer**: eye-height, follow, rooftop and air views,
   none from the game's fixed camera. Vantage points fix that, but they are drawn at the
   checker's own field of view (wider than the game's 20°) and do not draw the game's moving
   things, so its frame figures are the room alone (A measures the real frame).
4. **Trains**: paths are lines only (`raised`), fine; but a path must stay within the cell (else a
   warning), so the trains' runs in and out of the tunnels are the runtime's extrapolation past
   the path's ends, and the train entity's position is only a marker. The kit does not check that
   a `name` parameter names a path (it says so); a misspelt path fails only at load in the cart.
5. **Schema**: Mochi was easy to write and to change; refs (routes, entry, exit) resolve and are
   checked. Missing for rooms: a 2D box (`size` is a `vec3` whose y is the height A ignores) and
   angles as a type (degrees in `fixed`, converted by the runtime).
6. **For the pull-back at Gate 2** (not built yet; what the kit will do): DESIGN.md's complex is
   a vertical section, rooms stacked (a cinema on the 8th floor above the mall). Cells are columns
   in x and z covering every height, so two rooms one above the other cannot be two cells; and
   decision 2 makes each interior its own world, while the pull-back draws the current room and
   its neighbours at once, which needs two packs open (`stdlib/worldpack.akr` keeps one,
   `wp_pack`). Ways out, for the main session to choose: one world per complex with the rooms laid
   side by side in x (the section unfolded, never stacked in the same x and z), each room a cell
   or a few, and the kit's per-cell stand-ins drawn for the neighbours; or several worlds with
   the neighbours' stand-ins exported as plain meshes the cart embeds. A 30 m room already fills
   a 32 m cell (the platform's box is x 0.75–31.25 of 0–32); longer rooms span cells.
