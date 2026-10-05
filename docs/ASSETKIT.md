# Mei Asset Kit

A command-line 3D asset tool designed for AI agents. An editable JSON recipe describes
named parts and modeling operations. The tool builds native Mei meshes, validates their
actual fixed-point geometry, reports costs and topology per part, and checks actual triangle
visibility through Mei's compiler and GPU. Preview images help assess appearance; a numerical
verification gate decides whether geometry and visibility pass.

Modeling and ordinary builds use Python 3.10+ without third-party packages; textures read from
PNG images or sheets need Pillow ([Textures](#textures)). Visibility
verification additionally requires NumPy and `meic` / `mei-asset-probe`; `make` builds the
native tools. Preview rendering uses `meic` / `mei-headless`. No GUI, model service or network
is involved in these checks. The visibility verification gate (`verify`) is called the **Asset
Checker**. The kit's code is `tools/assetkit/`; what it shares with the World Kit (errors, JSON
input, schema validation, vectors, the compiler and runner wrappers, images and staged outputs)
is in `tools/kitcore/`.

## Agent workflow

```sh
# Discover the exact supported input contract.
python3 tools/mei_assets.py schema

# Start from a working recipe. Alternatives: vessel, cottage, kiosk (palette materials),
# stall (textures; init copies its sheet beside the recipe).
python3 tools/mei_assets.py init /tmp/robot.asset.json --example robot

# Edit the JSON, preserving meaningful node IDs.
# Check bounds, topology, counts and per-part costs before rendering.
python3 tools/mei_assets.py inspect /tmp/robot.asset.json

# Build the native tools if necessary.
make build/meic build/mei-headless build/mei-asset-probe

# Numerically check geometry and triangle visibility. Nonzero exit means failure.
python3 tools/mei_assets.py verify /tmp/robot.asset.json -o build/robot-check

# Build and render the actual exported mesh from six angles.
python3 tools/mei_assets.py preview /tmp/robot.asset.json -o build/assets/robot
```

Open `build/assets/robot/contact.png`, then adjust the recipe and rerun. The contact sheet
contains isometric, front, right, back, top and rear-quarter views. Individual PNGs and
GPU CSVs are also saved. `report.json` includes vertex/triangle counts, mesh bytes, bounds,
recipe/mesh hashes, topology warnings and CPU/GPU statistics for each view.

For an agent building a game:

1. Establish the intended size in world units, facing direction, silhouette and triangle budget.
2. Block out the silhouette with named primitives, extrusions or lofts. Keep repeated parts in
   `prototypes` and use instances. Give sibling nodes distinct IDs.
3. Run `inspect`; use the per-part report to find expensive or malformed geometry.
4. Run `verify`. Repair the named geometry and face-order conflicts; rerun until it passes.
   Make verification mandatory in the recipe before accepting the asset. Existing modeling
   examples may fail this stronger check: the robot still has intersecting shoulder/cuff
   components that its earlier material-color checks did not detect.
5. Use `preview` to assess silhouette and style. Export with the mandatory gate enabled.
6. Import the generated Akari file into the cart. Verify the asset in its intended camera and
   scene too: the preview's statistics measure an isolated asset, not its cost in every scene.

The CLI prints JSON on stdout for both successes and failures and exits 0 on success or 1 on
failure. `--help` prints human-readable help. Recipe errors contain a JSON Pointer `path`
and an actionable `message`. Commands accepting a recipe also accept `-` to read stdin.

## Commands

| Command | Result |
|---|---|
| `schema` | Full JSON Schema, including supported operations and field bounds |
| `init FILE [--example robot\|vessel\|cottage\|kiosk\|stall]` | Editable starter (with the images it reads, beside it); refuses to overwrite unless `--force` |
| `validate FILE [--strict]` | Schema, reference, geometry, fixed-point and budget checks |
| `inspect FILE [--strict]` | Same checks, with full bounds and per-part report |
| `verify FILE [-o DIR]` | Geometry checks plus native triangle-ID visibility and ordering-graph checks |
| `build FILE -o DIR [--verify] [--preview] [--strict] [--depth] [--perspective]` | Native and exchange artifacts; optional or recipe-mandated verification gate |
| `preview FILE -o DIR [--verify] [--strict] [--depth] [--perspective]` | Build plus six native renders and contact sheet |
| `import-obj FILE -o RECIPE [--name NAME] [--force]` | Geometry-only OBJ import into an explicit `mesh` recipe |
| `pack FILE... -o DIR [--name NAME] [--slots 14-0] [--palette 0] [--palette8 14]` | Several assets (or one) for a cart without a world: shared texture slots and palettes, one loader ([Placement](#placement-build-and-pack)) |
| `export FILE -o DIR [--format glb\|gltf]` | One glTF 2.0 file for ordinary 3D viewers, drawn as Mei draws it ([export](#viewing-an-asset-elsewhere-export)) |

`--strict` fails on topology warnings, useful for closed props. Omit it for intentionally open
surfaces. Build/preview accept `--compiler PATH` and `--runner PATH` for other Mei builds.
Verification accepts `--compiler PATH` and `--probe PATH`. `--depth` and `--perspective` on build and
preview say the asset is drawn with the depth buffer and perspective texturing, as in a world whose
`runtime` says so: the preview cart draws so (`preview.akr` and the six views), and the Asset
Checker runs in [depth mode](#depth-mode) where the recipe's policy does not set `depth` or
`perspective` itself. Without them an untextured asset previews as before, whatever its world.
Use a dedicated generated-output directory: builds replace their own filenames there.
Validation, serialization and optional rendering finish in a staging directory before outputs
are replaced; failed geometry checks or renders leave the previous build's files intact.
Do not use the recipe's own directory as the output directory if its name would collide with
the generated recipe copy. Obsolete files from earlier differently named builds are not removed.

## Recipe contract

```json
{
  "format": "mei-asset",
  "version": 1,
  "name": "stool",
  "budget": {"vertices": 256, "triangles": 200},
  "materials": {"wood": {"color": "#b98962"}},
  "nodes": [
    {"id": "seat", "op": "cylinder", "radius": 0.5, "height": 0.12,
     "segments": 10, "material": "wood", "transform": {"translate": [0, 0.8, 0]}},
    {"id": "legs", "op": "group", "children": [
      {"id": "leg", "op": "box", "size": [0.1, 0.74, 0.1], "material": "wood",
       "transform": {"translate": [0.28, 0.37, 0]}}
    ], "modifiers": [{"op": "radial", "count": 3}]}
  ]
}
```

Names use lowercase letters, digits and underscores, beginning with a letter (up to 48
characters). Unknown properties, duplicate JSON keys, booleans in numeric fields, nonfinite
numbers, missing references and prototype cycles are errors. Use `schema` as the authoritative
machine-readable field reference. No expressions, code execution or random generation occur
inside recipes; identical recipes produce identical native binaries.

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
`verification-failed/`. Successful builds include `verification.json` and the verification
result in `report.json`. The report records recipe, mesh, compiler and probe hashes.

### What is checked

1. **Geometry:** duplicates across parts, positive-area coplanar overlaps, and proper triangle
   intersections in the final quantized mesh. Shared boundaries are permitted. Existing
   topology reports still cover open/nonmanifold surfaces; use `--strict` when those should fail.
2. **Coverage and identity:** a temporary diagnostic mesh gives every exported triangle a
   unique RGB555 ID. It keeps vertex positions, winding, face order, double-sided and Gouraud
   flags. Palette-backed and textured faces are checked untextured: see [Palette-backed
   materials](#palette-backed-materials); faces with cutouts are judged per texel ([The Asset
   Checker and textures](#the-asset-checker-and-textures)). Dithering is disabled and no HUD is drawn. The real
   core renders the ID buffer; `mei-asset-probe` captures its projected integer vertices and
   16.16 depths. One check cart is compiled per asset (per level of detail): it holds every
   camera's numbers in a table, the same literals a cart for one camera would have, and draws the
   camera whose index is in its `asset_view` global. The probe runs it once per camera, each time
   on a machine made fresh as `mei_create()` makes one, with the index written into RAM before the
   first frame, so each view's capture is the one a cart compiled for that camera alone gives. Of
   a view's numbers only `native_cpu_cycles` differs from such a cart's: 35 or 36 cycles more, for
   reading the table.
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
and a pixel where two faces' outlines meet is decided by neither: the 1–3 pixel flips at such
places no longer fail an asset that the World Checker would pass in a level. What a margin can
hide: a real mis-sort confined to the margin (faces overlapping by less than about two pixels,
the edges of thin parts) is not reported, and inside the band it is not judged at all. The report
says how much: `undecided_wrong_pixels` counts the pixels within the margin where the drawn face
is truly behind the expected one, so `wrong_pixels` + `undecided_wrong_pixels` is the count at
`edge_margin` 0, and `tested_pixels` + `undecided_pixels` is every covered pixel. A pass needs
covered pixels, not decided ones: an asset no wider than about two pixels in every view (a thin
pole at the fitted scale) has its depth order judged nowhere, which its `tested_pixels` of 0 shows;
check such an asset with `scale: "world"` or a smaller `edge_margin` if its order matters. `edge_margin: 0`
judges every pixel, as before. Coverage errors are judged at every pixel whatever the margin, and
the ordering graph and its cycles take no margin. `verify --edge-margin N` sets it for one run.

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
checked exactly as before, its report byte for byte the same. A world recipe with
`"runtime": {"depth": true}` checks its assets so unless their policy says otherwise
([WORLDKIT.md](WORLDKIT.md#depth-mode)). With `depth`:

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
  crossing) and ordering cycles (the graph is not built). They are still listed in `geometry`.
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

**Time.** The garden's 41 assets that require the check (`carts/garden/world/assets/`, 57 levels of
detail), each checked on its own, two at a time, from cold (no cache), October 2026: in depth mode
339.7 s before the one cart and the view selection, 16.3 s after (20.8 times faster; the median
asset 24 times, `park_bench` 5.5 s to 0.18 s, `residential_car_park` 19.9 s to 1.6 s, `coin`, whose
policy has 4 views, 2.2 times); without depth, every view still judged, 305.2 s and 58.4 s (5.2
times, from the one cart alone). `kiosk`: 6.1 s and 0.30 s with depth, 5.3 s and 1.1 s without.
`stall`: 7.0 s and 0.66 s. The verdicts are the same in all of them; without depth the reports
are too, but for `native_cpu_cycles` (above) and the probe's hash. What a depth-mode check spends
now: the probe drawing the 144 views (about 3 ms each), the reference judging 16 (10–50 ms each),
the geometry audit and Python's start.

### Reports and repairs

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
Up to 12 failing views get images; all views retain numerical results. Geometry findings and
per-view conflict lists are bounded, with geometry truncation stated explicitly.

Follow the evidence rather than moving arbitrary vertices until a screenshot looks good:

- Duplicate/coplanar faces: remove the covered faces or tile materials on a single surface.
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

The gate currently covers opaque static meshes (untextured, palette-backed or textured faces,
cutouts per texel in depth mode) and sampled fitted cameras. Near-plane or
guard-band clipping is rejected as unsupported, not treated as a pass. Animation, arbitrary
camera translations/FOVs, other ordering-table ranges, exact real-number visibility before
projection, fully enclosed internal components and unobserved faces are not certified.
The report states coverage and unobserved-face counts. It is a strong finite regression gate,
not a proof for every possible camera or pose. Assets drawn with the depth buffer are checked
in [depth mode](#depth-mode), where every camera of the sweep is drawn but only the views that
draw every face (16 by default, `depth_views`) are judged.

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
| `box` | `size: [x,y,z]` | Centered at the origin; `open`: sides to leave out, from `top` (+Y), `bottom` (−Y), `left` (−X), `right` (+X), `back` (−Z), `front` (+Z) |
| `sphere` | `radius` | `rings: 6`, `segments: 12`; scale for an ellipsoid |
| `cylinder` | `radius`, `height` | `segments: 12`, `caps: true`; centered, along Y |
| `cone` | `radius`, `height` | Same as cylinder; tip at +height/2 |
| `extrude` | `points: [[x,y],…]`, `depth` | Simple concave or convex XY polygon, extruded symmetrically along Z; either outline winding |
| `lathe` | `profile: [[radius,y],…]` | `segments: 12`, `caps: true`; rotate a silhouette around Y; heights strictly increase; zero-radius tips only at endpoints |
| `loft` | `sections: [{"y":…, "points": [[x,z],…]},…]` | `caps: true`; increasing Y; same point count, correspondence and winding in every section |
| `mesh` | `vertices: [[x,y,z],…]`, `faces: [[index,…],…]` | Zero-based indices; planar simple polygons are triangulated; outward right-handed winding; optional `face_materials` gives one material name per source polygon |
| `group` | `children: [node,…]` | Combined geometry; material inherited by children lacking an explicit material |
| `instance` | `ref` | Reference to a node in the root `prototypes` object; explicit instance material overrides the whole referenced component |

A box's `open` sides are left out with the vertices only they use: `["bottom"]` for a building
or a block standing on the ground, whose underside nobody sees and which would otherwise sort
against the ground under it; `["bottom", "left", "right", "back", "front"]` for a flat ground
tile, its top alone (a box of any height, moved down by half of it, puts the top at 0). At least
one side stays; each is named once. An open box is an open surface, so it gets the
`open_surface` topology warning (and fails `--strict`), as any intentionally open mesh does.

Extrusion supports concave outlines through ear-clipping triangulation. Outline holes,
self-crossings, repeated endpoint vertices, and duplicate/collinear adjacent points are not
accepted. Loft correspondence matters: use the same corner order at every height. Nonplanar
polygons in explicit meshes must be supplied as triangles. Coordinates are rounded to Mei's
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

Materials have `color: "#RRGGBB"` and optional `smooth: false`, `double_sided: false`.
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
head uses this approach, retaining a closed mesh with shared boundary vertices.

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
`palette_layout` places the swatch (texels u 0–15 of `row` in texture `slot`, 0–14; default slot
14, row 0; 8 bytes of VRAM) and the first 4-bit palette (`first`, 0–254; default 0).

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
budget"). Measured with the kiosk example's previews, the same mesh built once palette-backed
and once with plain vertex colours: in the isometric view the mesh's GPU cycles (excluding the
`cls` and the HUD text) go from about 18,050 to 29,800, +65 %: the 94 triangles cost the same and
the 12,600 filled pixels cost double. That is 0.6 % of the 2,000,000-cycle frame budget (1.2 %
of the 1,000,000 it was) for an asset covering a sixth of the screen. CPU cost rises about 7 % (textured packets are longer).
Mix both kinds freely: only palette-backed materials pay for textures, so leave materials that
never change colour unbacked (the kiosk's door is).

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
palette entries, so one palette and one relocation serve them all. A level with no fewer
triangles than the one before is a warning (`lod_not_simpler`). The report's `lod` lists each
level's distance, triangles and vertices, with `cull` and `band`. `build` writes each level as
`NAME.lodK.bin` (K from 1) and embeds it in `NAME.akr` as `ASSET_NAME_LODK`. `verify` checks
every level as an asset of its own with the same policy (pictures under `lodK/`), lists the
levels' results under `lod`, and fails if any level fails. Choosing the level is the consumer's:
the World Kit stores the distances in the pack and the reader chooses per placement
([WORLDKIT.md](WORLDKIT.md#levels-of-detail)).

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
scales and verify in the actual scene.

## Outputs and game integration

For an asset named `stool`, `build` produces:

| File | Purpose |
|---|---|
| `stool.bin` | Native Mei mesh, with deduplicated fixed-point vertices and triangle faces |
| `stool.akr` | `embed ASSET_STOOL: Mesh = "stool.bin"` |
| `stool.asset.json` | Copy of the editable source recipe |
| `stool.obj`, `stool.mtl` | Geometry/material exchange with external modeling tools |
| `stool.model.json` | Explicit geometry in Mei Modeler's project format |
| `preview.akr` | Standalone camera-fitted preview cart source |
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
`[start, end)` indices into the exported mesh's faces. In `stool.bin`, a palette-backed face has
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

Version 1 makes static meshes with solid colours, baked or palette-backed, and
[textures](#textures). Boolean solids, skeletal animation, morph animation and automatic LOD
generation are not included, and the repository has no other tool for them.

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

## Textures

Decided by the owner on 2026-10-04 (see [Decisions](#decisions)) and built: a material can carry
a texture, drawn through palettes of its own. Textures are most useful with the opt-in depth
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
no textures ([`export`](#viewing-an-asset-elsewhere-export) does). A textured face's vertex colour is the baked shade as a tint, 128 for unchanged, as
for palette-backed faces.

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
material's projection's (a `fit` material's hand UVs stay within 0–1).

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

A texture drawn once (`fit`, `disc`) is placed plainly with a one-texel **gutter** to its right
and below that repeats its last column and row, because a face's coordinate can reach its width
exactly at a corner. It is any size up to 255 × 255.

### Cutouts

A texture with holes (an image's transparent pixels, or the `clear` colour of a pattern or texel
grid) draws nothing there and writes no depth: fences, grilles, railings, foliage, round signs.
Cutouts draw correctly only with the depth buffer, so they are allowed only in assets whose
policy says `"depth": true` (`"verification": {"required": true, "depth": true, "perspective":
true}`); any other asset using one fails with an error at its texture. Draw such an asset with
`render_depth(true)`. Semi-transparency stays per face (glass), not per texel.

### Animated textures

`{"sheet": "neon", "frames": ["a", "b", "c"], "ticks": 8}` is an animated texture: each frame a
cell of the sheet, all the same size and with their holes in the same places, each shown 8 ticks,
looping. Meshes are read in place from ROM, so frames are not chosen by rewriting faces: the
texture has one tile in VRAM (frame 0 is loaded), and its frames are kept in ROM in the tile's
own layout (`NAME.frames`), ready to be copied into the tile when the frame changes. All frames
share one palette (they are quantised together). Every placement of the asset animates in step.
`stdlib/texanim.akr` copies a frame when it changes (`tex_frame_at`, `tex_frame_copy`, with the
constants in `NAME.akr`: [LANGUAGE.md](LANGUAGE.md#animated-textures-texanimakr-and-world-backdrops-wpbackdropakr));
a world's animations are advanced by `wp_animate()`. Palette cycling (`palette_rotate`, `palette_lerp`) is the
cheaper alternative for flicker and glow.

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

It compiles each recipe, packs all their tiles once into the slots given (a range `10-14`, which
is also their order of preference, or a list `14,12`; default `14-0`), gives the palette-backed
materials of each asset consecutive 4-bit palettes from `--palette` with one shared swatch at row
0 of the first slot, then the 4-bit textures' palettes, and 8-bit palettes from `--palette8`
down. It writes each mesh for that placement (`NAME.bin`, `NAME.lodK.bin`), the slots' texels
(`street.slotK.tex`), the palettes (`street.tpal` for textures, `street.pal` and
`street.swatch` for palette-backed materials), animation frames (`street.frames`), one
`street.akr` that embeds every mesh and defines `street_load()`, and the manifest
`street.pack.json`. It does not run the Asset Checker; `build` or `verify` each asset for that.

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
- `list`: per textured material, its tile (`tile` is the content key that removes duplicates),
  where it is (`slot`, `x`, `y` in texels, `gutter`), its window halfword (`null` when drawn
  once), its palette (`palette`: a 4-bit palette 0–254 or an 8-bit one 0–14; `first_colour` its
  colour 0) and which entry each colour has (`indices`), and the faces (half-open ranges of the
  exported faces).
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

[`stall`](../examples/assets/stall.asset.json) is a noodle stall with every kind of texture:
`brick` (box), `planks` (planar, from above), `grain` (cylindrical, turned 90°), `stripes` on the
awning, a 32 × 16 8-bit sign from a named cell of
[`art/stall_sheet.png`](../examples/assets/art/stall_sheet.png) (`fit`), an emblem with
transparent corners on a disc (`disc`, a cutout), lattice side screens (`fit`, a cutout through
`clear`) and an animated lantern (two frames, cylindrical, emissive). It requires the Asset
Checker in depth mode. Numbers (`build`): 144 triangles, 116 vertices, 8 tiles in slots 13 (4-bit)
and 14 (8-bit), 1,507 bytes of texels (2,176 on the 8-texel grid), 4-bit palettes 0–1 and 8-bit
palette 14, 5 windows, no split faces. Its check: 18 of the 144 views judged, 0 wrong pixels, 0 coverage errors,
0.7 s (14.3 s judging every view, one cart each). Preview views: 99,000–107,300 GPU and 22,200–25,700 CPU cycles. Packed with the kiosk and
drawn by a cart in depth and perspective mode (four views, from the stall a third of the screen
to a close view filling it, the kiosk beside it): 109,154–200,638 GPU and 30,686–34,855 CPU
cycles a frame. `tests/test_assetkit.py` packs and draws the same pair.

The sheet is authored art (drawn once with Pillow and committed; no generator rewrites it).

### For a region packer (the World Kit)

Built (2026-10-04): the World Kit packs a region's textures with these pieces
([WORLDKIT.md](WORLDKIT.md#textures-per-region), `tools/worldkit/textures.py`). What it uses:

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

## Decisions

The project owner's decisions about the kit (2026-10-03), besides those described above:

- **The boundary with the World Kit is "could you place it twice?"** Anything reusable (a
  staircase, a vending machine, a length of guard rail) is an asset. Anything that exists once,
  at one place in a world, belongs to the world recipe ([WORLDKIT.md](WORLDKIT.md)), including
  terrain. The World Kit refers to asset recipes by name; this kit never learns that worlds
  exist. Both import `tools/kitcore/`. A single tool that both models and builds levels was
  rejected.
- **Day and night through palettes:** palette-backed materials, with emissive ones on entries of
  their own ([Palette-backed materials](#palette-backed-materials)).
- **Shading** is baked, time-neutral and, for placed assets, rotation-neutral (`"mode":
  "vertical"`). Every wall then has the same shade, which is accepted: colour, textures and the
  palette's tint separate surfaces. If a real street looks flat, the fallback is a variation of
  a few percent by facing, baked in the asset's own frame. Baking a sun direction per placement
  and lighting at draw time were both rejected.
- **Textures** (revised 2026-10-04): procedural patterns and recipe texel grids for repeats, and
  PNG images and sheets now for detailed art; 4-bit by default, 8-bit per texture; UVs by
  projection or `fit`, hand UVs only in `mesh` nodes; cutouts in depth-mode assets; animated
  textures from sheet frames; the World Kit packs VRAM per region
  ([Textures](#textures)). Built as decided, with these details settled in the building: the
  projections work in each primitive's own coordinates; repeating textures are 8–128 texels
  (power-of-two) tiles, at most 7 an asset (a mesh's windows); textures drawn once carry a
  one-texel gutter; `build` places one asset's textures itself and `pack` places a set's.
- **Examples.** Of the five examples, `kiosk` and `stall` (in depth mode) pass the Asset
  Checker (and require it).
  `robot`, `vessel` and `cottage` predate the gate and fail its geometry check with surface
  intersections (`verify`, October 2026); they remain as modelling examples. Three more recipes
  made while the kit was developed (`ion_cruise`, `sky_castle` and `clockwork_kraken`) also fail
  it and were left out until fixed, as was `tools/mei_modeler.py`.

## Tests

```sh
make test-assets
```

This builds the native runner, compiler and diagnostic probe, and checks geometry, winding, transformations, quantization,
schema failures, deterministic exports, OBJ import, output preservation on failure, and all
five examples rendered from six angles by Mei. It pins the build outputs of legacy recipes byte
for byte, checks palette entry assignment, the vertical bake under rotation, the manifest and
`relocate`, and renders a palette-backed asset in the emulator while rewriting a surface entry
and blending an emissive one with `palette_lerp`. For textures it checks every pattern (and
that its divisions are checked), texel grids and `clear`, quantisation (exact when colours fit,
index 0 never used), 8-bit textures, images, grid and named sheets and animations (with Pillow),
the error without Pillow, each projection's orientation, `offset`, `rotate` and `flip`, hand
UVs, splitting without T-junctions, the 7-window limit, the native face bytes and tints, levels
of detail sharing level 0's textures, the packer's duplicates, window-aligned origins, reserved
swatch block, gutters, shared palettes and overflow errors, `pack` and `build`'s files, and
draws texels and a packed pair in depth and perspective mode in the emulator. For `export` it
checks the glTF's structure (buffer views, accessor counts and bounds, indices, unlit materials,
nearest samplers, decodable PNGs), that its colours are the native vertex colours, that texels
read back through the PNGs and UVs are the texels the faces sample (repeating and drawn once,
holes as alpha 0), that nothing is mirrored (+X stays +X, the front faces +Z, outward
counter-clockwise winding), and the stall's `.glb` and `.gltf` from the command line. With NumPy it also checks identical-color
occlusion, crossing-depth cycles, exact native coverage, palette-backed faces in the gate,
the depth policy (a plate on a body and crossing faces pass, coplanar faces still fail),
required-policy enforcement, textured faces judged as solid faces, cutout coverage judged per
texel (and that judging it by the outline fails),
preservation of prior artifacts on failed verification, that the one check cart draws each
camera as a cart of its own did, that depth mode's 16 views draw every face the 144 do and are
rows of the full sweep, the planted faults of [Depth mode](#depth-mode), and `preview --depth`. It also runs as part of `make test` when
Python is available. Pure Python tests can run independently; native render tests skip if
the binaries are absent:

```sh
python3 -m unittest discover -s tests -p test_assetkit.py -v
```

Example recipes: [`robot`](../examples/assets/robot.asset.json),
[`vessel`](../examples/assets/vessel.asset.json), [`cottage`](../examples/assets/cottage.asset.json),
[`kiosk`](../examples/assets/kiosk.asset.json) (palette-backed and emissive materials, tags,
vertical lighting and a required verification policy), [`stall`](../examples/assets/stall.asset.json)
(textures of every kind, cutouts, an animation, depth mode).
