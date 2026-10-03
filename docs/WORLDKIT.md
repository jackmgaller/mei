# Mei World Kit

**Status: design, partly built.** What exists: the pack format ([WORLDPACK.md](WORLDPACK.md),
normative) with its reference encoder `tools/worldkit/pack.py`; the console reader
`stdlib/worldpack.akr`; the tool, `tools/mei_world.py`, with the [recipe format](#recipe-format)
and [command line](#command-line) below; and the **World Checker**, the in-level verification
every build runs ([WORLDCHECKER.md](WORLDCHECKER.md)). Not built yet: terrain, textures, audio
banks and backdrops. This document records the project owner's decisions (most of them made on
2026-10-03), proposes the rest, and lists what is still open. The game that motivates it is
described in [PLATFORMER.md](PLATFORMER.md). It depends on three things, all now in place:

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
5. **Textures and UVs.** Regions own texture sets (decision 4), but the Asset Kit cannot author
   textured surfaces yet (proposed in [ASSETKIT.md](ASSETKIT.md), "Textures"). Until it can, a
   region's texture set is empty, and the stage-3 texture-swap seam has nothing to swap.

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
- Terrain is ground by default ([Ground](#ground)): a heightfield is the open floor that
  ground-first drawing is for, and a swept path lying on it is too. A raised path (a bridge, a
  viaduct) is not, so a path will be able to say so.
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

**Decided: ground first.** Within the near cells, the placements a level marks as ground are drawn
in a pass of their own before the rest (the world pack's ground pass), so nothing standing on the
ground sorts behind a large ground face; see [Ground](#ground) and WORLDPACK.md, "Ground".

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
edges; the World Checker samples cameras with its `radius`, `height` and `step`. `GAME.game.akr`
exports it as `GAME_PROBE_RADIUS` and `_FLOOR_MAX_DEGREES`, `_HEIGHT` and `_STEP` when the
schema gives them, and `_CEILING_MAX_DEGREES` (always: the angle the kit used), so a cart moves
the same body the level was checked for. It is geometry, not movement rules.
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
probe requires `radius` and `floor_max_degrees`; `height`, `step` and `ceiling_max_degrees` are
optional. `convert` writes the canonical style shown above (probe values and field types aligned,
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

## Recipe format

The conventions are the Asset Kit's: `format` and `version`, names matching
`^[a-z][a-z0-9_]{0,47}$`, unknown properties and duplicate keys are errors, errors carry a JSON
Pointer `path` and a `message`, a `file` when the error is in a cell file or the game schema, and
a `line` and `column` when that file is Mochi ([Game data](#game-data-and-stable-ids)). There are
no expressions or random generation; Y is up, lengths are world units and angles degrees. `schema` is the
authoritative contract; `schema --game FILE` folds one game's entity types and parameters in.

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
| `grid.cell_size` | 16, 32, 64 or 128 units: the pack's `cell_shift`. Cell (*i*, *j*) (`at`) covers *x* in [*i S*, (*i*+1) *S*) and *z* likewise |
| `overhang` | How far a placement may reach past its cell (default 8, at most half a cell) |
| `collision.pad` | How far walls are copied past a cell's edge: at least, and by default, the probe radius |
| `collision.surfaces` | Material `tag` to surface byte; untagged faces and unmapped tags get `default` (unmapped tags are listed in the warnings) |
| `palette` | `swatch_slot` and `swatch_row` (default 14, 0): where the world's swatch row lives in VRAM; `first`: the first 4-bit palette regions are given (default 0) |
| `regions` | Named regions in order (the pack's region numbers): optional `palettes` (`first`, `count`) and `variants`. `textures`, `audio` and `backdrop` are reserved and rejected for now |
| `layers` | World-wide layer names in order (the pack's layer ids), each with an optional exclusive `group` and `on` (at start) |
| `verification` | The World Checker's per-world settings: `mode` (`report`, the default, or `enforce`) and `thresholds` |
| `terrain` | Reserved ([Terrain](#terrain)); rejected for now |

A **placement** is an `id` (unique in its cell; reports and the pack's 16-bit tag follow it), an
`asset`, a `position` (world coordinates, in the cell), `yaw` (degrees, as `mesh_at()`), an
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
`palettes.first` may place them, and overlaps are errors). That departs from the placeholder split
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

### Merged scatter

`"merge": true` on a placement merges it, with the cell's other merged placements of the same
layer and the same `ground`, into one mesh placed at the cell's centre (split only between
props, at 2,048 vertices or 4,000 faces). The reader spends about 500 cycles on every placement
it draws beyond its vertices and faces (WORLDPACK.md, "Costs"), so eight bollards cost one
placement instead of eight; the price is ROM (each copy's vertices are stored) and coarser
culling (one sphere). Collision is unchanged: each merged prop keeps its own. The pack needs no
new record. `report.json` lists what was merged per cell.

### Ground

`"ground": true` on a placement makes it **ground**: the reader draws the near cells' ground in a
pass of its own before everything else near the camera, so nothing standing on it can be drawn
behind it (WORLDPACK.md, "Ground", has the reasons and the exact cases). Without a depth buffer a
large floor face sorts by its average depth, and one ordering table draws it over the feet of what
stands on it; flagging the floors of the two example worlds took their near-camera wrong-order
pixels from 153,444 to 2,775 (`test_room`) and from 365,309 to 318,722 (`two_districts`, where
most of what is left is inside the shop asset; WORLDCHECKER.md, "Ground").

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
neighbours' tops, and ground faces that overlap are sorted among themselves as before. Objects
stand on the ground, not in it: a buried part is drawn over the ground. Stand-ins are never ground
(a stand-in is the whole cell); a merged mesh is ground when its props are. The World Checker
warns of geometry an upward ground face can hide (`ground_hides`) and of ground that can overlap
ground (`ground_over_ground`), and counts the pixels where the ground truly hides what is drawn
over it (`ground_inversion`, a threshold).

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

For a world named `city` of a game named `game`, `build` produces:

| File | Purpose |
|---|---|
| `city.world.bin` | The pack: index, regions, cells, mesh pool, collision, entity records |
| `city.akr` | `embed WORLD_CITY: u8 = "city.world.bin"`; `world_city_load()` (opens the pack, copies the swatch, loads every region's first variant); constants for regions, variants, colour ranges (`_SURFACE`, `_EMISSIVE` and their counts), layers, entity numbers and saved bits; `world_city_string()` for `name` parameters |
| `game.game.akr` | The game's type numbers, world numbers, probe constants, parameter `struct`s and `enum`s, imported by every world of the game; make links one copy per game for a cart's worlds, so a cart compiles it once ([Using a world in a cart](#using-a-world-in-a-cart)) |
| `city.swatch` | The 8-byte palette swatch row, when any material is palette-backed |
| `city.ids.json` | A copy of the ID lock file (the lock itself is written beside the recipe) |
| `source/` | The world file, cell files and every asset recipe used, as built, and the game schema exactly as written (Mochi comments kept; the report's `game_sha256` is the hash of its JSON form, so comments and layout do not change it) |
| `report.json` | Per cell and region: triangles (always and per layer), placements, collision triangles by kind, bytes, palettes and variants, entity numbers, ID changes, asset hashes and Asset Checker results, warnings, the World Checker's result |

With `preview` (or `build --preview`) there is also `preview/`: for every region, its busiest
cell seen from a fixed camera above its south edge, once per palette variant, drawn by the real
reader (so far cells appear as stand-ins), as PNGs with GPU statistics, and `contact.png`.
Every build also writes `verification/`: the World Checker's report, `world-check.json`, and
pictures of its worst views ([WORLDCHECKER.md](WORLDCHECKER.md)).

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

**The pack format is specified in [WORLDPACK.md](WORLDPACK.md)** (version 1.1), byte by byte:
header, sparse index, layers, regions, cells, placements, entities and their parameter records,
collision blocks with precomputed rows and a lookup grid, and the mesh pool (meshes stay in the
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
`--probe` to use other builds, `--assets DIR` to use another asset directory.

| Command | Result |
|---|---|
| `schema [--game FILE]` | The world recipe's JSON Schema (cell files and game schemas under `$defs`, Mochi under `$defs/game/x-mochi`), with the game's entity types (Mochi or JSON) folded in when given |
| `convert FILE [-o OUT] [--force]` | A game schema in the other form: JSON to canonical Mochi, or a `.mochi` file to JSON. Without `-o`, the result holds the `text` (Mochi) or `game` (JSON) |
| `init DIR [--example room\|city] [--force]` | Copies an example world (world file, cells, game schema, asset recipes) into a new directory |
| `validate FILE` | Every static check: schemas, references, game data, IDs, palettes, that every asset compiles and that the pack can hold the world; the ID changes a build would make |
| `inspect FILE [--cell ID]` | The same, with the full report: per cell and per region costs, palettes and variants, entity numbers, asset hashes, warnings |
| `build FILE -o DIR [--locked] [--preview] [--world-checker full\|skip\|N]` | The outputs above; runs each asset's required Asset Checker policy, then the World Checker seam |
| `preview FILE -o DIR [--cell ID] [--locked] [--world-checker full\|skip\|N]` | `build`, plus native renders of a cell per region and palette variant (`--cell` picks the cell) |

`--world-checker` is for quick builds, such as the World Kit's own tests: `full` (the default)
runs the World Checker with the world's settings; `skip` does not run it, and `report.json`
says so (`"verification": {"ran": false, "ok": null, "skipped": true, "reason": ...}`); a number
*N* samples at most *N* views (the checker's `sampling.max_views`), and the report's
`verification.reduced` records it. A world whose recipe says `"verification": {"mode":
"enforce"}` builds only with the full check: `skip` or *N* is refused with an error at
`/verification/mode`. make's world rule ([Using a world in a cart](#using-a-world-in-a-cart))
always runs the full check.

*Proposals, not built:* `verify FILE [-o DIR] [--cell ID] [--layers A,B]` (the World Checker,
diagnostic only), and `standin-draft FILE --cell ID -o RECIPE` (an Asset Kit recipe of boxes from
the cell's placement bounds, for an agent to edit; the Asset Kit then builds it like any other, so
the World Kit still models nothing).

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
material). `make test-world` (also part of `make test`) runs `tests/test_worldkit.py`, which builds
both and runs them on the console.

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
   world test_room: 1 cell, 12,592 bytes, 0 warnings -> build/worlds/examples/worlds/test_room
     World Checker (report): 132 views, 0 hard failures, 79 over thresholds; peaks 50 tris, CPU 56,018, GPU 198,538 cycles; build/worlds/examples/worlds/test_room/verification/world-check.json
   ```

   An invalid recipe stops make with the kit's errors, one per line (`file:line:column: JSON
   Pointer: message`), and the `mei_world.py validate` command that gives them as JSON;
2. links every world's `NAME.akr`, `NAME.world.bin` and `NAME.swatch`, and each game's
   `GAME.game.akr`, into `build/cart-worlds/NAME/` (`tools/world_cart.py link`), so that worlds
   of one game share one `GAME.game.akr`. Two worlds of one name, or two worlds of one game
   built from different game schemas, are an error;
3. compiles the cart with `meic -I build/cart-worlds/NAME`: an import that is not next to the
   importing file is looked for there before the standard library
   ([LANGUAGE.md](LANGUAGE.md#building-and-running)).

A world is rebuilt when its recipe, a cell file, its game schema, its ID lock file, an asset
recipe, its cell or asset folder (a file added or removed), or the kit's Python changes:
`build.d` beside the build records what the build read. Editing the cart's own files rebuilds
only the cart. A recipe edit that adds a saved entity updates the ID lock file beside the recipe,
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
layer (`wp_variant_name`, `wp_layer_name`). Stick: move; d-pad or right stick:
look; L and R: down and up; A: walk or fly; B: next palette variant; SELECT and X: choose a layer
and switch it; START: next world; Y: hide the overlay.

**Open** (found while writing World Viewer; neither is built): a helper that draws the live
entities' meshes in the near cells, which every game that draws entities writes for itself
(World Viewer's `draw_entities()`, the World Checker's verification cart); and a way to call
"the open world's" generated functions without a branch per world (World Viewer's
`world_load(k)` chooses between `world_test_room_load()` and `world_two_districts_load()`).

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
cut per cell by the kit, so seams match by construction instead of by a seam check. Until it is
built, ground can be written as an explicit Asset Kit `mesh` per cell.

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
| 3 | Region resources, seams, swaps spread over frames, stand-ins across a region boundary | Textures and UVs in the Asset Kit, or the seam has only palettes and audio to change |

Interiors (the mall) need nothing new after stage 1: a door is an entity with a `world_ref`.
