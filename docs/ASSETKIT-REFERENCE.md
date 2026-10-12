# Asset Kit reference

The full reference of the Asset Kit: what each command prints and writes, the recipe's fields,
textures, the Asset Checker and its reports, the outputs and the tests. Start with the guide,
[ASSETKIT.md](ASSETKIT.md), for the loop, the authoring rules, the conventions and the command
list. `python3 tools/mei_assets.py schema` is the authoritative machine-readable contract. The
owner's decisions about the kit are in [DECISIONS.md](DECISIONS.md#the-asset-kit).

## Command details

The command list is in the guide ([Commands](ASSETKIT.md#commands)); `--help` prints each
command's options.

### Output: the summary and the full report

`preview` and `verify` print a summary of one screen, in plain text: the verdict, each failure,
the counts (triangles and vertices against the budget, textures and VRAM bytes, always, also
when 0, and palette entries for palette-backed materials), the bounds and how far the asset
reaches below y = 0 (and which parts), the allowed findings as counts per kind and part pair,
the compile warnings counted by code, the look, the images and where the full report is.
`--json` prints the full report instead, as before. `preview` always writes the full report to
`report.json` in its output directory; `verify -o DIR` writes `verification.json` there.
`build` prints JSON as before. `pine` from Fall Line (`carts/fallline/models/pine/`):

```
pine: preview written to build-mine/assets/pine
verdict: PASS (depth mode); 104 findings allowed in depth mode (surface_intersection, t_junction)
views judged: 16; faces seen 82 of 82
allowed surface_intersection: 104 (tier_1/trunk 30, snow_1/trunk 18, tier_2/trunk 12, snow_1/tier_2 11, and 3 more pairs)
close faces: 2 part pairs (they z-fight from a distance)
  close_faces: 7 between snow_3 and tier_3: snow_3's faces 24.9 mm in front of tier_3's, facing the same way (…)
  close_faces: 7 between snow_4 and tier_4: snow_4's faces 19.5 mm in front of tier_4's, facing the same way (…)
triangles 82 of 100, vertices 81 of 128, textures 0, VRAM 0 bytes, palette entries 1
bounds: x -1.98 .. 2.20  y -1.00 .. 6.60  z -2.14 .. 2.14  (size 4.18 x 7.60 x 4.29)
below y = 0: down to -1.00 (trunk)
warning open_surface: 8 (snow_1, snow_2, snow_3, snow_4, tier_3, tier_4, ...)
look: background #70d0f8 to #fffcf4, ground #eef5fc (from carts/fallline/models/asset-preview.json)
images: build-mine/assets/pine/contact.png (6 fitted views)
        build-mine/assets/pine/cameras.png (the asset's share of a frame's GPU: eye_level 0.4 %, closeup_1 4.2 %, closeup_2 3.3 %)
full report: build-mine/assets/pine/report.json (or run with --json)
```

A failure names the parts and where they are, in the asset's coordinates (world units as placed
at the origin with yaw 0), besides the face indices:

```
test: FAIL (ordering-table mode): 4 problems, see failures
  FAIL geometry: surface_intersection: 60 between bar and body (faces 20/49, 20/64, 20/68, 22/53, ...) at (-0.76, -0.89, -0.25)
  FAIL geometry: coplanar_overlap: 8 between body and cap (faces 32/100, 34/101, 35/100, 35/101, ...) at (0.25, 1.00, -0.42)
  FAIL views: 864 wrong-depth pixels in 4 views, most where body is drawn over bar (faces 45/82 at (-0.99, -0.18, 0.62)) (see views[].issues)
  FAIL views: ordering cycles in 4 views, the first through body, bar at (1.03, -0.21, -0.53) (see views[].ordering_graph)
```

A geometry line's position is the middle of its first face pair's centres; a views line's, of
the face pair with the most wrong pixels in the part pair with the most. The same lines are the
report's `failures` (and the flush-contact error's summary). Every face a report names (in
`geometry.findings`, `views[].issues`, `ordering_graph`) has `at`, its centre. Paths are shown
relative to the current directory. At most 8 failures, 4 part pairs per kind of allowed finding
and 3 close-face lines are shown, each list with a count of the rest. A failed verification under
`preview` prints the same summary, the failing renders and `verification.failed.json`; any other
error is one line, `error at PATH (node): message`.

`--strict` fails on topology warnings, useful for closed props. Omit it for intentionally open
surfaces. `--depth` and `--perspective` on build and
preview say the asset is drawn with the depth buffer and perspective texturing, as in a world whose
`runtime` says so: the preview cart draws so (`preview.akr` and the six views), and the Asset
Checker runs in [depth mode](#depth-mode) where the recipe's policy does not set `depth` or
`perspective` itself. Without them an untextured asset previews as before, whatever its world.
Use a dedicated generated-output directory: builds replace their own filenames there.
Validation, serialization and optional rendering finish in a staging directory before outputs
are replaced; failed geometry checks or renders leave the previous build's files intact.
Do not use the recipe's own directory as the output directory if its name would collide with
the generated recipe copy. Obsolete files from earlier differently named builds are not removed.

**Flush contacts.** `inspect` adds `flush_contacts`: the duplicate faces and coplanar overlaps of
the mesh (the geometry audit without its crossing test), which the Asset Checker fails in either
mode, as `count`, `by_code`, one `summary` line per part pair, a `hint` and `fixes`, one per part
pair in the summary's order ([Authoring rules](ASSETKIT.md#authoring-rules-depth-mode)). A fix names the
smaller part (by surface area), the way to move it and about how far: two parts back to back (one
standing on the other) get `sink top about 0.02 along -Y into base, or open top's face toward
-Y (an unrotated box: "open": ["bottom"])`, or, when the policy has no depth buffer (where sunk
parts cross, which fails), only the opening; faces level with each other and facing the same way
get `move … about 0.03 along … so its face stands proud`. It needs NumPy; without it `checked` is
false and says why. The robot example (1,520 triangles) takes about 0.5 s and finds its 8
coplanar overlaps; the cottage (316) 0.06 s and its 36.

`build` and `preview` run the same check first and put it in their result and `report.json`
(`flush_contacts`). When the Asset Checker is to run (a required policy, or `--verify`) and its
policy does not say `"geometry": "warn"`, flush contacts **stop the command before anything is
rendered or written**: the error, at `/verification`, lists the part pairs and the fixes, and
the output carries `flush_contacts`:

```json
{"ok": false, "errors": [{"path": "/verification", "message": "Stopped before rendering: 4 flush
  contacts, which the Asset Checker fails in either mode: coplanar_overlap: 4 between base and top
  (faces 8/16, 8/17, 9/16, 9/17) at (-0.08, 0.50, -0.25). Fix: sink top about 0.02 along -Y into
  base, or open top's face toward -Y (an unrotated box: \"open\": [\"bottom\"]). Nothing was
  written; run inspect to see them all."}], "flush_contacts": {…}}
```

Levels of detail are checked too (lines `lod K …`). The check is in the command line; the
`build()` function runs it when called with `flush_check=True`.

**Close faces.** `inspect` adds `close_faces`, and `verify` lists the same as `warnings` (after
`allowed`; in full in `geometry.close_faces`): pairs of faces that face the same way (normals
within 5°), overlap in projection by more than 1 cm² and lie less than **3 cm** apart, but not in
one plane (that is a coplanar overlap). They are never a failure: the depth test draws them right
from close by, and no view of the sweep fails them. But a key step is 1/4,096 of the depth, and a
face seen at a grazing angle needs about ten ([RENDERING.md](RENDERING.md#precision): 2.7 cm at 8
units for a floor at 11°), so a gap *g* ties from about *g* / 0.0034 units at such an angle and
*g* / 0.00029 face on: 1 cm from 2.9 units and 34 units, 3 cm from 8.8 and 103. Each part pair's
line says so:

```
close_faces: 4 between panel and board: panel's faces 10.0 mm in front of board's, facing the same way (faces 12/0, 14/0, 12/2, 14/2): they z-fight from about 2.9 units at a grazing view, 34 face on
```

`pairs` gives per pair `front`, `behind`, `count`, `gap_min`, `gap_max`, `fights_from` and up to 8
face pairs. Stand the front part 3 cm proud, or remove the covered face. Faces inside a solid
(a panel's back sunk into its board) are listed too: they show only if the solid's face does
not cover them. Faces back to back (a plate under a box) are not listed, as culling hides one of
each pair; double-sided materials are not treated differently. The cottage lists the crossing
bars of its windows (1 mm apart) and their panes (1.7–2.3 cm); the vessel its foot (just under
3 cm). The check takes 0.17 s for the robot (1,520 triangles), 0.02 s for the cottage.

**More in `inspect`.**

- `face_maps` and `decals`: each node's per-side materials and each decal, with their triangles
  ([Face materials and decals](#face-materials-and-decals)); `build`'s `report.json` has them too.
- `texture_windows`: the repeating textures' windows in use, `used` of `max` (7), each with its
  texture (`pattern 'brick'`, `image art/x.png`, `sheet 'signs' cell …`), size, bits and the
  `materials` that use it (materials with the same texture share one window). With more than 7,
  every command fails with an error that lists the windows the same way.
- A recipe **over its budgets** is reported in full: the breach is a warning (`over_budget`, with
  `key`, `count` and `budget`) at the start of `warnings`, and `parts` still gives every part's
  counts, so you can see what to cut. `build`, `preview` and `verify` still fail on it.
- `warnings` gains `mirror_coincides` (a mirror whose copy lies exactly over the original, as
  for a part centred on the mirror plane: every face doubled), `mirror_overlaps` (the part spans
  the mirror plane, so the copy overlaps it), `mirror_touches` (faces on the mirror plane, which
  the copy's lie back to back on: open that side), each with the part and the modifier's `path`,
  and `below_ground` (parts reaching below y = 0, the ground an asset stands on, lowest first).
  These are `inspect`'s: `build`'s report and `--strict` are as before.

### Quick facts: info and floors

Two read-only commands for placing an asset (`tools/assetkit/info.py`). They compile the recipe
and nothing else: no native tools, nothing written, a fraction of a second. They print plain
text; `--json` gives the same as JSON (errors too: plain `error at PATH: message` without it).

**`info FILE`**: the triangles, vertices and mesh bytes; the drawn bounds; the collision (which
recipe, its triangles as floors, walls, faces too steep to stand on and ceilings, as the World
Kit files them, its bounds and highest floor); each level of detail's triangles and switch
distance, `cull` and `band` (a world's `lod` may change the distances); the palettes
(palette-backed, and the textures' 4-bit and 8-bit); and per texture its size, bits, source,
`stored` bytes (`vram_bytes`, the gutter included) and `allocated` bytes (on the packer's 8-texel
grid, what a world region's `textures.budget` counts), with the textures that are one tile
(`same tile as`), each image or sheet several textures read, and the texture windows. `--at
X,Y,Z --yaw DEG` adds the bounds where a world placement there puts them (yaw as `mesh_at()`:
+Z toward +X). `--collision auto` (the default) takes `NAME_col.asset.json` beside the recipe
when there is one, else the recipe itself; `self`, `none` or a recipe path say otherwise.
`--floor-max DEG` is the steepest floor (default 45, the World Kit's; the game's probe may say
less: the garden's is 40).

```
$ python3 tools/mei_assets.py info carts/garden/shrinetown/assets/station_platform/station_platform.asset.json --at 160,9,8 --yaw 90
station_platform: 674 triangles, 486 vertices, 32,056 mesh bytes
bounds (drawn): [-20.0, 0.0, -2.9] .. [20.0, 4.72, 2.9] (size [40.0, 4.72, 5.8])
  placed at [160.0, 9.0, 8.0] yaw 90: [157.1, 9.0, -12.0] .. [162.9, 13.72, 28.0]
collision: station_platform_col.asset.json (beside the recipe): 208 triangles (38 floors, 164 walls, 0 too steep, 6 ceilings at floor_max 45 deg); ...
levels of detail: L0 674 tris from 0, L1 126 tris from 30, L2 40 tris from 70; band 2
textures: 16 tiles, 5,487 bytes stored, 7,648 allocated on the 8-texel grid (what a world region's budget counts)
  name_board             96x36      4   1,813   2,080  sheet 'station' cell name_board
  ...
  image art/station_sheet.png: 10 textures, 7,200 bytes (bin_burn, bin_cans, clock, ...)
texture windows: 5 of 7: ...
```

**`floors FILE`**: the collision's highest floor under each point of a grid (`--step`, default 0.25;
over the collision's bounds or `--area X0,Z0,X1,Z1`), north (+Z) up, as heights and as a map of
marks: `.` a floor, `#` a wall passing within half a step, `^` a face too steep to stand on above
the floor there, blank nothing. `--below Y` takes the highest floor at or below Y (the platform
under a roof); the JSON's `stacks` list every floor at each point. With `--at` and `--yaw` the grid
is in world coordinates. Floors are tested as triangles in floating point, so a point exactly on an
edge may differ from the reader's integer rows; a world's own floors as the console finds them are
`mei_world.py floors` ([WORLDKIT-REFERENCE.md](WORLDKIT-REFERENCE.md#quick-tools)).

### Native tools

`verify`, `preview` and `build` run Mei's compiler (`meic`), the headless runner
(`mei-headless`, for previews) and the asset probe (`mei-asset-probe`, for the Asset Checker).
Each is taken from the first of:

1. its own option: `--compiler PATH`, `--runner PATH`, `--probe PATH`;
2. `--build-dir DIR`: `DIR/meic`, `DIR/mei-headless`, `DIR/mei-asset-probe`, the directory
   `make B=DIR` builds into;
3. its environment variable, `MEIC`, `RUN` or `PROBE` (as the test suites read them);
4. the environment variable `B`, a build directory relative to the repository (as make's `B`);
5. `build/`.

A command checks the tools it needs before it starts (`verify`: compiler and probe; `preview`:
compiler and runner, and the probe when the recipe requires the check or `--verify` is given). A
missing tool is an error at `/arguments/tools` naming the file, the directory it looked in, which
of the above chose it, the make command that builds it (`make B=build-mine build-mine/meic`) and
how to point the kit elsewhere.

### Camera views at world scale

The six fitted views scale every asset to about 2 units, so a 24 m railcar is a thin strip and
a sign on it a few pixels. `preview` (and `build --preview`) also renders views at the asset's
own size, as a game draws it: the mesh placed with `mesh_at` at the origin with yaw 0, the
camera where you put it, 60° field of view, near 0.1, far just past the asset. They draw with the
depth buffer (and perspective) when the six views do or the recipe's policy says `depth` (or
`perspective`): as the Asset Checker judges the asset, also when it is untextured, whose six
views draw without depth unless `--depth` is given. No HUD text is drawn. The contact sheet and
the six views are unchanged.

```sh
# a player's view and close-ups along a long asset
python3 tools/mei_assets.py preview railcar.asset.json -o build/assets/railcar --closeups
# eye and target, in the asset's coordinates (world units)
python3 tools/mei_assets.py preview stall.asset.json -o build/assets/stall \
  --camera counter=0,1.5,-2.5:0,1,0
# eye, then yaw and pitch in degrees (yaw 0 looks along +Z, positive turns toward +X;
# positive pitch looks up), and a named part framed close
python3 tools/mei_assets.py preview stall.asset.json -o build/assets/stall \
  --camera high=0,4,-4@0,-45 --part sign
```

| Option | Views |
|---|---|
| `--camera NAME=EX,EY,EZ:TX,TY,TZ` | From the eye, looking at the target. Repeatable. Without `NAME=` the view is `cameraN`; write `--camera=…` then if the eye's x is negative |
| `--camera NAME=EX,EY,EZ@YAW,PITCH` | From the eye, at that yaw and pitch (degrees), as `camera_look` takes them in radians |
| `--cameras FILE` | A JSON list of `{"name", "eye", "target"}` or `{"name", "eye", "yaw", "pitch"}`, for a set of views kept beside the recipe |
| `--part ID` | `part_ID`: that part's bounds (an `id` from `inspect`'s `parts`; all parts with that id together) framed from the isometric view's direction. A decal's id (`PART/ID`, from `inspect`'s `decals`) gives `decal_PART_ID`: the decal face on, from outside its face. Repeatable; an unknown id is an error listing the parts and decals |
| `--closeups` | `eye_level`: a player's eye 1.6 units above the asset's base, on its −Z side, far enough back to see its whole front, looking at the middle of its front. And, when the asset is more than 1.5 times as long along one axis as across the others, `closeup_1` … (up to 4) along that axis: each frames one equal segment from the front, 15° above (from +X when the long axis is Z) |
| `--upscale N` | 1–4, default 2: each camera view's PNG is 320 × 240 scaled up N times, pixel for pixel (the console draws 320 × 240) |

Each view is written as `camera_NAME.png` and the views together as `cameras.png` (two columns).
**Where the costs are:** `report.json` (and the output with `--json`) has `preview.cameras`, an
object whose `views` list has one entry per camera view, in the order given; the six fitted
views are in `preview.views`, the same way:

```json
"preview": {
  "contact": "…/contact.png",
  "views": [{"view": "isometric", "image": "view_isometric.png", "stats": {…}, "cost": {…}}, …],
  "cameras": {
    "contact": "…/cameras.png", "upscale": 2,
    "budgets": {"cpu": 1000000, "gpu": 2000000},
    "baseline": {"cpu_cycles": 4917, "gpu_cycles": 76800},
    "views": [
      {"view": "eye_level", "image": "camera_eye_level.png", "eye": [0, 1.6, -5.2], "target": […],
       "yaw_degrees": 0.0, "pitch_degrees": -4.1, "triangles": 202, "stats": {…},
       "cost": {"cpu_cycles": 31000, "gpu_cycles": 88000, "cpu_frame_percent": 3.1, "gpu_frame_percent": 4.4,
                "asset_cpu_cycles": 26083, "asset_gpu_cycles": 11200,
                "asset_cpu_frame_percent": 2.6, "asset_gpu_frame_percent": 0.6}}
    ]
  }
}
```

(The numbers are illustrative.) So one view's GPU share for the asset is
`preview.cameras.views[i].cost.asset_gpu_frame_percent`; with `jq`:
`jq '.preview.cameras.views[] | {view, gpu: .cost.asset_gpu_frame_percent}' report.json`. Per view:
its eye, target (when given), yaw and pitch (degrees), triangles drawn, the runner's statistics
and `cost`: the frame's CPU and GPU cycles and their share of the frame budgets
(`MEI_CYCLES_PER_FRAME` 1,000,000 and `MEI_GPU_CYCLES_PER_FRAME` 2,000,000, read from
`src/core/mei.h`, in `budgets`), and the asset's own share, `asset_cpu_cycles` and
`asset_gpu_cycles`: the frame minus the `baseline` frame drawn the same way without the asset
(in depth mode 4,917 CPU and 76,800 GPU cycles: the clears). The six fitted views' entries have
the same `cost` without the `asset_` fields, of the whole frame with its HUD text. A failed
verification puts the same `preview` in `verification.failed.json`.

Measured: a 24 × 3.5 × 2.9 m railcar (202 triangles, depth policy) with `--closeups`: five views,
`eye_level` 0.6 % of the GPU budget for the asset and each close-up 2.2–3.0 %; the `stall`
example's `--part sign` 3.8 %, its whole isometric fitted frame 5.3 %. A view costs one compile
and one run, about 0.05 s.

`eye_level` stands 1.6 units above the ground: y = 0 when the asset reaches below it (a post sunk
into the snow), else the asset's base. It starts as far back as the asset's front needs and
steps back by a tenth until all eight corners of the asset's bounds are inside the view, a tenth
of the way in from its edges, so a tall model (a 12 m pylon seen from 1.6 m) is not cropped.

### The look: background and ground

By default the views are drawn on a near-black background (`rgb(24, 28, 36)`) with nothing
else, which hides how an asset reads against a game's scenery: pale chrome on white snow, say,
or a post that is meant to stand a metre deep in the ground. A **look** gives every view of
`preview` (and `build --preview`), the six fitted views and the camera views, the game's
background and ground:

```sh
# a sky gradient, top to bottom, and white snow
python3 tools/mei_assets.py preview pine.asset.json -o build-mine/assets/pine --closeups \
  --background '#70d0f8,#fffcf4' --ground '#eef5fc'
```

| Option | Effect |
|---|---|
| `--background #RRGGBB` | The views' background in that colour (the frame's clear) |
| `--background #TOP,#BOTTOM` | A vertical gradient over the whole view, drawn before anything else |
| `--ground #RRGGBB` | The ground, the plane y = 0, in that colour: a faint checker (every other tile 0.96 times the colour) of square tiles aligned to the world's metres, 1 m, or 2, 4, … m so that at most 16 lie along a side. In the fitted views it reaches about three camera distances past the asset; in the camera views 20 units, or three times the asset's width if more, past the farthest eye (along X or Z), and their far clip is moved past its corners. `none`: no ground |
| `--look FILE` | A look file; `none`: no look file |

What lies below y = 0 is drawn, **seen through the ground, half tinted with its colour**, so the
part of a post sunk into the snow shows as such and the line where the asset meets the ground
is plain to see. A cart draws three passes for it, under the depth buffer: the ground (drawn and
flushed), the depth buffer cleared, the asset (all of it), then the ground again, half
transparent (blend mode 0), which tests against the asset: where a part is behind the ground, it
shows through half mixed with the ground; above the ground the asset is drawn as it is. A view
with a ground therefore draws with the depth buffer (and perspective-correct textures) also when
the asset would otherwise preview without them. Seen from below y = 0 (a `--camera` there),
everything above the ground is the part behind it. HUD text is dark on a light background
(luma above 140).

**A look file** sets the look once for a cart's assets: `asset-preview.json`, in the recipe's
folder or any folder above it up to the repository's root (the nearest wins), applies to every
preview of those recipes; `--background` and `--ground` override its values, `--look FILE` names
another and `--look none` ignores it. A recipe read from stdin has none unless given. Fall Line's,
`carts/fallline/models/asset-preview.json`, is its sky and snow:

```json
{
  "background": ["#70d0f8", "#fffcf4"],
  "ground": "#eef5fc"
}
```

`background` is a colour or a list of one or two; `ground` a colour. The report's `preview.look`
says what was drawn and where it came from (`"from": "carts/fallline/models/asset-preview.json"`,
or `arguments`). Without a look (no options and no file), the views and `preview.akr` are exactly
as before. The ground is in `preview_ground.bin` and `preview_ground_tint.bin` (the fitted views;
`preview.akr` embeds them) and `camera_ground.bin` and `camera_ground_tint.bin` (the camera
views), in the output directory. Costs include the look: the fitted views' frame costs include
the ground's passes, and a camera view's `baseline` draws the ground (with the background) without
the asset, so `asset_gpu_cycles` is still the asset's share. The six Fall Line models preview in
0.9–1.8 s each with `--closeups`, their Asset Checker included.

## Recipe fields

A recipe's shape and its naming rules are in the guide ([Recipe contract](ASSETKIT.md#recipe-contract)).
`schema` gives every field with its bounds and defaults; this section says what they do.

### Coordinates and transforms

Y is up. Distances are Mei world units and angles are degrees. The examples face -Z, which
is the preview's front camera; assets may use another facing convention if the cart needs it.

Every node accepts `id`, `material`, `transform` and `modifiers`. A transform contains optional
`scale`, `rotate`, `translate` and `pivot` three-number arrays. Defaults are scale `[1,1,1]` and
zero for the others. Zero scale is rejected; negative scale repairs winding automatically.

The exact order is:

1. Generate geometry or combine children after their own transforms.
2. Apply modifiers in list order, in that node's local coordinates.
3. Scale around the pivot, rotate X then Y then Z around the pivot, then translate.
4. Let the parent apply its modifiers and transform.

Mirror/radial modifiers operate around the local origin (mirror can supply an `offset`). To
repeat an offset shape around a center, place the shape in a child and repeat its parent group,
as in the stool example. A node's own translation happens **after** its modifiers.

### Geometry operations

| `op` | Required fields | Optional fields / convention |
|---|---|---|
| `box` | `size: [x,y,z]` | Centered at the origin; `open`: sides to leave out, from `top` (+Y), `bottom` (−Y), `left` (−X), `right` (+X), `back` (−Z), `front` (+Z), or by axis `+y`, `-y`, `-x`, `+x`, `-z`, `+z`; `faces`, `decals` ([below](#face-materials-and-decals)) |
| `sphere` | `radius` | `rings: 6`, `segments: 12`; scale for an ellipsoid |
| `cylinder` | `radius`, `height` | `segments: 12`, `caps: true`; centered, along Y |
| `cone` | `radius`, `height` | Same as cylinder; tip at +height/2 |
| `extrude` | `points: [[x,y],…]`, `depth` | Simple concave or convex XY polygon, extruded symmetrically along Z; either outline winding |
| `lathe` | `profile: [[radius,y],…]` | `segments: 12`, `caps: true`; rotate a silhouette around Y; heights strictly increase; zero-radius tips only at endpoints |
| `loft` | `sections: [{"y":…, "points": [[x,z],…]},…]` | `caps: true`; increasing Y; same point count, correspondence and winding in every section |
| `mesh` | `vertices: [[x,y,z],…]`, `faces: [[index,…],…]` | Zero-based indices; planar simple polygons are triangulated; outward right-handed winding; optional `face_materials` gives one material name per source polygon |
| `group` | `children: [node,…]` | Combined geometry; material inherited by children lacking an explicit material |
| `instance` | `ref` | Reference to a node in the root `prototypes` object; explicit instance material overrides the whole referenced component, except the sides of `faces` maps and decals |

`cylinder`, `cone`, `lathe`, `loft` and `extrude` take `faces` and `decals` too, and `mesh`
`decals` ([Face materials and decals](#face-materials-and-decals)).

A box's `open` sides are left out with the vertices only they use: `["bottom"]` for a building
or a block standing on the ground, whose underside nobody sees and which would otherwise sort
against the ground under it; `["bottom", "left", "right", "back", "front"]` for a flat ground
tile, its top alone (a box of any height, moved down by half of it, puts the top at 0). At least
one side stays; each is named once. An open box is an open surface, so it gets the
`open_surface` topology warning (and fails `--strict`), as any intentionally open mesh does.

Extrusion supports concave outlines through ear-clipping triangulation. Outline holes,
self-crossings, repeated endpoint vertices, and duplicate/collinear adjacent points are not
accepted. Loft correspondence matters: use the same corner order at every height. Nonplanar
polygons in explicit meshes must be supplied as triangles: a polygon with a corner farther from
its plane than 10^-6 of its extent (at least 10^-10 units) is an error that names the corner, its
vertex, how far off it is and the tolerance. Coordinates are rounded to Mei's
16.16 representation before topology checks and export; collapsed triangles are errors.

### Modifiers

| `op` | Fields | Meaning |
|---|---|---|
| `mirror` | `axis: "x"\|"y"\|"z"`, `offset: 0`, `keep_original: true` | Reflect around an axis plane, correcting winding |
| `array` | `count`, `step: [x,y,z]` | Copies at 0, step, 2×step, … |
| `radial` | `count`, `axis: "y"`, `degrees: 360` | Copies across an angular span; endpoint excluded to avoid a duplicate at 360° |
| `taper` | `top`, `bottom: 1` | Scale X/Z by a positive factor interpolated across the node's Y bounds |
| `twist` | `degrees` | Rotate progressively around Y from zero at the bottom to the supplied angle at the top |
| `subdivide` | `levels: 1…3` | Split each triangle into four per level, sharing midpoint vertices |

Taper and twist move existing vertices; subdivide first or provide more loft/lathe sections
when a curved deformation needs additional geometry. Subdivision preserves the surface and
can improve depth sorting, but each level multiplies triangle count by four. Mirror copies
are welded only where coordinates coincide; the tool does not remove internal caps or perform
a Boolean union. Overlapping copies may consequently produce topology warnings.

### Materials and lighting

Materials have `color: "#RRGGBB"` and optional `smooth: false`, `double_sided: false` and
`blend` ([Semi-transparent materials](#semi-transparent-materials)).
The implicit `default` material is `#c4cad4`. Flat shading is the default. Smooth shading uses
area-weighted vertex normals within each named part and material; split parts to retain a
hard boundary. Reflections and nonuniform scales are handled before normals are calculated.

Root `lighting` accepts `direction: [-0.4,0.85,-0.35]`, `ambient: 0.45`, `bake: true` and
`mode: "directional"`. Lighting is baked into face/vertex colors at export. Set `bake: false` for
unlit colors. Double-sided faces render their single baked color from either side.

The directional bake is in the asset's own frame: an asset drawn with `mesh_at(…, yaw)` at yaw
180 is lit from the opposite side to one drawn at yaw 0. For assets placed at arbitrary yaws
(buildings, props scattered through a scene), use `"mode": "vertical"`. Its shade depends only
on the normal's Y: `ambient + (1 - ambient) × (1 + y) / 2`, so tops are fully lit, walls get the
midpoint and undersides get `ambient`. Any rotation about Y leaves every face's shade unchanged.
The price is that all walls share one shade, so adjacent walls of a box are not told apart by
lighting; separate them with material colors. `direction` is an error in vertical mode.

Use `mesh.face_materials` for adjacent colored regions on one continuous surface, such as
a robot's visor and eyes. Each entry names a material for the corresponding source polygon;
all triangles produced from that polygon retain the material. This avoids overlapping colored
panels that can cut through one another under Mei's triangle depth sorting. The robot example's
head uses this approach, retaining a closed mesh with shared boundary vertices. Primitives do the
same with `faces` (a material per side) and `decals` (rectangles baked into a face), below.

### Semi-transparent materials

`blend` makes a material's faces semi-transparent, in one of the GPU's four blend modes
([RENDERING.md](RENDERING.md), `src/core/gpu.c`); without it a material is opaque:

| `blend` | Mode (blend byte) | Each 5-bit channel of the pixel (B: what is behind, F: the face) | For |
|---|---|---|---|
| `"half"` | 0, `BLEND_HALF` | (B + F) / 2 | glass, water, a canopy |
| `"add"` | 1, `BLEND_ADD` | B + F, at most 31 | glows, light shafts |
| `"sub"` | 2, `BLEND_SUB` | B − F, at least 0 | shadows, darkening |
| `"quarter"` | 3, `BLEND_QUARTER` | B + F / 4, at most 31 | faint glows |

```json
"materials": {"glass": {"color": "#38b8e8", "smooth": true, "blend": "half"}}
```

`build` and `pack` write every face of the material with flag bit 3 (`FACE_SEMI`) set and the
mode in its blend byte (LANGUAGE.md, "Mesh format"); nothing else about the face changes. Such a
face tests the depth buffer and writes none, so it hides nothing drawn after it. How it combines:

- **Colour and lighting** are as for any face: F is the face's baked, shaded colour (with
  `bake: false` its plain colour), so dark glass in `add` adds little.
- **Textures:** each texel is blended. A texture with holes (a cutout) draws nothing on texel 0
  and blends the rest; as for any cutout, the asset's policy must say `"depth": true`
  ([Cutouts](#cutouts)).
- **Palette-backed and emissive materials:** the palette entry's colour is blended, so
  rewriting the palette still recolours the face; an emissive `add` material is a glow whose
  strength is its palette entry (black adds nothing).
- **`double_sided`:** both sides are drawn and blended, so where a closed double-sided shell's
  front and back overlap on screen the face is blended twice.
- **Fog** (`fog()`): in `add`, `sub` and `quarter` a fogged pixel fades toward black, so the
  face's contribution fades out with distance; in `half` toward the fog colour.
- **Cost:** a semi-transparent pixel costs the GPU twice an opaque one (LANGUAGE.md,
  "Performance notes").

**Drawing order.** Semi-transparent faces must be drawn after the opaque faces behind them, back
to front: the blend reads what is already in the framebuffer, and they write no depth. `mesh*()`
does this. With `render_depth(true)` it puts them in a table of their own (`stdlib/depth.akr`),
drawn after every opaque face of the frame, farthest bucket first. Without the depth buffer every
face goes into the ordering table by its average view depth and the table is drawn back to
front, so a blended face is drawn after the opaque faces behind it only where the buckets order
them so: a large blended face around small opaque ones (glass over a cockpit) can be drawn
before a face it covers. The [Asset Checker](#semi-transparent-faces) finds those places; the
depth buffer removes them. A cart that builds its own packets keeps the same order (RENDERING.md,
"Drawing order"). The order of blended faces among themselves is their buckets': overlapping
`half` faces look different in another order, and so do adding and subtracting faces together,
while faces that all add (`add`, `quarter`) or all subtract (`sub`) do not.

**Where the faces are.** The material manifest gives each material's `blend` and its faces
(half-open ranges of the exported faces); `pack`'s `NAME.pack.json` gives each asset's
materials and tags the same way ([Outputs and game integration](#outputs-and-game-integration)).
`report.json` counts the semi-transparent triangles by mode (`blend`). The `.mtl` file gives a
`half` material `d 0.5`; `export` makes it an alpha-blended glTF material
([below](#viewing-an-asset-elsewhere-export)). Fall Line's sled canopy is the example
(`carts/fallline/models/sled/make_sled.py`). The World Kit places such a mesh as built; the World
Checker does not compare semi-transparent faces' pixels (its `unverifiable_faces` warning).

### Face materials and decals

**Face materials.** `faces` on a `box`, `cylinder`, `cone`, `lathe`, `loft` or `extrude` node
gives sides materials of their own; the sides it does not name keep the node's `material`. It
adds no triangles and no vertices: the same faces with other materials.

```json
{"id": "shop", "op": "box", "size": [3, 2.4, 2], "material": "wall", "open": ["bottom"],
 "faces": {"top": "roof", "back": "sign"}}
```

| `op` | Sides |
|---|---|
| `box` | `top`, `bottom`, `left`, `right`, `back`, `front`, or `+y`, `-y`, `-x`, `+x`, `-z`, `+z`, as for `open`: `back` is −Z, the side the front camera sees |
| `cylinder`, `cone`, `lathe`, `loft` | `top` (`+y`) and `bottom` (`-y`), the caps; `side`, everything else |
| `extrude` | `front` (`+z`) and `back` (`-z`), the outline's two faces; `side`, the walls |

A side is named once (`top` with `+y` is an error). A side without faces is an error that says
why: open, `caps: false`, a cone's top, a lathe profile ending in radius 0. A textured material
follows its projection on its side as anywhere (a `fit` texture on a box's `back` covers that
side once), and each repeating one is a texture window: the limit of 7 counts them and
`inspect`'s `texture_windows` lists them. `inspect` and `report.json` list the maps as
`face_maps`: per node its part, path, `sides` (side: material) and `triangles` per side. A `mesh`
node's polygons take `face_materials` instead.

**Decals.** `decals` on a `box`, `cylinder`, `cone`, `lathe`, `loft`, `extrude` or `mesh` node
lays rectangles of other materials on its flat faces:

```json
{"id": "wall", "op": "box", "size": [4, 3, 0.2], "material": "wall", "open": ["bottom"],
 "decals": [{"id": "poster", "face": "back", "material": "poster", "size": [0.8, 1.2], "at": [0.8, 0.1]}]}
```

| Field | Meaning |
|---|---|
| `face` | The flat face: a side of the table above (not the curved `side` of a cylinder, cone, lathe or loft, nor an extrusion's walls), or a `mesh` node's polygon index |
| `material` | The decal's material. A textured one draws its texture once over the rectangle as `fit` does, with the texture's `rotate` and `flip`, so its texture says `"projection": "fit"` (an error otherwise: a repeating texture would take a window for nothing) |
| `size` | Width and height, in the primitive's own units |
| `at` | The centre, default `[0, 0]`: right and up from the primitive's origin as it lies on the face, the face seen from outside (u's right, v's up). Primitives are centred, so `[0, 0]` is the middle of a box's side or of a cap. On a box's `back` (−Z) right is +X, on its `front` −X; on an extrusion's `back`, `at` is in the outline's own x and y |
| `id` | Default `decal_K` (K its index); the decal is `PART/ID` in the reports |

Up to 32 a node. A decal lies inside its face, at least 0.001 units from the face's edges and from
the other decals on it; otherwise the error says which edge and by how much, and the face's
extent in `at`'s coordinates:

```
The decal at [1.8, 0], size [1, 1], does not fit inside the side 'back' of 'wall': its right edge is 0.3 past the face's right edge. In at's coordinates (right and up as seen from outside, from the primitive's origin) the face spans x -2 to 2, y -1.5 to 1.5; a decal lies inside its face, at least 0.001 from its edges. Move or shrink it, or give the whole side the material (faces).
```

Decals are applied with `faces`, before the node's modifiers and transform, so `array`, `mirror`
and instances copy them. An instance's `material` changes neither.

**How a decal is made.** It is baked into its face: the face's outline gets the rectangle as a
hole, the ring around the hole is triangulated again (ear clipping, the hole joined to the
outline by one edge), and the rectangle becomes two faces of the decal's material. The
rectangle's corners are corners of the ring's triangles, so there are no T-junctions, and the
decal lies in the face's plane sharing its edges with the ring, so nothing overlaps: no coplanar
overlap for the Asset Checker, nothing for the depth test to tie, nothing for the ordering table
to sort wrong. The part stays closed. **Cost: 8 triangles and 4 vertices a decal**, whatever its
size: a face of *m* corners with *k* decals becomes *m* + 8*k* − 2 triangles where it was *m* − 2
(the decal's own 2 and 6 more around it). The ring keeps the face's material (a `mesh`
polygon's from `face_materials`) and, on a `mesh` node with `uvs`, its hand UVs: the outline's
corners keep theirs and each rectangle corner takes them interpolated over the polygon's triangle
it lies in, so a textured face looks the same around its decals as without them.

The alternative was drawing order: a quad over the face, drawn after it. In the face's plane that
is a coplanar overlap, which the Asset Checker fails in both modes, and the order would rest on
each mode's tie-breaking; standing proud of the face, it must be 3 cm out before the depth key
stops tying it ([close faces](ASSETKIT.md#authoring-rules-depth-mode)), and without the depth buffer the
ordering table sorts the quad and the face's large triangles by depth and gets it wrong from many
angles. Measured with the default sweep (144 views) on a 0.8 × 1.2 poster on a 4 × 3 wall: the
quad 3.5 cm proud (12 triangles) passes in depth mode and fails without it, 12,818 wrong-depth
pixels in 52 views; the decal (18 triangles) passes both.

**In the reports.** `inspect` and `report.json` list `decals`: per decal its `id`, `part`,
`path`, `face`, `material`, `at`, `size`, `triangles` (its faces in the final mesh, every copy),
`added_triangles` (8 a copy), `bounds` and `normal` (the first copy's). A decal's faces belong to
its node's part. `preview --part PART/ID` frames a decal face on
([Camera views](#camera-views-at-world-scale)), and the Asset Checker's issues name a decal's
faces with `decal` beside `part` and `material`.

### Palette-backed materials

An ordinary material's colour is baked into vertex colours, which live in the mesh in ROM: a
cart cannot recolour it. A palette-backed material is drawn through a palette entry instead,
so rewriting that entry at run time (`load_palette`, `palette_lerp`, `palette_rotate`) recolours
every face using it. Material fields:

| Field | Default | Meaning |
|---|---|---|
| `palette` | `false` (`true` when emissive) | Draw through a palette entry |
| `class` | `"surface"` | `"emissive"`: palette entries of its own, never shaded, reported separately |
| `tag` | none | Opaque surface tag (a name), carried to the outputs; the kit does not interpret it |
| `share` | `true` | Palette-backed only. `false`: an entry of its own, never shared (below) |

```json
"materials": {
  "wall": {"color": "#d9c6a0", "palette": true, "tag": "wall"},
  "door": {"color": "#6b4a3a", "tag": "door"},
  "neon": {"color": "#ff3fa4", "class": "emissive", "tag": "sign"}
},
"lighting": {"mode": "vertical", "ambient": 0.5},
"palette_layout": {"slot": 14, "row": 0, "first": 0}
```

**Representation.** Each palette-backed face is a 4-bit textured face whose three texture
coordinates are the same texel of a 16-texel *swatch*: texel `u` of one texture row holds palette
index `u`. The face's palette byte selects a 4-bit palette and its `u` the entry, so the GPU
fills the face with exactly that palette colour (equal coordinates interpolate to the same texel
everywhere, also after near-plane or guard-band clipping). The baked shade becomes the vertex
tint, where 128 is unchanged: a face shaded 0.75 has tint 96 and shows 75 % of its entry's
colour, so shape shading survives any recolouring. Smooth materials still get Gouraud tints.
`palette_layout` places the swatch (texels u 0–15 of `row` in texture `slot`, 0–31 but not 15;
default slot 14, row 0; 8 bytes of VRAM) and the first 4-bit palette (`first`, 0–510, the
palettes never running into 255, the fonts'; default 0). Slots 16–31 and palettes 256–511 are
VRAM's second megabyte ([DECISIONS.md](DECISIONS.md#vram-at-2-mb)); a face there has bits 6 and 7
of its flags set ([LANGUAGE.md](LANGUAGE.md#mesh-format)).

**Entries.** The kit gives one entry to each distinct colour per class among the palette-backed
materials the mesh uses: surface entries first, then emissive, as indices 1–15 of palette
`first`, then of `first + 1`, and so on. Index 0 is never used, since the GPU never draws it.
Surface materials with the same colour share an entry and recolour together by default; give a
material `"share": false` to force an entry of its own, so it can be recoloured separately while
looking the same by default (its manifest entry says `"separate": true`, and a packer keeps it
separate too). An emissive material never shares an entry with a surface one, even with the same
colour, so a cart can drive emissives with a different curve.

**Emissive shading.** An emissive surface's brightness is its palette entry's, not the light's:
its tint is 128 at every vertex, whatever the lighting, `smooth` or orientation. Brightening or
dimming it is the cart's job, through its entries. Emissive implies `palette: true`; setting
`palette: false` on an emissive material is an error.

**Tags** are names such as `wall`, `floor` or `sign`, on any material (palette-backed or not).
The kit carries them to `report.json` (triangles per tag, tags per part) and to the material
manifest (face ranges per tag), so a later tool can derive collision surface types or other
game data from them. The kit attaches no meaning to them.

**Cost.** A textured pixel costs the GPU twice a flat one (`gpu_used()`; `DECISIONS.md`, "GPU
budget"). Measured with the kiosk example's previews, the same mesh built once palette-backed and
once with plain vertex colours: in the isometric view the mesh's GPU cycles (excluding the `cls` and
the HUD text) go from about 18,050 to 29,800, +65 %: the 94 triangles cost the same and the 12,600
filled pixels cost double. That is 0.6 % of the 2,000,000-cycle frame budget (1.2 % of the 1,000,000
it was) for an asset covering a sixth of the screen. CPU cost rises about 7 % (textured packets are
longer). Mix both kinds freely: only palette-backed materials pay for textures, so leave materials
that never change colour unbacked (the kiosk's door is).

**Caveats.** Fog makes textured faces fade toward half the fog colour (their colour is a tint),
so they can only fog toward dark colours. Do not enable `subdivide()` for these meshes: a swatch
has nothing to warp, and splitting would only add triangles. Palette 255 and texture slot 15
hold the fonts.

**Verification.** The gate checks palette-backed faces as untextured faces with the same
geometry, flags and order. That is exact: such a face covers precisely the pixels of the
untextured face (only texel index 0 skips pixels, and swatch faces never sample it), and
`mesh()` clips, culls and sorts textured faces like untextured ones. Faces of a
[texture](#textures) are judged the same way unless the texture has holes.

### Levels of detail

`lod` gives an asset simpler meshes for farther away. Level 0 is the recipe's own `nodes`; each
entry of `lod.levels` is a coarser level with its own `nodes` and the `distance` (units, from the
viewer to the placed mesh) from which it is drawn. Every level shares the recipe's materials,
prototypes, lighting, palette layout, budget and verification policy:

```json
"lod": {
  "levels": [
    {"distance": 24, "nodes": [{"id": "body", "op": "box", "size": [6, 9, 5], "open": ["bottom"],
                                "material": "brick", "transform": {"translate": [0, 4.5, 0]}}]},
    {"distance": 48, "nodes": [{"id": "body", "op": "box", "size": [6, 9, 5], "open": ["bottom", "back"],
                                "material": "brick", "transform": {"translate": [0, 4.5, 0]}}]}
  ],
  "cull": 90,
  "band": 1
}
```

| Property | Meaning |
|---|---|
| `levels` | 1–7 coarser levels, distances increasing |
| `cull` | Not drawn at all from this distance on (beyond the last level). Default: never culled |
| `band` | Hysteresis in units, default 1: a consumer changes level only once the distance is this far past a switch distance. Distances (and the cull) must lie more than twice the band apart, and the first more than twice the band from 0 |

A level may draw only palette-backed materials that level 0 draws: every level uses level 0's
palette entries, so one palette and one relocation serve them all. A level may draw textured
materials level 0 does not (since 2026-10-05: a far card's second drawing, an impostor's
pictures): level 0 loads and places every textured material its levels' nodes name
(`material`, `face_materials`), so every level shares one placement, and they count in the
asset's VRAM. A level with no fewer
triangles than the one before is a warning (`lod_not_simpler`). The report's `lod` lists each
level's distance, triangles and vertices, with `cull` and `band`. `build` writes each level as
`NAME.lodK.bin` (K from 1) and embeds it in `NAME.akr` as `ASSET_NAME_LODK`. `verify` checks
every level as an asset of its own with the same policy (pictures under `lodK/`), lists the
levels' results under `lod`, and fails if any level fails. Choosing the level is the consumer's:
the World Kit stores the distances in the pack and the reader chooses per placement
([WORLDKIT-REFERENCE.md](WORLDKIT-REFERENCE.md#levels-of-detail)).

### Impostors

Built (2026-10-05). `tools/assetkit/impostor.py` makes an asset's coarsest level from pictures of
its level 0: `with_impostor(recipe, folder, NAME, ppu)` renders level 0 orthographically from the
front (looking along +Z) and the side (from +X) as the console colours it (textures, palette
colours, the baked shade; texture holes stay holes), `ppu` pixels a unit with 2 × 2 supersampling,
writes them as 4-bit cutout PNGs (`art/NAME_front.png`, `art/NAME_side.png`, at most 15 colours by
median cut), and puts in place of the coarsest level a box of four double-sided quads round level
0's bounds, the front picture on its front and back and the side picture on its ends, mapped by
world position. The pictures are brightened by the shade the box's walls get, so they come out as
drawn. A recipe's generator calls it (Pillow and NumPy); rerunning writes the same files. The
asset's policy must allow cutouts (`depth: true`).

Eight triangles and two small textures: the shrine's temple (2 pixels a unit: 3,136 + 1,792 bytes
of VRAM on the 8-texel grid), pagoda (3: 1,920 + 1,920) and two-storey gate (2.5: 1,120 + 480)
(`carts/garden/shrine/assets/art/make_impostors.py`), and the shrine town's station concourse (3:
3,040 + 2,080, `make_concourse.py`), in place of 30–56 triangles of flat palette bands. Seen from
much nearer than its pictures' scale the box shows its flatness; the shrine town draws them from
70–110 units.

### Budgets and diagnostics

The default asset budget is 2,048 vertices and 2,000 triangles. The vertex cap matches Mei's
mesh limit. The triangle default is an authoring allowance, not the whole scene's budget;
an explicit `budget.triangles` may go up to the hardware's 4,000-triangle frame limit.
Choose much smaller budgets for repeated objects. Exceeding a budget fails the build.

Each part reports bounds, vertex/triangle counts, materials, boundary edges, nonmanifold
edges, inconsistent winding and duplicate triangles. Closed parts with negative aggregate
signed volume generate a winding warning. Repetitions retain their source part path so a
report points back to the recipe that needs changing. Topology checks are per part and do not
detect all inter-part intersections or every self-intersection caused by deformation.

Without the depth buffer ([Depth mode](#depth-mode) is the alternative), large overlapping
triangles and details close to a surface can obscure one another even when the mesh is
topologically valid. Subdivide selected large
surfaces, give decorations enough separation, and inspect native renders. The generated
preview uses a fitted camera and tight clip range for ordering-table precision. It scales and
centers the original exported mesh for viewing without changing the exported world units.
Extremely small/large meshes may still expose fixed-point precision limits; use ordinary prop
scales and verify in the actual scene. `inspect` reports a recipe over its budgets in full, so
the per-part counts show what to cut.

### Triangle costs

What each operation makes, before vertices at the same 16.16 position are merged (so vertex
counts are at most these). *s* is `segments`, *r* `rings`, *n* the points of an outline or
profile, *k* the sections of a loft. Checked against `compile_recipe` for the values shown.

| `op` | Triangles | Vertices | Example |
|---|---|---|---|
| `box` | 12, less 2 a side in `open` | 8 (fewer when sides are open) | a box 12; `"open": ["bottom"]` 10 |
| `cylinder` | 4*s* − 4 (2*s* sides, *s* − 2 each cap); 2*s* with `caps: false` | 2*s* | *s* 12: 44 |
| `cone` | 2*s* − 2 (*s* sides, *s* − 2 the base) | *s* + 1 | *s* 12: 22 |
| `sphere` | 2*s*(*r* − 1) | *s*(*r* − 1) + 2 | default 12 × 6: 120 |
| `lathe` | 2*s* per pair of rings, *s* where one is a zero-radius pole; *s* − 2 per cap (a ring with radius) | *s* a ring, 1 a pole | 3 rings, *s* 12: 48 + 20 = 68 |
| `extrude` | 4*n* − 4 (2*n* sides, *n* − 2 each cap) | 2*n* | a square 12, a hexagon 20 |
| `loft` | 2*n*(*k* − 1) + 2(*n* − 2) with caps | *n k* | 6 points, 3 sections: 24 + 8 = 32 |
| `mesh` | *m* − 2 per polygon of *m* corners | as given | a quad 2 |
| `faces` | no change | no change | a box with a sign side 12 |
| a decal | 8 more | 4 more | a box with a decal 20; two decals 28 |

Modifiers multiply: `mirror` 2 (with `keep_original`), `array` and `radial` their `count`,
`subdivide` 4 per level. Texture splitting adds pieces (`split_faces` in the report). For the
cost of drawing them, see a camera view's `cost` ([Camera views](#camera-views-at-world-scale)).

### Hidden limits

Limits that are not budgets, each an error naming itself when reached:

| Limit | Value |
|---|---|
| Vertices of a mesh | 2,048 (the console's; `budget.vertices` at most) |
| Triangles | `budget.triangles` at most 4,000 (the frame's limit); default 2,000 |
| Root `nodes`, a group's `children`, `materials`, `prototypes` | 128 each (`lod.levels[].nodes` 128) |
| Modifiers on a node | 16 |
| The expanded recipe | 4,096 nodes, 32 levels deep; 65,536 vertices or triangles along the way |
| `segments` | 3–128; `rings` 2–64; a lathe profile 128 points, an extrude outline or loft section 256 |
| `array` and `radial` count | 128 |
| A `mesh` node | 8,192 vertices and faces, 256 corners a polygon |
| Repeating textures | **7 an asset** (a mesh's texture windows; one per distinct tile); tiles 8–128 texels, powers of two |
| A face on a repeating texture | 255 texels each way, else it is split |
| Textures drawn once (`fit`, `disc`) | 255 × 255 texels with the one-texel gutter; 8-bit ones 127 tall |
| A slot | 256 × 256 4-bit or 256 × 128 8-bit texels; slot 15 holds the fonts |
| Levels of detail | 7 |
| Decals | 32 a node; each at least 0.001 units inside its face and from the others |
| Coordinates | −32,767 to 32,767 units in a recipe; the mesh's 16.16 vertices below 32,768 |

## Textures

A material can carry a texture, drawn through palettes of its own (decided by the owner on
2026-10-04: [DECISIONS.md](DECISIONS.md#the-asset-kit)). Textures are most useful with the opt-in depth
buffer and perspective-correct texturing ([RENDERING.md](RENDERING.md)): large textured faces do
not warp, and texel 0 can be a hole. They also draw without it, affinely, as any textured face
does. The code is `tools/assetkit/textures.py` (sources, projections, splitting),
`tools/assetkit/texout.py` (files and loader), `tools/assetkit/packer.py` (`pack`) and the packer
the World Kit can share, `tools/kitcore/texpack.py`.

Patterns and texel grids need nothing beyond Python. Images and sheets are read with **Pillow**;
without it a recipe that uses one fails with an error saying so.

### Sources

A textured material has a `texture` with exactly one source:

```json
"brick":  {"color": "#9c4f34", "tag": "wall",
           "texture": {"pattern": "brick", "colors": ["#9c4f34", "#d6cbb4", "#86412b"],
                       "params": {"courses": 4, "bricks": 2}, "projection": "box", "scale": [0.5, 0.25]}},
"trim":   {"color": "#202020",
           "texture": {"texels": ["0110", "1221", "1221", "0110"],
                       "colors": ["#202020", "#e0c040", "#f0f0f0"], "projection": "fit"}},
"poster": {"color": "#e0e0d8", "texture": {"image": "art/poster.png", "bits": 8, "projection": "fit"}},
"sign":   {"color": "#d86030", "class": "emissive",
           "texture": {"sheet": "signs", "cell": "ramen", "bits": 8, "projection": "fit"}},
"glow":   {"color": "#d04a2c", "class": "emissive",
           "texture": {"sheet": "signs", "frames": ["glow_a", "glow_b"], "ticks": 12,
                       "projection": "cylindrical", "scale": [0.95, 0.3]}}
```

- **`pattern`**: generated by the kit, deterministically (integer hashes, no random numbers),
  `size` texels square or `[width, height]` (default 16), in `colors` (default: the material's
  colour). Every pattern repeats seamlessly when its divisions divide the size, and the kit
  checks that they do.

  | Pattern | Colours | `params` (default) |
  |---|---|---|
  | `brick` | brick, mortar, a varied brick (optional) | `courses` 4, `bricks` 2 a course, `bond` 0.5 (a course's shift, in bricks), `mortar` 1 texel, `seed` 0 |
  | `tile` | tile, grout, a second tile alternating as a checkerboard (optional) | `count` 2 a side, `grout` 1 |
  | `planks` | wood, joint, alternate boards (optional), grain streaks (optional) | `boards` 4 (along u), `joint` 1, `seed` 0 (where each board's end joint falls) |
  | `grain` | light, dark, a middle tone (optional) | `rings` 3 bands across u, `waves` 1 and `amplitude` 3 texels of waver along v, `seed` 0 |
  | `checker` | two | `count` 2 squares a side |
  | `stripes` | two or more, cycled | `count` 4, `axis` `u` (stripes across u) or `v` |
  | `lattice` | bar, background | `count` 2 bars each way, `bar` 2 texels, `diagonal` false; with `clear` naming the background, a grille or fence |
  | `speckle` | base, then flecks | `density` 0.25 of the texels, `seed` 0 |

- **`texels`**: rows of hex digits, top row first; digit k is `colors[k]` (up to 16 colours).
- **`image`**: a PNG file, relative to the recipe's folder.
- **`sheet`** with **`cell`**: one cell of a sheet. A sheet is one PNG holding many textures,
  declared once in the recipe's root `sheets`: a uniform grid,
  `"signs": {"image": "art/signs.png", "grid": [32, 16]}`, whose cells are named `[column, row]`,
  or, without `grid`, named rectangles in a file beside the image with the same stem
  (`art/signs.sheet.json`):

  ```json
  {"format": "mei-sheet", "version": 1,
   "cells": {"ramen": [0, 0, 32, 16], "emblem": [32, 0, 16, 16]}}
  ```

  A sheet is only an authoring container: the kit slices it, and every cell a recipe uses is
  packed like any other texture. The sheet's layout never becomes the VRAM layout.
- **`sheet`** with **`frames`** and **`ticks`**: an animated texture (below).

A material with a texture may not set `palette` or `share` (its texture has palettes of its own);
`class: "emissive"` makes its faces unshaded, as for palette-backed materials. The material's
`color` remains its colour in the exchange files (`.obj`/`.mtl`, the Modeler project), which carry
no textures ([`export`](#viewing-an-asset-elsewhere-export) does). A textured face's vertex colour
is the baked shade as a tint, 128 for unchanged, as for palette-backed faces.

**Texture fields** (also in `schema`):

| Field | Meaning |
|---|---|
| `pattern`, `params`, `size`, `colors` | a pattern and its parameters, size and colours |
| `texels`, `colors` | a texel grid |
| `image` | a PNG |
| `sheet`, `cell` / `frames`, `ticks` | a sheet's cell, or an animation of its cells, each shown `ticks` ticks (1–255) |
| `clear` | patterns and texel grids: this colour of `colors` is a hole (texel 0) |
| `bits` | 4 (default) or 8 |
| `projection` | `planar`, `box` (default), `cylindrical`, `disc` or `fit` |
| `axis` | `planar` (default `z`) and `disc` (default `y`) |
| `scale` | `[u, v]`: world units a repeat for `planar`, `box` and `cylindrical` (default `[1, 1]`); the world units the texture spans for `disc` (default the primitive's diameter); not for `fit` |
| `offset` | `[u, v]` added, in repeats (fractions of the texture) |
| `rotate` | 0, 90, 180 or 270: the texture turned clockwise on the surface |
| `flip` | `u`, `v` or `both`: mirrored |

### Bit depth and quantisation

Textures are **4-bit** unless they ask for **`"bits": 8`**. A 4-bit texture has at most 15
colours and an 8-bit one 255: index 0 is never a colour, since the GPU draws nothing for it. The
kit converts every colour to the GPU's 15 bits; when the distinct 15-bit colours fit, they are
kept exactly. Otherwise a median cut (boxes split along their widest channel at the median by
texel count, each box's colour its mean) picks the colours and every texel takes the nearest one;
the report gives `quantised_from` (the colours before). An image's pixels with alpha below one
half are holes.

VRAM is reported per texture (`vram_bytes`): rows of whole bytes, its gutter included (below),
so a 16 × 16 4-bit pattern costs 128 bytes, a 32 × 16 8-bit sign drawn once 33 × 17 = 561. An
8-bit texture is at most 128 texels tall (an 8-bit texture's rows 128 and on would be in the
next slot), 127 when drawn once.

### Projections

Texture coordinates come from each corner's position in its **primitive's own coordinates**,
before the node's modifiers and transform: an instance, array copy or rotated node keeps its
texture on its faces, and taper or twist bend the texture with the surface. Scaling a node with
its transform stretches its texture; size the primitive instead to keep the texel density.

| Projection | Mapping | Repeats |
|---|---|---|
| `planar` | along `axis`, as seen from the front (`z`, from −Z), from +X (`x`) or from above (`y`); `scale` world units a repeat | yes |
| `box` | each face by its dominant normal axis, seen from outside (each side of a box reads the right way round) | yes |
| `cylindrical` | around the primitive's Y axis: u by angle, v by height. The repeats around are rounded to a whole number, about the circumference at the largest radius over `scale[0]`, so there is no seam | yes |
| `disc` | in the plane across `axis`, centred on the primitive's origin, spanning its diameter (or `scale`): wheel faces, dials, round signs | no |
| `fit` | the texture exactly covers each face it is on: each plane of the primitive (each source polygon of a `mesh` node) | no |

Orientation, measured on the native renders: u runs to the right and v down as the face is seen
from outside, with "up" the primitive's +Y (+Z for a face that looks straight up or down). A
mirrored copy (the `mirror` modifier, a negative scale) is seen from its own outside too, so
text on it still reads the right way round; `flip` mirrors on purpose. The texture repeats from
the primitive's origin: at `offset` 0 a box centred on the origin has a repeat's edge through its
middle; `offset` [0.5, 0.5] centres a repeat on it instead.

**Hand UVs.** A `mesh` node may give `uvs`, one `[u, v]` per vertex in repeats (1 = the
texture's width or height; 0, 0 its top-left): its textured faces use them instead of the
projection. They are the escape hatch for shapes no projection fits. Whether they repeat is the
material's projection's (a `fit` material's hand UVs stay within 0–1). A polygon with decals
keeps them around its decals ([How a decal is made](#face-materials-and-decals)).

### Repeats, texture windows and splitting

A texture with a repeating projection is a **tile** that repeats through a **texture window**
([DECISIONS.md](DECISIONS.md#texture-windows)): it is stored once and faces sample it modulo its
size. Its width and height are therefore powers of two from 8 to 128. A mesh has at most **7
windows**, so an asset can use at most 7 different repeating textures (an error says so); the
same tile used by several materials is one window. Each face's coordinates are shifted by whole
repeats so its first repeat starts at 0.

Texture coordinates are 8 bits, so a face may span at most 255 texels of a tile (15 repeats of
16 texels). A longer face is **split** along the lines u = kL and v = kL, L being the largest
multiple of the tile size not above 255 (240 for 16 texels, 224 for 32, 192 for 64, 128 for 128):
the same lines for every face of the texture, so two neighbours that both need cutting share
their cuts. A neighbour that did not need cutting gets the new points on the edges it shares, so
no T-junctions open. The report gives `split_faces`; the pieces count against the budget. A
20-unit wall of a 16-texel brick at one unit a repeat (320 texels) is cut once along its length.
A corner within 10^-6 texels of a cut line counts as on it: with a `scale` that is not a power of
two, a corner meant to lie on a line lands a hair off it (240.00000000000017 texels), and cutting
there made a sliver that collapsed at 16.16 precision, an error. Of 1,500 random textured boxes
and cylinders (scales 0.1–1.1, offsets 0, 0.3 and 0.5), 328 failed so before and none now
(an `offset` of 0.3 moves corners off exact coordinates too); every recipe in the repository
builds byte-identical meshes either way. Should a piece still collapse, the error is at the
material's `texture/scale` and names the material, its texture, size, projection and scale.

A texture drawn once (`fit`, `disc`) is placed plainly with a one-texel **gutter** to its right
and below that repeats its last column and row, because a face's coordinate can reach its width
exactly at a corner. It is any size up to 255 × 255.

### Cutouts

A texture with holes (an image's transparent pixels, or the `clear` colour of a pattern or texel
grid) draws nothing there and writes no depth: fences, grilles, railings, foliage, round signs.
Cutouts draw correctly only with the depth buffer, so they are allowed only in assets whose
policy says `"depth": true` (`"verification": {"required": true, "depth": true, "perspective":
true}`); any other asset using one fails with an error at its texture. Draw such an asset with
`render_depth(true)`. Semi-transparency is per material, not per texel: a material with
[`blend`](#semi-transparent-materials) blends every texel of its faces but the holes, in one mode;
a texel has no alpha of its own.

### Animated textures

`{"sheet": "neon", "frames": ["a", "b", "c"], "ticks": 8}` is an animated texture: each frame a cell
of the sheet, all the same size and with their holes in the same places, each shown 8 ticks,
looping. Meshes are read in place from ROM, so frames are not chosen by rewriting faces: the texture
has one tile in VRAM (frame 0 is loaded), and its frames are kept in ROM in the tile's own layout
(`NAME.frames`), ready to be copied into the tile when the frame changes. All frames share one
palette (they are quantised together). Every placement of the asset animates in step.
`stdlib/texanim.akr` copies a frame when it changes (`tex_frame_at`, `tex_frame_copy`, with the
constants in `NAME.akr`:
[LANGUAGE.md](LANGUAGE.md#animated-textures-texanimakr-and-world-backdrops-wpbackdropakr)); a
world's animations are advanced by `wp_animate()`. Palette cycling (`palette_rotate`,
`palette_lerp`) is the cheaper alternative for flicker and glow.

### Placement: `build` and `pack`

An asset declares its textures; where they go is a packer's business (`kitcore/texpack.py`).
The packer removes duplicate tiles (equal texels, size, depth and window use: one brick tile
however many materials or assets use it), gives tiles palettes (4-bit tiles share 16-colour
palettes while their colours fit, first fit in order; 8-bit tiles share 256-colour ones), and
places each tile in a slot at an origin that is a multiple of 8, as windows need. A slot holds
tiles of one depth: 256 × 256 4-bit texels or 256 × 128 8-bit ones. Slot 15 and 4-bit palette
255 (8-bit palette 15) hold the fonts and are never used. Textures that do not fit are an error
naming the tile and the total.

**`build`** places one asset's textures on its own, so that its mesh, preview and check work
alone: in slots from `palette_layout.slot` (default 14) down to 0, then 14 down, the
palette-backed swatch's 8 × 16-texel block reserved; 4-bit palettes after the swatch's (or from
`palette_layout.first`); 8-bit palettes from 14 down. `palette_layout` may be given for a
textured asset without palette-backed materials.

**`pack`** places a set of assets together, for a cart that draws them without a world:

```sh
python3 tools/mei_assets.py pack examples/assets/stall.asset.json examples/assets/kiosk.asset.json \
    -o build/street --name street --slots 10-14 --palette 0 --palette8 14
```

It compiles each recipe, packs all their tiles once into the slots given (0–31 but not 15: a range
`10-14`, which is also their order of preference, or a list `14,12`; default `14-0`), gives the
palette-backed materials of each asset consecutive 4-bit palettes from `--palette` (0–510; an
asset's palettes never cross 255, the fonts', and move to 256 instead) with one shared swatch at row
0 of the first slot, then the 4-bit textures' palettes, and 8-bit palettes from `--palette8` (0–31
but not 15) down. It writes each mesh for that placement (`NAME.bin`, `NAME.lodK.bin`), the slots'
texels (`street.slotK.tex`), the palettes (`street.tpal` for textures, `street.pal` and
`street.swatch` for palette-backed materials), animation frames (`street.frames`), one `street.akr`
that embeds every mesh and defines `street_load()`, and the manifest `street.pack.json` (per asset
its files, counts, palette entries, textures, and each material's and tag's faces, blend modes
included: [the material manifest](#outputs-and-game-integration)). It does not run the Asset
Checker; `build` or `verify` each asset for that.

```
import "street.akr"
import "depth.akr"

fn init() { street_load() }        // texels, swatch and palettes into VRAM, once

fn draw() {
    cls(rgb(24, 28, 36))
    render_depth(true)
    camera_look(vec3(0.0, 1.5, -4.2), 0.0, -0.05)
    mesh_at(ASSET_STALL, vec3(0.0, 0.0, 0.0), 0.0)
    mesh_at(ASSET_KIOSK, vec3(4.0, 0.0, 2.0), 0.6)
}
```

A slot's file holds the rows from its first used row to its last, whole rows (128 bytes a 4-bit
row, 256 an 8-bit one), so a slot with one 33 × 17 8-bit sign costs 4,352 bytes of ROM. The
loader copies them with `memcpy`; textures load before the swatch, which may share their slot.

`--swatch` keeps the swatch's block free and loads the swatch even when no material is
palette-backed. Every swatch is the same 16 texels (texel *u* holds index *u*), so such a pack
can share slot 14 with a world's swatch: the movement garden draws its star, the hanafuda moon
card, from a pack in slot 14 that no world region uses (`--slots 14 --palette 254 --swatch`;
[carts/garden/README.md](../carts/garden/README.md#goals)).

### Outputs and the manifest

A textured asset's `build` adds `NAME.slotK.tex` (each slot used), `NAME.tpal` (the texture
palettes, index 0 of each 0), `NAME.frames` (animations), and to `NAME.akr` their embeds and
`asset_NAME_load()`, which a cart (and the preview cart) calls once:

```
// Textures: slots 13, 14; palettes 4-bit 0, 4-bit 1, 8-bit 14. Call asset_stall_load() before drawing.
embed ASSET_STALL_TEX13: u8 = "stall.slot13.tex"
embed ASSET_STALL_TEX14: u8 = "stall.slot14.tex"
embed ASSET_STALL_TEXPAL: u16 = "stall.tpal"
embed ASSET_STALL_FRAMES: u8 = "stall.frames"
const ASSET_STALL_LANTERN_AT = 0                // and _FRAME_BYTES, _FRAMES, _TICKS, _ROW_BYTES,
const ASSET_STALL_LANTERN_VRAM = 426040         // _ROWS, _STRIDE: the copy a helper will make
fn asset_stall_load() { … }
```

`report.json` gains `textures`: textured triangles, `split_faces`, `windows`, the tiles, slots
and palettes used, `vram_bytes` (the tiles) and `vram_bytes_allocated` (rounded to the 8-texel
grid), and per texture its source, size, depth, colours, projection, `repeat`, `cutout`,
`vram_bytes`, `quantised_from`, and `frames`, `ticks` and `rom_bytes` for an animation.

The **material manifest** (`NAME.materials.json`) gains `textures`, the shape a packer reads
(`pack`'s `NAME.pack.json` lists the same entries per asset):

```json
"textures": {
  "slots": [{"slot": 13, "bits": 4, "file": "stall.slot13.tex", "first_row": 0, "rows": 17,
             "stride": 128, "bytes": 2176}, …],
  "palettes": {"file": "stall.tpal", "runs": [{"bits": 4, "first_colour": 0, "colours": 32, "offset": 0},
                                             {"bits": 8, "first_colour": 3584, "colours": 18, "offset": 32}]},
  "animations": [{"tile": "b0efae980a6dbfe3", "label": "lantern", "file": "stall.frames", "offset": 0,
                  "frames": 2, "ticks": 12, "frame_bytes": 128, "row_bytes": 8, "rows": 16,
                  "vram": 426040, "stride": 128}],
  "windows": [562, 578, 594, 610, 626],
  "list": [{"material": "lantern", "tile": "b0efae980a6dbfe3",
            "source": {"sheet": "signs", "image": "art/stall_sheet.png", "sha256": "…", "frames": ["glow_a", "glow_b"]},
            "width": 16, "height": 16, "bits": 4, "projection": "cylindrical", "repeat": true, "cutout": false,
            "colours": ["#6b1010", …], "slot": 13, "x": 112, "y": 0, "gutter": 0, "window": 626,
            "palette": 1, "first_colour": 16, "indices": {"#6b1010": 1, …}, "vram_bytes": 128,
            "night": "per_colour", "faces": [[80, 100]], "frames": 2, "ticks": 12}, …]
}
```

- `slots`: each slot file, the rows it covers and their stride; `palettes.runs`: where in
  `NAME.tpal` (`offset`, in colours) each run of palette colours starts and which colours it
  loads.
- `animations`: per animated tile, its frames in `file` from `offset`, each `frame_bytes` long:
  `rows` rows of `row_bytes`, to be copied to texture-area byte `vram` and every `stride` bytes
  after (`VRAM_TEXTURES + vram`). Frame k starts at `offset + k × frame_bytes`.
- `windows`: the mesh's window table, in order (window n is entry n − 1).
- `list`: per textured material, its tile (`tile` is the content key that removes duplicates), where
  it is (`slot`, `x`, `y` in texels, `gutter`), its window halfword (`null` when drawn once), its
  palette (`palette`: a 4-bit palette 0–254 or 256–511, or an 8-bit one 0–14 or 16–31;
  `first_colour` its colour 0) and which entry each colour has (`indices`), and the faces (half-open
  ranges of the exported faces).
- `night`: what a day/night palette variant can do with the texture. `per_colour` (4-bit): each
  entry of its palette can be given its own night colour, as palette-backed entries are. `multiply`
  (8-bit): a region's night variant is to tint the whole 256-colour palette by one colour (each
  channel times a factor), not entry by entry (built in the World Kit); the palette's colours
  are `first_colour` + 1 onward.

In `NAME.bin` a textured face has flag bit 1 set, texture byte `slot | 16 (4-bit) | window << 5`,
palette byte its palette, and texture coordinates `u | v << 8`: for a windowed tile the face's own
coordinates (0–255, the window adds the origin), for a tile drawn once the coordinates plus its
`x`, `y`.

### The Asset Checker and textures

Textured faces are judged as **solid faces**, as palette-backed faces are, except faces whose
texture has holes. A texture without holes never samples texel 0, so its face covers exactly the
pixels of the untextured face; such faces are drawn untextured in the identity cart, with the
same geometry, flags and order.

**Cutout faces are judged per texel.** The verification cart keeps them textured: it loads the
packed texture area with every texel that is not 0 made 1, colour 1 white, and carries each
face's ID in its tint (a white texel tinted t shows 255 t >> 7, so t = ⌈1024 k / 255⌉ shows the
5-bit value k exactly). The reference rasteriser then samples the real texels the way the GPU
does ([RENDERING.md](RENDERING.md#perspective-correct-texturing)): the vertex reciprocals 2^40 / w
from the console's own projected depths, the exact q-weighted planes divided at each span's first
pixel, every 16th and its last and stepped between with truncation (affine when the scaled
reciprocals are equal), then the texture window and the texel. A pixel on texel 0 is not covered,
so the faces behind it are expected there. Coverage is exact (0 coverage errors in the stall's 144
views and the tests' fence), and replacing the per-texel coverage with the face's outline or with affine
mapping gives thousands of coverage errors on the same views (`tests/test_assetkit.py`,
`TextureCheckerTests`). Animations are checked with frame 0; their frames have their holes in the
same places.

### Cost

Textured pixels cost the GPU twice a flat one, as palette-backed faces already do; perspective
correction adds 24 cycles a triangle and 2 per divide (RENDERING.md). A mesh with a window table
costs about 55 more CPU cycles a `mesh*()` call and 10 per visible windowed face (LANGUAGE.md,
"Performance notes"). Measured with the stall's previews in depth mode, the same mesh with and
without its textures (the frame's clears and HUD text included): isometric view 94,687 → 105,828
GPU cycles (+12 %) and 20,776 → 24,547 CPU cycles (+18 %); front view 91,752 → 99,672 and
19,760 → 23,296. Patterns and images add VRAM, not GPU time.

### The example: `stall`

[`stall`](../examples/assets/stall.asset.json) is a noodle stall with every kind of texture: `brick`
(box), `planks` (planar, from above), `grain` (cylindrical, turned 90°), `stripes` on the awning, a
32 × 16 8-bit sign from a named cell of
[`art/stall_sheet.png`](../examples/assets/art/stall_sheet.png) (`fit`), an emblem with transparent
corners on a disc (`disc`, a cutout), lattice side screens (`fit`, a cutout through `clear`) and an
animated lantern (two frames, cylindrical, emissive). It requires the Asset Checker in depth mode.
Numbers (`build`): 144 triangles, 116 vertices, 8 tiles in slots 13 (4-bit) and 14 (8-bit), 1,507
bytes of texels (2,176 on the 8-texel grid), 4-bit palettes 0–1 and 8-bit palette 14, 5 windows, no
split faces. Its check: 18 of the 144 views judged, 0 wrong pixels, 0 coverage errors, 0.7 s (14.3 s
judging every view, one cart each). Preview views: 99,000–107,300 GPU and 22,200–25,700 CPU cycles.
Packed with the kiosk and drawn by a cart in depth and perspective mode (four views, from the stall
a third of the screen to a close view filling it, the kiosk beside it): 109,154–200,638 GPU and
30,686–34,855 CPU cycles a frame. `tests/test_assetkit.py` packs and draws the same pair.

The sheet is authored art (drawn once with Pillow and committed; no generator rewrites it).

### Texture tips

- **Use power-of-two scales** (0.25, 0.5, 1, 2 units a repeat) for repeating textures: texel
  coordinates are then exact binary fractions, so repeats line up with box edges and the cuts of
  long faces fall on exact coordinates. Size the primitive, not the node's `scale`, to keep the
  texel density. One texel is `scale` / tile size units: a 16-texel brick at 0.5 is 3.1 cm a
  texel.
- **Text:** draw it with `"bits": 8`, or without antialiasing (Pillow: `draw.fontmode = "1"`). A
  4-bit texture has 15 colours, and the many grey edge shades of antialiased text are merged by
  the quantiser (`quantised_from` in the report) into a smear of the nearest colours; the GPU
  samples the nearest texel, so the edge shades buy no smoothness either.
- **Smallest readable glyph:** about 7 texels tall (5 wide) in the texture, as `font_small()`'s
  capitals ([LANGUAGE.md](LANGUAGE.md)), and about 7 pixels tall on screen. At 60° field of view
  and 240 lines a unit at distance *d* is about 208 / *d* pixels tall, so a glyph that must read
  from *d* units is at least *d* / 30 units tall: 17 cm from 5 m, 33 cm from 10 m. Texels much
  smaller than a pixel at that distance flicker, as nothing filters them: aim for one texel
  about *d* / 208 units.

### For a region packer (the World Kit)

Built (2026-10-04): the World Kit packs a region's textures with these pieces
([WORLDKIT-REFERENCE.md](WORLDKIT-REFERENCE.md#textures-per-region), `tools/worldkit/textures.py`).
What it uses:

- `kitcore.texpack.pack(tiles, slots, first_palette, palette8, reserved, group=None)` → a
  `Packing` (`group`: tile key → a group, tiles sharing palettes only within one; the World Kit
  keeps surface and emissive textures apart; without it packing is as before), with
  `placements` by tile key, `palettes`, `slot_image(slot)`, `encode(key, frame)`,
  `palette_bytes(bits, palette)` and `summary()`; `Tile` and `Placement` are its records.
- `compile_recipe(recipe, folder)` gives the mesh with `mesh.textures['textures']` (material →
  `Texture`, whose `.tile` is the `Tile`), and `native_bytes(mesh, materials, lighting, packing)`
  writes the mesh for any packing that places its tiles; `texout.outputs()` writes the slot,
  palette and frame files and the loader lines for a packing.
- A region's palette variants: 4-bit textures entry by entry (`night: per_colour`), 8-bit
  textures by one tint over their palette (`night: multiply`).

## Automated visibility gate

Run a diagnostic sweep without exporting game assets:

```sh
python3 tools/mei_assets.py verify model.asset.json -o build/model-check
```

Or prevent publication of a bad build:

```sh
python3 tools/mei_assets.py build model.asset.json -o build/model --verify
```

To make the gate persistent, add this root property to the recipe:

```json
"verification": {
  "required": true,
  "yaw_steps": 24,
  "pitches": [-0.35, 0, 0.35],
  "distances": [1, 1.5],
  "far": 100,
  "geometry": "error"
}
```

Then both `build` and `preview` enforce it even without `--verify`. Merely including
`verification` implies `required: true`; explicitly setting it false leaves verification
opt-in. Ordinary legacy recipes without this property retain their existing build behavior.
There is no CLI bypass of a required recipe policy. Failed verification leaves previous
mesh/import outputs intact and writes `verification.failed.json` plus diagnostic images under
`verification-failed/`. When a preview was asked for (`preview`, `build --preview`), the model
is still rendered as it stands, so that it can be seen while being repaired: the six views,
`contact.png` and any camera views go to `verification-failed/preview/` (replaced on each failed
run), each marked with a red VERIFICATION FAILED, and `verification.failed.json` gains `preview`
(with `"failing": true`). Nothing is exported. The error message lists the failures and names
the renders. Successful builds include `verification.json` and the verification
result in `report.json`. The report records recipe, mesh, compiler and probe hashes.

### What is checked

1. **Geometry:** duplicates across parts, positive-area coplanar overlaps, and proper triangle
   intersections in the final quantized mesh. Shared boundaries are permitted. Existing
   topology reports still cover open/nonmanifold surfaces; use `--strict` when those should fail.
2. **Coverage and identity:** a temporary diagnostic mesh gives every exported triangle a unique
   RGB555 ID. It keeps vertex positions, winding, face order, double-sided and Gouraud flags;
   semi-transparent faces add nothing to it and are judged apart ([Semi-transparent
   faces](#semi-transparent-faces)). Palette-backed and textured faces are checked untextured: see
   [Palette-backed materials](#palette-backed-materials); faces with cutouts are judged per texel
   ([The Asset Checker and textures](#the-asset-checker-and-textures)). Dithering is disabled and no
   HUD is drawn. The real core renders the ID buffer; `mei-asset-probe` captures its projected
   integer vertices and 16.16 depths. One check cart is compiled per asset (per level of detail): it
   holds every camera's numbers in a table, the same literals a cart for one camera would have, and
   draws the camera whose index is in its `asset_view` global. The probe runs it once per camera,
   each time on a machine made fresh as `mei_create()` makes one, with the index written into RAM
   before the first frame, so each view's capture is the one a cart compiled for that camera alone
   gives. Of a view's numbers only `native_cpu_cycles` differs from such a cart's: 35 or 36 cycles
   more, for reading the table.
3. **Expected visibility:** a separate CPU rasterizer uses those projected vertices and Mei's
   exact integer top-left pixel-coverage rule, then selects the nearest triangle by reciprocal
   depth. Coverage is checked at every pixel, including triangle boundaries. Depth order is
   judged at every pixel the policy's `edge_margin` decides (below). Colors and lighting do not
   decide pass/fail; identically colored surfaces still produce distinct IDs.
4. **Ordering constraints:** overlapping covered triangles create far-before-near relationships.
   Reports include conflicts whose order reverses across the overlap and actual directed-cycle
   witnesses. Such cycles cannot be solved by finding a different simple draw order for those
   triangles. The graph is conservative: it includes surfaces hidden behind other surfaces.

A pass requires covered pixels, no geometry errors under the selected policy, zero
wrong-depth pixels, zero coverage discrepancies and no ordering cycles. Two triangles within
two normalized 16.16 depth units are treated as a depth tie; ties are counted explicitly.
This tolerance does not suppress geometric duplicates or coplanar-overlap errors.

**The edge margin.** `edge_margin` (pixels, default 1, the World Checker's `ordering.edge_margin`)
says where depth order is judged: at a pixel the nearest face covers at least that far inside its
outline, and only when it is nearer, by more than the depth tie, than every other face that comes
within that distance of the pixel (its plane extended there). The other covered pixels are
`undecided_pixels`. A thin face seen edge-on is less than two pixels wide and so wholly undecided,
and a pixel where two faces' outlines meet is decided by neither: the 1–3 pixel flips at such places
no longer fail an asset that the World Checker would pass in a level. What a margin can hide: a real
mis-sort confined to the margin (faces overlapping by less than about two pixels, the edges of thin
parts) is not reported, and inside the band it is not judged at all. The report says how much:
`undecided_wrong_pixels` counts the pixels within the margin where the drawn face is truly behind
the expected one, so `wrong_pixels` + `undecided_wrong_pixels` is the count at `edge_margin` 0, and
`tested_pixels` + `undecided_pixels` is every covered pixel. A pass needs covered pixels, not
decided ones: an asset no wider than about two pixels in every view (a thin pole at the fitted
scale) has its depth order judged nowhere, which its `tested_pixels` of 0 shows; check such an asset
with `scale: "world"` or a smaller `edge_margin` if its order matters. `edge_margin: 0` judges every
pixel, as before. Coverage errors are judged at every pixel whatever the margin, and the ordering
graph and its cycles take no margin. `verify --edge-margin N` sets it for one run.

**Faces in one bucket** (without the depth buffer; see [Depth mode](#depth-mode)). The ordering
table has 1,024 buckets over the camera's range, about 0.1
units each at `far` 100 and in a world's near pass. Faces whose average depths fall in one bucket
are not sorted among themselves: the face submitted first is drawn last, on top, even when it is
the farther ([WORLDPACK.md](WORLDPACK.md#faces-in-one-bucket); LANGUAGE.md says the same of keyed
faces). An asset's faces are submitted in the order the recipe produces them: its `nodes` in
order, each node's faces in the order its operation makes them, a group's children in order.
So when two faces of one asset lie closer in depth than a
bucket and overlap on screen (a sign on a wall, a stripe painted on a floor), the one that must
show is the one earlier in the recipe: put the sign's node before the wall's. The Asset Checker
judges the result (a depth difference above the tie tolerance drawn the wrong way is a wrong
pixel), so a recipe that relies on the rule is checked, not trusted. The rule holds only within
a bucket: from a camera at which the two faces' average depths fall in different buckets they
are sorted by depth, so the order cannot rescue faces that truly cross.

### Depth mode

An asset that a game draws with the depth buffer ([RENDERING.md](RENDERING.md)) says so in its
policy, and the checker judges it as the depth test draws it:

```json
"verification": {"required": true, "depth": true, "perspective": true}
```

(`verify --depth --perspective` for one run; `preview --depth --perspective` previews and checks so,
as in a depth-mode world; `depth_views` or `verify --depth-views N` sets how many views are judged,
below.) Both default to false, and an asset without them is
checked exactly as before (the same verdict, counts and views). A world recipe with
`"runtime": {"depth": true}` checks its assets so unless their policy says otherwise
([WORLDKIT-REFERENCE.md](WORLDKIT-REFERENCE.md#depth-mode)). With `depth`:

- The verification cart imports `depth.akr` and calls `render_depth(true)` (and
  `render_perspective(true)`) before drawing; coverage and the expected face come from the same
  native projected vertices as before.
- **Depth order is a regression check.** Two faces are a tie at a pixel unless the farther is
  more than **2 steps of the depth key** behind the nearer (2/4,096 of its depth; a step is at most
  1/4,096 of 1/*w*, and a tie goes to the later packet), so a wrong pixel is a fault of the depth
  test or the face loops, not of the asset: it should be 0. No allowance for vertex rounding is
  needed, as the reference rasterises from the console's own projected vertices. `edge_margin`
  applies as before.
- **Not failures:** `surface_intersection` (the depth test draws crossing faces right along their
  crossing) and ordering cycles (the graph is not built). The crossings are still counted, in
  `geometry.allowed` by part pair ([Reports and repairs](#reports-and-repairs)).
  **Still failures:** duplicate faces and coplanar overlaps, which fight in the depth buffer as
  they did in a bucket, coverage errors, and the budgets and levels of detail as before.
- **Duplicates and coplanar overlaps are geometry checks**, judged on the mesh without rendering
  (the depth test ties such faces, so no view could fail them: a planted coplanar overlap has 0
  wrong pixels in its views). The tolerances, on the 16.16-quantised mesh: a *duplicate* is a
  face with the same three vertex indices as an earlier one; a *coplanar overlap* is two faces
  whose unit normals are parallel (cross product below 10^-8), every vertex of each within 2^-18
  units of the other's plane, and whose intersection in that plane has an area above 2^-36 square
  units (sharing an edge or a corner is not an overlap). Faces a little apart (a sign 1 mm off a
  wall) are neither: they tie only from far enough away, which the depth key's precision
  ([RENDERING.md](RENDERING.md)) and the game's distances decide, not the asset.
- **T-junctions are reported** (`t_junction` in `geometry`, with both faces): a vertex within
  2^-16 units (one step of the 16.16 coordinates) of the inside of another face's edge, not a
  corner of that face. The two faces' edges are rasterised from different corners and can leave a
  crack of background pixels along the edge, which no view can catch: the reference draws the
  same crack. Not a failure (`street_utility_pole` in the garden has 4, its insulators standing on
  the cross-arm's edge); split the edge at the vertex. Without depth the audit does not look for
  them, so its findings are as before.
- **Fewer views are judged** (below): `depth_views`, default 16.
- The report adds `depth_mode`: the settings, `key_steps`, `key_tolerance` and `view_selection`.
- `render_depth(true)` brings perspective with it (`stdlib/depth.akr`), so `depth` without
  `perspective` draws as with both.

So the authoring rules made for the ordering table apply only without depth: splitting long
faces, keeping details clear of surfaces, removing crossing faces and buried parts for ordering's
sake, and recipe order ("a sign before its wall"). Measured with the default profile (144 views;
`coin` 360):

| Asset | Without depth: ok, wrong pixels, cyclic views | With depth: ok, wrong pixels | What still fails with depth |
|---|---|---|---|
| `kiosk` | yes, 0, 0 | yes, 0 | |
| `test_room`'s `coin` | yes, 0, 0 | yes, 0 | |
| `vessel` | no, 4,892, 144 | **yes**, 0 | |
| `robot` | no, 1,205, 140 | no, 0 | 8 coplanar overlaps |
| `cottage` | no, 28,514, 144 | no, 0 | 36 coplanar overlaps |
| `two_districts`' `torii` | no, 3,183, 132 | no, 0 | 10 coplanar overlaps |

(The table was measured judging all 144 views; judging the chosen views gives the same verdicts
and counts: `vessel` 18 views, `robot` 18, `cottage` 19, `kiosk` 16.)

**The views judged in depth mode.** Ordering-table mistakes depend on the exact camera, so without
depth every view of the sweep is judged. With depth what the views are for is coverage: that the
console draws every face, and every texel of a cutout face, where the reference expects it, and a
face's coverage can only be judged where it is drawn. Drawing a view is cheap (the probe runs the
one cart for every camera of the sweep, about 3 ms each); judging one is not (the reference
rasteriser, in Python, 10–50 ms). So every view of the sweep is drawn, and the reference judges
those that `tools/assetkit/views.py` chooses from what the console drew:

1. For each view of the sweep, the pixels of each face in its triangle-ID buffer and, for cutout
   faces, the texels they show (texture coordinates interpolated linearly from the projected
   corners: off by a texel here and there, enough to choose by).
2. A view *shows a face well* when it draws at least half the face's largest count over the sweep
   (a cutout face: 90 %).
3. A greedy cover, deterministic: take the view that draws the most faces and cutout texels no
   chosen view draws; on a tie the one showing well the most faces none shows well yet; then the
   most shown well only once; then the most pixels; then the earliest. It goes on until every face
   and cutout texel the sweep draws is drawn, and then up to `depth_views` views.
4. A face the console draws in no view could be one it fails to draw. For each such face that an
   estimate made without the console sees (points about 1.2 % of the bounding radius apart over
   the faces, projected into a 160 × 120 depth buffer; at least 4 pixels in some view), the view
   the estimate shows it best in is judged too.

So the judged views draw every face the 144 draw: `observed_faces` is the same as with every
view judged, and `view_selection` says so (`faces_drawn_by_sweep`, `faces_drawn_by_views`, the
faces shown well once and twice, the cutout texels, `suspect_faces`). The count goes above
`depth_views` only when the cover needs it: over the garden's 41 checked assets, the stall and
the kiosk (59 levels of detail; `coin`'s policy has 4 views), 16 views draw every face but in the
two viaducts (each of whose small rail posts shows in a few views only: 21 and 20 views) and the
stall (18, for its cutout texels); about 5,700 of the levels' 5,741 drawn faces are also shown
well. A judged view is the same row as in the full sweep (with its `sweep_index`).
`"depth_views": 144` (or `verify --depth-views 144`) judges every view, which reproduces the
earlier depth-mode report.

Planted faults, in depth mode with the 16 views (`tests/test_assetkit.py`, `CheckViewTests`): a
plate face the console does not draw (a *missing face*: 1,745 wrong pixels, the body behind it
showing, and it is a suspect face); a plate face drawn with one corner moved to another vertex (a
*crack*: 773 coverage errors); one byte of a fence's cutout mask cleared (a *cutout hole* where
the texture has none: 658 coverage errors); a *duplicate face* and a *coplanar overlap* (geometry
failures, 0 wrong pixels); a *T-junction* (reported). A crack or T-junction in the asset itself,
which the console and the reference draw alike, is not a rendering fault; a gap shows as open
edges in the topology report (`--strict` fails on them) and a T-junction as above.

**Time.** The garden's 41 assets that require the check (`carts/garden/world/assets/`, the city
block's, removed 2026-10-11; 57 levels of
detail), each checked on its own, two at a time, from cold (no cache), October 2026: in depth mode
339.7 s before the one cart and the view selection, 16.3 s after (20.8 times faster; the median
asset 24 times, `park_bench` 5.5 s to 0.18 s, `residential_car_park` 19.9 s to 1.6 s, `coin`, whose
policy has 4 views, 2.2 times); without depth, every view still judged, 305.2 s and 58.4 s (5.2
times, from the one cart alone). `kiosk`: 6.1 s and 0.30 s with depth, 5.3 s and 1.1 s without.
`stall`: 7.0 s and 0.66 s. The verdicts are the same in all of them; without depth the reports
are too, but for `native_cpu_cycles` (above) and the probe's hash. What a depth-mode check spends
now: the probe drawing the 144 views (about 3 ms each), the reference judging 16 (10–50 ms each),
the geometry audit and Python's start.

### Semi-transparent faces

Faces of a material with [`blend`](#semi-transparent-materials) hide nothing, and the checker
judges them so, with and without depth:

1. **They do not occlude.** In the ID buffer's mesh they stay semi-transparent (flag bit 3), in
   blend mode `add` with colour 0: the console draws them where it would (in their buckets, or
   after the opaque faces with the depth buffer), testing depth and writing none, and they change
   no pixel. The reference leaves them out. So the opaque faces are judged exactly as if the
   blended ones were absent: what is behind a pane of glass must be drawn, a blended face never
   counts as covering a pixel, and it takes part in no `wrong_order` finding and no ordering
   cycle. A console that drew them opaque fails (the glass would hide what the reference expects).
2. **Where they show is judged in a second buffer, the blended layer.** A second check cart draws
   the same cameras with every opaque face black (colour 0, still writing depth; a cutout face
   through its mask) and every blended face adding its own ID (1 to N in face order, 5 bits a
   channel). The reference expects at each pixel the sum, per channel and saturating at 31, of
   the IDs of the blended faces covering it that are nearer than every opaque face covering it.
   A pixel is judged when each blended face covering it is nearer, by more than the depth tie,
   than every opaque face covering the pixel or within `edge_margin` of it, or farther than the
   nearest one by more than the tie, and lies at least `edge_margin` inside its own outline; a
   pixel no blended face covers must stay black. The tie is the same as for opaque faces (2 steps
   of the depth key in depth mode, 2/65,536 units without). A judged pixel whose drawn sum differs
   is a wrong pixel, and any fails the asset. Blended cutout faces are judged per texel, as
   opaque ones are ([The Asset Checker and textures](#the-asset-checker-and-textures)).
3. **The geometry audit is unchanged**: duplicates and coplanar overlaps fail with a blended face
   as with an opaque one (a pane coplanar with a wall ties with it in the depth test, pixel by
   pixel), crossings fail without the depth buffer and are allowed with it, and `close_faces`
   warns as before.

In depth mode the blended layer finds faults of the console (a blended face not drawn, or drawn
where it is hidden): it should have no wrong pixel. Without the depth buffer it finds the
ordering table's mistakes: an opaque face drawn over a blended face in front of it, or a blended
face drawn over an opaque face in front of it. A red box inside a glass box (`blend: "half"`,
`tests/test_assetkit.py`, `BlendTests`) passes in depth mode, while without depth the ordering
table draws small faces of the box over the big glass faces in front of them: 598 wrong pixels in
16 of the 144 views.

**Not judged:** the order of blended faces among themselves (a sum does not depend on it), their
colours and the blending itself (the IDs say which faces were drawn, not how they mixed), and
pixels where the sums are ambiguous: two faces whose IDs add up to the same sum as another set,
or a channel saturating at 31, can hide a missing or extra face there.

In depth mode the views are chosen as before, the blended faces' pixels counted from the blended
layer where a pixel holds one face's ID alone (a sum is attributed to no face, or to a wrong one:
enough to choose by), so the judged views draw them too. The second cart costs a second compile
and probe run, for assets with blended faces only: Fall Line's sled (448 triangles, 50 of them
its canopy) checks in about 1.5 s, and its observed faces went from 351 to 437 when the canopy
became see-through (the pilot is judged through it).

The report adds, per view, `blend` (`tested_pixels`, `undecided_pixels`,
`undecided_wrong_pixels`, `wrong_pixels`, and `issues`: `blend_wrong` with the blended faces
expected to show there, those expected hidden behind an opaque face, the drawn and expected
values and a sample pixel; a failing view's image is `visibility_NNNN_blend.png`), the same
counts in `totals.blend`, and `blend` at the top: the blended faces, their modes, how many were
seen, and the scope. `observed_faces` counts the blended faces expected to show in some judged
view.

### Reports and repairs

A verification report begins with its verdict:

| Field | Meaning |
|---|---|
| `ok` | The verdict |
| `verdict` | One line: `PASS` or `FAIL`, the mode, how many problems, and how many geometry findings the mode allowed |
| `failures` | Every reason for a failure, one line each: each failing geometry code per part pair (largest first), wrong-depth pixels, coverage errors, ordering cycles, no covered pixels, and each level of detail's (`lod K …`). Empty when `ok` |
| `allowed` | The allowed geometry findings, one line per code and part pair (the 12 largest; `geometry.allowed` has all) |

`geometry` agrees with it: its `ok` is the geometry verdict under the policy, so a depth-mode
asset with only crossing parts has `geometry.ok` true. Its fields:

| Field | Meaning |
|---|---|
| `ok` | No failing finding under the policy |
| `counts` | Every code found, failing or allowed |
| `failing` | The failing codes, counted |
| `allowed_codes` | The codes the policy allows: `surface_intersection` and `t_junction` in depth mode; every code with `geometry: "warn"`; none otherwise |
| `summary` | One line per part pair and failing code, as in `failures` |
| `findings` | **Every** failing finding, in full, ordered by part pair (no limit) |
| `allowed` | The allowed findings, per code and part pair: `count` and up to 3 `examples` |

So the findings that fail are never crowded out by allowed ones. The cottage example in depth
mode (`verify examples/assets/cottage.asset.json --depth`):

```json
"ok": false,
"verdict": "FAIL (depth mode): 7 problems, see failures; 284 findings allowed in depth mode (surface_intersection, t_junction)",
"failures": [
  "geometry: coplanar_overlap: 8 between front_windows/window/group_window/frame and front_windows/window/group_window/pane (faces 80/93, 80/95, 82/93, 82/95, ...) at (0.58, 0.94, -0.88)",
  "geometry: coplanar_overlap: 8 between side_windows/group_window/frame and side_windows/group_window/pane (faces 176/189, 176/191, 178/189, 178/191, ...) at (1.08, 0.96, -0.46)",
  "geometry: coplanar_overlap: 6 between front_windows/window/group_window/frame and walls (faces 12/129, 12/131, 14/81, 14/83, ...) at (-0.45, 0.82, -0.80)",
  "geometry: coplanar_overlap: 6 between side_windows/group_window/frame and walls (faces 20/177, 20/179, 20/225, 20/227, ...) at (1.00, 1.08, -0.37)",
  "geometry: coplanar_overlap: 4 between foundation and walls (faces 8/18, 8/19, 9/18, 9/19) at (-0.02, 0.20, -0.29)",
  "geometry: coplanar_overlap: 2 between door and foundation (faces 8/56, 8/57) at (-0.15, 0.20, -0.57)",
  "geometry: coplanar_overlap: 2 between door and walls (faces 18/56, 18/57) at (0.21, 0.20, -0.55)"
],
"allowed": [
  "surface_intersection: 40 between front_windows/window/group_window/cross_h and front_windows/window/group_window/cross_v",
  …
```

Face pairs are `a/b`, zero-based faces of the exported mesh. A coplanar finding's message says
whether the two faces are back to back (one part standing on another) or facing the same way.

Each camera has numeric counts and witnesses such as:

```json
{
  "code": "wrong_order",
  "drawn": {"face": 2, "part": "body", "material": "default"},
  "expected": {"face": 14, "part": "plate", "material": "default"},
  "pixels": 1248,
  "sample_pixel": [163, 88],
  "max_depth_error": 0.1483
}
```

Face numbers are zero-based indices in the exported triangle mesh; part names map back to
recipe nodes/prototypes. Reports give the exact camera, affected faces, depth error, cycle
or crossing witnesses, and repair guidance. The optional PNGs show **native IDs | expected
IDs | discrepancies in red**. Their false colors identify triangles; they are not shaded art.
Up to 12 failing views get images; all views retain numerical results. Per-view conflict lists
are bounded (32 per view); failing geometry findings are not.

Follow the evidence rather than moving arbitrary vertices until a screenshot looks good:

- Coplanar faces of two parts (one standing flush on or against another): sink one 1–2 cm into
  the other, or open the hidden face ([Authoring rules](ASSETKIT.md#authoring-rules-depth-mode)).
- Duplicate/coplanar faces on one surface: remove the covered faces or tile materials on a
  single surface.
- Intersections: split/trim surfaces at the connection and remove buried faces. Prefer one
  connected surface for an attached badge, socket or backpack.
- Wrong order without intersections: split the named long faces or subdivide the local region,
  preserving shared boundaries. Rerun the exact failed camera and then the whole sweep.
- Ordering cycles/depth reversals: split the involved geometry; simply rearranging face order
  cannot satisfy all recorded constraints.

Repairs are not applied automatically: geometry changes can alter the intended design and
consume the mesh budget. The checker supplies explicit findings for an agent to repair and
recheck; it never silently changes materials or loosens tolerances to obtain a pass.

### Camera scope and limits

Defaults are 24 yaw samples starting at -0.65 radians, three pitches and two distances: 144
views. Distances multiply the fitted camera distance (2.6 times the normalized bounding-sphere
radius). The original mesh is centered and uniformly fitted as in preview. FOV is Mei's default
60°, near depth is 0.1, and far depth defaults to 100 to exercise the normal ordering-table
precision rather than only a tightly fitted preview range. Match `far` to the intended cart.

Two policy settings narrow the cameras to how the asset is seen in a game:

- `yaw_range_degrees: [from, to]` samples `yaw_steps` yaws evenly from `from` to `to` (both
  included) instead of the whole circle. A camera at yaw 0 stands on the asset's −Z side looking
  toward +Z, at 90 on the −X side. Use it for an asset seen from one side only, such as one
  mounted on a wall: a fire escape on a building's +Z face is checked with yaws around 180, not
  from inside the building. Pitches are already a list (`pitches`, −1.4 to 1.4 radians).
- `scale: "world"` draws the mesh at its own size instead of fitting it into about 2 units; the
  camera stands at `distances` × 2.6 × its own bounding-sphere radius. With the default fit, the
  ordering table's 1,024 buckets over `far` are 0.1 fitted units, which for a 30-unit asset is a
  1.5-unit step, much coarser than the 0.094 units a world's near pass sorts in (96 units over
  1,024 buckets). At world scale the faces sort in the same 0.1-unit buckets as in a world with
  `far` 100. Use it for large assets (a steel frame, a car park); set `far` to the world's near
  range.

`verify` takes them as `--yaw-range FROM,TO` and `--scale world`.

For an exploratory check:

```sh
python3 tools/mei_assets.py verify model.asset.json -o build/model-check \
  --yaw-steps 48 --pitches=-0.6,0,0.6 --distances=1,2 --far 100
```

Overrides on `verify` are exploratory; edit the recipe to change an enforced build policy.
`--geometry warn` records geometric defects as warnings, but visibility and cycles still must
pass. Use it explicitly for diagnosis, not to label intersecting geometry as clean.

The gate currently covers static meshes (untextured, palette-backed or textured faces,
cutouts per texel in depth mode; semi-transparent faces as [above](#semi-transparent-faces)) and
sampled fitted cameras. Near-plane or
guard-band clipping is rejected as unsupported, not treated as a pass. Animation, arbitrary
camera translations/FOVs, other ordering-table ranges, exact real-number visibility before
projection, fully enclosed internal components and unobserved faces are not certified.
The report states coverage and unobserved-face counts. It is a strong finite regression gate,
not a proof for every possible camera or pose. Assets drawn with the depth buffer are checked
in [depth mode](#depth-mode), where every camera of the sweep is drawn but only the views that
draw every face (16 by default, `depth_views`) are judged.

## Cookbook

Small recipes for common pieces, each checked with `inspect` (no flush contacts, no close faces)
and `preview` with a required depth-mode policy (`"verification": {"required": true, "depth":
true, "perspective": true}`), which they pass (the sign and the poster with texel grids in place of
their images). Nodes and materials only; wrap them in a recipe.

**A sign with a plain back.** A box whose `back` side (−Z, facing the front camera) has the sign's
material, textured with `fit` (the whole texture over that side), the other sides plain: one
closed part, nothing flush ([Face materials](#face-materials-and-decals)). The post is thinner
than the board and sunk 10 cm into it, its front 4 cm behind the board's (not 1 cm: [close
faces](ASSETKIT.md#authoring-rules-depth-mode)), its top opened. 22 triangles.

```json
"materials": {
  "wood": {"color": "#6b4a3a"},
  "face": {"color": "#e8d8b0", "texture": {"image": "art/sign.png", "bits": 8, "projection": "fit"}}
},
"nodes": [
  {"id": "board", "op": "box", "size": [1.2, 0.6, 0.12], "material": "wood", "faces": {"back": "face"},
   "transform": {"translate": [0, 2.2, 0]}},
  {"id": "post", "op": "box", "size": [0.08, 2.0, 0.04], "material": "wood", "open": ["top"],
   "transform": {"translate": [0, 1.0, 0]}}
]
```

**A decal on a wall.** A poster baked into the wall's front (the box's `back`): the wall's face is
cut around the rectangle, which becomes two faces of the poster's material, in the wall's plane
([Decals](#face-materials-and-decals)). Nothing is flush or proud, so it passes with and without
the depth buffer. `at` is the poster's centre from the wall's centre, right and up as the front
camera sees it. 18 triangles: the wall's 10 and the decal's 8.

```json
"materials": {
  "wall": {"color": "#c8b8a0"},
  "poster": {"color": "#d04030", "texture": {"image": "art/poster.png", "projection": "fit"}}
},
"nodes": [
  {"id": "wall", "op": "box", "size": [4, 3, 0.2], "material": "wall", "open": ["bottom"],
   "decals": [{"id": "poster", "face": "back", "material": "poster", "size": [0.8, 1.2], "at": [0.8, 0.1]}],
   "transform": {"translate": [0, 1.5, 0]}}
]
```

**A drum with a lid and a label.** A cylinder's caps in one material and a label on the lid: 52
triangles (44 and the decal's 8).

```json
"materials": {
  "drum": {"color": "#406040"}, "lid": {"color": "#a0a8b0"}, "label": {"color": "#e0d0a0"}
},
"nodes": [
  {"id": "drum", "op": "cylinder", "radius": 0.3, "height": 0.9, "segments": 12, "material": "drum",
   "faces": {"top": "lid", "bottom": "lid"},
   "decals": [{"id": "label", "face": "top", "material": "label", "size": [0.24, 0.12], "at": [0, -0.1]}],
   "transform": {"translate": [0, 0.45, 0]}}
]
```

On a cap, `at`'s right and up are as the top view shows the top cap (+X right, +Z up), so
`[0, -0.1]` sits the label 10 cm toward the front camera.

**Stairs.** One `extrude` of the stairs' side outline (x the run, y the rise), turned so the
extrusion runs along X and the flight climbs away from the front camera (`rotate` [0, −90, 0]
turns the outline's +X to +Z). One closed part, no steps to stack or sink. Four steps of 18 × 28
cm, 1.2 m wide: 36 triangles (4*n* − 4 for the 10 points).

```json
{"id": "flight", "op": "extrude", "material": "stone", "depth": 1.2,
 "points": [[0, 0], [0, 0.18], [0.28, 0.18], [0.28, 0.36], [0.56, 0.36], [0.56, 0.54],
            [0.84, 0.54], [0.84, 0.72], [1.12, 0.72], [1.12, 0]],
 "transform": {"rotate": [0, -90, 0]}}
```

**A disc texture on a rotated cylinder** (a clock, a wheel, a round sign). `disc` maps in the
primitive's own coordinates, before its transform, so it stays on the caps however the cylinder
is turned. To face the front camera, turn the cylinder's +Y to −Z with `rotate` [−90, 0, 0]: the
top cap then faces −Z and reads the right way round (u along +X, v down); [90, 0, 0] would show
the bottom cap, mirrored. The sides take the disc's outermost texels, so give the picture a
rim of one colour. 60 triangles with 16 segments.

```json
"materials": {
  "dial": {"color": "#f0ead8", "texture": {"projection": "disc", "colors": ["#000000", "#303030", "#f0ead8", "#c03020"],
           "texels": ["11111111", "12222221", "12232221", "12232221", "12233321", "12222221", "12222221", "11111111"]}}
},
"nodes": [
  {"id": "face", "op": "cylinder", "radius": 0.3, "height": 0.06, "segments": 16, "material": "dial",
   "transform": {"rotate": [-90, 0, 0], "translate": [0, 1.8, 0]}}
]
```

## Outputs and game integration

For an asset named `stool`, `build` produces:

| File | Purpose |
|---|---|
| `stool.bin` | Native Mei mesh, with deduplicated fixed-point vertices and triangle faces |
| `stool.akr` | `embed ASSET_STOOL: Mesh = "stool.bin"` |
| `stool.asset.json` | Copy of the editable source recipe |
| `stool.obj`, `stool.mtl` | Geometry/material exchange with external modeling tools |
| `stool.model.json` | Explicit geometry in Mei Modeler's project format |
| `preview.akr` | Standalone camera-fitted preview cart source; with a [look](#the-look-background-and-ground)'s ground it embeds `preview_ground.bin` and `preview_ground_tint.bin`, written beside it |
| `report.json` | Build costs, hashes, per-part diagnostics and optional native render results |
| `stool.lod1.bin`, … | With `lod`: each coarser level's native mesh, embedded in `stool.akr` as `ASSET_STOOL_LOD1`, … |
| `stool.materials.json` | Material manifest: palette entries, classes, tags and face ranges (below) |
| `stool.slotK.tex`, `stool.tpal`, `stool.frames` | With textures: the texels of each slot used, the texture palettes and animation frames ([Outputs and the manifest](#outputs-and-the-manifest)) |

Recipes with palette-backed materials also get:

| File | Purpose |
|---|---|
| `stool.pal` | Default colours of the palettes used, 15-bit, 16 per palette (unused indices 0) |
| `stool.swatch` | The 8-byte swatch row: texel `u` holds index `u` |

Recipes using none of the material extensions build byte-identical files to earlier versions of
the kit; the manifest, written for every build so that a packer reads one shape of data for every
asset, is the only addition (for such a recipe it lists each material's colour, triangles and
faces, with no palette and no tags).

Import the `.akr` from your cart and draw normally:

```
import "stool.akr"

fn draw() {
    cls(rgb(24, 28, 36))
    camera(vec3(0.0, 1.0, -4.0), 0.0)
    mesh_at(ASSET_STOOL, vec3(0.0, 0.0, 0.0), 0.0)
}
```

With palette-backed materials the `.akr` also embeds the palette and swatch, defines the colour
indices and a loader, and the cart calls the loader once:

```
embed ASSET_KIOSK_PALETTE: u16 = "kiosk.pal"
embed ASSET_KIOSK_SWATCH: u8 = "kiosk.swatch"
const ASSET_KIOSK_COLOUR = 0           // first colour of the first palette (palette × 16)
const ASSET_KIOSK_SURFACE = 1          // surface entries: colours 1..4
const ASSET_KIOSK_SURFACE_COUNT = 4
const ASSET_KIOSK_EMISSIVE = 5         // emissive entries: colours 5..6
const ASSET_KIOSK_EMISSIVE_COUNT = 2
fn asset_kiosk_load() { … }            // swatch into VRAM, then load_palette(…)
```

```
import "kiosk.akr"
embed NIGHT_SIGNS: u16 = "night_signs.pal"   // two 15-bit colours: the emissives at night
var night: fixed = 0.0                       // 0 day .. 1.0 night, set by the game

fn init() { asset_kiosk_load() }

fn update() {
    // Blend only the signs; surface entries keep their colours.
    palette_lerp(ASSET_KIOSK_EMISSIVE, &ASSET_KIOSK_PALETTE[ASSET_KIOSK_EMISSIVE - ASSET_KIOSK_COLOUR],
                 NIGHT_SIGNS, ASSET_KIOSK_EMISSIVE_COUNT, night)
}
```

A class's range runs from its first to its last entry and may include index 0 of a later
palette when it spans palettes; blending that unused colour is harmless.

The **material manifest** is for tools that pack several assets into shared palettes or derive
game data. For the kiosk (abridged):

```json
{
  "format": "mei-asset-materials", "version": 1, "name": "kiosk",
  "swatch": {"file": "kiosk.swatch", "slot": 14, "row": 0, "texels": 16, "meaning": "…"},
  "palette": {"file": "kiosk.pal", "first_colour": 0, "colours": 16, "palettes": [0]},
  "entries": [
    {"colour": 1, "palette": 0, "index": 1, "class": "surface", "color": "#3d4f66",
     "rgb15": 12583, "materials": ["fascia"]},
    {"colour": 5, "palette": 0, "index": 5, "class": "emissive", "color": "#ff3fa4",
     "rgb15": 20735, "materials": ["neon"]}
  ],
  "classes": {"surface": {"first_colour": 1, "colours": 4, "entries": [1, 2, 3, 4]},
              "emissive": {"first_colour": 5, "colours": 2, "entries": [5, 6]}},
  "materials": {"door": {"color": "#6b4a3a", "class": "surface", "palette_colour": null,
                         "tag": "door", "triangles": 4, "faces": [[10, 14]]}},
  "tags": {"door": [[10, 14]], "window": [[32, 34]], "roof": [[80, 88]], "floor": [[88, 96]]}
}
```

`colour` is the global palette colour index (`palette × 16 + index`). Face ranges are half-open
`[start, end)` indices into the exported mesh's faces. A material with
[`blend`](#semi-transparent-materials) has `"blend"` too (`"half"`, `"add"`, `"sub"` or
`"quarter"`), so its ranges are the mesh's semi-transparent faces; Fall Line's sled:
`"glass": {"color": "#38b8e8", "class": "surface", "palette_colour": null, "tag": "glass",
"triangles": 50, "faces": [[138, 188]], "blend": "half"}`. `pack`'s `NAME.pack.json` gives each
asset its `materials` and `tags` in this shape (with `palette_colour` where the pack put the
entry), and an asset with levels of detail `level_materials`, one per level from 1, so a packer
or a cart reads which faces are which from the manifest, not from the kit's internals. In
`stool.bin`, a palette-backed face has
flag bit 1 set, texture byte `slot | 16`, palette byte `palette`, and every texture coordinate
`index | row << 8`; that is all a packer needs to move entries. `assetkit.compiler.relocate(binary,
colours, slot, row)` does it: it maps old colour indices to new ones and moves the swatch,
rejecting index 0 and any textured face that is not a swatch face. The manifest's `entries`
then give the default colours to place in the shared palette.

OBJ import preserves geometry and winding, including negative vertex indices. It intentionally
does not import material files, UVs, supplied normals or textures, and returns a warning about
that conversion. Assign recipe materials afterward. The Modeler exchange file carries base
colors and its global lighting toggle; it does not preserve procedural operations, smooth
normals or a custom light direction when re-exported through that editor. Keep the recipe as
the source of truth. The editor may impose additional object/coordinate limits on large recipes.

Version 1 makes static meshes with solid colours, baked or palette-backed,
[textures](#textures) and [semi-transparent materials](#semi-transparent-materials). Boolean
solids, skeletal animation, morph animation and automatic LOD generation are not included. The
Animation Kit ([ANIMKIT.md](ANIMKIT.md)) animates rigs of rigid parts built from Asset Kit
recipes; the repository has no tool for the others.

### Viewing an asset elsewhere: `export`

`export` writes the asset as one self-contained glTF 2.0 file for an ordinary 3D viewer (a
browser page with three.js, Blender, a model viewer), looking as Mei draws it:

```sh
python3 tools/mei_assets.py export examples/assets/stall.asset.json -o build/export      # stall.glb
python3 tools/mei_assets.py export examples/assets/stall.asset.json -o build/export --format gltf
```

`--format glb` (the default) writes `NAME.glb`; `--format gltf` writes `NAME.gltf` with its buffer
embedded as a data URI. The command needs only the standard library (and Pillow where the recipe's
textures read images, as for `build`), runs no verification and writes nothing else. Its JSON
result gives the file, its triangles, vertices, primitives and images, `hidden_faces`
(palette-backed faces on a swatch texel 0, which Mei never draws; left out), `dropped_frames` and
`lod_levels_not_exported`. The code is
`tools/assetkit/gltf.py`.

The file is made from what the console reads, not from the recipe: the native mesh exactly as
`build` writes it, and the texture area and palettes as the asset's loader fills them, each texel
looked up as the GPU does. So it carries:

| What Mei draws | In the glTF |
|---|---|
| Geometry after modifiers, prototypes, fixed-point rounding and texture splits | `POSITION`, one primitive per material |
| Baked lighting (vertex colours; a textured or palette-backed face's tint) | `COLOR_0`, converted from the display's sRGB to linear; every material is `KHR_materials_unlit` |
| Palette-backed colours | `COLOR_0`: the swatch colour times the tint |
| Textures (4- and 8-bit, through their palettes) | RGBA PNGs, sampled `NEAREST` both ways, no mipmaps |
| Texture windows (repeating tiles) | the tile, `REPEAT`, UV = texel coordinate / tile size |
| Tiles drawn once | the tile and its gutter, `CLAMP_TO_EDGE` |
| Cutouts (texel 0) | alpha 0, `alphaMode: MASK` |
| `double_sided` | `doubleSided: true` |
| `blend: "half"` | `alphaMode: BLEND`, base colour alpha 0.5; `add`, `sub` and `quarter` have no glTF equivalent and are exported opaque (a note says so). `extras.mei.blend` names the mode |
| Emissive (never shaded) | unshaded `COLOR_0`; also `emissiveFactor` (and `emissiveTexture`) for viewers without the unlit extension |

Not carried: animated textures beyond frame 0 (the result's `dropped_frames` and the material's
`extras.mei.frames` say which), levels of detail beyond level 0, run-time palette changes, Mei's
screen-space colour interpolation, affine texturing where perspective is off, ordering-table sorting
without the depth buffer, dithering and the 15-bit framebuffer. A viewer draws with a depth buffer
and perspective-correct texturing, so the closest Mei pictures are `preview --depth --perspective`.

**Handedness.** Mei's world is left-handed: `camera_look` at yaw 0 looks along +Z with +X to the
right of the screen. glTF is right-handed with +Y up and +Z toward the viewer. `export` negates Z,
which keeps every point where a viewer sees it: the kit's front (−Z) faces glTF's +Z, the default
front of a glTF asset, and the native face order is then glTF's counter-clockwise front. The
`.obj` exchange file is written in the kit's coordinates unchanged, so a right-handed tool shows
it mirrored left to right.

Compared with the kit's own `preview --depth --perspective` images (the six views drawn in
three.js with `MeshBasicMaterial` and vertex colours, the same cameras and a 60° field of view),
the stall, robot, kiosk, cottage and vessel differ by 3.4–4.2 levels of 255 on average per
channel, the HUD text included; 98–99 % of pixels are within 24 levels. Textures sit in the same
places, the same way round.

## Tests

```sh
make test-assets
```

This builds the native runner, compiler and diagnostic probe, and checks geometry, winding,
transformations, quantization, schema failures, deterministic exports, OBJ import, output
preservation on failure, and all five examples rendered from six angles by Mei. It pins the build
outputs of legacy recipes byte for byte, checks palette entry assignment, the vertical bake under
rotation, the manifest and `relocate`, and renders a palette-backed asset in the emulator while
rewriting a surface entry and blending an emissive one with `palette_lerp`. For textures it checks
every pattern (and that its divisions are checked), texel grids and `clear`, quantisation (exact
when colours fit, index 0 never used), 8-bit textures, images, grid and named sheets and animations
(with Pillow), the error without Pillow, each projection's orientation, `offset`, `rotate` and
`flip`, hand UVs, splitting without T-junctions, the 7-window limit, the native face bytes and
tints, levels of detail sharing level 0's textures, the packer's duplicates, window-aligned origins,
reserved swatch block, gutters, shared palettes and overflow errors, `pack` and `build`'s files, and
draws texels and a packed pair in depth and perspective mode in the emulator. For `export` it checks
the glTF's structure (buffer views, accessor counts and bounds, indices, unlit materials, nearest
samplers, decodable PNGs), that its colours are the native vertex colours, that texels read back
through the PNGs and UVs are the texels the faces sample (repeating and drawn once, holes as alpha
0), that nothing is mirrored (+X stays +X, the front faces +Z, outward counter-clockwise winding),
and the stall's `.glb` and `.gltf` from the command line. With NumPy it also checks identical-color
occlusion, crossing-depth cycles, exact native coverage, palette-backed faces in the gate, the depth
policy (a plate on a body and crossing faces pass, coplanar faces still fail), required-policy
enforcement, textured faces judged as solid faces, cutout coverage judged per texel (and that
judging it by the outline fails), preservation of prior artifacts on failed verification, that the
one check cart draws each camera as a cart of its own did, that depth mode's 16 views draw every
face the 144 do and are rows of the full sweep, the planted faults of [Depth mode](#depth-mode), and
`preview --depth`. For agents' use it checks that failing findings are reported in full and first
with hundreds of allowed crossings beside them (`FindingsTests`), that the verdict and the geometry
block agree (`VerdictTests`), `inspect`'s flush contacts, the tool paths (options, `--build-dir`,
`MEIC`/`RUN`/ `PROBE`, `B`) and their error, camera parsing and close-ups, camera views' sizes and
costs (`CameraViewTests`), failing renders kept and marked (`FailedPreviewTests`), the authoring
rules' conventions on renders (`ConventionTests`), and (`FeedbackTests`) `build` and `preview`
stopping before rendering on flush contacts with a fix naming the part, direction and distance,
close parallel faces as a warning in `inspect` and `verify`, `inspect`'s texture windows, its full
report over budget, its mirror and below-ground warnings, texture splits that no longer collapse and
the error when one does, the planarity error's numbers, node ids in errors, and box sides named by
axis. `FaceMaterialTests` checks `faces` on every primitive that takes it (sides by name and axis,
no added triangles, the errors, instances keeping them, texture windows counted); `DecalTests` that
each decal adds 8 triangles and 4 vertices and keeps its part closed, its corners and texture
coordinates, `rotate`, no flush contacts or T-junctions (with NumPy), the errors, `mesh` polygons
and modifiers' copies, `--part` framing a decal, and (with NumPy and the native tools) that a baked
decal passes the Asset Checker with and without the depth buffer where a quad 3.5 cm proud fails
without it. `LookTests` checks the look's options and files (found above the recipe, overridden by
the options, Fall Line's), that a preview without a look is unchanged, the ground's tiles and tint,
the eye-level view's framing of a 12 m pylon, and the `stripes` axis and lighting `direction`
conventions; `LookRenderTests` renders a post sunk 1 m into a white ground under a sky gradient and
finds the sky, the ground, the post above it and the part below it tinted; `SummaryTests` that
findings carry their positions, that allowed findings collapse to counts per kind and pair, the
summaries of `preview` and `verify` (under 25 lines, failures with parts and positions, textures and
VRAM at 0) and Fall Line's pine previewed on its snow. `BlendTests` checks `blend`: each mode's flag
and blend byte (on plain, palette-backed and textured faces), the material manifest's and the pack's
face ranges, the `.mtl` and glTF, and (with NumPy and the native tools) that the checker judges a
core through its glass, fails a console drawing the glass opaque or leaving out a glass face, finds
the ordering table's mistakes around the glass without the depth buffer, judges a blended cutout per
texel, and that `preview` draws the glass blended. It also runs as part of `make test` when Python
is available. Pure Python tests can run independently; native render tests skip if the binaries are
absent:

```sh
python3 -m unittest discover -s tests -p test_assetkit.py -v
```

Example recipes: [`robot`](../examples/assets/robot.asset.json),
[`vessel`](../examples/assets/vessel.asset.json), [`cottage`](../examples/assets/cottage.asset.json),
[`kiosk`](../examples/assets/kiosk.asset.json) (palette-backed and emissive materials, tags,
vertical lighting and a required verification policy), [`stall`](../examples/assets/stall.asset.json)
(textures of every kind, cutouts, an animation, depth mode).
