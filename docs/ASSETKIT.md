# Mei Asset Kit

A command-line 3D asset tool designed for AI agents. An editable JSON recipe describes
named parts and modeling operations. The tool builds native Mei meshes, validates their
actual fixed-point geometry, reports costs and topology per part, and checks actual triangle
visibility through Mei's compiler and GPU. Preview images help assess appearance; a numerical
verification gate decides whether geometry and visibility pass.

Modeling and ordinary builds use Python 3.10+ without third-party packages; textures read from
PNG images or sheets need Pillow ([Textures](ASSETKIT-REFERENCE.md#textures)). Visibility
verification additionally requires NumPy and `meic` / `mei-asset-probe`; `make` builds the
native tools. Preview rendering uses `meic` / `mei-headless`. No GUI, model service or network
is involved in these checks. The visibility verification gate (`verify`) is called the **Asset
Checker**. The kit's code is `tools/assetkit/`; what it shares with the World Kit (errors, JSON
input, schema validation, vectors, the compiler and runner wrappers, images and staged outputs)
is in `tools/kitcore/`.

This is the guide: the loop, the authoring rules and conventions, the commands and where to look
next. The rest is in other files:

| Document | What is in it |
|---|---|
| [ASSETKIT-REFERENCE.md](ASSETKIT-REFERENCE.md) | The reference: what each command prints and writes, every recipe field (operations, modifiers, materials, decals, palettes, levels of detail, impostors, budgets and limits), textures, the Asset Checker and its reports, the outputs, `export`, a cookbook and the tests |
| [DECISIONS.md](DECISIONS.md#the-asset-kit) | The project owner's decisions about the kit |
| [WORLDKIT.md](WORLDKIT.md) | The World Kit, which places assets in levels |
| [ANIMKIT.md](ANIMKIT.md) | The Animation Kit, which animates rigs of rigid parts built as Asset Kit recipes |

## Quick reference

The loop, with a private build directory (`make B=build-mine build-mine/meic
build-mine/mei-headless build-mine/mei-asset-probe` once):

1. **Edit** the recipe (`init FILE --example robot` for a start; `schema` for every field).
2. **`inspect FILE`.** Fix *everything* it reports before rendering: `flush_contacts` (with a
   fix per part pair in `fixes`), `close_faces`, the `warnings` (budgets, mirror copies over
   their originals, parts below y = 0, open surfaces) and `texture_windows` (at most 7).
3. **`preview FILE -o DIR --build-dir build-mine --closeups`** (and `--camera`, `--part` for the
   views a player has). Look at `contact.png` and `cameras.png`; the frame costs are in
   `report.json` at `preview.cameras.views[i].cost` ([Camera
   views](ASSETKIT-REFERENCE.md#camera-views-at-world-scale)). With a required policy, `build` and
   `preview` stop before rendering on flush contacts. Give the views the game's sky and ground with
   `--background` and `--ground`, or once for a cart's assets in an `asset-preview.json` ([The
   look](ASSETKIT-REFERENCE.md#the-look-background-and-ground)).
4. **`verify FILE --build-dir build-mine`** until `ok`; then the asset is done. Make the policy
   required in the recipe (`"verification": {"required": true, "depth": true, "perspective":
   true}` for a depth-mode game) so every later build checks it.

| Look up | Where |
|---|---|
| Facing (−Z is the front), box sides, rotation, winding, u/v | [the conventions table](#authoring-rules-depth-mode) |
| What each primitive costs | [Triangle costs](ASSETKIT-REFERENCE.md#triangle-costs) |
| Limits that are not budgets (2,048 vertices, 128 root nodes, 7 windows) | [Hidden limits](ASSETKIT-REFERENCE.md#hidden-limits) |
| A side or a cap in another material; a sign, poster or label on a face | [Face materials and decals](ASSETKIT-REFERENCE.md#face-materials-and-decals) |
| A sign, a decal, stairs, a dial | [Cookbook](ASSETKIT-REFERENCE.md#cookbook) |
| Texture scale, text on textures | [Texture tips](ASSETKIT-REFERENCE.md#texture-tips) |
| What a failure means and how to repair it | [Reports and repairs](ASSETKIT-REFERENCE.md#reports-and-repairs) |

## Agent workflow

```sh
# Discover the exact supported input contract.
python3 tools/mei_assets.py schema

# Start from a working recipe. Alternatives: vessel, cottage, kiosk (palette materials),
# stall (textures; init copies its sheet beside the recipe).
python3 tools/mei_assets.py init /tmp/robot.asset.json --example robot

# Edit the JSON, preserving meaningful node IDs.
# Check bounds, topology, counts, per-part costs and flush contacts before rendering.
python3 tools/mei_assets.py inspect /tmp/robot.asset.json

# Build the native tools if necessary (make B=DIR ... for a private build directory).
make build/meic build/mei-headless build/mei-asset-probe

# Numerically check geometry and triangle visibility. Nonzero exit means failure.
python3 tools/mei_assets.py verify /tmp/robot.asset.json -o build/robot-check

# Build and render the actual exported mesh from six angles, plus close-ups at world scale.
python3 tools/mei_assets.py preview /tmp/robot.asset.json -o build/assets/robot --closeups
```

Open `build/assets/robot/contact.png`, then adjust the recipe and rerun. The contact sheet
contains isometric, front, right, back, top and rear-quarter views. Individual PNGs and
GPU CSVs are also saved. `report.json` includes vertex/triangle counts, mesh bytes, bounds,
recipe/mesh hashes, topology warnings and CPU/GPU statistics for each view. With `--closeups`,
`--camera` or `--part`, `cameras.png` shows views at world scale, larger, with each view's frame
cost ([Camera views](ASSETKIT-REFERENCE.md#camera-views-at-world-scale)).

With a private build directory (`make B=build-mine`), give it once: `--build-dir build-mine`, or
`export B=build-mine` (or `MEIC`, `RUN` and `PROBE`, as the test suites read them) and every
command finds its tools there ([Native tools](ASSETKIT-REFERENCE.md#native-tools)).

A recipe with more than a few dozen parts, or one with levels of detail and a collision recipe
made from the same measurements, is easier to write as a Python script that writes the JSON:
`tools/assetkit/author.py` has the builders such scripts share ([Writing recipes from
Python](ASSETKIT-REFERENCE.md#writing-recipes-from-python)).

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

The CLI exits 0 on success or 1 on failure. `preview` and `verify` print a one-screen summary
([Output](ASSETKIT-REFERENCE.md#output-the-summary-and-the-full-report)), and with `--json` the full
report; the other commands (but `info` and `floors`) print JSON on stdout for both successes and
failures. `--help` prints human-readable help. Recipe errors contain a JSON Pointer `path` and an
actionable `message`, and, when the path runs through nodes, `node`: their ids as `inspect`'s parts
name them (`"path": "/nodes/1/children/0/size/2"`, `"node": "group_1/arm"`; a node without an id is
`OP_INDEX`; `prototype wheel: rim`, `lod level 1: lump`). Commands accepting a recipe also accept
`-` to read stdin. A failure's JSON output begins with `ok` and `errors`; a verification report
begins with `ok`, `verdict`, `failures` and `allowed` ([Reports and
repairs](ASSETKIT-REFERENCE.md#reports-and-repairs)).

## Authoring rules (depth mode)

Most assets are drawn with the depth buffer (`"verification": {"required": true, "depth": true,
"perspective": true}`, [Depth mode](ASSETKIT-REFERENCE.md#depth-mode)). There, parts may cross each
other freely, but:

- **Never let two parts' faces sit flush in the same plane.** A box standing on another box, a panel
  laid on a wall, a frame level with the wall it sits in: two faces in one plane that overlap in
  area fight in the depth buffer, and the Asset Checker fails them as `coplanar_overlap` (in either
  mode). **Sink the part 1–2 cm into its neighbour** (stand the box at 0.99 instead of 1.0, set the
  panel 0.01 into the wall), **or open the hidden face** (a box's `"open": ["bottom"]` where it
  stands on something). A picture on a face (a poster, a label, a stain) is a **decal**, baked into
  the face ([Face materials and decals](ASSETKIT-REFERENCE.md#face-materials-and-decals)), not a
  panel laid on it. A part floating 1 mm off a surface is not flush and passes the check, but ties
  in the depth buffer from far enough away; sinking it is safer. `inspect` lists flush contacts by
  part pair before anything is rendered (`flush_contacts`, with NumPy), `build` and `preview` check
  for them too (and stop when the Asset Checker is to run), and `verify` lists them first in its
  `failures`.
- **Keep faces that face the same way at least 3 cm apart** where one covers the other: a sign
  panel standing 1 cm proud of its board, a post 1 cm in front of the face it runs up. The
  depth buffer allows them, so no check fails them, but they tie in the depth key from a
  distance and the farther face shows through: a sign 1 cm in front of its board lost half its
  triangles from 7 m. `inspect` and `verify` warn of them (`close_faces`, below).
- Without the depth buffer, crossing parts fail too; see [the
  gate](ASSETKIT-REFERENCE.md#automated-visibility-gate) and [Reports and
  repairs](ASSETKIT-REFERENCE.md#reports-and-repairs).

Conventions, each checked on native renders (`tests/test_assetkit.py`, `ConventionTests`):

| What | Convention |
|---|---|
| Facing | Y is up. Models face **−Z**: the preview's `front` view, a camera on −Z looking toward +Z, sees that side. On screen the front view has +X to the right and +Y up; the `right` view (a camera on +X) has +Z to the right; the `top` view has +X to the right and +Z up |
| Box `open` sides | By axis: `left` −X, `right` +X, `bottom` −Y, `top` +Y, **`back` −Z, `front` +Z**. So a box's `back` is the side a model faces with (the front camera sees it) and its `front` is the model's back. The axis names `-x`, `+x`, `-y`, `+y`, `-z`, `+z` are accepted too and mean the same sides (`-z` is `back`) |
| Rotation | `rotate` is in degrees, X then Y then Z. `[0, 90, 0]` turns +X to −Z and the −Z front to −X: clockwise in the top view, the way a positive camera yaw turns right. `[0, 0, 90]` turns +X to +Y: counterclockwise in the front view. `[90, 0, 0]` turns +Y to +Z: the top tips away from the front camera. In general a positive angle turns clockwise as seen from the positive end of its axis in Mei's views |
| Mesh winding | Outward: (b − a) × (c − a) points out of the solid. A face toward the front camera lists its corners clockwise as seen on screen: top-left, top-right, bottom-right, bottom-left. The reverse order faces away and is culled (not drawn) unless the material is `double_sided` |
| u and v | u runs right and v down as the face is seen from outside, "up" being the primitive's +Y (+Z for a face looking straight up or down, as in the top view). A mirrored copy is seen from its own outside too |
| `box` and `planar` | u = 0 and v = 0 at the primitive's origin: a repeat's top-left corner is there, and the repeat runs right and down from it, so a box centred on the origin has a repeat's corner at the middle of each face (`offset` [0.5, 0.5] centres a repeat instead). `planar` along `z` is seen from −Z (u along +X, v along −Y), along `x` from +X (u along +Z), along `y` from above (u along +X, v along −Z), each as `box` draws that side |
| `cylindrical` | u = 0 on the −Z meridian (the line facing the front camera), growing toward +X, so rightward in the front view, and around; v = 0 at the primitive's y = 0 (its middle: primitives are centred), growing downward |
| `disc` | Centred on the primitive's origin. About `y` (the default) as seen from above: u = 0 at the −X edge and v = 0 at the +Z edge. Both caps of a cylinder get the same mapping, so the bottom cap, seen from below, shows it upside down. About `z` and `x` as `planar` sees those axes |
| `fit` | Each plane of the primitive gets the whole texture over the bounding rectangle of its faces in that plane, in its own right/down frame: u = 0 at the left edge, v = 0 at the top. A plane is a box side, each side quad of a cylinder or lathe (so each gets the whole texture), a cap, an extrusion's outline face; in a `mesh` node, each source polygon. On a shape that is not a rectangle (a triangle, a round cap, an L shape) the parts of the texture outside it are not drawn |
| `stripes` `axis` | The colour changes **along** the axis: `u` (the default) makes bands side by side along u, each running the whole way along v, so on a wall (`box`, `planar` `z` or `x`, `fit`) **vertical stripes**, and around a `cylindrical` surface stripes running up it; `v` makes bands stacked along v: horizontal stripes on a wall, rings around a cylinder. On a face looking up or down (`box`, `planar` `y`, `disc` `y`), u runs along +X, so `u` stripes run along Z, front to back. A texture's `rotate` 90 turns them a quarter turn |
| Lighting `direction` | Points **from the asset toward the light**, in the asset's own frame: a face whose outward normal is `direction` gets the full colour, one facing away gets `ambient` (the shade is `ambient + (1 − ambient) × max(0, n · direction)`, n the face's unit normal, `direction` normalised). The default `[-0.4, 0.85, -0.35]` is a light above, in front (−Z, the side the front camera sees) and to the left in the front view (−X) |

## Commands

| Command | Result |
|---|---|
| `schema` | Full JSON Schema, including supported operations and field bounds |
| `init FILE [--example robot\|vessel\|cottage\|kiosk\|stall]` | Editable starter (with the images it reads, beside it); refuses to overwrite unless `--force` |
| `validate FILE [--strict]` | Schema, reference, geometry, fixed-point and budget checks |
| `inspect FILE [--strict]` | Same checks, with full bounds, per-part report, `flush_contacts`, `close_faces`, `texture_windows` and more `warnings` (below); a recipe over its budgets is reported in full |
| `verify FILE [-o DIR] [--build-dir DIR] [--json]` | Geometry checks plus native triangle-ID visibility and ordering-graph checks; a [summary](ASSETKIT-REFERENCE.md#output-the-summary-and-the-full-report), or the full report with `--json` |
| `build FILE -o DIR [--verify] [--preview] [--strict] [--depth] [--perspective] [--build-dir DIR]` | Native and exchange artifacts; optional or recipe-mandated verification gate |
| `preview FILE -o DIR [--verify] [--strict] [--depth] [--perspective] [--build-dir DIR] [--closeups] [--camera SPEC]… [--cameras FILE] [--part ID]… [--upscale N] [--background C[,C]] [--ground C\|none] [--look FILE\|none] [--json]` | Build plus six native renders and contact sheet, and [camera views](ASSETKIT-REFERENCE.md#camera-views-at-world-scale), in [a look](ASSETKIT-REFERENCE.md#the-look-background-and-ground); a [summary](ASSETKIT-REFERENCE.md#output-the-summary-and-the-full-report), or the full report with `--json` |
| `info FILE [--at X,Y,Z] [--yaw DEG] [--collision auto\|asset\|self\|none\|PATH] [--json]` | Bounds (drawn and collision, and placed), triangles per level of detail and switch distances, texture bytes per texture, palettes, texture windows ([Quick facts](ASSETKIT-REFERENCE.md#quick-facts-info-and-floors)) |
| `floors FILE [--step 0.25] [--at X,Y,Z] [--yaw DEG] [--below Y] [--area X0,Z0,X1,Z1] [--json]` | A grid of the collision's top floor heights, with walls and too-steep faces marked ([Quick facts](ASSETKIT-REFERENCE.md#quick-facts-info-and-floors)) |
| `import-obj FILE -o RECIPE [--name NAME] [--force]` | Geometry-only OBJ import into an explicit `mesh` recipe |
| `pack FILE... -o DIR [--name NAME] [--slots 14-0] [--palette 0] [--palette8 14]` | Several assets (or one) for a cart without a world: shared texture slots and palettes, one loader ([Placement](ASSETKIT-REFERENCE.md#placement-build-and-pack)) |
| `export FILE -o DIR [--format glb\|gltf]` | One glTF 2.0 file for ordinary 3D viewers, drawn as Mei draws it ([export](ASSETKIT-REFERENCE.md#viewing-an-asset-elsewhere-export)) |

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

## Examples

`init FILE --example NAME` copies one of five recipes in `examples/assets/` (with the images it
reads):

| Example | What it shows | The Asset Checker |
|---|---|---|
| [`robot`](../examples/assets/robot.asset.json) | Meshes, spheres and cylinders, prototypes and instances, `mirror`, `face_materials` on its head | Fails (surface intersections) |
| [`vessel`](../examples/assets/vessel.asset.json) | Lathes and an extrusion, `mirror` | Fails without depth; passes in depth mode |
| [`cottage`](../examples/assets/cottage.asset.json) | Boxes and extrusions, prototypes and instances, `mirror` and `array` | Fails (coplanar overlaps) |
| [`kiosk`](../examples/assets/kiosk.asset.json) | Palette-backed and emissive materials, tags, vertical lighting and a required verification policy | Passes, and requires it |
| [`stall`](../examples/assets/stall.asset.json) | Textures of every kind, cutouts, an animation, depth mode | Passes in depth mode, and requires it |

`robot`, `vessel` and `cottage` predate the Asset Checker; they remain as modelling examples
([DECISIONS.md](DECISIONS.md#the-asset-kit); the measurements are in
[Depth mode](ASSETKIT-REFERENCE.md#depth-mode)). Real assets that pass it are in the carts'
folders, for example `carts/fallline/models/` and `carts/garden/shrinetown/assets/`, and the lab
models in `examples/assets/lab/`.

## Tests

```sh
make test-assets                                                  # the suite, verbose
python3 -m unittest discover -s tests -p test_assetkit.py -v      # the same, without make
```

`make test` runs it too, and `tests/test_author.py`, the authoring module's tests. Pure
Python tests run anywhere; native render tests are skipped when the binaries are absent, and the
Asset Checker's tests when NumPy is. What the suite covers is listed
in [the reference](ASSETKIT-REFERENCE.md#tests).

## Where to look next

| To | Read |
|---|---|
| Know what `preview` and `verify` print, and find a view's frame cost | [Output](ASSETKIT-REFERENCE.md#output-the-summary-and-the-full-report), [Camera views](ASSETKIT-REFERENCE.md#camera-views-at-world-scale) |
| Fix flush contacts and close faces | [Command details](ASSETKIT-REFERENCE.md#command-details) |
| Place an asset in a world: bounds, floors, texture bytes | [Quick facts](ASSETKIT-REFERENCE.md#quick-facts-info-and-floors) |
| Look up an operation, a modifier or a material field | [Recipe fields](ASSETKIT-REFERENCE.md#recipe-fields) |
| Give one side or a rectangle of a face another material | [Face materials and decals](ASSETKIT-REFERENCE.md#face-materials-and-decals) |
| Recolour at run time (day and night, glowing signs) | [Palette-backed materials](ASSETKIT-REFERENCE.md#palette-backed-materials) |
| Make glass, water or a glow | [Semi-transparent materials](ASSETKIT-REFERENCE.md#semi-transparent-materials) |
| Add far levels, or an impostor | [Levels of detail](ASSETKIT-REFERENCE.md#levels-of-detail), [Impostors](ASSETKIT-REFERENCE.md#impostors) |
| Texture an asset | [Textures](ASSETKIT-REFERENCE.md#textures), [Texture tips](ASSETKIT-REFERENCE.md#texture-tips) |
| Understand a failed check and repair it | [Reports and repairs](ASSETKIT-REFERENCE.md#reports-and-repairs), [What is checked](ASSETKIT-REFERENCE.md#what-is-checked) |
| Draw several assets in a cart without a world | [Placement: `build` and `pack`](ASSETKIT-REFERENCE.md#placement-build-and-pack) |
| Import the result into a cart | [Outputs and game integration](ASSETKIT-REFERENCE.md#outputs-and-game-integration) |
| See the asset in another 3D viewer | [`export`](ASSETKIT-REFERENCE.md#viewing-an-asset-elsewhere-export) |
| Copy a working piece (a sign, a decal, stairs, a dial) | [Cookbook](ASSETKIT-REFERENCE.md#cookbook) |
