# Fall Line

A Y2K downhill racer: a hover-sled with no engine and no brakes, one course, Time Attack. The
pitch is "Fall Line — Game Pitch" (2026-10-10); this cart is its minimum viable version. The
fictional company is a placeholder, **Synergen**, and the course is the **Synergen Glacier
Array**.

The slope is BG2, the affine plane, with real crests and run-outs: the camera always faces
straight down the fall line (yaw 0, no roll), so every screen row meets the slope along one line
of constant z, and each row is found by casting one ray against the course's side profile.

## What the MVP is

| In | Out (later) |
|---|---|
| One course, about 1.75 km, 60–90 s: three blind crests, two run-outs, ~20 gate pairs, hazards | Other courses, Circuit, CPU rivals |
| Time Attack: title → countdown → run → results with splits → retry | Split-screen, ghost exchange |
| Carve (stick or d-pad), A tuck, B hard edge, Start pause | Boost meter (R), pre-load jumps (X), kickers |
| Airtime off crests from the physics alone; a landing thump | Ice and boost-strip tiles |
| Gates: clean pass gives a small speed bump, a miss adds 2.0 s | The announcer |
| Hazards (trees, pylons, markers) knock you down for about 1 s | Ring speedometer, 3D menu carousel |
| Best run's ghost, in RAM and on the memory card | Camera yaw follow |
| Sky gradient, one band of distant ridges and towers, haze toward the horizon | |
| HUD: speed, time, split, gates | |
| Music (one breakbeat track for the run, a title loop) and sound effects | |

**Gate 1** (passed 2026-10-11). The slope engine's captured run over the crests was shown to the
owner before the gameplay went on the real slope; the fallback would have been a single grade
with polygon kickers. Known weak spots: the last ten or so rows before a crest step metres a row,
so the run-edge lines break into dashes there, and faint lines across the run flicker at mid
distance. The chase camera pitches 0.7 of the grade's angle (`CAM_FOLLOW` in `camera.akr`) so
the ridges stay in view on the steep pitches.

## Folders and owners

The MVP was built by five agents, each writing only its own files (the director, the main
session, integrated and committed). The table is kept as the map of the cart's parts. Build into
a private directory (`make B=build-fl-NAME ...`), never `build/`, when others are working too.

| Path | What | Owner |
|---|---|---|
| `slope.akr`, `sky.akr`, `plane_art.akr`, `art/plane_*`, `tools/gen_fallline_plane.py`, `tests/slope/` | The slope renderer, sky, ridges, haze, crest occlusion, the plane art and its generator, and the engine's own test cart | **A, slope engine** |
| `fallline.akr`, `game.akr`, `course.akr`, `physics.akr`, `rider.akr`, `hud.akr`, `ghost.akr`, any other top-level `.akr` not listed here, `tests/harness.akr`, `tests/run.sh`, `tests/check.sh` | The game | **B, gameplay** |
| `models/sled/`, `models/gate/`, `models/finish/`, `tools/gen_fallline_assets.py`, `assets.akr`, `art/` (except `art/plane_*`) | Hero models, and the pack of every model | **C, hero models** |
| `models/pine/`, `models/pylon/`, `models/marker/` | Small models | **D, small models** |
| `music.akr`, `mu_data.akr`, `sfx.akr`, `audio/`, `tools/gen_fallline_audio.py` | Music and sound effects | **E, audio** |

`fallline.akr` (the entry point, `cart "Fall Line", "FALLLINE"`) must compile whenever it
exists, because `make` builds every `carts/NAME/NAME.akr`. `make test-carts` runs
`tests/check.sh` (six scenarios: a bot's full run with the budgets, the countdown, a hazard, a
missed gate, pause, the memory card).

## Coordinates and the course

- 1 unit = 1 metre. **Y up. +Z is downhill** (the camera's yaw 0 looks along +z). X is across the
  run; the run is 40 m wide, x from −20 to +20, centred on x = 0.
- **The profile** is the height of the snow along the descent: a polyline of points (z, y),
  z increasing, in `course.akr` (`PROFILE`, `PROFILE_N`, struct `ProfPt { z: fixed, y: fixed }`).
  Between points the snow is straight; it does not vary with x. Crests are where the grade
  steepens, run-outs where it flattens. A crest can be rounded by adding short segments.
  B owns `course.akr` and may tune the profile; A's renderer must accept any polyline that
  descends (y never rises) and is at most 64 points.
- **Texture coordinates.** v follows the arc length s along the profile (so the snow does not
  stretch over a crest), u follows x: `u = S·x + UOFF`, `v = S·s`, with S texels a metre chosen by
  A. The map wraps along v; the run's edges are tile columns at fixed u.
- **Course objects** (gates, hazards, finish) are placed by (x, z); their y is the snow height at
  z. Models stand vertical, not tilted to the slope.

## Interfaces

**Slope engine (A) → game (B)**, in `slope.akr` (it imports `planes.akr`, `depth.akr`,
`course.akr`, `plane_art.akr` and `sky.akr`). **Status: ready.**

```
fn slope_init()                                  // planes on, depth test on, sky, ridges, haze, BG2; camera_clip(0.3, 500)
fn slope_frame(eye: vec3, pitch: fixed)          // camera_look(eye, 0.0, pitch), every line table, the depth proxy; leaves poly_upper(true)
fn slope_y(z: fixed) -> fixed                    // snow height at z (the profile, extended straight past both ends)
fn slope_grade(z: fixed) -> fixed                // dy/dz at z (negative downhill)
fn slope_s(z: fixed) -> fixed                    // arc length from PROFILE[0] to z
fn slope_layer(p: vec3, r: fixed) -> s32         // 0: hidden, don't draw; 1: in front of every crest; 2: partly behind one
fn slope_draw_layer(layer: s32)                  // the following mesh draws: depth test on, into PH (same for 1 and 2)
fn slope_haze_objects(on: bool)                  // whether the haze tints PH too (on at the start)
fn slope_cycles() -> s32                         // CPU cycles the last slope_frame() took
fn slope_horizon() -> s32                        // the horizon's screen row (off the screen when looking far down)
fn slope_top() -> s32                            // the first screen row of snow (240: none)
const SLOPE_FAR: fixed = 480.0                   // view depth where the snow has faded into the haze
```

- Call `slope_frame()` first in `draw()`, then draw the objects. `slope_layer(p, r)` takes the
  object's foot on the snow (or its centre) and a radius that covers it (its top is taken as
  `p.y + r`); it returns 0 behind the camera, beyond `SLOPE_FAR` or wholly behind a crest.
- **Never `cls()`**: `planes_on()` auto-erases to holes, and a clear would cover the planes.
- **Everything draws with the depth test, into PH.** `slope_frame()` leaves `render_depth(true)`
  and `poly_upper(true)` on. Don't turn `poly_upper` off for objects: PL is behind the snow.
- A decal on the snow (the sled's shadow, a mark) is coplanar with the snow's depth: draw it with
  `depth_offset(4)` or so, or it fights the snow.
- The interface list (`text`, `ui_*`) is in PH (above the snow). The haze tints PH on rows whose
  snow is beyond 60 m (at most -4 red, -2 green in 5-bit units at 480 m), which reaches a HUD at
  the top of the screen only while the camera looks far down a steep pitch;
  `slope_haze_objects(false)` turns it off for PH (or put the HUD on BG0).
- Cost: `slope_frame()` measured 18,100 CPU cycles a frame on average and 24,700 at most over the
  whole course in `tests/slope/` (about 2,300 a frame plus 100 a row of snow; the most rows are
  on the steep pitches, looking down); `slope_layer()` about 100 an object. GPU: the depth proxy
  fills the snow's area once, flat (50,000–60,000 cycles), besides the depth clear (38,400).
- The camera: on the steepest pitches a pitch that follows the grade fully puts the horizon above
  the screen, and the top quarter is valley haze. A pitch of about 0.7 of the grade's angle keeps
  the ridges in view.
- Gate 1: `carts/fallline/tests/slope/capture.sh` builds the engine's own test cart
  (`tests/slope/slope_test.akr`: the camera down the whole profile at 20–35 m/s, test boxes
  around each crest), prints the cycles and writes a contact sheet and a GIF of each crest and
  run-out into `build-fl-slope/gate1/`.

**Crest occlusion: a depth proxy, not a priority split.** The snow is also drawn as a few flat
quads (one per profile segment in view, as wide as the screen at their depth) into PL with the
depth test, and BG2's priority is above PL, so the quads never show but put the snow into the
depth buffer. Objects draw into PH (above BG2) with the depth test, so whatever is behind the
snow from the eye fails the test and the snow shows there. That handles every crest on screen at
once, objects partly behind a crest, and the metre a model reaches below the snow (which a
priority split would have drawn over the snow in front of it). A `PLN_PRIO` line split was
not needed: channel 4 is unused. **The depth buffer works with `planes_on`** (auto-erase,
holes, the upper bit): checked in `tests/slope/`.

**Line channels.** A: 0 (sky, `BD_COLOR`), 3 (haze, `PLN_OFS`), 7 (BG2 affine); 2 and 4 are
A's but unused. B: 1, 5, 6. Priorities (`PLN_PRIO`, set once by `slope_init`): BG1 (ridges) 1,
PL 2, BG2 (snow) 3, PH 5, BG0 6 (normal and front tiles). **BG0** is B's (HUD) if B wants it;
otherwise the HUD uses the interface list (`text`, `ui_*`), which `planes_on` puts in PH. The
colour offset enables (`PLN_MATH` bits 24–29) are A's: BG2 and PH.

**VRAM.** A uses no texture slot: the snow's atlas is `ATLAS_0` (page 12) and the ridges'
`ATLAS_1` (page 13), the maps `MAP_BG2` (32 KB) and `MAP_BG1` (4 KB), the tables
`LT_AFFINE`, `LT_FREE` (haze) and the sky gradient at `0x44B000` (the spare 4 KB, 1,024 words).
`LT_BACKDROP`, `LT_BG0`, `LT_BG1`, `MAP_FREE` and pages 14–15 (`ATLAS_2`, `ATLAS_3`) are free
for B. The model pack uses texture slots 0–9 (the kit packs only into 0–14); slot 15 stays the
standard library's font. **Palettes:** A uses 4-bit palettes **240–248** (the snow's eight bands
240–247, the ridges 248), inside 8-bit palette 15, which C's pack never takes (its 8-bit
palettes come down from 14, and 15 holds the font's palette 255).

**Models (C, D) → game (B).** A model is `models/NAME/NAME.asset.json` (several part recipes
`NAME_PART.asset.json` if needed), packed by `tools/gen_fallline_assets.py` into `art/` and
`assets.akr`, which defines every `ASSET_*` and `assets_load()`. B draws them with `mesh_xf` /
`mesh_at`. Any model with more than one part, or a glow drawn separately, also gets
`models/NAME/NAME.akr` with `fn NAME_draw(root: mat4, t: s32, variant: s32)`, which does not
import any mesh file.

**Audio (E) → game (B).** `music.akr`: `music_title()`, `music_run()`, `music_stop()`,
`music_tick()` (called once a frame), `music_duck(on: bool)` (pause). `sfx.akr`: `sfx_tick(speed:
fixed, carve: fixed, airborne: bool, tuck: bool)` once a frame (the wind and the snow hiss
follow it), and one-shots `sfx_gate()`, `sfx_miss()`, `sfx_crash()`, `sfx_land(force: fixed)`,
`sfx_countdown(n: s32)` (3, 2, 1, 0 = go), `sfx_finish()`, `sfx_menu()`. Channels: music 0–9,
sound effects 10–15.

## Style sheet

- **Look.** Y2K techno-futurism, a 1999 sports-drink advert crossed with a translucent iMac:
  cyan, silver, white and electric blue, with lime, tangerine or magenta accents; translucent
  plastic, frosted glass, fake chrome (a bright gradient strip). Big sunny sky, white snow.
- **Facing.** Models face **−Z**, the Asset Kit's convention (B turns them; the sled travels +z).
  A model's origin is on the snow under its middle. Anything that stands on the snow extends at
  least 1 m below y = 0, so it sits on a 35° slope without floating.
- **Drawing.** Depth buffer and perspective texturing. Every recipe:
  `"verification": {"required": true, "depth": true, "perspective": true}`.
- **Triangles** (the frame limit is 4,000; many hazards are on screen at once): sled ≤ 500, gate
  pair ≤ 200, finish arch ≤ 500, pine ≤ 100, pylon ≤ 60, marker ≤ 40.
- **Textures:** at most 2 per model, each ≤ 64 × 64 and 4-bit. Vertex colours and
  palette-backed materials cost no VRAM; prefer them.
- **Lighting** is baked, sun high and from the front-left of the descent.

| Model | Owner | What | Size |
|---|---|---|---|
| `sled` | C | The hover-sled with its pilot under a closed canopy (no animation) | about 2.4 m long |
| `gate` | C | A gate pair: two posts 6 m apart (centres at x = ±3); anything spanning the gap is ≥ 2.5 m above the snow | posts about 3 m |
| `finish` | C | The finish arch, spanning the run's middle 24 m | about 8 m high |
| `pine` | D | A conifer, the commonest hazard | 4–7 m |
| `pylon` | D | A pylon or post of the resort's machinery, a hazard | 3–5 m |
| `marker` | D | A run-edge marker or chevron board, a hazard | about 1.5 m |

## Building and checking

```sh
make B=build-fl-NAME build-fl-NAME/meic build-fl-NAME/mei-headless build-fl-NAME/mei-asset-probe
python3 tools/mei_assets.py verify carts/fallline/models/sled/sled.asset.json --build-dir build-fl-NAME
MEIC=build-fl-NAME/meic RUN=build-fl-NAME/mei-headless carts/fallline/tests/run.sh 1 600 /tmp/x
```

A model is done when `verify` passes and its preview sheet has been looked at. The slope is done
at Gate 1. The game is done when a full run plays from the title to the results and back, within
the CPU budget (1,000,000 cycles a tick) and the GPU budget (2,000,000).
