# Mei Asset Kit

A command-line 3D asset tool designed for AI agents. An editable JSON recipe describes
named parts and modeling operations. The tool builds native Mei meshes, validates their
actual fixed-point geometry, reports costs and topology per part, and checks actual triangle
visibility through Mei's compiler and GPU. Preview images help assess appearance; a numerical
verification gate decides whether geometry and visibility pass.

Modeling and ordinary builds use Python 3.10+ without third-party packages. Visibility
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

# Start from a working recipe. Alternatives: vessel, cottage, kiosk (palette materials).
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
| `init FILE [--example robot\|vessel\|cottage\|kiosk]` | Editable starter; refuses to overwrite unless `--force` |
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
   flags. Palette-backed faces are checked untextured: see [Palette-backed
   materials](#palette-backed-materials). Dithering is disabled and no HUD is drawn. The real
   core renders the ID buffer; `mei-asset-probe` captures its projected integer vertices and
   16.16 depths.
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

(`verify --depth --perspective` for one run.) Both default to false, and an asset without them is
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
- The report adds `depth_mode`: the settings, `key_steps` and `key_tolerance`.
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

**Time.** Without and with depth: `kiosk` 5.5 s and 5.6 s, `coin` 11.5 s and 13.1 s, `robot`
21.0 s and 13.2 s (no ordering graph). Most of it is `meic` compiling one cart per view (2.9 s of
`kiosk`'s 5.5; 3.5 s with depth, which compiles `depth.akr` and its face loops too) and about a
fifth the probe. The easy win, not taken: compile the cart once and let the probe write each
view's camera into RAM, as the World Checker's cart reads its views from embedded data.

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

The gate currently covers opaque static meshes (untextured or palette-backed faces) and sampled
fitted cameras. Near-plane or
guard-band clipping is rejected as unsupported, not treated as a pass. Animation, arbitrary
camera translations/FOVs, other ordering-table ranges, exact real-number visibility before
projection, fully enclosed internal components and unobserved faces are not certified.
The report states coverage and unobserved-face counts. It is a strong finite regression gate,
not a proof for every possible camera or pose. Assets drawn with the depth buffer are checked
in [depth mode](#depth-mode).

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
`mesh()` clips, culls and sorts textured faces like untextured ones. Any other textured face is
rejected by the gate.

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

Version 1 focuses on static meshes with solid colours, baked or palette-backed. Texture and UV
authoring (see the proposal below), Boolean solids, skeletal animation, morph animation and
automatic LOD generation are not included, and the repository has no other tool for them.

## Textures (decided, not built)

Decided by the owner on 2026-10-04, revising the earlier proposal now that the Prism Engine has
an opt-in depth buffer and perspective-correct texturing ([RENDERING.md](RENDERING.md)): large
textured faces no longer warp, and texel 0 can be a hole that the depth test handles correctly.
Nothing below is built yet.

**Sources.** A textured material takes its texels from one of:

- a **pattern**: a named procedural pattern (brick, tile, planks, wood grain and the like), a few
  parameters each, generated deterministically by the kit; for cheap repeating surfaces;
- **texels** written in the recipe: rows of hex digits naming the material's `colors` (about
  16×16; trims, icons, simple signs);
- an **image**: a PNG file beside the recipe, or one cell of a **sheet** (below); for anything
  detailed (signage, liveries, faces, panels).

```json
"brick":  {"color": "#a0522d", "class": "surface", "tag": "wall",
           "texture": {"pattern": "brick", "colors": ["#a0522d", "#d8d0c0"],
                       "params": {"courses": 4, "bond": 0.5}, "size": 16,
                       "projection": "box", "scale": [0.5, 0.25]}},
"ramen":  {"color": "#202020", "class": "emissive",
           "texture": {"sheet": "signs", "cell": "ramen", "projection": "fit"}},
"livery": {"color": "#e0e0d8",
           "texture": {"image": "art/car_side.png", "bits": 8, "projection": "fit"}}
```

**Sheets.** A sheet is one PNG holding many textures, declared once per recipe: either a uniform
grid (`"sheets": {"signs": {"image": "art/signs.png", "grid": [32, 16]}}`, cells named by
`[column, row]`) or named rectangles in a sidecar `NAME.sheet.json`. A sheet is only an authoring
container: the kit slices it, and every cell it uses is packed like any other texture. The
sheet's layout never becomes the VRAM layout.

**Animated textures.** A texture may be a sequence of frames, written as cells of a sheet:
`{"sheet": "neon", "frames": ["a", "b", "c"], "ticks": 8}` (each frame shown for 8 ticks,
looping). Meshes are read in place from ROM, so frames are not selected by rewriting the faces:
the packer gives the texture one tile in VRAM and keeps its frames in ROM, and a stdlib helper
copies the current frame into that tile when it changes (a 16×16 4-bit frame is 128 bytes).
Every placement of the asset animates in step. Palette cycling (shifting the colours of a
texture's palette entries) is the cheaper alternative for flicker and glow, and stays available.

**Bit depth.** Textures are **4-bit by default** (one 16-colour palette per face, at most 15
colours, since index 0 is reserved) so that every texture works with region palette variants for
day and night. A texture may ask for **`"bits": 8`** (255 colours, twice the VRAM); its 256-entry
palette is the kit's own, and a region's night variant applies to it as a single tint
(`multiply`) rather than per-colour choices. The kit quantises images to the depth asked for,
or keeps them exact when they already fit, and reports each texture's VRAM cost.

**Placement (UVs).** UVs are generated per primitive, by `projection`:

| Projection | Mapping |
|---|---|
| `planar` | along an axis (`axis`), `scale` world units per repeat |
| `box` | by each face's dominant normal axis |
| `cylindrical` | around Y |
| `disc` | radially in a plane (`axis`): wheel faces, dials, round signs |
| `fit` | the texture exactly covers each face it is on (its extent in the face's plane): a sign on a panel, a livery on a car side |

Every projection takes `offset`, `rotate` (0, 90, 180, 270) and `flip` (mirroring, so the two
sides of a car can share one texture). Hand-written per-vertex
UVs exist only in explicit `mesh` nodes, the escape hatch for shapes nothing else fits.

**Cutouts.** In assets drawn with the depth buffer (policy `"depth": true`), a texture may have
holes: transparent pixels of an image (alpha below one half) or a `"clear"` colour in texels
become texel 0, which draws nothing and writes no depth (fences, railings, grilles, foliage). An
asset without depth mode may not use cutouts. For faces with cutouts the Asset Checker renders the
real texels and judges coverage per texel; other textured faces are judged as solid faces, as
swatch faces are today. Semi-transparency stays per face (glass), not per texel.

**Who owns VRAM.** An asset declares the textures it uses; it does not place them. The **World
Kit packs each region's textures**: it removes duplicates (one brick tile however many assets use
it), packs tiles into texture slots at window-aligned origins, writes window tables and rewrites
the faces' texture bytes, and fails the build with a report when a region's textures do not fit.
A cart that uses assets without a world packs them with an Asset Kit command (`mei_assets.py
pack`). Repeats rely on texture windows ([DECISIONS.md](DECISIONS.md#texture-windows)): a tile
is stored once and repeats inside its window; a face spanning more than 255 texels of a pattern
is split.

**Cost.** Textured pixels cost the GPU twice a flat one, as palette-backed faces already do;
perspective correction adds a little per triangle and per 16 pixels (RENDERING.md). Patterns and
images add VRAM, not GPU time.

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
  ([Textures](#textures-decided-not-built)).
- **Examples.** Of the four examples, only `kiosk` passes the Asset Checker (and requires it).
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
four examples rendered from six angles by Mei. It pins the build outputs of legacy recipes byte
for byte, checks palette entry assignment, the vertical bake under rotation, the manifest and
`relocate`, and renders a palette-backed asset in the emulator while rewriting a surface entry
and blending an emissive one with `palette_lerp`. With NumPy it also checks identical-color
occlusion, crossing-depth cycles, exact native coverage, palette-backed faces in the gate,
the depth policy (a plate on a body and crossing faces pass, coplanar faces still fail),
required-policy enforcement and
preservation of prior artifacts on failed verification. It also runs as part of `make test` when
Python is available. Pure Python tests can run independently; native render tests skip if
the binaries are absent:

```sh
python3 -m unittest discover -s tests -p test_assetkit.py -v
```

Example recipes: [`robot`](../examples/assets/robot.asset.json),
[`vessel`](../examples/assets/vessel.asset.json), [`cottage`](../examples/assets/cottage.asset.json),
[`kiosk`](../examples/assets/kiosk.asset.json) (palette-backed and emissive materials, tags,
vertical lighting and a required verification policy).
