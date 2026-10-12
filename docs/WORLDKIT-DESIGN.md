# World Kit design record

The design of the World Kit as the project owner decided it (most of it on 2026-10-03), the
proposals made along the way and what is still open. What is built is described in the guide,
[WORLDKIT.md](WORLDKIT.md), and the reference, [WORLDKIT-REFERENCE.md](WORLDKIT-REFERENCE.md);
this file keeps the reasons and the history, so that the reference can say only what exists.
Proposals are marked *Proposal*; where one has since been built, a note says so and points to
the reference.

## Status and history

This record was the first part of WORLDKIT.md while the World Kit was a design ("Status: design,
partly built"). What has been built since is in the guide's [status](WORLDKIT.md#status); not
built yet are audio banks and spreading a region swap over a seam
([WORLDKIT-REFERENCE.md](WORLDKIT-REFERENCE.md#region-seams)), and the [proposals](#proposals-not-built)
and [open questions](#open-questions) below. [Build order](#build-order) says where the stages
stand. The game that motivates the kit is described in [PLATFORMER.md](PLATFORMER.md). The kit
depended on three things, all now in place:

- **A larger cart ROM.** A cart may be up to 64 MB, read in place from a 128 MB window at
  `0x08000000` (commit `620a8d1`; [DECISIONS.md](DECISIONS.md), "Cart ROM: up to 64 MB in a
  128 MB window"). Embeds of 64 KB or more go to the assembler in memory, so a large pack costs
  compile time in proportion to its size. See [ROM](WORLDKIT-REFERENCE.md#rom).
- **The Asset Kit** ([ASSETKIT.md](ASSETKIT.md)), with the changes this design asked of it, most of
  which have landed: see [Asset Kit changes this needs](#asset-kit-changes-this-needs).
- **A runtime.** Tsumiki, the stdlib 3D toolkit that had a scene, solids, a character controller
  and cameras, was removed in October 2026 ([ROADMAP.md](ROADMAP.md)). Its replacement for worlds
  is the narrow pack reader `stdlib/worldpack.akr` (cells, culled drawing in passes, collision
  queries, entity tracking; [WORLDPACK.md](WORLDPACK.md)).

## Decisions

The project owner settled the decisions in the table below. They are stated as the design.
Everything else marked *Proposal* was this document's addition, there for the owner to accept or
argue with. Numbers are derived from the spec and docs with the arithmetic shown, or marked
*placeholder*.

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
| 15 | Units: the tools enforce no scale; the convention is one unit per metre | [Recipe files and units](#recipe-files-and-units) |

Decisions made later, while building, are recorded where they apply: the floor query bridging
small cracks (2026-10-05, [Collision](#collision)) and the heights file as a text grid
([Terrain](#terrain)).

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

### What the Asset Kit was when the design was written

As checked against `tools/mei_assets.py` and `tools/assetkit/` on 2026-10-03. Since then the Asset
Kit has gained textures and UVs, authored levels of detail, decals and semi-transparent
materials ([ASSETKIT.md](ASSETKIT.md)), and its Asset Checker a depth mode:

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
- Texture and UV authoring (then proposed in ASSETKIT.md, "Textures"; built 2026-10-04), LOD
  generation and animation were not included.

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
   palette-backed face is a 4-bit textured face sampling one texel of a solid swatch, tinted by its
   baked shade ([ASSETKIT-REFERENCE.md](ASSETKIT-REFERENCE.md#palette-backed-materials)). With the
   material manifest and `relocate()`, a packer can move an asset's entries into a region's
   palettes.
3. **Done: surface tags and the vertical bake** (`tag`, `lighting.mode: "vertical"`).
4. **Done: forced separate entries and a manifest for every build.** Surface materials of the
   same colour share an entry by default; a recipe may force separate ones (`"share": false`).
   The material manifest is written for every build, so a world build reads one shape of data
   for every asset.
5. **Done: textures and UVs.** Regions own texture sets (decision 4). The Asset Kit authors textured
   assets ([ASSETKIT-REFERENCE.md](ASSETKIT-REFERENCE.md#textures)) and the World Kit packs them per
   region ([Textures per region](WORLDKIT-REFERENCE.md#textures-per-region)). Repeating textures use
   the Prism Engine's per-polygon **texture windows**
   ([DECISIONS.md](DECISIONS.md#texture-windows)), which `mesh()` already sends from a mesh's window
   table: many small repeating tiles share one texture slot instead of a slot each.

Two items earlier versions of this list carried are no longer Asset Kit changes: terrain belongs
to the World Kit ([Terrain](#terrain)), and the scene probe is a World Kit component (part of the
World Checker)
([Verification](#verification)).

## Data model

**Decided: one format for open worlds and discrete levels.** A world is a set of self-contained
cells plus an index; the runtime keeps the cells near the player active. A discrete level is a
world with one cell, or with every cell always active. Interiors such as the mall are separate
one-cell (or few-cell) worlds reached through doors. A door is an ordinary entity whose game type
happens to carry a world reference.

**Decided: layers.** A layer is a named group of placements within a cell that the game switches:
festival stalls that appear at night, a bridge raised by a switch, the before and after states of
a building site. The kit does not know what a layer means. It knows the group exists so it can
check triangle budgets and sorting with each layer on. (Built:
[WORLDKIT-REFERENCE.md](WORLDKIT-REFERENCE.md#data-model).)

*Proposal* (not built): the world recipe may name a shared `common` file holding the common
texture set and common palettes, so the city and the mall interiors use the same common set and a
door between them only swaps region resources.

## Terrain

**Decided: terrain belongs to the World Kit.** Ground (a heightfield) and paths (a profile swept
along a line) are described in world coordinates in the world recipe, generated by the shared
core and cut per cell by the kit, so seams match by construction. They are the only modelling the
World Kit does. Paths are world data in their own right too: the same line can be a road, a
traffic route or a rail to grind. Paths come first.
Terrain collision comes from the terrain itself. (Built, paths first and then terrain:
[WORLDKIT-REFERENCE.md](WORLDKIT-REFERENCE.md#terrain).)

**Decided while building: the heights file is a text grid, not a PNG heightmap.** Agents author
terrain, and they read and edit text line by line; a text grid diffs and reviews in git, carries
metres exactly with no scale or bit depth to choose, and needs nothing beyond the standard
library (the kits build recipes without Pillow).

### Corrections to the reserved design

- **Several placements a cell, not one.** The reservation had one terrain piece per cell; a tile
  (by default 16 quads, 32 m at 2 m spacing) is the unit instead, so culling and levels of detail
  work on pieces of a useful size and a cell of 128 units at 1 m stays inside the 2,048 vertices
  of a mesh.
- **Terrain in a cell file stays reserved** (an error that says to put terrain in the world
  file): nothing has needed it.
- **Sweeps follow their path's line, or drape.** The ground is shaped to the path with a `bed`, or a
  [draped](WORLDKIT-REFERENCE.md#draped-paths) path takes its heights from the ground as the
  operations left it and then cuts its own bed, so the order the reservation worried about (the
  ground before the beds that depend on it) is the build's order.

## Streaming without a disc

**Decided.** Cart ROM is memory-mapped, so geometry and collision are read in place, as on the
N64, not loaded from a disc as on the PlayStation or in GTA. `embed` already places files in ROM
and `mesh()` draws a `*Mesh` that points into ROM (LANGUAGE.md, "Memory" and "Mesh format").
"Streaming" means choosing which cells to draw and collide with, swapping a region's textures
and palettes in VRAM, and spawning and retiring entities; cells are position-independent blobs
behind an index. What that means for the pack, ROM and VRAM is in
[WORLDKIT-REFERENCE.md](WORLDKIT-REFERENCE.md#streaming-rom-and-vram).

### Regions and the VRAM split

**Decided.** A region (district) owns a texture set, named palette variants, an audio bank and a
backdrop. VRAM cannot hold two regions' textures at once, so there is a shared common set plus
one set per region, and swaps happen at natural seams: underpasses, covered arcades, station
concourses.

*The first placeholder split* (with 1 MB, never built): slots 0–5 common, 6–13 region, 14 effects
and HUD, 15 fonts; palettes 0–63 common, 64–191 region, 192–254 backdrop, HUD and effects.

Swap cost: filling all 16 slots costs about 900,000 cycles (spec p. 11), so about 56,000 a slot
(PLANES.md gives the same for a 32 KB atlas). A region's 8 slots are about 450,000 cycles, nearly
half a frame's 1,000,000; all 30 a region may have are about 1,700,000, nearly two frames.
*Proposal:* swap one slot a frame (about 6% of the CPU) over 8 frames, plus the region's palettes,
while the player is inside a seam. During those frames nothing on screen may use region textures,
which the kit can check (see [Verification](#verification)). Not built:
[WORLDKIT-REFERENCE.md](WORLDKIT-REFERENCE.md#region-seams) lists what a seam still needs.

**Found while checking: sight lines cross region boundaries.** From a downtown rooftop the electric
town is visible while its textures are not loaded. *Proposal:* stand-ins use only the common set and
common palettes, so any cell's stand-in can be drawn whichever region is loaded, and a cell in a
region that is not loaded is always drawn as its stand-in, even when near. Region boundaries that
the player can approach without passing a seam then show stand-ins at close range; the layout should
avoid that (a viaduct, a wall of buildings, a river), and the kit can report where it happens.
Built: the kit's stand-ins draw far colours (palette entries of their region, every region's
palettes being loaded at once) and, for cutouts, the stand-ins' own texture set, which every
region's set holds ([Stand-ins made by the kit](WORLDKIT-REFERENCE.md#stand-ins-made-by-the-kit)).

**As built, regions get disjoint palettes**
([WORLDKIT-REFERENCE.md](WORLDKIT-REFERENCE.md#palettes-per-region)). That departs from the
placeholder split above, which shared one range among regions and swapped it: with flat-colour
materials a region needs tens of colours, not hundreds, so every region's palettes can be loaded at
once, and a far cell's stand-in is coloured correctly whichever region the player is in. Shared
ranges belong with region texture sets, when there is something to swap.

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
around the player. (Built in the reader as three passes, far, ground and near:
[WORLDPACK.md](WORLDPACK.md#what-a-reader-does), "Drawing".)

**Decided: ground first.** Within the near cells, the placements a level marks as ground are drawn
in a pass of their own before the rest (the world pack's ground pass), so nothing standing on the
ground sorts behind a large ground face; see [Ground](WORLDKIT-REFERENCE.md#ground) and
WORLDPACK.md, "Ground".

The far backdrop (skyline, sky gradient, distant hills) belongs on the Horizon Engine, the plane
chip ([PLANES.md](PLANES.md)): a tile plane and a backdrop line table cost no GPU cycles and no
triangles.

**Fixed point limits world coordinates.** `length`, `normalize` and the dot product overflow for
vectors longer than about 181 (LANGUAGE.md), and Tsumiki told carts to keep levels within about
±90 units. A city is far larger. *Proposal:* the pack stores every cell's contents in cell-local
coordinates around the cell's centre, and the runtime renders camera-relative: the camera's cell
centre is the origin for the frame, and each placement's position is its local position plus an
integer number of cells. Collision queries happen in the player's cell's frame. With 64-unit cells
local coordinates stay within ±32 plus overhang. (Built: the pack's cell-local coordinates and the
reader's camera-relative drawing, [WORLDPACK.md](WORLDPACK.md#what-a-reader-does).)

**No per-object culling then.** `mesh*()` transforms every vertex of every mesh it is given (26
cycles a vertex, 40 with fog) before culling faces. The runtime needs a bounding-sphere or box
test per placement and per cell before calling `mesh*()`. The kit computes the bounds. (Built: the
reader culls each cell by its bounds and each placement by its sphere.)

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

## Game data and stable IDs

**Decided.** Goals, collectibles, switches, triggers and missions are entries with a type, a
stable ID and parameters. The game defines the types and supplies a schema; the kit validates
recipes against it and otherwise does not interpret them. Stable IDs matter because each goal has
a saved bit that must survive level edits, as the Asset Kit asks agents to preserve node IDs. The
stakes are higher here: an Asset Kit ID only labels a report; a World Kit ID addresses a player's
save.

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

## Recipe files and units

**Decided: units.** The tools do not enforce a scale. The convention, used by the examples and the
platformer, is one unit per metre (the Asset Kit's stool seat is at 0.8).

**One file per cell** confirms an earlier proposal: an open world of hundreds of cells in one
JSON file is unwieldy for an agent and close to the 8 MiB input limit, and an agent editing one
cell should not rewrite the others.

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
from the terrain itself ([Terrain](WORLDKIT-REFERENCE.md#terrain)).

**Decided: surface types are an opaque byte the game defines.** The kit derives each collision
triangle's surface byte from its material's Asset Kit `tag` through a table in the world recipe,
without knowing what slippery, wall-jump or ledge-grab mean. Floor, wall and ceiling are classified
by the normal against the game schema's `probe.floor_max_degrees`; the body radius (`probe.radius`)
sets how far walls are copied past a cell's edge (the pack's `pad`). Moving objects (trains, lifts)
are entities with a collision asset in their own frame; the game moves them and the runtime tests
queries in that frame.

**Decided (2026-10-05): the floor query bridges small cracks, and the World Checker agrees.** The
shrine town's World Checker reports held about 50 cracks of 0.016 to 0.25 units, which drowned the
real problems; the rule and its costs are in [Cracks](WORLDKIT-REFERENCE.md#cracks).

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

## Proposals not built

### A level bias that follows the measured cost

*Proposal*, not built ([levels of detail as built](WORLDKIT-REFERENCE.md#levels-of-detail)). The
switch distances are set for a world's worst views, so every other view draws coarser than it could:
in the shrine town the full check's median view is about 310,000 draw CPU cycles of the 600,000
budget. The reader could scale the distances it compares by a bias *b* (0.75–1.5), kept per frame
from what the last frames cost:

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
range's top). Levels then become a quality floor rather than a budget, and the zones' sooner levels
(`carts/garden/shrinetown/DESIGN.md` 12.6) could go back to the recipes' own, the bias pulling them
in only where a view needs it. What it cannot fix: a single frame's spike (a region entered, cells
loaded), and GPU-bound views, which a CPU measurement does not see (the GPU's `GPU_CYCLES` could be
averaged the same way).

### Two more commands

*Proposals*, not built ([the command line as built](WORLDKIT-REFERENCE.md#command-line)):
`verify FILE [-o DIR] [--cell ID] [--layers A,B]` (the World Checker on a recipe, diagnostic only;
today it runs on a built pack, `python3 tools/worldkit/verify.py PACK -o DIR`), and `standin-draft
FILE --cell ID -o RECIPE` (an Asset Kit recipe of boxes from the cell's placement bounds, for an
agent to edit; the Asset Kit then builds it like any other, so the World Kit still models
nothing).

### One loader for several worlds

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

**Decided:** a uniform square grid, the cell size chosen per world (16, 32, 64 or 128 units: the
pack's `cell_shift` 4–7) and stored in the pack header; it is not a property of the format or the
runtime. The same holds for runtime capacities, such as active entities or placements drawn a frame:
they are constants each cart sets, not limits of the format (the reader keeps no storage per
placement or entity; WORLDPACK.md, "The console reader"). *Recommendation:* 64 units until stage 2
measures. Alternatives considered: a quadtree or irregular cells for districts of very different
density, and a precomputed potentially-visible set per cell, which the kit could produce offline
from the same renders it verifies with; in a dense city, buildings hide most cells. (Built since,
per hand-placed zone rather than per cell: [Occlusion](WORLDKIT-REFERENCE.md#occlusion).)

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
operations are `set`, `add`, `carve`, `fill`, `ramp`, `terrace`, `smooth`, `bed`, `paint`,
`hole`, `cliff` and `water` ([Heightfields](WORLDKIT-REFERENCE.md#heightfields)), and a path that
drapes itself over the ground ([Draped paths](WORLDKIT-REFERENCE.md#draped-paths)). Open: noise or
erosion (the recipe has no random generation, so it would need a seed).

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

**Where it stands** (2026-10-03). Everything stage 1 and stage 2 need first is built, and the two
example worlds rehearse their shapes: `test_room` is a one-cell garden (slope, ledge, wall,
collectible, a trigger, a layer pair), and `two_districts` four cells in two regions with stand-ins,
a layer, palette variants and merged scatter, both checked by the World Checker on every build and
walked through in World Viewer. Neither stage is built as the game: the movement garden cart, its
character control and its camera zones are the game's ([PLATFORMER.md](PLATFORMER.md)), and stage
2's per-cell budgets have been measured only on the examples
([WORLDCHECKER.md](WORLDCHECKER.md#ground)). Stage 3's region resources are built (2026-10-04:
texture sets, night variants, animated textures, backdrops; the example `night_market`, two
regions); its seams are not ([Region seams](WORLDKIT-REFERENCE.md#region-seams)). Terrain
(2026-10-04) is built, with a third example, `shrine_grounds`, the shape of the shrine grounds the
garden's shrine hill is to grow into ([Terrain](WORLDKIT-REFERENCE.md#the-example-shrine-grounds)).
Cliffs, water, draped paths, things set on the ground and scatter (2026-10-04) are built, with a
second terrain example, `forest_mountain`
([Terrain](WORLDKIT-REFERENCE.md#the-example-forest-mountain)).
