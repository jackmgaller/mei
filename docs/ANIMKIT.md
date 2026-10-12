# Mei Animation Kit

A command-line tool for animating rigid-part rigs, built for Mech Expo 2000
(`carts/mechexpo/`) and a companion to the [Asset Kit](ASSETKIT.md): a move is an editable JSON
file of keyframed poses, boxes and marks; `verify` checks it frame by frame as the game will play
it, `preview` draws it with Mei's real compiler and GPU, and `export` bakes every move into the
data the cart's runtime (`carts/mechexpo/anim.akr`) draws and the fight collides with.

The kit is Python 3.10+ with the standard library only (it compiles the parts' recipes with the
Asset Kit's own code). `preview` and the runtime tests need `meic` and `mei-headless`.

| Where | What |
|---|---|
| `tools/mei_anim.py` | the entry point: `verify`, `preview`, `export`, `info` |
| `tools/animkit/` | `rig.py` (rigs, posing), `move.py` (the format, sampling, plants and reaches), `verify.py`, `preview.py`, `export.py`, `summary.py` |
| `carts/mechexpo/anims/MECH/MOVE.anim.json` | the moves (the animator's); `_body.anim.json` per mech: the boxes every move starts from |
| `carts/mechexpo/anim_data.akr`, `carts/mechexpo/anims/anim_data.bin` | the export (generated: do not edit) |
| `carts/mechexpo/anim.akr` | the runtime |
| `carts/mechexpo/tests/anim/` | the kit's test cart (`anim_test.akr`, `run.sh`, `check.sh`), test moves (`anims/`) and examples (`examples/`) |
| `tests/test_animkit.py` | the Python suite |

## Quick reference

With a private build directory (`make B=build-mine build-mine/meic build-mine/mei-headless`
once):

```sh
python3 tools/mei_anim.py verify carts/mechexpo/anims/hero/atk_f.anim.json
python3 tools/mei_anim.py preview carts/mechexpo/anims/hero/atk_f.anim.json -o build-mine/anim/atk_f --build-dir build-mine
python3 tools/mei_anim.py info carts/mechexpo/anims/hero/atk_f.anim.json     # frame by frame: boxes, marks, motion
python3 tools/mei_anim.py export                                              # every move into the cart's anim_data
```

1. **Write** the move: keys (poses and their timing), boxes, marks, motion, plants. Start from
   `_body.anim.json` (`"base"`) so the hurt and push boxes are there.
2. **`verify`** until it passes. It names the frames, the parts and by how much.
3. **`preview`**, and look at `contact.png` (every key, the phases' edges, and about 24
   frames) and `frames/frame_NNN.png` (every frame).
4. **`export`**, then build the cart. A move is done when `verify` passes and its contact sheet
   has been looked at (`carts/mechexpo/README.md`).

## Coordinates

1 unit = 1 m, Y up, 60 frames a second. A rig is authored facing −Z, +X its left side.
**Fight-local** coordinates (boxes, offsets, motion, reaches): x forward (the model's −Z), y
up, the origin the **root**, on the floor under the pelvis. The fight places the root and turns
the mech to face +x or −x (`anim_place()`), so one animation serves both facings.

**Rotations** are the Asset Kit's: `[x, y, z]` in degrees, applied X, then Y, then Z, about the
parent joint's axes (R = Rz Ry Rx). On a hanging limb +X swings it forward; on an upright one
(the torso, the head) +X leans it back. +Y turns the left side forward, so −Y brings the right
shoulder forward. Z is applied last, about the parent's front-to-back axis: on a hanging limb +Z
swings a left limb out and a right limb in, but on a limb raised forward by X the same Z swings
it across the body; check a raised arm in the preview. Rotations are not mirrored between
sides.

## Rigs

A rig is `models/NAME/NAME.rig.json`, written by the model's generator (B's,
`tools/gen_mechexpo_assets.py`; format `mei-rig` version 1). The kit reads:

| Field | Use |
|---|---|
| `parts[]` | parent first: `id`, `parent` (null for the root, the pelvis), `offset` (the joint from the parent's joint in the rest pose, m), `rotate` (a rest rotation; the weapons' `[-90, 0, 0]`), `recipe` (the part's Asset Kit recipe, origin at the joint, relative to the rig), `asset` (its `ASSET_*` name in the cart's pack), `bounds` (in the part's frame: the default extent of a box that follows the part) |
| `mounts[]` | joints without a part of their own (the Hero's empty left weapon mount): they still get a matrix, for `anim_part()` |
| `poses` | named poses: `drop` (the pelvis lowered from its rest height) and `rotate` per joint. `guard` is the pose a move starts from |

A part's matrix relative to the root is parent × T(offset) × R(rest) × R(pose); the pelvis also
takes the pose's `offset`. The runtime numbers parts one way for every mech (`enum Part` in
`anim.akr`, `PARTS` in `tools/animkit/rig.py`): `pelvis, torso, head, pauldron_r, upper_arm_r,
forearm_r, hand_r, weapon_r, pauldron_l, upper_arm_l, forearm_l, hand_l, weapon_l, thigh_r,
shin_r, foot_r, thigh_l, shin_l, foot_l`. Pauldrons hang off the torso beside the upper arms (not
their children): pose them as joints of their own.

## The move format

`MECH/MOVE.anim.json`, the file named after the move (`enum Mv` in `anim.akr`; files starting
with `_` are not moves). Every path in a move is relative to its own file.

```json
{
  "format": "mei-anim", "version": 1,
  "note": "Tip Thrust: ...",
  "base": "_body.anim.json",
  "length": 38,
  "phases": {"startup": 13, "active": 4, "recovery": 21},
  "design": {"hit": [4.0, 6.5, 10.4, 8.5], "tolerance": 0.5},
  "keys": [
    {"at": 0, "from": "guard", "ease": "ease"},
    {"at": 4, "offset": [-0.2, -0.85], "pose": {"upper_arm_r": [-15, 0, -14]}, "reach": {"foot_r": [0.54, 0.0]}},
    {"at": 13, "ease": "out", "pose": {"upper_arm_r": [91, 0, -4]},
     "boxes": {"blade": {"kind": "hit", "part": "weapon_r", "min": [-0.12, 0.5, -0.4], "max": [0.12, 7.3, 0.4], "split": 3}}},
    {"at": 17, "boxes": {"blade": null}},
    {"at": 37, "from": "guard"}
  ],
  "motion": [{"from": 4, "to": 13, "by": [1.2, 0], "ease": "ease"}],
  "plant": {"foot_r": [[0, 3], [9, 37]], "foot_l": [[0, 8], [13, 37]]},
  "marks": {"step": [9, 13], "cancel": [[13, 22]]},
  "allow": [["forearm_r", "weapon_r"]]
}
```

| Field | Meaning |
|---|---|
| `format`, `version` | `"mei-anim"`, 1 |
| `rig` | the rig (usually inherited from the base) |
| `base` | a move to start from (below) |
| `length` | frames, 1–600 |
| `loop` | the move loops: after its last key it interpolates back to its first, at `length` (idle, walks). Default false |
| `air` | an airborne move: no floor check, no push box needed, boxes may reach 4 m below the root (`atk_air`, `jump`) |
| `phases` | `startup`, `active`, `recovery` in frames; `verify` checks that they add up to `length` and that the frames with a hit box are exactly `startup` .. `startup + active − 1` (frames count from 0: startup 13 means the hit box is on frame 13, the 14th) |
| `design` | the design's numbers: `hit` `[x0, y0, x1, y1]`, what the hit boxes should span over the active frames, within `tolerance` (default 0.5 m) |
| `boxes` | the boxes from frame 0 (below) |
| `keys` | the keys, in order of their frames |
| `motion` | root motion (below) |
| `plant` | feet held in place (below) |
| `marks` | per-frame flags (below) |
| `allow` | pairs of parts (`["forearm_r", "weapon_r"]`, or `part/node` ids) that may pass into each other |
| `note` | free text: what the move is |

### Keys

A key is `{"at": frame, ...}`, frames 0 to `length − 1`, in order, the first at 0.

| Field | Meaning |
|---|---|
| `from` | start this key's pose from one of the rig's poses (`"guard"`) instead of the previous key's |
| `pose` | `{"part": [x, y, z]}`: these joints' rotations; every joint not named keeps the previous key's (the first key's: the guard's) |
| `offset` | `[forward, up]`: the pelvis moved from its rest place (fight-local m). The guard's is `[0, −drop]` |
| `ease` | how this key moves to the next: `linear`, `ease` (slow out and in, the default), `in` (slow start, fast end: into a strike), `out` (fast start, slow end: a follow-through), `hold` (stays, then snaps at the next key) |
| `reach` | `{"foot_l": [forward, up]}`: where a joint at the end of a two-joint chain goes, from its place in the rest pose; `[x, 0]` puts a foot flat on the floor x m forward of its hip line. Reach keys make a track of their own per joint: between its first and last key the joint follows it (eased by the key's `ease`), solved every frame |
| `boxes` | box changes from this frame on: `{"name": box}` adds or replaces, `{"name": null}` removes |
| `remove` | in a derived move: drop the base's key at this frame |

Interpolation is pose to pose: a key with `pose`, `offset` or `from` is a **pose key**, and each
joint's angles go from one pose key to the next by the first one's `ease`. A key with only
`boxes` or `reach` changes those and leaves the pose's curve alone, so a hit box can start on any
frame without a key in the motion.

### Plants and reaches (the legs)

Keying angles moves the feet with the body: a lunge slides them, a crouch sinks them. Two tools
solve the leg (thigh and shin turned about X, two-joint IK) every frame instead:

- **`plant`**: `{"foot_l": [[from, to], ...]}`: the foot stays where it was on the range's first
  frame, in the world (root motion undone), set on the floor and level, keeping its heading.
- **`reach`** (on keys): the foot goes to a place given relative to the root; for a step, a
  drag or a lifted foot.

On a frame both cover, the plant wins. A plant the leg cannot reach fails `verify` ("the leg does
not reach"): lower the pelvis, step sooner, or end the plant. Where a plant ends and a reach
starts, give the reach the planted place relative to the root on that frame (the root has moved:
the planted place minus the root's travel), or the foot jumps; `verify` warns of a foot that
slides along the floor.

### Boxes

Boxes are 2D rectangles in fight-local metres, baked at export from the parts they follow, so
the fight's collision reads rectangles. A box has a `kind` (`hit`, `hurt`, `push`) and either
follows a part or is a fixed rectangle:

| Field | Meaning |
|---|---|
| `part` | the part it follows. Without `min`/`max`: the part's bounds (the rig's) |
| `min`, `max` | a box in the part's own frame; each frame its 8 corners are posed and the rectangle around them, seen from the side, is the box |
| `split` | 1–6: cut the box into this many along its longest side (a sword held diagonally: thinner boxes along it) |
| `rect` | `[x0, y0, x1, y1]` from the root, instead of a part (push boxes) |
| `hit` | which hit of a multi-hit move a hit box is, 0–7 |
| `grow` | metres added on every side |

Boxes are rounded to 1/256 m. At most 16 a frame (`ANIM_MAX_BOXES`). Each mech's
`_body.anim.json` holds its hurt boxes (head, torso, pelvis, forearms, sword hand, thighs,
shins) and push box (1.6 m either side, 11.5 m tall); a move made from it keeps them and adds
its own.

### Root motion

`motion` is a list of `{"from": f0, "to": f1, "by": [forward, up], "ease": ...}`: the root
moves by `by` over frames f0 to f1 (`linear` by default; `ease`, `in`, `out`). A one-frame range
is a jump (`{"from": 42, "to": 43, "by": [12, 0]}`: a teleport). `anim_root(f)` is the motion from
frame f to f + 1, as the differences of the rounded total, so the frames add up to `by` exactly.
The fight moves the root; the animation's poses are relative to it.

### Marks

`marks` is `{"name": [frame, [from, to], ...]}` (ranges inclusive):

| Name | Bit | The fight (or the runtime) |
|---|---|---|
| `cancel` | 1 `MARK_CANCEL` | the cancel window |
| `invuln` | 2 `MARK_INVULN` | nothing hits |
| `armour` | 4 `MARK_ARMOUR` | hits land but do not interrupt |
| `flash` | 8 `MARK_FLASH` | the super's flash |
| `step` | 16 `MARK_STEP` | a foot comes down (a sound, a shake) |
| `release` | 32 `MARK_RELEASE` | the wave leaves, the throw slams |
| `riposte` | 64 `MARK_RIPOSTE` | the Parry's riposte starts |
| `parry` | 128 `MARK_PARRY` | the Parry's stance |
| `nopush` | 256 `MARK_NOPUSH` | no push box and no hurt (`verify` then needs neither) |
| `hide` | 512 `MARK_HIDE` | `anim_draw()` draws nothing (the Void Step's gone frames) |

### A move made from another (`base`)

`"base": "PATH"` starts from another move (recursively). The derived file's top-level fields
replace the base's (`rig`, `length`, `phases`, `design`, `loop`, ...; `"design": null` drops
it); `boxes` and `marks` merge by name; `keys` merge by frame: a key at a frame the base has
merges into it (`pose` and `boxes` by name, other fields replaced), a new frame is inserted,
`"remove": true` drops the base's key. Joints keep carrying from key to key, so a derived key
that sets one joint holds it until a later key sets it again.

The echo shares the Hero's skeleton, so a Double-blade move can be the Hero's with
`"rig": "../../models/doubleblade/doubleblade.rig.json"` and the differences: `"from":
"guard"` then means the Double-blade's guard. `carts/mechexpo/tests/anim/examples/
doubleblade_thrust.anim.json` is the Hero's Tip Thrust retimed for the Double-blade with both
blades.

## Commands

| Command | Result |
|---|---|
| `verify MOVE... [--json] [--tolerance M]` | the checks below; exit 1 on a failure |
| `preview MOVE -o DIR [--build-dir DIR] [--as MOVE] [--every N] [--columns N] [--distance M] [--no-boxes] [--json]` | every frame drawn by Mei and a contact sheet |
| `export [-o DIR] [--anims DIR] [--extra DIR]... [--runtime] [--no-meshes]` | every move of both mechs into `DIR/anim_data.akr` and `DIR/anims/anim_data.bin` (default the cart) |
| `info MOVE [--json]` | the move frame by frame: keys, boxes, hits, marks, root motion |

`verify` and `preview` print a summary (`--json`: the full report); `export` prints JSON. The
native tools are found as the Asset Kit finds them: `--compiler`/`--runner`, else `--build-dir`,
else `MEIC` and `RUN`, else `$B`, else `build/`.

### verify

| Check | Fails when |
|---|---|
| `format` | the file breaks the format (the error's JSON Pointer path names the field) |
| `timing` | the phases do not add up to the length, or the frames with a hit box are not the phases' active frames |
| `design` | the hit boxes' extent over the active frames is further than `design.tolerance` from `design.hit` on any side |
| `boxes` | a frame has no hurt box (except `nopush` frames), more than 16 boxes, a box thinner than 0.1 m, more than 30 m from the root, or reaching more than 2 m below it (4 m on an `air` move, or on a frame whose root motion has lifted the root). A grounded frame without a push box is a warning |
| `parts` | two parts pass into each other deeper than the rig's own poses (rest and guard) have them, plus `--tolerance` (0.12 m). Each part is fitted with a box per piece of its recipe (the recipe's top-level nodes), and the pairs are tested by the separating axis test on every frame. Parent and child, and two parts on one joint, are not tested; `allow` excuses a pair |
| `floor` | anything below the floor by more than 0.03 m on a grounded move (the floor follows the root when motion lifts it); a plant the leg cannot hold |

Warnings: a foot on the floor that slides more than 0.04 m a frame (`slides`), a step mark with no
foot down, a pose for a part the rig lacks, a looping move with root motion.

```
atk_f: PASS
  file: carts/mechexpo/anims/hero/atk_f.anim.json
  38 frames, keys at 0, 4, 9, 13, 17, 27, 37; startup 13, active 4, recovery 21
  hit boxes span x 3.61 to 10.42, y 6.77 to 8.18
  active frames 13-16; lowest point -0.000 m; 1335 piece pairs checked; up to 15 boxes a frame
```

### preview

Exports the cart's moves with this one in its place (`--as MOVE` for a file not named after a
move) into `DIR`, with a copy of `anim.akr`, builds a cart that draws frame f on tick f from the
side as the game sees it (facing +x, the camera on −Z, `--distance` 15 m; the game's is about
31 m), the root moved by its motion, the depth buffer on, with the boxes outlined (hit red, hurt
blue, push yellow), the floor and its metre ticks, the frame number, KEY on key frames, the phase,
the marks and the CPU cycles of `anim_draw()`. `DIR/contact.png` holds every key, the first and
last active frame and every Nth frame (`--every`, default about 24 frames in all);
`DIR/frames/frame_NNN.png` every frame; `DIR/gpu.csv` the frames' costs.

The boxes are drawn in the fight's plane (z = 0); the near-side arm and its weapon are about
2.5 m in front of it, so with perspective they look larger than their boxes: about 20 % at
15 m, 8 % at 31 m.

### export

Bakes every move of `enum Mv` for both mechs (`enum Mech`) in that order. A move without a file
gets the mech's `_body.anim.json` as a **stand-in** (the guard held; looping for `idle`,
`walk_f`, `walk_b`, `crouch` and `block`): the runtime has every move from the start, and
`anim_standin()` says which. `--extra DIR` adds moves from another folder in place of the
cart's (the test cart's), `--runtime` copies `anim.akr` beside the output (for a cart that
imports it from there), `--no-meshes` writes data that names no meshes (no pack import).

## The exported data

`anim_data.akr` (generated) imports the pack (`assets.akr`), embeds `anims/anim_data.bin` as
`AK_BLOB` and holds two tables: `AK_MOVES` (an `AnimMove` per mech and move: length, flags,
and where its sections start in the blob) and `AK_MESH` (each mech's part meshes in `Part`
order, `null` where it has none). The blob, per move, every section 4-byte aligned:

| Section | Per frame |
|---|---|
| frames | per part (`Part` order) a `PartXf`, 32 bytes: the rotation's 9 entries as `fixed16` (4.12) and one of padding, the translation as 3 `fixed`: the part's matrix relative to the root |
| box_first | a `u16`: the frame's first box (one more at the end: the count) |
| boxes | `Box` records, 20 bytes: kind, hit, part, padding, x0, y0, x1, y1 (`fixed`) |
| marks | a `u32` |
| root | the root motion over the frame, two `fixed` (raw) |

About 860 bytes a frame (608 of them the pose). Every pose is baked, plants and reaches
included, so what `verify` checked is what the game draws, the runtime has no solving to do, and
the runtime and the kit agree to the 4.12 rounding (`tests/test_animkit.py` compares them).

## The runtime (`carts/mechexpo/anim.akr`)

| | |
|---|---|
| `enum Mech { Hero, Doubleblade }`, `enum Mv { idle, ... super, thrown_vault }`, `enum Part { pelvis, ... foot_l }` | new moves go at the end of `Mv`, so the others keep their numbers (`thrown_vault`: the victim of the Double-blade Hero's Vault Throw) |
| `anim_len(m, mv) -> s32` | frames |
| `anim_loops(m, mv) -> bool`, `anim_standin(m, mv) -> bool` | |
| `anim_boxes(m, mv, f: s32, out: *Boxes)` | the frame's boxes (`Box { kind, hit, part, x0, y0, x1, y1 }`, fight-local, x0 < x1) |
| `anim_root(m, mv, f: s32) -> vec2` | the root's motion from f to f + 1 |
| `anim_marks(m, mv, f: s32) -> u32` | `MARK_*` bits |
| `anim_place(pos: vec2, facing: s32) -> mat4` | the root's world matrix at fight (x, y), facing +x (facing > 0) or −x: turned about Y, not mirrored |
| `anim_draw(m, mv, f: fixed, root: mat4)` | poses and draws; a fractional f interpolates between two frames (hitstop, stretched hitstun) |
| `anim_part(m, mv, f: fixed, root: mat4, part: Part) -> mat4` | a part's matrix (a weapon's +Y runs along its blade) |
| `anim_draw_boxes(m, mv, f: s32, pos: vec2, facing: s32)` | outlines the boxes (training mode); after the camera is set |
| `var anim_cpu: s32` | the cycles of the last `anim_draw()` |

Frames past the end are clamped (a loop wraps), so a held last frame needs nothing. The cart
calls `assets_load()` once and draws with `render_depth(true)`.

## Cost

Measured with the test cart (`carts/mechexpo/tests/anim/`, scenes 4 and 6), both mechs with
B's parts as they stood on 2026-10-12 (1,776 and 1,798 triangles), the depth buffer on:

| | CPU cycles | GPU cycles |
|---|---|---|
| two mechs posed and drawn, the game's camera (31 m), the Tip Thrust played through against the guard: worst frame of 76 | `anim_draw()` × 2: 353,824; the frame: 361,710 | 212,666 |
| the same pair at 17 m | the frame: 412,253 | 252,015 |
| posing alone, both mechs (38 matrices, no drawing), a whole frame | 27,480 (about 720 a part) | |
| the same between two frames (interpolated) | 36,828 | |
| building the same 38 matrices from interpolated angles, as a runtime that kept only keys would (key search and easing not counted) | 30,876 | |

Budgets a tick: CPU 1,000,000, GPU 2,000,000. Almost all of the CPU is `mesh_xf()`'s faces
(about 100 cycles a triangle in depth mode); posing is under 3 % of the frame either way. Baking
costs ROM instead: about 860 bytes a frame, so the full move list (about 1,270 frames a mech by
MOVES.md) comes to about 2.2 MB of the 64 MB cart limit, where keys alone would be about 0.7 MB
(the boxes are baked per frame in both cases). It buys exact agreement with `verify` and IK for
free at run time; the RAM used is nothing (the data is read from ROM).

## Lighting

Each part's shading is baked into its mesh with the light above and in front, no X component,
ambient 0.66, so it turns with the part. Rendered side by side with the same frames lit after
posing (each posed frame built as one Asset Kit model), the Tip Thrust, an arm raised 160° over
the shoulder and a tucked jump look nearly the same at 9 m and alike at the game's distance: the
side camera sees mostly flank faces (normals ±X), whose shading the turn does not change, and
the high ambient keeps the rest within about a third of full. Planned only if it is needed: a
second baked variant of the torso and pelvis for moves that turn the body over (a vault throw),
or relighting faces at run time from a table of normals (about 40 cycles a face, some 70,000 a
mech).

## Tests

```sh
python3 -m unittest discover -s tests -p test_animkit.py -v      # B=DIR or MEIC, RUN for the runtime tests
B=build-mine carts/mechexpo/tests/anim/check.sh                   # verify every move; scenes 5 and 4
B=build-mine carts/mechexpo/tests/anim/run.sh 1 3 build-mine/anim-test/boxes    # one scene: OUT.png, OUT.csv, OUT.log
```

`tests/test_animkit.py`: the rotation convention against the Asset Kit's, the guard on the floor,
the part and move lists against `anim.akr`, format errors and their paths, carrying and
interpolating keys, loops, root motion adding up exactly, boxes following parts, a plant holding
a foot through root motion, merging a base, each `verify` check failing when it should, the
export's layout; and with `meic` and `mei-headless`, the runtime's matrices, boxes and marks
against the kit's (the test cart's scene 5).

The test cart's scenes: 1 the game's camera with boxes, 7 the same at 17 m, 2 a grab and 3 a
jump crossing over (the two mechs overlapping, depth buffer), 4 the cost of two mechs, 5 the
runtime's numbers, 6 the cost of posing alone. `ANIM_F` picks the frame of scenes 1–3.

## Limitations and plans

- Rotations interpolate as Euler angles, per component: fine for the side-on swings of these
  moves; a joint turned far about two axes at once can take a curved path. Planned if needed:
  per-joint quaternion interpolation.
- One `ease` per key for every joint; no per-joint curves.
- Plants and reaches solve two-joint chains (legs; an arm can be planted the same way) by
  turning both joints about X; they do not turn a leg sideways.
- The `parts` check fits boxes to recipe nodes, so a node with much empty space around it (a
  rotated wing) can report a near miss; `allow` excuses a pair that does not show.
- The preview frames the mech from one side only; the other facing is the same animation turned.
