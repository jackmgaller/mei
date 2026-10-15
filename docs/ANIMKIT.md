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
| `tools/mei_anim.py` | the entry point: `verify`, `preview`, `export`, `info`, `pose`, `fmt`, `check` |
| `tools/animkit/` | `rig.py` (rigs, posing), `move.py` (the format, sampling, plants and reaches, aims), `verify.py`, `preview.py`, `export.py`, `pose.py`, `fmt.py`, `summary.py` |
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
python3 tools/mei_anim.py pose carts/mechexpo/anims/hero/atk_f.anim.json --frames 13   # joints, blade, boxes, lowest points
python3 tools/mei_anim.py export                                              # every move into the cart's anim_data
python3 tools/mei_anim.py fmt                                                 # every move file in the one style
B=build-mine python3 tools/mei_anim.py check                                  # fmt, verify all, export, both suites
```

1. **Write** the move: keys (poses and their timing), boxes, marks, motion, plants. Start from
   `_body.anim.json` (`"base"`) so the hurt and push boxes are there; aim blades with `"aim"`
   and set the pelvis on the floor with `"floor"` rather than fitting angles by hand.
2. **`pose`** to read where a frame puts the blade, the boxes and the lowest points, and
   **`verify`** until it passes. It names the frames, the parts and by how much.
3. **`preview`**, and look at `contact.png` (every key, the phases' edges, and about 24
   frames) and `frames/frame_NNN.png` (every frame).
4. **`check`** (it checks the files' style, verifies every move, exports and runs the kit's
   two suites), then build the cart. A move is done when `verify` passes and its contact sheet
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
| `allow` | pairs of parts every move of the rig may pass into each other (`verify`'s `parts` check); a move's `allow` adds to them. Both mechs': each forearm with its weapon (a bent wrist puts the grip in the cuff) and the torso with each thigh (a raised knee under the skirt) |

A part's matrix relative to the root is parent × T(offset) × R(rest) × R(pose); the pelvis also
takes the pose's `offset`. The runtime numbers parts one way for every mech (`enum Part` in
`anim.akr`, `PARTS` in `tools/animkit/rig.py`): `pelvis, torso, head, pauldron_r, upper_arm_r,
forearm_r, hand_r, weapon_r, pauldron_l, upper_arm_l, forearm_l, hand_l, weapon_l, thigh_r,
shin_r, foot_r, thigh_l, shin_l, foot_l` (`SKELETON`, every rig's), then `wing_l, wing_r, halo`:
joints only Seraph's rig has (the wings the torso's children, the halo the head's), appended so
the others keep their numbers. A mech's exported frames hold its parts up to the last one its rig
has (19 for every mech but Seraph, 22 for Seraph: [The exported data](#the-exported-data)), so a
joint appended for one mech leaves the others' data as it was. Pauldrons hang off the torso
beside the upper arms (not their children): pose them as joints of their own.

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
    {"at": 4, "offset": [-0.2, -0.85], "pose": {"upper_arm_r": [-15, 0, -14]}, "reach": {"foot_r": "guard"}},
    {"at": 13, "ease": "out", "pose": {"upper_arm_r": [91, 0, -4]}, "aim": {"weapon_r": [3, -10]},
     "boxes": {"blade": {"kind": "hit", "part": "weapon_r", "min": [-0.12, 0.5, -0.4], "max": [0.12, 7.3, 0.4],
                         "split": 3}}},
    {"at": 17, "boxes": {"blade": null}},
    {"at": 37, "from": "guard"}
  ],
  "motion": [{"from": 4, "to": 13, "by": [1.2, 0], "ease": "ease"}],
  "plant": {"foot_r": [[0, 3], [9, 37]], "foot_l": [[0, 8], [13, 37]]},
  "marks": {"step": [9, 13], "cancel": [[13, 22]]},
  "allow": [["head", "upper_arm_r"]]
}
```

| Field | Meaning |
|---|---|
| `format`, `version` | `"mei-anim"`, 1 |
| `rig` | the rig (usually inherited from the base) |
| `base` | a move to start from (below) |
| `retime` | with `base`: `[[base frame, new frame], ...]`, the base's keys, motion, plants and marks moved to new frames (below) |
| `length` | frames, 1–600 (with `retime` and no `length`: the base's last frame's new place + 1) |
| `loop` | the move loops: after its last key it interpolates back to its first, at `length` (idle, walks). Default false |
| `air` | an airborne move: no floor check, no push box needed, boxes may reach 4 m below the root (`atk_air`, `jump`) |
| `travel` | metres a frame the fight moves the root forward (negative: back) while the move plays, up to 2: the walks' speeds (`moves.akr`'s `walk_f`, `walk_b`). Not exported (the fight moves the root itself); plants hold in the world through it and `verify` counts it when it looks for sliding feet |
| `still` | joints held at rotation 0 on every frame, whatever the keys and the rig's poses say: `["weapon_r", "weapon_l"]`. A move made from another mech's (`base`) leaves out the keys of joints its own rig must not turn: Seraph's fists on Shadow's claw keys. An `aim` at a still part still turns its wrist |
| `phases` | `startup`, `active`, `recovery` in frames; `verify` checks that they add up to `length` and that the frames with a hit box are exactly `startup` .. `startup + active − 1` (frames count from 0: startup 13 means the hit box is on frame 13, the 14th) |
| `design` | the design's numbers: `hit` `[x0, y0, x1, y1]`, what the hit boxes should span over the active frames, within `tolerance` (default 0.5 m) |
| `boxes` | the boxes from frame 0 (below) |
| `keys` | the keys, in order of their frames |
| `motion` | root motion (below) |
| `plant` | feet held in place (below) |
| `marks` | per-frame flags (below) |
| `allow` | pairs of parts (`["forearm_r", "weapon_r"]`, or `part/node` ids) that may pass into each other, added to the rig's `allow` and the base's |
| `floor_allow` | `{"wing_l": 2.15}`: parts that may go into the floor, each up to its depth in metres (at most 5): `verify`'s `floor` check warns instead of failing. For a move made for another body and not yet re-keyed (phase 1's Seraph: its folded wings on Shadow's knockdown, and phase 1's Gamma: its jerrycan rack on Beam's); no move of the cart uses it now |
| `note` | free text: what the move is |

### Keys

A key is `{"at": frame, ...}`, frames 0 to `length − 1`, in order, the first at 0.

| Field | Meaning |
|---|---|
| `from` | start this key's pose from one of the rig's poses (`"guard"`) instead of the previous key's |
| `pose` | `{"part": [x, y, z]}`: these joints' rotations; every joint not named keeps the previous key's (the first key's: the guard's) |
| `offset` | `[forward, up]`: the pelvis moved from its rest place (fight-local m). The guard's is `[0, −drop]` |
| `relative` | `true`: this key's `pose` angles and `offset` are added to the rig's guard rather than replacing the carried values: `{"torso": [-10, 4, 0]}` is the guard's torso leaned 10° more. A move written this way carries onto another rig's guard (below) |
| `aim` | `{"weapon_r": [elevation, yaw]}`: the wrist (the part's parent) is solved so the part's +Y (the blade) points this way (below) |
| `floor` | `true`: the offset's `up` is set so the lowest part touches the floor on this frame (feet, knees, a hand on the floor); keys that carry this offset carry the new one. `forward` is kept |
| `ease` | how this key moves to the next: `linear`, `ease` (slow out and in, the default), `in` (slow start, fast end: into a strike), `out` (fast start, slow end: a follow-through), `hold` (stays, then snaps at the next key) |
| `reach` | `{"foot_l": [forward, up]}`: where a joint at the end of a two-joint chain goes, from its place in the rest pose; `[x, 0]` puts a foot flat on the floor x m forward of its hip line. `"guard"`: where the rig's guard puts it, to the centimetre (a foot's on the floor: the Hero's left foot `[-2.51, 0]`, the Double-blade's `[-2.94, 0]`). `null` ends the track (below). Reach keys make a track of their own per joint: between its first and last key the joint follows it, solved every frame |
| `reach_ease` | how the reach tracks move from this key to their next: as `ease`; default the key's `ease`. A planted foot sliding at the walk's speed wants `linear` while the body eases |
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

The root's travel is the move's root motion plus its `travel` (the speed the fight moves the
root at, which is not exported). A walk keys the swinging foot with reaches and plants the
standing one: the plant holds it in the world while the fight carries the root on, so the foot
slides back against the root by exactly the walk's speed, and `verify` sees it standing still.
`carts/mechexpo/anims/hero/walk_f.anim.json` is the example (`"travel": 0.075`, the right foot
planted on 0–32, the left on 0–8 and 24–47).

A reach track runs from its first key to its last. `null` ends it early: `{"at": 20, "reach":
{"foot_l": null}}` holds the value of the key before it until frame 19, and from frame 20 the
leg is posed by its keyed angles again; a later reach key starts a new track. A key's `ease`
eases the reach tracks too unless it gives `reach_ease`.

A reach or a plant turns the thigh and the shin about X; their Y and Z stay as keyed. `verify`
warns (`legs`) when a pose key names a thigh or a shin whose X the track or plant solves on
every frame the key reaches (from the pose key before it to the one after): that keyed bend
never shows. End the reach before it (`null`) if the keyed knee is the one wanted.

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

### Aiming a blade

`"aim": {"weapon_r": [elevation, yaw]}` on a key solves the wrist so the blade points that way
in the root's frame, whatever the arm, the torso's twist and the pelvis do:

- **elevation**: degrees above level, −90 (straight down) to 90 (straight up);
- **yaw**: degrees round from straight ahead (fight-local +x), +90 to the mech's left (away
  from the game's camera), −90 to its right (toward it), ±180 behind. A right-to-left cut
  sweeps from negative yaw to positive.

The wrist (`hand_r` for `weapon_r`) turns from the angles the key would otherwise give it (its
own `pose` entry, or the carried one) by the smallest turn that points the blade, so the
blade's roll follows the key; the angles are rounded to 0.01° and carry to the next keys like
keyed ones (the aim does not: a later key that moves the arm moves the blade). `pose` and
`info --joints` print what the wrist was solved to, and every frame's blade direction in the
same terms, so a design box can be met by reading the numbers rather than by trial. A wrist
turned more than 100° from straight is a warning (`aim`): turn the forearm toward the aim.

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
| `charge` | 1024 `MARK_CHARGE` | the move holds this frame while its button is held (Beam's Volt Orb, `sp_n`) |
| `ward` | 2048 `MARK_WARD` | Seraph's Wing Ward (`sp_d`): a shot of the other side that touches a hurt box on this frame, coming at the front, is sent back |
| `shield` | 4096 `MARK_SHIELD` | Gamma's Lead Shielding (`sp_d`), the brace: the first hit that lands on this frame, on the ground, is absorbed (Tank's armour for one hit), then the move jumps to its `riposte` frame |

### A move made from another (`base`)

`"base": "PATH"` starts from another move (recursively). The derived file's top-level fields
replace the base's (`rig`, `length`, `phases`, `design`, `loop`, ...; `"design": null` drops
it); `boxes` and `marks` merge by name; `allow` lists add to the base's; `keys` merge by
frame: a key at a frame the base has merges into it (`pose` and `boxes` by name, other fields
replaced), a new frame is inserted, `"remove": true` drops the base's key. Joints keep
carrying from key to key, so a derived key that sets one joint holds it until a later key sets
it again.

**`retime`** moves the base to new frames before the derived file's own fields and keys are
merged: `"retime": [[0, 0], [3, 2], [6, 5], [9, 7], ..., [38, 34]]` maps each base frame
between two pairs linearly (rounded to the nearest frame, halves up), and before the first or
after the last pair one for one. It moves the base's keys, its motion's `from` and `to`, its
plant ranges and its marks; the length becomes the base's last frame's new place + 1 unless the
file gives one. `phases` and `design` are not moved: give them. Base keys that land on one
frame merge, the later over the earlier; the derived file's keys then go by the new frames (a
`remove` drops a retimed key). The Double-blade's Jump is the Hero's with nothing but a retime
and its rig.

Seraph's moves are its own (`anims/seraph/`, on its boxer's guard), but for the three throws'
victims: `thrown`, `thrown_vault` and `thrown_slam` are Shadow's (`"base":
"../shadow/MOVE.anim.json"`, so the shoulders follow the throwers' hands as Shadow's do) with
Seraph's rig and `"still": ["weapon_r", "weapon_l"]` (Shadow's claw keys would twist the fists),
their keys from the slam on replaced (`"remove"`) so they end face down in `hit_air`'s last frame.
Every Seraph move keeps the weapon joints still the same way.

Gamma's moves are its own too (`anims/gamma/`), every one based on Gamma's `_body.anim.json`
(Beam's boxes on Gamma's rig) and on no other move: where MOVES.md says a move is Beam's (the
reactions, the crouch, the jump, the grabs), Beam's keys were copied in with their bases merged,
then re-keyed where Gamma's kit met itself or the floor (the stowed shield and the pauldron, the
projector and the shield, the jerrycan rack lying on its back). The shield (`weapon_l`) is held at
0 by the body's `"still"`; the moves that swing it (`block`, `hit_high`, `hit_low`, `sp_d`, `win`)
give `"still": []` and key it about Y.

The echo shares the Hero's skeleton, so a Double-blade move can be the Hero's with
`"rig": "../../models/doubleblade/doubleblade.rig.json"` and the differences: `"from":
"guard"` then means the Double-blade's guard, and so do a reach's `"guard"` and a
`"relative"` key's angles and offset: a Hero key written relative to the guard lands on the
Double-blade's lower guard by itself, where an absolute one keeps the Hero's angles.
`carts/mechexpo/anims/doubleblade/atk_d.anim.json` is the Hero's Low Sweep retimed, with the
Double-blade's offsets and boxes; `carts/mechexpo/tests/anim/examples/doubleblade_thrust.anim.json`
is the Hero's Tip Thrust re-keyed for the Double-blade with both blades, and
`examples/aimed_lunge.anim.json` a Hero move written with `relative`, `aim`, `floor`, a
`"guard"` reach, `reach_ease` and a reach ended by `null`.

## Commands

| Command | Result |
|---|---|
| `verify MOVE... [--json] [--tolerance M]` | the checks below; exit 1 on a failure |
| `preview MOVE -o DIR [--build-dir DIR] [--as MOVE] [--every N] [--columns N] [--distance M] [--no-boxes] [--json]` | every frame drawn by Mei and a contact sheet |
| `export [-o DIR] [--anims DIR] [--extra DIR]... [--runtime] [--no-meshes]` | every move of every mech into `DIR/anim_data.akr` and `DIR/anims/anim_data.bin` (default the cart) |
| `info MOVE [--json] [--joints [--frames F]]` | the move frame by frame: keys, boxes, hits, marks, root motion; `--joints`: as `pose` |
| `pose MOVE [--frames F] [--no-joints] [--json]` | where each frame puts things (below); `F` is `13`, `10-16,20` or `keys` (default every frame) |
| `fmt [MOVE...] [--check]` | rewrite move files in the one compact style (default every file of the cart's `anims/`); `--check` lists the files that would change and exits 1 if any |
| `check [--no-tests] [--fight] [--build-dir DIR]` | `fmt --check` on the cart's moves, `verify` on every move (the cart's, the test cart's, the examples), `export` into the cart, then `tests/test_animkit.py` and `carts/mechexpo/tests/anim/check.sh`; `--fight` adds the cart's fight scenarios (`carts/mechexpo/tests/check.sh`). Stops at the first failure, exit 1 |

`verify`, `preview`, `pose` and `info` print a summary (`--json`: the full report); `export`
prints JSON. The native tools are found as the Asset Kit finds them: `--compiler`/`--runner`,
else `--build-dir`, else `MEIC` and `RUN`, else `$B`, else `build/`.

### verify

| Check | Fails when |
|---|---|
| `format` | the file breaks the format (the error's JSON Pointer path names the field) |
| `timing` | the phases do not add up to the length, or the frames with a hit box are not the phases' active frames |
| `design` | the hit boxes' extent over the active frames is further than `design.tolerance` from `design.hit` on any side |
| `boxes` | a frame has no hurt box (except `nopush` frames), more than 16 boxes, a box thinner than 0.1 m, more than 30 m from the root, or reaching more than 2 m below it (4 m on an `air` move, or on a frame whose root motion has lifted the root). A grounded frame without a push box is a warning |
| `parts` | two parts pass into each other deeper than the rig's own poses (rest and guard) have them, plus `--tolerance` (0.12 m). Each part is fitted with a box per piece of its recipe (the recipe's top-level nodes), and the pairs are tested by the separating axis test on every frame. Parent and child, and two parts on one joint, are not tested; `allow` excuses a pair |
| `floor` | anything below the floor by more than 0.03 m on a grounded move (the floor follows the root when motion lifts it), with the offset `up` the pelvis needs on the worst frame (or key `"floor": true` there), unless the move's `floor_allow` allows the part that deep (a warning then); a plant the leg cannot hold |

Warnings: a foot on the floor that slides more than 0.04 m a frame in the world (the root's
motion and `travel` counted: `slides`), a step mark with no foot down, a pose for a part the rig
lacks, a looping move with root motion, a keyed knee or hip a reach or plant hides (`legs`), a
wrist an `aim` bends more than 100° (`aim`), a `"floor"` key whose lowest part is held by a
plant or a reach and so cannot be brought down (`floor`).

```
atk_f: PASS
  file: carts/mechexpo/anims/hero/atk_f.anim.json
  38 frames, keys at 0, 4, 9, 13, 17, 27, 37; startup 13, active 4, recovery 21
  hit boxes span x 4.04 to 10.84, y 6.56 to 8.23
  active frames 13-16; lowest point -0.000 m; 1307 piece pairs checked; up to 15 boxes a frame
  warn slides: foot_l slides along the floor on frames 7 (up to 0.05 m a frame): "plant" it, or lift it.
```

### pose

Where each frame puts things, in fight-local metres (forward, up, from the root): the offset and
the root's travel; every joint; each weapon's base (its grip) and tip, how far to the side each
is (the model's +X, the mech's left: the near-side sword is at about −3 m) and the blade's
`[elevation, yaw]` as `aim` takes them; the hit and hurt boxes; the lowest point of each part
(the floor is 0); the top of the hurt boxes. The aims and `floor` keys the move solved are
listed first. `--json` gives the same with every joint as `[forward, up, side]` and each
frame's angles.

```
$ python3 tools/mei_anim.py pose carts/mechexpo/anims/hero/atk_f.anim.json --frames 13 --no-joints
atk_f (hero): 38 frames; points are forward,up from the root (m)
frame 13 KEY: offset -0.75,-1.30; root moved +1.20,+0.00
  weapon_r base 3.59,7.43 side -3.18, tip 10.65,7.82 side -4.51; aim [3.1, -10.6]
  hit  blade.0     x 4.04 to 6.34, y 7.05 to 7.99
  ...
  lowest   foot_r -0.00  foot_l -0.00  shin_l +0.19  shin_r +0.43  thigh_l +2.18  thigh_r +2.90
           pelvis +3.69  hand_l +4.38  ...
  hurt top 10.96
```

### fmt and check

`fmt` writes every move file one way, so files from different animators diff cleanly: the
top-level fields one a line in the order of the format's table (`format`, `version`, `note`,
`base`, `rig`, `retime`, `length`, ... `allow`); keys, motions and the top-level boxes one a
line, each key's fields in the order `at`, `remove`, `from`, `relative`, `ease`,
`reach_ease`, `offset`, `floor`, `pose`, `aim`, `reach`, `boxes`, `note`; anything that does
not fit in 100 columns filled into lines with the continuation aligned under its first entry.
It checks that the values come back unchanged. `check` is the one command to run before
committing moves (`make test` runs the Python suite, `make test-carts` the test cart's checks).

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

Bakes every move of `enum Mv` for every mech (`enum Mech`) in that order. A move without a file
gets the mech's `_body.anim.json` as a **stand-in** (the guard held; looping for `idle`,
`walk_f`, `walk_b`, `crouch` and `block`): the runtime has every move from the start, and
`anim_standin()` says which. `--extra DIR` adds moves from another folder in place of the
cart's (the test cart's), `--runtime` copies `anim.akr` beside the output (for a cart that
imports it from there), `--no-meshes` writes data that names no meshes (no pack import).

## The exported data

`anim_data.akr` (generated) imports the pack (`assets.akr`), embeds `anims/anim_data.bin` as
`AK_BLOB` and holds three tables: `AK_MOVES` (an `AnimMove` per mech and move: length, flags,
and where its sections start in the blob), `AK_MESH` (each mech's part meshes in `Part`
order, `null` where it has none) and `AK_NPART` (how many parts each mech's frames hold: its
parts in `Part` order up to the last one its rig has; 19, and Seraph's 22). The blob, per move,
every section 4-byte aligned:

| Section | Per frame |
|---|---|
| frames | per part (`Part` order, the mech's `AK_NPART`) a `PartXf`, 32 bytes: the rotation's 9 entries as `fixed16` (4.12) and one of padding, the translation as 3 `fixed`: the part's matrix relative to the root |
| box_first | a `u16`: the frame's first box (one more at the end: the count) |
| boxes | `Box` records, 20 bytes: kind, hit, part, padding, x0, y0, x1, y1 (`fixed`) |
| marks | a `u32` |
| root | the root motion over the frame, two `fixed` (raw) |

About 860 bytes a frame (608 of them the pose; Seraph's 704). The mechs follow each other in
`Mech` order, so a mech appended to `Mech` adds its moves at the end of the blob and every other
mech's bytes stay where they were. Every pose is baked, plants and reaches
included, so what `verify` checked is what the game draws, the runtime has no solving to do, and
the runtime and the kit agree to the 4.12 rounding (`tests/test_animkit.py` compares them).

## The runtime (`carts/mechexpo/anim.akr`)

| | |
|---|---|
| `enum Mech { Hero, Doubleblade, ..., Shadow, Seraph }`, `enum Mv { idle, ... super, thrown_vault, ... }`, `enum Part { pelvis, ... foot_l, wing_l, wing_r, halo }` | new mechs, moves and parts go at the end, so the others keep their numbers (`thrown_vault`: the victim of the Double-blade Hero's Vault Throw) |
| `anim_len(m, mv) -> s32` | frames |
| `anim_loops(m, mv) -> bool`, `anim_standin(m, mv) -> bool` | |
| `anim_boxes(m, mv, f: s32, out: *Boxes)` | the frame's boxes (`Box { kind, hit, part, x0, y0, x1, y1 }`, fight-local, x0 < x1) |
| `anim_root(m, mv, f: s32) -> vec2` | the root's motion from f to f + 1 |
| `anim_marks(m, mv, f: s32) -> u32` | `MARK_*` bits |
| `anim_place(pos: vec2, facing: s32) -> mat4` | the root's world matrix at fight (x, y), facing +x (facing > 0) or −x: turned about Y, not mirrored |
| `anim_draw(m, mv, f: fixed, root: mat4)` | poses and draws; a fractional f interpolates between two frames (hitstop, stretched hitstun) |
| `anim_part(m, mv, f: fixed, root: mat4, part: Part) -> mat4` | a part's matrix (a weapon's +Y runs along its blade); for a part past the mech's `AK_NPART` (a wing or the halo on a mech without them) the joint it would hang from: the torso, the head |
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
a foot through root motion, merging a base; `retime` (keys, motion, plants, marks, the frame
map), `relative` keys on the other rig's guard, the `"guard"` foot of each rig, `aim` within
0.05° under a twisted torso, `travel` holding plants in the world and the slide warning, a reach
ended by `null`, `reach_ease`, the `legs` warning, `floor` keys and the offset `verify` names,
the rig's and the base's `allow`, `still` holding joints at 0 through keys and bases, `floor_allow`
turning a sinking part's failure into a warning only to its depth, the `ward` mark (its bit, Seraph's
`sp_d` frames, the exported marks), the `shield` mark (its bit, Gamma's `sp_d` frames and its
`riposte`, the exported marks), each rig's part count (19,
Seraph's 22) and the export's `AK_NPART`; `pose`'s blade and boxes, `fmt` keeping every file's values
(and the cart's files in the style); each `verify` check failing when it should, the export's
layout; and with `meic` and `mei-headless`, the runtime's matrices, boxes and marks against the
kit's (the test cart's scene 5).

The test cart's scenes: 1 the game's camera with boxes, 7 the same at 17 m, 2 a grab and 3 a
jump crossing over (the two mechs overlapping, depth buffer), 4 the cost of two mechs, 5 the
runtime's numbers, 6 the cost of posing alone. `ANIM_F` picks the frame of scenes 1–3.

## Limitations and plans

- Rotations interpolate as Euler angles, per component: fine for the side-on swings of these
  moves; a joint turned far about two axes at once can take a curved path. Planned if needed:
  per-joint quaternion interpolation.
- One `ease` per key for every joint (and one `reach_ease` for its reach tracks); no per-joint
  curves.
- Plants and reaches solve two-joint chains (legs; an arm can be planted the same way) by
  turning both joints about X; they do not turn a leg sideways.
- `aim` turns the wrist only: it does not move the arm, so an aim far from where the forearm
  points bends the wrist far (a warning past 100°). It points the blade's axis; the edge's roll
  follows the key's wrist.
- A reach's `"guard"` is the guard's place forward to the centimetre, and a foot's flat on the
  floor (the values the moves had keyed by hand), not the guard's exact place: the guard's feet
  are tilted, their joints 1.5 cm (Hero) and 3.5 cm (Double-blade) above the level foot's.
- The `parts` check fits boxes to recipe nodes, so a node with much empty space around it (a
  rotated wing) can report a near miss; `allow` excuses a pair that does not show.
- The preview frames the mech from one side only; the other facing is the same animation turned.
