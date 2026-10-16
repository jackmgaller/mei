# Agent E's notes: the front end

The title, the stage select with its section model, the stage's end, the pause, the save, and the checks
of all of these (the transition between rooms was mine until 2026-10-15; it is agent H's now,
`NOTES_H.md`). Kept current. A's side is in `NOTES_A.md` ("Hooks for E and F"), F's in
`NOTES_F.md`.

## Status (2026-10-15, in the main checkout)

- **In the cart**: `afterhours.akr` imports `dr_front.akr`. The cart opens on the title; START
  goes to the stage select; A plays the hovered stage; each room's way out goes through H's
  transition into the next room; the last shows the stage's end; A goes back to the select, the
  next stage unlocked. Progress is saved to the memory card. In play, START opens the pause
  (below); SELECT restarts the room at once.
- **Checks**: `tests/front/check.sh`: the worlds' guard (`check_worlds.py`), then 13 scenarios
  (60-72), about two minutes; `tests/check.sh` runs it at its end. All pass.
- **Captures**: `tests/front/shots/` (`tests/front/shots.sh` makes them, about 40 s).

## The fonts' slot and palettes (2026-10-15, after the owner's stage 2 end screen)

The front end's fonts are loaded once, at boot, into **texture slot 7 and 4-bit palettes
250-251** (`art/make_front_art.py`). Stage 2's dressed rooms, on the kit's default slots, copied
textures into slot 7 and the menus' text became noise. B now reserves both in all three world
recipes (`"textures": {"slots": "13-8,6-0,16-31"}`, `"palette": {"reserved": [250, 251]}`).
Two checks keep it so:

- **`tests/front/check_worlds.py`** (standard library; `tests/front/check.sh` runs it first):
  reads the slot and palettes from the fonts' headers and every world's `report.json` (through
  the cart's `worlds.json`), and fails naming the world and region whose texture set uses the
  slot, or whose palettes (its 4-bit palettes, its colour run, its textures' 4-bit and 8-bit
  palettes) reach those palettes.
- **In the scenarios**: 60, 65 and 66 compare the fonts' texture rows and palettes in VRAM with
  `front_art.akr`'s blobs on every select frame, every transition frame once the next room is in
  (its caption is drawn over it) and every end frame.

Checked both ways: with the worlds built from the committed recipes (before B's reservation) the
guard fails (`level2`, regions `foodhall` and `shopfloor`: a texture in slot 7) and scenario 66
fails at frame 2,734 (the transition into the shop floor); with B's recipes both pass.

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

## The transition (agent H's since 2026-10-15)

`dr_trans.akr` is H's (`NOTES_H.md`: a pan at the game's own scale, the two rooms joined at
their doors, 54 frames). What stays mine around it: `trans_caption()` (the next room's name, in
`dr_menu.akr`), `section_light()` and the section's reading (`dr_section.akr`), and the
scenarios that play through it (60, 64, 66), which read its `tr_ready`, `tr_clock_ok`,
`tr_skipped` and `TR_N`. The strips in `tests/front/shots/` start at frames 459 and 2,023 of
scenario 60 and 4,454 of scenario 66, 60 frames each.

**Measured** (release builds, 2026-10-15, the dressed aquarium; scenarios 60, 69, 67 and 66: each
stage from the select through its legs to its end; no frame dropped):

| Stage | The select (its worst: the A press, `stage_prepare()` and the model) | The end (its first frame) | The transitions (H's) |
|---|---|---|---|
| The station | 443,537 CPU, 365,019 GPU | 510,762 / 359,808 | 435,235 / 344,119 |
| The tower | 470,737 / 349,480 | 468,504 / 346,437 | 400,127 / 390,372 |
| The aquarium | 691,237 / 406,008 | 652,337 / 398,056 | 834,029 / 618,930 |
| The store | 667,486 / 379,518 | 676,594 / 381,100 | 618,649 / 477,698 |

**The stage's start** is spread over the select's fade-out (2026-10-15, with A): the A press calls
A's `stage_prepare()` (the world opened bare), each fade frame `stage_prepare_step()` (one of the
first room's textures), and the last `stage_start()`, which then opens nothing again; on that
frame the room is not drawn (`fe_draw_room()` is false while the screen is black). Before, that
one frame was 1,041,439 CPU for the dressed aquarium (a frame dropped, scenario 67); now it is
about 330,000.

**The menus open worlds for display only** (`world_show()` in `dr_menu.akr`, 2026-10-15): the
pack, its swatch and every region's palettes, no region entered, so no texture is copied (the
stand-ins draw palette-backed far colours). A world of one region with textures and no stand-ins
(its model draws its placements) gets its textures one a frame, its model held back until they
are in. Scenario 68 hovers every stage 40 frames and prints each one's frames (release build):

| Stage | The frame opening its world | The other frames, worst CPU / GPU |
|---|---|---|
| The station | (open already: the title's) | 363,042 / 218,056 |
| The tower | 344,698 | 320,052 / 204,298 |
| The aquarium | 557,913 | 504,637 / 261,521 |
| The store | 545,913 | 516,227 / 234,521 |
| The platform | 241,862 | 235,314 / 177,479 |

What remains is the model itself: about 120 cycles a stand-in triangle, and the aquarium's
eight and the store's five stand-ins are 4,000-5,600 triangles. Lower stand-in caps in the
world recipes would make it cheaper (the model is about 25 px a room).



## Stages of doors (A's runtime for stage 2, 2026-10-15)

For A's rooms of doors (NOTES_A.md) and B's `level2` (the store). Scenario 66 plays it from the
select with B's eight legs: seven transitions (rooms 2 -> 3 -> 2 -> 1 -> 2 -> 3 -> 4, numbered
from 0: back into lower rooms too), each handing over at clock 0 at the door he comes in by.
- **The section** reads rooms with no exit box (`exit` is `ref?`), the rooms off the `next`
  chain (in entity order, as A's `level_rooms()`), and each room's doors with where they lead; in
  the model a room of doors shows its doors, each dotted to the room it leads to.
- **Names** come from each room's `name` in the world (`the_last_train` shows as THE LAST
  TRAIN); `ROOM_NAMES` only when a world gives none.
- **The save**: in a stage of doors `room_time` sums every visit, so a room's bit is saved as he
  leaves it and its best (that sum) at the stage's end.
- **The stage table** follows `LEVELS` (below, "The menus").

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

- **Title**: stage 1's model, every room lit, "AFTER HOURS", "TOKYO 1990", PRESS START. The
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
- **The stages** are A's levels (dr_levels.akr's `STAGE_STATION`, `STAGE_TOWER`,
  `STAGE_AQUARIUM`, `STAGE_STORE`, `PLATFORM_LEVEL`); the select lists them in A's order, each
  row in `STAGES` (`dr_menu.akr`) keyed by its constant: "THE STATION", "THE TOWER", "THE
  AQUARIUM" (J's), "AFTER CLOSING" (the store), "THE WAY HOME" (Gate 1's platform). The names
  are placeholders (the game's title and stage names are open). A new stage is a row there with
  a save slot of its own. Up to about six fit the list (22 px a stage).
- **Save slots** are fixed per stage, whatever the order (`StageDef.save`: 0 the station, 1 the
  tower, 2 the aquarium, 3 the store, 4 the platform), so inserting a stage keeps everyone's
  progress. The save went to version 2 with this (2026-10-15); a version-1 save reads as fresh.
- The station's passage shows small in the models: its kit-made stand-in left out its main
  placement (246 triangles, `left_out` 1 under the 700 cap in `station.world.json`'s
  `standins`); a cap of about 900 for that cell would bring it in (B).

## The save

`dr_save.akr`: save number 0, 424 bytes (2 blocks), title "AFTER HOURS" and a 3-frame icon (a
tower in section, its floors lighting up, the thief's orange on the roof; `art/save_icon.bin`).
Per stage: cleared, unlocked, the rooms ever cleared, each room's best clearing time, the
stage's best total and fewest restarts, runs finished. Read at boot (`card_load()`); written in
the background (`save_flush()` once a frame from `fe_draw()`: a write starts when the save
changed and the card is idle, so no frame waits on the card) after each room's exit and at the
stage's end. A card with no save, or another version, gives a fresh one (stage 1 open). The
ghosts' tapes are not saved (DESIGN.md wants them; a later version).

## The pause (2026-10-15, `dr_pause.akr`)

START in the Play phase calls A's hook `fe_pause()` (`dr_hooks.akr`), which sets
`Mode.Pause` and returns true; in a stand-in run it returns false and START restarts the room,
as A's tests expect. **SELECT restarts the room at once** (A's `room_restart()`, called from the
Play phase), so the quick restart needs no menu. START and SELECT are masked out of the tick's
input, so neither is ever in a tape.

- **Rows**: RESUME (also B or START), RESTART ROOM (`room_restart()`: from the room's door, a
  restart counted, the attempt kept as the ghost if best), RESTART STAGE (the stage from its first
  room, the run's time and restarts from 0; the world reopened with A's `stage_prepare()` over a
  fade, as the select does), STAGE SELECT (the run left; the select on this stage), CONTROLS.
- **The map**: the stage's section model at the select's angle (`section_view()`), the rooms
  visited on this run lit (`run_visited` and the room he is in), the others dimmed, the route
  through them traced, and a blinking mark where the thief stands. Under it, the room's number and
  name. With CONTROLS chosen, the controls take the map's place: the pad's buttons and what they
  do, then the keyboard's.
- **The clock**: in `Mode.Pause` A's `update()` ticks nothing, so the room's clock, the run's time,
  the watchers, the fans and the trains stand still and paused time is not counted. The header
  shows the room's clock, the run's time and the restarts as they stopped.
- **Sound**: F's `au_pause(true)` on opening, `au_pause(false)` on every way out.
- **Tapes stay exact**: nothing ticks while paused, and the menu hands back to play only once A,
  B and START are released, so the button that closed it is never a press on the first tick after
  (scenario 70 checks a tape against itself with a pause in the middle, tick for tick).
- **Measured** (release, the aquarium, 72): worst paused frame 347,139 CPU, 231,799 GPU. The map
  is the select's model, and the stage's world is already open.

## Checks (`tests/front/`)

Their own harness, since `tests/harness.akr` replaces the same hooks for A's scenario 48.

| Scenario | Checks |
|---|---|
| 60 | The station from the title (release build): START, A, two transitions of `TR_N` frames, each handing over at the next room's clock 0 with the thief at his door and the clock held at 0 from ready to control; the stage's time its rooms'; the save (slot 0: cleared, three rooms, bests, the tower unlocked) written and read back from the card byte for byte; the rooms' names from the world; the select after it (the tower hovered, then the station with every room lit); every frame of the transitions, the title, the select and the end within the CPU and GPU budgets; no frame dropped |
| 61 | A blank card gives a fresh save; with rooms 1 and 3 of the station cleared their palettes are the world's and room 2's dimmed; the tower, locked, is drawn as a silhouette (the fog on) and A does not play it |
| 62, 63 | The round trip across two boots on one card: 62 writes a known save, 63 boots and reads it |
| 64 | Skipping with A after 20 frames: control at once, room 2 at clock 0, its region loaded, then it runs; the frame within the budgets |
| 66 | The store (rooms of doors; reached at A's `STAGE_STORE`, the stages before it cleared) from the select with B's eight legs (release build): seven transitions into the rooms the ways out lead to, lower ones too; each hands over at clock 0 at the door he comes in by; the end, the save (its five rooms, its total), the platform stage unlocked; every frame within the budgets |
| 67 | The aquarium (J's: rooms of doors, two on two levels, entered twice) the same way with J's ten legs (release build): nine transitions, the end, the save (all eight rooms), the store unlocked; every frame within the budgets |
| 68 | Every stage open, each hovered 40 frames (release build): the frame opening its world for the model and the others under 700,000 CPU and the GPU's budget, each printed; no frame dropped |
| 69 | The tower (rooms of doors, the lift hall entered twice) the same way with B's six legs: five transitions, the end, the save, the aquarium unlocked |
| 70 | A tape with a pause in the middle (release build): the station's room 1 played to clock 300, SELECT (the room again, a restart counted, the run's time kept), then the same tape paused at clock 150 for 60 frames: while paused the clock, the room and the run's time stand still; after it, the room matches the first attempt tick for tick to clock 300 |
| 71 | Each row: RESTART ROOM (clock 0 at the door, a restart counted), CONTROLS shown, B resumes where it stood, RESTART STAGE from room 2 (room 1, clock 0, the run's time and restarts 0), STAGE SELECT (the select, the station hovered); four pauses |
| 72 | The aquarium (opened with the playtest unlock), paused, then the cursor to CONTROLS (release build): every paused frame under 700,000 CPU and the GPU's budget; no frame dropped |
| 73 | Not a check: `shots.sh`'s pause in the store's fourth room (`pause_map.png`, `pause_controls.png`) |
| 65 | The platform stage (the last; one room, no stand-ins): unlocked by the save, dimmed before it is cleared, played with B's tape, its end, its save, the select with its room lit |

## For the owner

- **Look at**: `tests/front/shots/title.png`, `select_*.png`, `end.png`, `end_store.png`,
  `pause_map.png`, `pause_controls.png`, and
  H's transition in `transition_1_to_2.png`, `transition_2_to_3.png` (the station) and
  `transition_store_back.png` (every 6th frame).
- **The model turns 26 degrees either side**, not a whole turn (above). A whole turn is a
  one-line change (`menu_yaw()`).
- **Stage names are placeholders**: "PLATFORM TO ROOF", "THE STATION", "THE TOWER", "THE
  AQUARIUM", "AFTER CLOSING", "THE WAY HOME". The title's "TOKYO 1990" is the owner's
  (2026-10-15). The rooms' names are the worlds'.
- **The title** has the stage track and no ambience; F's notes say how to make it silent.

## Requests

- None open. (The pause's hooks are A's: `Mode.Pause`, `fe_pause()`, `room_restart()`, SELECT's
  restart; landed 2026-10-15.)

## Files (mine)

| File | What |
|---|---|
| `dr_front.akr` | The hooks (`fe_start`, `fe_update`, `fe_draw`, `fe_draw_room`, `fe_owns_transition`, `fe_event`) and the imports |
| `dr_section.akr` | The section: reading a world's rooms, drawing them in place or as a model, their lights, the route |
| `dr_menu.akr` | The title, the stage select, the stage's end, the transition's caption; the stage table |
| `dr_save.akr` | The save |
| `dr_pause.akr` | The pause: its rows, the map, the controls |
| `front_art.akr` | Generated by `art/make_front_art.py`: the fonts' and the icon's embeds |
| `art/make_front_art.py`, `art/front_title.fnt`, `art/front_head.fnt`, `art/save_icon.bin` | The generator and what it writes |
| `tests/front/harness.akr`, `run.sh`, `check.sh`, `shots.sh`, `shots/` | The scenarios and the captures |
| `NOTES_E.md` | This |

## Playtest unlock (added by the coordinator, 2026-10-15)

In the stage select, A (or START) with L and R held starts a locked stage, so the owner can play
any stage without clearing the ones before it (`select_update()` in `dr_menu.akr`). The save is not
changed. Keyboard: hold Q and E, press J. Scenario 72 uses it to reach the aquarium. The pause's
CONTROLS panel lists it ("L+R+A").
