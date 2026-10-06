# Mei World Kit

**Status: design, partly built.** What exists: the pack format, version 1.3
([WORLDPACK.md](WORLDPACK.md), normative) with its reference encoder `tools/worldkit/pack.py`; the
console reader `stdlib/worldpack.akr`; the tool, `tools/mei_world.py`, with the [recipe
format](#recipe-format) (cells, regions and palette variants, layers, [ground](#ground), [merged
scatter](#merged-scatter), [paths](#paths), [levels of detail](#levels-of-detail), collision, game data in
[Mochi](#game-data-and-stable-ids) or JSON, the ID lock file, and [terrain](#terrain): ground
heightfields with cliffs and water, profiles swept along paths, draped paths, things set on the
ground and [scatter](#scatter)) and [command line](#command-line)
below; the **World Checker**, the in-level
verification every build runs ([WORLDCHECKER.md](WORLDCHECKER.md)); five example worlds in
`examples/worlds/`; and make's rule for [a cart that uses worlds](#using-a-world-in-a-cart), with
World Viewer (`carts/worldview/`) as its example; [textures per region](#textures-per-region),
night variants for them and [backdrops](#backdrops) on the plane chip, with a fourth example,
`night_market`. Not built yet: audio banks and spreading a region swap over a seam (see
[Region seams](#region-seams) and [Build order](#build-order) for where the stages stand). This document records
the project owner's decisions (most of them made on 2026-10-03), proposes the rest, and lists
what is still open. The game that motivates it is described in [PLATFORMER.md](PLATFORMER.md)
and is not built. It depends on three things, all now in place:

- **A larger cart ROM.** A cart may be up to 64 MB, read in place from a 128 MB window at
  `0x08000000` (commit `620a8d1`; [DECISIONS.md](DECISIONS.md), "Cart ROM: up to 64 MB in a
  128 MB window"). Embeds of 64 KB or more go to the assembler in memory, so a large pack costs
  compile time in proportion to its size. See [ROM](#rom).
- **The Asset Kit** ([ASSETKIT.md](ASSETKIT.md)), with the changes this design asked of it, most of
  which have landed: see [Asset Kit changes this needs](#asset-kit-changes-this-needs).
- **A runtime.** Tsumiki, the stdlib 3D toolkit that had a scene, solids, a character controller
  and cameras, was removed in October 2026 ([ROADMAP.md](ROADMAP.md)). Its replacement for worlds
  is the narrow pack reader `stdlib/worldpack.akr` (cells, culled drawing in passes, collision
  queries, entity tracking; [WORLDPACK.md](WORLDPACK.md)).

The World Kit is a command-line tool for AI agents, a sibling of the Asset Kit. An editable JSON
recipe places Asset Kit assets into cells and regions, attaches game data to them, and builds one
native world pack that a cart embeds. The World Checker samples cameras through the playable
space and reports budget overruns, face-ordering errors and holes in collision (report-only at
first; see [Verification](#verification)). The Asset Kit's own verification gate is the **Asset Checker**
(`mei_assets.py verify`).

**Reading this document.** The project owner settled the decisions in the table below. They are
stated as the design. Everything else marked *Proposal* is this document's addition, there for the
owner to accept or argue with. Numbers are derived from the spec and docs with the arithmetic
shown, or marked *placeholder*.

| # | Decided | Section |
|---|---|---|
| 1 | Separate tool, shared core, one-way dependency on the Asset Kit | [The boundary](#the-boundary-with-the-asset-kit) |
| 2 | One format for open worlds and discrete levels; interiors are separate worlds | [Data model](#data-model) |
| 3 | "Streaming" without a disc: ROM is read in place; cells are position-independent blobs | [Streaming](#streaming-without-a-disc) |
| 4 | Regions above cells, each owning textures, palette variants, audio and a backdrop | [Regions](#regions-and-the-vram-split) |
| 5 | A low-detail stand-in per cell | [Sight lines](#sight-lines-and-stand-ins) |
| 6 | Layers: named groups of placements the game switches | [Data model](#data-model) |
| 7 | Opaque game data with stable IDs, validated against a game-supplied schema | [Game data](#game-data-and-stable-ids) |
| 8 | No game rules in the kit, including time of day | [Day and night](#day-and-night) |
| 9 | The World Checker: budgets, ordering, collision holes; its scene probe is a World Kit component; thresholds are per-world settings and it starts report-only | [Verification](#verification) |
| 10 | Time-neutral, rotation-neutral baked shading; materials draw through palette entries; emissive materials get entries of their own | [Day and night](#day-and-night) |
| 11 | Build order: a movement garden (the first World Kit level), one district block, a second region | [Build order](#build-order) |
| 12 | The boundary is "could you place it twice?": reusable things are assets | [The boundary](#the-boundary-with-the-asset-kit) |
| 13 | Terrain (ground heightfields and swept paths, in world coordinates) belongs to the World Kit | [Terrain](#terrain) |
| 14 | Collision is authored separately as simpler geometry; surface types are an opaque byte | [Collision](#collision) |
| 15 | Units: the tools enforce no scale; the convention is one unit per metre | [Recipe format](#recipe-format) |

## What this is for

The motivating game is a 3D platformer with Mario 64-style movement, set in a 1990s Japanese
metropolis: downtown, shrines, parks, an electric-town district and a mall. The city is one open
world of several regions with many small goals: a collectible unit scattered everywhere, and
switches that start short challenges, in the manner of Mario Kart World's open world. The mall is
an interior reached through doors. [PLATFORMER.md](PLATFORMER.md) describes the game.

The same kit should serve games built from discrete levels, without a second format.

## Goals and non-goals

Goals:

- One recipe format and one pack format for a one-room test level, a course-based game and a
  multi-region open world.
- Placement, grouping and game data only. Every triangle comes from an Asset Kit recipe.
- A numerical checker, like the Asset Checker, that an agent can iterate against: budgets, sorting and
  collision checked from sampled cameras, with witnesses that name the cell, placement and face.
- Deterministic builds: identical recipes and asset recipes give byte-identical packs.
- Stable identifiers for anything a save file refers to.

Non-goals:

- **General modelling.** No geometry operations in world recipes, not even "a floor here":
  buildings, platforms, stairs and props are assets. The one exception, by the owner's decision,
  is [terrain](#terrain): ground and paths described in world coordinates, which exist once and
  must meet across cell seams. The owner explicitly does not want a hybrid tool.
- **Game rules.** The kit does not know what a coin, a switch, a mission, a door or night is.
- **A game engine.** The runtime reads the pack and answers geometric questions (what to draw,
  what is under this point). Character control, cameras, AI and saving are the game's.
- **Disc-style streaming.** There is no disc and no loading of geometry into RAM.

## The boundary with the Asset Kit

### What the Asset Kit is today

Checked against `tools/mei_assets.py` and `tools/assetkit/` on `main`:

- A recipe (`"format": "mei-asset"`, `"version": 1`) has a `name`, `materials`, `prototypes`,
  `nodes`, optional `lighting`, `budget` and `verification`. Names match
  `^[a-z][a-z0-9_]{0,47}$`. Unknown properties are errors. There are no expressions.
- Operations: `box`, `sphere`, `cylinder`, `cone`, `extrude`, `lathe`, `loft`, `mesh`, `group`,
  `instance`; modifiers `mirror`, `array`, `radial`, `taper`, `twist`, `subdivide`.
- A material is `color` (`#RRGGBB`) plus optional `smooth` and `double_sided`, and the
  extensions this design asked for: `palette` (draw through a palette entry: a 4-bit textured face
  sampling one texel of a solid *swatch*, with the baked shade as the vertex tint), `class`
  (`surface` or `emissive`: entries of its own, never shaded) and `tag` (an opaque name carried to
  the outputs). Lighting is baked at export from one direction and an ambient term, or with
  `lighting.mode: "vertical"` from the normal's Y alone, which survives any yaw.
- Output is one native mesh: at most 2,048 vertices, an authoring budget of up to 4,000
  triangles, faces untextured or palette swatch faces. Mesh size is 16 + 16 × vertices + 36 ×
  faces bytes. `build` also writes an `.akr` embed, an OBJ, a Modeler project, a preview cart,
  `report.json` with recipe and mesh hashes, and a material manifest (`NAME.materials.json`:
  palette entries, classes, tags and face ranges). `assetkit.compiler.relocate()` moves a
  mesh's palette faces to other palette colours and another swatch position, for a packer.
- `verify` renders a triangle-ID version of the mesh through the real compiler and GPU, compares
  every pixel with an independent reciprocal-depth rasterizer, and builds a far-before-near
  ordering graph to find cycles. It samples **fitted cameras around one isolated mesh** (144
  views by default) and rejects views that need near-plane or guard-band clipping. It accepts
  opaque untextured faces and palette swatch faces.
- Texture and UV authoring (proposed in ASSETKIT.md, "Textures"), LOD generation and animation
  are not included.

### Decided: separate tool, shared core, one-way dependency

World recipes reference asset recipes by name. The Asset Kit never learns that levels exist.
World recipes contain no general modelling; asset recipes contain no placement or game data.
Level geometry (buildings, platforms, stairs) is modelled as assets and placed by the world
recipe.

**Decided: the boundary is "could you place it twice?"** Anything reusable (a staircase, a
vending machine, a length of guard rail) is an asset. Anything that exists once, at one place in
the world, belongs to the world: placements, game data, collision choices and terrain.

The shared core is what both tools import: fixed-point geometry and quantization, the compiler
and probe wrappers, schema validation with JSON Pointer errors, and native preview rendering.
It lives in `tools/kitcore/`; the kits stay `tools/assetkit/` and `tools/worldkit/`, with their
entry points `tools/mei_assets.py` and `tools/mei_world.py`. The World Kit additionally calls the
Asset Kit's public compile entry points (`assetkit.compiler.compile_recipe`, `native_bytes`,
`material_manifest`, `relocate`) to build the assets a world references. The dependency stays
one-way.

A world build compiles every referenced asset recipe itself, requires each asset's own
verification policy to pass, and records each recipe's hash in the world report, so a world
build is reproducible from recipes alone and never trusts a stale `.bin`.

### Asset Kit changes this needs

These are Asset Kit features, not World Kit features. Each is generic: none mentions worlds.

1. **Done: a material class** (decision 10). `"class": "emissive"` gives a material palette
   entries of its own, never shaded, so emissives can brighten while everything else darkens.
2. **Done: palette-backed materials.** Palettes only reach the screen through a texel, so each
   palette-backed face is a 4-bit textured face sampling one texel of a solid swatch, tinted by
   its baked shade ([ASSETKIT.md](ASSETKIT.md), "Palette-backed materials"). With the material
   manifest and `relocate()`, a packer can move an asset's entries into a region's palettes.
3. **Done: surface tags and the vertical bake** (`tag`, `lighting.mode: "vertical"`).
4. **Done: forced separate entries and a manifest for every build.** Surface materials of the
   same colour share an entry by default; a recipe may force separate ones (`"share": false`).
   The material manifest is written for every build, so a world build reads one shape of data
   for every asset.
5. **Done: textures and UVs.** Regions own texture sets (decision 4). The Asset Kit authors
   textured assets ([ASSETKIT.md](ASSETKIT.md#textures)) and the World Kit packs them per region
   ([Textures per region](#textures-per-region)).
   Repeating textures use the Prism Engine's per-polygon **texture windows** ([DECISIONS.md](DECISIONS.md#texture-windows)), which `mesh()` already sends from a
   mesh's window table: many small repeating tiles share one texture slot instead of a slot each.

Two items earlier versions of this list carried are no longer Asset Kit changes: terrain belongs
to the World Kit ([Terrain](#terrain)), and the scene probe is a World Kit component (part of the
World Checker)
([Verification](#verification)).

## Data model

| Thing | What it is | Owns |
|---|---|---|
| **World** | One pack: a set of cells and an index. A city, a mall, a test room, a course | regions, cells, the ID lock file |
| **Region** | A district whose cells share one set of resources | texture set, palette variants, audio bank, backdrop |
| **Cell** | A self-contained square of the world | placements, layers, collision, entities, a stand-in |
| **Placement** | One asset at a position and yaw, with a stable ID | an asset reference, an optional layer |
| **Layer** | A named group of placements and entities in one cell that the game switches on and off | nothing else; the kit only knows it exists |
| **Entity** | Game data: a type, a stable ID, a position and parameters | an optional asset to draw, an optional layer |
| **Palette variant** | A named full set of a region's palette colours (`day`, `night`, …) | colours |
| **Stand-in** | A cheap low-detail mesh drawn for a cell when it is far away | an asset reference |

**Decided: one format for open worlds and discrete levels.** A world is a set of self-contained
cells plus an index; the runtime keeps the cells near the player active. A discrete level is a
world with one cell, or with every cell always active. Interiors such as the mall are separate
one-cell (or few-cell) worlds reached through doors. A door is an ordinary entity whose game type
happens to carry a world reference.

**Decided: layers.** A layer is a named group of placements within a cell that the game switches:
festival stalls that appear at night, a bridge raised by a switch, the before and after states of
a building site. The kit does not know what a layer means. It knows the group exists so it can
check triangle budgets and sorting with each layer on.

*Built:* layers are named world-wide in the world file (so the game switches one in every cell at
once), at most 8 used in any one cell (one byte of mask), and may name an exclusive `group`:
`bridge_up` and `bridge_down` in group `bridge` are never on together. The pack maps the name to
each cell's bit. Placements, entities and their collision can be in layers.

*Proposal:* the world recipe may name a shared `common` file holding the common texture set and
common palettes, so the city and the mall interiors use the same common set and a door between
them only swaps region resources.

## Terrain

**Decided: terrain belongs to the World Kit.** Ground (a heightfield) and paths (a profile swept
along a line) are described in world coordinates in the world recipe, generated by the shared
core and cut per cell by the kit, so seams match by construction. They are the only modelling the
World Kit does. Paths are world data in their own right too: the same line can be a road, a
traffic route or a rail to grind. Paths come first.
Terrain collision comes from the terrain itself.

**Built: paths as world data** ([Paths](#paths) in the recipe format; WORLDPACK.md, "Paths"):
named polylines in world coordinates, raised or lying on the ground, open or closed, with a
surface tag, stored once per world in the pack and exported as numbered constants; the reader
looks them up by number or name and answers the nearest point on a path (a grind check) and the
point at a length along it (a mover). They make no geometry: a rail, a wire or a jib is drawn and
collided with by assets placed along it.

**Built: terrain geometry** (`tools/worldkit/terrain.py`): ground heightfields in the world
recipe's `terrain` property, and profiles swept along paths in a path's `sweep`. Both are made in
world coordinates and cut per cell by the kit; what reaches the pack is what it already held,
with no format change: ordinary native meshes placed at their cell's centre (yaw 0, cell-local
vertices, as merged scatter is) and collision triangles in world coordinates. Worlds without
terrain build exactly as before, byte for byte. The example is
[`examples/worlds/shrine_grounds`](../examples/worlds/shrine_grounds) ([below](#the-example-shrine-grounds)).

**Built on it:** [cliffs](#cliffs) (vertical faces and overhangs a heightfield cannot make),
[water](#water) (ponds, streams and waterfalls, semi-transparent, and a query for wading),
[draped paths](#draped-paths) (a trail that follows the ground and cuts its own bed),
[things set on the ground](#on-the-ground) and seeded [scatter](#scatter). The example using all
four is [`examples/worlds/forest_mountain`](../examples/worlds/forest_mountain)
([below](#the-example-forest-mountain)). Worlds that use none of them build as before, byte for
byte.

### Heightfields

```json
"terrain": {
  "materials": {
    "grass":  {"color": "#5f8f3e"},
    "earth":  {"color": "#86684a"},
    "gravel": {"color": "#b9b2a2", "tag": "gravel"}
  },
  "fields": {
    "grounds": {
      "spacing": 2, "min": [0, 0], "max": [128, 128],
      "material": "grass", "steep": {"degrees": 38, "material": "earth"},
      "lod": {"distance": 64, "tolerance": 0.3},
      "operations": [
        {"op": "set", "area": {"rect": [44, 50, 114, 116]}, "height": 3, "falloff": 2},
        {"op": "ramp", "from": [28, 0, 64], "to": [46, 3, 64], "width": 6, "falloff": 2},
        {"op": "carve", "area": {"circle": [22, 82, 9]}, "height": -1.4, "falloff": 4},
        {"op": "bed", "path": "sando", "width": 5, "depth": 0.6, "falloff": 3}
      ]
    }
  }
}
```

A **field** is a grid of height samples `spacing` units apart over the rectangle from `min` to
`max` (x, z), each quad between four samples taking a material. Its heights start at `height`
(default 0) or come from a `heights` file; then its `operations` change them, in order.

| Field property | Meaning |
|---|---|
| `spacing` | 0.5, 1, 2, 4 or 8 units between samples. Cells and tiles are whole numbers of quads |
| `min`, `max` | The rectangle, corners multiples of `spacing`. Quads over no cell are left out (a warning, `terrain_outside_cells`) |
| `height` / `heights` | The starting height of every sample, or a text file of them (below); not both |
| `material` | The terrain material of every quad not painted |
| `steep` | `{"degrees", "material"}`: unpainted quads steeper than that take the material (a bank, a cliff) |
| `operations` | Below |
| `tile` | Units per side of a tile, the unit of one mesh and one placement: at most a cell and 32 quads. Default: a cell, or 16 quads if that is less |
| `tolerance` | How far (units) level 0 may stray from the samples where quads merge (below). Default 0.01 |
| `lod` | `{"distance", "tolerance" (default 0.25), "band" (default 2)}`: a coarser level of every tile, drawn from that distance |
| `shading` | `smooth` (default: each corner shaded by the field's normal at that sample, so shading runs on across seams) or `flat` |
| `ground`, `collision` | Drawn in the ground pass; its faces are collision. Both default true |

Fields may not overlap or touch: make one field, or leave a gap. **The heights file** is text, one
line per row of samples from z = `min` to `max`, each row's samples from x = `min` to `max`
separated by spaces, `#` starting a comment; a field of 64 × 50 quads has 51 lines of 65 numbers.
*Decided here: a text grid, not a PNG heightmap.* Agents author terrain, and they read and edit
text line by line; a text grid diffs and reviews in git, carries metres exactly with no scale
or bit depth to choose, and needs nothing beyond the standard library (the kits build recipes
without Pillow). Most terrain needs no file at all: the operations below describe it in a few
lines, which is what an agent should reach for first. A painted heightmap can be converted to the
text grid by a script when a person wants to paint one.

**Operations.** Each acts within an `area` (omitted: the whole field) and fades out over
`falloff` units outside it (a smoothstep; default 0, a hard edge). An area is exactly one of
`{"rect": [x0, z0, x1, z1]}`, `{"circle": [x, z, radius]}`, `{"polygon": [[x, z], ...]}` (even-odd)
or `{"path": NAME, "width": w}` (within w / 2 of a path of the world file, seen from above).

| `op` | What it does |
|---|---|
| `set` | Flattens the area to `height` (a terrace, a courtyard, a plinth) |
| `add` | Raises the area by `height` (negative lowers it): with a falloff, a hill |
| `carve` | Lowers to at most `height` (a pond, a cutting); lower ground is left alone |
| `fill` | Raises to at least `height`; higher ground is left alone |
| `ramp` | Along the centre line `from` → `to` (`[x, y, z]` each), `width` across: the ground set to the line's height (a ramp between terraces) |
| `terrace` | Heights become flats `step` apart from `base` (default 0), joined by banks that take the top `bank` fraction of each step (default 0.25): a smooth hill becomes a stepped one |
| `smooth` | `passes` (default 1) of a 3 × 3 blur |
| `bed` | Along a path, within `width`: the ground set to the path's line less `depth` (the bed a sweep lies in; it cuts and fills). An open path's bed ends square at its ends |
| `paint` | The quads whose centres lie in the area take `material` (no falloff) |
| `hole` | The quads whose centres lie in the area are left out (no falloff) |
| `cliff` | The quads whose centres lie in the area move up by `height` (down if negative) as one sheet, joined to the rest by vertical walls of `material` (default: the `steep` material, else the field's); `overhang` and `lip` make the top jut out ([Cliffs](#cliffs)). No falloff |
| `water` | A flat water surface at `level` on every quad of the area with a corner below it, in a `water` material ([Water](#water)). No falloff |

Heights are rounded to 16.16 after the last operation. `report.json`'s `terrain` has, per field,
samples, quads, holes, the height range, tiles, triangles per level and per cell, vertices,
triangles per material and `full_triangles` (two per quad, for comparison);
`mei_world.py floor FILE X Z ...` answers the highest floor under points, from terrain, sweeps
and placements, for setting things on the ground.

**How a field is cut and simplified.** The field is cut into tiles aligned to the world's lattice
(a tile never crosses a cell edge). In each tile the quads are merged greedily, row by row, into
rectangles that share a material and are flat: every sample within `tolerance` of the patch
through the rectangle's corners, the patch's twist (how far its two triangles part from it)
included. Flat ground, a terrace's top and an evenly sloping ramp each become a few rectangles;
a single quad that is not flat is two triangles, split along the diagonal that makes both the
same kind for the body (both floors or both walls by the game's `floor_max_degrees`, so that no
steep sliver lies between two floors where they meet), then along the shorter rise. A rectangle
with only its own four corners on its edges is two triangles. One with more (the corners of
smaller neighbours) is zipped between its two long sides when the extra points lie on those
alone, and otherwise fanned from its centre, so no vertex lies in the middle of another face's
edge: there are no T-junctions in a tile. Across a tile edge both tiles use the same points:
every corner either tile has on that edge, at any level of detail. So the seams match by
construction, at every pair of levels, and the coarse level keeps its tile's edge points.

The coarse level is the same merge with the `lod` tolerance; each tile carries it as a
[level of detail](#levels-of-detail) (switching at `distance` from the tile's centre, with
`band`) when it has fewer faces. Collision is always level 0, in world coordinates, with each
material's `tag` as its surface; it is tagged 0xFFFE (sweeps 0xFFFD, scatter 0xFFFC) where an
asset placement carries its number, and the report's `placement_tags` names them `terrain`,
`sweeps` and `scatter`. A cell with terrain holds at most 65,532 placements of its own.

### Cliffs

```json
{"op": "cliff", "area": {"polygon": [[24, 116], [60, 122], [90, 114], [128, 120], [128, 192], [24, 192]]},
 "height": 14, "material": "rock", "overhang": 0.8, "lip": 1.5}
```

A heightfield has one height per sample, so its steepest bank spans a quad (a 2 m spacing makes
a 14 m rise at least 2 m deep). A `cliff` cuts the field instead: the quads whose centres lie in
the area become a **sheet** moved up by `height`, and along every quad edge between two sheets a
vertical wall joins them. The samples on such an edge keep one height per sheet, so later
operations act on each sheet separately: a `set`, `ramp` or `carve` after the cliff shapes the
plateau and the ground below on their own terms (an absolute height is the sheet's own), and
`smooth` and falloffs never blend the top into the foot. An operation changes a sheet's copy of
an edge sample only where a quad of that sheet is in its area or falloff (or the operation has
no area). A negative height lowers the area instead (a pit, a quarry face).

`overhang` (at most half the spacing) moves the top sheet's edge points out over the wall by that
much, along the average of their edges' outward normals; the wall rises upright to `lip` below the
top, then leans out to the moved edge, so the top band juts over the face: a waterfall's lip, a
ledge that hides the wall from above. The walls are steep faces of the wall material (collision
walls by `floor_max_degrees`) and share their points with both sheets' tiles, so there are no
cracks between wall and ground. A cliff's area follows quad edges, so its outline is stepped at
the spacing seen from above: a polygon traced at an angle gives a stair-stepped wall line. A face
looks out over the lower of its two sheets, also where operations after the cliffs leave the sheet
at the higher offset lower (flats cut into a slope as sheets of small offsets, then `set`).
`report.json`'s field entry has `cliff_triangles`.

### Water

```json
"materials": {"water": {"color": "#3f7393", "water": true, "tag": "water"}},
...
{"op": "water", "area": {"circle": [34, 38, 16]}, "level": 1.4, "material": "water"}
```

A terrain material with `"water": true` is water: its faces are semi-transparent (the GPU's half
blend, drawn by the ordering table back to front in depth mode too), have no collision and are
never ground. Water comes three ways:

- **A `water` operation**, for ponds and pools: a flat surface at `level` over every quad of its
  area that has a corner below it, merged into rectangles per tile as the ground is. Carve the
  bed first and give the water the carve's height plus the depth you want; the area may be loose
  (the surface stops where the ground rises above it).
- **A water sweep**, for streams: a path whose sweep's material is water, usually
  [draped](#draped-paths) with `downhill` so it never runs uphill, cutting its own bed.
- **A waterfall**: a short sweep of a single upright profile edge hanging from a cliff's lip to
  the pool below, with `"double_sided": true` so it is drawn from behind too.

The body walks through water and stands on the bed under it. The game decides what water does
(the movement garden wades: it slows with depth, no swimming), and for that the kit writes
`NAME.water.bin`, every upward water face of the world (the pond, the pool, the streams' tops),
which `NAME.akr` embeds and opens. `stdlib/wpwater.akr`'s `wp_water(p, above)` answers whether a
point is under a water surface, with the surface's `level`, the `depth` of the point below it and
the material tag's surface byte (`collision.surfaces`, as any tag's) in `wp_water_hit`:

```
if wp_water(pl.pos, 0.0) { slow_by(wp_water_hit.depth) }
```

A cart that opens a world without water after one with it calls `wp_water_close()` (the
movement garden does, switching between the garden and the shrine). `wp_water()` tests every water
triangle's bounds (about 12 cycles each; the example's 512 triangles, all of
its water, cost about 6,000 cycles a query, and a game that queries once a frame from the feet
can afford it). A material with `water` cannot be painted or used for a cliff's wall.
`report.json`'s `terrain` has `water_triangles`.

### Sweeps

```json
"paths": {
  "sando": {"points": [[76, 0, 4], [76, 0, 40], [76, 12, 74], [76, 12, 84]],
            "sweep": {"profile": [[-3.2, -0.6], [-2, 0], [2, 0], [3.2, -0.6]],
                      "materials": ["stone_dark", "stone", "stone_dark"],
                      "stairs": {"rise": 0.3}, "caps": true}}
}
```

A path's `sweep` carries a **profile** along it: points `[x, y]` across the path, x to the right
of its direction and y up from its line, each edge facing to its left (an edge drawn left to right
faces up). `material` gives every edge one terrain material, `materials` one each. The path stays
world data as before ([Paths](#paths)); the sweep adds geometry and collision.

| Sweep property | Meaning |
|---|---|
| `profile` | 2–64 points; consecutive points differ |
| `material` / `materials` | Terrain materials: one for all edges, or one per edge |
| `stairs` | `{"rise": r}`: each sloping segment climbs in equal steps no higher than r instead of a slope (a run of 3 m with `rise` 0.3 is 10 risers between 11 treads; the path's points are the landings) |
| `caps` | Close an open path's two ends with the profile's outline, fanned from its first point. Default false |
| `ground` | Drawn in the ground pass. Default: true unless the path is `raised` or its material is water |
| `collision` | Its faces are collision triangles. Default true; water never has collision |
| `double_sided` | Its faces are drawn from both sides (a waterfall seen from behind). Default false |

Cross-sections are made at the path's points (mitred at a corner, so the profile keeps its width;
a turn of more than 120° is an error), where its line crosses a cell edge, and at both heights of
every riser. The strip between two cross-sections goes to the cell holding the middle of its line,
so a cross-section on a seam is shared and the two cells' pieces meet there exactly. A sweep may
reach past its cell by at most the world's `overhang` (an error names the point). The line is the
path's own: a sweep lies on the ground because the ground is shaped to it, with a `bed`, or
because the path is [draped](#draped-paths) over the ground. One sweep piece is a placement per
cell per path.

**Lying on the ground: the bed.** A sweep lying on terrain and the terrain under it would be
coplanar and fight in the depth buffer (RENDERING.md, "Precision": a floor seen at 11° needs about
39 cm of separation at 128 units). So the profile's top is the path's line, its sides slope down
below it, and a `bed` operation lowers the ground under the path by more than the sides go down.
The rule that keeps the ground out of the sweep's top: the bed's `width` covers the top's width,
since the ground between two samples is their interpolation, and the samples within a quad of the
top's edge must be at the bed's height; the profile's sides should reach as far as the bed and its
falloff, so that the ditch is covered. In the example the sando's top is 4 m wide, its sides
slope 26° to 3.2 m out and 0.6 m down, and its bed is 5 m wide, 0.6 m deep with a falloff of 3:
the ground under the top is 0.6 m below the path's line, so 0.6 m below the flat part and at
least 0.3 m below every tread (a tread lies at most one rise below the line). Sides gentler than the game's slide angle
let the body walk on and off the path; steep sides are walls it cannot step over.

### Draped paths

```json
"trail_low": {"points": [[112, 12], [104, 34], [86, 54], [77, 70]],
              "drape": {"bed": {"width": 3.2, "depth": 0.3, "falloff": 2}},
              "sweep": {"profile": [[-2.2, -0.3], [-1.2, 0], [1.2, 0], [2.2, -0.3]],
                        "materials": ["earth", "gravel", "earth"], "caps": true}}
```

A path with `drape` lies on the terrain: its points need only x and z (`[x, z]`; a `y` is
ignored), and the kit resamples its line every `step` units and gives each point the height of
the ground there (the highest field), as the fields' operations left it. Then it smooths the
heights, lifts them, and cuts the path's own bed into every field before the heights are final.
The pack stores the draped line, so the game's path queries follow the ground too. Paths drape in
the world file's order (a later one lies in an earlier one's bed where they cross).

| `drape` property | Meaning |
|---|---|
| `step` | Resample every `step` units. Default: the finest field's spacing |
| `smooth` | Passes of a 1-2-1 smoothing along the line. Default 2 |
| `lift` | Added to the ground's height. Default 0 |
| `downhill` | The line never rises from its first point to its last: where the ground rises, the bed cuts through it (a stream). Default false |
| `bed` | `{"width", "depth", "falloff"}`: the `bed` operation along the draped line, so the sweep lies in it ([the bed rule](#sweeps)). A field's `bed` operation may not name a draped path |

For a trail, a bed as wide as the sweep's top and as deep as its sides go down keeps the ground
out of the sweep, as for a sando. `report.json`'s `terrain.draped` has the number of points of
each draped path. Draping uses the fields only (sweeps and placements are not ground for it), and
a draped path must pass over a field at every point.

### On the ground

A placement's or an entity's `position` may be `[x, z]`: it stands on the ground, at the highest
terrain or sweep floor there (collision floors of the fields and sweeps, not of placements). Or
it is `[x, y, z]` with `"drop": true`: at the highest such floor at or below `y` (on a lower
terrace, under an overhang). `lift` is added after either (a coin floating 1 m up; a tree sunk
0.15 m into a slope), and is an error with a plain `[x, y, z]`. A position with no floor under it
is an error naming the point. (`mei_world.py floor FILE X Z ...` answers the highest floor under
points from the command line, placements' floors included.)

### Scatter

```json
"scatter": {
  "forest": {
    "assets": [{"asset": "maple", "weight": 3, "collision": "park_tree_col"},
               {"asset": "park_tree", "weight": 2, "collision": "park_tree_col"}],
    "area": {"rect": [0, 0, 128, 192]},
    "spacing": 7, "fill": 0.8, "seed": 11, "lift": -0.15,
    "exclude": [{"circle": [112, 10, 9]}, {"rect": [0, 116, 24, 192]}],
    "clearance": 1.5, "max_slope": 32, "chunk": 16, "cull": 48, "coarse": 22
  }
}
```

The world file's `scatter` sets props over an area by density, on the ground, with no
placements to write. Each is laid on a lattice of `spacing`-unit squares (the world's, so editing
one part of an area does not move the rest): a square keeps a candidate with probability `fill`,
moved from its centre by up to `jitter` of the spacing; the candidate is dropped outside the
area, in an exclusion, within `clearance` of any sweep's edge (trails and streams clear
themselves), over water, where it would not stand on what `on` allows, or on ground steeper than
`max_slope`. The asset is chosen by weight, the yaw at random in whole degrees. Every choice comes
from SHA-256 of the seed, the scatter's name and the square, so the same recipe scatters the same
props everywhere, and each prop's ID (`NAME_I_J`) lasts while its square keeps it.

| Property | Meaning |
|---|---|
| `assets` | 1–32 of `{"asset", "weight" (default 1), "collision" ("self", "none" (default) or a collision asset), "lift"}` |
| `area`, `exclude` | An area as the operations' (`rect`, `circle`, `polygon`, `path` with `width`); up to 256 exclusions |
| `spacing`, `fill`, `jitter`, `seed` | About how far apart; the fraction kept (default 1); how far from the square's centre (default 0.8); the pattern (default 0) |
| `clearance`, `max_slope`, `on` | Kept off sweeps by this much (default 1); not on ground steeper than this (degrees, default 35); `terrain` (default), `sweeps` or `both` |
| `yaw`, `lift`, `layer` | Degrees or `"random"` (default); added to the height on the ground; a layer of the world |
| `chunk` | Props are merged per square of 4, 8, 16 (default), 32 or 64 units: one placement each |
| `coarse`, `cull` | From `coarse` units a chunk draws its assets' level 1 (assets with [`lod`](#levels-of-detail)); from `cull` units it is not drawn |
| `lod` | `"assets"`: a chunk takes its levels from its assets instead (with `cull` as a last cull mark); not with `coarse` |
| `thin` | With `"lod": "assets"`: `{"distance", "keep", "scale"}`: from `distance` a chunk draws only a seeded share `keep` of its props, each grown by `scale` (default 1) about its base |

**Budgets.** A forest of placed trees would cost the reader about 500 cycles a tree; scatter
merges each cell's props per scatter, layer and chunk into one mesh at the cell's centre ([merged
scatter](#merged-scatter), split between props at 2,048 vertices or 4,000 faces), and gives it
the chunk's levels: the merged level 1 of its assets from `coarse` and nothing from `cull`, with
a band of 2. So a forest costs the chunks near the eye at full detail, a ring beyond them coarse,
and nothing past `cull`.

**`"lod": "assets"`.** `coarse` gives every asset in a chunk its level 1 at one distance and
ignores the assets' own switch distances, their further levels and their cull distances: a tree
with a second far level, or a fern that should vanish at 45 units, cannot say so. With `"lod":
"assets"` a chunk has a level wherever one of its assets switches level or is culled, at that
asset's own distance (its recipe's, or the world's `lod.assets` override, times `lod.scale`);
each level is the merge of every prop at the level its asset draws there, without the props
culled by then, and the chunk is culled once all of them are (or at the scatter's `cull`, which
stays a cap). The distance is the chunk's, eye to the centre of its sphere, as for any placement.
Distances closer than twice the band (2) to the one before are moved out to keep the reader's
rule, so a change comes up to a few units late, never early; a chunk holds at most 8 levels.
`thin` is for forests seen from far off: from its distance only a seeded share of the props is
drawn (`keep`, chosen by a hash of each prop's ID, so a prop is kept or dropped the same way at
every level and in every build), each grown by `scale`; `keep` 0.5 and `scale` 1.2 draw half the
trees at 72% of their cover. A chunk's stand-in level ([Stand-ins made by the
kit](#stand-ins-made-by-the-kit)) is thinned too. The shrine's forests use both; without `lod`
a scatter is built exactly as before. Each prop keeps its own collision (tagged 0xFFFC). Assets with
repeating textures cannot be scattered (a merged chunk has no texture window table). The World
Checker judges scatter like any placement: a cell's `cell_triangles` counts every chunk's level 0,
so a forest's cells need that threshold raised, while its views' budgets see the levels actually
drawn. A chunk smaller than a cell culls more finely; a larger one costs fewer placements.
`report.json`'s `scatter` lists per scatter what was placed, per asset and per cell, the
candidates dropped and why, the chunks and their triangles; a scatter that places nothing is a
warning (`scatter_empty`).

### Materials, palettes and textures

Terrain materials are declared in `terrain.materials` with an Asset Kit material's `color`,
`class` (`surface` or `emissive`), `tag` and `share`, and are always palette-backed: a face is a
4-bit textured face sampling one texel of the world's swatch, tinted by its baked shade. Their
entries join the palette of each region that draws them, as one more asset named `terrain` would
([Palettes per region](#palettes-per-region)): entries of the same class and colour share with
the assets' (a kerb can share an entry with a building's stone), and a variant recolours them by
`MATERIAL` or `terrain.MATERIAL`. Shading is baked by `terrain.lighting`, an Asset Kit lighting
object (default `"mode": "vertical"`, as the assets are; terrain is never turned, so
`directional` is also allowed).

A terrain material may instead carry a **texture** ([Textured terrain](#textured-terrain)).

### Textured terrain

Built (2026-10-05). A terrain material with a `texture` draws an Asset Kit texture
([ASSETKIT.md](ASSETKIT.md#textures)) repeating in world coordinates, so its pattern runs on
across faces, tiles, cells and sweeps with no seam of its own:

```json
"floor": {"color": "#6e6236",
          "texture": {"image": "assets/art/terrain_floor.png", "scale": [2.4, 2.4], "span": 223}}
```

- **The texture** is a `pattern`, `texels` or an `image` (relative to the world file; make reads
  it as a dependency), 4- or 8-bit, with sides of 8, 16, 32, 64 or 128 texels (it repeats). No
  holes (`clear`, transparent pixels), sheets or animations.
- **Projection** `box` (the default: each face from the axis nearest its normal, so banks and
  cliffs are textured from the side) or `planar` (default axis `y`: from above); `scale` is
  world units a repeat; `offset`, `rotate` and `flip` as in the Asset Kit. The pattern is fixed
  to the world's axes, not to a path's direction.
- **Coordinates.** Texel coordinates are 8 bits and do not wrap, so each face's are shifted by
  whole repeats to start in the first. The texture is stored repeated `span` texels further each
  way (default 96; at most 255 texels a side in all, 127 tall for an 8-bit texture), and a face
  that reaches no further samples those stored repeats without a texture window. A face that
  reaches further samples the texture as loaded through a texture window (DECISIONS.md,
  "Texture windows"), up to 255 texels. Field rectangles and sweep strips of a textured material
  are kept within that windowed reach (a rectangle within its `scale` × (255 − size) / size
  units; a strip cut between its cross-sections where it would pass the stored repeats); a face
  that still reaches past 255 texels (a near-vertical quad) has its texture stretched to the
  stored repeats, with the warning `terrain_texture_stretched`.
- **Why the span.** A mesh with a texture window table leaves the reader's quicker face loops
  (LANGUAGE.md, "Performance notes": about 55 cycles a call and 10 a visible face more, and
  never the loop for meshes with nothing to clip), and a terrain piece gets a table as soon as
  one of its faces needs a window. A span that covers the largest face (a whole field tile: 16 units at
  2.4 units a 32-texel repeat needs a span of 223) keeps every piece windowless and the ground's
  draw cost exactly that of palette-backed ground; a smaller span saves VRAM (a 32-texel 4-bit
  texture is 8,385 bytes at the default span, 32,768 at 223) and costs CPU where faces are
  large. `report.json`'s `terrain.texture_windows` counts the pieces and triangles with windows.
- **VRAM.** Each textured material's stored repeats, and the texture as loaded for one with
  windowed faces, join the texture set of each region that draws it as the tiles of one more
  asset named `terrain` ([Textures per region](#textures-per-region)); equal tiles are packed
  once (two materials of one image and span at different scales share a tile). The material has
  no palette entry, except for a field's coarse level ([lod](#heightfields)), which is drawn
  untextured in the texture's mean colour (`far` in the report), a palette entry of its own.
- **Shading** is baked into the vertex colours as for palette-backed terrain; a texel is drawn
  times its face's shade.

`report.json`'s `terrain.textures` has, per textured material, the texture's summary, `scale`,
`span`, `stored` (texels), `texel_cm`, `reach` (units a face may span through a window),
`triangles`, `windowed`, `stretched` and `far`. The kit's test is
`tests/test_worldkit.py`'s `test_textured_terrain`; the shrine world
(`carts/garden/shrine/`) is the example, with 15 textured materials drawn by
`carts/garden/shrine/assets/art/draw_terrain.py`.

### Costs and checking

Every tile and sweep piece is an ordinary placement: about 500 cycles of the reader's per
placement cost, its vertices and faces, and a bounding sphere for culling; ROM is the native mesh
format's 16 + 16 × vertices + 36 × faces bytes. The World Checker checks terrain as any other
ground, from the pack: cracks and mismatched edges at seams (the seams are shared exactly, so it
finds none there), coverage, budgets per view and per cell, wrong-order pixels. It needs no
change for terrain. What it does find on terrain are narrow walls between floors: where a steep
face's tip meets floors on both sides (a sweep's steep side, a cap, a bank cut by a bed), a point
query falls through for a few centimetres. The diagonal rule above removes the ones inside a
single quad; the rest are the recipe's shapes, and a gentler side or bank removes them.

### The example: shrine grounds

[`examples/worlds/shrine_grounds`](../examples/worlds/shrine_grounds): 128 × 128 units in four
64-unit cells, drawn in depth mode, on the movement garden's game schema. A hill rises in four
terraces (3, 6, 9 and 12 m, banks of 2 m, walls) to a summit court with the shrine hall; a stone
sando with 40 steps climbs the front, a gravel path winds up the back through trees, two ramps
(10° and 27°) and a slide slope (37°) cross the west terraces; a pond, a storehouse and a
cemetery on a gravel plinth sit on the lower ground. Its numbers (`report.json` and the World
Checker, default settings, 512 views):

| | |
|---|---|
| Field | 4,096 quads at 2 m in 16 tiles; level 0 2,079 triangles (25% of 8,192), coarse level 1,485 |
| Sweeps | sando 508 triangles (40 risers), back path 46 |
| Cells, triangles drawn | 296, 802, 1,430, 1,602 (the threshold is set to 2,000) |
| Pack | 547,680 bytes |
| Views: triangles | median 617, peak 1,800 (of 4,000) |
| Views: GPU cycles | median 250,198, peak 411,876 (of 1,600,000) |
| Views: draw CPU cycles | median 180,660, peak 402,670 (of 600,000) |
| Coarse tiles drawn | in 250 views, 873 placements |
| Coverage errors, wrong-order pixels | 0, 0 |
| Static findings | 7 cracks of the kind above (2 at the sweeps' caps, 5 where beds cut banks and ramps); none on a seam |

The movement garden's controller (carts/garden, built against this world with its world import
changed) walks it as designed: up the 10° and 27° ramps onto the terraces; held at the foot of a
56° bank (walls); sliding back off the 37° slope (over its 30° slide angle) and off it when
standing on it; up all 40 steps (0.3 m risers, a 0.32 m step) to y = 12; along the back path to
the summit; and across the sando from the side, down its bed and up its 26° side. Screenshots
are in [`examples/worlds/shrine_grounds/screenshots`](../examples/worlds/shrine_grounds/screenshots).

### The example: forest mountain

[`examples/worlds/forest_mountain`](../examples/worlds/forest_mountain): 128 × 192 units in six
64-unit cells, depth mode, on the movement garden's game schema (the same `garden.game.mochi` as
shrine grounds'). A torii at the south gate; a draped gravel trail climbs a wooded slope to a
ford; a stream, draped downhill with its own bed, comes down from a pool under a 14 m cliff band
(rock, overhang 0.8, lip 1.5) that crosses the world east of x = 24, where a 19 m waterfall (a
double-sided water sweep) falls from the lip; a second trail climbs the switchbacks west of the
cliff to the plateau and its shrine hall; a pond (a carve and a water operation) lies to the
south-west. 302 trees and 70 boulders are scattered, clear of the trails, streams, water, the
gate's clearing and the switchbacks. Placements and coins are given as `[x, z]` (coins with a
`lift`). Its numbers (`report.json` and the World Checker, default settings except
`cell_triangles` 4,000, 600 views):

| | |
|---|---|
| Field | 6,144 quads at 2 m in 24 tiles; level 0 5,493 triangles (of 12,288), 394 of them cliff walls, 68 water; coarse level 3,187 |
| Sweeps | trails 226 and 514 triangles (draped to 37 and 84 points), streams 222 and 222, waterfall 2 |
| Water | 512 upward triangles in `forest_mountain.water.bin` (28,676 bytes) |
| Scatter | forest: 302 trees in 90 chunks of 16, 10,500 triangles at level 0 (dropped: 45 excluded, 40 near a sweep, 11 over water, 2 steep, 25 outside the area, 1 with no floor); rocks: 70 in 24 chunks of 32, 1,400 triangles |
| Cells, triangles drawn | 2,528 to 3,803 (threshold 4,000) |
| Pack | 2,091,904 bytes |
| Views: triangles | median 1,242, peak 3,131 (of 4,000) |
| Views: GPU cycles | median 331,526, peak 563,538 (of 1,600,000) |
| Views: draw CPU cycles | median 314,926, peak 620,135 (of 600,000: 3 views over, in report mode) |
| Coarse and culled | coarse placements drawn in 529 views (4,635); 8,516 placements culled by distance |
| Coverage errors, wrong-order pixels | 0, 0 |
| Static findings | 10 cracks of the kind [above](#costs-and-checking): 3 at scattered props' collision on slopes, 4 at the upper trail's switchback mitres, 2 at a boulder placed on the trail, 1 at the pond's bank; none on a seam. 4 far cells without stand-ins |

The far forest is culled, not drawn coarse, past 48 units: from the plateau the far slope shows
bare ground, which a backdrop or stand-ins would cover. The movement garden's controller, built
against this world, walks the draped lower trail from the gate to the ford's bank (y 8.46);
wades the ford, 34 ticks in water, `wp_water` reporting 0.5 m at the deepest; is held at the foot
of the cliff band (z 117.7 against the wall at 118, pushed by walls for 486 ticks); and climbs the
switchbacks to the plateau (highest y 38.0). The console test (`tests/worldkit/forest.akr`) reads
floors on the plateau, under the cliff and on the trail, and the pond's and pool's water.
Screenshots, with a top-down view of the collision, are in
[`examples/worlds/forest_mountain/screenshots`](../examples/worlds/forest_mountain/screenshots).

### Corrections to the reserved design

- **Several placements a cell, not one.** The reservation had one terrain piece per cell; a tile
  (by default 16 quads, 32 m at 2 m spacing) is the unit instead, so culling and levels of detail
  work on pieces of a useful size and a cell of 128 units at 1 m stays inside the 2,048 vertices
  of a mesh.
- **Terrain in a cell file stays reserved** (an error that says to put terrain in the world
  file): nothing has needed it.
- **Sweeps follow their path's line, or drape.** The ground is shaped to the path with a `bed`,
  or a [draped](#draped-paths) path takes its heights from the ground as the operations left it
  and then cuts its own bed, so the order the reservation worried about (the ground before the
  beds that depend on it) is the build's order.

## Streaming without a disc

**Decided.** Cart ROM is memory-mapped, so geometry and collision are read in place, as on the
N64, not loaded from a disc as on the PlayStation or in GTA. `embed` already places files in ROM
and `mesh()` draws a `*Mesh` that points into ROM (LANGUAGE.md, "Memory" and "Mesh format").
"Streaming" here means three things only:

1. choosing which cells to draw, and at what detail, and which to collide with;
2. swapping textures and palettes in the 2 MB of VRAM when the player crosses into a region;
3. spawning and retiring entities as their cells become active and inactive.

Cells are position-independent blobs behind an index: every reference inside a pack is an
offset from the pack's start, so cells can be rebuilt one at a time and the pack can be embedded
anywhere. Audio needs no loading at all: sample data may be read from RAM or ROM
(DECISIONS.md), so a region's audio bank is a table of ROM addresses.

One limit worth knowing: a GPU packet's link to the next packet is 24 bits (`hdr & 0xFFFFFF` in
`src/core/gpu.c`), so with ROM moved to `0x08000000`, packet lists cannot be chained through ROM.
This design never needs that. Mesh and collision data are read in place; packets are built each
frame in the RAM packet arena (160 KB) as they are today.

### ROM

Mesh size is 16 + 16 × vertices + 36 × faces bytes. A shop-row building of 300 vertices and 400
triangles is 16 + 4,800 + 14,400 = 19,216 bytes, about 19 KB. A 4-bit texture slot is 32 KB.
The old 2 MB cart (less its code, audio and the system's needs) held on the order of a hundred
such meshes: enough for the test room and one block, not for a city. With the 64 MB ROM that has
landed, a cart holds about 3,500 of them before textures and audio, and instances share one copy.
ROM stops being the limit; VRAM and the frame budget remain.

### Regions and the VRAM split

**Decided.** A region (district) owns a texture set, named palette variants, an audio bank and a
backdrop. VRAM cannot hold two regions' textures at once, so there is a shared common set plus
one set per region, and swaps happen at natural seams: underpasses, covered arcades, station
concourses.

VRAM is 2,048 KB since 2026-10-05 ([DECISIONS.md](DECISIONS.md#vram-at-2-mb); it was 1,024 KB,
spec p. 11; PLANES.md "Memory map"):

| Use | Size | Note |
|---|---|---|
| framebuffers A and B | 300 KB | 2 × 153,600 bytes |
| spare | 4 KB | |
| palette bank 0 | 8 KB | colours 0–4095 (4-bit palettes 0–255); palette 255 (colours 4080–4095) is the font's |
| Horizon Engine line tables | 8 KB | convention |
| Horizon Engine pages 10–15 | 192 KB | maps and atlases for backdrops |
| texture slots 0–15 | 512 KB | 32 KB each (one 4-bit 256×256 texture; an 8-bit one takes two) |
| texture slots 16–31 | 512 KB | the second megabyte, `0x500000`–`0x57FFFF` |
| palette bank 1 | 8 KB | colours 4096–8191 (4-bit palettes 256–511, 8-bit 16–31); polygons only |
| free | 504 KB | pages 49–63 and the rest of page 48: plane atlases and maps, or a cart's own use |

300 + 4 + 8 + 8 + 192 + 512 + 512 + 8 + 504 = 2,048. Slot 15 holds the fonts (rows 0–66), so 31
whole slots are free for polygons, 30 of them for regions by default (slot 14 holds the world's
swatch row and, in the garden, the star).

*The kit's default split:* every region may use slots 13–0 and then 16–31 (30 slots, 983,040
bytes) and 4-bit palettes 0–254 and 256–511; slot 14 the swatch and effects, slot 15 and palette
255 the fonts. Regions' palettes are disjoint ([Palettes per region](#palettes-per-region)); their
texture sets share the slots and are swapped. The kit enforces whatever split the world recipe
declares and reports use per region.

*The first placeholder split* (with 1 MB, never built): slots 0–5 common, 6–13 region, 14 effects
and HUD, 15 fonts; palettes 0–63 common, 64–191 region, 192–254 backdrop, HUD and effects.

Swap cost: filling all 16 slots costs about 900,000 cycles (spec p. 11), so about 56,000 a slot
(PLANES.md gives the same for a 32 KB atlas). A region's 8 slots are about 450,000 cycles, nearly
half a frame's 1,000,000; all 30 a region may have are about 1,700,000, nearly two frames. *Proposal:* swap one slot a frame (about 6% of the CPU) over 8 frames,
plus the region's palettes, while the player is inside a seam. During those frames nothing on
screen may use region textures, which the kit can check (see [Verification](#verification)).

**Found while checking: sight lines cross region boundaries.** From a downtown rooftop the
electric town is visible while its textures are not loaded. *Proposal:* stand-ins use only the
common set and common palettes, so any cell's stand-in can be drawn whichever region is loaded,
and a cell in a region that is not loaded is always drawn as its stand-in, even when near. Region
boundaries that the player can approach without passing a seam then show stand-ins at close
range; the layout should avoid that (a viaduct, a wall of buildings, a river), and the kit can
report where it happens. Built: the kit's stand-ins draw far colours (palette entries of their
region, every region's palettes being loaded at once) and, for cutouts, the stand-ins' own
texture set, which every region's set holds ([Stand-ins made by the kit](#stand-ins-made-by-the-kit)).

## Sight lines and stand-ins

**Decided.** Every cell has a low-detail stand-in, because the 1,024-bucket ordering table
mis-sorts long sight lines and far cells must be cheap.

The arithmetic behind "mis-sorts": `camera_clip(near, far)` maps view depth linearly onto 1,024
buckets, so a bucket is (far − near) / 1,024 deep (`stdlib/gfx.akr`). At the defaults (0.1 to
100) that is 0.098 units. A rooftop view out to 400 units in one pass makes every bucket 0.39
units deep, deeper than a kerb or a step, and the Asset Kit's checks of an isolated asset at
far = 100 no longer describe it. Faces in one bucket draw in reverse insertion order (spec p. 15).

*Proposal: two passes split by cell.* The runtime draws far cells' stand-ins first with their own
`camera_clip` range, flushes them (`ot_flush()` exists), then draws the near cells with a tight
range. Two passes give two full sets of 1,024 buckets. With a near range of 0.1 to 96 a bucket is
0.094 units; with a far range of 64 to 400, 0.33 units, coarse enough only for stand-ins. This is
correct when the near set is a convex region of cells containing the camera: any line of sight
leaves a convex region once and never re-enters, so along every ray near geometry comes before far
geometry. A 3 × 3 block of cells around the camera's cell is convex. Placements that overhang a
neighbouring cell weaken this, so the kit limits overhang (see [Verification](#verification)).
The near set is chosen around the camera, which may trail the player; the collision set is chosen
around the player.

**Decided: ground first.** Within the near cells, the placements a level marks as ground are drawn
in a pass of their own before the rest (the world pack's ground pass), so nothing standing on the
ground sorts behind a large ground face; see [Ground](#ground) and WORLDPACK.md, "Ground".

The far backdrop (skyline, sky gradient, distant hills) belongs on the Horizon Engine, the plane
chip ([PLANES.md](PLANES.md)): a tile plane and a backdrop line table cost no GPU cycles and no
triangles.

**Fixed point limits world coordinates.** `length`, `normalize` and the dot product overflow for
vectors longer than about 181 (LANGUAGE.md), and Tsumiki told carts to keep levels within about
±90 units. A city is far larger. *Proposal:* the pack stores every cell's contents in cell-local
coordinates around the cell's centre, and the runtime renders camera-relative: the camera's cell
centre is the origin for the frame, and each placement's position is its local position plus an
integer number of cells. Collision queries happen in the player's cell's frame. With 64-unit cells
local coordinates stay within ±32 plus overhang.

**No per-object culling today.** `mesh*()` transforms every vertex of every mesh it is given (26
cycles a vertex, 40 with fog) before culling faces. The runtime needs a bounding-sphere or box
test per placement and per cell before calling `mesh*()`. The kit computes the bounds.

### A frame budget (placeholder)

From LANGUAGE.md "Performance notes": a vertex is 26 cycles, a back-facing face about 48, a
visible face about 130–163, a face clipped at the near plane about 4,000 and one clipped to the
guard band about 3,000. Suppose world drawing gets 500,000 of the 1,000,000 CPU cycles (the
spec's "What the budget buys" leaves half for game logic). For closed meshes with about one vertex
per two faces and half the faces facing away, a submitted face costs about
0.5 × 145 + 0.5 × 48 + 0.5 × 26 ≈ 110 cycles, so about 4,500 faces, of which about 2,250 are
visible. Ten faces clipped near the camera take 40,000 of that. That leaves roughly 4,100 submitted
faces a frame, near and far together. (This was 2,000 when the CPU had 500,000 cycles a tick,
before [it went to 60 MHz](DECISIONS.md#the-cpu-at-60-mhz); the per-cell numbers below were set
then.)

For comparison, Tsumiki's Playroom ran at a median of 903 triangles, peak 1,555, with CPU at
46% median and 67% peak of 500,000 cycles (TSUMIKI.md, removed; in git history before `ad01707`).

With the CPU at 1,000,000 the GPU binds about as soon: 2,250 visible triangles cost 90,000 cycles
of setup, and 2.5 screens of textured fill (192,000 pixels × 2) cost 384,000, about 47% of the
1,000,000 budget of then (24% of the 2,000,000 since 2026-10-03), with blended faces and overdraw
beyond that.

*Placeholder per-cell budgets:* near pass 1,600 faces, of which about four of the nine near cells
are in view, so about 400 faces per cell as drawn from any one camera; far pass 400 faces, so
stand-ins of at most 32 faces if about 12 of them are in view. These are starting numbers for stage 2 to
measure, not limits to design to.

### Stand-ins made by the kit

```json
"standins": {"distance": 128}
```

Authoring a stand-in per cell is work that goes stale when the cell changes, and a stand-in that
is not the cell's own geometry changes the picture when the cell comes near: a canopy sheet
stands in for trees, then the trees appear. With `standins` the kit makes a stand-in for every
cell that names none, from the cell itself: each placement, scatter chunk and terrain tile at
the level it draws at `distance` (times `lod.scale`), without what is culled by then, merged into
one mesh around the cell's centre (placements in a layer are left out, and sweeps unless
`"sweeps": true`: the field under them stands in). A far ground level ([Levels of
detail](#levels-of-detail)) is made again for it without the skirts between the cell's own
tiles, which meet exactly. So when the cell moves from the far ring to the near ring, what was
drawn as its stand-in is drawn again as its placements, at their levels for that distance.

In a world with one region the merged mesh keeps its faces' textures. Faces with repeating
textures lose their window in the merge (a merged mesh has no window table; the warning
`standin_windows` names the cells). A stand-in is drawn whichever region is loaded, so in a world
with several regions (built 2026-10-05) every face that samples the region's texture set is drawn
instead in its tile's **far colour**, the mean of its texels (as a textured field's coarse level
is): a palette-backed face of the world's swatch. A region's far colours are reduced to at most 30
surface and 15 emissive ones (the Asset Kit's median cut), each a palette entry of the region,
shared like any entries and listed in its palette as `far.ASSET.MATERIAL`; a variant tints them by
class. A cutout face (foliage) is drawn solid in its colour, unless the stand-ins have a texture
set of their own (below). A cell more than one mesh holds from that distance (2,048
vertices, 4,000 faces) is an error at `/standins/distance`. `report.json`'s `standins` lists per
cell the pieces merged (`placements`), the pieces a cap left out (`left_out`) and the triangles as
drawn (a quad is two), with the cell's `cap` and `ground` when it has them. The shrine's stand-ins
are 81–302 triangles (with [quads](#quads)); the World Checker's `standin_triangles` threshold
applies as to any stand-in.

```json
"standins": {"distance": 128, "triangles": 90, "ground": 32,
             "cells": {"c2_4": {"triangles": 140}}}
```

Two options keep stand-ins small where a cell holds much more than its far view needs:

- `triangles` (1–4,000) caps each stand-in's triangles as drawn. The cell's ground goes in first,
  always: its field tiles and water, its `ground` placements and, with `"sweeps": true`, its
  ground sweeps ([Ground](#ground)). Then the rest goes in largest first, each piece whole or not
  at all, skipping what does not fit and trying the next. A piece's size is its bounding box's
  height times its longer horizontal side (as placed, with a scatter prop's thinning `scale`), so
  tall and wide things, the silhouette, go before low and small ones; ties go to the larger
  footprint, then to the placements' order. A scatter chunk goes in prop by prop, the props of
  equal size in a seeded order (by each prop's ID, as `thin` chooses), so a cap keeps a
  spread-out share of a wood rather than one corner of it. A sweep that is not ground (raised, or
  `"ground": false`) is a piece like the others. If the ground alone is over the cap, the
  stand-in is the ground alone and the warning `standin_over_cap` names the cell, its ground's
  triangles and the cap.
- `ground` (4, 8, 16, 32 or 64 units) resamples the cell's field tiles on one grid of that many
  units over the whole cell, as the far ground levels do ([Levels of detail](#levels-of-detail)),
  in place of the level they draw at `distance`: on a 64-unit cell, `32` is 8 triangles where the
  ground is flat, plus skirts on the cell's border where a straight edge stands above the ground
  beside it. Where the grid cannot be laid over the whole cell (a grid point with no field under
  it, or more tiles than one mesh holds), each tile is resampled on its own (`nx = round(tile /
  grid)`, at least one square), and a tile that cannot be keeps its own coarsest level. Each grid
  point takes the highest ground under it, so a cliff becomes a slope one grid square wide whose
  top edge may move by up to a square, and its overhang is gone. A field's water is a piece of
  its own and is kept as it is, over the resampled bed; where the coarser bed rises above the
  water's surface (a narrow stream between banks), the water is hidden there.

`cells` overrides `triangles` and `ground` per cell ID (a cell not in the world is an error). A
world without these options builds as before, byte for byte. In the shrine town's grey box
(64-unit cells, far ground at 16, built as its three strip worlds), `{"distance": 128, "sweeps":
true}` gives stand-ins of 90–540 triangles; adding `"triangles": 90, "ground": 32` gives 28–90,
except cell `c3_2`, whose ground alone is 103, 85 of them its water, which `ground` does not
resample (`standin_over_cap`).

**The stand-ins' own texture set** (built 2026-10-05; the common set proposed in [Regions and the
VRAM split](#regions-and-the-vram-split), for cutouts only). Drawn solid in a far colour, a
tree's two crossed cards are two dark slabs, and a fence or a lattice a wall:

```json
"standins": {"distance": 128, "textures": {"slots": "0", "budget": 32768}}
```

With `textures`, every 4-bit cutout texture (one with holes, not animated) of the levels the
stand-ins draw (each placement's and scatter prop's level at `distance`, not culled by then, not
in a layer) is packed once into these slots (default `"0"`, budget their 32,768 bytes a slot) and
left out of the regions' own sets. Its slots are taken out of every region's slot list, and every
region's set holds the same image of them, so the cards are in VRAM whichever region was entered
last; wp_region_enter() copies them with the region's other slots (no reader change). Each region
holds its own copies of the palettes of the cards it draws, after its texture palettes, so its
variants tint them as its own. A stand-in then keeps those faces textured, cut out as near; with
[haze](#haze) it draws them through a second copy of those palettes that the variants haze. Over
the budget, the build fails at `/standins/textures` naming each texture and its bytes.
`report.json`'s `standins.textures` gives the set's slots, budget, bytes (as `vram_bytes` and
`vram_bytes_allocated` on the 8-texel grid), tiles, palettes and bytes per `ASSET.MATERIAL`; each
region's `textures` counts its own tiles only. In a world with one region nothing changes: its
stand-ins keep every texture already.

In the shrine town (two regions): 15 tiles, 23,764 bytes (27,488 on the grid) in slot 0: the
far cards of the cedar, giant cedar, hollow sacred cedar, ginkgo, maple, small maple and zelkova
(5,408 for each 96 × 96 card, 2,720 for the cedars' 32 × 128 one), the hollow cedar's leaf
cluster, and the lattices, grilles and railings of the fire tower, the canal grille, the arched
bridge, the pool fence, the watermill's wheel, the platforms and the ramen shop's treads. The
regions' own sets fell by those tiles (the town from 252,963 to 243,100 bytes, the shrine from
105,825 to 87,171). The full check's peaks did not move (GPU 908,916 to 909,169 cycles).

## Game data and stable IDs

**Decided.** Goals, collectibles, switches, triggers and missions are entries with a type, a
stable ID and parameters. The game defines the types and supplies a schema; the kit validates
recipes against it and otherwise does not interpret them. Stable IDs matter because each goal has
a saved bit that must survive level edits, as the Asset Kit asks agents to preserve node IDs. The
stakes are higher here: an Asset Kit ID only labels a report; a World Kit ID addresses a player's
save.

**Built: the game schema.** A small file the game owns, in the kit's own restricted format so
that parameters can be packed into fixed records the cart reads without parsing. It is written in
**Mochi**, a tiny type-description language (`NAME.game.mochi`):

```
// The game schema of a small city game.
game city

probe {
  radius            = 0.3
  height            = 1.6
  step              = 0.32
  floor_max_degrees = 40
}

worlds city, mall

saved type coin

saved type challenge_switch {
  course:      ref
  time_window: any | day | night = any
  reward:      u8 = 1
}

type camera_zone {
  size:     vec3 = [8, 4, 8]
  mode:     follow | fixed | rail
  priority: s16 = 0
}

type door {
  world:  world
  spawn:  name = entrance
  locked: bool = false
  key:    ref?
}
```

Field types are `bool`, `u8`, `s16`, `s32`, `fixed`, `vec3`, `name`, `world` (a world of
`worlds`), `ref` (an entity ID) and enums, written as their values separated by `|`. A field is
required unless it has a default (`= value`); a `ref` is required, `ref?` may be none, and a ref
never has a default. Types are numbered in the order they are written; `world` values are indexes
of `worlds`. The kit checks that references resolve, without knowing why they exist, and emits
the type numbers, an Akari `struct` per type with parameters and an `enum` per enum parameter in
`GAME.game.akr`, which every world of the game imports. `saved` asks the kit for a persistent bit
per entity of that type. `probe` describes the player's body: the kit classifies collision by
`floor_max_degrees` (and `ceiling_max_degrees`, default 45) and copies walls `radius` past cell
edges; the World Checker samples cameras with its `radius`, `height` and `step`, and does not
report a crack that the game's floor query bridges with its `bridge` ([Cracks](#cracks)).
`GAME.game.akr` exports it as `GAME_PROBE_RADIUS` and `_FLOOR_MAX_DEGREES`, `_HEIGHT`, `_STEP`
and `_BRIDGE` when the schema gives them, and `_CEILING_MAX_DEGREES` (always: the angle the kit
used), so a cart moves the same body the level was checked for. It is geometry, not movement
rules.
Everything else (what `night` means, whether a coin respawns) is the game's. Entity IDs are
world-wide, so a `ref` and a saved bit can name any entity.

*Mochi is a front end, not a second format.* The kit translates it into the JSON form (format
`mei-world-game`, whose JSON Schema `schema` prints under `$defs/game`, with Mochi's grammar, rules
and an example under `$defs/game/x-mochi`) and everything downstream sees only that. A game schema whose file does not end in `.mochi` is read as JSON, which stays
fully supported; `convert` turns one form into the other, and JSON → Mochi → JSON gives the same
schema. It describes data only: no expressions, conditions, includes or macros, and world and cell
recipes stay JSON. Each construct is one JSON construct:

| Mochi | JSON |
|---|---|
| `game city` | `"format": "mei-world-game", "version": 1, "name": "city"` |
| `probe { radius = 0.3  floor_max_degrees = 40 }` | `"probe": {"radius": 0.3, "floor_max_degrees": 40}` |
| `worlds city, mall` | `"worlds": ["city", "mall"]` |
| `saved type coin` | `"coin": {"saved": true}` in `types` |
| `type door { ... }` | `"door": {"params": {...}}` |
| `count: u8 = 1` | `"count": {"type": "u8", "default": 1}` (likewise `bool`, `s16`, `s32`, `fixed`, `vec3`, `name`) |
| `course: ref` / `key: ref?` | `{"type": "entity_ref", "required": true}` / `{"type": "entity_ref"}` |
| `exit: world = city` | `{"type": "world_ref", "default": "city"}` |
| `mode: follow \| fixed = fixed` | `{"type": "enum", "values": ["follow", "fixed"], "default": "fixed"}` |
| `kind: \| only` | `{"type": "enum", "values": ["only"]}`: a one-value enum starts with `\|` |

The rest of the syntax: spaces and line breaks are free and `//` starts a comment; `:` gives a
type, `=` a value; numbers are written as in JSON (`1` and `1.0` stay an integer and a float);
vec3 defaults are `[x, y, z]`; `true` and `false` are bool defaults; names, enum values and world
names are bare and follow the kit's name rule, `^[a-z][a-z0-9_]{0,47}$`. There are no reserved
words, so an enum value may be `u8` (`kind: u8 | s16`, where the `|` makes it an enum) and a field
may be called `world`. `game` comes first; `probe`, `worlds` and types follow in any order. The
probe requires `radius` and `floor_max_degrees`; `height`, `step`, `ceiling_max_degrees` and
`bridge` are optional. `convert` writes the canonical style shown above (probe values and field types aligned,
a blank line between statements); it drops `"saved": false`, empty `params` and `"required":
false`, which mean the same as leaving them out.

Errors in a Mochi file carry `file`, `line` and `column` besides the usual `path` and `message`,
say what was expected and usually how to fix it. Errors that the kit's JSON validation finds
later (a `u8` default of 300, an enum default that is not a value, a field named after an Akari
keyword) are mapped back from their JSON Pointer to the line of the construct it names:

```json
{"ok": false, "errors": [{"path": "/types/trigger/params/count/default", "message": "Maximum is 255.",
  "file": ".../garden.game.mochi", "line": 19, "column": 21}]}
```

**Built: the ID lock file.** The kit writes `NAME.ids.json` beside the recipe and expects it to
be committed. It maps every saved entity's ID to its bit, append-only:

```json
{"format": "mei-world-ids", "version": 1, "world": "test_room", "next_bit": 3,
 "bits": {"coin_on_ledge": 0, "gate_switch": 1}, "retired": {"coin_old": 2},
 "renamed": {"coin_ledge": "coin_on_ledge"}}
```

A new saved entity gets the next bit. A deleted entity's bit is retired, never given to another
ID; re-adding the same ID gives its own bit back (it names the same goal). Renaming is a delete
plus an add unless the entity says `"was": "old_id"`, which moves the bit and records the rename;
`was` may stay in the recipe afterwards as history. A `was` naming an entity that still exists, or
one the lock has never seen, is an error, as is a lock file whose bits collide. `validate` and
`inspect` report the changes a build would make without writing; `build` writes the lock only
after its outputs are published, and `build --locked` fails instead of changing it (for CI). A save
holds up to 32,000 bytes (MEMCARD.md), so bits are not scarce: 256,000 of them.

## Day and night

**Decided: no game rules in the kit, including time of day.** The guiding principle is that the
kit knows what can be present and visible, so it can pack and verify it; it knows nothing about
when or why. The game has a day/night cycle and some goals exist only at night, but a time window
is just a game-defined parameter, as `time_window` is above. A region's palette variants are just
named variants to the kit. The game treats them as dawn, day, dusk and night and blends between
two with `palette_lerp` (`stdlib/colour.akr`, about 38 cycles a colour); the kit packs them and
previews each. Verification assumes everything that can be present is present: every entity,
whatever its time window.

**Decided: shading and emissives.** Baked vertex colours carry time-neutral shape shading only.
Emissive materials get palette entries of their own so they can brighten while everything else
darkens.

**Decided and built: palette-backed materials.** A palette colour reaches the screen only through
a texel of a textured face, so the Asset Kit draws each palette-backed material as a 4-bit
textured face sampling a solid swatch of one palette entry, with the baked shade as the vertex
tint (128 is unchanged). Palette variants and emissives then work as decided. Cost: textured
pixels are twice the GPU fill (above, still about 43% of the budget), and textured faces can only
fog toward dark colours (spec p. 17), which suits night but not bright haze. Two alternatives were
considered and not taken: recolouring vertices at run time (meshes are in ROM, so RAM copies or a
per-vertex blend costing CPU every frame), and the Horizon Engine's colour offset (`PLN_OFS`), a
uniform additive shift rather than a palette, still worth keeping for a whole-screen dusk tint on
top.

**Decided and built: rotation-neutral shading.** The Asset Kit's `lighting.mode: "vertical"`
shades by the normal's Y alone (tops light, walls mid, undersides dark), so a building placed at
any yaw is lit like every other. Every wall then has the same shade, which is accepted: colour,
textures and the palette's tint separate surfaces. If a real street looks flat, the fallback is a
few percent of variation by facing, baked in the asset's own frame. Baking a sun direction per
placement and lighting at draw time were both rejected. The World Kit warns about a placed asset
that is not baked vertically and is placed at a yaw other than 0.

*Placeholder palette cost:* blending a region's 2,048 colours every frame is 2,048 × 38 = 77,824
cycles, 16% of the CPU. Blending 256 colours a frame (9,728 cycles, 2%) refreshes the whole region
every 8 frames, which is smooth enough for a day that lasts minutes.

## Recipe format

The conventions are the Asset Kit's: `format` and `version`, names matching
`^[a-z][a-z0-9_]{0,47}$`, unknown properties and duplicate keys are errors, errors carry a JSON
Pointer `path` and a `message`, a `file` when the error is in a cell file or the game schema, and
a `line` and `column` when that file is Mochi ([Game data](#game-data-and-stable-ids)). There are
no expressions or random generation; Y is up, lengths are world units and angles degrees.
`schema` is the authoritative contract; `schema --game FILE` folds one game's entity types and
parameters in.

**Decided: units.** The tools do not enforce a scale. The convention, used by the examples and the
platformer, is one unit per metre (the Asset Kit's stool seat is at 0.8).

**Files.** A world is a world file, one file per cell, a game schema and a directory of Asset Kit
recipes. A one-cell world may keep its cell inline instead. This confirms the earlier proposal of
one file per cell: an open world of hundreds of cells in one JSON file is unwieldy for an agent and
close to the 8 MiB input limit, and an agent editing one cell should not rewrite the others. The
cell files are every `*.cell.json` in `cell_dir`, in name order, each named after its cell's
`id`; adding a cell is adding a file. The world file of the two-district example:

```json
{
  "format": "mei-world", "version": 1, "name": "two_districts",
  "game": "city.game.mochi", "assets": "assets", "cell_dir": "cells",
  "grid": {"cell_size": 32},
  "collision": {"surfaces": {"default": 0, "tags": {"ground": 1, "wall": 3, "roof": 4}}},
  "regions": {
    "downtown": {"variants": {"day": {}, "night": {"surface": {"multiply": "#506090"},
                                                   "colors": {"shop.window": "#fff0b0"}}}},
    "shrine": {"variants": {"day": {}, "night": {"surface": {"multiply": "#405080"}}}}},
  "layers": {"festival": {}}
}
```

and one of its cells, `cells/downtown_b.cell.json`:

```json
{
  "format": "mei-world-cell", "version": 1,
  "id": "downtown_b", "at": [1, 0], "region": "downtown", "standin": "block_far",
  "placements": [
    {"id": "ground", "asset": "ground_tile", "position": [48, 0, 16], "ground": true,
     "collision": "self"},
    {"id": "shop_1", "asset": "shop", "position": [48, 0, 20], "yaw": 90, "collision": "shop_col"}
  ],
  "entities": [
    {"id": "coin_b", "type": "coin", "position": [40, 1, 8]},
    {"id": "night_switch", "type": "switch", "position": [56, 0, 8],
     "params": {"target": "coin_far", "time_window": "night"}}
  ]
}
```

| Property | Meaning |
|---|---|
| `game`, `assets`, `cell_dir` | Paths relative to the world file: the game schema, the Asset Kit recipes (`NAME.asset.json`), the cell files |
| `asset_dirs` | More directories of Asset Kit recipes, searched with `assets` (a level whose grey boxes and real assets live in folders of their own), at most 256; an entry ending in `/*` is every immediate subfolder of its folder, in name order (`"assets/*"` once for a folder per asset; a glob with no subfolders is an error), and a directory named twice is searched once. A name found in two of them is an error that names both files |
| `grid.cell_size` | 16, 32, 64 or 128 units: the pack's `cell_shift`. Cell (*i*, *j*) (`at`) covers *x* in [*i S*, (*i*+1) *S*) and *z* likewise |
| `overhang` | How far a placement may reach past its cell (default 8, at most half a cell) |
| `collision.pad` | How far walls are copied past a cell's edge: at least, and by default, the probe radius |
| `collision.surfaces` | Material `tag` to surface byte; untagged faces and unmapped tags get `default` (unmapped tags are listed in the warnings) |
| `palette` | `swatch_slot` and `swatch_row` (default 14, 0): where the world's swatch row lives in VRAM; `first`: the first 4-bit palette regions are given (default 0); `first8`: the first 8-bit palette 8-bit textures take, regions taking them downward (default 31, the top of palette bank 1) |
| `textures` | Every region's texture `slots` 0–31 (a range `"13-6"` in order of preference, or a list `"14,12,16-31"`; default `"13-0,16-31"`) and VRAM `budget` (bytes; default the slots', 983,040 for the default 30), unless the region gives its own ([Textures per region](#textures-per-region)) |
| `regions` | Named regions in order (the pack's region numbers): optional `palettes` (`first`, `count`), `variants` (with `texels` and `backdrop` colours for textures and the silhouette), `textures` and `backdrop` ([Backdrops](#backdrops)). `audio` is reserved and rejected for now |
| `layers` | World-wide layer names in order (the pack's layer ids), each with an optional exclusive `group` and `on` (at start) |
| `paths` | Named polylines in world coordinates, in order (the pack's path numbers): [Paths](#paths) |
| `lod` | The switch distances of assets with levels of detail: `scale`, and per asset `distances`, `cull`, `band`, `off`; far levels of the fields' tiles (`ground`) and cull distances for sweeps (`sweeps`) ([Levels of detail](#levels-of-detail)) |
| `standins` | Stand-ins made by the kit from each cell's own contents, for every cell that names none: `distance`, `sweeps`, a cap on `triangles`, a `ground` grid, and per-cell `cells` overrides ([Stand-ins made by the kit](#stand-ins-made-by-the-kit)) |
| `meshes.quads` | Pack pairs of triangles as quads: the same pictures, fewer faces ([Quads](#quads)) |
| `runtime.near_far` | The near pass's far depth the pack asks the reader for (units; default 1.5 cells). `wp_open()` sets `wp_near_far` to it and the World Checker measures with it |
| `runtime.depth`, `runtime.perspective` | The game draws the world with the depth buffer, and with perspective-correct texturing (`render_depth(true)`, `render_perspective(true)`; default false). Not stored in the pack: the checkers judge the world and its assets so ([Depth mode](#depth-mode)) |
| `verification` | The World Checker's per-world settings: `mode` (`report`, the default, or `enforce`) and `thresholds` |
| `terrain` | Terrain materials, their `lighting`, and ground heightfields (`fields`): [Terrain](#terrain). Sweeps are in `paths` |
| `scatter` | Seeded props over areas, set on the ground and merged per chunk: [Scatter](#scatter) |

A **placement** is an `id` (unique in its cell; reports and the pack's 16-bit tag follow it), an
`asset`, a `position` (world coordinates, in the cell; `[x, z]` or `drop` sets it on the ground,
[On the ground](#on-the-ground)), `yaw` (degrees, as `mesh_at()`), an
optional `layer`, `merge` and `ground` (below) and a required `collision`: `"self"` (the asset's
own mesh), `"none"`, or a companion collision asset recipe placed the same way. Requiring it
makes an agent decide for every asset. An **entity** is an `id` (world-wide), a game `type`, a
`position`, optional `yaw`, `layer`, `asset` (a mesh the game may draw), `collision` (an asset
in the entity's own frame, for moving objects), `params` and `was`. A cell's `standin` is an
ordinary asset modelled in cell-local coordinates around the cell's centre. Placing an asset
whose lighting is directional at a yaw other than 0 is a warning
([Day and night](#day-and-night)).

**Collision as built.** Each placement's collision asset is compiled, its faces turned and moved
as `mesh_at()` draws them, given surface bytes from their material tags and the placement's
layer, and tagged with the placement's number. Downward faces resting on a floor (centroid within
1/256 unit above a floor triangle of the same or no layer) are dropped: the bottom of a box
standing on the ground would otherwise be a ceiling at ground level. The pack's encoder then
classifies, files and copies triangles into neighbouring cells.

### Palettes per region

Every asset drawn in a region (placements, stand-ins and entity meshes, not collision assets)
contributes its material manifest's palette entries to the region. Entries of the same class and
colour share one region entry, across assets, as they do within one asset; an entry the asset's
recipe forced apart (`share: false`, manifest `separate`) stays apart. Surface entries come first,
then emissive ones, as indices 1–15 of consecutive 4-bit palettes, so a cart can blend the
emissive range on its own curve. Each asset's palette faces are then rewritten with
`assetkit.compiler.relocate()` to the region's colours and the world's swatch position, so a mesh
drawn in two regions is stored twice (the pack pools identical bytes).

**Regions get disjoint palettes** (by default consecutively from `palette.first`; an explicit
`palettes.first` may place them, and overlaps are errors). There are 512 4-bit palettes, 0–511 in
two banks; a region's range never includes 255 (the fonts'), so a region that does not fit below
it starts at 256, in palette bank 1, and its main run is loaded there (`load_palette()` and
`palette_lerp()` address colours 4096–8191 in bank 1). That departs from the placeholder split
in [Regions and the VRAM split](#regions-and-the-vram-split), which shared one range among regions
and swapped it: with flat-colour materials a region needs tens of colours, not hundreds, so every
region's palettes can be loaded at once, and a far cell's stand-in is coloured correctly whichever
region the player is in. Shared ranges belong with region texture sets, when there is something to
swap.

**Variants** are named full sets of the region's colours, in order (default: one, `default`). A
variant starts from the entries' own colours, multiplies surface and emissive entries by
`surface.multiply` and `emissive.multiply`, then sets exact `colors` by `MATERIAL` (that material
of every asset drawn in the region) or `ASSET.MATERIAL`. A name that matches nothing is an error;
two names giving one shared entry two colours is an error that suggests `share: false`; recolouring
an entry another material shares is a warning. The kit attaches no meaning to the names.

**Fog per variant** (the GPU's fog toward a colour: [DECISIONS.md](DECISIONS.md#fog-toward-a-colour)).
A variant may declare `"fog": {"color": "#c6cec8", "near": 48, "far": 300}` (near 0–4,095 units,
far at least near + 1): a day haze, or night darkness. When any variant does, `NAME.akr` gets
`world_NAME_fog(region, variant)`, which calls `gpu_fog()` with that variant's fog, or
`gpu_fog_off()` for a variant without it; the game calls it with `wp_region_enter(k, v)`. A world
without fog generates what it always did. The World Checker does not draw fog (it costs the GPU 8
cycles a triangle and nothing a pixel).

### Textures per region

Built (2026-10-04). A world may place Asset Kit assets with textures ([ASSETKIT.md](ASSETKIT.md#textures)).
Every textured asset drawn in a region (placements and entity meshes) contributes its tiles to
the region's **texture set**, which `tools/worldkit/textures.py` packs once with the kits' shared
packer (`kitcore/texpack.py`, as `mei_assets.py pack` does):

- **duplicates removed** across every asset the region uses (the same brick tile in two assets
  is one tile; the night market's crate is one tile in each region that has crates);
- **palettes shared** while their colours fit, 15 colours to a 4-bit palette and 255 to an 8-bit
  one, but surface and emissive textures never share a palette (so a variant can tint them
  differently; a tile used by both classes is tinted as emissive, with a warning);
- **window-aligned tiles**: every tile at a multiple of 8 texels, repeating tiles reached through
  texture windows;
- **slots** from the region's `textures.slots` (else the world's, else `"13-0,16-31"`), in that
  order of preference, never 15 (the fonts). A set that fits in 13–0 packs exactly as it did
  before slots 16–31 existed; a face in slots 16–31 has bit 6 of its flags set
  ([LANGUAGE.md](LANGUAGE.md#mesh-format)), and one with a palette in bank 1 bit 7. Slot 14 holds the world's swatch row by default; a region
  may still use it: the packer keeps the swatch's 16 × 1 texels free and the region's slot image
  carries the swatch bytes.

Each placed mesh is then written for the region's placement (`native_bytes()` with the region's
packing; palette-backed materials of a textured asset go to the region's entries the same way),
so a textured asset drawn in two regions is stored twice. Untextured assets are relocated as
before, byte for byte.

**Palettes.** A region's 4-bit texture palettes follow its palette-backed entries' palettes in
its own range (`palettes.first`, `count`; still disjoint from every other region's), so its main
colour run covers them and palette variants recolour them entry by entry. 8-bit texture palettes
(256 colours each, 8-bit palette *p* is colours 256 *p* ..) are taken from `palette.first8`
(default 31, the top of palette bank 1; it was 14) downward, region after region, never 15, and
stored as extra runs; the build fails if one would overlap a 4-bit palette a region uses.

**VRAM budget.** A region may use its slots' 32,768 bytes each, or `textures.budget` bytes (tiles
counted on the 8-texel grid, gutters included). Over it, or when the tiles do not fit in the
slots, the build fails at `/regions/NAME/textures` with what the region needs and every asset's
share:

```
Region 'market' needs 3,360 bytes of texture VRAM; that is over its budget (slots 13,12,..,6,
budget 2,048 bytes). By asset: stall 2,176 bytes (8 tiles), shopfront 928 bytes (4 tiles),
crate 128 bytes (1 tile), paving 128 bytes (1 tile). Use fewer or smaller textures, ...
```

`report.json` gives each region's `textures`: `vram_bytes` (the tiles) and
`vram_bytes_allocated` (on the grid), `tiles`, each slot's rows and ROM bytes, the palettes, VRAM
`by_asset`, and its animations (frames, ticks, ROM bytes, bytes a frame).

**Night.** A variant's `surface.multiply` and `emissive.multiply` tint every colour of a 4-bit
texture of that class, as they tint palette-backed entries; `texels` then sets exact colours:
`"texels": {"shopfront.window": {"#30384a": "#ffd27a"}}` lights the shop window's panes (colours
are compared at 15 bits; a colour the texture does not have is an error, as is a recolour of an
8-bit texture). An entry shared with another texture changes with it (a warning). An 8-bit
texture's whole palette is tinted by its class's multiply (`night: multiply`, as the manifest
says): there is one tint per variant, not colours per entry. Both are stored per variant, so the
reader loads or blends them like any other variant (`wp_variant_load()`, `wp_variant_blend()`).

**Animated textures.** Each animated tile of the region (`"frames"` and `"ticks"` in its asset)
has its frames in the pack in the tile's own layout; the reader copies a frame into the tile
when it changes (`wp_animate(t)`, every placement in step). The texture set holds frame 0.

**What is refused.** An authored stand-in with textures (a stand-in is drawn whichever region is
loaded, so it cannot use a region's set; in a world with several regions the kit's own stand-ins
draw far colours instead: [Stand-ins made by the kit](#stand-ins-made-by-the-kit)), and a merged
placement whose mesh has repeating textures (a merged mesh keeps no window table). Textured terrain's tiles join the region's set as one more
asset's ([Textured terrain](#textured-terrain)).

**Cost** (the night market's market region, measured on the console, `tests/worldkit/market.akr`):
2,434 bytes of tiles (3,360 on the grid) in slots 13 (4-bit) and 12 (8-bit), 6,528 bytes of ROM;
entering it (`wp_region_enter()`: texels, palettes and the backdrop's 23,552 bytes of art) costs
29,419 cycles, the harbour 10,580. Its two animations cost 259 cycles a frame while neither
changes frame and up to 3,020 when the 33 × 17 neon sign does (17 rows of 17 bytes: rows that
are not word-aligned copy a byte at a time). The scene's frames are 48,000–85,000 CPU and
130,000–194,000 GPU cycles in depth and perspective mode.

### Backdrops

Built (2026-10-04). A region's `backdrop` is a sky and a horizon silhouette drawn by the Horizon
Engine ([PLANES.md](PLANES.md)) behind the 3D world: no GPU cycles and no triangles, and with the
plane chip erasing the frame to holes the GPU's 38,400-cycle `cls()` goes too.

```json
"backdrop": {
  "elevations": [-8, 0, 6, 30, 70],
  "sky": {"day":   ["#8a9298", "#e8dcc8", "#b8d0e8", "#6898d0", "#3060a8"],
          "night": ["#141420", "#2a2440", "#1a1c3a", "#0c1028", "#04060f"]},
  "silhouette": {"pattern": "skyline", "width": 1024, "height": 40, "seed": 11,
                 "colors": ["#5a6878", "#3a4250", "#485666"]}
}
```

- **Sky**: a gradient on the backdrop colour, one colour per stop for each palette variant (a
  variant not given takes the first's colours times its `surface.multiply`), stops at
  `elevations` (degrees above the horizon, increasing; below 0 is the haze under the horizon).
- **Silhouette** (optional): a 4-bit panorama 256, 512 or 1024 pixels around and up to 128
  tall, on tile plane BG1. From a PNG (`image`: transparent pixels are sky, at most 15 colours)
  or generated (`pattern`: `skyline`, blocks with lit windows; `mountains`, ranges far to near;
  deterministic by `seed`). Its 8 × 8 tiles are deduplicated into an atlas at plane page 12
  (`0x460000`, planes.akr's `ATLAS_0`) and its map is 128 × 32 entries at most at `0x452000`
  (`MAP_BG1`), both copied by `wp_region_enter()`. `horizon` gives the rows below the horizon
  line (default 0: it stands on the horizon). Its colours are one 4-bit palette in the region's
  range, so variants recolour it: the surface tint, then exact colours in the variant's
  `backdrop` (the skyline's windows lit at night).

**How it moves with the camera** (`stdlib/wpbackdrop.akr`, `wp_backdrop_draw(yaw, pitch)`): the
camera has no roll, so the horizon is a screen line, 120 + *F* tan(pitch) with *F* = 207.8
pixels a radian (the default 60° camera; `wp_backdrop_focal`). Each sky stop at elevation *e* is
put on line 120 − *F* tan(*e* − pitch) and the line table interpolates between them, so tilting
the camera slides the gradient exactly at the horizon and approximately away from it. The
silhouette's horizon row is put on the horizon line and only its own rows are shown (BG1's
window), so the plane's vertical wrap never shows a second copy. Horizontally it scrolls
`rate` = width × `repeat` / 2π pixels a radian of yaw, its column 0 facing +Z at the screen's
centre, turning the same way as the world. The world turns at *F* pixels a radian at the
screen's centre, so a panorama matches it exactly only when width × repeat ≈ 2π *F* ≈ 1,306:
`repeat` defaults to the whole number nearest that (1 for 1,024 pixels: 0.78 of the world's
rate; 3 for 512: 1.18; 5 for 256: 0.98), and the report gives the ratio (`against_the_camera`).
A tile plane scrolls by whole pixels and has no scale, which is why the rate is not exact; the
affine plane BG2 could scale it but is left for the game's Mode 7 floor or water. Measured on
the night market: the skyline moved 88 pixels for a 0.55-radian turn (0.55 × 162.97 = 89.6).

**With depth mode.** The depth buffer orders polygons only; holes stay holes, so the planes show
wherever no polygon is drawn ([RENDERING.md](RENDERING.md)). A cart draws no `cls()` (it would
cover the planes) and calls `render_depth(true)` as before.

**Cost.** `wp_backdrop_draw()` is about 5,300–5,500 CPU cycles a frame (the 240-line gradient
and the scroll, five stops); planes.akr, which `wpbackdrop.akr` imports, adds 3 cycles a drawn
face to `mesh()`. VRAM: the market skyline (1,024 × 40, 459 tiles) 15,360 bytes of atlas and
8,192 of map; the harbour's mountains (512 × 36, 47 tiles) 2,048 and 4,096. GPU: none.

### Region seams

Entering a region (`wp_region_enter(k, v)`) copies its texture set, palettes and backdrop art at
once and sets `wp_region_loaded = k`, so the near cells of every other region draw as their
stand-ins (which carry no textures). That is all that is built. A seam where a player crosses
into another region while seeing both still needs:

- a swap spread over frames: one slot a frame with `wp_texture_load(k, t)` (about 56,000 cycles
  a full slot), the palettes and backdrop last, while nothing on screen uses either region's
  textures;
- the seam's geometry (an underpass, an arcade) authored so that both regions' textured cells
  are out of sight while the swap runs, and a check of that in the World Checker (views at the
  seam must draw no textured cell of the region being replaced);
- or slots split between regions (`textures.slots` per region, disjoint), so two neighbouring
  regions' sets coexist and only the far ones swap, with the budget each then has.

The World Checker already judges every view with its camera cell's region entered and the other
regions' near cells as stand-ins.

### Merged scatter

`"merge": true` on a placement merges it, with the cell's other merged placements of the same
layer and the same `ground`, into one mesh placed at the cell's centre (split only between
props, at 2,048 vertices or 4,000 faces). The reader spends about 500 cycles on every placement
it draws beyond its vertices and faces (WORLDPACK.md, "Costs"), so eight bollards cost one
placement instead of eight; the price is ROM (each copy's vertices are stored) and coarser
culling (one sphere). Collision is unchanged: each merged prop keeps its own. The pack needs no
new record. `report.json` lists what was merged per cell.

### Ground

Ground matters only without the depth buffer: in a world drawn with it ([Depth mode](#depth-mode))
the depth test draws what stands on the ground in front of it, and `ground` changes no picture
(the flag is still stored; drawing ground first does no harm under the depth test).

`"ground": true` on a placement makes it **ground**: the reader draws the near cells' ground in a
pass of its own before everything else near the camera, so nothing standing on it can be drawn
behind it (WORLDPACK.md, "Ground", has the reasons and the exact cases). Without a depth buffer a
large floor face sorts by its average depth, and one ordering table draws it over the feet of what
stands on it; flagging the floors of the two example worlds took their near-camera wrong-order
pixels from 153,444 to 2,775 (`test_room`) and from 365,309 to 318,722 (`two_districts`). What
was left was the examples' own modelling, fixed since: ground slabs whose sides overlapped their
neighbours, and faces hidden inside an asset (the shop's body top under its roof, the canopy's
trim on its roof). With ground modelled as surfaces and those faces removed, the near-camera
count is 0 and 348 (WORLDCHECKER.md, "Ground").

**The rule: flag as ground only the lowest open floor of an area, the surfaces nothing is ever
under or behind from where the camera can be; everything raised stays an ordinary placement.**
Ground-first drawing draws whatever a ground face truly hides over it, so:

| Ground | Not ground |
|---|---|
| a floor, a street, a courtyard | a platform, block, step or kerb on the floor |
| a floor rising into a ramp up from its edge (a valley seen from above) | a ramp up to a higher floor that is also ground: the crest hides the feet of what stands beyond it |
| one surface per area, its pieces meeting edge to edge | a bridge, a walkway or a ramp you can walk or see under |
| | a floor at the edge of a pit or a drop with anything drawn below it (the lip hides part of it) |
| | water, glass and other semi-transparent surfaces |
| | anything seen from below |

Ground meshes are best surfaces rather than solids: the sides of a ground slab lie under its
neighbours' tops, and ground faces that overlap are sorted among themselves as before. A ground
piece is a `box` with every side but its top left out (`"open": ["bottom", "left", "right",
"back", "front"]`, [ASSETKIT.md](ASSETKIT.md#geometry-operations)), or an explicit `mesh` of
upward faces only, as the examples' `ground_tile` and `room_floor` are; a building or block
standing on the ground is a box with `"open": ["bottom"]`. The same goes for faces inside
an asset that nothing can see, such as the top of a body under the roof sitting on it: they still
sort, and can be drawn over what covers them. The examples' `shop` is one `mesh` shell whose
window, sign and roof edge are bands of its walls (`face_materials`), with no bottom, and passes
the Asset Checker. Objects
stand on the ground, not in it: a buried part is drawn over the ground. Stand-ins are never ground
(a stand-in is the whole cell); a merged mesh is ground when its props are. The World Checker
warns of geometry an upward ground face can hide (`ground_hides`) and of ground that can overlap
ground (`ground_over_ground`), and counts the pixels where the ground truly hides what is drawn
over it (`ground_inversion`, a threshold).

### Levels of detail

An asset whose recipe has `lod` ([ASSETKIT.md](ASSETKIT.md#levels-of-detail)) is placed with all
its levels: the pack stores its coarser meshes, its switch distances and its cull distance once
per asset, and the reader draws each placement at the level its distance from the eye chooses,
with a hysteresis band so a camera hovering at a switch distance does not make it flicker between
levels ([WORLDPACK.md](WORLDPACK.md#levels-of-detail)). Placements need nothing; collision always
comes from the placement's collision asset, whatever level is drawn. The distances are data, in
the asset's recipe and, for one world, in the world file:

```json
"lod": {"scale": 0.8,
        "assets": {"shop": {"distances": [20, 40], "cull": 80},
                   "lamp_post": {"cull": null, "band": 2},
                   "station": {"off": true}}}
```

| Property | Meaning |
|---|---|
| `scale` | Multiplies every asset's switch and cull distances (not the band): one knob for the whole world. Default 1 |
| `assets.NAME.distances` | Replaces the recipe's switch distances, one per level after level 0 |
| `assets.NAME.cull` | Replaces the recipe's cull distance; `null` removes it |
| `assets.NAME.band` | Replaces the recipe's band |
| `assets.NAME.off` | Draw this asset's level 0 always in this world |

Distances must increase by more than twice the band and stay within 1,400 units; an error points
at the asset's entry (or at `/lod/scale`). Naming an asset without `lod`, or one nothing draws, is
a warning (`lod_unused`). A merged placement (`"merge": true`) draws its level 0 only: merged
meshes have no levels (`lod_merged`). `report.json` lists, per asset with levels, the distances,
cull and band the pack holds and each level's triangles (`lod`), and the asset summaries carry the
recipe's per-level report.

Levels of detail are kept apart from stand-ins (WORLDPACK.md says why): stand-ins replace whole
far cells, levels replace single placements inside the near cells. In a small world all of whose
cells are near (the movement garden), only levels of detail reduce what is drawn. The World
Checker judges the levels the reader actually draws, in its worst case (the finest level the band
allows), and checks each view's triangles and draw cycles against its budgets, naming the
heaviest placements drawn (with their distance and level) when a view is over
([WORLDCHECKER.md](WORLDCHECKER.md#levels-of-detail)).

**Cull distances in a recipe without levels.** A recipe whose `lod` has only a `cull` (a lantern,
a barrier) gets a cull mark of its own. Before 2026-10-05 the kit ignored such a `lod`, so these
props were drawn to the end of the near pass; outside the shrine the movement garden's
`office_ac_unit` (cull 56) and `shrine_stall` (cull 64) are such recipes, so the garden's pack
changed with this (only those eight placements gained a cull mark).

**Far ground.** A field's tiles have level 0 and, with the field's `lod`, a coarse level that
keeps every point its edges share with its neighbours, so that tiles at different levels meet.
On a mountain that leaves a coarse tile with tens of triangles (the shrine's: 30 to 100), too
many for ground a hundred units off. `lod.ground` adds far levels to every field tile:

```json
"lod": {"ground": [{"distance": 36, "grid": 8}, {"distance": 76, "grid": 16}]}
```

Each is a regular grid over the tile (`grid` units a square, 4 to 64), two triangles a square,
resampled from the tile's coarsest level (where textured ground is drawn in its textures' far
colours) by `tools/worldkit/farground.py`: the heights are the tile's own under each grid point
(its top where a cliff stands), each square takes the face under its centre (flags, texture,
palette, and colours and texture coordinates carried over affinely) and is split along the
diagonal whose middle lies nearer the ground there. Its edges do not keep the neighbours'
points, so where its straight edge stands more than 0.05 units above the finer ground beside it
a **skirt** hangs down from that grid segment, facing out of the tile, far enough to close the
crack. A level is kept only where it has fewer faces than the level before it (a flat tile of
two triangles keeps none). The distances are `lod.scale`d and must clear the field's own `lod`
by more than twice its band. `report.json`'s `far_ground` counts the tiles and triangles per
level.

**Sweeps.** A swept profile has no levels; `"sweeps": {"cull": 56, "paths": {"torii_stairs":
{"cull": 44}}}` culls every sweep's pieces from `cull` (eye to the piece's centre), or a path's
own (`null`: never). The field under a sweep is still drawn, so a trail or a stair turns into the
ground it runs on.

`runtime.near_far` sets the near pass's far depth for the world. The default, 1.5 cells, is 96
units in 64-unit cells; a shorter one draws less but brings the edge where placements appear
nearer. It is stored in the pack, so the cart and the World Checker draw with the same range, and
exported as `WORLD_NAME_NEAR_FAR`.

**Depth mode and the near range.** Without the depth buffer the near pass's range keeps its
ordering table's buckets fine; with it (`runtime.depth`) the range only decides what is drawn,
and a placement in a near cell beyond `near_far` is culled although no stand-in covers its cell.
A near cell reaches up to two cells from the eye (three on the diagonal), so a depth-mode world
that draws its distance can set `near_far` past that and let each placement's levels and cull
decide: the shrine uses 192 (three of its 64-unit cells).

**A level bias that follows the measured cost** (*proposal*, not built). The switch distances are
set for a world's worst views, so every other view draws coarser than it could: in the shrine
town the full check's median view is about 310,000 draw CPU cycles of the 600,000 budget. The
reader could scale the distances it compares by a bias *b* (0.75–1.5), kept per frame from what
the last frames cost:

- the cart measures the world's draw with `CYCLES` around `wp_draw()` (the reader can do it in
  `wp_draw()` itself) and keeps a short average *c* of the last 4 frames;
- with a target *T* (say 80% of the world's share, 480,000 of 600,000), *b* moves toward
  *b* · (*T* / *c*) by at most 2% a frame, clamped to the range, so a view that grows heavier is
  drawn coarser within a few frames, and a light view draws finer;
- the comparison is `d < D · b` for each switch distance *D*, and the hysteresis band is scaled
  with it, so placements at a switch distance still do not flicker; cull distances and stand-ins
  are not biased (what pops in at the near ring's edge stays where the World Checker saw it);
- the bias is one `fixed` the reader multiplies into the eye distance it already computes per
  placement (`__wp_lod_mesh()`): about 10 cycles a placement, under 4,000 a frame.

The World Checker would keep judging the levels at *b* = 1 (and, to bound the worst case, at the
range's top). Levels then become a quality floor rather than a budget, and the zones' sooner
levels (DESIGN.md 12.6) could go back to the recipes' own, the bias pulling them in only where a
view needs it. What it cannot fix: a single frame's spike (a region entered, cells loaded), and
GPU-bound views, which a CPU measurement does not see (the GPU's `GPU_CYCLES` could be averaged the
same way).

### Haze

Built (2026-10-05). Far geometry fades toward the colour of the sky at the horizon (aerial
perspective), so it recedes instead of reading as dark blocks:

```json
"haze": {"start": 20, "end": 280, "amount": 0.55, "standins": 0.38}
```

| Property | Meaning |
|---|---|
| `start`, `end` | The amount grows linearly from 0 at `start` (default 0) to `amount` at `end` (units from the eye) |
| `amount` | How far a colour moves toward the haze colour at `end` and beyond, 0–1 |
| `standins` | The amount for stand-ins; default the amount at 1.5 times the stand-in distance |
| `emissive` | Emissive faces (lit windows, lamps, signs) are hazed by this times the amount; default 0.5 |
| `elevation` | Where on each region's backdrop sky the haze colour is read, degrees above the horizon; default 2 |
| `colors` | The haze colour per palette variant name, instead of the sky's |

Nothing is computed at run time (`tools/worldkit/haze.py`): what is drawn far off is separate
data already, so the kit bakes the haze into it.

- **Levels of detail** after level 0 (assets', scatter chunks', terrain tiles' and the far ground
  levels): each level is hazed by the amount at the distance it switches in, through its faces'
  vertex colours. An untextured face's colour is mixed exactly. A palette-backed face's colour is
  its palette entry times its vertex tint (128 is unchanged, 255 at most), so the tint is set to
  turn the entry's colour into the hazed one: t' = t (1 − a) + 128 a S / b per channel, b the
  entry's colour, S the haze colour. A textured face's tint applies to all its texels, so b is the
  tile's mean brightness, as grey: the texture brightens toward the haze with a cast of its colour
  and keeps its own hues (a per-channel tint for a card's mean green turned its brown trunk pink).
  The tint is the first variant's haze colour; at night the variant's palette darkens under the
  same tint, so a far level is a little lighter at night than exact haze toward the night sky
  would make it.
- **Stand-ins**, at `standins`: in a world with several regions their faces are drawn in far
  colours ([Stand-ins made by the kit](#stand-ins-made-by-the-kit)), and with haze those become
  entries of their own (palette-backed faces' colours join the tiles' means in the reduction),
  which only stand-ins draw: every palette variant hazes them exactly toward its own haze colour.
  Their cut-out cards (the stand-ins' texture set) are drawn through a second copy of the cards'
  palettes, hazed the same way. Everything else in a stand-in (and every stand-in in a world with
  one region) is tinted as the levels are.

Level 0 is never hazed, and an asset without levels is drawn unhazed to the end of the near pass.
A level's haze is the amount where it starts, so it steps up a little at each switch. ROM grows by
the levels whose bytes no longer pool with another copy; palettes by the far colours' entries
(about 3 palettes a region) and the cards' second copies. `report.json`'s `haze` gives the
settings, each region's colour per variant and the number of levels hazed. A world without
`haze` builds as before, byte for byte.

In the shrine town (the settings above; day `#c6ccc2`, night `#24213e` from its sky): 2,246
levels hazed, the pack 11,480,668 bytes (11,456,388 without), the regions' palettes to 245
(232 without); no frame cost, and the full check's peaks unchanged by the haze and the cards
(shrinetown/DESIGN.md 12.7 has the views, before and after).

### Quads

`"meshes": {"quads": true}` pairs the triangles of every mesh the kit packs into quads
(`tools/worldkit/quads.py`). The Asset Kit and the terrain write every face as a triangle, so a
wall, a roof panel or a card is two faces and the reader's per-face work (the back-face test,
the packet, the sort) is paid twice. Mei draws a quad as its triangles 0-1-2 and 1-2-3, so two
triangles that share an edge, face the same way and agree in everything their face records hold
(flags, blend, texture, palette, and colour and texture coordinate at both shared corners; a
flat face's one colour) draw the same pixels as one quad with that edge as its diagonal, when:

- they lie flat to within 1°: the reader decides whether a quad faces away by its first triangle
  alone, so a folded pair would be drawn or dropped whole (seen from within a degree of edge-on
  a flat pair can still differ, where it covers next to no pixels);
- the four corners make a strictly convex quad: a quad cut by the near plane or the guard band
  is clipped as the polygon around its corners and fanned from one of them, which covers a
  dart's two triangles wrongly (the World Checker found 2,834 coverage-error pixels in one view
  before this rule).

Semi-transparent and keyed faces stay triangles (the ordering table sorts a quad as one face),
and so do the double-sided faces of a placement's level 0 and of entities: a tree crown of
cutout cards is sorted nearest first triangle by triangle, which keeps its overdraw down where
it fills the screen (pairing them added 16,000 GPU cycles to the shrine's worst close view).
What changes is the order faces are sorted in, by a quad's four corners instead of each
triangle's three, so where coplanar faces overlap (a trim on a wall) a few pixels along their
edges can go to the other face: 51 pixels in the shrine's view from the road. On the shrine the
pass packs 47,505 faces where there were 78,925 (40% fewer), and the World Checker's peak draw
CPU went from 921,962 to 726,303 cycles before the other changes of that day; GPU triangles and
pixels are unchanged.

### Paths

`paths` in the world file names polylines in world coordinates: a rail to grind or hang from, a
wire between two poles, a crane's jib, a train's route. The kit attaches no meaning to them and
makes no geometry from them unless a path has a `sweep` ([Terrain](#sweeps)); it checks them,
packs them once per world ([WORLDPACK.md](WORLDPACK.md#paths) says why not per cell) and exports
their numbers:

```json
"paths": {
  "overpass_rail": {"points": [[40, 6, 20], [52, 6, 20], [60, 7.5, 28]], "raised": true, "tag": "rail"},
  "train_route":   {"points": [[8, 0.5, 8], [120, 0.5, 8], [120, 0.5, 120], [8, 0.5, 120]], "closed": true}
}
```

| Property | Meaning |
|---|---|
| `points` | 2–4,095 points `[x, y, z]`, world coordinates, in order; no point may repeat the one before it. A path may cross cell seams and leave the cells (a warning, `path_outside_cells`). A draped path's points may be `[x, z]` |
| `drape` | The path lies on the terrain and may cut its own bed; the pack stores the draped line ([Draped paths](#draped-paths)) |
| `raised` | Not lying on the ground (a rail, a wire, a jib). Default false. Carried to the pack for the game; a raised path's sweep is not ground |
| `sweep` | A profile carried along the path: geometry and collision the kit makes ([Sweeps](#sweeps)) |
| `closed` | A loop: the last point joins the first (do not repeat it). Default false |
| `tag` | A surface tag, mapped to the pack's surface byte by `collision.surfaces` as material tags are (unmapped tags get `default` and are listed in the warnings) |

A path is at most 16,384 units long. The generated `NAME.akr` has `WORLD_NAME_PATH_<PATH>` (its
number) and `WORLD_NAME_PATHS`; `report.json` lists each path's number, points, segments, length,
`raised`, `closed` and surface byte. An entity refers to a path by name through a `name`
parameter of its type, and the cart finds it with `wp_path_find(world_NAME_string(params.path))`,
which is one pointer comparison because the pack stores the string once. The kit does not check
that such a name is a path: `name` parameters mean what the game says. The reader's path queries
and their costs are in [WORLDPACK.md](WORLDPACK.md#paths): a grind check against a rail of a few
segments is about 300–450 cycles.

### Objects on platforms

(Without the depth buffer. In [depth mode](#depth-mode) objects, platforms and thin walls are
ordered per pixel, and the rule below does not apply.)

Entities' meshes and the game's own objects (pickups, the player's character) are drawn after
`wp_draw()` into the near pass, and there a raised platform's top sorts by its average depth, which
can be nearer than an object standing or floating on it: the example `test_room`'s coin above the
`ledge` lost a wedge to the ledge's top from cameras close above it. The reader's
`wp_draw_object()` and `wp_draw_entities()` draw an object as a unit keyed at its nearest point,
and 1.5 units nearer while the eye is above the object's base, which is never wrong against what
lies wholly below the base (WORLDPACK.md, "Objects", has the rule, the measurements and every case
it does not handle). It is the game's way of drawing entities: World Viewer and the World
Checker's verification cart use `wp_draw_entities()`.

**The rule for authors: a platform top that objects stand or float on is no more than about 4
units across a face (split larger tops into smaller faces), and an object keeps about 1.5 units
(`wp_object_bias`) clear of thin geometry in front of it (walls, posts, railings, the platform
above it) where the camera looks down on it.** Closer than that, the object shows through. The
World Checker aims cameras at every entity with a mesh (WORLDCHECKER.md, "Entities") and reports
both: something drawn over an entity truly in front of it, and an entity drawn over a face truly
in front of it.

An object's own mesh is checked by its asset's policy, which should look at it the way the game
will: `test_room`'s coin now asks for 24 yaws, five pitches (−0.9 to 0.9 radians) and three
distances (360 views; it had four level views at one distance). That policy found a fault in it:
the Asset Kit's `cylinder` fans each cap from one rim vertex, and those sliver triangles sort far
from where they meet the 0.08-unit rim, which was drawn over the caps in 9 pixels of 5 views. The
coin is now an explicit `mesh` whose caps fan from their centres (22 vertices, 40 triangles; it
passes); the World Checker decides 60.0% of its pixels in the views aimed at it, from 57.5%.

### Depth mode

A game that draws the world with the depth buffer ([RENDERING.md](RENDERING.md)) says so in the
recipe:

```json
"runtime": {"depth": true, "perspective": true}
```

and calls `render_depth(true)` and `render_perspective(true)` itself (the recipe does not turn
them on: it is not stored in the pack, and the game decides how it draws). The build then:

- runs every required Asset Checker policy with `depth` and `perspective` as the world's, unless
  the asset's recipe sets them itself ([ASSETKIT.md](ASSETKIT.md#depth-mode)); `report.json`'s
  `assets` entry says `verified_with` for those;
- runs the World Checker in depth mode ([WORLDCHECKER.md](WORLDCHECKER.md#depth-mode)): every
  pass judged as one by depth, ordering a regression check, no cameras aimed at entities by
  default, no ground warnings; coverage, budgets and collision as before.

What the depth buffer makes unnecessary for such a world: flagging ground
([Ground](#ground)), the platform and clearance rule for objects ([Objects on
platforms](#objects-on-platforms)), recipe order between overlapping faces
([WORLDPACK.md](WORLDPACK.md#faces-in-one-bucket)), and keeping assets free of crossing faces.
What it does not: coplanar faces still fight (use the decal offset), semi-transparent faces are
still drawn by the ordering table, back to front, and collision, budgets and coverage are
checked as before. The movement garden built this way comes back from the World Checker with no
wrong-order pixel in 600 views, against 45,108 in 239 views without
([WORLDCHECKER.md](WORLDCHECKER.md#depth-mode)).

## Collision

**Decided: authored separately as simpler geometry.** Render meshes are detailed (window frames,
signs) and a player catches on detail that should be smooth, so collision is not derived from
them. Each placed asset names a companion collision asset (an ordinary Asset Kit recipe, such as
`shop_row_col`), or says `"self"` to use its own mesh (simple props), or has none. It is stored as
triangles with plane equations, floor/wall/ceiling classes and a per-cell lookup grid precomputed
by the kit ([WORLDPACK.md](WORLDPACK.md), "Collision blocks"), which addresses the precision and
division costs that made Tsumiki avoid triangle soup; a floor query costs about 450 cycles,
against Tsumiki's 2,000 among 41 solids. Analytic solids (Tsumiki's boxes, ramps and cylinders)
were not taken: a city's slopes, stairs and roofs do not reduce to them. Terrain collision comes
from the terrain itself ([Terrain](#terrain)).

**Decided: surface types are an opaque byte the game defines.** The kit derives each collision
triangle's surface byte from its material's Asset Kit `tag` through a table in the world recipe,
without knowing what slippery, wall-jump or ledge-grab mean. Floor, wall and ceiling are classified
by the normal against the game schema's `probe.floor_max_degrees`; the body radius (`probe.radius`)
sets how far walls are copied past a cell's edge (the pack's `pad`). Moving objects (trains, lifts)
are entities with a collision asset in their own frame; the game moves them and the runtime tests
queries in that frame.

### Cracks

**Decided (2026-10-05): the floor query bridges small cracks, and the World Checker agrees.** A
crack is a small horizontal gap between walkable floors: where two assets' collision meshes meet,
inside an asset's own collision, at a bridge's or platform's joints. A point query falls through
one, or snags in it. The shrine town had about 50 findings of 0.016 to 0.25 units, so the
checker's report drowned the real problems in them. A game whose probe gives `bridge` (units;
the movement garden's is 0.4375) stands its body with `wp_floor_across(p, above, below, bridge)`
(`stdlib/worldpack.akr`) instead of `wp_floor(p, above)` (the garden's `col_stand()` asks it
only where its own query, movers included, finds nothing within reach):

- Where `wp_floor()` finds a floor at or above `p.y - below`, that is the answer, unchanged. On
  whole floors the two queries are the same, bit for bit.
- Otherwise it steps out from `p` along x, z and the two diagonals, 1/16 unit a step (181/4096 in
  x and z on the diagonals, exact in fixed point), to the nearest floor within `p.y - below ..
  p.y + above` on each side. A direction with one on both sides, `a + b` steps apart with `a + b`
  at most `bridge × 16`, bridges the gap: the higher of the two floors is the answer. With none,
  `wp_floor()`'s answer stands.

So a gap is bridged when it is narrower than `bridge - 1/8` across its line, and narrower than
0.92 (`bridge - 1/8`) at any angle (the nearest direction is at most 22.5° off): 0.31 and 0.29
units for 0.4375. A gap wider than `bridge` is never bridged, at any point, nor is an edge with no
floor beyond it (a ledge), nor a gap whose far side is out of the window (a step down into a
trench is a fall). What it does give is a fillet in a floor's concave corners: a point in the
corner of a hole's outline, less than `bridge` from both edges along a diagonal, is held (a
triangle about 0.3 units on a side in a right-angled corner). The real gaps the shrine town means
to be fallen through are 0.5 units and wider.

The cost, measured by `tests/worldpack/bench.akr` (cycles; `wp_floor` 448 there): 512 where
`wp_floor()` finds a floor in the window, and 11,478 where it does not and nothing is bridged
(every step of every direction: 6 out along each of the 4, plus the first query), which is the
body in the air over far ground, once a tick, about 1.1 % of a frame.

The World Checker's crack check uses the same rule, through `verify_static.reader_floor_across()`
(bit for bit `wp_floor_across()`, which `tests/test_worldpack.py` compares on 2,160 points near
gaps of 0.016 to 0.6 units at six angles, across a cell seam): a gap whose every point the game's
query bridges, for a body at the edge's height with the probe's step above and below, is not a
crack, and a mismatched edge whose sliver is bridged is not reported. What remains is listed by
`mei_world.py cracks` and kept in the world's crack baseline ([WORLDCHECKER.md](WORLDCHECKER.md#crack-baseline)).
A game without `bridge` (or with 0) is checked as before.

## Build outputs and the runtime contract

For a world named `city` of a game named `game`, `build` produces:

| File | Purpose |
|---|---|
| `city.world.bin` | The pack: index, regions, cells, mesh pool, collision, entity records |
| `city.akr` | `embed WORLD_CITY: u8 = "city.world.bin"`; `world_city_load()` (opens the pack, copies the swatch, loads every region's first variant); constants for regions, variants, colour ranges (`_SURFACE`, `_EMISSIVE` and their counts), layers, paths, the near range (`_NEAR_FAR`, when the recipe sets it), entity numbers and saved bits; `world_city_string()` for `name` parameters |
| `game.game.akr` | The game's type numbers, world numbers, probe constants, parameter `struct`s and `enum`s, imported by every world of the game; make links one copy per game for a cart's worlds, so a cart compiles it once ([Using a world in a cart](#using-a-world-in-a-cart)) |
| `city.swatch` | The 8-byte palette swatch row, when any material is palette-backed |
| `city.water.bin` | The world's upward water faces, when it has water, for `wpwater.akr`'s `wp_water()` ([Water](#water)); `city.akr` embeds it and opens it in `world_city_load()` |
| `city.ids.json` | A copy of the ID lock file (the lock itself is written beside the recipe) |
| `source/` | The world file, cell files, terrain heights files and every asset recipe used, as built, and the game schema exactly as written (Mochi comments kept; the report's `game_sha256` is the hash of its JSON form, so comments and layout do not change it) |
| `report.json` | Per cell and region: triangles (always and per layer), placements, merged meshes, ground placements, collision triangles by kind, bytes, palettes and variants, entity numbers, paths, levels of detail, ID changes, recipe, game and asset hashes and Asset Checker results, warnings; and `verification`, the World Checker's summary, failures and static results, whose row per sampled view stays in `verification/world-check.json` (named by `verification.views_report`), or why it did not run (`ran: false`, with `skipped` for `--world-checker skip`) |

With `preview` (or `build --preview`) there is also `preview/`: for every region, its busiest
cell seen from a fixed camera above its south edge, once per palette variant, drawn by the real
reader (so far cells appear as stand-ins), as PNGs with GPU statistics, and `contact.png`.
Every build also writes `verification/`: the World Checker's report, `world-check.json`, and
pictures of its worst views ([WORLDCHECKER.md](WORLDCHECKER.md)); a build with `--world-checker
skip` writes none.

**Packs are build outputs, not sources.** World packs and the rest of a world's outputs are
built into `build/` (the tests use temporary directories) and are not committed: the recipes
are the source, together with the ID lock file, which is committed. Packs for released
games are to be published separately, later. Small existing carts that commit their generated
assets (`carts/*/`) are not affected.

Outputs are staged and replaced only on success, as in the Asset Kit. Before anything is written,
every referenced asset is compiled from its recipe and each asset whose recipe requires
verification is checked by the Asset Checker, which must pass. Then `build` hands the staged
outputs to the World Checker through one seam, `worldkit.build.run_gate(context)`, which calls
`worldkit.verify.check_world(context)` (context: the staged pack and
`.akr`, the mode and thresholds, the game's probe, the report and the native tools) and records
its result in the report. In `report` mode nothing fails; in `enforce` mode a failed check leaves
the previous build in place with `verification.failed.json`.

The checks run in parallel, one worker process per core (`MEI_KIT_JOBS=N` sets the number): the
Asset Checker per asset and per level of detail, and the World Checker's ordering comparison per
view. The results, and so `report.json`, are the ones a serial run gives. With `--cache DIR`
(make passes `$(B)/kit-cache`) the build also keeps each Asset Checker verdict and the World
Checker's result there, by a SHA-256 of everything the result depends on, and reuses them while
it is unchanged (`tools/worldkit/cache.py`):

| Result | Its key |
|---|---|
| Asset Checker verdict, per level of detail | The level's recipe (its nodes; the recipe's materials, prototypes, lighting, budget and verification policy, in their order) and its compiled mesh's bytes, the source of `assetkit/visibility.py` and every `tools/` module it imports, `meic`, `mei-asset-probe`, the standard library `meic` compiles with, the Python and NumPy versions |
| World Checker result, with its `verification/` files | The pack's bytes, the world's name, verification mode and thresholds, the game's probe and `--world-checker`; the source of `worldkit/verify.py` and its imports, `meic`, `mei-headless`, `mei-scene-probe`, the standard library, Python and NumPy |

A reused World Checker result records `verification_timing: {"cached": true}` in the build's
result instead of its timings; nothing else differs. Errors (a missing tool) are never kept.
The cache keeps the four most recent World Checker results per world and every verdict (a line
of JSON each); deleting the directory is always safe. `tests/test_worldcache.py` checks that
cached and parallel results equal a serial run's and that a change to any key input misses.

**The pack format is specified in [WORLDPACK.md](WORLDPACK.md)** (version 1.3), byte by byte:
header, sparse index, layers, regions, paths, cells, placements and their levels of detail, entities and their parameter
records, collision blocks with precomputed rows and a lookup grid, and the mesh pool (meshes stay in the
native format). `tools/worldkit/pack.py` is the reference encoder and decoder the kit builds on,
and `stdlib/worldpack.akr` the console reader. What the reader does each frame (cells from the
index, the two drawing passes, collision in the player's cell, entities spawned and retired as
cells and layers change, region palettes) is in WORLDPACK.md, "What a reader does"; what it
does not do is in [open question 3](#3-the-runtime).

## Verification

**Decided: the World Checker.** The analogue of the Asset Checker: sample camera positions
through the playable space, including rooftops and the air between them, since they give the
longest sight lines, and check GPU and CPU budgets and face ordering; plus collision checks for
holes. **Decided:** its scene probe is a World Kit component, not an Asset Kit change, because a
camera standing in a level sees several meshes at once, palette swatch faces, and faces crossing
the near plane and the guard band, which the Asset Checker rejects. **Decided:** thresholds are
per-world settings with defaults from the kit, and the checker starts in **report-only** mode
until a real level has been measured: it records what it finds in the build report and fails
nothing on thresholds. Switching a world to enforcing is an explicit edit of its recipe
(`"verification": {"mode": "enforce"}`).

**Built.** [WORLDCHECKER.md](WORLDCHECKER.md) is the reference: what fails in each mode, the
settings and their defaults, the static collision checks, how views are sampled, the ordering
check and its evidence, timings and limits. Every `build` runs it through `run_gate()` ([Build
outputs](#build-outputs-and-the-runtime-contract)); `tools/worldkit/verify.py` runs it on any
pack.

Before the World Checker runs, `validate` and `build` check the recipe itself: every referenced
asset builds and passes its own verification policy; references resolve (assets, regions,
layers, stand-ins, entity types, `entity_ref`, `world_ref`) and parameters match the game
schema; placements lie in their cells and overhang a neighbour by no more than `overhang`, which
keeps the two-pass sort sound; regions' palettes do not overlap; and the ID lock file agrees with
the recipe.

Not checked yet (WORLDCHECKER.md, "Limits"): the seam rule, that nothing drawn while a region's
texture slots are being swapped samples a region texture; and that stand-ins use only the common
texture set, which waits for region texture sets.

## Command line

Parallel to `mei_assets.py`: JSON on stdout for successes and failures (an error has `path`,
`message` and, as in [Recipe format](#recipe-format), `file`, `line` and `column` where they
apply), exit 0 or 1, `-` for
stdin (relative paths then resolve from the current directory), `--compiler`, `--runner` and
`--probe` to use other builds, `--assets DIR` to use another asset directory, and for `build` and
`preview`, `--cache DIR` to keep and reuse the checkers' results ([Build outputs and the runtime
contract](#build-outputs-and-the-runtime-contract)).

| Command | Result |
|---|---|
| `schema [--game FILE]` | The world recipe's JSON Schema (cell files and game schemas under `$defs`, Mochi under `$defs/game/x-mochi`), with the game's entity types (Mochi or JSON) folded in when given |
| `convert FILE [-o OUT] [--force]` | A game schema in the other form: JSON to canonical Mochi, or a `.mochi` file to JSON. Without `-o`, the result holds the `text` (Mochi) or `game` (JSON) |
| `init DIR [--example room\|city\|terrain] [--force]` | Copies an example world (world file, cells, game schema, asset recipes) into a new directory |
| `validate FILE` | Every static check: schemas, references, game data, IDs, palettes, that every asset compiles and that the pack can hold the world; the ID changes a build would make |
| `inspect FILE [--cell ID]` | The same, with the full report: per cell and per region costs, palettes and variants, entity numbers, asset hashes, warnings |
| `build FILE -o DIR [--locked] [--preview] [--world-checker full\|skip\|N] [--crack-baseline FILE\|none]` | The outputs above; runs each asset's required Asset Checker policy, then the World Checker seam (with `NAME.cracks.json` beside the recipe as its crack baseline, when there is one) |
| `preview FILE -o DIR [--cell ID] [--locked] [--world-checker full\|skip\|N]` | `build`, plus native renders of a cell per region and palette variant (`--cell` picks the cell) |
| `floor FILE X Z [X Z ...]` | The highest floor under each point, from the world's collision as the kit builds it: `{"at", "y", "from"}`, `from` being `terrain`, `sweep` or a placement's ID (`y` null: none). For setting placements and entities on the ground |
| `check FILE [--cells I,J[;I,J...]] [--camera SPEC]... [--cameras FILE] [--max-views 200] [-o DIR]` | The World Checker on a few cells and cameras, in seconds ([Quick tools](#quick-tools)) |
| `floors FILE --area X0,Z0,X1,Z1 [--step 1] [--layers A,B] [--below Y]` | The pack's floor heights over an area as `wp_floor()` finds them, what each belongs to, holes and cracks ([Quick tools](#quick-tools)) |
| `textures FILE [--region R] [--cells ...] [--add REGION:ASSET,...]` | Texture VRAM per region, by asset and by image, against the region's budget ([Quick tools](#quick-tools)) |
| `cracks FILE [--routes FILE] [--near 3] [--baseline [FILE]] [--write-baseline]` | Every collision crack the game's floor query does not bridge, on routes first, the widest first; compared with or written to the crack baseline ([Quick tools](#quick-tools)) |

`--world-checker` is for quick builds, such as the World Kit's own tests: `full` (the default)
runs the World Checker with the world's settings; `skip` does not run it, and `report.json`
says so (`"verification": {"ran": false, "ok": null, "skipped": true, "reason": ...}`); a number
*N* samples at most *N* views (the checker's `sampling.max_views`), and the report's
`verification.reduced` records it. A world whose recipe says `"verification": {"mode":
"enforce"}` builds only with the full check: `skip` or *N* is refused with an error at
`/verification/mode`. make's world rule ([Using a world in a cart](#using-a-world-in-a-cart))
always runs the full check.

The World Checker also runs on its own on any built pack: `python3 tools/worldkit/verify.py
PACK -o DIR` ([WORLDCHECKER.md](WORLDCHECKER.md)). *Proposals, not built:* `verify FILE [-o DIR]
[--cell ID] [--layers A,B]` (the World Checker on a recipe, diagnostic only), and `standin-draft
FILE --cell ID -o RECIPE` (an Asset Kit recipe of boxes from the cell's placement bounds, for an
agent to edit; the Asset Kit then builds it like any other, so the World Kit still models
nothing).

### Quick tools

Built (2026-10-05). Four read-only commands for placing things in a world, each in seconds
once the world has been compiled (`tools/worldkit/quick.py`; `cracks` takes minutes on a large
world, and with `--write-baseline` writes the crack baseline). They print plain text; `--json`
gives the result as JSON (and errors as the other commands give them; plain `error at PATH:
message` without it). Exit 1 when the result fails (a check that fails, a region over its
budget).

**The compiled world is cached.** Each needs the world compiled (pack, placements, texture
sets), which takes about 30 s for the shrine town (30 cells, 7 MB). The tools keep it in
`BUILD_DIR/kit-cache/quick/` (`--build-dir DIR`, else `$B`, else `build/`; `--cache DIR`,
`--no-cache`, `--refresh`) with a manifest of everything the compile read: the world file, the
cell files and the cell folder's listing, the game schema, the ID lock file, every asset recipe
used and the images and sheets its textures read, each asset directory's listing (and a `/*`
entry's subfolders), the terrain's heights files and images, and the hash of the kit's code
(`worldkit/cache.py`'s `code_hash`). While all of it is unchanged the next run loads the
compiled world in about 0.6 s; after any change it compiles again and keeps the new one. Nothing
a build writes is touched: the ID lock file is never written.

**`check FILE --cells ... --camera ...`** runs the World Checker (`verify()` with a `focus`,
[WORLDCHECKER.md](WORLDCHECKER.md#the-quick-check)) with the world's own settings: mode,
thresholds, runtime (depth, perspective) and the game's probe. For the cells (`I,J` as a cell's
`at`, or a cell ID; separated by `;` or the option repeated) it runs the static collision
checks for what lies in them (cracks and mismatched floor edges, entities in solid, the cells'
budgets) and the views sampled from them (at most `--max-views`, default 200; the full check
samples 600 over the whole world); each camera (`--camera NAME=EX,EY,EZ:TX,TY,TZ` or
`NAME=EX,EY,EZ@YAW,PITCH`, or a `--cameras` file, as the Asset Kit's
[camera views](ASSETKIT.md#camera-views-at-world-scale) take them) is a vantage point, once per
layer set. Every view lists its heaviest placements, named. The text lists the cells' budgets,
the cameras and the worst sampled views (`--rows`), each with triangles, draw CPU and GPU cycles
and stand-ins, against the limits:

```
$ python3 tools/mei_world.py check carts/garden/shrinetown/shrinetown.world.json --camera v5_spawn=160,1.6,26@0,0 --build-dir build-mine
shrinetown: World Checker on 1 camera (report mode; compiled world cached, 0.6 s; check 3.5 s)
Views: 5 (5 from 1 camera x 5 layer sets); limits 4,000 triangles, 600,000 draw CPU, 1,600,000 GPU cycles
  view                           tris  draw CPU       GPU stand-ins  heaviest placements (faces, level)
  v5_spawn                        995   341,884   329,076        10  station_concourse 579 L0, station_platform 410 L0, arcade_roof 130 L1
                               eye [160.0, 1.6, 26.0] yaw 0.0 pitch 0.0
  ...
ok: 0 hard failures, 0 over thresholds
```

On the shrine town (Apple-silicon Mac): one or two cells about 10 s, a camera 2.5–5 s, plus
0.4–0.6 s to load the cached world (22–30 s to compile it after a change); the full build
with the World Checker takes about 160 s (the checker 113 s of it, its static checks 87). A
cell's collision findings are the full check's in that cell (`tests/test_worldkit.py` compares
them).

**`floors FILE --area X0,Z0,X1,Z1 [--step 1]`** reads the built pack's collision with the
reader's own floor query (`verify_static.reader_floor()`, bit for bit `wp_floor()`): at each
grid point the highest floor (or the highest at or below `--below Y`, as a body there finds it),
with the layers on at the start (`--layers A,B` for others, `""` for none). It prints the
heights, north up, then a letter per point for what the floor belongs to (a placement, by cell
and ID with its asset, or `terrain`, `sweep`, `scatter`), with a legend; `!` marks a hole (no
floor where the four neighbours have floors within the probe's step) and the World Checker's
crack findings in the area are listed. A placement's collision copied into a neighbouring cell
keeps its own cell's tag; the name is taken from the nearest placement with that tag. Unlike
`floor`, which tests the kit's collision before packing in floating point, a point exactly on a
face's edge is decided as the console decides it.

**`cracks FILE`** runs the World Checker's crack and mismatched-edge checks over the whole world
(every layer off and each alone, as the full check does), with the game's floor query's bridging
([Cracks](#cracks)), and lists every finding that remains, not only the full check's first 50:
those within `--near` units (default 3) of a `--routes` polyline first, then the widest first,
each with both floors named. `--baseline` compares with the crack baseline (exit 1 when one is
new) and `--write-baseline` writes it ([WORLDCHECKER.md](WORLDCHECKER.md#crack-baseline)). On the
shrine town (about 3 minutes, a minute of it compiling the world when it is not cached; the
routes from `layout.py`'s `R_*` lines):

```
$ python3 tools/mei_world.py cracks carts/garden/shrinetown/shrinetown.world.json --build-dir build-mine --routes routes.json
shrinetown: 3 cracks and mismatched floor edges the floor query does not bridge (probe radius 0.3, step 0.32, bridge 0.4375: 7 steps of 1/16), 2 on a route
crack         0.188 at (220.094, 2.267, 155.938) cell [3, 2]: sweep | terrain on BRIDGE (0.11)
crack         0.125 at (171.884, 52.7147, 343.962) cell [2, 5]: terrain | terrain on R_ROPEBRIDGE (2.96)
crack         0.250 at (320.125, 10.2, 156.467) cell [4, 2]: viaduct_27 | terrain
```

**`textures FILE`** gives each region's texture VRAM as the kit packs it: every distinct tile
once, on the 8-texel grid, against `textures.budget` (the numbers of `report.json`'s
`regions.R.textures`), then per asset its bytes, its own (tiles no other asset of the region
uses) and shared ones and whom it shares with, per image or sheet the bytes and the assets that
read it, and the tiles assets share. `--region R` shows one; `--cells` the assets drawn in those
cells, with their bytes and the bytes no other asset of the region uses; `--add
REGION:ASSET[,ASSET...]` counts assets as if placed there (names in the world's asset
directories, or recipe paths), to check a budget before placing. The shrine town's
`tools/textures.py` adds its zones and allowances on top.

### Using the tool

```sh
python3 tools/mei_world.py schema --game examples/worlds/test_room/garden.game.mochi
python3 tools/mei_world.py init /tmp/room --example room
python3 tools/mei_world.py inspect /tmp/room/test_room.world.json
make build/meic build/mei-headless build/mei-asset-probe
python3 tools/mei_world.py preview /tmp/room/test_room.world.json -o build/worlds/room
```

A cart then imports the generated file and draws through the reader:

```
import "test_room.akr"

fn init() { assert(world_test_room_load()) }

fn draw() {
    cls(rgb(40, 60, 120))
    wp_draw(vec3(32.0, 4.0, 8.0), 0.0, -0.2)
}
```

Examples: [`examples/worlds/test_room`](../examples/worlds/test_room) (one cell inline: a floor, a
slope, a ledge, a wall, a canopy whose underside is a ceiling from a companion collision asset, a
gate in an exclusive pair of layers, a collectible with a required Asset Checker policy and a
trigger whose parameters use every kind of reference) and
[`examples/worlds/two_districts`](../examples/worlds/two_districts) (four cells in two regions with
day and night variants, stand-ins, a far cell, merged scatter, a festival layer, a `share: false`
material), and [`examples/worlds/shrine_grounds`](../examples/worlds/shrine_grounds) (terrain:
a terraced hill, a pond, swept paths and stairs, in depth mode; [Terrain](#the-example-shrine-grounds)) and
[`examples/worlds/forest_mountain`](../examples/worlds/forest_mountain) (a cliff band with an
overhang, a pond, streams and a waterfall, draped trails, scatter, things set on the ground, in
depth mode; [Terrain](#the-example-forest-mountain)).
`make test-world` (also part of `make test`) runs `tests/test_worldkit.py`, which builds them and
runs them on the console, and `tests/test_mochi.py`.

## Using a world in a cart

A cart in `carts/NAME/` that uses worlds lists their recipes in `carts/NAME/worlds.txt`, one
repository path per line (`#` starts a comment). World Viewer's:

```
examples/worlds/test_room/test_room.world.json
examples/worlds/two_districts/two_districts.world.json
```

Its Akari source imports each world's generated file by name, as if it were next to it:

```
import "test_room.akr"        // also brings in worldpack.akr and garden.game.akr

fn init() { assert(world_test_room_load()) }
```

`make build/carts/NAME.mei` then:

1. builds each recipe once (`tools/world_cart.py build`, which runs `mei_world.py build` with the
   build directory's tools) into `build/worlds/<the recipe's folder>/`, for example
   `build/worlds/examples/worlds/test_room/`. The World Checker runs as every build runs it,
   report-only unless the recipe says `enforce`, and make prints two lines per world:

   ```
   world test_room: 1 cell, 10,888 bytes, 0 warnings -> build/worlds/examples/worlds/test_room
     World Checker (report): 333 views, 0 hard failures, 0 over thresholds; peaks 49 tris, CPU 41,830, GPU 315,256 cycles; build/worlds/examples/worlds/test_room/verification/world-check.json
   ```

   An invalid recipe stops make with the kit's errors, one per line (`file:line:column: JSON
   Pointer: message`), and the `mei_world.py validate` command that gives them as JSON;
2. links every world's `NAME.akr`, `NAME.world.bin` and `NAME.swatch`, and each game's
   `GAME.game.akr`, into `build/cart-worlds/NAME/` (`tools/world_cart.py link`), so that worlds
   of one game share one `GAME.game.akr`. Two worlds of one name, or two worlds of one game
   built from different game schemas, are an error;
3. compiles the cart with `meic -I build/cart-worlds/NAME`: an import that is not next to the
   importing file is looked for there before the standard library
   ([LANGUAGE.md](LANGUAGE.md#building-and-running)). Because the importing file's own folder
   comes first, a world must not share its name with a file in the folder that imports it: a
   world named `garden` generates `garden.akr`, which `carts/garden/garden.akr` would shadow.
   The garden imports its world from `carts/garden/ground/ground.akr` for this reason.

A world is rebuilt when its recipe, a cell file, its game schema, its ID lock file, an asset
recipe, a terrain heights file, its cell or asset folder (a file added or removed), or the
kit's Python changes: `build.d` beside the build records what the build read. A kit change can change any output, so
it rebuilds every world, but the checkers' results are kept in `build/kit-cache/` by a hash of
their inputs, so a rebuild checks again only the assets and pack whose inputs changed: with
nothing changed but the build's own Python, the garden rebuilds in seconds. Editing the cart's
own files rebuilds only the cart. A recipe edit that adds a saved entity updates the ID lock file beside the recipe,
which is then committed with it. Packs stay in the build directory; `make B=DIR` builds them
into `DIR/worlds/`. Building a world needs Python 3.10 or later and NumPy (for the Asset and
World Checkers).

For a cart's test scenarios, `tools/cart_scenario.sh` passes `SC_IMPORT=DIR` to meic as `-I
DIR`; `carts/worldview/tests/run.sh` shows the use. `make test-carts` runs World Viewer's
scripted run and `tests/world_carts.sh`, which checks these rules (what rebuilds after which
edit, the errors, two worlds of one game).

**World Viewer** (`carts/worldview/`, built on request) is the example: `make
build/carts/worldview.mei`, then `./build/mei build/carts/worldview.mei`. It flies a camera
through both example worlds, or walks it as the game's probe body (`GAME_PROBE_RADIUS`,
`_HEIGHT` and `_STEP`: the eye at the body's height, floors followed up to a step through
`wp_floor`, walls pushed out at the radius through `wp_push`), and shows the cell, triangles
drawn, CPU and GPU cycles, the surface byte under the camera and the names of the variant and
layer (`wp_variant_name`, `wp_layer_name`), and draws the world's paths as yellow lines
(`wp_path_draw`) while the overlay is on. Stick: move; d-pad or right stick:
look; L and R: down and up; A: walk or fly; B: next palette variant; SELECT and X: choose a layer
and switch it; START: next world; Y: hide the overlay.

It draws the live entities' meshes (the coin) with `wp_draw_entities()`
([Objects on platforms](#objects-on-platforms)).

**A world with textures or a backdrop** ([Textures per region](#textures-per-region),
[Backdrops](#backdrops)): its loader also enters the first region that has either
(`wp_region_enter(k, 0)`), and `NAME.akr` imports `wpbackdrop.akr` when a region has a backdrop.
The night market's test cart (`tests/worldkit/market.akr`) is the pattern:

```
import "night_market.akr"
import "depth.akr"

fn init() {
    assert(world_night_market_load())                    // enters the market
    wp_backdrop_show(WORLD_NIGHT_MARKET_REGION_MARKET)   // compositor on, sky and BG1 set up
}

fn draw() {
    wp_animate(frame() as s32)                           // the neon sign and the lantern
    wp_backdrop_draw(yaw, pitch)                         // no cls(): the planes are behind
    render_depth(true)
    render_perspective(true)
    wp_draw(eye, yaw, pitch)
}
```

and at dusk `wp_variant_blend(k, day, night, t)` with `wp_backdrop_variant(day, night, t)`; on
crossing into another region, `wp_region_enter(k, v)` and `wp_backdrop_show(k)`. Screenshots of
it, day and night, are in `examples/worlds/night_market/screenshots/`.

**Open** (found while writing World Viewer; not built): a way to call "the open world's"
generated functions without a branch per world (World Viewer's `world_load(k)` chooses between
`world_test_room_load()` and `world_two_districts_load()`). The other item found then, a helper
that draws the live entities' meshes in the near cells, is `wp_draw_entities()`.

## Open questions

### 1. Collision source and surface types

Settled: see [Collision](#collision). Option (b), authored separately, was decided over deriving
collision from render meshes and over analytic solids.

### 2. Cell size and the grid

Constraints: cell-local coordinates must stay well inside the ±181 dot-product limit; the near
set (3 × 3 cells) sets the near pass's depth range and so its bucket depth; a cell is the unit of
activation, so its contents set the per-cell budget; the index costs 4 bytes a cell (a 1 km square
at 64 units is 16 × 16 = 256 cells, 1 KB).

| Cell size | Near set span | Near-pass bucket (far = 1.5 cells) | Local coordinates |
|---|---|---|---|
| 32 | 96 | 0.047 | ±16 plus overhang |
| 64 | 192 | 0.094 | ±32 plus overhang |
| 128 | 384 | 0.19 | ±64 plus overhang |

**Decided:** a uniform square grid, the cell size chosen per world (16, 32, 64 or 128 units:
the pack's `cell_shift` 4–7) and stored in the pack header; it is not a property of the format or
the runtime. The same holds for runtime capacities, such as active entities or placements drawn
a frame: they are constants each cart sets, not limits of the format (the reader keeps no
storage per placement or entity; WORLDPACK.md, "The console reader"). *Recommendation:* 64
units until stage 2 measures. Alternatives considered: a quadtree or irregular cells for
districts of very different density, and a precomputed potentially-visible set per cell, which
the kit could produce offline from the same renders it verifies with; in a dense city, buildings
hide most cells.

### 3. The runtime

With Tsumiki removed, the stdlib needs at least: pack and index lookup; cell selection and
two-pass drawing with per-placement culling and camera-relative transforms; collision queries
(floor under a point, push out of walls, ceiling, a ray for the camera); texture and palette
swapping spread over frames; entity spawn and retire lists with layer masks.

Settled: the pack format is the contract, versioned in its header, and a narrow reader in
`stdlib/` (`worldpack.akr`, imported only by carts that use it) answers only geometric questions.
Character control, cameras, goals and saving stay in the game; a shared character body may be
lifted out later, once a second game wants the same one.

### 4. Terrain operations

Settled differently from this document's earlier recommendation (terrain operations in the Asset
Kit): terrain belongs to the World Kit ([Terrain](#terrain)), described in world coordinates and
cut per cell by the kit, so seams match by construction instead of by a seam check. Built: the
operations are `set`, `add`, `carve`, `fill`, `ramp`, `terrace`, `smooth`, `bed`, `paint` and
`hole` ([Heightfields](#heightfields)). Open: noise or erosion (the recipe has no random
generation, so it would need a seed), and a sweep that drapes itself over the ground.

### 5. What the World Checker samples and what fails

Settled: [WORLDCHECKER.md](WORLDCHECKER.md), "Settings" and "Outcome", has the sampling (eye
and follow cameras over every floor, rooftops, the air between rooftops, seams and vantage
points, each with the layer combinations) and the default thresholds, which are this document's
earlier placeholders. The Asset Checker demands zero wrong-depth pixels and no ordering cycles
for an isolated asset; a whole street from the near pass will not meet that, so the World
Checker allows a bounded fraction of the screen outside a near band of the camera, and none
within it or on an entity.

## Build order

**Decided:**

1. **A movement garden** ([PLATFORMER.md](PLATFORMER.md#the-movement-garden)). Movement is
   tuned in a small garden cart, which is also the first level built with the World Kit: a
   slope, a ledge, a wall, one collectible and one camera zone, as the one-cell world above,
   growing as the moves need. Paths come before ground heightfields.
2. **One small district block.** A few cells of one region, with stand-ins, a layer, and palette
   variants.
3. **A second region,** to force the texture-swap seam.

*Proposal: what each stage proves and needs.*

| Stage | Proves | Needs first |
|---|---|---|
| 1 | Recipe, schema, ID lock file, pack, collision format and queries, holes check, one-view budget check | The runtime reader, the collision decision, the tool and the World Checker (done) |
| 2 | Cell selection, two-pass sorting, stand-ins, layers, the World Checker at scale, the per-cell budgets above | The larger ROM, palette-backed materials, the material class and the scene probe (done) |
| 3 | Region resources, seams, swaps spread over frames, stand-ins across a region boundary | Textures and UVs in the Asset Kit (on [texture windows](DECISIONS.md#texture-windows)), or the seam has only palettes and audio to change |

Interiors (the mall) need nothing new after stage 1: a door is an entity with a `world_ref`.

**Where it stands** (2026-10-03). Everything stage 1 and stage 2 need first is built, and the
two example worlds rehearse their shapes: `test_room` is a one-cell garden (slope, ledge, wall,
collectible, a trigger, a layer pair), and `two_districts` four cells in two regions with
stand-ins, a layer, palette variants and merged scatter, both checked by the World Checker on
every build and walked through in World Viewer. Neither stage is built as the game: the movement
garden cart, its character control and its camera zones are the game's
([PLATFORMER.md](PLATFORMER.md)), and stage 2's per-cell budgets have been measured only on the
examples ([WORLDCHECKER.md](WORLDCHECKER.md#ground)). Stage 3's region resources are built
(2026-10-04: texture sets, night variants, animated textures, backdrops; the example
`night_market`, two regions); its seams are not ([Region seams](#region-seams)).
Terrain (2026-10-04) is built, with a third example, `shrine_grounds`, the shape of the shrine
grounds the garden's shrine hill is to grow into ([Terrain](#the-example-shrine-grounds)).
Cliffs, water, draped paths, things set on the ground and scatter (2026-10-04) are built, with a
second terrain example, `forest_mountain` ([Terrain](#the-example-forest-mountain)).
