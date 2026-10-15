# Agent A's notes: the stealth core (Gate 1)

What the runtime does, what it reads from the room, the tape format, my answers to B and the
decisions Gate 1 makes. Kept current. B's side is in `NOTES_B.md`.

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
- Strings are read from whichever pack is open, so `dr_world.akr` reads any dorobo world.
- **Which world a level is** lives in `dr_levels.akr` (mine): level 0 is `level1`, level 1 the
  platform. A level is one run; A at a run's end line opens the next level (`level_switch(-1)`),
  which forgets the ghosts and enters the new world's regions afresh.
- **Level 1's tapes** (`tests/tapes/level1_solution.akr`) are scenarios 41-45 (room k from its
  clock 0) and 46 (the whole level as one run). A room builder's change that moves a watcher or a
  wall shows there first.

## Build, play, test

```sh
make B=build-dr-A build-dr-A/mei build-dr-A/carts/dorobo.mei
build-dr-A/mei --no-boot build-dr-A/carts/dorobo.mei
MEIC=build-dr-A/meic RUN=build-dr-A/mei-headless WORLDS=build-dr-A/cart-worlds/dorobo carts/dorobo/tests/check.sh
MEIC=build-dr-A/meic RUN=build-dr-A/mei-headless WORLDS=build-dr-A/cart-worlds/dorobo carts/dorobo/tests/shots.sh
```

Controls: d-pad or stick to walk (the stick's tilt sets the speed), R held to run, A to hide in a
hiding place (move or A to come out), B to use the tool, L to switch tool, START to restart the
room. At the exit, A plays the room again. Keyboard: arrows (or WASD for the stick), E = R,
J = A, K = B, Q = L, Enter = START.

`check.sh` needs `WORLDS` (the build directory's `cart-worlds/dorobo`, which make writes) as the
garden's does; `make test-carts` should pass `MEIC=$(B)/meic RUN=$(B)/mei-headless
WORLDS=$(B)/cart-worlds/dorobo` after building `$(B)/carts/dorobo.mei` (for the world).

## Files (mine)

| File | What |
|---|---|
| `dorobo.akr` | The entry point: the cart line, the pad as the input, the game, B's world |
| `dr_game.akr` | The frame loop: the clock, a tick's order, the catch, the freeze, the restart, the exit |
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
