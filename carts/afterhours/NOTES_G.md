# Agent G's notes: the dash

The owner (2026-10-15): "I think a dash could be fun. A lot of times you're moving slowly. It
could add a little more sauce and complexity." This is the design, why, what was built, and what
it changed in other agents' files. Kept current.

## The design (written before building)

**X: a short committed slide.** Press X and the thief throws himself 2 m in a straight line in
0.2 s, low to the floor, then takes a breath before he can move again. It is a burst for
crossing a gap, not a faster way to travel, and it costs a small noise where he lands.

| | | Why |
|---|---|---|
| Button | **X** (keyboard U). A press starts it; holding does nothing more | X and Y are free; X sits beside A under the right thumb, and the left thumb keeps steering. R is a hold (run), so the dash wants a press of its own |
| Direction | The stick or d-pad at the press, made a unit vector (a half-tilted stick dashes as far as a full one); with nothing held, the way he faces | A dash from standing still has to go somewhere, and he faces the way he last moved |
| Distance and speed | **2.0 m over 12 ticks**, fast then slowing: 0.24, 0.24, 0.24, 0.22, 0.20, 0.18, 0.16, 0.14, 0.12, 0.10, 0.08, 0.08 m. Peak 14.4 m/s, mean 10 m/s | 2 m is about one cone's width at 3-4 m from a guard, and a pillar's shadow is about as deep: enough to cross one, not two. Easing out reads as a slide that lands, not a teleport |
| Committed | No steering and no stopping once started; R, A, B and L do nothing during it | The cost of the speed is that you choose before you go. It is what makes it a puzzle move rather than a faster walk |
| Recovery | **8 ticks** after it, standing (drawn crouched): input does nothing | He lands exposed for a moment; a dash into the open next to a turning head is a real risk. Short enough not to feel sluggish |
| Cooldown | **60 ticks (1 s)** from one press to the next | Chaining dashes with walking between is 3.6 m/s, between the walk (2.4) and the run (4.8): useful for open floor, never better than running for distance |
| Noise | **A skid where he stops: one noise of 3.0 m** (half the 6-7 m the guards hear a run), at the end of the slide or where a wall stopped it. Silent while sliding; not a run (no run ring) | A cost you can plan with: dash where no guard stands within 3 m. Dashing right behind a guard's back (the classic sneak) brings him round. The noise is at the landing, not the start, so it is never a free lure |
| Walls | Each tick's slide is three substeps, each at most 0.08 m (the run's step), each pushed out of walls, tracks and open trains as walking is. A substep that is held to less than half its length ends the dash: a bump, then the skid noise and the recovery. At a slant he slides along the wall as walking does | Collision is position-push, not swept: a step of more than about 0.33 m could pass through a 0.06 m glass screen. No substep is longer than a run's step, so the dash passes no wall a run cannot |
| Seen | **Every point of his path is tested.** After the fans are cast (the tick's usual order), the substep points of this tick are tested in order against the drawn fans; at the first one a fan covers, he stops there and is caught. Touch is tested as before. Walking and running are one point a tick, so nothing changes for them | The drawn cone is the test. At 0.24 m a tick a dash could otherwise skip across a cone's narrow end near the guard with no tick inside it. Stopping him at the covered point means the freeze shows him inside the red cone, under the "!" |
| Limits | Not while hidden (X does nothing), not in the caught freeze. Through a door or the exit as walking (their boxes are 0.4 m deep or more; a tick moves at most 0.24 m, so none is skipped) | |

**How it reads at 23 px tall:** during the slide he is drawn low (three quarters of his height)
with three afterimages behind him in his orange, fading (where he was 2, 4 and 6 ticks before).
Where he stops, the skid's ring opens to 3 m over half a second like the bell's and the fragile
things' rings, so the player sees how far it carried. During the recovery he is drawn crouched
(0.85). When the dash is ready again, a small orange ring closes onto his feet (8 ticks): no HUD
needed, so nothing in A's HUD changes.

**What it should do to the puzzles.** The rooms are timing windows on a clockwork. The dash
tightens the window a crossing needs (2 m in 12 ticks instead of 25 running or 50 walking), so
a player who has learned a room can cut a wait short or slip a gap the intended route waits out.
It does not cross two cones, it cannot go behind a guard unheard, it lands you standing for 8
ticks, and you get one a second. The existing tapes never press X, so they replay as before.
Whether it makes stage 1 too easy is for the owner to judge by playing it.

## Sounds for F

| Hook (weak in `dr_dash.akr`, F replaces it in `dr_audio.akr`) | When | The sound |
|---|---|---|
| `au_dash(dx: fixed)` | The tick the dash starts | A quick push-off: a cloth whoosh and a soft sneaker squeak, short (about 0.2 s, the slide's length) |
| `au_dash_end(bump: bool, dx: fixed)` | The tick it ends (the skid noise is made then) | `bump` false: a short rubber skid; true: a soft body thud into a wall. Both quieter than the run's heel strikes |
| `au_dash_ready(dx: fixed)` | The tick the dash is ready again (60 ticks after the press) | Optional, very quiet: a tiny tick or breath, or nothing |

`dx` is `thief.x - cam_x`, as for F's other calls. `au_thief(moved, ...)` is given `moved = 0`
during the slide and the recovery, so no footsteps play under the dash.

## For B's model (`levels/rules_model.py`)

Nothing needs changing for the existing tapes (none press X). For tapes that dash, the model
needs, in the thief's update (A's tick order: the trains, the thief, the keys, the tools, the
guards, the fans, the test):

1. A press of X (bit 64; pressed = held and not held the tick before), not hidden, not dashing
   or recovering, and `clock >= ready_at`: the dash starts on this tick. Direction: the input's
   move vector (`input_move`) divided by its length; if it is zero, `(sin head, cos head)`.
   `head = heading_to(dx, dz)`. `ready_at = clock + 60`.
2. On dash tick k (0..11, k = 0 on the press tick): d = `DASH_STEP[k]`; three substeps of
   s = d / 3, each `p = solid_push(x + dx s, z + dz s, 0.3)`; the point is kept for the test.
   If a substep moved less than s / 2, the dash ends after it (a bump). Footsteps' stride is not
   advanced; it is not running.
3. On the dash's last tick (k = 11, or a bump): one noise of radius 3.0 at his position (heard
   by any patrol or posted guard within 3.0 m, whatever his `hear`), then 8 ticks of recovery in
   which input does nothing (no movement, no A, B, L, X; START still restarts).
4. The fragile things, the cards, the doors and the exit are tested at his position at the end
   of the tick, as for walking.
5. After the fans are cast: the kept points in order; the first one any fan covers (centre
   test, not hidden) becomes his position. Then the usual test (seen, touched, the doors).

## Built

Built as designed (2026-10-15), with one change after the captures: the slide's figure leans
0.2 m a metre of height at 0.8 of his height (0.3 and 0.75 read as a falling log), the recovery
0.08 at 0.85.

**Files (mine):** `dr_dash.akr` (the rules, the drawing, F's weak hooks), `tests/g_dash.akr`
(scenarios 70-78), `tests/g_shots.sh` (the captures), and in `dr_thief.akr` (A said it is not
touching it): `import "dr_dash.akr"`, `dash_reset()` in `thief_reset()`, `dash_tick_start(t)`
and `dash_busy()` in `thief_update()`, and the fragile things' test moved into
`fragile_touch(x, z, t)` (the same test, now also called for each point of a slide).

**Changed in A's files** (each one line, marked `agent G`):

| File | Line | Why |
|---|---|---|
| `dr_game.akr`, `tick()` | `dash_path_test()` after `sight_cycles = ...`, before `tape_record` | the path test needs the tick's fans; before the record, so the ghost's track holds the point he was stopped at |
| `dr_view.akr`, `draw_people()` | `} else if !dash_figure() {` in place of `} else {` before the thief's `mesh_at` | the dash draws him while he slides or recovers. Not the HUD |
| `dr_view.akr`, `draw_rings()` | `dash_rings()` before its `depth_offset(0)` | the skid's ring, the dust, the ready ring, drawn with the other noise rings |
| `tests/harness.akr` | `import "g_dash.akr"`; `else => g_init()` in `test_init()`; `else => g_scenario(f)` in `scenario()` | my scenarios in a file of my own |
| `tests/check.sh` | `run 70 200` ... `run 76 500`, and the `DASH` and `ROUTE` lines printed | `check.sh` runs them |

No event was added to `Ev` (E's and the harness's matches stay as they are); E can read
`dashing()`, `dash.rec` and `dash.ready_at` if a HUD cue is wanted later.

**Checks** (`tests/check.sh`, all passing with A's 32 and E's 7):

| Scenario | What it checks |
|---|---|
| 70 | 2.0 m (within 3 mm) over 12 ticks, each tick its `DASH_STEP` (36 ticks checked); down held through the slide and the recovery does not steer it; 8 ticks standing; X in the cooldown does nothing; X held 66 ticks dashes once; with no stick, the way he faces; a half-tilted diagonal stick (s8 59, -29) dashes the full 2 m its way |
| 71 | No noise on any slide tick but the last; then exactly one, 3.0 m, where he stopped. Every patrol and posted guard goes to it exactly when within 3 m: the posted guard 4.0 m off does not (he hears a run at 5.9 m), 2.5 m off he does, alone |
| 72 | Into the pillar at x 3: stopped at x 2.4 (its face less his radius), a bump, ended early, the skid there, then the recovery, never past the face on any tick. Into the 0.06 m glass screen: stopped at -10.27, never into it. At a slant against the platform's edge (the track solid behind it): held at z 2.7, slides on 1.7 m or more, all 12 ticks, no bump |
| 73 | A 900-tick tape with six dashes (one through a fragile thing, which knocks it over; one into a pillar), walking and a run: the replay after START matches on every tick, the dash's state and the fragile things included |
| 74 | A posted guard's fan 10 degrees wide, fixed; a dash across it 0.8 m from him, where two ticks' ends (z 1.51, 1.69) both lie outside it: caught on the slide's 6th tick at the first substep inside (z 1.57), stopped there; the drawn fan is the fan tested and covers him; on every tick before, no drawn cone covered him or any point of his path; the replay after the restart is caught on the same tick at the same point |
| 75 | Six dashes round B's platform: the frame budget and the dash's own cycles (below) |
| 76 | A route: B's tape for level 1's first room with X pressed at clock 335 (on the walk to the stair) clears on tick 347 instead of 385, never caught |

77 and 78 are captures (`tests/g_shots.sh`): `tests/shots/dash_strip.png` (a dash in level 1's
first room: the tick before, the slide every 2 ticks, its end, the recovery, the skid's ring, the
ready ring at +61) and `tests/shots/dash_caught.png` / `_x3` (74's catch: stopped inside the
narrow fan, the "!" over him).

**The existing tapes are unchanged and clear as before**: the platform's three (1, 14, 15),
level 1's five and the run (41-46: 4,786 ticks), stage 2's eight legs (63, 64: 10,216 ticks). None
presses X, and with no dash `dash_path_test()` returns at once.

**Measured** (B's platform, scenario 75):

| | Debug (`--trap-fmul`) | Release (`TRAP=0`) |
|---|---|---|
| The dash's worst tick (three substeps' `solid_push` against the walls, the path test) | 12,398 cycles | 8,709 cycles |
| The worst frame of a run with six dashes | 343,141 CPU, 326,300 GPU | 270,585 CPU (A's solutions' worst: 269,513) |
| A tick without a dash (the calls alone) | up to about 800 more than before (level 1's run: 498,998 against 498,217) | |

**What a dash does to a room, so far:** in level 1's first room a dash anywhere on the walk to
the stair saves 24-38 ticks of 385 (10 %) and is never caught; it cannot shorten the wait for
the guard to turn away, which is the room's puzzle. Untried on stage 2's rooms: B's model needs
the dash first (above) to look for new routes properly.

## For the owner

- The numbers to judge with a pad: 2 m, 12 ticks, 8 ticks of recovery, 1 s between dashes, a
  3 m skid. All are constants at the top of `dr_dash.akr`.
- Whether the skid noise is the right cost, or whether the dash should be silent and rarer
  (a longer cooldown, or a charge or two a room shown on the HUD).
- The path test: a dash through a cone is caught even if it would end beyond it. It closes the
  narrow ends of cones to a dash; walking and running are unchanged.
- No sound yet: F has the list above.
- The control is X (keyboard U); `afterhours.akr`'s header comment and any controls screen
  should say so (A's and E's files).
