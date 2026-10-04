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

The gate currently covers opaque static meshes (untextured or palette-backed faces) and sampled
fitted cameras. Near-plane or
guard-band clipping is rejected as unsupported, not treated as a pass. Animation, arbitrary
camera translations/FOVs, other ordering-table ranges, exact real-number visibility before
projection, fully enclosed internal components and unobserved faces are not certified.
The report states coverage and unobserved-face counts. It is a strong finite regression gate,
not a proof for every possible camera or pose. No runtime depth buffer is added to Mei.

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
the 12,600 filled pixels cost double. That is 1.2 % of the 1,000,000-cycle frame budget for an
asset covering a sixth of the screen. CPU cost rises about 7 % (textured packets are longer).
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

## Textures (proposal)

Not built. The owner's chosen direction: **named procedural patterns** (brick, tile, planks,
wood grain…, a few parameters each, generated deterministically by the kit) and **small texel
grids written in the recipe** as rows of palette indices (about 16×16, for trims, icons and
simple signs), with **UVs always automatic per primitive**: planar, box or cylindrical
projection with a scale, never hand-placed coordinates. Image files come later, for signage.

**Recipe sketch.** A material gains an optional `texture`; its colours are palette entries
exactly as for palette-backed materials, so `class` and `tag` apply unchanged:

```json
"brick": {"color": "#a0522d", "class": "surface", "tag": "wall",
  "texture": {"pattern": "brick", "colors": ["#a0522d", "#d8d0c0"],
              "params": {"courses": 4, "bond": 0.5, "mortar": 1},
              "size": 16, "projection": "box", "scale": [0.5, 0.25]}},
"shop_sign": {"color": "#202020", "class": "emissive",
  "texture": {"texels": ["1111111111111111", "1222222222222221", "…"],
              "colors": ["#202020", "#ffe070"], "projection": "planar", "axis": "z",
              "scale": [1.6, 0.4]}}
```

`texels` rows are hex digits naming `colors` entries (1-based, so a row can never contain
index 0). `projection` maps object-space positions to UV per face corner: `planar` along an axis,
`box` by each face's dominant normal axis, `cylindrical` around Y; `scale` is world units per
repeat. A solid palette-backed material is the degenerate case: a one-texel texture with one
colour and constant UVs, which is the swatch the kit already emits.

**Palette entries.** A face selects one 4-bit palette, so all colours of one textured material
must sit in the same 16-colour palette (at most 15). Entry assignment becomes packing of groups
into palettes, where today's solid materials are groups of one; the manifest would list each
group so a packer keeps it together. Texels hold palette-local indices, so a packer may move a
group to another palette at the same indices with `relocate`-style rewriting of face bytes only,
but merging groups into one palette at different indices means rewriting texels too. Sharing an
entry between a pattern colour and a solid material of the same colour and class works as now.

**Mesh format and runtime.** No format change: faces already carry four 8-bit UVs, a slot, a
4-bit flag and a palette, per face corner, so projections need no extra vertices. UVs are whole
texels (0–255) and wrap only at the 256-texel page edge, which is the real design constraint for
repeats. Three options per pattern: fill a whole slot with repeated tiles (32 KB, any repeat);
fill a band 256 texels wide and one tile high (16 rows of 4-bit = 2 KB) and split faces where
they cross a tile row; or keep one tile (128 bytes for 16×16) and split faces at every tile
boundary, which costs triangles. Large textured faces warp affinely; carts would use
`subdivide()` near the camera, which (unlike for swatches) then earns its CPU cost.

**Texture windows (since approved and built).** The repeat constraint above is now partly
answered by the Prism Engine's per-polygon texture windows
([DECISIONS.md](DECISIONS.md#texture-windows), [LANGUAGE.md](LANGUAGE.md#mesh-format)): a face
may name one of up to 7 windows from its mesh's window table, a power-of-two rectangle of 8–256
texels per axis (origins on multiples of 8) that its u and v wrap within. A tile is then stored once and repeats inside its own window, so many
patterns share one slot: the third option's VRAM cost (128 bytes for a 16×16 tile) without its
face splitting. What windows do not change: coordinates are still 8 bits per vertex, so one face
spans at most 255 texels of a pattern (15 repeats of a 16-texel tile, 7 of a 32-texel one), and
a larger face must still be split, or carry a larger pre-repeated tile. The proposal becomes:
patterns packed as window-aligned tiles, split only where a face's span exceeds 255 texels.

What the kit still needs to use them, none of it built: the texture authoring above (patterns,
texel grids, projections); packing tiles into a slot at window-aligned origins and writing the
window table and the faces' window bits (`tools/meshlib.py`, which the kit exports through,
already writes both: `Mesh.window()` and `face(window=...)`); splitting faces at 255 texels of
span; the material manifest listing tiles and windows, and `relocate()` moving them (today it
rejects any textured face that is not a swatch face); and the Asset Checker's identity mesh
treating a windowed face whose texels never contain index 0 like a swatch face.

**Verification.** The gate stays as it is if pattern and grid texels never contain index 0:
coverage is then that of the untextured face, as for swatches. `identity_mesh` would check
"the face's texture region contains no index 0" against the texels the kit generated instead
of "the UVs are one swatch texel". Cutouts (index 0 as holes: fences, foliage) would change
coverage per texel and need the probe to render real texels: a gate redesign, so the proposal
excludes them.

**VRAM and GPU.** The swatch row is 8 bytes. A 16×16 4-bit tile is 128 bytes; the repeat
options above cost 128 bytes, 2 KB or 32 KB per pattern, against 15 free 32 KB slots. Fill cost
is the same as palette-backed solids (textured pixels at twice the flat cost); patterns add no
GPU cost over swatches, only VRAM and, with face splitting, triangles.

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
- **Textures** are to be named procedural patterns and small texel grids written in the recipe,
  with UVs always generated by projection; image files come later, for signage
  ([Textures](#textures-proposal)).
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
