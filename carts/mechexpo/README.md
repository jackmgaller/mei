# Mech Expo 2000

A side-on 2.5D mech fighting game: Street Fighter's structure with Smash Bros.' easy controls.
Rival companies bring their newest mechs to the year 2000's big expo, where the UAPC is running a
trial for a defence contract; every fight is a product demonstration. The pitch is "Mech Expo
2000 — MVP and Future Work" (2026-10-11); this cart is its MVP. The look and feel are in
[STYLE.md](STYLE.md).

## What the MVP is

| In | Out (later) |
|---|---|
| Two mechs: the Hero Mech (Momentum Robotics, kinetic) and its echo, the Double-blade Hero (Umbral Research, antimatter) | The other four base mechs and their echoes |
| One stage: a flat demo hangar with walls on both sides | Stage events, moving stages, ring-outs |
| Versus: two players, or one player against the CPU | Story scenes, endings, the secret boss |
| Arcade ladder: CPU mirror match, then your echo (or, as the echo, the original). Clearing it with the Hero unlocks the Double-blade Hero, saved to the memory card | Memory card saves beyond the unlock |
| Training: a dummy and a move list | The announcer |
| One power meter, one super a mech; rounds (best of three, 60 s), a timer, health bars, a HUD | A half-bar meter tier |
| Y2K menus at placeholder quality: title, mode select, character select, results, pause | The brochure menus at full quality |
| One fight track, a menu loop, the core sound effects | |

**Controls.** Stick or d-pad: walk, crouch, and the direction of a move. A attack, B special,
X jump, Y grab, R block, A + B super (when the meter allows), Start pause. L is unused. Any move
is one direction plus one button; no motion inputs, no tilts, no per-direction aerials.

## Gates

1. **The Animation Kit prototype (A).** The Hero's parts driven by the Animation Kit through one
   real move (a forward attack): its contact sheet, a capture from Mei with the hit and hurt
   boxes drawn, a capture of the two mechs overlapping (a grab, and one crossing the other), and
   the CPU and GPU cost of two posed mechs. Shown to the owner; the animator (F) starts after it.
2. **First playable.** Two mechs fight with real animations in the hangar with the HUD, from the
   character select to the results.
3. **The MVP.** Everything in the table above, within budget, with `make test-carts` passing.

## Folders and owners

Each agent writes only its own files, in this shared checkout, and builds into its own build
directory (`make B=build-mx-LETTER ...`), never `build/`. Nobody commits; the director (the main
session) integrates and commits. A file you need from someone else that does not exist yet: use
a stand-in in your own files until it lands. Each owner writes the interface files below **first**
(stubs that compile), so the others can build against them.

| Path | What | Owner |
|---|---|---|
| `tools/mei_anim.py`, `tools/animkit/`, `tests/test_animkit.py`, `docs/ANIMKIT.md`, `anim.akr`, `tests/anim/` | The Animation Kit (format, `verify`, `preview`, `pose`, `export`, `fmt`, `check`), the runtime that poses and draws a rig, and the kit's own test cart | **A, Animation Kit** |
| `anims/` (`anims/hero/*.anim.json`, `anims/doubleblade/*.anim.json`), the exported `anim_data.akr` | Every move's animation, timing and boxes. Until Gate 1, A writes the one proof move | **F, animator** (from Gate 1) |
| `models/`, `tools/gen_mechexpo_assets.py`, `art/` (except `art/stage_*` and `art/ui_*`), `assets.akr` | The mechs' parts and rigs, the stage's polygon props, the emblems, and the pack of every model | **B, models** |
| `fight.akr`, `fighter.akr`, `moves.akr`, `meter.akr`, `cpu.akr`, `MOVES.md`, `tests/harness.akr`, `tests/run.sh`, `tests/check.sh` | The fight: rules, frame data effects, input, meters, rounds, the CPU, the dummy, and the cart's test cases | **C, combat** |
| `mechexpo.akr`, `game.akr`, `stage.akr`, `camera.akr`, `hud.akr`, `fx.akr`, `menus.akr`, `save.akr`, `stage_art.akr`, `art/stage_*`, `art/ui_*`, `tools/gen_mechexpo_stage.py`, `tools/gen_mechexpo_ui.py`, any other top-level `.akr` not listed here | The entry point, the game's flow and modes, the stage on the plane chip, the camera, the HUD, effects, the menus and the unlock save | **D, stage and front end** |
| `music.akr`, `mu_data.akr`, `sfx.akr`, `audio/`, `tools/gen_mechexpo_audio.py` | Music and sound effects | **E, audio** |

`mechexpo.akr` (the entry point, `cart "Mech Expo 2000", "MECHEXPO"`) must compile whenever it
exists, because `make` builds every `carts/NAME/NAME.akr`. Changes to shared files (the
`Makefile`, `AGENTS.md`'s tables, `docs/`) other than those listed go through the director.

## Coordinates

- 1 unit = 1 metre, Y up, 60 frames a second; all game state is fixed-point and deterministic.
- **The fight plane is z = 0.** Fighters move in x and y only; x is across the stage. The floor
  is y = 0. The hangar's walls are at **x = ±36**; the rounds start with the fighters at
  **x = ±9**, facing each other.
- **The fighters are never more than 36 m apart** (`FIGHT_MAX_SEP` in `fight.akr`, C's): the
  camera's widest view is about 48 m, where a mech is about 80 px tall, and the separation
  stops a fighter walking or being knocked further away, like Street Fighter's screen edge. It
  acts as a wall for corner pressure, as the hangar's walls do.
- **Mechs** are about 12 m tall. A recipe faces −Z (the Asset Kit's convention), +X is the
  mech's left. In the fight a mech is turned about Y to face +x or −x (rotated, not mirrored, so
  winding and culling stay right). Its root is on the floor under the pelvis.
- **Fight-local coordinates** (boxes, root motion): x forward (the way the mech faces), y up,
  origin at the root; the fight flips x by the facing.

## Interfaces

**Rig (B) → Animation Kit (A).** Each mech has `models/NAME/NAME.rig.json`, written by its
generator: the parts, each with its `id`, `parent` (or null for the root), the joint's `offset`
from the parent's joint in the rest pose, and its part recipe (`parts/NAME_ID.asset.json`, origin
at the joint), plus the attachment points A or F need (each hand's weapon mount; a weapon is a
part like any other). A owns the format and may add to it; B keeps the generators writing it.
The echo shares the Hero's skeleton: same part ids, same joints.

**Animation runtime (A, data by F) → fight (C), scene (D)**, in `anim.akr`. A designs the API;
this is what the others rely on, in substance:

```
enum Mech { Hero, Doubleblade }
enum Mv { ... }                                  // the move list below; the same names for both mechs
fn anim_len(m: Mech, mv: Mv) -> s32              // frames
fn anim_boxes(m: Mech, mv: Mv, f: s32, out: *Boxes) // the hit, hurt and push boxes at frame f: 2D rectangles
                                                 // in fight-local metres, baked at export from the parts they follow
fn anim_root(m: Mech, mv: Mv, f: s32) -> vec2    // root motion over frame f (fight-local)
fn anim_marks(m: Mech, mv: Mv, f: s32) -> u32    // flags F sets per frame: cancel window, invulnerable, armour, super flash, a step
fn anim_draw(m: Mech, mv: Mv, f: fixed, root: mat4) // pose and draw; f fractional for blends and hitstop
fn anim_part(m: Mech, mv: Mv, f: fixed, root: mat4, part: s32) -> mat4 // a part's matrix (sword trails, sparks)
```

- **Timing lives in the animations (F); what a hit does lives in the fight (C).** F sets each
  move's startup, active and recovery frames (the frames with hit boxes are active), its boxes,
  root motion and marks. C owns damage, hitstun, blockstun, chip, meter gain, knockback and
  which moves can cancel into which (during F's cancel window). C proposes timing changes; F
  makes them.
- **Collision is 2D**: rectangles in the fight plane. Push boxes keep the mechs apart on the
  ground; a jump can cross over.

**The move list** (`Mv`, the same for both mechs): `idle`, `walk_f`, `walk_b`, `crouch`,
`jump` (up, forward and back share it; the fight moves the root), `land`, `block`,
`hit_high`, `hit_low`, `hit_air`, `knockdown`, `getup`, `ko`, `win`, `intro`; `atk_n`, `atk_f`,
`atk_d`, `atk_air`; `sp_n`, `sp_f`, `sp_u`, `sp_d`; `grab`, `grab_whiff`, `throw`, `thrown`,
`grab_break`; `super`. C writes what each move does in `MOVES.md` (the design, for F to animate)
and may ask the director to add to the list.

**Fight (C) → game (D)**, in `fight.akr`:

```
fn fight_init(p1: Mech, p2: Mech, mode: FightMode, cpu_level: s32) // FightMode: Versus, VsCpu, Arcade, Training
fn fight_tick(pad1: u32, pad2: u32, st1: vec2, st2: vec2) // one frame of the fight, hitstop and rounds included
fn fight_get() -> *Fight                         // read-only: per fighter its mech, move, frame (fixed), x, y,
                                                 // facing, health, meter, flash; the round, timer, wins, phase
                                                 // (intro, fight, ko, round over, match over), the camera's shake
fn fight_events() -> *Events                     // this frame's events: hit (where, how hard), block, chip, whiff,
                                                 // grab, throw landing, break, land, step, meter full, super, KO, time up
fn fight_training(opt: *TrainOpts)               // the dummy: stand, crouch, jump, block all, CPU; refill health and meter
fn fight_moves(m: Mech) -> *MoveList             // names and inputs, for the training move list
```

D draws the fighters (`anim_draw` with `fight_get()`'s state), the effects and the HUD from the
events and state, and calls E's sound effects for each event. C never draws or plays sound.

**Audio (E) → game (D).** `music.akr`: `music_menu()`, `music_fight()`, `music_stop()`,
`music_tick()` (once a frame), `music_duck(on: bool)` (pause). `sfx.akr`: one-shots
`sfx_hit(power: s32)`, `sfx_block()`, `sfx_chip()`, `sfx_swing(m: Mech)`, `sfx_grab()`,
`sfx_throw()`, `sfx_break()`, `sfx_land()`, `sfx_step()`, `sfx_meter_full()`, `sfx_super()`,
`sfx_ko()`, `sfx_round()`, `sfx_menu_move()`, `sfx_menu_ok()`, `sfx_menu_back()`,
`sfx_unlock()`. Channels: music 0–9, sound effects 10–15. `sfx_hit`'s power is 0 light,
1 medium, 2 heavy, 3 crushing (a super's or a throw's hit). `sfx_pan(x: fixed)` pans the next
one-shot to stage x (−36..36) and then resets. `music_fight()` and `music_menu()` do nothing if
their track is already playing, so the fight track runs on through the rounds. `sfx.akr`
imports `anim.akr` for `Mech`.

**Models (B) → game (D), runtime (A).** `assets.akr` (generated by
`tools/gen_mechexpo_assets.py`) defines every `ASSET_*` and `assets_load()`. The stage props
are B's models, placed by D.

## Rendering, VRAM and budgets

- **Depth buffer and perspective texturing**; every recipe has
  `"verification": {"required": true, "depth": true, "perspective": true}`.
- **Layers** (the plane chip, [docs/PLANES.md](../../docs/PLANES.md)): the backdrop gradient,
  BG1 for the parallax (crowds, booths, banners), BG2 for the floor, polygons for the mechs, the
  effects and the props, BG0 for the HUD. The plane chip, its line channels and priorities are D's.
- **Texture slots:** B's pack uses 0–7, D 8–14; slot 15 is the standard library's font. B's
  8-bit palettes come down from 14 as the pack assigns them; D uses 4-bit palettes 240–254.
  Tell the director if either side needs more. **In `art/`, D's files start with `stage_` or
  `ui_`**; everything else there is B's pack, which `gen_mechexpo_assets.py` rewrites.
- **D's use, as built:** atlases ATLAS_0 the floor, ATLAS_1 the hall, ATLAS_2 the HUD, ATLAS_3
  the menu page; texture slots 8 (fonts), 9 (UI sprites), 10 (effects); palettes 240–254 (244 is
  lent to the menu page and the hall's put back); a backdrop table at 0x582000; line channels 0,
  2 and 7. Priorities: BG2 0, BG1 1, the mechs 2, BG0 (the HUD's frame) 3, the interface list 4.
- **Triangles:** a mech about 1,600–1,800 (the sketches are 1,632 and 1,734); the frame limit is
  4,000.
- **Budgets a tick:** CPU 1,000,000 cycles, GPU 2,000,000 (`mei-headless --gpu-stats`). The
  sketches cost about 155,000 CPU cycles and 5 % of the GPU each, posed as one mesh; the rig's
  per-part transforms and the fight have to fit beside two of them.
- **The camera is side-on** by default (the owner's choice, 2026-10-12); the 13° angled framing
  stays as an option in the pause menu.
- **Lighting** is baked into each part, from above and in front with no x component, so both
  facings shade alike. A rotating part carries its shading with it; Gate 1 shows whether that
  reads wrong in motion.

## Building and checking

```sh
make B=build-mx-A build-mx-A/meic build-mx-A/mei-headless build-mx-A/mei-asset-probe
python3 tools/mei_assets.py verify carts/mechexpo/models/hero/hero.asset.json --build-dir build-mx-A
make B=build-mx-A build-mx-A/carts/mechexpo.mei
```

A model is done when `verify` passes and its preview has been looked at. An animation is done
when the Animation Kit's `verify` passes and its contact sheet has been looked at. Run
`mei_anim.py check` before committing moves: it checks the files' style, verifies every move,
exports and runs the kit's two suites.
