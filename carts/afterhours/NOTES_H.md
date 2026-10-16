# Agent H's notes: the transition between rooms

`dr_trans.akr`, taken over from agent E (2026-10-15). The owner's note: "It's really high
quality, but also it makes the building look way vaster than it is." The transition now shows
the next room as next door, at the game's own scale; the owner chose the pan and separate
texture slots for the rooms a door joins (2026-10-15). Kept current.

## What it does

54 frames (0.9 s, `TR_N`) from the frame the thief steps into a way out to the frame he is in
control at the next room's clock 0. A or START skips it from frame 8.

- **The camera does not pull back.** It keeps the game's pitch (60 degrees), field of view (20)
  and distance (28.2 m), so both rooms stay at about 24 px a metre, and slides from the room
  he left, as A framed it, to the next room, as A will frame it (both read through A's
  `cam_eye()`, so a change to A's framing is followed).
- **The two rooms are drawn joined at their doors**, not where the World Kit world keeps them
  (32 m apart in x, at their real heights). The next room is set beside the room he left, on
  the side its door faces, the two doors level in z, `TR_GAP` (1.5 m) apart plus 0.5 m for each
  metre the stair climbs. A door in a back wall that leads up puts the next room behind and
  above (the lobby's escalator); one in a front wall that leads down, in front and below. The
  rooms' floors are drawn at most one storey apart, 5 m (`TR_STOREY`): the tower's 40 m and the
  lift's 35 m from the shop floor to the food hall are drawn as 5. A pair is drawn the same way
  in both directions.
- **Doors on an upper level** (the aquarium's mezzanines and catwalks, A's `room.upper` and a
  door's `level`): the way out, the way in and the stair are at the doors' heights, the floor
  plus `upper`; the storey cap applies to the floors, then each door's level is added. The
  great tank's catwalk (1F, 3.2 m) to the tank tops (2F, 4 m) is a stair of 0.8 m; the hall's
  mezzanine to the great tank's catwalk, level to level, a landing.
- **The thief walks on**: from where he left, through the way out, up or down a stair across
  the gap, to his spawn. The stair (steps 0.3 m high, 1.2 m wide) rises out of the void ahead of
  him and sinks behind him, and is gone before he stops. The way ahead is dotted in his colour.
  The real floors are marked at the stair's ends, from the world's `room.storey` (B3 to B2, 1F
  to 2F, 7F to B1).
- **The room he left is frozen as he left it, drawn by A's own code**: its state (the room but
  its wall map and sight segments, the guards, trains, keys, lights, the clock: 15,537 bytes) is
  copied on frame 0 (`tr_freeze()`) and swapped in around A's `draw_lights()`, `draw_trains()`,
  `draw_doors()`, `draw_things()`, `draw_cones()` once the runtime's room is the next one. A
  dark room's lit cones and dotted outlines, its levels, everything A draws, stay as they were.
  Each room's things are drawn only while its box is on the screen.
- **The next room is loaded a piece a frame** (A asked, 2026-10-15: with the aquarium dressed,
  loading a room was about a million cycles in one frame). Its textures are copied two a frame
  on frames 1-4 (its placements show once they are in); then A's `transition_ready_step()` runs
  one piece a frame on frames 5-8 (`tr_load_piece()`): the entities, the doors and sight
  segments, the framing, the entry at clock 0. Each piece is 5,000-110,000 cycles (release).
  The room is then drawn with its guards, cones, trains and doors at clock 0; it is dark until
  he crosses into it (unless he cleared it before on this run), then its lights come on and its
  name shows (E's `trans_caption()`).
- **The cones**: the next room's are A's `draw_cones()`, whose dark fans A keeps as meshes
  (`cone_cached()`); while the room is still off the screen its dark fans are built one a frame
  (`tr_cones_prebuild()`), not all on the frame it comes into view. The room left's are copied
  from A's kept meshes on frame 0 into a 64 KB pool of mine (`tr_cones_some()`) and drawn from
  there, since A keeps one fan per watcher and the next room's replace them.
- **The hand-over**: the camera arrives 3 frames before control (`TR_SETTLE`); those frames are
  drawn by A's `view_draw_room()`, so the frame before control and the first frame in control
  differ only in the HUD and the caption. The frames from the exit to frame 5 change only where
  the thief walks.

## Textures

A region's texture set is copied into its slots. **The worlds give the rooms a door joins
disjoint slot sets** (B's `levels/assemble.py`: two sets, `13-8,6-0` and `16-31`, when the rooms
can be coloured with two, else three; J's aquarium, whose doors make a cycle of seven rooms,
has three). Both rooms are then drawn textured the whole way, the next room's textures copied
two a frame on frames 1-4.

- **The transition does not depend on the sets**: `tr_slots_apart()` compares the two rooms'
  own slots, for any number of sets, any world. Should two joined rooms share a slot, it falls
  back to the stand-in and a one-frame swap half way (the pop the owner saw in
  `*_shared.png`), which `tr_split_off()` forces for the captures.
- **`tests/trans/check_slots.py BUILD`** checks every world in `worlds.txt`: each pair of rooms
  a door (or an exit and `next`) joins must have disjoint given slot sets and disjoint used
  slots. Today: station 2 pairs, tower 3, aquarium 8, store 4, level1 4, level2 4; none share.
  It replaces my `split_worlds.py`, gone now that the recipes carry the sets.

## Numbers

Release build (`TRAP=0`); frame budgets 1,000,000 CPU and 2,000,000 GPU cycles. Scenario 95
(`tests/trans/stages/`) plays each stage's solution tapes through every transition and fails
when a transition frame comes within 15% of a budget; `tests/trans/check.sh` runs all four.

| Worst transition frame, CPU / GPU | Before (the load in one frame) | After |
|---|---|---|
| The station (2 transitions) | 385,861 / 347,138 | 335,227 / 343,135 |
| The tower (5; dressed since) | 397,563 / 398,436 | 505,676 / 422,868 |
| The aquarium, dressed (9) | **1,001,175** / 631,990: over the budget, the first room's load | 661,893 / 778,992 |
| The store (7) | 613,592 / 492,234 | 515,867 / 475,466 |

E's scenarios measure the same transitions with their harness's own checks in the frame (the
fonts compared every transition frame): the aquarium's worst there is 804,823, the store's
630,871, the tower's 587,832.

- What a frame of the aquarium's costs now: both rooms' placements about 350,000 (2,500
  triangles), the kept fans (A's dots now in the mesh) a few thousand, the frozen state's
  copies about 30,000, a load piece up to 110,000 or one watcher's fan built up to about 190,000.
- RAM: 48 KB for the frozen and next rooms' states (`TR_STATE` twice), 64 KB for the room
  left's kept fans (`TR_CONE_POOL`; should it fill, its cones are drawn by `draw_cones()`).
- VRAM: the largest pair a door joins, the store's shop floor and food hall, 379,552 bytes in
  16 slots.

## The alternatives I tried

`tr_style()` (a weak function; the captures replace it): **TR_PAN** (the cart's); **TR_STEP**,
stepping back to 1.5 times the distance half way (66 frames: the rooms shrink and grow again,
like leaving the building); **TR_PAIR**, back until both rooms are whole (84 frames, 64 m to
108 m back: small models in a void, the picture the owner did not want).

## Captures and checks

```sh
make B=build-ah-H build-ah-H/mei build-ah-H/carts/afterhours.mei
MEIC=build-ah-H/meic RUN=build-ah-H/mei-headless WORLDS=build-ah-H/cart-worlds/afterhours \
  carts/afterhours/tests/trans/check.sh          # check_slots.py, scenario 90, scenario 95 x 4
MEIC=build-ah-H/meic RUN=build-ah-H/mei-headless WORLDS=build-ah-H/cart-worlds/afterhours \
  carts/afterhours/tests/trans/shots.sh          # the strips below
# one front end scenario with a setting replaced and a line a frame (camera, triangles, cycles):
TR_HEAD='fn tr_log() -> bool { return true }' TRAP=0 MEIC=build-ah-H/meic RUN=build-ah-H/mei-headless \
  WORLDS=build-ah-H/cart-worlds/afterhours carts/afterhours/tests/trans/run.sh 60 6400 /tmp/t60
```

**Scenario 95** (`tests/trans/stages/`): one stage (`STAGE`, a constant of `dr_levels.akr`)
started directly, its solution tapes played leg by leg (nobody catches), every transition's
hand-over checked, the worst transition frame printed, a failure when it is within 15% of the
budgets.

**Scenario 90** (`tests/trans/upper/`): the aquarium stage started directly, the thief put into
the first way out on the upper level of each room he comes into. Two transitions today: the
hall's mezzanine to the great tank's catwalk, and the catwalk up to the tank tops. Each must
hand over at clock 0 with the thief at his door's spawn on its level, within the budgets.

`tests/trans/shots/` (every 4th frame from the frame before the exit, four to a row):

| File | What |
|---|---|
| `station_1_to_2.png` | The last train's stair up to the ticket gates (B3 to B2) |
| `store_back.png`, `store_booth.png`, `store_lift.png` | The shop floor back into the staff corridor; the corridor's stair up to the booth; the lift down to the food hall |
| `aquarium_hall_to_great_upper.png`, `aquarium_great_to_tops_upper.png` | Doors on upper levels (scenario 90; the thief is put at the door, so the first frames' camera has not followed him there) |
| `station_1_to_2_shared.png`, `store_back_shared.png` | As it was with shared slots: the pop half way |
| `station_1_to_2_step.png`, `store_back_pair.png` | TR_STEP and TR_PAIR |
| `old_lobby_to_aquarium.png`, `old_stage2_back.png` | E's pull-back (every 6th frame), made once from `git show HEAD:carts/afterhours/dr_trans.akr` on 2026-10-15 |

E's `tests/front/check.sh` passes (its scenarios read `tr_ready`, `tr_clock_ok`, `tr_skipped`
and `TR_N`, which keep their meanings).

## Agreed with A and J (and what I ask)

- **A**: (0) Loading uses A's `transition_ready_step()`; the room left's cones repeat
  `draw_cones()`'s loop only to copy each fan (A's `cone_cached()` mesh, or the plain fan).
  (1) The frozen room is A's state swapped in around A's draw functions; `tr_parts()`
  lists what is copied (the room but `walls`, `wps`, `segs`, `bands`; `guards`, `trains`,
  `shells`, `nshell`, `thief`, `toys`, `bells`, `fragile_down`, `fragile_at`, `light_lit`,
  `att_taken`, `att_open`, `door_t`, `card_t`, `clock`, `phase`, `best`). A new global those
  draw functions read belongs in that list; tell me, or add it there. (2) `tr_people()`
  repeats `draw_people()` without the thief (the transition walks him): if A splits
  `draw_people()` into the watchers, the thief and the ghost, I will call A's. (3) The camera:
  I read A's `cam_eye(cam_x, cam_tz)` at both ends, so framing both levels of a two-level room
  (A's "the camera frames both levels") needs nothing from me as long as it goes through
  `cam_eye()`. (4) With shared slots only, the transition writes `wp_region_loaded` before
  `transition_ready()` and enters the region itself half way.
- **J**: a door on level 1 is drawn at the room's floor plus `upper`; its `spawn` should carry
  the same `level` (A puts the thief on his door's level). A door in a side wall joins the rooms
  side by side, one in the back wall leading up puts the next room behind. Three slot sets
  work; `check_slots.py` checks them when the rooms are textured (greyboxes take no slots).
- **E**: the strips in `tests/front/shots.sh` start at frames of the old 90-frame transitions;
  `tests/trans/shots.sh` finds its frames from each run.
