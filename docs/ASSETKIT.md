# Mei Asset Kit

A command-line 3D asset tool designed for AI agents. An editable JSON recipe describes
named parts and modeling operations. The tool builds native Mei meshes, validates their
actual fixed-point geometry, reports costs and topology per part, and checks actual triangle
visibility through Mei's compiler and GPU. Preview images help assess appearance; a numerical
verification gate decides whether geometry and visibility pass.

Modeling and ordinary builds use Python 3.10+ without third-party packages. Visibility
verification additionally requires NumPy and `meic` / `mei-asset-probe`; `make` builds the
native tools. Preview rendering uses `meic` / `mei-headless`. No GUI, model service or network
is involved in these checks.

## Agent workflow

```sh
# Discover the exact supported input contract.
python3 tools/mei_assets.py schema

# Start from a working recipe. Alternatives: vessel, cottage.
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
| `init FILE [--example robot\|vessel\|cottage]` | Editable starter; refuses to overwrite unless `--force` |
| `validate FILE [--strict]` | Schema, reference, geometry, fixed-point and budget checks |
| `inspect FILE [--strict]` | Same checks, with full bounds and per-part report |
| `verify FILE [-o DIR]` | Geometry checks plus native triangle-ID visibility and ordering-graph checks |
| `build FILE -o DIR [--verify] [--preview] [--strict]` | Native and exchange artifacts; optional or recipe-mandated verification gate |
| `preview FILE -o DIR [--verify] [--strict]` | Build plus six native renders and contact sheet |
| `import-obj FILE -o RECIPE [--name NAME] [--force]` | Geometry-only OBJ import into an explicit `mesh` recipe |

`--strict` fails on topology warnings, useful for closed props. Omit it for intentionally open
surfaces. Build/preview accept `--compiler PATH` and `--runner PATH` for other Mei builds.
Verification accepts `--compiler PATH` and `--probe PATH`.
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
   flags. Dithering is disabled and no HUD is drawn. The real core renders the ID buffer;
   `mei-asset-probe` captures its projected integer vertices and 16.16 depths.
3. **Expected visibility:** a separate CPU rasterizer uses those projected vertices and Mei's
   exact integer top-left pixel-coverage rule, then selects the nearest triangle by reciprocal
   depth. Every covered pixel is checked, including triangle boundaries. Colors and lighting
   do not decide pass/fail; identically colored surfaces still produce distinct IDs.
4. **Ordering constraints:** overlapping covered triangles create far-before-near relationships.
   Reports include conflicts whose order reverses across the overlap and actual directed-cycle
   witnesses. Such cycles cannot be solved by finding a different simple draw order for those
   triangles. The graph is conservative: it includes surfaces hidden behind other surfaces.

A pass requires nonzero tested coverage, no geometry errors under the selected policy, zero
wrong-depth pixels, zero coverage discrepancies and no ordering cycles. Two triangles within
two normalized 16.16 depth units are treated as a depth tie; ties are counted explicitly.
This tolerance does not suppress geometric duplicates or coplanar-overlap errors.

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

For an exploratory check:

```sh
python3 tools/mei_assets.py verify model.asset.json -o build/model-check \
  --yaw-steps 48 --pitches=-0.6,0,0.6 --distances=1,2 --far 100
```

Overrides on `verify` are exploratory; edit the recipe to change an enforced build policy.
`--geometry warn` records geometric defects as warnings, but visibility and cycles still must
pass. Use it explicitly for diagnosis, not to label intersecting geometry as clean.

The gate currently covers opaque static meshes and sampled fitted cameras. Near-plane or
guard-band clipping is rejected as unsupported, not treated as a pass. Animation, arbitrary
camera translations/FOVs, other ordering-table ranges, exact real-number visibility before
projection, fully enclosed internal components and unobserved faces are not certified.
The report states coverage and unobserved-face counts. It is a strong finite regression gate,
not a proof for every possible camera or pose. No runtime depth buffer is added to Mei.

### Coordinates and transforms

Y is up. Distances are Mei world units and angles are degrees. The examples face -Z, which
is the preview's front camera; assets may use another facing convention if the cart needs it.
This is independent of Tsumiki's usual +Z character convention.

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
| `box` | `size: [x,y,z]` | Centered at the origin |
| `sphere` | `radius` | `rings: 6`, `segments: 12`; scale for an ellipsoid |
| `cylinder` | `radius`, `height` | `segments: 12`, `caps: true`; centered, along Y |
| `cone` | `radius`, `height` | Same as cylinder; tip at +height/2 |
| `extrude` | `points: [[x,y],…]`, `depth` | Simple concave or convex XY polygon, extruded symmetrically along Z; either outline winding |
| `lathe` | `profile: [[radius,y],…]` | `segments: 12`, `caps: true`; rotate a silhouette around Y; heights strictly increase; zero-radius tips only at endpoints |
| `loft` | `sections: [{"y":…, "points": [[x,z],…]},…]` | `caps: true`; increasing Y; same point count, correspondence and winding in every section |
| `mesh` | `vertices: [[x,y,z],…]`, `faces: [[index,…],…]` | Zero-based indices; planar simple polygons are triangulated; outward right-handed winding; optional `face_materials` gives one material name per source polygon |
| `group` | `children: [node,…]` | Combined geometry; material inherited by children lacking an explicit material |
| `instance` | `ref` | Reference to a node in the root `prototypes` object; explicit instance material overrides the whole referenced component |

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

Root `lighting` accepts `direction: [-0.4,0.85,-0.35]`, `ambient: 0.45` and `bake: true`.
Lighting is baked into face/vertex colors at export. Set `bake: false` for unlit colors.
Double-sided faces render their single baked color from either side.

Use `mesh.face_materials` for adjacent colored regions on one continuous surface, such as
a robot's visor and eyes. Each entry names a material for the corresponding source polygon;
all triangles produced from that polygon retain the material. This avoids overlapping colored
panels that can cut through one another under Mei's triangle depth sorting. The robot example's
head uses this approach, retaining a closed mesh with shared boundary vertices.

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

There is no depth buffer in Mei. Large overlapping triangles and details close to a surface
can obscure one another even when the mesh is topologically valid. Subdivide selected large
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

Import the `.akr` from your cart and draw normally:

```
import "stool.akr"

fn draw() {
    cls(rgb(24, 28, 36))
    camera(vec3(0.0, 1.0, -4.0), 0.0)
    mesh_at(ASSET_STOOL, vec3(0.0, 0.0, 0.0), 0.0)
}
```

OBJ import preserves geometry and winding, including negative vertex indices. It intentionally
does not import material files, UVs, supplied normals or textures, and returns a warning about
that conversion. Assign recipe materials afterward. The Modeler exchange file carries base
colors and its global lighting toggle; it does not preserve procedural operations, smooth
normals or a custom light direction when re-exported through that editor. Keep the recipe as
the source of truth. The editor may impose additional object/coordinate limits on large recipes.

Version 1 focuses on static colored meshes. Texture-atlas/UV authoring, Boolean solids,
skeletal animation, morph animation and automatic LOD generation are not included. Existing
Tsumiki tools remain available for texture cells, rigid rigs, animation clips and morphs.

## Tests

```sh
make test-assets
```

This builds the native runner, compiler and diagnostic probe, and checks geometry, winding, transformations, quantization,
schema failures, deterministic exports, OBJ import, output preservation on failure, and all
three examples rendered from six angles by Mei. With NumPy it also checks identical-color
occlusion, crossing-depth cycles, exact native coverage, required-policy enforcement and
preservation of prior artifacts on failed verification. It also runs as part of `make test` when
Python is available. Pure Python tests can run independently; native render tests skip if
the binaries are absent:

```sh
python3 -m unittest discover -s tests -p test_assetkit.py -v
```

Example recipes: [`robot`](../examples/assets/robot.asset.json),
[`vessel`](../examples/assets/vessel.asset.json), [`cottage`](../examples/assets/cottage.asset.json).
