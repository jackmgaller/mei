# Mei World Kit

**Status: design proposal.** There is no `tools/mei_world.py` yet. The pack format and a runtime
that reads it now exist ([WORLDPACK.md](WORLDPACK.md), `stdlib/worldpack.akr`); the rest is not
implemented. This document records the design decisions made so far, proposes the rest, and lists
what is still open. It depends on three things:

- **A larger cart ROM.** Today a cart is at most 2 MB, mapped at `0x200000`
  ([DECISIONS.md](DECISIONS.md), "Cart file format"). A change to a 64 MB limit inside a 128 MB
  window at `0x08000000` is in progress and not yet merged. A test room fits in 2 MB; an open
  world with several regions does not (see [ROM](#rom)).
- **The Asset Kit** ([ASSETKIT.md](ASSETKIT.md)), plus the changes to it listed in
  [Asset Kit changes this needs](#asset-kit-changes-this-needs).
- **A runtime.** Tsumiki, the stdlib 3D toolkit that had a scene, solids, a character controller
  and cameras, was removed in October 2026 ([ROADMAP.md](ROADMAP.md)). Its replacement for worlds
  is the narrow pack reader `stdlib/worldpack.akr` (cells, culled two-pass drawing, collision
  queries, entity tracking; [WORLDPACK.md](WORLDPACK.md)).

The World Kit is a command-line tool for AI agents, a sibling of the Asset Kit. An editable JSON
recipe places Asset Kit assets into cells and regions, attaches game data to them, and builds one
native world pack that a cart embeds. A verification gate samples cameras through the playable
space and fails the build on budget overruns, face-ordering errors and holes in collision.

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
| 9 | In-level verification: budgets, ordering, collision holes | [Verification](#verification) |
| 10 | Time-neutral baked shading; emissive materials need their own palette entries | [Day and night](#day-and-night) |
| 11 | Build order: test room, one district block, a second region | [Build order](#build-order) |

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

- **Modelling.** No geometry operations in world recipes, not even "a floor here". Terrain,
  buildings and platforms are assets. The owner explicitly does not want a hybrid tool.
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
- A material is `color` (`#RRGGBB`) plus optional `smooth` and `double_sided`. Lighting is baked
  at export into per-vertex RGB colours from one direction and an ambient term.
- Output is one native mesh: at most 2,048 vertices, an authoring budget of up to 4,000
  triangles, every face **untextured** (flags are only Gouraud and double-sided). Mesh size is
  16 + 16 × vertices + 36 × faces bytes. `build` also writes an `.akr` embed, an OBJ, a Modeler
  project, a preview cart and `report.json` with recipe and mesh hashes.
- `verify` renders a triangle-ID version of the mesh through the real compiler and GPU, compares
  every pixel with an independent reciprocal-depth rasterizer, and builds a far-before-near
  ordering graph to find cycles. It samples **fitted cameras around one isolated mesh** (144
  views by default) and rejects views that need near-plane or guard-band clipping. It accepts
  only opaque untextured faces.
- Texture and UV authoring, LOD generation and animation are not included.

### Decided: separate tool, shared core, one-way dependency

World recipes reference asset recipes by name. The Asset Kit never learns that levels exist.
World recipes contain no modelling operations; asset recipes contain no placement or game data.
Level geometry (terrain, buildings, platforms) is modelled as assets and placed by the world
recipe.

The shared core is what both tools import: fixed-point geometry and quantization, the compiler
and probe wrappers, schema validation with JSON Pointer errors, and native preview rendering.

*Proposal:* extract the core from `tools/assetkit/` into a package both import (for example
`tools/meikit/`), and let the World Kit additionally call the Asset Kit's public compile entry
point to build the assets a world references. The dependency stays one-way. One concrete
refactor this needs: `assetkit/schema.py`'s `validate` resolves `$ref` against its own module's
`SCHEMA`, so it cannot validate a second schema yet.

*Proposal:* a world build compiles every referenced asset recipe itself, requires each asset's
own verification policy to pass, and records each recipe's hash in the world report, so a world
build is reproducible from recipes alone and never trusts a stale `.bin`.

### Asset Kit changes this needs

These are Asset Kit features, not World Kit features. Each is generic: none mentions worlds.

1. **A material class (decided, decision 10).** Emissive materials (neon, lit windows) must get
   palette entries of their own so they can brighten while everything else darkens. *Proposal:*
   `"class": "emissive"` on a material, default `"surface"`.
2. **Palette-backed materials (found while checking; see [Day and night](#day-and-night)).**
   Palettes only affect textured faces: a palette colour reaches the screen through a texel, and
   the Asset Kit emits no textured faces. A material class alone therefore changes nothing on
   screen. Day/night palette variants need materials that draw through a palette entry.
3. **Textures and UVs.** Regions own texture sets (decision 4), but the Asset Kit cannot author
   textured surfaces. Until it can, a region's "texture set" is empty, and the stage-3
   texture-swap seam has nothing to swap.
4. **Possibly terrain operations** (`heightfield`, extrude-along-path). Open; see
   [open question 4](#4-terrain-operations-in-the-asset-kit).
5. **A probe for scenes, not single meshes,** for in-level verification: arbitrary camera
   positions, several meshes per view, textured faces, and views with near-plane and guard-band
   clipping (a camera standing in a level always has floor faces crossing the near plane). This
   belongs in the shared core.

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
A 2 MB cart (less its code, audio and the system's needs) holds on the order of a hundred such
meshes: enough for the test room and one block, not for a city. 64 MB holds about 3,500 of them
before textures and audio, and instances share one copy. ROM stops being the limit; VRAM and the
frame budget remain.

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
Emissive materials need palette entries of their own so they can brighten while everything else
darkens, which needs a material class in the Asset Kit.

**Found while checking: palettes do not reach Asset Kit meshes.** A palette colour reaches the
screen only through a texel of a textured face; an untextured face's colour is its vertex colour.
The Asset Kit emits only untextured faces with lighting baked into RGB. So `palette_lerp` cannot
change the colour of any Asset Kit asset today. Options, none decided:

- **(a) Palette-backed materials.** The Asset Kit draws each material as a 4-bit textured face
  sampling a solid swatch of one palette entry, with the baked shade as the vertex tint (128 is
  unchanged). Palette variants and emissives then work as decided. Cost: textured pixels are
  twice the GPU fill (above, still about 43% of the budget), and textured faces can only fog
  toward dark colours (spec p. 17), which suits night but not bright haze.
- **(b) Recolour vertices at run time.** Meshes are in ROM and cannot be written, so this needs
  RAM copies of the colour words, or a per-vertex blend in the draw path like fog's (about 14
  more cycles a vertex). It costs CPU every frame for every vertex drawn.
- **(c) The plane chip's colour offset.** With the compositor on, `PLN_OFS` darkens or tints the
  low polygon layer at no cost, and emissive faces drawn as upper (PH) pixels without the offset
  bit stay bright (PLANES.md, "Colour offset" and "The priority bit"). It is a uniform additive
  shift, not a palette, and it spends the PH layer on emissives.

*Recommendation:* (a), because it is the decided model and the GPU has room; (c) is worth
keeping for a whole-screen dusk tint on top.

*Proposal:* the shape shading that "time-neutral" implies should also be rotation-neutral.
Today the Asset Kit bakes one directional light in the asset's own frame. A building placed at
yaw 180 then has its lit side facing the wrong way relative to every other building. A mostly
vertical bake direction (tops light, walls mid, undersides dark) survives any yaw.

*Placeholder palette cost:* blending a region's 2,048 colours every frame is 2,048 × 38 = 77,824
cycles, 16% of the CPU. Blending 256 colours a frame (9,728 cycles, 2%) refreshes the whole region
every 8 frames, which is smooth enough for a day that lasts minutes.

## Recipe format (sketch)

The conventions are the Asset Kit's: `format` and `version`, names matching
`^[a-z][a-z0-9_]{0,47}$`, unknown properties and duplicate keys are errors, errors carry a JSON
Pointer `path` and a `message`, no expressions or random generation, Y up, world units, angles in
degrees. A one-cell test room (stage 1), assuming 1 unit is about 1 metre (the Asset Kit examples
suggest that scale, a stool seat at 0.8; nothing in the repo fixes it):

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
- `palettes` gives one colour per variant for each palette-backed material name. This depends on
  [Asset Kit change 2](#asset-kit-changes-this-needs); until then it has no effect on screen.
- `standin` names an ordinary asset recipe, `room_far`.
- Collision is absent because its source is [open](#1-collision-source-and-surface-types).
- `textures`, `audio` and `backdrop` on a region are left out until there is something to put in
  them; their formats are not designed here.

*Proposal: one file per cell.* An open world of hundreds of cells in one JSON file is unwieldy
for an agent and close to the Asset Kit's 8 MiB input limit. A world file can list
`"cells": {"dir": "cells"}` instead, with each cell in `cells/ID.cell.json` holding exactly the
object shown above. The kit reports and verifies one cell at a time on request.

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
space, including high vantage points, since rooftops give the longest sight lines, and fail the
build on GPU budget overruns and face-ordering errors; plus collision checks for holes.

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

**Failure.** Dropped triangles and a full packet arena always fail. Budgets and ordering
thresholds are open ([question 5](#5-what-the-gate-samples-and-what-fails)). In seam views, any
drawn face that samples a region texture fails, because those slots are being overwritten.

The Asset Kit's checker cannot do this as it stands: it rejects views with near-plane and
guard-band clipping, renders one mesh, and accepts only untextured faces
([Asset Kit change 5](#asset-kit-changes-this-needs)). The ID rendering also has to strip the
textured flag while keeping coverage, and palette index 0 (never drawn) makes holes in textured
faces that the expected rasterizer must reproduce. How long a sweep takes per view was not
measured for this document.

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

Options:

- **(a) Derived from the render meshes,** filtered by a material tag in the Asset Kit. No extra
  authoring, but render meshes are detailed (window frames, signs) and a player catches on detail
  that should be smooth.
- **(b) Authored separately as simpler geometry:** a collision asset per placement (an ordinary
  Asset Kit recipe, `shop_row_col`), or `"collision": "self"` for simple props.
- **(c) Analytic solids** as Tsumiki had: boxes, ramps, upright cylinders and one heightfield.
  Tsumiki chose these on purpose and left triangle soup out because plane tests need wide
  products and divisions per triangle, thin triangles lose precision, and a spatial index is
  needed. That fits rooms; a city's slopes, stairs and roofs do not reduce to them.

Surface types (slippery, wall-jump, ledge-grab) and floor/wall/ceiling classes are game data. The
kit can classify by normal against the game's `probe.floor_max_degrees`, and carry a surface byte
from the collision asset's material names through a world-level table, without knowing what
either means. Moving objects (trains, lifts) are entities with a collision asset in their own
frame; the game moves them and the runtime tests queries in that frame.

*Recommendation:* (b) triangles, with the expensive work moved into the kit. The kit has the
geometry offline and can precompute plane equations, classes and a per-cell lookup grid in
cell-local coordinates, which addresses the precision and division costs that ruled out triangle
soup for Tsumiki. Tsumiki's measured costs (a floor query among 41 solids about 2,000 cycles) are
the target to beat.

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

*Recommendation:* a uniform square grid of 64 units with a sparse index, until stage 2 measures.
Alternatives: a quadtree or irregular cells for districts of very different density, and a
precomputed potentially-visible set per cell, which the kit could produce offline from the same
renders it verifies with; in a dense city, buildings hide most cells.

### 3. The runtime

With Tsumiki removed, the stdlib needs at least: pack and index lookup; cell selection and
two-pass drawing with per-placement culling and camera-relative transforms; collision queries
(floor under a point, push out of walls, ceiling, a ray for the camera); texture and palette
swapping spread over frames; entity spawn and retire lists with layer masks.

Where the contract is drawn: *recommendation:* the pack format is the contract, versioned in its
header, and a narrow reader module answers only geometric questions. Character control, cameras,
goals and saving stay in the game. Tsumiki was a broad toolkit; the reasons it was removed "in
favour of a different approach" are not recorded in the repo, so a narrow reader is the safer
guess, not a known preference. Whether it lives in `stdlib/` (imported only by carts that use it,
as `planes.akr` is) or ships with the kit is open.

### 4. Terrain operations in the Asset Kit

Terrain can be written today as an explicit `mesh` (up to 8,192 vertices in the recipe, 2,048 in
the exported mesh), but an agent then writes every height by hand, and there are no expressions.
Candidates: `heightfield` (a grid of heights) for parks and shrine hills, and a sweep of a profile
along a path for roads, kerbs, rails and viaducts. Both are generic modelling and would not
mention worlds. Terrain that spans cells is split into one asset per cell either way, and the
kit's seam check makes the edges agree. *Recommendation:* add both, after stage 1 shows what the
test room's slopes needed.

### 5. What the gate samples and what fails

Open: sample density per cell; which yaws and pitches; whether follow-camera positions are
sampled or only eye positions; and the thresholds. The Asset Kit demands zero wrong-depth pixels
and no ordering cycles for an isolated asset. A whole street from the near pass will not meet
that.

*Recommendation, to start:* zero wrong-order pixels and no cycles where either face belongs to an
entity's asset or lies within a near band of the camera (*placeholder*: 16 units); a bounded
fraction of the screen elsewhere (*placeholder*: 0.5%), reported with witnesses; GPU cycles at
most 80% of 1,000,000 and CPU cycles for drawing at most 60% of 500,000 in every view
(*placeholders*), leaving room for game logic and for camera positions the sampling missed.

## Build order

**Decided:**

1. **One test room.** Movement and collision first: a slope, a ledge, a wall, one collectible and
   one camera zone, as the one-cell world above.
2. **One small district block.** A few cells of one region, with stand-ins, a layer, and palette
   variants.
3. **A second region,** to force the texture-swap seam.

*Proposal: what each stage proves and needs.*

| Stage | Proves | Needs first |
|---|---|---|
| 1 | Recipe, schema, ID lock file, pack, collision format and queries, holes check, one-view budget gate | The runtime reader; collision decided. Fits in a 2 MB cart |
| 2 | Cell selection, two-pass sorting, stand-ins, layers, the sampled-view gate at scale, the per-cell budgets above | The larger ROM; palette-backed materials and the material class in the Asset Kit; the scene probe |
| 3 | Region resources, seams, swaps spread over frames, stand-ins across a region boundary | Textures and UVs in the Asset Kit, or the seam has only palettes and audio to change |

Interiors (the mall) need nothing new after stage 1: a door is an entity with a `world_ref`.
