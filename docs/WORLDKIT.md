# Mei World Kit

**Status: design, partly built.** What exists: the pack format ([WORLDPACK.md](WORLDPACK.md),
normative) with its reference encoder `tools/worldkit/pack.py`; the console reader
`stdlib/worldpack.akr`. The tool itself, `tools/mei_world.py`, is being built to the
[command line](#command-line-sketch) below. Not built yet: terrain, the in-level
verification gate and its scene probe (being built separately as `tools/worldkit/verify.py` and
`tools/worldkit/scene_probe.c`), textures, audio banks and backdrops. This document records the
decisions made so far, proposes the rest, and lists what is still open. Where it and the owner's
later decisions in [DECISIONS.md](DECISIONS.md) ("World Kit, Asset Kit and the first open-world
game") ever disagree, DECISIONS.md wins. It depends on three things, all now in place:

- **A larger cart ROM.** A cart may be up to 64 MB, read in place from a 128 MB window at
  `0x08000000` (commit `620a8d1`; [DECISIONS.md](DECISIONS.md), "Cart ROM: up to 64 MB in a
  128 MB window"). Embeds of 64 KB or more go to the assembler in memory, so a large pack costs
  compile time in proportion to its size. See [ROM](#rom).
- **The Asset Kit** ([ASSETKIT.md](ASSETKIT.md)), with the changes this design asked of it, most of
  which have landed: see [Asset Kit changes this needs](#asset-kit-changes-this-needs).
- **A runtime.** Tsumiki, the stdlib 3D toolkit that had a scene, solids, a character controller
  and cameras, was removed in October 2026 ([ROADMAP.md](ROADMAP.md)). Its replacement for worlds
  is the narrow pack reader `stdlib/worldpack.akr` (cells, culled two-pass drawing, collision
  queries, entity tracking; [WORLDPACK.md](WORLDPACK.md)).

The World Kit is a command-line tool for AI agents, a sibling of the Asset Kit. An editable JSON
recipe places Asset Kit assets into cells and regions, attaches game data to them, and builds one
native world pack that a cart embeds. A verification gate samples cameras through the playable
space and reports budget overruns, face-ordering errors and holes in collision (report-only at
first; see [Verification](#verification)).

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
| 9 | In-level verification: budgets, ordering, collision holes; the scene probe is a World Kit component; thresholds are per-world settings and the gate starts report-only | [Verification](#verification) |
| 10 | Time-neutral, rotation-neutral baked shading; materials draw through palette entries; emissive materials get entries of their own | [Day and night](#day-and-night) |
| 11 | Build order: a movement garden (the first World Kit level), one district block, a second region | [Build order](#build-order) |
| 12 | The boundary is "could you place it twice?": reusable things are assets | [The boundary](#the-boundary-with-the-asset-kit) |
| 13 | Terrain (ground heightfields and swept paths, in world coordinates) belongs to the World Kit | [Terrain](#terrain) |
| 14 | Collision is authored separately as simpler geometry; surface types are an opaque byte | [Collision](#collision) |
| 15 | Units: the tools enforce no scale; the convention is one unit per metre | [Recipe format](#recipe-format-sketch) |

## What this is for

The motivating game is a 3D platformer with Mario 64-style movement, set in a 1990s Japanese
metropolis: downtown, shrines, parks, an electric-town district and a mall. The city is one open
world of several regions with many small goals: a collectible unit scattered everywhere, and
switches that start short challenges, in the manner of Mario Kart World's open world. The mall is
an interior reached through doors.

The same kit should serve games built from discrete levels, without a second format.

## Goals and non-goals

Goals:

- One recipe format and one pack format for a one-room test level, a course-based game and a
  multi-region open world.
- Placement, grouping and game data only. Every triangle comes from an Asset Kit recipe.
- A numerical gate, like the Asset Kit's, that an agent can iterate against: budgets, sorting and
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
4. **Approved: forced separate entries and a manifest for every build.** Surface materials of the
   same colour share an entry by default; a recipe may force separate ones. The material
   manifest is written for every build, so a world build reads one shape of data for every asset.
5. **Textures and UVs.** Regions own texture sets (decision 4), but the Asset Kit cannot author
   textured surfaces yet (proposed in [ASSETKIT.md](ASSETKIT.md), "Textures"). Until it can, a
   region's texture set is empty, and the stage-3 texture-swap seam has nothing to swap.

Two items earlier versions of this list carried are no longer Asset Kit changes: terrain belongs
to the World Kit ([Terrain](#terrain)), and the scene probe is a World Kit component
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

*Proposal:* layers are per cell, at most 8 per cell (one byte of mask), and may name an
`exclusive` group: `bridge_up` and `bridge_down` in group `bridge` are never on together. The
game can switch a layer in many cells at once by name; the runtime maps the name to each cell's
bit. Entities can be in layers too.

*Proposal:* the world recipe may name a shared `common` file holding the common texture set and
common palettes, so the city and the mall interiors use the same common set and a door between
them only swaps region resources.

## Terrain

**Decided: terrain belongs to the World Kit.** Ground (a heightfield) and paths (a profile swept
along a line) are described in world coordinates in the world recipe, generated by the shared
core and cut per cell by the kit, so seams match by construction. They are the only modelling the
World Kit does. Paths are world data in their own right too: the same line can be a road, a
traffic route or a rail to grind. Neither is needed before the movement garden; paths come first.
Terrain collision comes from the terrain itself.

**Not built.** What is reserved for it, so nothing built first blocks it:

- The world recipe reserves a top-level `terrain` property (an error today, with a message
  saying so), and a cell file the same, so terrain can be world-wide (cut per cell by the kit) or,
  if that ever proves useful, per cell.
- The generated geometry is an ordinary native mesh per cell plus collision triangles in world
  coordinates, which the pack already holds: a cell's stand-in, placements and collision block
  take it with no format change. A terrain piece would be packed as a placement at its cell's
  centre whose mesh is in cell-local coordinates (yaw 0), as a merged mesh of small scatter props
  would be.
- Materials and palette entries of terrain would be declared in the world recipe and packed into
  region palettes by the same packer as asset entries, so a path's kerb can share an entry with
  a building's stone.
- Paths as world data (a rail to grind, a traffic route) would be named and exported to the
  generated `.akr` as point lists, or carried as entities of a game type, whichever the game
  schema asks for. The kit attaches no meaning to them.

## Streaming without a disc

**Decided.** Cart ROM is memory-mapped, so geometry and collision are read in place, as on the
N64, not loaded from a disc as on the PlayStation or in GTA. `embed` already places files in ROM
and `mesh()` draws a `*Mesh` that points into ROM (LANGUAGE.md, "Memory" and "Mesh format").
"Streaming" here means three things only:

1. choosing which cells to draw, and at what detail, and which to collide with;
2. swapping textures and palettes in the 1 MB of VRAM when the player crosses into a region;
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

VRAM is 1,024 KB (spec p. 11, PLANES.md "Memory map"):

| Use | Size | Note |
|---|---|---|
| framebuffers A and B | 300 KB | 2 × 153,600 bytes |
| spare | 4 KB | |
| palette memory | 8 KB | 4,096 colours; palette 255 (colours 4080–4095) is the font's |
| plane chip line tables | 8 KB | convention |
| plane chip pages 10–15 | 192 KB | maps and atlases for backdrops |
| texture slots 0–15 | 512 KB | 32 KB each (one 4-bit 256×256 texture; an 8-bit one takes two) |

300 + 4 + 8 + 8 + 192 + 512 = 1,024. Slot 15 holds the fonts (rows 0–66), so 15 whole slots are
free for polygons.

*Placeholder split:* slots 0–5 common, slots 6–13 region (8 slots, 256 KB), slot 14 effects and
HUD, slot 15 fonts. Palettes as 4-bit palettes of 16: 0–63 common (1,024 colours), 64–191 region
(2,048 colours), 192–254 backdrop, HUD and effects, 255 font. The kit enforces whatever split the
world recipe declares and reports use per region.

Swap cost: filling all 16 slots costs about 900,000 cycles (spec p. 11), so about 56,000 a slot
(PLANES.md gives the same for a 32 KB atlas). A region's 8 slots are about 450,000 cycles, nearly
a whole frame's 500,000. *Proposal:* swap one slot a frame (about 11% of the CPU) over 8 frames,
plus the region's palettes, while the player is inside a seam. During those frames nothing on
screen may use region textures, which the kit can check (see [Verification](#verification)).

**Found while checking: sight lines cross region boundaries.** From a downtown rooftop the
electric town is visible while its textures are not loaded. *Proposal:* stand-ins use only the
common set and common palettes, so any cell's stand-in can be drawn whichever region is loaded,
and a cell in a region that is not loaded is always drawn as its stand-in, even when near. Region
boundaries that the player can approach without passing a seam then show stand-ins at close
range; the layout should avoid that (a viaduct, a wall of buildings, a river), and the kit can
report where it happens.

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

The far backdrop (skyline, sky gradient, distant hills) belongs on the plane chip (PLANES.md):
a tile plane and a backdrop line table cost no GPU cycles and no triangles.

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
guard band about 3,000. Suppose world drawing gets 250,000 of the 500,000 CPU cycles (the spec's
"What the budget buys" leaves half for game logic). For closed meshes with about one vertex per
two faces and half the faces facing away, a submitted face costs about
0.5 × 145 + 0.5 × 48 + 0.5 × 26 ≈ 110 cycles, so about 2,300 faces, of which about 1,150 are
visible. Ten faces clipped near the camera take 40,000 of that. That leaves roughly 2,000 submitted
faces a frame, near and far together.

For comparison, Tsumiki's Playroom ran at a median of 903 triangles, peak 1,555, with CPU at
46% median and 67% peak (TSUMIKI.md, removed; in git history before `ad01707`).

The GPU is unlikely to bind first: 1,200 visible triangles cost 48,000 cycles of setup, and 2.5
screens of textured fill (192,000 pixels × 2) cost 384,000, about 43% of the 1,000,000 budget.

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

*Proposal: the game schema.* A small file the game owns, in the kit's own restricted format so
that parameters can be packed into fixed records the cart reads without parsing:

```json
{
  "format": "mei-world-game",
  "version": 1,
  "probe": {"radius": 0.3, "height": 1.6, "step": 0.32, "floor_max_degrees": 40},
  "types": {
    "coin": {"saved": true, "params": {}},
    "challenge_switch": {"saved": true, "params": {
      "course": {"type": "entity_ref"},
      "time_window": {"type": "enum", "values": ["any", "day", "night"]}
    }},
    "camera_zone": {"params": {
      "size": {"type": "vec3"},
      "mode": {"type": "enum", "values": ["follow", "fixed", "rail"]}
    }},
    "door": {"params": {"world": {"type": "world_ref"}, "spawn": {"type": "name"}}}
  }
}
```

Field types are `bool`, `u8`, `s16`, `s32`, `fixed`, `vec3`, `enum`, `name`, `entity_ref` and
`world_ref`. The kit checks that references resolve, without knowing why they exist, and emits an
Akari `struct` per type in the generated `.akr`. `saved: true` asks the kit for a persistent bit
index per entity of that type. `probe` describes the player's body for collision checks and camera
sampling; the kit uses it as geometry, not as movement rules. Everything else (what `night` means,
whether a coin respawns) is the game's.

*Proposal: the ID lock file.* The kit writes `NAME.ids.json` beside the recipe and expects it to
be committed. It maps every saved entity's ID to its bit index, append-only. A deleted entity's
bit is retired, never reused; a new entity gets the next free bit. Renaming is a delete plus an
add unless the entity says `"was": "old_id"`. Builds fail if the lock file and the recipe disagree
in a way that would move an existing bit. A save holds up to 32,000 bytes (MEMCARD.md), so bits
are not scarce: 256,000 of them.

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
per-vertex blend costing CPU every frame), and the plane chip's colour offset (`PLN_OFS`), a
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

## Recipe format (sketch)

The conventions are the Asset Kit's: `format` and `version`, names matching
`^[a-z][a-z0-9_]{0,47}$`, unknown properties and duplicate keys are errors, errors carry a JSON
Pointer `path` and a `message`, no expressions or random generation, Y up, world units, angles in
degrees.

**Decided: units.** The tools do not enforce a scale. The convention, used by the examples and the
platformer, is one unit per metre (the Asset Kit's stool seat is at 0.8). A one-cell test room
(stage 1):

```json
{
  "format": "mei-world",
  "version": 1,
  "name": "test_room",
  "game": "game.schema.json",
  "assets": {"dir": "../assets"},
  "grid": {"cell_size": 64},
  "regions": {
    "lab": {
      "palette_variants": ["day", "night"],
      "palettes": {
        "concrete": ["#a4a8ad", "#3b4255"],
        "lamp": ["#fff3c4", "#ffe08a"]
      }
    }
  },
  "cells": [
    {"id": "room", "at": [0, 0], "region": "lab", "standin": "room_far",
     "layers": {"gate_open": {}},
     "placements": [
       {"id": "floor", "asset": "room_floor", "position": [32, 0, 32]},
       {"id": "slope", "asset": "ramp_4x2", "position": [38, 0, 36], "yaw": 90},
       {"id": "ledge", "asset": "ledge_block", "position": [26, 0, 36]},
       {"id": "wall", "asset": "climb_wall", "position": [32, 0, 44]},
       {"id": "gate", "asset": "gate", "position": [32, 0, 24], "layer": "gate_open"}
     ],
     "entities": [
       {"id": "coin_ledge", "type": "coin", "asset": "coin", "position": [26, 2.5, 36]},
       {"id": "cam_wall", "type": "camera_zone", "position": [32, 1, 42],
        "params": {"size": [8, 4, 4], "mode": "fixed"}}
     ]}
  ]
}
```

Notes on the sketch:

- `asset` names an Asset Kit recipe: `ramp_4x2` resolves to `../assets/ramp_4x2.asset.json`.
  The world recipe never contains geometry.
- `at` is the cell's grid coordinate; cell (i, j) covers x from 64i to 64i + 64 and z from 64j to
  64j + 64. Positions are world coordinates in the recipe, and the kit checks that each
  placement's position lies in its cell, then stores it cell-locally.
- `palettes` gives one colour per variant for each palette-backed material name.
- `standin` names an ordinary asset recipe, `room_far`.
- Collision is absent from this sketch; see [Collision](#collision).
- `textures`, `audio` and `backdrop` on a region are left out until there is something to put in
  them; their formats are not designed here.

*Proposal: one file per cell.* An open world of hundreds of cells in one JSON file is unwieldy
for an agent and close to the Asset Kit's 8 MiB input limit. A world file can list
`"cells": {"dir": "cells"}` instead, with each cell in `cells/ID.cell.json` holding exactly the
object shown above. The kit reports and verifies one cell at a time on request.

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

## Build outputs and the runtime contract

For a world named `city`, `build` produces (*proposal*):

| File | Purpose |
|---|---|
| `city.world.bin` | The pack: index, regions, cells, mesh pool, collision, entity records |
| `city.akr` | `embed WORLD_CITY: u8 = "city.world.bin"`, the entity `struct`s, layer and region name constants |
| `city.ids.json` | The ID lock file (written beside the recipe, not in the output directory) |
| `city.world.json` | Copy of the recipe (and its cell files) |
| `report.json` | Per cell and region: triangles, bytes, VRAM and palette use, asset hashes, warnings |
| `verification.json` | Gate results, as the Asset Kit's |
| `preview/` | Native renders per region and palette variant, and a contact sheet |

Outputs are staged and replaced only on success, and a failed gate leaves the previous pack in
place with `verification.failed.json`, as in the Asset Kit.

**The pack format is specified in [WORLDPACK.md](WORLDPACK.md)** (version 1.0), byte by byte:
header, sparse index, layers, regions, cells, placements, entities and their parameter records,
collision blocks with precomputed rows and a lookup grid, and the mesh pool (meshes stay in the
native format). `tools/worldkit/pack.py` is the reference encoder and decoder the kit builds on,
and `stdlib/worldpack.akr` the console reader. What the reader does each frame (cells from the
index, the two drawing passes, collision in the player's cell, entities spawned and retired as
cells and layers change, region palettes) is in WORLDPACK.md, "What a reader does"; what it
does not do is in [open question 3](#3-the-runtime).

## Verification

**Decided.** The analogue of the Asset Kit's gate: sample camera positions through the playable
space, including rooftops and the air between them, since they give the longest sight lines, and
check GPU and CPU budgets and face ordering; plus collision checks for holes.

**Decided: the scene probe is a World Kit component,** not an Asset Kit change: it renders
scenes rather than single meshes, from arbitrary camera positions, with several meshes per view,
textured (palette swatch) faces, and near-plane and guard-band clipping (a camera standing in a
level always has floor faces crossing the near plane). It is being built as
`tools/worldkit/verify.py` and `tools/worldkit/scene_probe.c`.

**Decided: thresholds are per-world settings** with defaults from the kit, and the gate starts
in **report-only** mode until a real level has been measured: it records what it finds in the
build report and fails nothing. Switching a world to enforcing is an explicit edit of its recipe.

*Proposal:* what a build checks, in three groups.

**Static checks (no rendering).**

- Every referenced asset builds and passes its own verification policy.
- References resolve: assets, regions, layers, stand-ins, entity types, `entity_ref`,
  `world_ref`. Parameters match the game schema.
- Placements lie in their cells; no placement's bounds overhang a neighbouring cell by more than
  a declared margin (*placeholder*: 8 units), which keeps the two-pass sort sound.
- The ID lock file agrees with the recipe.
- VRAM and palette use per region fit the declared split. Stand-ins use only the common set.
- Collision: no cracks, meaning boundary edges of walkable floors that face another floor within
  `probe.step` in height across a gap narrower than `probe.radius`; floor edges on a cell
  boundary match the neighbouring cell's; no entity origin inside solid collision.

**Sampled views (rendered natively).** Cameras are sampled from walkable floors (a grid over each
cell's floor triangles at the probe's eye height and a follow-camera offset), from authored
vantage points, from every cell's highest floors (rooftops), and from points inside seams. Each
view runs the real runtime in a generated verification cart, as the Asset Kit generates a
preview cart, and records CPU cycles, GPU cycles, triangles submitted and dropped, and packet
arena use. It also renders the triangle-ID buffer and compares it with the independent
rasterizer, as the Asset Kit does. Views are repeated with each layer combination: all off, each
layer alone, and the largest set allowed by the exclusive groups.

**Failure, once enforcing.** Dropped triangles and a full packet arena always fail. Budget and
ordering thresholds are per-world settings ([question 5](#5-what-the-gate-samples-and-what-fails)
has the starting defaults). In seam views, any drawn face that samples a region texture fails,
because those slots are being overwritten.

The Asset Kit's checker cannot do this as it stands: it rejects views with near-plane and
guard-band clipping and renders one mesh, hence the scene probe. Its ID rendering has to strip
the textured flag while keeping coverage, and palette index 0 (never drawn) makes holes in
textured faces that the expected rasterizer must reproduce. How long a sweep takes per view was
not measured for this document.

## Command line (sketch)

Parallel to `mei_assets.py`: JSON on stdout for successes and failures, exit 0 or 1, `-` for
stdin, `--compiler`, `--runner` and `--probe` to use other builds.

| Command | Result |
|---|---|
| `schema [--game FILE]` | The world recipe's JSON Schema, with the game's entity types folded in |
| `init FILE [--example room\|block]` | Editable starter world, with its asset recipes |
| `validate FILE` | Static checks only |
| `inspect FILE [--cell ID]` | Static checks plus per-cell and per-region costs |
| `verify FILE [-o DIR] [--cell ID] [--layers A,B]` | Sampled-view gate, diagnostic only |
| `build FILE -o DIR [--verify] [--preview]` | The pack and its imports; recipe-mandated gate as in the Asset Kit |
| `preview FILE -o DIR [--cell ID] [--variant NAME]` | Native renders of cells from sampled and vantage cameras |
| `standin-draft FILE --cell ID -o RECIPE` | An Asset Kit recipe of boxes from the cell's placement bounds, for an agent to edit |

`standin-draft` writes an ordinary asset recipe and stops; the Asset Kit builds it like any
other, so the World Kit still models nothing. *All commands are proposals.*

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
the runtime. *Recommendation:* 64 units until stage 2 measures. Alternatives considered: a quadtree or irregular cells for districts of very different density, and a
precomputed potentially-visible set per cell, which the kit could produce offline from the same
renders it verifies with; in a dense city, buildings hide most cells.

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
cut per cell by the kit, so seams match by construction instead of by a seam check. Until it is
built, ground can be written as an explicit Asset Kit `mesh` per cell.

### 5. What the gate samples and what fails

Open: sample density per cell; which yaws and pitches; whether follow-camera positions are
sampled or only eye positions. Decided: thresholds are per-world settings with kit defaults, and
the gate starts report-only. The Asset Kit demands zero wrong-depth pixels and no ordering cycles
for an isolated asset. A whole street from the near pass will not meet that.

*Recommendation for the defaults:* zero wrong-order pixels and no cycles where either face belongs to an
entity's asset or lies within a near band of the camera (*placeholder*: 16 units); a bounded
fraction of the screen elsewhere (*placeholder*: 0.5%), reported with witnesses; GPU cycles at
most 80% of 1,000,000 and CPU cycles for drawing at most 60% of 500,000 in every view
(*placeholders*), leaving room for game logic and for camera positions the sampling missed.

## Build order

**Decided:**

1. **A movement garden.** Movement is tuned in a small garden cart, which is also the first level
   built with the World Kit: a slope, a ledge, a wall, one collectible and one camera zone, as the
   one-cell world above, growing as the moves need. Paths come before ground heightfields.
2. **One small district block.** A few cells of one region, with stand-ins, a layer, and palette
   variants.
3. **A second region,** to force the texture-swap seam.

*Proposal: what each stage proves and needs.*

| Stage | Proves | Needs first |
|---|---|---|
| 1 | Recipe, schema, ID lock file, pack, collision format and queries, holes check, one-view budget gate | The runtime reader and the collision decision (both done) |
| 2 | Cell selection, two-pass sorting, stand-ins, layers, the sampled-view gate at scale, the per-cell budgets above | The larger ROM, palette-backed materials and the material class (done); the scene probe (in progress) |
| 3 | Region resources, seams, swaps spread over frames, stand-ins across a region boundary | Textures and UVs in the Asset Kit, or the seam has only palettes and audio to change |

Interiors (the mall) need nothing new after stage 1: a door is an entity with a `world_ref`.
