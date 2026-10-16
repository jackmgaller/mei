# Agent A's notes: the stealth core (Gate 1)

What the runtime does, what it reads from the room, the tape format, my answers to B and the
decisions Gate 1 makes. Kept current. B's side is in `NOTES_B.md`.

## The stages (2026-10-15, with E, B and J)

`dr_levels.akr`: `STAGE_STATION` 0 (`station`), `STAGE_TOWER` 1 (`tower`), `STAGE_AQUARIUM` 2
(`aquarium`, J's), `STAGE_STORE` 3 (`store`; `STAGE2` an alias), `PLATFORM_LEVEL` 4; `LEVELS` 5.
E's stage table is keyed by these. `stage_amb(k)` (`dr_world.akr`) gives each room F's ambience:
the station 1-3, the tower 4 (its roof 5), the aquarium J's `AQUARIUM_AMB`, the store 6-10, the
platform 1. Level 1 and level 2 are gone from the runtime and the scenarios (B removes them).

| Scenario | What it plays |
|---|---|
| 41-43 | The station's rooms, each with B's tape from its clock 0 |
| 46 | The station as one run (2,835 ticks), its totals and worst frame |
| 47 | Every room's framing, every stage (each world opened bare, each room's box read, nothing loaded) |
| 48 | The state flow through a front end: the station, two transitions, its end, again |
| 63, 64 | The store's eight legs (10,216 ticks), alone and through transitions |
| 83 | J's aquarium room by room, entered by every way in, 40 ticks each: worst frame 810k (debug, quarantine, after J's watcher changes) |
| 85, 86 | J's aquarium tapes: the ten legs in order (8,693 ticks; worst frame CPU 692,513 debug, quarantine; GPU 381,437), and through a front end's nine transitions, by both levels' doors |
| 88 | Each stage started as E's select does it: `stage_prepare(n)`, `stage_prepare_step()` a frame (one texture each) until done, `stage_start(n)`; no frame dropped; a prepare spoiled by another open falls back to opening the stage. `stage_start()` itself: 127k-324k cycles release (the aquarium's room load 271k) |
| 91, 92 | The tower (now B's stage of doors, six legs): in order (6,969 ticks), and through transitions |
| 87 | (diagnostic, not in `check.sh`) the aquarium's legs with nobody catching: the first tick of each leg on which any watcher would see or touch him |
| 84 | A guard sent 200 m off walks toward it without overflow (the trap scenario 47 once hit at `dr_watch.akr:94`: a room loaded without `enter_room()` kept the last cell's guards; `guard_walk()` now measures a far target at a sixteenth) |

**Dropped frames fail every scenario** (`drop_watch()` in the harness), except the frame after
one on which the harness itself did heavy test work (`test_heavy`: the lit-fan grid sweeps, the
framing search). The harness enters rooms as the game does: a stage through `stage_prepare()`
and its steps, a room by `room_prepare()` and a texture a frame (83).

**Worst frames in play only** (release, scenario 85, after each room's clock 2): the aquarium's
rooms 195k-492k CPU (the hall's the most, mostly drawing; the rules' tick under 50k), GPU up to
533k.

**Dark fans kept** (2026-10-15): a dark-eyed watcher's lit fan and its dotted outline (the dots
now small triangles on the floor) are one mesh per watcher (`cone_cached()`), rebuilt only when
the fan's points, the lights on or its colour change; the lights' half-planes are worked out once
(`room_light()`), a triangle outside a light's bounds is skipped before clipping. Scenario 80
checks every tick that the kept mesh is the one a rebuild makes. Release, scenario 85, the dark
rooms' worst frames in play before and after: hall 491,703 -> 473,701, great tank 450,520 ->
452,158, jellyfish 469,277 -> 454,722, quarantine 340,181 -> 340,403, tank tops 285,006 ->
251,573 (a worst frame is one where a moving guard's fan is rebuilt); the dark fans' average a
frame 57,000-139,000 (before: about 120,000-250,000 every frame).

**Stepped room load** for H's transition: `transition_ready_step()` (pieces: the entities, the
doors and sight segments, the framing, the entry; `ready_piece`), `load_room_piece(k, p)`.
**Pause** for E: `Mode.Pause`, `fe_pause()` on START, `room_restart()`, SELECT restarts at once
(START and SELECT are never in a tape).

## The aquarium stage: the dark, walkways, two-level rooms (2026-10-15, agreed with J)

J leads the stage (`NOTES_J.md`, "Runtime, agreed with A"); B added the schema fields
(`afterhours.game.mochi`); `dr_world.akr` reads them. Nothing changes for a room that does not
use them: every earlier tape replays as before.

**The rules as built:**

- **Dark rooms** (`room.dark`): `light` entities are boxes in plan (size x, z, the entity's yaw)
  on a level, lit always (`period` 0) or for `on` ticks from `offset` every `period` ticks on the
  room clock (floor modulo). A watcher without a torch (`guard.torch` false; every camera) sees
  the thief only where his centre is inside the fan **and** inside a light on now on his level. A
  torch guard sees his whole fan; a torch lights only for its holder.
- **Drawn as tested:** a dark-eyed watcher's fan is drawn bright only where it is lit (each of its
  16 triangles clipped to each light on, `cone_lit()`), the rest as a dotted outline; each light
  on has a faint wash on its floor; the thief is drawn dimmed when he stands unlit and a
  dark-eyed watcher shares his level.
- **Water and open air** are walls with `blocks` false and `solid` true on their level (no type of
  their own, J's choice): they stop the thief and the guards, cones cross them.
- **Two levels** (`room.upper` > 0: a walkway that many metres above the floor): every wall,
  watcher (its waypoints with it), hide spot, fragile thing, card, door, exit and light has a
  `level` (0 floor, 1 walkway). The thief is on the level of the spawn or door he came in by (a
  catch or START puts him back there); he and the guards collide only with their level's solid
  walls (the tracks and trains are on level 0); a fan is cast against its level's blocking walls
  and sees only a thief on its level; spots, fragile things, cards, doors and the exit are his
  only on his level. Noise is heard across levels: a guard walks to the point under (or over) it
  on his own level. The levels join only through other rooms' doors (no stairs in v1).
- **Drawing and framing:** everything on level 1 is drawn at floor + `upper`. The camera frames
  the floor's front edge and the walkway's back edge (BACK_Y..FRONT_Y), panning in z beyond that:
  with `upper` 3.2 the deepest two-level room with no z pan is **7.60 m** (one level: 10.15 m).
- **The tick order:** the trains, the lights (`lights_update(clock)`), the thief (his level),
  the cards and doors (his level), the tools, the guards (their level; noise from any), the fans
  (per level), G's dash path test and the catch test, both through `watcher_sees(i, x, z)`: not
  hidden, the watcher's level, the fan covers the point, and lit if the watcher is dark-eyed.

**Checks** (`tests/check.sh`), on A's stand-in aquarium rooms (`dr_standin.akr`: a dark gallery
with two tanks' light, one timed, a dark-eyed camera, a torch guard and a pool; a tank hall with
a floor and a walkway 3.2 m up, a floor guard looking at the walkway and a walkway camera):

| Scenario | What it checks |
|---|---|
| 80 | In the camera's fan in the dark: unseen, drawn dimmed; into light A: caught on the tick he enters it, the drawn lit fan covering him then and not the tick before; on a grid of the room the drawn lit fan is the rule, point for point (twice); under timed light B while off: unseen; caught on the tick it comes on; the torch guard catches him unlit; every tick, the drawn lit fan is the test |
| 81 | The hall's floor and walkway entered by different doors (level, spawn, a ghost each); on the floor the walkway's railing does not stop him and the walkway camera's fan over him does not see him; on the walkway the railing holds him and the floor guard's fan under him does not see him; his run is heard below and the guard walks to beneath him; caught on the walkway: back at its door, on the walkway; both levels framed |
| 82 | The budget in the stand-in rooms: worst frame CPU 205,581 (debug) / 168,625 (release), GPU 187,065 |

`dr_dash.akr` (G's) tests its path points with `watcher_sees()` (one line, marked agent A) and
draws its figure at his level.

## Stage 2: keycards, rooms of doors, re-entry (2026-10-15, agreed with B)

The schema is B's (`afterhours.game.mochi`: `door`, `keycard`, `room.exit` optional,
`room.name`); the runtime is `dr_keys.akr` (new), with `dr_room.akr` (`Door`, the cards),
`dr_world.akr` (reading them), `dr_game.akr` (the graph, re-entry) and `dr_view.akr` (drawing).
Level 1 and the platform play exactly as before: 4,786 ticks for level 1's run, every tape and
E's suite pass.

**The rules as built:**

- **Keycard:** picked up when the thief's centre comes within 0.5 m (`CARD_R`). Kept, not used
  up; held colours (`held`, bit c: 1 red, 2 blue, 3 green, 4 yellow) show top right on the HUD.
  Drawn by A: a slab in its colour, turning a hand's breadth off the floor, a ring in its colour
  opening every 1.5 s. `Ev.CardTake` (a = colour), `au_card(dx)`.
- **Staff door** (`door` with a `card`): shut, it is a wall across its box (solid and blocking:
  it stops the thief and the guards and cuts cones). The thief holding its colour opens it by
  walking into it (his circle within 0.08 m of the box, `DOOR_REACH`); it opens, and so does
  the door on its other side (`to`). Drawn by A: a leaf in its card's colour with a white
  stripe, as tall as the box (1 m in the room's front metre, like the cut front wall), swung 90
  degrees into the room over 15 ticks when open. Builders leave the doorway open and framed.
  `Ev.Unlock` (a = colour), `au_unlock(dx)`.
- **The run's state is committed when he leaves a room** (B's rule 4): caught or START, he is
  back at the spawn he came in by, clock 0, and the room is as it was when he came in (a card
  picked up in the attempt lies there again, a door opened is shut again). A card picked up
  opens doors at once, in the same attempt. A stage restart (`stage_start`, `run_start`) clears
  everything.
- **Rooms of doors:** a door with `to` leads to the room holding that door; he comes in at its
  `spawn`, the room's clock at 0, whichever way and however often. `end` ends the stage. A
  door with neither is a staff door inside a room (open: a gap). A door is armed only once he
  has been out of its box. `next` only numbers the rooms (rooms off the chain follow in entity
  order); a room's doors are numbered in entity order (B's `S2_LEG_DOOR` counts the same way).
- **Ghosts** are per room and door he came in by (`ghost_for(k, d)`, 16 slots; a slot is the
  best attempt's track, 28.8 KB, not its input: the 8 x 53 KB tapes before took about as much).
- **Times:** `room_time`, `room_restarts`, `room_spent` sum every visit; the run's end lists
  every room visited.
- **For E:** at `Ev.RoomExit`, `exit_to_room` (-1: the end), `exit_to_door`, `exit_door`
  (`EXIT_LINE` for a level 1 exit) are set, and in a transition `trans_to`, `trans_door`;
  `room_door_spawn(k, d)` gives the world spawn of room k by door d before it loads;
  `run_cleared` / `run_visited` are the rooms left / entered (bit k).
- **For F:** `au_room()` 6-10 are stage 2's rooms in `next` order (cinema, projection booth,
  staff corridor, shop floor, food hall).

**Checks** (`tests/check.sh`), on A's stand-in rooms of doors (`dr_standin.akr`: a hall with a
blue staff door, a store with the blue card and a posted guard, a vault with the end):

| Scenario | What it checks |
|---|---|
| 60 | The shut door stops him and cuts a cone; the card picked up (held, not the run's until he leaves); re-entry into the hall by its other door at clock 0, with a ghost of its own; the blue door opened by walking into it, a cone through it; into the hall by the blue door, still open; the rooms' times over six visits make the total |
| 61 | Caught holding the card: back at the store's door, the card lying there again, the caught attempt the store-by-this-door's ghost; START after opening the door: the door shut again, the card (committed) still held |
| 62 | 60 through a front end's transitions: five transitions door to door, each room held at its clock 0, the end door to Mode.End |

| 63 | B's level2 (`tests/tapes/level2_solution.akr`): the eight legs in order, the state carried, never caught; each leg starts in `S2_LEG_ROOM[i]` at clock 0 and leaves by `S2_LEG_DOOR[i]`; the rooms' times make the total; every frame within the budgets |
| 64 | 63 through a front end's transitions: seven, door to door, back into lower rooms and on, each room held at its clock 0, the end door to Mode.End |

**The levels** (`dr_levels.akr`): `LEVELS` 3: level1 (0), level2 (1, `STAGE2`), platform (2,
`PLATFORM_LEVEL`), B's order; E's stage table follows `LEVELS`.

**Measured, level2 as one run** (scenario 63): 10,216 ticks (B's model: 10,219). Legs, cart
ticks: 1281, 1238, 1753, 926, 1383, 1229, 1402, 1004. Worst frame CPU 272,308 (debug) / 221,910
(`TRAP=0`), GPU 279,284; sight worst 59,968 (debug) / 35,302.
With B's dressed rooms (later the same day): the same ticks; worst frame CPU 641,370 (debug, the
shop floor), GPU 418,247. Stage 2's fragile things draw as gift boxes (`mb_gift`).

## Hooks for E and F (2026-10-15, in the worktree `afterhours-next`)

All in `dr_hooks.akr` (mine) as weak defaults that E's and F's files replace, called from
`dr_game.akr`, `dr_thief.akr`, `dr_train.akr`, `dr_watch.akr`. Without E's files the cart and
every scenario behave as before. `afterhours.akr` imports F's `dr_audio.akr` and E's
`dr_front.akr` (the cart opens on E's title); A's harness imports `dr_audio.akr` (not E's: its
own front-end stand-in replaces the same hooks). `tests/check.sh`: 32 scenarios pass (48 and 49
for the hooks, 60-64 for stage 2), then E's `tests/front/check.sh` (7). Its logs go to `tests/out/check-BUILD` (BUILD the
folder `MEIC` is in), so agents checking at once from their own build directories do not
overwrite each other's.

**For E: the modes** (E builds on these; the "ten points" names were dropped by agreement):

- `Mode`: Title, Select, Play, Transition, End; `mode` starts at Play. A plays the rooms in Play;
  in every other mode `update()` calls `fe_update(pad, press)` and nothing ticks.
- `fe_start()`: once at the end of `init()`, the first stage already set up (E goes to the
  title with `game_mode(Mode.Title)`).
- `fe_draw() -> bool` after A's room (true: E drew the front end, A draws no HUD);
  `fe_draw_room() -> bool` whether A draws the room (in Play, Transition, End without E).
  `draw_trains()`, `draw_things()`, `draw_people()`, `draw_cones()` stay callable with E's own
  camera: they read only `at()` / `view_origin` and the current camera.
- `fe_owns_transition() -> bool`: true, and a room's exit goes to `Mode.Transition` (`trans_to`
  is the next room); E calls `transition_ready()` (the next room loaded at its clock 0, not
  running; `Ev.RoomReady`) and `transition_control()` (play, `Ev.RoomEnter`). The stage's last
  exit goes to `Mode.End` with `phase` Clear and `Ev.StageClear`.
- `stage_start(n)`: always reopens stage n's world (`level_switch`); forgets the ghosts only when
  n is not `ghost_stage`, the stage they were recorded on. `game_mode(m)`. `level_open_n(n)` in
  `dr_levels.akr` opens a stage's world to draw it.
- Events: `fe_event(e: Ev, a)`, as listed in `dr_hooks.akr` (RoomEnter means in control).
- The stage's result for the end and the save: `room_time[k]`, `room_restarts[k]`,
  `room_spent[k]`, `total`, `run_restarts()`, `run_length`, `stage_of()`.
- `au_tick()` is A's on every frame (all modes, the freeze included): E need not call it.

**For F: the calls**, wired as NOTES_F.md asks; signatures and `AMB_*` (0-5) agreed:

| Call | Where A makes it |
|---|---|
| `au_tick()` | the end of every `update()` |
| `au_music(true)` | `run_start()` |
| `au_room(amb)` | `enter_room()` (not restarts): level 1 by room order, the platform level 1, a stand-in 0 |
| `au_restart()` | every `restart_attempt()`, room entries included |
| `au_retry()` | START |
| `au_caught()` | `caught()` |
| `au_thief(moved, running, dx)` | every tick: straight-line metres moved, R held while moving, `thief.x - cam_x` |
| `au_hide(on)` | into and out of hiding |
| `au_train(t, phase, head, dx, to_close)` | every tick, every train (TPhase 0 off, 1 arriving, 2 stopped, 3 leaving; ticks until the doors close while open, else -1) |
| `au_exit()`, `au_clear()` | through the exit; the stage's end |
| `au_alert(dx)`, `au_knock(dx)`, `au_bell(dx)` | a guard sets off toward a noise; a fragile thing; a bell |

## The framing (changed 2026-10-15; for the room builders and `capture.py`)

The camera is unchanged: fixed yaw, 60 degrees down, a 20-degree field of view, 28.166 m from its
target (`CAM_DIST`), the target 0.6 m over the floor. **What changed is where the target sits in z**
(`frame_room()` in `dr_view.akr`): it used to put the room box's front edge on line 246, below
the picture, so the front row of floor and the cut front wall were cut off. Now:

- The room's whole floor, from its box's front edge (z = centre - size / 2, at the floor's height:
  where the cut front wall stands) to its back edge, lies between picture lines 16 and 222, clear of
  the HUD's lines (top 4-12, bottom 228-236). The back wall's top may still leave the picture.
- A room that fits (up to about 9.8 m deep) is centred between those lines and the camera never
  moves in z. A deeper one pans in z with the thief, between the front edge on line 222 and the
  back edge on line 16, eased like the pan in x. Of the rooms today only Gate 1's platform (11.5 m
  with the cupboard) pans, by 1.3 m.
- To reproduce it in a capture: find the target z at which the floor's front edge projects to line
  222 and the one at which the back edge projects to line 16 (the camera's x and y as above); use
  their mean when the first is the larger, else the first (the thief near the front).
- **The pixels a metre do not change** (the distance and the field of view are the same): about
  24 at the target, 21-22 at a room's back edge. Only the picture moves up the floor.
- Checked by scenario 47 on the five rooms of level 1 and the platform; the captures with the thief
  walked to each room's front row are `tests/shots/frame_level1_room1.png` .. `room5` and
  `frame_platform.png` (`tests/shots.sh`).

## Hiding reads at a glance (2026-10-15)

A hidden thief is drawn crouched (0.55 of his height) and dimmed to a dull brown (`mb_hidden`
in `dr_view.akr`), not his orange, with a faint cool ring at his feet. Going in, a pale ring
closes onto him over 12 ticks; coming out, one opens out and fades. Captures: `tests/shots/`
`hiding_before_change.png` (before), `hiding_enter.png`, `hiding.png`, `hiding_leave.png`, and the
four side by side in `hiding_compare.png` (level 1's gates, `tests/shots.sh`, scenario 56).

## Status (2026-10-15, level 1 in the cart)

- **The cart plays level 1** (`level1`, B's five rooms) as its first run; at level 1's end line,
  A starts Gate 1's platform as the next run (B's proposal); after it, A starts level 1 again.
  `dr_levels.akr` holds the list.
- **`tests/check.sh` passes, nothing PENDING**: 25 scenarios, about a minute (47, the framing,
  added since). Level 1's five
  tapes clear their rooms unseen (41-45: ticks 385, 1,510, 940, 1,181, 770, counting the clear's
  tick, one more than B's table), and the whole level as one run clears with no restarts in 4,786
  ticks, the total equal to the rooms' times (46). The platform's re-recorded tapes clear (1, 14,
  15).
- **`turn_toward()`'s tie is explicit** (below, "Level 1", rule 5).
- Earlier: Level 1's rules (centre test, sight through open doors, the run, turn rate, no tools).
- Not done: audio; a pause menu (START restarts at once); the pull-back between rooms. I have not
  played it with a pad.

## Level 1 (for B, the level lead)

**The rules now** (B's `rooms/platform/rules_model.py` needs the first three):

1. **Caught at his centre**: a fan catches him when it covers his centre point (edges count),
   `fan_covers()` in `dr_sight.akr`; a fan triangle with no area covers nothing. A guard still
   catches him by touch (their 0.3 m circles meeting), unless he is hidden.
2. **Sight into a train**: a train cuts the cones along its outline: each car's two sides and the
   train's two ends, with a gap at each open door (stopped, doors on that side), and no lines
   between its cars. A cone through an open door reaches into the car, and through it if the
   far side's door is open too. Closed doors, sides and windows block.
3. **Per watcher**: `speed`, `sight`, `fov` as before, and `turn_rate` (degrees a second; 240 when
   the schema's default) for how fast his head turns. The pace to a noise (1.5 times `speed`) and
   the look-around (150 ticks) are still the same for everyone: ask if a room needs them per
   watcher.
4. **No tools**: a room with `toys` and `bells` 0 shows no tool HUD; B and L do nothing.
5. **A turn of exactly 180 degrees** (`turn_toward()` in `dr_room.akr`; to within 0.001 rad,
   `TURN_TIE`) has no shorter way, so it goes to his right: clockwise seen from above, the
   heading increasing (from +z toward +x). B: in the model, if abs(abs(d) - pi) < 0.001 after
   wrapping, turn by +min(step, abs(d)). Every other turn takes the shorter way, as before.

**Open with the owner (not changed)**: a guard catches the thief by touch when their 0.3 m
circles meet. To catch only when the guard's body reaches the thief's centre (as the cones do) is
a one-line switch in `dr_game.akr`'s `tick()`: `let r = THIEF_R + GUARD_R` becomes
`let r = GUARD_R`. B's model would change the same way, and the tapes would want a recheck (they
can only get easier).

**The run** (`dr_game.akr`): the rooms the loader gives, in order. Going through a room's exit
loads the next room at once, its clock at 0, the thief at its spawn; START and catches restart
the room only. Each room keeps its own best attempt as its ghost. After the last room, the run's
end shows a line per room (its clearing time and restarts) and the run's total (every attempt's
ticks) and restarts; A starts the run again. The HUD shows "ROOM n" when the run has more than
one room.

**The loader, as B decided** (NOTES_B.md, "Level 1"), all in `dr_world.akr`:

- Rooms from `first` along `next` (no `first` in the world: entity order, which the platform
  uses); room k's entities are those whose positions lie in its box (position +- size / 2 in x
  and z, 0.5 m margin).
- The room entity's y is the floor: the people, cones, rings and the camera's framing are drawn
  at it; trains at their path's height.
- Entering a room enters its cell's region (`wp_region_enter`) when it is not the one loaded.
- Strings are read from whichever pack is open, so `dr_world.akr` reads any After Hours world.
- **Which world a level is** lives in `dr_levels.akr` (mine): level 0 is `level1`, level 1 the
  platform. A level is one run; A at a run's end line opens the next level (`level_switch(-1)`),
  which forgets the ghosts and enters the new world's regions afresh.
- **Level 1's tapes** (`tests/tapes/level1_solution.akr`) are scenarios 41-45 (room k from its
  clock 0) and 46 (the whole level as one run). A room builder's change that moves a watcher or a
  wall shows there first.

## Build, play, test

```sh
make B=build-dr-A build-dr-A/mei build-dr-A/carts/afterhours.mei
build-dr-A/mei --no-boot build-dr-A/carts/afterhours.mei
MEIC=build-dr-A/meic RUN=build-dr-A/mei-headless WORLDS=build-dr-A/cart-worlds/afterhours carts/afterhours/tests/check.sh
MEIC=build-dr-A/meic RUN=build-dr-A/mei-headless WORLDS=build-dr-A/cart-worlds/afterhours carts/afterhours/tests/shots.sh
```

Controls: d-pad or stick to walk (the stick's tilt sets the speed), R held to run, A to hide in a
hiding place (move or A to come out), B to use the tool, L to switch tool, START to restart the
room. At the exit, A plays the room again. Keyboard: arrows (or WASD for the stick), E = R,
J = A, K = B, Q = L, Enter = START.

`check.sh` needs `WORLDS` (the build directory's `cart-worlds/afterhours`, which make writes) as the
garden's does; `make test-carts` should pass `MEIC=$(B)/meic RUN=$(B)/mei-headless
WORLDS=$(B)/cart-worlds/afterhours` after building `$(B)/carts/afterhours.mei` (for the world).

## Files (mine)

| File | What |
|---|---|
| `afterhours.akr` | The entry point: the cart line, the pad as the input, the game, B's world |
| `dr_game.akr` | The frame loop: the clock, a tick's order, the catch, the freeze, the restart, the exit |
| `dr_keys.akr` | Stage 2: the keycards, the staff doors, the ways out of a room of doors, the run's state (committed on leaving) |
| `dr_room.akr` | The room in RAM (walls, waypoints, watchers, trains, spots, fragile things) and plan geometry |
| `dr_sight.akr` | The fans: 17 rays cut by wall sides and train sides; the circle-against-fan test |
| `dr_watch.akr` | Patrol guards, posted guards, cameras; hearing |
| `dr_thief.akr` | Movement and collision, hiding, fragile things, the toy and the bell |
| `dr_train.akr` | The timetable, the cars, the shells and the tracks' solid boxes |
| `dr_tape.akr` | Tapes (spans), the position track, the best attempt, the ghost |
| `dr_view.akr` | The camera and its pan, all the drawing, the HUD and the line at the exit |
| `dr_mesh.akr` | Stand-in meshes built in RAM: boxes, prisms, rings |
| `dr_standin.akr` | My stand-in platform: the rules' scenarios run on it (its numbers are known) |
| `dr_world.akr` | A level's world into the room model, room by room, and drawing it (`wp_draw`) |
| `dr_levels.akr` | Which world each level is: `level1`, then the platform |
| `tests/harness.akr`, `tests/a_tapes.akr` | The scenarios and my tapes (`tests/tapes/` is B's) |
| `tests/run.sh`, `tests/check.sh`, `tests/shots.sh` | Run one, run all, make the captures |

## The rules as the runtime runs them (numbers for the owner to judge)

- **The clock**: one tick a frame, 0 at the door. Nothing catches up after a late frame: the room
  runs slow instead, so a tape is the same whatever the frame rate.
- **A tick, in order**: the trains (a function of the clock alone), the thief (his input,
  collision), the tools, the guards (routes, hearing, turning), every watcher's fan, then the
  test. The frame draws that state: the fans drawn are the fans the thief was tested against.
- **Thief**: walks 2.4 m/s (silent), runs 4.8 m/s holding R (heard by each patrol or posted guard
  within his `hear`; the ring drawn has the room's largest `hear`). Footprint: a circle of the
  probe's 0.3 m. Collides in plan with solid walls, the tracks and open trains' shells.
- **Caught**: his centre inside a drawn fan (unless hidden), a patrol or posted guard touching
  him (unless hidden), or inside a carriage on the tick its doors close. The game
  freezes 20 ticks (a third of a second) with a red "!" over him and the catching fan red; then
  the room restarts at the spawn, clock 0. 20 frames from the mistake to the next try.
- **Sight**: a fan of 17 rays (16 triangles), `fov` wide and `sight` long, each ray cut at the
  nearest side of a blocking wall or a train's outline (with gaps at its open doors). Glass and
  benches (`blocks: false`) do not cut it; the tracks do not.
- **Patrol guards** walk their routes at `speed`, turning their heads at `turn_rate` (240 degrees a
  second by default)
  toward where they walk, and at a waypoint toward its `look`. **Posted guards and cameras** hold
  `look_a`, turn to `look_b` over `turn`, hold, turn back: a function of the clock and `phase`.
- **Hearing**: a patrol or posted guard who hears a noise walks to it at 1.5 times his `speed`,
  stops 0.8 m from it, looks around for 150 ticks (70 degrees each way), and walks back to where
  he left his route, which he takes up again (a posted guard turns back to where the clock's
  cycle is). A newer noise he hears sends him to it instead. Walls do not stop sound. Guards walk
  straight (no path finding): stuck for 40 ticks, he looks around where he is.
- **Wind-up toy** (B with the toy selected): set down 0.5 m ahead of him, facing his way; walks
  0.9 m/s for 8 s, turning right at walls, heard 4 m round every tick it walks. A guard who hears
  it follows it until it runs down, then looks around.
- **Pocket bell**: set at his feet; beeps once 3 s later, heard 9 m round.
- **Hiding**: A with his centre in a `hide_spot` box; drawn crouched. Any move, or A, ends it.
- **Fragile**: brushing one (the footprints overlap) is one noise of its `noise`; drawn knocked
  over.
- **Trains**: the head runs from the path's first point to `stop` over `arrive` ticks, slowing to
  0 (s = stop (1 - (1 - u)^2)); stands `dwell` ticks with its doors open; leaves over `leave`
  ticks, speeding up until its tail has passed the path's end (s = stop + (L + length - stop)
  u^2). Only the part on the path exists (drawn, blocking): it comes out of the end wall. The
  track (the path, `width` wide) is solid to the thief and the guards, except, while a train
  stands open, the stretch under it, where its shell (sides with gaps at the doors on its
  `sides`, and its two ends) stops him instead: he walks in at a door, along the carriages, and
  out at a door on the other side.
- **The exit**: his centre in the `exit` box: the next room of the run, or the run's end (above).

## The tape format

```
struct Span {      // dr_tape.akr
    n:   u16       // ticks this input lasts
    pad: u16       // buttons held (input.akr's bits; START is not recorded)
    sx:  s8        // the stick, -127..127 (x right; y up = +z, away from the camera)
    sy:  s8
}
```

A tape is a `const` array of spans from the clock's 0 of a fresh attempt. A button counts as
pressed on the first tick of a span that holds it after one that did not. The harness plays a tape
by the room clock, so after a catch the same tape plays again from its start.

## Decisions (Gate 1's five, with reasons)

1. **Walls for the cones: a wall map per room**, B's `wall` entities (boxes in plan with
   `blocks` and `solid`), not rays against the world's collision. One 2D model serves sight, the
   thief's and the guards' movement and glass; the World Kit's collision is 3D triangles with no
   "blocks sight" flag, so using it would mean slicing walls at a sight height, and glass would
   need a surface byte. The trains join the same model as moving rectangles. The cost is that
   the walls are written twice (the assets and the map), from the same numbers by B's script.
   Measured on B's platform (25 walls, 100 sides, 4 watchers): sight takes 54,000 cycles a frame
   on average and 75,000 at worst (5-8 % of the CPU), at most about 1,040 ray-side tests a frame
   after culling each fan's candidates by its bounds and its two edges.
2. **What a cone tests**: Gate 1 tested the footprint as a circle (0.3 m) against the polygon;
   the owner found it too hard, and since Level 1 it is **his centre point** against the polygon,
   exactly in 16.16. The checks confirm that the drawn cone's vertices are the fan's
   points exactly, and that an independent per-triangle test agrees on the tick of the catch and
   on every tick before it.
3. **The tape and the ghost**: the tape is run-length spans of the quantized input the room was
   played with (the stick is rounded to s8 before the tick uses it, so a replay is exact); B's
   2,168-tick solution is 72 spans, 432 bytes. Each attempt also records the thief's position every
   tick (centimetres, 4 bytes a tick, up to 2 minutes). Each room of a run keeps its own best. The best attempt so far (a clear beats
   none; then the faster clear; else the nearest approach to the exit) is drawn on the next
   attempt as a faint additive figure at the same tick of the clock, from that track: replaying
   the tape alongside would cost a second room's CPU. For the memory card the tape is what to
   save; the track can be rebuilt by replaying it at load.
4. **The camera's pan**: fixed yaw, pitch (60 degrees), field of view (20) and distance (28.2 m).
   The target's x follows the thief with a lead of up to 2.2 m the way he walks across the
   screen, eased (the lead over about 40 frames, the camera an eighth of the way each frame), and
   is clamped so the room's ends rest on the screen's edges. The view is 13.2 m wide, so he sees
   about 8.8 m ahead, more than any 6 m cone. In z the whole floor is kept on the picture, a
   deep room panning in z (see "The framing"). A cone
   beyond a side of the screen that reaches within 2 m of it is marked by a yellow arrow at the
   edge. Not done: leaning the pan toward a guard who heard something.
5. **The World Kit's fit**: good for a room's data. Entities with stable IDs, refs for routes and
   the room's entry and exit, a World Kit path per track, typed parameter records read by a cast:
   the loader is `dr_world.akr`, about 170 lines with Level 1's run of rooms, and B's recipe builds and
   checks cleanly. What it does not do for this game: sight and movement are plan geometry on the
   wall map, not the world's collision (I use no `wp_push` or `wp_floor`); everything that moves
   is drawn by the cart. The pull-back's stand-ins are untried (Gate 2).

## What feels wrong or is unfinished (my read, without a pad)

- He stops dead when he walks straight into a pillar; he slides only when he meets it at an angle.
- Guards go straight to a noise: across a track they stand at its edge until they give up.
- Four overlapping half-blend cones make the middle of the platform hard to read; the back-wall
  camera's 9.5 m cone spans the room's whole depth.
- The run's ring (7 m, B's `hear`) is large on screen; it may read better as a pulse.
- The trains read as pale blue slabs; the doors show only as gaps in a dark sill. Now that a
  cone reaches into a car through an open door, those gaps matter more than they show.
- Caught at his centre, but a guard still catches him by touch at their 0.3 m circles: a fan
  may now cover half of him safely while a guard brushing his shoulder catches him. For the owner.
- A hidden thief is safe from a guard walking into him, and a guard who touches him catches
  him: both are my choices for the owner to judge.
- The freeze is 20 ticks; the clear tick costs 64,000 cycles more (keeping the tape), unseen.

## Measured: level 1 as one run (scenario 46, TRAP=0)

| Room | Clears on tick | Worst CPU in play | Worst GPU in play | Triangles submitted |
|---|---|---|---|---|
| 1, the last train | 385 | 86,965 | 268,029 | 350 |
| 2, the ticket gates | 1,510 | 82,041 | 194,816 | 304 |
| 3, the passage | 940 | 66,125 | 204,031 | 208 |
| 4, the lobby | 1,181 | 102,399 | 213,564 | 353 |
| 5, the aquarium | 770 | 280,251 | 372,408 | 1,249 |

The run: 4,786 ticks (80 s), no restarts, no frame late. Its worst frames are the door into the
aquarium (395,774 CPU cycles, 40 %: reading the room's entities and loading its region's
textures) and the end line (425,354 GPU cycles, 21 %, over the aquarium). Sight is at most 28,241
cycles a frame in level 1 (2 watchers a room at most, 340 ray-side tests). Greybox rooms; the
dressed rooms will add triangles.

## Measured (release build, B's platform; tests 1, 14, 15 and 31 with TRAP=0)

| Frame | CPU cycles | GPU cycles | Triangles submitted |
|---|---|---|---|
| Worst in play (a busy tour: running, toy, bell, a train standing) | 260,313 (26 %) | 342,081 (17 %) | 799 |
| Worst in the solutions' play | 269,513 (27 %) | 339,085 (17 %) | 782 |
| The clear tick (the tape kept: then a 67 KB copy, now 53 KB) | 316,086 (32 %) | | 820 |
| Sight alone, worst / mean | 75,495 / 53,664 | | |

Remeasured after the Level 1 rules (test 31, TRAP=0): worst 261,009 CPU, 342,081 GPU, sight
74,659 worst and 53,504 mean: unchanged. In the debug builds the scenarios use (`--trap-fmul`),
the same worst frame is about 334,000 CPU cycles and sight 133,000. No frame ran late.

## Answers to B

- **The solution tapes** (`tests/tapes/platform_solution.akr`): imported; scenarios 1, 14 and 15
  play `SOLUTION_PLATFORM`, `_ON_FOOT` and `_BELL`, and `check.sh` runs all three. Each clears
  three ticks later than your note says (your model's count, I think: I count the ticks run, the
  clear's included).
- **Level 1** (NOTES_B.md): agreed and built as you decided; see "Level 1" above.
- **v2's track bands**: in, as described under Trains above.
- **v1's proposals**: the wall map (1) is the decision above; the trains as sections (2) are
  drawn so, cut at 0.9 m, roofless, from the `train` fields; a train asset (3) is not used in
  Gate 1, so that what is drawn is exactly what blocks, cut where the path ends.
- **The world**: `world_platform_load()`, `wp_draw()` in depth mode with the near pass only
  (`wp_far_ring` 0); entity positions are world positions; boxes turn by the placement's yaw.

## Requests and proposals

- To the main session: add `tests/check.sh` to `make test-carts` with `WORLDS` (above).
- DESIGN.md, when it is next edited: Gate 1's open choice of walls is made (a wall map), the
  freeze is 20 ticks, and the speeds above are the ones to judge.
- To B: match `turn_toward()`'s tie ("Level 1", rule 5) in `rules_model.py`.
