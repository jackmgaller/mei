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
| Arcade ladder: CPU mirror match, then your echo (or, as the echo, the original). Clearing it with the Hero unlocks the Double-blade Hero, saved to the memory card | Memory card saves beyond the unlock |
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
source's charge-up with the burst, and a heavy or crushing `sfx_hit` scatters debris. By state,
once a fight frame from `game.akr`'s `sound_poll()` (the mechs' parts in `beam_fx.akr`'s
`beam_sfx()`, `tank_fx.akr`'s `tank_sfx()` and `twins_fx.akr`'s `twins_sfx()`):
`sfx_couple(on: bool)`, `sfx_react()`, `sfx_charge_full()`, `sfx_void(back: bool)`,
`sfx_smoulder()`. For the brochure: `sfx_page()` (from `menus_page()`), `sfx_stamp()`,
`sfx_pass()`, `sfx_shutter()` (`menus.akr`'s `menus_sfx()` times the stamps to their drawing).

**Loops** (Tank's treads, Beam's charge hum, which the Twins' Fusion Focus borrows lower, and the
Shock Grip's buzz): `sfx_hold(slot, id, pri, x, pitch, gain)` every frame a loop should sound, a
slot a side; `sfx_tick()` (once a frame, always, after the game's update) fades out over four
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
| `ncity`, `city` | up to 8 meshes of a city in polygons, in the world's coordinates, drawn at the origin every frame into the PL layer (the rooftop's; the hangar has none): the stage's priorities put PL behind BG2, and everything drawn after the city (the props, the mechs, the effects) is PH, in front of the deck (`stage_props()`, `stage_props_end()`) |
| `music` | the fight's track: 0, the fight track (`music_fight()`) |
| `nevents`, `events` | up to 4 timed events, none yet: `StEv.Fall` (a falling building across x0..x1 at frame `at` of a round, for `len` frames, with `power`, leaving rubble) and `StEv.Tilt` (the deck tilting to `amount` radians over `len` frames). Nothing runs them yet |

| Stage | Edges | Art | Props |
|---|---|---|---|
| `ST_HANGAR`, the demo hangar | walls at ±36 | `stage_art.akr` (`tools/gen_mechexpo_stage.py`) | the hangar's walls, two banner towers (B's) |
| `ST_ROOFTOP`, the rooftop showcase | a wall (the stairwell's housing) at −26, open at +26 | `roof_art.akr` (`tools/gen_mechexpo_rooftop.py`): the far shore, the moon and the sea on BG1 behind the [city in polygons](#the-rooftops-city) (PL) behind the roof deck on BG2, the deck transparent past its edges | the housing, the far parapet with three floodlight masts, the open edge's kerb (`props/rooftop/`, packed by the same generator into `roof_props.akr`), two banner towers; the city (`props/rooftop_city/`, packed into `roof_city3d.akr`) |

- **The fight's stage** is `fight.stage`, set by `fight_init()` from `fight_stage(id)` (called
  before it; the hangar until then), so a fight's stage is part of its state and replays. The
  fight, the camera, the stage's drawing and the CPU read it through `stage_now()`.
  `FIGHT_MAX_SEP` (36 m) stays a rule of every stage.
- **Choosing:** Versus and Training pick the stage on the stage select after the character
  select (`stage_select.akr`, drawn by `draw_stage_select()` in `menus.akr`); with one stage it
  is skipped. The arcade takes `LADDER_STAGES[ladder]`: the hangar, then the rooftop for the
  final. The title's attract view is the hangar.
- **Loading:** `stage_show()` loads the current stage's art (BG1 into ATLAS_1 and palettes
  244–249, BG2 into ATLAS_0 and 240–243) whenever the planes go on, so only one stage's art is
  in VRAM; the rooftop's props' pack (slot 13, palettes 200–203) and its city's (slot 14, palettes
  204–211) are loaded once at boot.
- **Adding a stage:** its art (a generator writing `art/stage_*` and an `.akr` of constants), its
  props, and a row in `STAGES` (with `STAGES_N`). The rooftop's generator is the example.
- **Tests:** scenarios 90–99 and 112–115 in `tests/stages/harness.akr` (the whole game): the
  hangar, the ring-outs, the lip, the closed side, the Twins, the CPU, the stage select, the
  budget, and four views of the rooftop's city (112 the fight's start, 113 the camera fully out,
  114 the open edge, 115 a ring-out; `tests/run.sh N FRAMES OUT` writes `OUT.png`).
- **The budget on the rooftop** (scenarios 98 and 99, CPU against CPU through the real game, a
  release build, with the city): the Hero against the Double-blade Hero 619,133 CPU cycles and
  762,371 GPU cycles at the peak, 2,195 triangles (577,165 and 640,455 with a mech within 8 m of
  the open edge); the split Twins against Tank 599,396 and 1,001,968, 2,135 triangles. With
  Osaka's city in polygons (until 2026-10-13) they were 654,591 and 825,722, 2,317 triangles, and
  633,953 and 1,059,699, 2,257. The city alone costs about 69,000 CPU and 70,000 GPU cycles a
  frame with the camera fully out (scenario 113, the mechs idle), 70,000 and 79,000 at the open
  edge (114); Osaka's cost 104,000 and 111,000, 105,000 and 145,000. Shadow against the split
  Twins (scenario 109's run, put on the rooftop for the measurement): 695,472 and 873,118, 2,335
  triangles, the worst fight measured there (729,468 and 932,847 with Osaka's); no late frames.

### The rooftop's city

The expo is held in Yokohama in October 2000, at the convention centre on the waterfront of
Minato Mirai 21 (the district built out for a real expo, YES'89), and the rooftop looks over it
at the blue hour. Its buildings are polygons, made with the Asset Kit by
`props/rooftop_city/make_city.py` (its recipes and its Pillow-drawn textures) and packed by
`tools/gen_mechexpo_rooftop.py` into `roof_city3d.akr` and `art/stage_roof_city_*`; the far
shore, the moon and the sea are BG1's, painted by the same generator. Six meshes, 414
triangles, each in the world's coordinates and drawn at the origin; every recipe passes
`verify`. As the place stood in 2000: nothing that opened later. Positions are in metres: x
across the fight plane (the open edge at +26), z behind it (the parapet at 30), y up from the
deck, the sea at −48.

| Mesh | Triangles | What |
|---|---|---|
| `city_mm` | 76 | Landmark Tower (x −112, z 330): a square shaft tapering from 44 m to 30 m, 118 m above the deck, under a stepped crown of four set-back storeys (a cool lit band, a storey of windows, a white lit band, a dark cap) with red aircraft lights; Queen's Square (x −90 to −22, z 300): three towers stepping down toward the sea, 78, 56 and 37 m above the deck, each roof a slope falling seaward with a white lit edge, the three slopes one wave |
| `city_towers` | 64 | eleven office and hotel towers inland (x −262 to 12, z 196–334), 11 to 72 m above the deck, three with a cool lit crown band |
| `city_wheel` | 14 | Cosmo Clock 21 (x 18, z 200): the wheel as one disc 68 m across facing the fight, its hub 20 m above the deck, in a 64 × 64 cutout texture (a solid lit rim with 16 gondola lights, eight spokes two texels thick, and at the hub the clock, a dark disc in a lit ring reading 20:00 in digits 4 × 7 texels), and its two legs |
| `city_bay` | 90 | across the harbour: the Bay Bridge (z 356, x 150–330: a girder with its lit lamp line, two towers of two legs, the outer and middle stays of its four fans), the Marine Tower (x 132, z 336: a slim tapering hexagon, its lit observation deck, a green beacon) and the moon's glade on the open water |
| `city_venue` | 50 | by the water on the right: the sail hotel (x 69–99, z 231–240, rising to 80 m above the water: a crescent of eight faces bowed toward the fight, its outline rising to a rounded peak near its seaward end, white with faint floor lines and a few lit rooms, lit from its foot) and the convention centre's exhibition hall (x 112–232, z 226–266, 20 m high: windows along its front, its eaves, six blue banners and a MECH EXPO 2000 sign on its roof), with their reflections |
| `city_quay` | 120 | below the open edge: the promenade (x 54–80, z 40–300) with 17 lamps, four kiosks with neon signs and two sign pylons; the tall ship in her dock (a white four-masted barque 44 m long, broadside at z 124, three square-rigged masts and a fourth without yards, her deck lights and her reflection), the dock's arm behind her, and a harbour launch with her cabin lit |

- **The views.** The fight's start (scenario 112) has the wheel and its clock between the mechs,
  Landmark Tower and Queen's Square behind 1P and the moon over the bay; the widest view (113)
  the whole skyline from the district to the sail hotel and the venue's sign; the open edge
  (114) and a ring-out (115) the harbour below: the venue and its sign, the tall ship, the
  promenade's lamps and neon, the Bay Bridge and the moon. The city stays cooler and quieter than
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
  ship, the launch, the sail hotel, the hall and the moon. The promenade's lamps would not show
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
  left of x = −30 (the camera's x runs −22 to 24) are not made, nor the wheel's foot, nor the
  promenade's +x edge (the camera is always to its left); a sign, a lamp, a stay or a reflection
  is one face.
- **Levels of detail and near culling are not used.** The camera only dollies 16–31 m, so a mesh
  100 m or more away changes size by a tenth: no level would ever be chosen. Cutting Osaka's
  ranks into meshes 70 m wide, each drawn only while the view reached it, saved 11,000 CPU
  cycles (2 %) on the widest view; the meshes stay whole.
- **VRAM.** Texture slot 14 (13 tiles, 8,781 bytes of 32,768, loaded once at boot) and 4-bit
  palettes 204–210 (the swatch's five and the textures' two; 211 is free). Nothing else: no
  atlas, no table, no second palette bank; BG1's art is 180 tiles (279 with Osaka's). The
  camera's far plane on the rooftop is 400 m (`ROOF_CLIP_FAR`; the hangar keeps 300): the Bay
  Bridge's far side, 364 m back, is the farthest polygon.

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
- **Palettes, as built with Beam, Tank and the Twins:** the pack's 4-bit palettes are 0–25 (its
  surface, emissive and texture palettes), counting up from 0; its 8-bit palettes would come down
  from 14.
- **The particle effects (fx.akr, mx-fx's):** texture slot 11 and 4-bit palette 192
  (`tools/gen_mechexpo_fx.py`, `fx_art.akr`); 193–195 are kept for more. A pool of 80 particles,
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
- **The roster** (`roster.akr`): the makers and the select's ten slots; a mech's names, maker,
  booth, power source, stats, blurb and unlock rule are its row. Adding a mech is filling in its
  slot's `mech` field (the file's first comment says how). `save.unlocked` keeps bit 0 for the
  Double-blade Hero (the MVP's saves still load), a bit per later unlockable slot, and bit
  16 + slot once the arcade has been cleared with that slot's mech.
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
