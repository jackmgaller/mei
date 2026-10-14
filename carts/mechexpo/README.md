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
| One stage: a flat demo hangar with walls on both sides (since: [stages as data](#stages), and the rooftop with ring-outs) | Stage events, moving stages |
| Versus: two players, or one player against the CPU | Story scenes, endings, the secret boss |
| Arcade ladder: CPU mirror match, then your echo (or, as the echo, the original). Clearing it with the Hero unlocks the Double-blade Hero, saved to the memory card (since: [the full ladder](#the-arcade-ladder), three fights on a difficulty) | Memory card saves beyond the unlock |
| Training: a dummy and a move list | The announcer |
| One power meter, one super a mech; rounds (best of three, 60 s), a timer, health bars, a HUD | A half-bar meter tier |
| The brochure menus (mx-menus): title, mode select, the 5 x 2 character select from `roster.akr`, VS, pause, results, the unlock | |
| One fight track, a menu loop, the core sound effects | |

**After the MVP: Tank** (Heartland Atomic Company, nuclear), the grappler, a base mech available
from the start: [MOVES.md](MOVES.md#tank-heartland-atomic-company-nuclear) is its design.
Its model is `models/tank/make_tank.py` (on the shared skeleton: treads on the shins, drive
sprockets on the feet, empty weapon mounts); its fight data `tank.akr`, its rules (super
armour, the command grabs) a marked block at the end of `fighter.akr`, its meter in `meter.akr`,
its CPU at the end of `cpu.akr`, its HUD gauge and reactor glow `tank_fx.akr`; its test
scenarios are 40-49. Until its animations land, its moves use the stand-in timings and boxes in
`tank.akr` and are drawn in the guard pose (`anims/tank/_body.anim.json`).

**Controls.** Stick or d-pad: walk, crouch, and the direction of a move. A attack, B special,
X jump, Y grab, R block, A + B super (when the meter allows), Start pause. L switches the
Twins between their forms (the other mechs ignore it). Any move
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
| `mechexpo.akr`, `game.akr`, `stage.akr`, `camera.akr`, `hud.akr`, `fx.akr`, `menus.akr`, `save.akr`, `stage_art.akr`, `art/stage_*`, `art/ui_*`, `tools/gen_mechexpo_stage.py`, `tools/gen_mechexpo_ui.py`, `stages.akr`, `stage_select.akr`, `roof_art.akr`, `roof_props.akr`, `roof_city3d.akr`, `props/`, `tools/gen_mechexpo_rooftop.py`, any other top-level `.akr` not listed here | The entry point, the game's flow and modes, the stages (mx-stages: the table, the stage select, the rooftop and its props) on the plane chip, the camera, the HUD, effects, the menus and the unlock save | **D, stage and front end** |
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
The echo shares the Hero's skeleton: same part ids, same joints. Seraph's rig (Shadow's skeleton)
has three joints more, appended to `enum Part` and the kit's `PARTS` after `foot_l`: `wing_l`,
`wing_r` (the torso's children) and `halo` (the head's). A mech whose rig lacks them draws nothing
there; its exported frames hold only its first 19 parts (`AK_NPART`), so the other mechs' data
did not change.

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
`music_tick()` (once a frame), `music_duck(on: bool)` (pause), `music_fanfare()` (the
arcade's cover, mx-ladder: channels 6 and 7). `sfx.akr`: one-shots
`sfx_hit(power: s32)`, `sfx_block()`, `sfx_chip()`, `sfx_swing(m: Mech)`, `sfx_grab()`,
`sfx_throw()`, `sfx_break()`, `sfx_land()`, `sfx_step()`, `sfx_meter_full()`,
`sfx_super(m: Mech)`, `sfx_ko()`, `sfx_round()`, `sfx_menu_move()`, `sfx_menu_ok()`,
`sfx_menu_back()`, `sfx_unlock()`. Channels: music 0–9, sound effects 10–15. `sfx_hit`'s power
is 0 light, 1 medium, 2 heavy, 3 crushing (a super's or a throw's hit). `sfx_pan(x: fixed)` pans
the next sound to stage x (−36..36) and then resets. `music_fight()` and `music_menu()` do
nothing if their track is already playing, so the fight track runs on through the rounds.
`sfx.akr` imports `anim.akr` for `Mech` and `Mv`.

The second round of sounds (mx-sfx) adds, by event (`game.akr`'s `sound_event()`):
`sfx_attack(m: Mech, mv: Mv)` (the Swing event, by the body and its move: the blades, Beam's
discharges, Tank's fists and Reactor Vent, the combined Twins' fists, ONE's and ZERO's lighter
strikes), `sfx_shot(m, lvl)` (the wave, or Beam's orb by level), `sfx_clash(orb: bool)` (an orb
fizzling against a wave), `sfx_armour(power)` (Tank's armour), `sfx_tank_lift()` (a command
grab caught), `sfx_throw_by(m, mv)` (Tank's slam, Beam's Shock Grip crack, else the throw),
`sfx_knockdown()` (a Land of power 2), `sfx_step_of(m)`; `sfx_super(m)` plays the power
source's charge-up with the burst, and a heavy or crushing `sfx_hit` scatters debris. Seraph's
(mx-seraph-fx): `sfx_mark(fresh: bool)` (the Mark event; a refresh quieter), `sfx_reflect()`
(the Reflect event), `sfx_column_lock()` (the Column event), and from its state (`seraph_fx.akr`'s
`seraph_sfx()`) `sfx_ward()`, `sfx_wing_beat()`, `sfx_dive(land: bool)` and the loops
`SFX_GLIDE` and `SFX_MARK_HUM`; its branches of `sfx_attack` (the column's impact, Ascension's
rush, the fists), `sfx_shot` (the bolt's cast) and `sfx_super` (the choir). By state,
once a fight frame from `game.akr`'s `sound_poll()` (the mechs' parts in `beam_fx.akr`'s
`beam_sfx()`, `tank_fx.akr`'s `tank_sfx()` and `twins_fx.akr`'s `twins_sfx()`):
`sfx_couple(on: bool)`, `sfx_react()`, `sfx_charge_full()`, `sfx_void(back: bool)`,
`sfx_smoulder()`. For the brochure: `sfx_page()` (from `menus_page()`), `sfx_stamp()`,
`sfx_pass()`, `sfx_shutter()` (`menus.akr`'s `menus_sfx()` times the stamps to their drawing).

**Loops** (Tank's treads, Beam's charge hum, which the Twins' Fusion Focus borrows lower, the
Shock Grip's buzz, Seraph's glide and its Mark bolt's hum): `sfx_hold(slot, id, pri, x, pitch,
gain)` every frame a loop should sound, a slot a side (0, 1) and a side's bolt (2, 3); `sfx_tick()` (once a frame, always, after the game's update) fades out over four
frames and stops every loop not held that frame, so loops stop by themselves on the pause, on
the menus, when the move ends and at a KO (`sfx_ko()` stops them at once).
`sfx_stop_fight()` (in `leave_fight()`) stops every fight sound still playing. The voices'
priorities are listed at the top of `sfx.akr`: a hit or a KO is never lost to a step, a swing or
a loop. `sfx_heard(id, ch)` is a weak hook the tests replace to log every sound started
(scenarios 80–89, `tests/sfx/harness.akr`).

**Models (B) → game (D), runtime (A).** `assets.akr` (generated by
`tools/gen_mechexpo_assets.py`) defines every `ASSET_*` and `assets_load()`. The stage props
are B's models, placed by D.

## Beam, the third mech

Beam (Raikō Chemical Group, chemical; `Mech.Beam`) is the first mech after the MVP, a base
mech available from the start: its design and frame data are in [MOVES.md](MOVES.md#beam-raikō-chemical-group-chemical).
Its own files: `models/beam/make_beam.py` (the model on the Hero's skeleton, 1,794 triangles),
`anims/beam/_body.anim.json` (the stand-in for every move until its animations land; the fight
plays it on the stand-in timings and boxes in `beam_moves.akr`), `beam_moves.akr` (its hits,
timings, the Volt Orb and the reaction), `beam_hud.akr` (the chemical meter and its select card)
and `beam_fx.akr` (its effects). The shared files call these with a line each; the shot system
in `fighter.akr` carries both the Hero's wave and Beam's orb (`Shot.lvl`, `str`, `half`, `y0`,
`y1`, `life`). Tests: scenarios 30–39 in `tests/harness.akr`.

## The Twins

The Twins (Binary Mechanica, fusion; `Mech.Twins`) are the base mech unlocked by clearing the
arcade with every base mech in the game (`RULE_BASES`: slots 0-3 that have a mech, so Hero,
Beam and Tank until Shadow joins). Split, the player's twin A leads and twin B copies its pad six
frames late; combined, they are one mid-weight brawler; L switches, a move each way (`combine`,
`split`), the bodies swapping on the move's `release` frame under a flash. The design is
[MOVES.md](MOVES.md#the-twins-binary-mechanica-fusion).

- **Three bodies, one fighter.** `Mech.Twins` is the combined form and the fighter's `mech`;
  `Mech.TwinA` and `Mech.TwinB` are the split form's bodies, for the animations and the drawing
  only. Each fighter has a `body` (the mech for everyone else); the fight times, boxes and draws
  by body. Split, twin B is a second body of the same fighter, `fight.f[s + 2]` (`Fight.f` holds
  four), with its own state in `fx[s + 2]`; its hits are the side's, and hits on it come off the
  side's one health bar. A fight without the Twins takes the old two-body paths unchanged.
- **Files:** `models/twins/make_twins.py` (the three rigs and models), `anims/twins/`,
  `anims/twin_a/`, `anims/twin_b/`, `twins.akr` (the hits, the stand-in timings and boxes, and
  the rules: the partner's pad and following, the leash, one-way pushing, combining and
  splitting, four-body collisions, the throws, the fusion meter's fills, the move lists),
  `twins_fx.akr` (twin B drawn 1.2 m behind the fight plane, the swap's flash, the camera over
  every body, the HUD's fusion gauge), the Twins' CPU at the end of `cpu.akr`. The shared files
  call these with a line each. Tests: scenarios 60-67 in `tests/harness.akr`, 68 (the unlock
  rule) and 69 (the budget with three bodies, through the real game) in `tests/twins/harness.akr`;
  70 is a measurement (the Twins' wins against each mech, CPU against CPU).
- **The budget split** (scenario 69, CPU against CPU, the split Twins against Tank, a release
  build): 521,418 CPU cycles and 560,514 GPU cycles at the peak, 1,768 triangles drawn; the
  three bodies' drawing (`prof_mechs`) about 396,000 cycles.

## Shadow

Shadow (Umbral Research, antimatter; `Mech.Shadow`, roster slot 1, SHADOW UR-01) is the
trickster: the Rift Mine, the Hex Bolt and its Siphon curse, Shadow Sneak, Eclipse Rise, Phantom
Grip and Total Eclipse. The design is [MOVES.md](MOVES.md#shadow-umbral-research-antimatter).

- **Files:** `models/shadow/make_shadow.py` (the model and rig), `anims/shadow/`, `shadow.akr`
  (its hits, the stand-in timings, boxes and marks, and its rules: the bolt in the shot system
  (`Shot.hex`), the Siphon (`meter_add` sends a cursed fighter's gains to `shadow_siphon`), the
  mines and snares, the Sneak's travel and hold, Phantom Grip's side swap, Total Eclipse's five
  hits by box index, the Diving Claw's dive), `shadow_fx.akr` (the bolt, the mines, the Sneak's
  shadow, the curse's glow, the snare, the afterimages, Total Eclipse's dark, the HUD's siphon),
  Shadow's CPU at the end of `cpu.akr`. The shared files call these with a line each; the fight
  state gains `Fighter.curse`, `Fighter.siphoned` and `Shot.hex`, and `enum Ev` gains `Curse`,
  `Mine`, `Snare` and `MineGone` (appended).
- **Tests:** scenarios 100-108 and 110 (the rooftop) in `tests/harness.akr`, 109 (the budget,
  through the real game) in `tests/shadow/harness.akr`; 111 is a measurement (Shadow's wins
  against each mech, CPU against CPU).
- **The budget** (scenario 109, CPU against CPU, a debug build, a mine and a bolt kept out, the
  other cursed, Total Eclipse forced twice): against the split Twins 613,403 CPU cycles and
  805,917 GPU cycles at the peak, 1,914 triangles; against Beam 557,418 and 740,850, 1,820
  triangles; Shadow's effects (`prof_fx`, with fx.akr's) at most about 76,000 cycles.

## Seraph

Seraph (Momentum Robotics, kinetic; `Mech.Seraph`, roster slot 6 under Shadow, SERAPH MR-02) is
Momentum's echo of Shadow, the paladin, unlocked by clearing the arcade with Shadow. Phase 1
(mx-seraph) put the mech in the game, drawn and pickable, with Shadow's moves as placeholders;
phase 2's fight and CPU (mx-seraph-fight) gave it its own moves: the Mark of Judgement and the
mark, the Seraph Dive, Ascension, the Wing Ward, Heaven's Arc and Judgement; its animations
(mx-seraph-anim) and its effects and sounds (mx-seraph-fx, below) are phase 2's other two parts.
What is real and what is still Shadow's:
[MOVES.md](MOVES.md#phase-1-what-is-in-the-game-now).

- **Files:** `models/seraph/make_seraph.py` (the model and rig: the owner's concept A, round 4b,
  from `concepts/angel_a/`, which stays as the record; its guard is Seraph's boxer's guard),
  `anims/seraph/` (Seraph's own moves, the weapon joints held at 0 with the kit's `"still"`; the
  throws' victims Shadow's to the slam, then face down), `seraph.akr` (its hits, its stand-in timings, boxes, marks and root
  motion, its move list, and its rules: the Mark bolt in the shot system (`Shot.mark`) and the
  mark (`Fighter.mark`, 360 frames of play); the Dive's glide and dive (`seraph_advance`, called
  from `fighter.akr`'s advance); the Wing Ward's reflect (`seraph_reflect`, from `shot_try`
  before the Parry's test, on the `ward` frames: `MARK_WARD` in `anim.akr`), which moves the shot
  to Seraph's slot (`Shot.refl`); Heaven's Arc (`seraph_hold`, from `throw_tick`; the victim plays
  `thrown_vault`); Judgement's lock (`judge_x`, on the first frame after the flash), its column
  (`seraph_column_box`, from `load_boxes`) and its x 1.5 on a marked mech (`seraph_judged`, from
  `resolve`; `Hit.nodebt` keeps the antimatter debt's 25 % from stacking with it)), and
  Seraph's CPU at the end of `cpu.akr`. Shadow's rules ask the predicates `has_hex_bolt`,
  `has_sneak`, `has_rift_mine`, `has_phantom_grip` and `has_eclipse` (Shadow's alone now) and
  `has_dive` (Shadow's and Seraph's); Seraph's ask `has_mark`, `has_glide`, `has_ward`,
  `has_over_throw` and `has_judgement`. `enum Ev` gains `Mark`, `Reflect` and `Column`
  (appended). Its numbers are a row of `STATS` (1,000 health, a walk of 0.080 m a frame forward
  and 0.064 back, the kinetic meter) and its names a row of `ROSTER`.
- **Its placeholders:** until a move's own animation lands, the fight plays it from
  `seraph.akr`'s stand-in data (`ser_std`, filled by `seraph_init()` when a Seraph fights, tells
  a placeholder of Shadow's from the data: [MOVES.md](MOVES.md#phase-1-what-is-in-the-game-now);
  `moves.akr`'s `use_standin` reads it); the drawing is the placeholder's. Still to come:
  `COVER_POSE` in `cover.akr` (it holds frame 119 of Shadow's win), and the halo's glow dimmed
  while Seraph lies (MOVES.md's effects table: the halo is an emissive part, so it needs a dimmed
  palette or mesh in the drawing, not a sprite).
- **Effects and sounds (mx-seraph-fx):** `seraph_fx.akr`, from the fight's events (`Mark`,
  `Reflect`, `Column`) and state (`Fighter.mark`, `Shot.mark`, `Shot.refl`, Seraph's move and
  frame, `seraph_warding`, `seraph_gliding`), called with a line each from `game.akr`
  (`seraph_fx_draw` after Shadow's, `seraph_fx_offset` after `fx_offset`, `seraph_sfx` in
  `sound_poll`, three lines of `sound_event`), `fx.akr` (`seraph_fx_shot` before the Hex Bolt and
  the orb; `seraph_trail` for the trails) and `hud.akr` (`seraph_mark_hud` after the Siphon,
  `seraph_super_col` for the SUPER label). Light gold and white-gold (`SRX_GOLD` 0x80E0FF,
  `SRX_CORE` 0xDCF8FF): the Mark bolt (gathering at the fist on `sp_n`'s first 16 frames, a flash
  as it leaves; a white-gold core in a gold glow 2.4 m across, a soft halo, a four-point glint
  turning, motes); the mark on every marked body (a split Twins' partner too: a sigil at the
  chest pulsing once a second, a ring turning over the head, motes rising, flickering in the
  last 60 frames; a ring bursting from the chest when it lands, half the size for a refresh);
  the HUD's mark on the marked side (the gauge hatched in gold, MARKED where the Siphon writes
  SIPHON, the time bar under the gauge, a shine sweeping the health bar toward the centre every
  30 frames, the bar flashing gold for 8 frames on a new mark) and Seraph's SUPER pulsing gold
  while the other is marked; the Wing Ward's sheen (a curved sheet of glows 11 m tall in front,
  a bright band running up and down it, fading over 4 frames); a reflect (a white glow 4 m
  across, a gold ring, a star, sparks) and the reflected shot drawn as light (a wave of light, a
  gold ball at the orb's size, the Mark bolt for a bolt); the fists' short white trails edged
  gold on the active frames; the Dive's downdraft on the hop, glows, streaks, feathers and
  ribbons off the wing tips through the glide, a streak along the dive and a downdraft at the
  touchdown; Ascension's light along the fist and a burst at each wing tip on the beat; Heaven's
  Arc's downdraft and feathers on each wing beat; Judgement's halo flare in the flash (rings
  growing to 4 m, a white glow, the core lit), the stage brightened to white-gold through
  `layer_offset` from the flash to the column's last active frame (fading over 12), the lock's
  gold ring opening to 5 m on the floor with a shaft of light over it and motes raining in, then
  the column (bands of additive Gouraud quads from the floor past the top of the view, ±2.5 m, a
  white core, flickering edges, held on the floor through its hit's hitstop) with dust, a floor
  ring and a flash. Sounds (`tools/gen_mechexpo_audio.py`, `SERAPH` after the loops so every
  earlier sound keeps its index and bytes): the bolt's cast and its hum (a loop in slots 2 and
  3, a side's bolt, rising with its speed), the mark landing (a struck bell; a refresh quieter),
  the ward's sweep, the reflect, a wing beat (the hop, Ascension's beat, Heaven's Arc's two), the
  glide's wind (a loop), the dive's whistle and touchdown, Ascension's rush, Judgement's choir
  (with the kinetic charge-up), the column's lock and its impact; 175,200 bytes in `sfx.adp`.
  VRAM: no new texture slot or palette (the particle sheet's glint, sigil and feather, below).
  The budget with the effects (debug builds, budget.sh): 162 against the split Twins on the
  rooftop 709,651 CPU and 1,030,911 GPU cycles at the peak, against Shadow in the hangar 581,483
  and 969,225; 168 on the container port 657,430 and 1,019,057; 198 (Judgement and a reflect
  against the split Twins on the container port, both marked) 671,195 and 1,103,457; the
  effects (`prof_fx`, with fx.akr's) at most 79,722 cycles (Shadow's 109: 78,971), the most of
  it fx.akr's pool of 80 particles (`seraph_fx_draw` itself about 7,000 at that frame, up to
  about 22,000 with the column over two marked twins); no late frames.
- **The model:** 1,892 triangles (Shadow's 1,800 and the Hero's 1,776; the pack's limit for it
  is 1,900, `MECH_LIMITS`), 13.55 m to the top of the halo in the rest pose (the roster's 135).
  Packed after the other mechs (`LATE` in the generator), with its grey copy: 83,896 bytes of
  meshes, as much again grey, 2,556 bytes of texture tiles (Momentum's mark on each pauldron,
  the MR-02 plate on each thigh, the hazard stripes on each shin), four more 4-bit palettes.
- **Tests:** scenarios 160 (against Shadow) and 161 (against the Hero) in `tests/harness.akr`:
  1,000 health, the kinetic meter, 22 parts a frame, the walk, the jab landing at 4 m and missing
  just past the fist where Shadow's Claw Jab reaches from 6 m, the lunge landing at 9 m and
  missing just past the fist's reach, Heaven's Arc's side swap, Judgement's one hit (280) from a
  full bar without debt; 170-181 its own moves (`tests/harness.akr`): the mark, Judgement's bonus
  and the debt, the Wing Ward against the wave, every orb, the Hex Bolt and a mirror's Mark, the
  Dive, Ascension, Heaven's Arc (and off the rooftop's edge), the column, the CPU;
  162-168 through the whole game in `tests/seraph/harness.akr`: 162 and 168 the budget
  (budget.sh), 163 the select with Seraph's card and spec sheet (and the roster row's checks),
  164-167 mid-fight against Shadow and the Hero in the hangar and on the rooftop; 190-199 its
  effects, HUD mark and sounds (`tests/seraph/harness.akr`: 190 the bolt and the mark, 191 the
  mark's HUD on the split Twins, 192-194 the ward sending back the wave, a full orb and a Hex
  Bolt, 195 the Dive, 196 Ascension and Heaven's Arc, 197 Judgement, 198 the budget, 199 every
  sound heard); ladder scenario 118 (Shadow's NORMAL run: the final is Seraph, the clear unlocks
  it) and 124 VIEWs 4 and 5 (Seraph's reveal, the VS card).
- **The budget** (scenarios 162 and 168, CPU against CPU, debug builds, Seraph's Mark bolt kept
  out, the other marked, a full bar every 300 frames for Judgement; mx-seraph-fight, before
  `seraph_fx.akr`): against the split Twins on the rooftop 712,455 CPU cycles and 935,109 GPU
  cycles at the peak, 2,300 triangles, the worst CPU of any fight measured; against Shadow in the
  hangar 567,762 and 774,901, 1,866 triangles; against the split Twins on the container port (168)
  666,525 and 962,451, 2,149 triangles, the worst GPU; the fight at most 69,655 cycles, the
  mechs' drawing 417,682, the effects' 74,880; no late frames. (Phase 1, with Shadow's mine, bolt
  and Total Eclipse kept out: 707,271 and 796,571; 579,210 and 763,551; 666,804 and 999,683.)
  Mid-fight (164-167, CPU against CPU without the extras): 504,681 to 629,409 CPU and 378,106 to
  604,592 GPU cycles.

## The arcade ladder

The full ladder (mx-ladder), after the MVP's two fights; the owner's decisions are in
[MOVES.md](MOVES.md#decided-by-the-owner-2026-10-13-the-arcade-ladder). `ladder.akr` holds the
run, the difficulties and the test unit's names; `game.akr` the flow; `menus.akr` the screens.

**A run** is `LADDER_N` (3) fights: `LADDER_N - 1` company fights, then the final.

- **The company fights** are against the base mechs (roster slots 0-4) of rival companies, drawn
  by lot (`ladder_make()`) from the run's seed: the game tick the run starts on, so a scripted
  run replays exactly. Never your own maker, never the final opponent's maker, no maker twice.
  The Twins are drawn while they are still locked. As the Hero or the Double-blade Hero the two
  rivals come from Raikō, Heartland and Binary Mechanica; as Shadow or Seraph from Raikō,
  Heartland and Binary Mechanica; as Beam, Tank or the Twins from the other four makers.
- **The final** is the slot below (or above) yours: the Double-blade Hero for the Hero ("UMBRAL
  RESEARCH PRESENTS ITS COMPETING PRODUCT"), the Hero for the Double-blade Hero ("MOMENTUM
  ROBOTICS DEFENDS ITS TITLE"), Seraph for Shadow ("MOMENTUM ROBOTICS PRESENTS ITS COMPETING
  PRODUCT"), Shadow for Seraph ("UMBRAL RESEARCH DEFENDS ITS TITLE"). A mech whose echo's slot has
  no mech yet (Beam, Tank, the Twins) meets **the UAPC test unit**: its own mech in the UAPC's
  grey, the client's own evaluation unit ("THE UAPC WILL NOW EVALUATE YOUR PRODUCT AGAINST ITS OWN
  TEST UNIT";
  "SPECIFICATION: YOURS. BUILDER: NOT DISCLOSED."). Giving an echo's slot its `mech` replaces the
  test unit with the echo, with no other change.
- **Stages:** the company fights in the hangar, the final on the rooftop (`LADDER_STAGES` in
  `stages.akr`; `stage_pick()` gives a longer ladder's extra company fights the last company
  stage).
- **Losing** offers another demonstration as often as wanted: the same fight again (the same
  opponent, CPU level and stage), or B to the title.

**Difficulty** (`DIFFS`, picked on the difficulty select before the character select; the cursor
starts on the last grade picked, kept in the save). The levels are `cpu.akr`'s; they ramp from
the first company fight to the final:

| Grade | Its expo name | Company fights | Final |
|---|---|---|---|
| EASY | PUBLIC DEMO DAY | the novice (`CPU_NOVICE`, -1), the novice | 0 |
| NORMAL | TRADE TRIAL | 1, 1 | 2 |
| HARD | FULL UAPC AUDIT | 2, 3 | 3 |

**The novice CPU** (`CPU_NOVICE_LEVEL`, below level 0): reacts after 40 frames, decides every 24
to 48, blocks 6 % of what it sees coming, never anti-airs, chains or breaks a grab, never spends
its super (A + B loses its B), and carries out 12 % of the grabs it decides on. Two fields with
defaults were added to `CpuLevel` for it (`supers`, `grabs`); the other levels' rows and dice are
unchanged.

**EASY, measured** (scenario 116; its VIEW 1 and 2, not in `check.sh`, take every level): a
scripted novice who walks in and mashes (a press on 22 % of frames: A mostly, then B, a jump, a
grab; it never blocks), every mech against every mech (36 matches a level), CPU levels on the
right:

| Player | Novice | 0 | 1 | 2 | 3 |
|---|---|---|---|---|---|
| The masher | 97 % | 97 % | 94 % | 38 % | 30 % |
| A weaker player (presses on 9 % of frames, wanders both ways, jumps more) | 100 % | 88 % | 83 % | 22 % | 11 % |

So EASY is won by mashing; NORMAL's final (level 2) is the first real step up.

**Any difficulty unlocks:** a clear marks the slot's clear bit (`save.unlocked`, bit 16 + slot)
on every grade, so every unlock rule counts it (`roster_clear()`), and sets the grade's stamp
(`save.medals`, bit 3 × slot + grade).

**The clear icons:** an APPROVED seal per grade cleared, bronze (EASY), silver (NORMAL) and gold
(HARD): award stickers on the select grid's card corner (9 px, only those earned), on the
catalogue's spec sheet ("CLEARED", all three, the uncleared as outlines), on the difficulty
select (with how many units carry each) and the schedule page.

**The save** (`save.akr`) is version 2: `medals` and `diff` appended (24 bytes). A version-1 save
(the MVP's 16 bytes) is migrated as it loads: its unlocks and clear count are kept, and each
clear it holds becomes a NORMAL stamp, since the MVP's ladder was two fights at CPU levels 1 and
2 (scenario 121).

**The screens** (the brochure's, `menus.akr`; the round calls in `draw_fight_overlay()`):

- **The difficulty select** ("TRIAL GRADES", P. 03): a card per grade, its seal, its expo name,
  two lines and how many units carry its stamp.
- **The character select** in the arcade: the right-hand page is the programme: the grade, two
  rivals "drawn by lot", the final's details withheld.
- **The schedule page** ("TODAY'S PROGRAMME", P. 09), before each fight: your exhibit (its
  photograph on a turntable, its maker, booth and grade) and the main stage's programme: each
  demonstration's day, time and venue, the rival's maker and unit; the fights won stamped
  APPROVED (the latest coming down as the page opens), the next highlighted, the final "TO BE
  ANNOUNCED" and stamped CLASSIFIED.
- **The reveal**, before the final (330 frames, A after 60): the stage dark, two spotlights
  coming up (on the print layer, BG0, so the unit stands in front of them), the announcement
  typed a line at a time, the opponent in silhouette (the GPU's fog toward the dark, `gpu_fog`,
  only on this screen: `draw()` turns it off on every other frame), then lit with a flash and
  playing its intro, its nameplate sliding in.
- **The VS card** is unchanged apart from the opponent (the test unit: TEST UNIT, UAPC, CLIENT
  GALLERY, the UAPC's roundel) and "DEMONSTRATION n/3".
- **The round calls**, in every mode (none in training): TEST n / "ROUND n // UNITS TO THEIR
  MARKS" (DECIDING TEST for the last), COMMENCE, CONCLUDED / "UNIT NO LONGER OPERATIONAL" at a
  KO, TIME EXPIRED / "THE JUDGES CONSULT THE DATA", OUT OF BOUNDS / "UNIT LEFT THE TEST AREA",
  the round's winner / "TEST SCORED FOR 1P", the match's winner / "MEETS THE REQUIREMENTS", NO
  RESULT and INCONCLUSIVE for draws.
- **The results** name the test unit as such, show the next demonstration (the final
  withheld), and after a loss ask "REQUEST ANOTHER DEMONSTRATION?".
- **The cover**, after the final's results: a magazine cover (`cover.akr` says what is on it,
  `menus.akr`'s `draw_cover()` draws it). The owner's notes (2026-10-13): a photograph, a
  fanfare, and headlines that vary.
  - **A photograph:** the winner in 3D, frozen in one held frame of its win move
    (`COVER_POSE`: the end of the win, weapons up; Tank at frame 40, square to the camera), on
    its maker's colour, cut at the knees; no idle motion and no turntable. Per mech: the turn
    toward the camera, the camera's distance, the feet's height and the backdrop's shades
    (lighter behind the dark Shadow).
  - **The fanfare**, "Contract Awarded" (`music_fanfare()` in `music.akr`, made by
    `tools/gen_mechexpo_audio.py`): 5.6 s at the menu's 128 bpm in E major. The expo's PA chime
    and a polite electric-piano jingle, then a snare roll and a riser into big-beat drums,
    supersaw brass stabs (E, E, E, C, D) and a hoover line, a held E major chord with the robot
    choir, a crash and a sub boom, and a last chime. A stereo one-shot on channels 6 and 7 with
    the reverb; the menu loop fades out under it and starts again when it ends (leaving the
    cover cuts it short).
  - **The words** are picked when the run is cleared (`cover_pick()`, before the save is
    written) from the run's seed and unit: a headline from those for the final's case, the
    maker's own among them (27 in all: 8 for a base mech's win, 7 for an echo's, 12 for a test
    unit's), never the last clear's headline when another fits (kept in `save.diff`'s second
    byte); then three cover lines: those about what is still locked first (who Binary Mechanica
    are while the Twins are locked; the client's own mechs after a test unit, else the echoes
    still in development), two variants each, then the trade press's own (18), without
    repeats. Templates fill in the maker, the unit and the count of echoes. Scenario 126
    measures every line against the layout (`COVER_W_*`).
  - Then the masthead, the grade's APPROVED sticker and a barcode; then the unlock screen if
    the clear unlocked a mech, then the title.
- **The masthead** is "PROCUREMENT TODAY", the owner's pick.

**The test unit's grey** is made by `tools/gen_mechexpo_assets.py`, not by hand: for each body in
`GREY_BODIES` (Shadow, Beam, Tank, the combined Twins, twin A, twin B, Seraph) every part recipe
is packed again as `grey_NAME` (`ASSET_GREY_*`), the same geometry with its colours mapped by
`grey_colour()`: a maker's saturated colour to the UAPC's grey paint (lighter for a lighter
colour), a neutral one to a gunmetal-to-primer ramp by its lightness, texture colours the same
way, the emissive glows the UAPC's pale blue. `assets.akr` lists the pairs (`GREY_FROM`,
`GREY_TO`); `anim.akr` fills a grey mesh table a mech at a time, the first time that mech is
drawn grey, and draws from it while `anim_grey` is set, which the game sets around a test
unit's bodies (`p_grey`), the split Twins' twin B included. The grey parts add 485,368 bytes of
meshes to the ROM (83,896 of them Seraph's) and 18 4-bit palettes. Shadow's and Seraph's are
packed though each has the other as its final: the owner's rule is a grey for every body
(scenario 125's VIEW 0 still fights Shadow's).

**Budgets** (scenarios 117-119, debug builds, peaks): the schedule page 275,000 CPU and 353,000
GPU cycles; the reveal 256,000 and 188,000; the cover 310,000 and 350,000; the fights with the
test unit 699,000 and 616,000 (scenario 125: Shadow against its grey copy 587,377 and 506,820,
1,888 triangles; the split Twins against theirs, four bodies, 595,066 and 529,384, 2,025
triangles); no late frames.

**Tests:** scenarios 116-127 in `tests/ladder/harness.akr` (the whole game), run by
`tests/check.sh` (`tests/ladder/run.sh SCENARIO VIEW FRAMES OUT`; `tests/run.sh` runs VIEW 0):
116 EASY against the masher, 117-119 a whole run on each grade (EASY with the Hero, NORMAL with
Shadow, HARD with Tank: the rivals drawn and checked, the Twins drawn while locked, a lost fight
and its continue, the levels, the reveal, the final (the Double-blade Hero, Seraph, the test
unit), the cover, the unlocks (the Double-blade Hero on EASY, Seraph on NORMAL), the stamps, the
save written, each screen's budget), 120 the lot over 300 seeds a mech, 121 the save's migration
(and the stamps on the select and the spec sheet), 122 the difficulty select, 123 the schedule
page, 124 the reveal (VIEWs 4 and 5: Shadow's final, Seraph, and its VS card), 125 the test unit
in a fight (VIEW 0's grey Shadow set by the harness, since Shadow's final is Seraph), 126 the
cover, 127 a continue.

## Stages

Stages are data (the pitch: "a floor (flat for now), edges (walls or open), and an optional list
of timed events. Then new stages are content, not engine work"). `stages.akr` holds the table
`STAGES`, a `Stage` a row:

| Field | What |
|---|---|
| `name`, `short`, `venue`, `blurb`, `colour` | the stage select's card (`short` where `name` does not fit) |
| `half` | the edges are at x = −half and +half |
| `edge: [2]Edge` | the −x and +x sides: `Edge.Wall` or `Edge.Open` (a lip, with ring-outs: [MOVES.md](MOVES.md#stages-and-ring-outs)) |
| `tilt` | the floor's slope across x; 0 (every stage is flat for now; the carrier's deck later) |
| `art: StageArt` | the plane chip's set: BG1's atlas, map, palettes, width, the art row on the floor line (`hall_line`) at depth `hall_z`, the parallax bands; BG2's atlas, map, palettes, texels a metre, the texel of world 0, what shows outside its map (`floor_out`), how far its rows go; the backdrop's four colours and their rows; `PLN_PRIO`; the camera's far plane (`clip_far`, 300 m); the layers a super's darkening reaches (`dark`) |
| `nprops`, `props` | up to 6 polygon props: a mesh at (x, 0, z) turned by yaw, drawn while the view comes within `near` m of x |
| `ncity`, `city` | up to 8 meshes of a city in polygons, in the world's coordinates, drawn at the origin every frame into the PL layer (the rooftop's city, the port's harbour; the hangar has none): the stage's priorities put PL behind BG2, and everything drawn after the city (the props, the mechs, the effects) is PH, in front of the deck (`stage_props()`, `stage_props_end()`) |
| `music` | the fight's track: 0, the fight track (`music_fight()`) |
| `nevents`, `events` | up to 4 timed events, none yet: `StEv.Fall` (a falling building across x0..x1 at frame `at` of a round, for `len` frames, with `power`, leaving rubble) and `StEv.Tilt` (the deck tilting to `amount` radians over `len` frames). Nothing runs them yet |

| Stage | Edges | Art | Props |
|---|---|---|---|
| `ST_HANGAR`, the demo hangar | walls at ±36 | `stage_art.akr` (`tools/gen_mechexpo_stage.py`) | the hangar's walls, two banner towers (B's) |
| `ST_ROOFTOP`, the rooftop showcase | a wall (the stairwell's housing) at −26, open at +26 | `roof_art.akr` (`tools/gen_mechexpo_rooftop.py`): the far shore, the moon and the sea on BG1 behind the [city in polygons](#the-rooftops-city) (PL) behind the roof deck on BG2, the deck transparent past its edges | the housing, the far parapet with three floodlight masts, the open edge's kerb (`props/rooftop/`, packed by the same generator into `roof_props.akr`), two banner towers; the city (`props/rooftop_city/`, packed into `roof_city3d.akr`) |

| `ST_PORT`, the container port | open at −30 (the quay's edge over the water), a wall (stacked containers) at +30 | `port_art.akr` (`tools/gen_mechexpo_port.py`): the far harbour and the Bay Bridge on BG1 behind the [harbour in polygons](#the-container-port) (PL) behind the apron's asphalt on BG2, the apron transparent past the open edge and past the landside crane rail | the container wall, the quay's coping and bollards (`props/port/`, packed by the same generator into `port_props.akr`); the harbour: the water, the apron past the rail, two gantry cranes, the container ship, the yard (`props/port_harbour/`, packed into `port_harbour.akr`) |

- **The fight's stage** is `fight.stage`, set by `fight_init()` from `fight_stage(id)` (called
  before it; the hangar until then), so a fight's stage is part of its state and replays. The
  fight, the camera, the stage's drawing and the CPU read it through `stage_now()`.
  `FIGHT_MAX_SEP` (36 m) stays a rule of every stage.
- **Choosing:** Versus and Training pick the stage on the stage select after the character
  select (`stage_select.akr`, drawn by `draw_stage_select()` in `menus.akr`); with one stage it
  is skipped. A card is a third of the page with three stages (96 px): on a card narrower than
  120 px the venue and the blurb wrap to the sheet (`wrap_text()`), the edges go without their
  EDGES label and the RING-OUTS tag sits 6 px lower; two cards are drawn as before. The arcade takes its stages from `LADDER_STAGES`: the hangar for the company
  fights, the rooftop for the final ([The arcade ladder](#the-arcade-ladder)). The title's attract view is the hangar.
- **Loading:** `stage_show()` loads the current stage's art (BG1 into ATLAS_1 and palettes
  244–249, BG2 into ATLAS_0 and 240–243) whenever the planes go on, so only one stage's art is
  in VRAM; the rooftop's props' pack (slot 13, palettes 200–203) and its city's (slot 14, palettes
  204–211) are loaded once at boot, the port's props' (slot 16, palettes 256–272) and harbour's
  (slot 17, palettes 288–300) the first time the port is shown (`stage_load()`): loaded at boot,
  their 40 KB took the boot a tick longer, and scenario 69, which counts its frames from the
  first, came out one short.
- **Adding a stage:** its art (a generator writing `art/stage_*` and an `.akr` of constants), its
  props, and a row in `STAGES` (with `STAGES_N`). The rooftop's generator is the example.
- **Tests:** scenarios 90–99 and 112–115 in `tests/stages/harness.akr` (the whole game): the
  hangar, the ring-outs, the lip, the closed side, the Twins, the CPU, the stage select, the
  budget, and four views of the rooftop's city (112 the fight's start, 113 the camera fully out,
  114 the open edge, 115 a ring-out; `tests/run.sh N FRAMES OUT` writes `OUT.png`). The port's,
  140–150 in the same file: 140 the fight's start, 141 the camera fully out, 142 by the container
  wall, 143 by the quay's edge, 144 a throw off the quay (the ring-out at −x, the loser 12 frames
  into its fall), 145 the wall stopping a knockdown, a throw and a walk, 146 the stage select to
  the port (every word of the cards fits the narrow sheet), 147–149 the budget, 150 the camera
  drifting (with `SEQ` for its frames).
- **The budget on the rooftop** (scenarios 98 and 99, CPU against CPU through the real game, a
  release build, with the city): the Hero against the Double-blade Hero 620,732 CPU cycles and
  780,013 GPU cycles at the peak, 2,197 triangles (577,457 and 642,509 with a mech within 8 m of
  the open edge); the split Twins against Tank 600,660 and 1,002,370, 2,135 triangles. With
  Osaka's city in polygons (until 2026-10-13) they were 654,591 and 825,722, 2,317 triangles, and
  633,953 and 1,059,699, 2,257. The city alone costs about 69,000 CPU and 71,000 GPU cycles a
  frame with the camera fully out (scenario 113, the mechs idle), 70,000 and 80,000 at the open
  edge (114); Osaka's cost 104,000 and 111,000, 105,000 and 145,000. Shadow against the split
  Twins (scenario 109's run, put on the rooftop for the measurement): 695,678 and 892,367, 2,339
  triangles, the worst fight measured there (729,468 and 932,847 with Osaka's); no late frames.
- **The budget on the port** (scenarios 147–149, CPU against CPU through the real game, a release
  build; 1P backs up to the quay edge for its first 400 frames): the Hero against the
  Double-blade Hero 582,554 CPU cycles and 708,418 GPU cycles at the peak, 2,024 triangles
  (536,217 and 610,847 with a mech within 8 m of the open edge); the split Twins against Tank
  571,292 and 958,336, 1,992 triangles; Shadow against the split Twins, with its mine, bolt, curse
  and Total Eclipse kept going (as scenario 109), 661,944 and 875,703, 2,152 triangles, the worst
  fight measured there. No late frames. Without the props and the harbour they are 496,785 and
  602,902 (1,743 triangles), 492,200 and 843,131 (1,646), 574,932 and 767,444 (1,850). With the
  mechs idle (scenarios 140–143, the mean of 14 frames) the harbour alone costs 68,000–72,000 CPU
  and 90,000–111,000 GPU cycles a frame and 258–284 drawn triangles; the props add 5,000–12,000
  CPU cycles (and 41,000 GPU cycles with the container wall filling the right of the view, 142).

### The rooftop's city

The expo is held in Yokohama in October 2000, at the convention centre on the waterfront of
Minato Mirai 21 (the district built out for a real expo, YES'89), and the rooftop looks over it
at the blue hour. Its buildings are polygons, made with the Asset Kit by
`props/rooftop_city/make_city.py` (its recipes and its Pillow-drawn textures) and packed by
`tools/gen_mechexpo_rooftop.py` into `roof_city3d.akr` and `art/stage_roof_city_*`; the far
shore, the moon and the sea are BG1's, painted by the same generator. Six meshes, 420
triangles, each in the world's coordinates and drawn at the origin; every recipe passes
`verify`. As the place stood in 2000: nothing that opened later. Positions are in metres: x
across the fight plane (the open edge at +26), z behind it (the parapet at 30), y up from the
deck, the sea at −48.

| Mesh | Triangles | What |
|---|---|---|
| `city_mm` | 76 | Landmark Tower (x −112, z 330): a square shaft tapering from 44 m to 30 m, 118 m above the deck, under a stepped crown of four set-back storeys (a cool lit band, a storey of windows, a white lit band, a dark cap) with red aircraft lights; Queen's Square (x −90 to −22, z 300): three towers stepping down toward the sea, 78, 56 and 36 m above the deck, each roof a gentle slope falling seaward with a cool lit edge (the steps between the towers larger than the slopes, so the three edges do not line up into one) |
| `city_towers` | 64 | eleven office and hotel towers inland (x −262 to 12, z 196–334), 11 to 72 m above the deck, three with a cool lit crown band |
| `city_wheel` | 24 | Cosmo Clock 21 (x 72, z 196), on the harbour side: the wheel as one disc 72 m across facing the fight (so that a texel of the clock is a pixel or more from every view), its hub 20 m above the deck, in a 64 × 64 cutout texture (a muted lit rim with 16 dim gondola lights, eight spokes two texels thick, and at the hub the clock, a dark disc in a lit ring reading 20:00 in white digits 4 × 7 texels); its two legs, the low building at its foot and its reflection |
| `city_bay` | 90 | across the harbour: the Bay Bridge (z 356, x 150–330: a girder with its lit lamp line, two towers of two legs, the outer and middle stays of its four fans), the Marine Tower (x 132, z 336: a slim tapering hexagon, its lit observation deck, a green beacon) and the moon's glade on the open water |
| `city_venue` | 46 | by the water on the right: the convention centre's exhibition hall (x 112–232, z 226–266, 20 m high: windows along its front, its eaves, six blue banners and a MECH EXPO 2000 sign on its roof) and its reflection, and behind it the sail hotel (x 207–237, z 287–296, rising to 80 m above the water: a crescent of eight faces bowed toward the fight, its outline rising to a rounded peak near its seaward end, white with faint floor lines and a few lit rooms) |
| `city_quay` | 120 | below the open edge: the promenade (x 54–80, z 40–300) with 17 lamps, four kiosks with neon signs and two sign pylons; the tall ship in her dock (a white four-masted barque 44 m long, broadside at z 124, three square-rigged masts and a fourth without yards, 22–24 m tall so that they stay under the venue's sign from the open edge, her deck lights and her reflection), the dock's arm behind her, and a harbour launch with her cabin lit |

- **The views.** The space between the mechs is kept quiet. The fight's start (scenario 112)
  has Landmark Tower and Queen's Square behind 1P, the wheel behind 2P and the moon over the
  bay; the widest view (113) the whole skyline from the district to the wheel and its clock
  beside 2P, the venue's sign and the sail hotel; the open edge (114) and a ring-out (115) the
  harbour below: the wheel, the venue and its sign, the tall ship, the promenade's lamps and
  neon, the sail hotel, the Bay Bridge and the moon. The city stays cooler and quieter than
  the mechs: the warm lights are sparse windows, the lamps and the moon.
- **What is a polygon.** Everything with sides to turn. What stays on BG1 (repainted) is what is
  too far to have any: the far shore across the harbour (inland a low skyline in the haze with a
  few pale windows, then the bay's far shore with red chimney lights, then open water), the
  moon (2000-10-12 was the eve of a full moon, which rises in the east, over the bay, at
  dusk), the glow along the horizon, the sea from the horizon down to the parapet with its
  ripples, the shore lights' broken reflections and the moon's glade, and below the parapet's
  line, seen past the open edge, the harbour's water. The sea is BG1, behind every polygon.
- **Reflections.** A light's reflection is a card hanging below the waterline under it, where its
  mirror image would be (an 8 × 32 cutout streak broken into ripples, warm or white); only
  nearer polygons hide it. Only lights with open water between them and the camera have one: the
  ship, the launch, the wheel, the hall and the moon. The promenade's lamps would not show
  one (from the roof the quay hides where it would be), and the far landmarks' are below the
  parapet's sight line.
- **Windows.** A building is a box (Queen's Square a prism) in emissive textures: a 32 × 32 texel
  tile of 8 × 8 cells, 6 to 12 % of the windows lit and the odd lit floor, a front and a darker
  side tone, so a building turns as the camera moves. The cells are 5.6 m for the towers 196–290
  m back and 8 m for those as far as Landmark Tower, so that a window's texel stays about a pixel
  or more and does not shimmer; Queen's Square has curtain-wall glass in a blue of its own. Every
  texture is drawn in the colours of two shared sets (`WINDOW`, `LANDMARK` in the script), so the
  13 tiles take two palettes. The venue's sign is drawn at two texels a dot, so that from every
  view (about 0.6 pixel a texel) no stroke falls between the pixels.
- **Layers.** The city is PL, the deck BG2 and the props and mechs PH, in the order BG1 0, PL 1,
  BG2 2, BG0 3, PH 4 (`ROOF_PRIO`). The compositor, not the depth test (the planes have no
  depth), puts the deck in front of the city, and the city shows below the lip past the open
  edge where the deck is transparent. The mechs, the props and the effects are PH, so on the
  rooftop they draw in front of the HUD's frame (BG0), which is in front of them in the hangar.
  A super's darkening and Shadow's Total Eclipse reach PL too (`StageArt.dark`).
- **What is not drawn.** The compositor hides what is under the deck, but the GPU has already
  drawn it, so the city does not go there: the deck and the parapet hide everything below a
  sight line over the rail (`hidden_base()`, with a 4 m margin: about y = −13 at z = 200 and
  −22 at z = 330), so a building left of the open edge starts there. Past the open edge the
  sea's level shows only from about x = 45 (the camera at its furthest, 23.5) or x = 70 (at 20).
  A roof above the eye (14 m), the +x face of a building right of x = 32 and the −x face of one
  left of x = −30 (the camera's x runs −22 to 24) are not made, nor the sail hotel's foot
  (behind the hall), nor the promenade's +x edge (the camera is always to its left); a sign, a
  lamp, a stay or a reflection is one face.
- **Levels of detail and near culling are not used.** The camera only dollies 16–31 m, so a mesh
  100 m or more away changes size by a tenth: no level would ever be chosen. Cutting Osaka's
  ranks into meshes 70 m wide, each drawn only while the view reached it, saved 11,000 CPU
  cycles (2 %) on the widest view; the meshes stay whole.
- **VRAM.** Texture slot 14 (13 tiles, 8,781 bytes of 32,768, loaded once at boot) and 4-bit
  palettes 204–211 (the swatch's six and the textures' two). Nothing else: no
  atlas, no table, no second palette bank; BG1's art is 180 tiles (279 with Osaka's). The
  camera's far plane on the rooftop is 400 m (`ROOF_CLIP_FAR`; the hangar keeps 300): the Bay
  Bridge's far side, 364 m back, is the farthest polygon.

### The container port

Honmoku pier, berth D-5, Port of Yokohama, late on 2000-10-12: where the exhibitors' mechs came
ashore, the same city as the rooftop some hours later. `tools/gen_mechexpo_port.py` paints the
plane art (`port_art.akr`, `art/stage_port_sky.*`, `art/stage_port_deck.*`) and packs the
polygons: the props (`props/port/make_port.py`, packed into `port_props.akr`) and the harbour
(`props/port_harbour/make_harbour.py`, packed into `port_harbour.akr`). Every recipe passes
`verify`, and running the generator twice writes the same files. Positions are in metres: x
across the fight plane, z behind it, y up from the apron.

- **Layout.** The open quay edge is at x = −30 and the container wall at +30 (`PORT_HALF`): the
  rooftop's sides flipped, so on the port 1P starts with its back to the drop. The half-width
  puts 21 m between each start mark (x = ∓9) and its side, where the rooftop's open edge is 17 m
  from 2P's: from the start it takes two throws (about 10 m each) and a knockdown to ring a mech
  out, not two throws. Past the edge the apron drops 3.5 m to the water (`WATER_Y`).
- **The look.** Sodium floodlights over worn asphalt, against the rooftop's cool blue hour. Every
  colour of the props, the harbour and the apron is graded for high-pressure sodium light
  (`sodium()`: multiplied by the lamp's colour, greyed a fifth), but for the near crane's light
  blue, which is kept. The backdrop's sky is darker than the rooftop's (`#04050a` at the top), with
  a brown sodium haze at the horizon. No events: the falling containers (`StEv.Fall`) are not
  made.
- **BG2, the apron** (765 tiles, palettes 240–243): asphalt in a ramp of ten warm tones, lit in
  pools under the cranes' and the masts' lights and darker toward the water (a light level per
  tile, a texel grain and a Bayer dither between two tones, so tiles repeat); the slabs' seams
  every 6 m with a twist-lock socket at each crossing; yellow lane lines along x at z = −7 (double)
  and 7, a dashed white line and arrows nearer; the berth's D-5 and HONMOKU PIER on the asphalt
  behind the fight; the quay's pale coping along the open edge with its yellow line; and at
  z = 20 the cranes' landside rail, where BG2 ends: past it, and past the open edge, BG2 is
  transparent and the harbour's polygons show.
- **BG1, the far harbour** (662 tiles, palettes 244–249), its row 184 on the water 330 m back: the
  Bay Bridge's near tower (two white legs, 104 rows tall from the water) with its fans of lit
  stays and its deck 34 rows up, running behind the ship; the far shore's low band of warehouses
  and lights, Daikoku's cranes with red lights, the far city's towers with Landmark Tower's red
  light; below the line the far water with the bridge's and the shore's broken reflections. The
  bridge sits at the left, where it shows over the open water past the quay's corner.
- **Layers** as the rooftop's (`PORT_PRIO`, `0x41220033`): BG1 0, PL 1 (the harbour), BG2 2 (the
  apron), BG0 3, PH 4 (the props, the mechs, the effects). The water runs 6 m under the apron at
  the open edge, so a mech falling past the lip sinks into it (the depth test hides it below the
  water) and is not drawn over the quay; the apron hides what is under it. A super's darkening
  reaches PL (`PORT_DARK`, `0x2E`).

| Mesh | Triangles | What |
|---|---|---|
| `port_wall` (prop, PH) | 48 | the container wall at x = 30: eleven rows of 40-ft containers (12.19 × 2.44 × 2.59 m) from z = −8 to 19.8, two to four high (5.2–10.4 m), long axis along x; the arena sees their doors and, at a slant, the long sides of the front row and of every container above the row in front of it. A box a row, each face in a texture of the row's stacked containers (16 × 16 texels a door, 64 × 16 a side: six invented shipping lines, KUROSHIO, TRIDENT, HOKUSEI, AMBERLINE, NORDVIK and MERIDIAN, plain leasing boxes, and crates of the five makers with their emblems: Momentum Robotics, Umbral Research, Raikō, Heartland and Binary Mechanica) |
| `port_kerb` (prop, PH) | 40 | the quay's coping along the open edge (0.45 m wide, 0.3 m high, z −12 to 20, its top painted yellow) and two mooring bollards on it |
| `port_water` | 22 | the water past the open edge (x −400 to −24, z −18 to 160), black with ripples catching the light (a 32 × 32 tile, 32 m), and three additive reflections under the ship's and the cranes' lights; in two pieces, so that only the near one is ever clipped at the eye |
| `port_apron` | 32 | the apron past the landside rail (x −30 to 90, z 19.5 to 52) in a 16 m asphalt tile, the waterside rail at z = 48, the berth's coping at z = 52 and the open edge's; the yard's ground behind the container wall (x 60 to 300) |
| `port_crane_a` | 142 | gantry crane A in Honmoku's light blue, working the ship: legs at x = 11 and 29 on the rails at z = 20.6 and 48, bogies, the portal 44 m up, sill girders, the boom 49 m up from z = 4 over the ship to z = 104 with four floodlights under it, the apex at 78 m with red aircraft lights, its stays, the machinery house, two floodlights under the portal with their glow, the trolley and its lit cab, and a container on the spreader 16 m up; lit from below |
| `port_crane_b` | 86 | gantry crane B, white with a red and white boom and apex (legs at x = 49 and 67), idle with its boom raised 75°; no bogies, house, floodlights or trolley (it is seen least) |
| `port_ship` | 86 | the container ship moored at the berth (x −20 to 270, z 54 to 86, her main deck 10 m above the apron): her navy hull in three stretches (KUROSHIO along the middle), the transom, an eleven-storey accommodation block at the stern (x −18 to −2, to 42 m) with its lit windows and bridge, the bridge wings, the funnel with the line's wave, a mast with its lights, and her deck cargo in eight blocks of two or three bays, four to seven high (to 28 m) |
| `port_yard` | 48 | the yard's stacks behind the container wall (three to five high) and two floodlight masts 30 m tall (in the yard by the wall, and at the quay's far corner) with their glow |

- **The views.** The fight's start (scenario 140) has the bridge and the far shore over the open
  water behind 1P, the ship's lit accommodation block between the mechs, its cargo and crane A's
  legs behind 2P; the widest view (141) the cranes' portals and floodlights overhead; the wall
  (142) the containers' doors; the edge (143) the quay's coping over the black water.
- **What is not drawn.** The camera's eye is 6.5 m up and its x runs −27.5 to 18.5: tops above the
  eye, faces toward +z and the far sides of things are left open. Nothing reaches nearer than
  z = −18, and what does reach behind the eye is small: a big face crossing the near plane cost
  about 15,000 CPU cycles a frame (the coping, when it ran to z = −40).
- **VRAM.** The props' pack in texture slot 16 (22,656 bytes of 32,768: the wall's 17 textures)
  and 4-bit palettes 256–272; the harbour's in slot 17 (17,792 bytes) and palettes 288–300. Both
  are in VRAM's second megabyte and the second palette bank, which the cart did not use, and both
  are loaded once, the first time the port is shown. The plane art uses the hangar's
  atlases, maps and palettes. The camera's far plane on the port is 420 m (`PORT_CLIP_FAR`).

## Rendering, VRAM and budgets

- **Depth buffer and perspective texturing**; every recipe has
  `"verification": {"required": true, "depth": true, "perspective": true}`.
- **Layers** (the plane chip, [docs/PLANES.md](../../docs/PLANES.md)): the backdrop gradient,
  BG1 for the parallax (crowds, booths, banners), BG2 for the floor, polygons for the mechs, the
  effects and the props, BG0 for the HUD. The plane chip, its line channels and priorities are D's.
- **Texture slots:** B's pack uses 0–7, D 8–14 (and 16–17, the port's); slot 15 is the
  standard library's font. B's
  8-bit palettes come down from 14 as the pack assigns them; D uses 4-bit palettes 240–254.
  Tell the director if either side needs more. **In `art/`, D's files start with `stage_` or
  `ui_`**; everything else there is B's pack, which `gen_mechexpo_assets.py` rewrites.
- **D's use, as built:** atlases ATLAS_0 the floor, ATLAS_1 the hall, ATLAS_2 the HUD, ATLAS_3
  the menu page; texture slots 8 (fonts), 9 (UI sprites), 10 (effects); palettes 240–254 (244 is
  lent to the menu page and the hall's put back); a backdrop table at 0x582000; line channels 0,
  2 and 7. Priorities: BG2 0, BG1 1, the mechs 2, BG0 (the HUD's frame) 3, the interface list 4.
- **Palettes, as built with Beam, Tank, the Twins, Shadow, the test units' grey parts and Seraph
  (mx-seraph):** the pack's 4-bit palettes are 0–47 (its surface, emissive and textured
  palettes), counting up from 0 (0–27 before the grey parts, 0–43 before Seraph); its 8-bit
  palettes would come down from 14. The pack's textures take texture slots 0 and 1: 30,848 bytes
  in slot 0 and, since Seraph, 5,248 in slot 1 (47,608 bytes of tiles before de-duplication); the
  pack's ROM in `art/` is 1,181,648 bytes (1,008,480 before Seraph).
- **The particle effects (fx.akr, mx-fx's):** texture slot 11 and 4-bit palette 192
  (`tools/gen_mechexpo_fx.py`, `fx_art.akr`); 193–195 are kept for more. Seraph's sprites
  (mx-seraph-fx: a four-point glint in four turns, the mark's sigil, a feather) are on the same
  sheet after the others, which keep their rectangles: rows 0–154, 19,840 bytes (14,592 before). A pool of 80 particles,
  at most 52 spawned a frame; at their busiest (scenarios 50–54) about 75,000 CPU cycles a frame
  in a release build.
- **The menus (mx-menus):** texture slot 12 (`ui_menu.tex`: the small fonts FONT_MICRO and
  FONT_SERIF, the rubber stamps, the lanyard strap); 4-bit palette 196 (PAL_POWER: the chemical,
  nuclear and fusion meter icons and the Raikō, Heartland and Binary Mechanica emblems, in slot 9)
  and 197–199 (PAL_PRINT: the print layer's ramps, written at run time). In the menus BG0 is the
  print layer (the catalogue's coloured photographs behind the mechs): `ui_print.tiles` in ATLAS_2
  and MAP_BG0, put back by `hud_show(true)`; priorities there BG1 1, BG0 1 (it wins the tie), the
  mechs 2, the interface list 4 (`PAGE_PRIO` in `menus.akr`).
- **The rooftop (mx-stages):** texture slot 13 and 4-bit palettes 200–203 for its props' pack
  (`roof_props.akr`, loaded once by `stage_boot()`), texture slot 14 and palettes 204–211 for its
  city in polygons (`roof_city3d.akr`, [above](#the-rooftops-city)); its plane art uses the hangar's atlases,
  maps and palettes (one stage is loaded at a time, by `stage_show()`). Priorities on the
  rooftop: BG1 (the horizon) 0, PL (the city in polygons) 1, BG2 (the deck) 2, BG0 3, PH (the
  mechs, the props, the effects and the interface list) 4.
- **The container port (mx-port):** texture slot 16 and 4-bit palettes 256–272 for its props'
  pack (`port_props.akr`), texture slot 17 and palettes 288–300 for its harbour
  (`port_harbour.akr`, [above](#the-container-port)), both loaded once by `stage_load()` the first
  time the port is shown: slots 16–31 and the second palette bank (256–511) were unused.
  Priorities as the rooftop's.
- **The roster** (`roster.akr`): the makers and the select's ten slots; a mech's names, maker,
  booth, power source, stats, blurb and unlock rule are its row. Adding a mech is filling in its
  slot's `mech` field (the file's first comment says how). `save.unlocked` keeps bit 0 for the
  Double-blade Hero (the MVP's saves still load), a bit per later unlockable slot, and bit
  16 + slot once the arcade has been cleared with that slot's mech; `save.medals` (version 2)
  the grades each slot cleared ([The arcade ladder](#the-arcade-ladder)).
- **The arcade ladder (mx-ladder):** no new texture slot or palette of D's. Texture slot 10 holds,
  under the effects' sprites, the cover's masthead font (`FONT_MAST`, rows 49-219); slot 12 the
  APPROVED seals (`UI_SEAL*`, 13 and 9 px, at row 116 beside the strap); both written by
  `tools/gen_mechexpo_ui.py`. The reveal uses the print layer (BG0, palettes 197-199) and the
  GPU's fog register while it shows. The model pack took 4-bit palettes 28–43 for the grey
  parts (above).
- **Triangles:** a mech about 1,600–1,800 (the sketches are 1,632 and 1,734; Seraph, with wings
  and a halo, 1,892); the frame limit is
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
