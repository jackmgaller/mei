# Agent E's notes: the front end

The transition between rooms, the title, the stage select with its section model, the stage's
end and the save. Kept current. A's side is in `NOTES_A.md` ("Hooks for E and F"), F's in
`NOTES_F.md`.

## Status (2026-10-15, in the worktree `afterhours-next`)

- **In the cart**: `afterhours.akr` imports `dr_front.akr`. The cart opens on the title; START
  goes to the stage select; A plays the hovered stage; each room's exit pulls back into the next
  room; the last exit shows the stage's end; A goes back to the select, the next stage unlocked.
  Progress is saved to the memory card.
- **Checks**: `tests/front/check.sh`, 6 scenarios (60-65), about 25 s; `tests/check.sh` runs it
  at its end. All pass, with A's 27.
- **Captures**: `tests/front/shots/` (`tests/front/shots.sh` makes them, about 40 s).

## Try it

```sh
make B=build-ah-E build-ah-E/mei build-ah-E/carts/afterhours.mei
build-ah-E/mei --no-boot build-ah-E/carts/afterhours.mei
MEIC=build-ah-E/meic RUN=build-ah-E/mei-headless WORLDS=build-ah-E/cart-worlds/afterhours carts/afterhours/tests/front/check.sh
MEIC=build-ah-E/meic RUN=build-ah-E/mei-headless WORLDS=build-ah-E/cart-worlds/afterhours carts/afterhours/tests/front/shots.sh
python3 carts/afterhours/art/make_front_art.py [--preview DIR]     # the fonts and the save icon
```

Pad: d-pad up and down to choose a stage, A (or START) to play it, B back to the title; A or
START skips a transition. Keyboard: arrows, J = A, K = B, Enter = START.

## The transition

`dr_trans.akr`. 90 frames (1.5 s) from the frame the thief steps into the exit to the frame he
is in control at the next room's clock 0:

| Frames | What is drawn | What happens |
|---|---|---|
| 0-29 | The room left as the game draws it (placements, the thief at the exit, the guards and cones where they were); the others as their stand-ins | The camera pulls back from 28 m toward 50-140 m (far enough to hold both rooms, across and up), its pitch from 60 to 33 degrees, its field of view from 20 to 24, and slides to between the two rooms. `au_transition()` on frame 0 |
| 30-49 | Every room as its stand-in | One of the next room's textures is copied into VRAM a frame (the room left's go, so nothing textured of it shows from here) |
| 50-89 | The next room as its placements, with its guards, trains and cones at clock 0; its name under it | `transition_ready()` (A's): its entities read, its region entered. Its lights come on. The camera slides on and drops in |
| 90 | (A's frame) | `transition_control()`: Mode.Play, clock 0, the thief at his door |

- **Lights**: the rooms cleared on this run are lit, the rooms ahead dark (their regions'
  palettes dimmed to 38% toward night blue, `section_light()`); the next room's come on at frame
  50, when its region is entered.
- **The route**: dotted, in the thief's orange, from the exit to the next room's door, drawn out
  over frames 11-56.
- **The camera** ends exactly on A's (`cam_x`, `cam_tz` after `view_restart()`), so the hand-over
  does not move. Before frame 50 it aims at an estimate of the next room's framing from the
  section's numbers (`cam_goal()`'s rule for x, this room's offset in z) and blends to the exact
  one over frames 50-76.
- **Skip**: A or START from frame 8: `au_transition_skip()`, then `transition_ready()` and
  `transition_control()` in that frame.
- **The world's rooms** are drawn in place: each room's cell is drawn by `dr_section.akr` with my
  own camera (not `wp_draw()`, whose near pass covers only the 3 × 3 cells round the eye, which
  at 100 m back holds no room).
- A stand-in room (A's tests) gets no transition (`fe_owns_transition()` is false).

**Measured** (scenario 60, release build, the whole of stage 1 from the title):

| Frames | Worst CPU | Worst GPU |
|---|---|---|
| The transitions (4) | 528,592 (53%: the aquarium's ready frame, frame 50: A's entity read and region entry, with 4 stand-ins and the aquarium drawn) | 439,880 (22%) |
| A skipped transition (scenario 64; the ready frame with every texture copied) | 252,103 | 305,860 |
| The title | 263,706 | 348,632 |
| The select (the frame a hovered stage's world is opened: about 100,000 of it) | 376,864 | 459,489 |
| The end | 297,142 | 365,835 |
| Play (A's, for comparison) | 375,129 | 459,690 |

No frame dropped. The stage takes 4,786 ticks with or without the transitions (they do not
tick). Before, the door into the aquarium cost 395,774 CPU on its own frame; now its textures
are copied over frames 30-33, one a frame (up to 32 KB, about 56,000 cycles, each).

## The section model

`dr_section.akr`, for the transition, the select, the end and later a pause map:

- `section_read()`: the open world's rooms in the run's order (as `dr_world.akr` orders them), each
  with its cell, region, centre, size, door and exit.
- `section_room(k, full)`: room k as its kit-made stand-in, or its placements (when `full`, or
  when the world has no stand-ins: the platform's).
- `section_view(x, y, w, yaw, pitch, route, silhouette, lit)`: **the whole stage as a small model
  in any screen box** (what a pause map needs: call it from the pause screen's draw with the
  stage's world open). The rooms packed side by side 3 m apart (the world's 32 m between cells
  closed up) and a rise of more than 9 m between two rooms closed up to 9 (the 40 m of tower
  between the lobby and the roof), seen from 60 m with a 14-degree field of view, near
  isometric. Lit rooms by `lit`; the route through them in orange (the others' in grey-blue);
  a locked stage as a flat silhouette (the GPU's fog at full, `gpu_fog(..., 0, 1)`); a stage
  with no room cleared dimmed by the fog at about 60%.
- Lit and dark rooms are their regions' palettes (every region of a world has its own colour
  range, all loaded at once). This dims what the stand-ins draw (far colours, palette-backed);
  a greybox's vertex colours do not dim, so a stage with nothing cleared is dimmed by the fog
  instead.

The model turns slowly: 26 degrees either side of the front over 14 s, not a whole turn, since
the rooms' fronts are cut at 1 m and their backs stand 2.4 m: from behind, a room is its back
wall.

## The menus

`dr_menu.akr`. The fonts are Belleza (the title) and Sofia Sans Condensed SemiBold (headings),
from `tools/fonts/`, baked by `art/make_front_art.py` into texture slot 7 (palettes 250-251);
numbers and small lines are the stdlib's pixel font.

- **Title**: stage 1's model, every room lit, "AFTER HOURS", "TOKYO 1998", PRESS START. The
  stage track plays under it; the room's ambience is off (`au_ambience(AMB_NONE)`, F's).
- **Stage select**: the stages down the left (number, name, best total and restarts, or "Not
  cleared yet", or "LOCKED" and "Clear stage n to open"); the hovered stage's model on the right;
  under it its rooms in two columns, a lit square for each cleared room and its best time. A
  locked stage cannot be played (`au_menu_deny()`). Hovering a stage opens its world
  (`level_open_n()`); picking one fades out and calls `stage_start()`, and the first room fades
  in. "NO MEMORY CARD" shows when there is none, "SAVING" while a write runs.
- **The stage's end** (Mode.End): STAGE CLEAR, the model with the whole route, each room's time
  and restarts, the total, "NEW BEST TIME" on a replay that beat it, and the stage it opened. A
  goes to the select with the opened stage hovered.
- **The stages** are A's levels in order (`STAGES` in `dr_menu.akr`, `level` equal to the index):
  stage 1 "PLATFORM TO ROOF" (level 1), stage 2 "THE WAY HOME" (Gate 1's platform). When stage 2
  of DESIGN.md (keycards) gets its world, it is a row in `STAGES` and its rooms' names in
  `ROOM_NAMES`, once A adds the level to `dr_levels.akr`.

## The save

`dr_save.akr`: save number 0, 424 bytes (2 blocks), title "AFTER HOURS" and a 3-frame icon (a
tower in section, its floors lighting up, the thief's orange on the roof; `art/save_icon.bin`).
Per stage: cleared, unlocked, the rooms ever cleared, each room's best clearing time, the
stage's best total and fewest restarts, runs finished. Read at boot (`card_load()`); written in
the background (`save_flush()` once a frame from `fe_draw()`: a write starts when the save
changed and the card is idle, so no frame waits on the card) after each room's exit and at the
stage's end. A card with no save, or another version, gives a fresh one (stage 1 open). The
ghosts' tapes are not saved (DESIGN.md wants them; a later version).

## Checks (`tests/front/`)

Their own harness, since `tests/harness.akr` replaces the same hooks for A's scenario 48.

| Scenario | Checks |
|---|---|
| 60 | Stage 1 from the title (release build): START, A, four transitions of 90 frames, each handing over at the next room's clock 0 with the thief at his door and the clock held at 0 from ready to control; the stage's 4,786 ticks; the save (cleared, five rooms, bests, stage 2 unlocked) written and read back from the card byte for byte; the select after it (stage 2 hovered, then stage 1 with every room lit); every frame of the transitions, the title, the select and the end within the CPU and GPU budgets; no frame dropped |
| 61 | A blank card gives a fresh save; with rooms 1 and 3 of stage 1 cleared their palettes are the world's and the others' dimmed; stage 2, locked, is drawn as a silhouette (the fog on) and A does not play it |
| 62, 63 | The round trip across two boots on one card: 62 writes a known save, 63 boots and reads it |
| 64 | Skipping with A after 20 frames: control at once, room 2 at clock 0, its region loaded, then it runs; the frame within the budgets |
| 65 | Stage 2 (one room, no stand-ins): unlocked by the save, dimmed before it is cleared, played with B's tape, its end, its save, the select with its room lit |

## For the owner

- **Look at**: `tests/front/shots/transition_1_to_2.png` and `transition_4_to_5.png` (every 6th
  frame), `title.png`, `select_*.png`, `end.png`.
- **The pop at frame 30**: the room left changes from its placements to its kit-made stand-in
  (the stand-ins draw far colours, the mean of each texture), by then about a third of its size.
  It has to: from frame 30 the next room's textures replace its own. Moving it later lengthens
  the transition or crowds the texture copies.
- **The model turns 26 degrees either side**, not a whole turn (above). A whole turn is a
  one-line change (`menu_yaw()`).
- **Names are mine**: "PLATFORM TO ROOF", "THE WAY HOME", "TOKYO 1998", the rooms' names (from
  ROUTE.md). A name field on the room type would let each world carry its own (B).
- **The title** has the stage track and no ambience; F's notes say how to make it silent.

## Requests

- To B: a `title: name` field on the `room` type, so the select and the transition read rooms'
  names from the world instead of `ROOM_NAMES`. Optional.
- To A (later): a pause menu can show the map with `section_view()`; the stage's world is open
  while it plays, so it needs only `section_read()` once and a screen box.

## Files (mine)

| File | What |
|---|---|
| `dr_front.akr` | The hooks (`fe_start`, `fe_update`, `fe_draw`, `fe_draw_room`, `fe_owns_transition`, `fe_event`) and the imports |
| `dr_trans.akr` | The transition |
| `dr_section.akr` | The section: reading a world's rooms, drawing them in place or as a model, their lights, the route |
| `dr_menu.akr` | The title, the stage select, the stage's end, the transition's caption; the stage table |
| `dr_save.akr` | The save |
| `front_art.akr` | Generated by `art/make_front_art.py`: the fonts' and the icon's embeds |
| `art/make_front_art.py`, `art/front_title.fnt`, `art/front_head.fnt`, `art/save_icon.bin` | The generator and what it writes |
| `tests/front/harness.akr`, `run.sh`, `check.sh`, `shots.sh`, `shots/` | The scenarios and the captures |
| `NOTES_E.md` | This |
