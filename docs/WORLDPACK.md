# The world pack format

**Version 1.5.** A world pack (`*.world.bin`) is the contract between the World Kit
([WORLDKIT.md](WORLDKIT.md)), which writes packs, and the reader a cart runs, which reads them in
place from ROM. This document is normative: a second encoder or reader can be written from it
alone. The reference implementations are `tools/worldkit/pack.py` (encoder, decoder and an exact
query oracle) and `stdlib/worldpack.akr` (the console reader); `tests/test_worldpack.py` checks
both against each other.

What each part's status is:

| Part | Format | Reference encoder/decoder | Console reader |
|---|---|---|---|
| Header, index, cells | specified | yes | yes |
| Placements, stand-ins, layers | specified | yes | yes: drawing, culling, layer masks |
| Ground placements (1.1) | specified | yes | yes: drawn first, in a pass of their own |
| Paths (1.2) | specified | yes, with an exact oracle | yes: by number and name, nearest point, point at a length, lines for debugging |
| Levels of detail, near range (1.3) | specified | yes, with the exact level rule | yes: a level per placement with hysteresis; the pack's near range |
| [Objects](#objects): entity meshes, the game's own | (not part of the format) | – | yes: culled, keyed at their nearest point, nearer from above (in depth mode: culled only) |
| Collision blocks (cells and entities) | specified | yes, with an exact oracle | yes: floor, ceiling, wall push, segment |
| Entities and parameter records | specified | yes | yes: iteration, tracking, lookup by number |
| Regions: palette variants, texture set | specified | yes | palettes loaded and blended; textures loaded at once (`wp_region_enter()`, or a texture at a time) |
| Region extensions (1.4): palette runs, animated textures, the backdrop's sky | specified | yes | yes: every run loaded and blended, frames copied when they change, the sky and silhouette drawn by the plane chip (`wpbackdrop.akr`) |
| Regions: backdrop copies | specified | yes | yes: copied on entering the region |
| Occlusion zones (1.5) | specified | yes, with the zone oracle | yes: the eye's zone found per frame, what it hides skipped |
| Regions: audio bank | specified | yes | **specified, reader not yet implemented** |
| Mesh pool | the native mesh format | yes | drawn by `mesh()`'s face loops |

## Contents

1. [Conventions](#conventions)
2. [Versions](#versions)
3. [Limits](#limits)
4. [Layout](#layout)
5. [Header](#header)
6. [Index](#index)
7. [Layers](#layers)
8. [Regions](#regions)
9. [Cells](#cells)
10. [Placements](#placements)
11. [Levels of detail](#levels-of-detail)
12. [Ground](#ground)
13. [Occlusion zones](#occlusion-zones)
14. [Objects](#objects)
15. [Entities](#entities)
16. [Collision blocks](#collision-blocks)
17. [Paths](#paths)
18. [Meshes and strings](#meshes-and-strings)
19. [What a reader does](#what-a-reader-does)
20. [Validation](#validation)
21. [Precision](#precision)
22. [Costs](#costs)
23. [The console reader](#the-console-reader-stdlibworldpackakr)
24. [Extensions not made](#extensions-not-made)

## Conventions

- **Bytes.** Little-endian. `u8 u16 u32 s16 s32` as in Akari. `fixed` is a signed 16.16 number
  stored as `s32` (raw value / 65,536). A *row* is four consecutive `fixed` values, laid out as an
  Akari `vec4`.
- **Offsets.** Every reference is a `u32` byte offset from the first byte of the pack. 0 means
  "none" (nothing lives at offset 0: the header does). There are no pointers.
- **Alignment.** The pack starts on a 4-byte boundary (`embed` guarantees it). Every table and
  record starts on a 4-byte boundary, so every `u32`, `fixed` and row load is aligned. (The CPU's
  `vld` needs only 4-byte alignment.) Strings need none.
- **Reserved fields** are written as zero and ignored by readers.
- **World coordinates.** Units, +X right, +Y up, +Z forward, as `gfx.akr`. Yaw turns +Z toward
  +X, as `mesh_at()` does: a model point (x, y, z) at yaw θ is placed at
  (x cos θ + z sin θ, y, −x sin θ + z cos θ).
- **The grid.** The world is a uniform square grid of cells of size *S* = 2^`cell_shift` units.
  Cell (*i*, *j*) covers *x* in [*i S*, (*i*+1) *S*) and *z* in [*j S*, (*j*+1) *S*): the low sides
  belong to the cell, the high sides to its neighbours. The cell holding world *x* is
  ⌊*x* / *S*⌋, which for a `fixed` is `(x as s32) >> cell_shift` (floor, then an arithmetic shift).
  *S* is a per-world choice made in the world recipe and carried in the header; nothing in the
  format or the reader assumes 64.
- **Cell-local coordinates.** Everything a cell holds is stored relative to its centre
  *C* = (*i S* + *S*/2, 0, *j S* + *S*/2): local = world − *C*. *y* is not offset. Local *x* and
  *z* of a point in the cell are in [−*S*/2, *S*/2).
- **Front faces.** A collision triangle (*a*, *b*, *c*) has the front normal
  (*c* − *a*) × (*b* − *a*), the side from which its corners appear counter-clockwise: the same
  winding as a mesh face (LANGUAGE.md, "Mesh format"), so a mesh's faces are usable as collision
  as they are (a quad's triangles are (0, 1, 2) and (2, 1, 3)).
- **Rounding.** Where the encoder rounds an exact value to `fixed`, it rounds to nearest with
  halves away from zero, so that round(−*v*) = −round(*v*). One property depends on it (shared
  edges, below).

## Versions

The header holds a major and a minor version; this document is 1.5.

- A reader refuses a pack whose **major** version it does not know.
- A reader accepts a pack with the same major and a **higher minor** version and reads it as the
  minor version it knows. A minor version may only add: data reached through fields that are
  reserved (zero) in earlier minors, header bytes past those the earlier minors define (the
  header says its own size: 1.2 defines 72, 1.3 80, 1.4 and 1.5 84), and flag bits. It never changes the size or meaning of an existing field or
  record.
- Header **flags** bits 0–3 mark features a reader may ignore; bits 4–7 mark features a reader
  must understand, so a reader refuses a pack with a bit 4–7 set that it does not know. Version
  1.1 defines bit 0 (ground); none of bits 4–7 is defined.

**1.1** adds [ground](#ground): placement flags bit 0, the cell's `ground_count` (its first
reserved word) and header flags bit 0. It is a minor version because it only gives meaning to
fields that are reserved, and so zero, in 1.0, and because ignoring them is safe: a 1.0 reader
draws a 1.1 pack's ground in the near pass with everything else, which is the 1.0 picture (the
ground sorted by its own depth), not a misreading; nothing else about the pack changes. The other
way round, a 1.0 pack reads as a pack without ground: a 1.1 reader reads the three fields only in
a pack whose minor version is at least 1. A 1.1 pack without ground differs from a 1.0 pack only
in its minor version.

**1.2** adds [paths](#paths): the header grows to 72 bytes (`header_size` 72) with `path_count`
and `path_off`, which point at a table of named polylines. It is a minor version because it only
adds header bytes past the 64 that 1.1 defines and data reached through them: a 1.1 reader, which
finds everything through offsets, reads a 1.2 pack as before and sees no paths. The other way
round, a reader reads the path words only when the minor version is at least 2 (a 1.2 pack's
`header_size` must then be at least 72), so a 1.0 or 1.1 pack has no paths. A 1.2 pack of a world
without paths has `path_count` and `path_off` 0; it differs from the 1.1 pack of the same world in
its minor version, its `header_size` and those 8 bytes, and so in every offset after the header,
which moves by 8.

**1.3** adds [levels of detail](#levels-of-detail) and the near range: the header grows to 80
bytes with `near_far` and `lod_slots`, and a cell's first two reserved words become `lod_off` and
`lod_first`. A placement's `mesh` stays its full-detail mesh (level 0), so a 1.2 reader draws a
1.3 pack as it always did, every placement at full detail and with its own near range: the right
picture, at the old cost. A 1.3 reader reads the four words only in a pack whose minor version is
at least 3 (and whose `header_size` is then at least 80), so older packs have no levels and the
default near range. A 1.3 pack of a world without levels or a near range has the four words 0; it
differs from the 1.2 pack in its minor version, `header_size` and those 8 header bytes (every later
offset moves by 8). The reader draws such a pack exactly as before: the one change on its path is a
test of `lod_off` per cell.

**1.4** adds [region extensions](#region-extensions-14): the header grows to 84 bytes with
`region_ext_off`, which points at one 32-byte record per region holding its extra palette runs
(8-bit texture palettes), its animated textures and its backdrop's sky record. A 1.3 reader reads
a 1.4 pack as before: the region records, their texture sets, main palette runs and backdrop
copies are 1.0 fields, so it loads the textures and the palettes of the main run, and sees no
8-bit runs, no animations and no sky. A reader reads `region_ext_off` only in a pack whose minor
version is at least 4 (and whose `header_size` is then at least 84). The reference encoder
writes 1.4 only for a world that needs an extension (an 8-bit texture, an animated texture or a
backdrop); every other world's pack is the 1.3 pack, byte for byte, as before 1.4 existed. A
world whose textures are all 4-bit and still, without a backdrop, stays 1.3: its texture set
and variants are 1.0 fields.

**1.5** adds [occlusion zones](#occlusion-zones): a cell's last two reserved words become
`zone_count` and `zone_off`, which point at the cell's zones, each a box the eye may be in and
the placements and stand-ins hidden from all of it. The header is the 1.4 header (84 bytes;
`region_ext_off` is 0 in a pack without region extensions). A 1.4 reader reads a 1.5 pack as
before and draws what the zones hide too: the right picture, at the old cost. A reader reads the
two cell words only in a pack whose minor version is at least 5. The reference encoder writes 1.5
only for a world that has a zone; every other world's pack is the 1.3 or 1.4 pack, byte for byte,
as before 1.5 existed.

## Limits

| What | Limit | Why |
|---|---|---|
| `cell_shift` | 4–7 (cells of 16, 32, 64 or 128 units) | A power of two, so finding a cell is a shift. 128 keeps local coordinates (±64 plus pad) well inside the ±181 at which `length()` and `dot()` of a local vector overflow, and keeps the near pass's ordering buckets (far = 1.5 cells: 0.19 units at 128) about kerb-deep. Below 16 the 3 × 3 near set spans under 48 units |
| World extent | every cell within ±32,767 units in *x* and *z* | World coordinates are `fixed` |
| Coordinates in a collision frame | \|*x*\|, \|*y*\|, \|*z*\| ≤ 4,096 | Keeps every row and product far from overflow |
| Grid | `w`, `h` ≥ 1 (`u16`) | The index is dense: 4 bytes a grid square |
| Regions | 1–65,535 | |
| Layers | 0–255 in a world, at most 8 per cell | One byte of mask per cell; layer ids are `u8` |
| Placements, entities per cell | `u32` counts; the reference encoder sets no lower limit | |
| Collision triangles per block | 65,535 of each kind | Lists hold `u16` numbers |
| Triangles of one kind in a lookup bucket | 255 | Bucket counts are `u8`; the encoder picks a finer grid to stay under it |
| Lookup grid | 1 × 1 to 32 × 32 (`grid_shift` 0–5) | |
| `pad` | 0 to *S*/2 | Wall pushes reach at most `pad` (below) |
| `overhang` | 0 to *S*/2 | How far placements may reach past their cell; the encoder enforces it |
| Mesh | the native format: at most 2,048 vertices | `mesh()` |
| Paths | `u32` count; 2–4,096 stored points each; a path at most 16,384 units long; points within ±32,767 units | Keeps the nearest-point query's products inside `fixed` ([Paths](#paths)) |
| Levels of detail | 1–8 levels after level 0 in a set (the cull mark included); switch distances plus the band at most 1,400 units | (distance / 8)² stays inside `fixed` |
| `near_far` | 0 (the default, 1.5 cells) or more than 0 up to 2,048 units | |
| Occlusion zones (1.5) | `u32` per cell; a zone's box within its cell's square in *x* and *z*; it hides placements of the 3 × 3 near cells and stand-ins of the 7 × 7 cells around its own | One mask word per 32 placements; 49 stand-in bits |

## Layout

```
header         80 bytes at offset 0 (84 in 1.4)
index          w x h u32: the offset of each grid square's cell, or 0
layers         layer_count x 8 bytes
regions        region_count x 32 bytes, each pointing at its textures, samples, palettes, backdrop
region ext     (1.4) region_count x 32 bytes: palette runs, animated textures, the sky record
paths          path_count x 48 bytes, then each path's points, 40 bytes each
cells          96 bytes each, pointing at their placements, entities and collision block
  placements   48 bytes each
  LOD table    placement_count x u32, when a placement has levels of detail; LOD sets, pooled
  entities     64 bytes each
  collision    a 48-byte block header, floor, wall and ceiling records, buckets, a u16 list
zones          (1.5) per cell with zones: 80 bytes each; placement masks, pooled
entity dir     entity_count x u32: the offset of entity number n's record
mesh dir       mesh_count x u32: the offset of each mesh in the pool
mesh pool      native meshes, each stored once
data           texture, sample, palette and parameter bytes; NUL-terminated names
```

Only the header's position is fixed. Everything else is found through offsets, may come in any
order, and must lie within the pack. The reference encoder writes them in the order above and is
deterministic: the same input gives the same bytes.

A discrete level is a world with one cell (or a few, all within the near set): it uses the same
records, and a reader treats it like any other world.

## Header

| Offset | Type | Field | |
|---|---|---|---|
| 0 | `[4]u8` | `magic` | `"MEIW"` (the `u32` 0x5749454D) |
| 4 | `u16` | `major` | 1 |
| 6 | `u16` | `minor` | 5 for a pack with occlusion zones; else 4 for one with a region extension; else 3 |
| 8 | `u32` | `size` | the pack's length in bytes, a multiple of 4 |
| 12 | `u8` | `cell_shift` | 4–7 |
| 13 | `u8` | `flags` | see [Versions](#versions); bit 0 (1.1): some cell has a ground placement |
| 14 | `u16` | `header_size` | 64 in 1.0 and 1.1, 72 in 1.2, 80 in 1.3, 84 in 1.4 and 1.5; at least 64, at least 72 when `minor` ≥ 2, 80 when ≥ 3, 84 when ≥ 4 |
| 16 | `s16` | `i0` | grid column of the index's first entry |
| 18 | `s16` | `j0` | grid row of the index's first entry |
| 20 | `u16` | `w` | index width (columns) |
| 22 | `u16` | `h` | index height (rows) |
| 24 | `u32` | `index_off` | |
| 28 | `fixed` | `pad` | how far past a cell's square its walls are copied in (and the largest push radius) |
| 32 | `fixed` | `overhang` | how far any placement reaches past its cell (informative for readers) |
| 36 | `u16` | `region_count` | at least 1 |
| 38 | `u16` | `layer_count` | |
| 40 | `u32` | `region_off` | |
| 44 | `u32` | `layer_off` | 0 when there are no layers |
| 48 | `u32` | `entity_count` | |
| 52 | `u32` | `entity_dir_off` | 0 when there are no entities |
| 56 | `u32` | `mesh_count` | |
| 60 | `u32` | `mesh_dir_off` | 0 when there are no meshes |
| 64 | `u32` | `path_count` | (1.2) |
| 68 | `u32` | `path_off` | (1.2) the path table, 0 when there are no paths |
| 72 | `fixed` | `near_far` | (1.3) the near pass's far depth the world asks for, or 0 for the reader's default (1.5 cells) |
| 76 | `u32` | `lod_slots` | (1.3) placements in cells that have a LOD table: the size of the level memory a reader may keep |
| 80 | `u32` | `region_ext_off` | (1.4) `region_count` region extension records, or 0 (always 0 in a 1.5 pack without them) |

## Index

`w × h` `u32` entries in rows: the entry for cell (*i*, *j*) is number (*j* − `j0`) × `w` +
(*i* − `i0`). It holds the offset of the cell's record, or 0 where the world has no cell. A cell
(*i*, *j*) outside `i0 ≤ i < i0 + w`, `j0 ≤ j < j0 + h` does not exist. Each cell record repeats
its own (*i*, *j*), which must match its entry.

A 1 km square of 64-unit cells is 16 × 16 = 256 entries, 1 KB; a world's index covers the
rectangle around its cells.

## Layers

`layer_count` records of 8 bytes. A layer's **id** is its position in this table (0–254).

| Offset | Type | Field | |
|---|---|---|---|
| 0 | `u32` | `name` | offset of a NUL-terminated ASCII name |
| 4 | `u8` | `group` | exclusive group number, or 0xFF for none |
| 5 | `u8` | `flags` | bit 0: on when the pack is opened |
| 6 | `u16` | reserved | |

Layer names are world-wide: a layer called `festival` is one switch for every cell that has it.
Each cell lists up to 8 layer ids, and its records refer to them by **bit**: bit *k* of a cell's
masks means the cell's *k*-th layer. Layers in the same `group` are exclusive: switching one on
switches the others off. The reader keeps one on/off bit per layer id; the format holds nothing
the game switches at run time.

## Regions

`region_count` records of 32 bytes. Cells name their region by number. A region's resources are
what a game loads when the player crosses into it ([WORLDKIT.md](WORLDKIT.md), "Regions and the
VRAM split").

| Offset | Type | Field | |
|---|---|---|---|
| 0 | `u32` | `name` | |
| 4 | `u16` | `texture_count` | |
| 6 | `u16` | `sample_count` | the audio bank |
| 8 | `u32` | `texture_off` | `texture_count` × 12 bytes |
| 12 | `u32` | `sample_off` | `sample_count` × 20 bytes |
| 16 | `u16` | `variant_count` | palette variants |
| 18 | `u16` | `colour_count` | colours in each variant |
| 20 | `u16` | `first_colour` | the palette memory colour (0–8,191; 4,096 and up are palette bank 1) the variants load to |
| 22 | `u16` | `backdrop_count` | |
| 24 | `u32` | `palette_off` | `variant_count` × `u32` name offsets, then `variant_count` × `colour_count` `u16` colours |
| 28 | `u32` | `backdrop_off` | `backdrop_count` × 12 bytes |

**Texture** (12 bytes): `u8 slot` (0–31; 16–31 since VRAM grew to 2 MB, DECISIONS.md), `u8 flags` (bit 0: 4-bit), `u16` reserved,
`u32 data` (offset), `u32 bytes`. The bytes are copied to the slot as `load_texture()` copies
them (the GPU's layout, spec p. 11), from the slot's first byte; a texture larger than one slot
runs into the next slot, as an 8-bit texture does. The World Kit writes one record per slot its
region uses, from row 0 to the last row a tile uses, with the world's swatch row in it when the
swatch shares the slot. A region's 4-bit texture palettes are part of its main palette run.

**Palette variants.** Variant *v*'s colours are the `colour_count` `u16` 15-bit colours at
`palette_off` + 4 × `variant_count` + 2 × `colour_count` × *v*. Loading variant *v* writes them to
palette memory from colour `first_colour`; blending between two is `palette_lerp()`.
`first_colour + colour_count` ≤ 8,192 (`load_palette()` puts colours 4,096 and up in palette bank
1; the World Kit never makes a run that crosses colour 4,096, nor palette 255).

**Sample** (20 bytes; *specified, reader not yet implemented*): `u32 name`, `u32 data` (offset of
the sample bytes, read in place: channels play from ROM), `u32 samples` (length in samples),
`u32 loop_start`, `u32 flags` (the `play_sample()` flags: `SND_16BIT`, `SND_ADPCM`, `SND_LOOP`,
`SND_REVERB`).

**Backdrop copy** (12 bytes): `u32 address` (a VRAM address: an atlas page, a plane map, a line
table, `planes.akr`'s layout), `u32 data`, `u32 bytes`. A backdrop is the list of copies that put
a region's plane-chip art in VRAM; `wp_region_enter()` makes them. How the planes are then set up
is the sky record's ([Region extensions](#region-extensions-14)), or the game's in a pack without
one.

### Region extensions (1.4)

At `region_ext_off`, one record of 32 bytes per region, in region order:

| Offset | Type | Field | |
|---|---|---|---|
| 0 | `u16` | `run_count` | extra palette runs |
| 2 | `u16` | `anim_count` | animated textures |
| 4 | `u32` | `run_off` | `run_count` × 8 bytes |
| 8 | `u32` | `anim_off` | `anim_count` × 20 bytes |
| 12 | `u32` | `sky_off` | the sky record (32 bytes), or 0 |
| 16 | `[4]u32` | reserved | |

**Palette run** (8 bytes): `u16 first_colour`, `u16 colours` (1–256), `u32 data`: the run's
colours for each of the region's palette variants, variant by variant (`variant_count` ×
`colours` `u16`). Loading variant *v* loads the main run and every run's *v*-th list; blending
blends each. The World Kit stores an 8-bit texture palette (colour 0 and its colours) as a run,
each variant's list its colours times that variant's tint. A region with runs has variants.

**Animated texture** (20 bytes): `u32 data` (the frames: `frames` × `rows` × `row_bytes` bytes, a
frame after another, each in the tile's own layout), `u32 vram` (the tile's first byte in the
texture area: VRAM_TEXTURES + `vram`), `u16 frames` (at least 1), `u16 ticks` (1–255: each frame
is shown that many ticks, looping), `u16 row_bytes`, `u16 rows`, `u16 stride` (128 in a 4-bit
slot, 256 in an 8-bit one), `u16` reserved. Frame *k* is copied row by row: row *r* to `vram` +
*r* × `stride`. Every row lies in the texture area and within its stride. At tick *t* the frame
is (*t* / `ticks`) mod `frames`; the texture set holds frame 0.

**Sky** (32 bytes): how the reader shows the region's backdrop.

| Offset | Type | Field | |
|---|---|---|---|
| 0 | `u32` | `mode` | BG1_MODE for the silhouette: map size, 8 × 8 4-bit tiles, its palette |
| 4 | `u32` | `atlas` | BG1_TILES: the silhouette's atlas page |
| 8 | `u32` | `map` | BG1_MAP |
| 12 | `fixed` | `rate` | plane pixels the silhouette scrolls a radian of yaw |
| 16 | `s16` | `horizon` | the plane row put on the horizon |
| 18 | `s16` | `top` | the plane row of the silhouette's first row |
| 20 | `u16` | `height` | the silhouette's rows (0: no silhouette) |
| 22 | `u16` | `stops` | the gradient's stops, 1–64 |
| 24 | `u32` | `flags` | bit 0: a silhouette (set exactly when `height` is not 0) |
| 28 | `u32` | `data` | `stops` `fixed` elevations (radians above the horizon, increasing), then each variant's `stops` `u32` colours (0xBBGGRR) |

**What a reader does with it** (`stdlib/wpbackdrop.akr`): every frame, with the camera's yaw
and pitch and the focal length *F* (207.8 pixels a radian for the default camera), stop *i* goes
to screen line 120 − *F* tan(*e*ᵢ − pitch) and the backdrop colour is interpolated between the
stops on every line (a line channel on BD_COLOR); the horizon is line *h* = 120 + *F* tan(pitch);
BG1 scrolls to x = yaw × `rate` − 160 (yaw taken in [0, 2π)), y = `horizon` − *h*, and is shown
only on lines `top` − y .. `top` + `height` − y − 1 (its window), so the map's vertical wrap
never shows twice. [WORLDKIT.md](WORLDKIT.md#backdrops) explains the choice.

## Cells

96 bytes.

| Offset | Type | Field | |
|---|---|---|---|
| 0 | `s16` | `i` | grid column |
| 2 | `s16` | `j` | grid row |
| 4 | `u16` | `region` | |
| 6 | `u8` | `layer_count` | 0–8 |
| 7 | `u8` | `flags` | reserved |
| 8 | `[8]u8` | `layers` | the layer ids of the cell's bits 0–7; unused entries 0xFF |
| 16 | row | `bounds` | a sphere (centre *x*, *y*, *z*, radius), cell-local, holding every placement's sphere; zero when there are none |
| 32 | row | `standin_bounds` | the stand-in mesh's sphere, cell-local |
| 48 | `u32` | `standin_off` | the stand-in mesh, in cell-local coordinates, or 0 |
| 52 | `u32` | `placement_count` | |
| 56 | `u32` | `placement_off` | |
| 60 | `u32` | `entity_count` | |
| 64 | `u32` | `entity_off` | |
| 68 | `u32` | `entity_first` | the number of its first entity: its entities are `entity_first` .. + `entity_count` − 1 |
| 72 | `u32` | `coll_off` | its collision block, or 0 |
| 76 | `u32` | `ground_count` | (1.1) its first `ground_count` placements are ground, the rest are not |
| 80 | `u32` | `lod_off` | (1.3) its LOD table: `placement_count` `u32` LOD set offsets, 0 for a placement without levels; or 0 |
| 84 | `u32` | `lod_first` | (1.3) the level-memory slot of its placement 0: placement *k*'s is `lod_first` + *k* (< `lod_slots`) |
| 88 | `u32` | `zone_count` | (1.5) its occlusion zones: the eye's zones while the eye is in this cell |
| 92 | `u32` | `zone_off` | (1.5) `zone_count` zone records, or 0 |

## Placements

48 bytes; an asset drawn at a position and yaw.

| Offset | Type | Field | |
|---|---|---|---|
| 0 | row | `sphere` | bounding sphere of the placed mesh, cell-local |
| 16 | row | `pos` | position (*x*, *y*, *z*, 0), cell-local |
| 32 | `fixed` | `cos` | cos yaw |
| 36 | `fixed` | `sin` | sin yaw |
| 40 | `u32` | `mesh` | the mesh (model coordinates) |
| 44 | `u8` | `mask` | the cell layer bit it belongs to (one bit), or 0 for always |
| 45 | `u8` | `flags` | bit 0 (1.1): ground; bits 1–7 reserved |
| 46 | `u16` | `tag` | the encoder's number for it (for reports and tests) |

The sphere must contain every vertex of the mesh, and of each of its levels of detail, as drawn
with the stored `cos` and `sin`. The
reference encoder takes the centre of the vertices' box and the largest distance from it, plus
2/65,536. The mesh's vertices may reach at most `overhang` past the cell's square, and `pos`
lies in the square.

A cell's ground placements come first in its list: placement *k* has the ground bit exactly when
*k* < `ground_count`. The reference encoder files them so, each group in the order it was given.

## Levels of detail

A placement may have **levels of detail**: coarser meshes drawn from given distances out, and
last, optionally, a distance past which it is not drawn at all (the **cull mark**). Level 0 is the
placement's `mesh`. The distance is from the eye to the centre of the placement's `sphere`, which
holds every level, so culling is the same whichever level is drawn.

**LOD set** (8 bytes and 16 a level), pointed at from the cell's LOD table; the reference encoder
stores each distinct set once, so every placement of one asset shares one:

| Offset | Type | Field | |
|---|---|---|---|
| 0 | `u8` | `count` | levels after level 0, the cull mark included: 1–8 |
| 1 | `u8` | `flags` | bit 0: the last level is the cull mark; bits 1–7 reserved |
| 2 | `u16` | reserved | |
| 4 | `fixed` | `band` | the hysteresis band, units (informative: the rows hold it) |
| 8 + 16 (*k* − 1) | `fixed` ×3, `u32` | `at2`, `out2`, `in2`, `mesh` | level *k*: ((*d*ₖ)/8)², ((*d*ₖ + band)/8)², ((*d*ₖ − band)/8)², its mesh (0 for the cull mark) |

*d*ₖ is level *k*'s switch distance. The encoder rounds *d* to `fixed` and squares exactly:
`at2` = round(*D*² / (64 × 65,536)) with *D* the raw distance. Distances increase by more than
twice the band from level to level (and the first is more than twice the band), so each level's
band lies clear of the next: `in2` ≤ `at2` ≤ `out2` < the next level's `in2`.

**Choosing a level.** With the eye relative to the frame's origin and the sphere centre relative
to the same origin, **q** = (centre − eye) × 0.125 (the CPU's `fmul`, lane by lane) and
*d²* = **q** · **q** (`vdot`: the exact sum, shifted right 16). Over the set's levels in order:
*plain* counts the levels with *d²* ≥ `at2`, *lo* those with *d²* ≥ `out2` and *hi* those with
*d²* ≥ `in2`; *lo* ≤ *plain* ≤ *hi*. The level drawn is:

- *plain* when the reader does not know the level it drew this placement at last (the first
  frame, a reset, a slot past the reader's memory);
- otherwise that level, clamped to [*lo*, *hi*]: it moves to a coarser level only once the eye is
  `band` past the switch distance, and back only once it is `band` inside it, so an eye hovering
  at a switch distance does not flip the level every frame (**hysteresis**);
- *lo*, the finest level the band allows, in the reader's worst-case mode (the World Checker's).

Level *k* > 0 draws the set's level *k* mesh; the cull mark draws nothing. `pack.lod_level()` and
`pack.lod_d2()` are the rule in exact integer arithmetic; the console reader agrees with them
bit for bit (`tests/test_worldpack.py`, `LodTests`).

**Kept apart from stand-ins.** A stand-in is a whole cell's low-detail mesh, authored per cell,
drawn in the far pass for cells 2 or more away, with its own clip range and ordering table;
levels of detail are per placement, authored per asset and shared by every placement of it, and
chosen inside the near pass by distance. They answer different distances (a far cell is at least a
cell away; a placement switches at a few tens of units, inside the near set) and different
granularity (a cell's skyline against one building's detail), and in a small world where every
cell is near (the garden's 2 × 2 cells of 64 units) stand-ins draw nothing and only levels of
detail help. Folding the stand-in into the levels would make a cell's far picture the sum of its
placements' coarsest levels, which costs the per-placement draw (about 500 cycles each) that one
merged stand-in avoids. So the two stay separate; an asset's coarsest level can be the cull mark,
which is what a stand-in already stands for once the cell is far.

**The near range.** `near_far` lets a world choose the near pass's far depth (`wp_open()` sets
`wp_near_far` to it; a cart may still change it), so the World Checker measures with the range the
cart will draw with.

## Ground

A level marks the placements that are **ground**: the open floor everything else stands on. The
reader draws them before everything else near the camera, so nothing standing on the ground can
sort behind it. Mei has no depth buffer: a large ground face sorts by its average depth, which
says little about the depth under a small object standing on it, so in one ordering table the
ground is drawn over the object's feet. The World Checker measured this on both example worlds:
wrong-order pixels near the camera in about half of all sampled views, up to 24,000 in one, from
ground tiles drawn over what stands on them and from faces inside one asset
([WORLDCHECKER.md](WORLDCHECKER.md), "Ground"). Drawing the floor first is the classic fix on
this kind of hardware.

**What the reader does.** After the far pass and with the near pass's camera and clip range, the
**ground pass**: the ground placements of the 3 × 3 near cells, culled as any placement (layers,
cell bounds, sphere), sorted among themselves in the frame's ordering table and drawn at once
(`ot_flush()`), unless none was drawn. Then the near pass as before, without them; the cart's own
meshes join it. The frame is drawn in three passes, each over the one before: far stand-ins,
ground, near. (In depth mode there is no ground pass: [Objects](#objects), "In depth mode".)

Why a pass of its own rather than the other ways of drawing ground "first" on this machine:

- *A depth bias* (`depth_bias()`) moves ground faces a fixed number of buckets farther. It fixes
  only errors smaller than the bias, and a ground face's average depth can lie anywhere along it
  (half of a 32-unit tile is 170 buckets at 64-unit cells), while a bias that large also puts the
  ground behind things it truly hides farther away.
- *Forcing ground into the near pass's farthest buckets* (`depth_key()`, or keyed faces) makes
  it farther than everything else only if the rest stays out of those buckets, and squeezes the
  ground's own order into a few buckets, so ground faces that do overlap sort worse than now.
- *A pass of its own* keeps all 1,024 buckets for the ground's own order and all 1,024 for the
  rest, changes nothing about how anything else sorts, and costs one flush (`ot_flush()` empties
  the table again) and a second look at the near cells: about 2,000 cycles a view in all
  ([Costs](#costs)). The GPU draws the same triangles.

**What it makes right.** At a pixel, ground-first drawing gives the true picture unless a ground
face is truly in front of a face drawn after it there, or two ground faces overlap there (they
are sorted among themselves by average depth, as before). So it is exact for:

- anything standing on or above the ground, whatever its size against the ground's faces:
  objects, characters, entities, the cart's own meshes; semi-transparent things too, which blend
  over the ground already drawn;
- ground faces that meet edge to edge, at one height or not, wherever the ground the camera can
  see forms a valley seen from above: a flat floor, a single slope, a floor rising into a ramp up
  from its edge, a bowl. Seen from above such a surface, its faces never overlap each other on
  screen and nothing above it is behind it, so their order does not matter;
- the far pass, which stays behind both.

**What it does not handle.** Whatever a ground face truly hides is drawn over it:

- anything under or behind ground: a bridge, raised platform, block or step flagged as ground
  (what passes under it or stands behind it shows through: a character walking behind a ground
  block is drawn over the block), a ground-flagged ramp the player can walk under;
- the far side of a crest: a ramp up to a higher floor, both flagged, hides the feet of what
  stands just past the top from below, and they are drawn anyway;
- a pit or a drop seen across its edge: the near lip hides the bottom and what falls in;
- an object sunk into the ground: its buried part shows;
- ground seen from below or from beside it (the underside of a walkway, a double-sided floor);
- ground that overlaps ground: a raised ground piece on the ground, or solid ground slabs, whose
  sides lie under their neighbours' tops, are sorted among themselves by average depth as before;
- semi-transparent ground (water, glass): what is under it is drawn over it without blending.

The rule for authors: **flag as ground only the lowest open floor of an area, the surfaces
nothing is ever under or behind from where the camera can be; everything raised (platforms,
ramps to higher floors, bridges, blocks, steps) stays an ordinary placement.** Ground meshes are
best modelled as surfaces rather than solids. The World Checker warns of geometry a ground face
can hide and of ground that can overlap ground, and measures the pixels where ground truly hides
what is drawn over it ([WORLDCHECKER.md](WORLDCHECKER.md), "Ground").

Stand-ins are never ground: a stand-in is a whole cell, drawn in the far pass (or, for a near cell
whose region is not loaded, in the near pass), so there is nothing to flag. A merged scatter mesh
is ground when the props merged into it are (the World Kit merges ground and the rest apart).
Terrain, when it is built ([WORLDKIT.md](WORLDKIT.md), "Terrain"), is ground by default.

## Occlusion zones

(1.5) Mei has no occlusion culling of its own: whatever lies in the view volume is transformed
and sorted, and in a town most of it is behind walls. A world may therefore say, per **zone** (a
box the eye can be in), which placements of the near cells and which stand-ins of the far ring
cannot be seen from anywhere in it, and the reader skips them while the eye is there: a
potentially visible set, worked out offline by the World Kit from occluders the author places
([WORLDKIT.md](WORLDKIT.md#occlusion)), checked by the World Checker
([WORLDCHECKER.md](WORLDCHECKER.md#occlusion)). The format holds only the answer, not the
occluders.

**Zone** (80 bytes), in the eye's cell's table (`zone_off`, `zone_count`):

| Offset | Type | Field | |
|---|---|---|---|
| 0 | row | `lo` | (*x*, *y*, *z*, 0), cell-local: the box's low corner |
| 16 | row | `hi` | (*x*, *y*, *z*, 0): its high corner; `lo` < `hi` in each lane, and *x* and *z* within the cell's square (−*S*/2 .. *S*/2) |
| 32 | `u8` | `layer` | a layer id: the zone counts only while that layer is on; 0xFF: always |
| 33 | `u8` | `flags` | reserved |
| 34 | `u16` | reserved | |
| 36 | `[2]u32` | `far` | stand-ins hidden: bit (*dj* + 3) × 7 + (*di* + 3) for the cell (*i* + *di*, *j* + *dj*), \|*di*\|, \|*dj*\| ≤ 3; bits 49–63 are 0 |
| 44 | `[9]u32` | `near` | per near cell, entry (*dj* + 1) × 3 + (*di* + 1): the offset of a mask of ⌈`placement_count` / 32⌉ `u32`, bit *k* (of word *k* / 32) set for each of that cell's placements it hides; or 0 |

A bit may be set only for a placement or stand-in that exists; bits past a cell's placements are
0. The reference encoder stores each distinct mask once.

**What a reader does.** At the start of `wp_draw()`, the **eye's zone** is the first zone in the
eye's cell's table whose box holds the eye in that cell's local coordinates (`lo` ≤ eye < `hi`,
lane by lane: the same frame the reader already works in) and whose layer is on; or none. With a
zone, the reader skips every placement whose bit is set in the near cell's mask, in the ground
pass and in the near pass, before its layer and sphere tests, and every stand-in whose bit is set
in `far`, in the far pass or drawn for a near cell of another region. Nothing else changes: the
same placements are drawn as without zones, less those, at the same levels of detail.
`pack.zone_at()` is the rule; `zone_hides_standin()` reads `far`.

**What a zone may hide.** A placement may be set in a zone's mask only if no point of any of its
levels can be seen from any point of the zone, whatever else is drawn, and likewise a stand-in.
The format does not check this (a reader cannot); the World Kit works it out conservatively, and
the World Checker tests it by casting rays. A zone is a claim about the eye, not the player: the
game's camera, wherever it trails, is what has to be inside.

**Why a set per zone, not a test per frame.** The cheapest per-frame alternative of the era is a
screen-space test: project each occluder's box to a rectangle with its far depth, and each
placement's sphere to a rectangle with its near depth, and skip the placement when its rectangle
lies inside an occluder's and behind it. That costs a projection per occluder (8 corners, about
26 cycles each, about 300 cycles with the min and max) and a projected sphere and a comparison
per placement and occluder in view (about 60 + 20 cycles), every frame: with 20 occluders in
view and 130 placements, about 6,000 + 130 × (60 + 20 × 20) ≈ 66,000 cycles, more than a tenth
of the 600,000 budget before anything is saved. A sphere also stands for its placement badly: a
20 m train car's sphere reaches the ground under the viaduct it stands on. The zone set moves all
of this offline, where it can use each placement's box and every point of the zone. At run time
it is a box test per zone looked at (about 40 cycles; zones are looked at in the eye's cell only,
and the first that holds the eye is used) and a bit test per placement looked at (about 10
cycles, only in a near cell for which the zone has a mask); a hidden placement costs about 10
cycles instead of the 60 of its sphere test and the 500 and more of drawing it. See
[Costs](#costs).

## Objects

Ground-first drawing fixes the lowest open floor. A small object on a **raised** platform, or
floating above one, has the same trouble in the near pass: the platform's top sorts by its
average depth, which can be nearer than the object although the object is in front of the top at
every pixel they share. This is not part of the format (nothing in the pack changes); it is how
the reader draws a game's objects into the near pass: an entity's mesh, a pickup, the player's
character. The World Checker's cameras aimed at entities ([WORLDCHECKER.md](WORLDCHECKER.md),
"Entities") found it in the example `test_room`: the coin floating 0.2 above the 3 × 2 × 3
`ledge`, drawn with `mesh_at()`, loses a wedge to the ledge's two top triangles from cameras
above the ledge's top and within about 4 units (21 of 201 views aimed at it, 14,466 pixels;
depth errors up to 1.7 units); the other camera kinds never looked at it closely enough.

**What the reader does.** `wp_draw_object(m, pos, yaw, radius, base)` draws the mesh as
`mesh_at()` would, after `wp_draw()`, with three differences:

1. it culls the mesh by the sphere of `radius` around `pos` against the near pass's view volume;
2. it sorts the mesh as a unit keyed at its nearest point: `depth_key(w, wp_object_squash)` with
   *w* the view depth of `pos` less `radius`. The object's faces keep their own order, squashed
   `wp_object_squash` times (default 2) toward *w*, so they do not interleave with a neighbour's;
3. while the eye is above `base` (the world height of the object's lowest point: its feet), *w*
   is moved `wp_object_bias` units nearer (default 1.5), but never nearer than the near plane.

Why the bias is safe from above: with the eye and the object both above a level plane, any line
of sight meets the object before the plane, so everything wholly below the object's base (the
platform it stands on, its sides, the floor and anything lower) is truly behind it. Moving the
object nearer can only be wrong against faces above its base. From below its base the platform's
top faces away and is culled, and its sides can truly hide the object, so the object sorts by its
nearest point alone.

Why not the other ways, measured with the World Checker on a test world of eight objects (a coin
above a 4 × 4 platform, two above a 12 × 12 platform, one on the ground 0.3 behind a thin wall,
two 0.5 apart, one under a slab, and a 1.85-unit figure of four boxes standing on the large
platform; 1,701 cameras at 0.6 to 6 units, pitches −60° to +15°; `tests/worldverify/worlds.py`,
`object_world()`). Pixels where something was drawn over an object truly in front of it ("drawn
over") and where an object was drawn over a face truly in front of it ("shows through"), in
views (pixels):

| | `mesh_at()` | the rule | bias alone (squash 1) | squash 4 | bias 0.75 | bias 2.5 |
|---|---|---|---|---|---|---|
| on the 4 × 4 platform: drawn over | 31 (6,687) | 0 | 0 | 0 | 0 | 0 |
| on the 12 × 12 platform (two): drawn over | 152 (35,192) | 89 (5,599) | 54 (1,285) | 60 (1,956) | 104 (8,196) | 58 (1,535) |
| behind the thin wall: shows through | 6 (88) | 153 (43,639) | 180 (65,945) | 166 (63,994) | 69 (13,731) | 163 (43,927) |
| the pair, the coin under the slab | 0 | 0 | 70 (70,945) | 2 (17) | 0 | 2 (17) |
| the figure: drawn over | 156 (32,694) | 78 (4,929) | 85 (5,929) | 26 (1,139) | 93 (8,861) | 47 (1,836) |
| the figure: its own faces | 28 (2,522) | 24 (2,166) | 30 (2,524) | 33 (9,712) | 24 (2,166) | 25 (2,167) |

- *A fixed bias without the key* (squash 1) pushes objects near the camera into the table's
  first bucket: two coins within the bias of the near plane lose their order (70 views). Keying
  each object as a unit at its nearest point keeps them in order there.
- *A bias always*, not only from above, draws the coin over the ledge's side from cameras below
  the ledge's top (`test_room`: 8 of 240 views, 897 pixels). *A bias of the object's size* (twice
  its radius, from above) is enough for `test_room`'s ledge but ties the fix to the object rather
  than to the face under it: the coin's 0.6 left 4,829 pixels drawn over coins in an earlier,
  coins-only version of the test world, against 396 with 1.5, and a character's would be larger
  than wanted.
- *More squash* (4) puts the figure's own faces into a quarter of the buckets: four times the
  pixels of the figure drawn wrongly over itself. *A larger bias* shows more through thin walls;
  a smaller one leaves more of the large platform over its coins.

**What it makes right.** From an eye above the object's base, every face wholly below the base
whose average depth lies less than `wp_object_bias` + `radius` nearer than the object's centre:
in practice a platform top up to about 4 units across (`test_room`'s 3 × 3 ledge: 0 errors from
720 cameras at 0.6 to 10 units, where `mesh_at()` gives 54 views and 13,768 pixels), the floor,
the platform's sides; and objects close together, which sort as units.

**What it does not handle.**

- A face above the object's base, truly in front of it and less than about `wp_object_bias` +
  `radius` in depth from it, from an eye above the base: a thin wall, a post or railing, a
  platform's edge rising above the object's feet, the underside or top of a platform seen through
  from above, another object's mesh that is not drawn with `wp_draw_object()`. The object shows
  through it (the coin 0.3 behind the wall above).
- A platform top whose average depth lies farther than the bias from the object on it: tops more
  than about 4 units across. Split them (the Asset Kit's `mesh` with smaller faces), or raise
  `wp_object_bias` for that game, accepting more of the case above.
- An object sunk into what it stands on, or standing on a slope that rises above its base nearby
  (the slope is not wholly below the base).
- From below the object's base, a large face above the base and behind the object sorts by
  average depth as before.
- The object's own faces still sort among themselves by average depth, squashed: a non-convex
  character needs to be modelled for that, as any mesh does (the Asset Checker).

So the authoring rule, with the ground's: **objects stand on platform tops no more than about 4
units across a face, and keep 1.5 units (`wp_object_bias`) clear of thin geometry in front of
them where the camera looks down on them.**

`wp_draw_entities()` draws the live entities' meshes of the 3 × 3 near cells this way, each culled
and keyed by its mesh's bounds (`wp_mesh_bounds()`, a scan of its vertices each time); a game
drawing its own character works the bounds out once (`wp_mesh_bounds(HERO)`: radius and lowest
point) and passes them with the character's position every frame:
`wp_draw_object(HERO, pos, yaw, b.x, pos.y + b.y)`. The same call suits any object the game
draws at a world position; `wp_object_bias` and `wp_object_squash` can be set before each call.

**In depth mode.** Everything above works around the ordering table. A cart that imports
`depth.akr` and calls `render_depth(true)` ([RENDERING.md](RENDERING.md),
[LANGUAGE.md](LANGUAGE.md#the-depth-buffer-and-perspective-depthakr)) has a depth buffer
order its pixels instead, and `depth.akr` replaces `wp_draw()` and `wp_draw_object()` with
versions that leave the workarounds out while the test is on (and are the same as these while it
is off):

- `wp_draw()` makes no `ot_flush()` and no ground pass: the far pass's stand-ins and every near
  placement, ground or not (`wp_stats.ground` stays 0), go into the same tables, opaque faces
  drawn nearest first and semi-transparent ones after them, back to front. Both passes sort over
  one clip range, `wp_clip_near` to the far pass's far depth (`wp_near_far` without a far pass),
  which is the range it leaves set; the culling is as before (the far pass's view volume still
  starts at half a cell).
- `wp_draw_object()` culls the object by its sphere as before and draws it as `mesh_at()` would,
  without the key or the bias: `wp_object_bias` and `wp_object_squash` do nothing, and none of
  the cases in "What it does not handle" remains (thin walls, large tops, sunk objects and the
  object's own faces are all ordered per pixel). The authoring rules above are for the ordering
  table only.

What is left is precision: vertex positions are whole pixels, so where two faces meet or lie
within about a key step of each other a pixel or few at the edge can go either way (RENDERING.md,
"Precision"; the depth prototype's World Checker run left 73 near and 81 far wrong-order pixels
over the Movement Garden's 600 views, against 51,382 and 4,810 with the ordering table).

## Entities

64 bytes; game data the reader iterates but does not interpret.

| Offset | Type | Field | |
|---|---|---|---|
| 0 | row | `pos` | position (*x*, *y*, *z*, 0), cell-local; it lies in the cell's square |
| 16 | `u16` | `type` | the game's type number |
| 18 | `u8` | `mask` | the cell layer bit it belongs to, or 0 |
| 19 | `u8` | `flags` | bit 0: `saved_bit` is valid |
| 20 | `s32` | `saved_bit` | its persistent bit index (the ID lock file's), or −1 |
| 24 | `fixed` | `yaw` | radians |
| 28 | `u32` | `mesh` | a mesh the game may draw for it, or 0 |
| 32 | `u32` | `coll` | a collision block in its own frame (a moving object), or 0 |
| 36 | `u32` | `params` | its parameter record, or 0 |
| 40 | `u32` | `params_size` | |
| 44 | `u32` | `number` | its number in the world (0 .. `entity_count` − 1) |
| 48 | `u32` | `cell` | its cell's record |
| 52 | `[3]u32` | reserved | |

**Numbers.** Entities are numbered in the order of their cells in the index (by row *j*, then
column *i*), then in their order in the cell. The entity directory maps a number to its record.
An `entity_ref` parameter holds a number. Numbers are stable for one pack, not across edits: what
a save remembers is `saved_bit`. (`pack.entity_numbers()` gives them before encoding.)

**Parameter records** are the game's structs, laid out by Akari's rules so that a cart reads them
by casting `params` to a pointer of its struct type: fields in order, each aligned to its size (4
for vectors), the size padded to the largest alignment. The World Kit's field types encode as:

| Type | Bytes |
|---|---|
| `bool`, `u8`, `enum` | `u8` (an enum is its value's index) |
| `s16` | `s16` |
| `s32`, `fixed` | `s32` (fixed: 16.16) |
| `vec3` | 16 bytes: three `fixed` and a zero |
| `name` | `u32`: a string offset in the pack |
| `entity_ref` | `u32`: an entity number, 0xFFFFFFFF for none |
| `world_ref` | `u32`: the game's number for another world (the kit's world list) |

## Collision blocks

A cell's collision is one block in cell-local coordinates. An entity may have a block in its own
frame (a lift, a train): a game asks it by turning the query into that frame. A block holds three
kinds of triangle, a lookup grid over *x* and *z*, and the list the grid points into.

### Block header (48 bytes)

| Offset | Type | Field | |
|---|---|---|---|
| 0 | `u8` | `grid_shift` | the grid is *G* × *G*, *G* = 2^`grid_shift` (0–5) |
| 1 | `u8` | `flags` | reserved |
| 2 | `u16` | reserved | |
| 4 | `fixed` | `half` | the grid covers [−`half`, `half`) in *x* and *z*; a cell's block has `half` = *S*/2 |
| 8 | `fixed` | `inv` | the grid's columns per unit, *G* / (2 `half`), rounded |
| 12 | `fixed` | `pad` | walls are filed this much wider (a cell's block: the header's `pad`) |
| 16 | `u32` | `floor_count` | |
| 20 | `u32` | `floor_off` | 64-byte records |
| 24 | `u32` | `wall_count` | |
| 28 | `u32` | `wall_off` | 80-byte records |
| 32 | `u32` | `ceil_count` | |
| 36 | `u32` | `ceil_off` | 64-byte records |
| 40 | `u32` | `bucket_off` | *G* × *G* buckets of 8 bytes |
| 44 | `u32` | `list_off` | `u16` triangle numbers |

### Kinds

A triangle with front normal **n** (unit) is a **floor** if *n*ʸ ≥ cos(`floor_max`), a
**ceiling** if *n*ʸ ≤ −cos(`ceiling_max`), and otherwise a **wall**. The angles are the world
recipe's (the game schema's `probe.floor_max_degrees`; the reference encoder defaults both to
45°) and are not stored: the kinds are. Floors and ceilings share a record format.

### Floor and ceiling records (64 bytes)

Four rows, each tested against the point's row **q** = (*x*, *z*, 1, 0) with one `vdot`:

| Offset | Row | |
|---|---|---|
| 0 | **h** = (*a*, *b*, *c*, info) | the surface's height at (*x*, *z*) is **h** · **q** = *a x* + *b z* + *c* |
| 16 | **e0** = (*m*ˣ, *m*ᶻ, *k*, *y*min) | edges of the triangle's outline seen from above: |
| 32 | **e1** = (*m*ˣ, *m*ᶻ, *k*, *y*max) | the point is inside when **e** · **q** ≥ 0 for all three |
| 48 | **e2** = (*m*ˣ, *m*ᶻ, *k*, 0) | |

The *w* lanes are not part of the products (**q**'s *w* is 0): **h**'s holds the info word, and
**e0** and **e1** the triangle's lowest and highest *y* (informative). The **info word** is
`surface | mask << 8 | tag << 16`: the game's surface byte, the cell layer bit the triangle
belongs to (or 0), and the encoder's 16-bit tag (0xFFFF for none; the reference encoder passes it
through, e.g. the placement it came from).

How the reference encoder computes them, from the corners (raw, in the block's frame):

- (*a*, *b*) = round(−*n*ˣ/*n*ʸ, −*n*ᶻ/*n*ʸ) from the unnormalized normal; *c* is then chosen so
  that the height is exact at the centroid **G**: *c* = round(*G*ʸ − *a G*ˣ − *b G*ᶻ). Rounding
  *a* and *b* then errs by at most 2⁻¹⁷ × (distance from the centroid).
- Each edge row comes from the edge's two ends taken in a canonical order (sorted by (*x*, *z*)):
  (*m*ˣ, *m*ᶻ) = round of the unit vector perpendicular to the edge, *k* = round(−**m** · **M**)
  with **M** the edge's midpoint; the whole row is then negated if the third corner lies on its
  negative side. So **two triangles that share an edge get exactly opposite rows**, and since
  `vdot`'s sum is exact before its final shift, the sign tests at any point are exact: every point
  on a shared edge passes at least one of them. A surface whose triangles meet edge to edge, with
  identical corner coordinates, has no holes at any precision. (T-junctions, where a corner lies on
  another triangle's edge, can leave cracks about 2⁻¹⁶ × edge length wide; the kit's crack check
  should reject them.)

### Wall records (80 bytes)

Rows tested against **q** = (*x*, *y*, *z*, 1):

| Offset | Field | |
|---|---|---|
| 0 | **p** = (*n*ˣ, *n*ʸ, *n*ᶻ, −*d*) | the unit front normal: **p** · **q** is the signed distance from the plane, positive in front |
| 16, 32, 48 | **e0**, **e1**, **e2** = (*u*ˣ, *u*ʸ, *u*ᶻ, *k*) | edges in the plane: **u** is the unit vector in the plane, perpendicular to the edge, toward the third corner; **e** · **q** is how far the point's projection lies inside that edge |
| 64 | `fixed` *h*ˣ, *h*ᶻ | the unit horizontal push direction: (*n*ˣ, *n*ᶻ) normalized |
| 72 | `fixed` inv | 1 / √(*n*ˣ² + *n*ᶻ²): how far to move horizontally per unit of distance |
| 76 | `u32` info | as for floors |

The reference encoder rounds **n** componentwise and sets −*d* = round(−**n**ᵣ · **G**) at the
centroid; edge rows use the same canonical-order construction as floors (sorted by (*x*, *y*,
*z*)), anchored at the edge's midpoint.

### The lookup grid

Bucket *b*(*x*) of a coordinate is computed exactly as

    b(x) = clamp(floor(fmul(x + half, inv) / 65536), 0, G − 1)

with `fmul` the CPU's (the 64-bit product shifted right 16, arithmetically). Bucket record
number *b*(*z*) × *G* + *b*(*x*) (8 bytes): `u32 start`, `u8 nf`, `u8 nw`, `u8 nc`, `u8`
reserved. Its triangles are list entries `start` .. `start + nf + nw + nc − 1`: first `nf` floor
numbers, then `nw` wall numbers, then `nc` ceiling numbers (indexes into the block's floor, wall
and ceiling records), each kind in increasing order. Points outside [−`half`, `half`) fall into the
edge buckets.

**Filing rule.** A triangle is listed in every bucket from *b*(*x*0) to *b*(*x*1 − 2⁻¹⁶) in *x*,
and likewise in *z*, of its **reach box** [*x*0, *x*1] × [*z*0, *z*1] (raw values):

- for a floor or ceiling, the box of every point its three rounded edge rows accept: the triangle
  their three lines make, whose corners the encoder works out exactly (and joins with the true
  corners), rounded outward to whole raw units;
- for a wall, the box of its corners grown by `pad` plus ⌈½ × its longest edge in units⌉ + 4 raw
  units (how far rounding can move its edges), so a point within `pad` of the wall finds it.

The far side is half-open so that triangles which line up with the grid (tiles, kerbs) are not
listed in the next bucket too; a point exactly on the outer edge of a surface (no triangle beyond
it) may therefore miss it. An encoder may list a triangle in more buckets than this (it costs only
time); it must not list it in fewer. The reference encoder picks the smallest `grid_shift` at
which no bucket holds more than 12 triangles of one kind (else the one with the fewest, which must
be at most 255).

**Cells copy their neighbours' triangles.** A triangle is stored in every cell whose square
[−*S*/2, *S*/2)² (in that cell's frame) its reach box overlaps, translated into each cell's frame
with its rows computed there. A cell's block therefore answers any query at a point in its square,
and any wall push of radius up to `pad`, without looking at the neighbours; only segments cross
cells. A triangle over a grid square that has no cell is kept only by the cells that exist.

### Layers and collision

A triangle in a layer has that layer's cell bit in its info word's mask byte (a triangle copied
into a neighbour gets the neighbour's bit for the same layer id, which the encoder adds to the
neighbour's layer list). A query skips triangles whose bit is off. An entity's block has no layers
(its masks are 0).

## Paths

A path is a named polyline in world coordinates: a rail to grind or hang from, a wire between
poles, a crane's jib, a train's route. The format attaches no meaning to it: a game's entities
name the path they use (a `name` parameter), or the game uses the path numbers the World Kit
exports. A path is **raised** (not lying on the ground: a rail, a wire) or not, and **closed** (a
loop) or open, and carries a surface byte, from its tag as a collision triangle's comes from its
material's tag. Paths are neither drawn nor collided with: what a rail looks like and how it is
stood on are an asset's, and later swept terrain's ([WORLDKIT.md](WORLDKIT.md#terrain)).

**Stored once per world, not per cell.** The path table hangs off the header and its points are
world coordinates. Paths are few (tens in a level) and short (a rail is a few segments); a game
asks about one path it already holds (the rail the player is near or on, the route a train
follows), not about everything in a cell; and an entity names a whole path, not a piece of one.
Clipping paths per cell would cut a rail crossing a seam into pieces in two cells, so a grind
check at the seam would ask both and join the answers, and a train's length along its route would
be stitched across cells, for no saving: a path costs 48 bytes and 40 a point. The price of world
coordinates is the overflow limit below, which the box test and the limits keep clear of.

### Path record (48 bytes)

`path_count` records at `path_off`; a path's **number** is its position (the recipe's order).

| Offset | Type | Field | |
|---|---|---|---|
| 0 | `u32` | `name` | offset of a NUL-terminated ASCII name, distinct among the paths |
| 4 | `u32` | `point_count` | stored points, 2–4,096: a closed path stores its first point again at the end |
| 8 | `u32` | `point_off` | `point_count` point records |
| 12 | `u8` | `flags` | bit 0: raised; bit 1: closed; bits 2–7 reserved |
| 13 | `u8` | `surface` | the game's surface byte |
| 14 | `u16` | reserved | |
| 16 | row | `lo` | the smallest *x*, *y*, *z* of its points; *w*: its **length**, the last point's `s` |
| 32 | row | `hi` | the largest *x*, *y*, *z* of its points; *w* 0 |

### Point record (40 bytes)

| Offset | Type | Field | |
|---|---|---|---|
| 0 | row | `pos` | the point (*x*, *y*, *z*, 0), world coordinates |
| 16 | row | `dir` | (*u*ˣ, *u*ʸ, *u*ᶻ, 0): the unit direction of the segment from this point to the next; zero for the last point |
| 32 | `fixed` | `s` | the length along the path to this point: 0 for the first, else the previous point's `s` + `len` |
| 36 | `fixed` | `len` | the length of the segment to the next point, more than 0; 0 for the last point |

A path of *n* stored points has segments 0 .. *n* − 2, segment *k* from point *k* to point *k* + 1.
The *w* lanes of `pos` and `dir` are 0 so that `dot(q − pos, dir)` and `q − pos − dir t` use only
*x*, *y* and *z*. The reference encoder computes them from the points rounded to `fixed` (raw):
`len` = round(√(**d** · **d**)), with **d** the raw difference, exactly (an integer square root, so
every machine gets the same bytes); `dir` = round(**d** / |**d**|) componentwise; `s` the sum of
the `len`s before. A segment whose rounded length is 0 is refused.

**Nearest point** (`wp_path_nearest(path, p, reach)`): for each segment, with **d** = **p** −
`pos`, *t* = clamp(**d** · `dir`, 0, `len`), the nearest point **c** = `pos` + `dir` *t* and
**e** = **p** − **c**: the segment counts when |*e*ˣ|, |*e*ʸ| and |*e*ᶻ| are all less than
`reach`, and the answer is the counting segment with the smallest **e** · **e** (ties: the first),
with its *t*, *s* = its `s` + *t*, **c** and **e** · **e**. A point outside the box [`lo` −
`reach`, `hi` + `reach`] has no answer, which a reader may decide first. With `reach` at most 100,
**e** · **e** ≤ 30,000; inside the box |**d**| is at most the path's length plus 1.8 `reach`, so
**d** · `dir` stays inside `fixed` for a path of up to 16,384 units.

**Point at a length** (`wp_path_at(path, s)`): a closed path takes *s* modulo its length, an open
one clamps *s* to 0 .. length; the segment is the last *k* (0 .. *n* − 2) whose `s` ≤ *s*, and the
point `pos` + `dir` (*s* − `s`).

## Meshes and strings

The **mesh pool** holds native Mei meshes (LANGUAGE.md, "Mesh format"), each 4-byte aligned and
stored once however many placements, stand-ins and entities use it. The mesh directory lists
every mesh in the pool (for tools; a reader reaches meshes through the records). Placement and
entity meshes are in model coordinates; a stand-in is in its cell's local coordinates.

**Strings** are NUL-terminated ASCII anywhere in the pack, referred to by offset; the reference
encoder stores each distinct string once.

## What a reader does

These are the semantics the reference reader implements and the oracle checks. A reader may add
to them; it should not answer differently.

**Finding a cell.** The cell at (*i*, *j*) is the index entry, or none. The cell of a world point
is (⌊*x*/*S*⌋, ⌊*z*/*S*⌋).

**Layer masks.** A cell's active mask has bit *k* set when its *k*-th layer is on. A placement,
entity or triangle with mask *m* is present when *m* = 0 or *m* & active ≠ 0.

**Floor.** The floor under world point **p** at or below **p**.*y* + `above`: in **p**'s cell, the
highest floor triangle that is present, contains (*x*, *z*) by its edge rows, and whose height is
≤ **p**.*y* + `above`. Ties go to the first filed. The answer is its height, surface, tag and
record.

**Ceiling.** The lowest ceiling over **p** at or above **p**.*y* − `below`, likewise.

**Wall push.** An upright body's point **p** with radius *r* ≤ `pad`, pushed out of walls: for
each wall listed in **p**'s bucket, in list order, tested at the position the earlier walls left:
if −*r* < **p** · **q** < *r* and all three edge rows ≥ 0, move the point horizontally by
(*r* − distance) × inv along (*h*ˣ, *h*ᶻ). A point slightly behind a wall (within *r*) is pushed
out in front, as Super Mario 64 does. A tall body asks at several heights. Corners get no slack:
a body can overlap a convex corner by up to *r* before either face holds it.

**Segment.** The first triangle (any kind, either side) that segment **a** → **b** crosses: one
whose plane (for floors and ceilings, whose height function) has **a** strictly on one side and
**b** on the other side or on it, and whose edge rows accept the crossing point. A triangle the
segment starts on does not count, so a camera ray from a point on a floor finds what is beyond.
The answer is the fraction *t* along the segment, the triangle, and whether it was hit from
behind. Every cell the segment's box touches is asked (each in its own frame), and in each the
buckets the segment passes through.

**Drawing** (three passes, [WORLDKIT.md](WORLDKIT.md), "Sight lines and stand-ins"). The frame's
origin is the centre of the camera's cell; the camera and everything drawn are relative to it,
so the vertex transform never sees a large coordinate. First the **far pass**: the stand-ins of
the cells 2 .. *R* cells from the camera's cell (Chebyshev distance), with the clip range
[*S*/2, 3*S*(2*R* + 1)/4], each culled by its stand-in sphere, flushed (`ot_flush()`) so the near
pass draws over it. Then the 3 × 3 cells around the camera's cell, with the range
[0.1, 1.5 *S*] by default, each cell culled by its `bounds`, then each present placement by its
sphere: first the **ground pass**, their ground placements, flushed when any was drawn
([Ground](#ground)); then the **near pass**, the rest. A sphere is culled when it lies wholly
outside one of the six planes of the view volume. A sphere in view that also lies inside the
guard band (screen x and y within -1000..999, with room to spare) and in front of the near plane
by 1/16 unit needs no clipping, so its mesh is drawn by the loops that skip the per-vertex and
per-face clipping tests (`__draw_mesh_safe`; the same packets). The near set is convex, so along any line of
sight near geometry comes before far; it is chosen around the camera, which may trail the player.
A near cell whose region is not loaded is drawn as its stand-in, in the near pass. The game's
objects join the near pass after it ([Objects](#objects)). With a depth buffer nothing is flushed
and there is no ground pass ([Objects](#objects), "In depth mode").

Each present placement in view is drawn at the level of detail its distance chooses
([Levels of detail](#levels-of-detail)), or not at all past its cull mark. In a 1.5 pack, what the
eye's occlusion zone hides is skipped first ([Occlusion zones](#occlusion-zones)).

**Paths.** A reader answers the two queries above ([Paths](#paths)) on a path it holds by
number or by name.

### Faces in one bucket

The near pass sorts by an ordering table of 1,024 buckets over its range (0.094 units a bucket for
the default 96 units). Faces in one bucket are not sorted among themselves: a bucket is a list to
which each face is added at the head, and the GPU draws it from the head, so **the face submitted
first is drawn last, on top**, whatever their depths (`tests/test_worldpack.py`,
`BucketRuleTests`: of two overlapping quads 0.0001 units apart, the farther, submitted first, is
the one on screen, within one mesh and across two `mesh_at()` calls). `wp_draw()` submits in a
fixed order: the far pass's stand-ins (flushed), the ground pass (flushed), then the near cells
by row and column (*dj* then *di*, from −1 to 1), each cell's placements in their order in the
cell (as the recipe lists them), each mesh's faces in their order in the mesh (an Asset Kit
asset's: its recipe's order, [ASSETKIT.md](ASSETKIT.md#automated-visibility-gate)). The cart's
own meshes come after `wp_draw()`, so in a shared bucket the world's faces are drawn over them;
`wp_draw_object()`'s keys and biases move an object out of the shared buckets. Within one asset
this is a rule recipes may rely on (a sign earlier than the wall it hangs on wins their ties);
between placements it depends on the placements' order and the cells' and should not be relied
on: the World Checker judges what is drawn either way. In depth mode the buckets order only the
cost; ties in the depth test go to the face drawn later, and a decal wins with
`depth_offset()`, whatever the order ([LANGUAGE.md](LANGUAGE.md#the-depth-buffer-and-perspective-depthakr)).

**Not with the depth buffer.** All of this is about the ordering table alone. A game that draws
with the depth buffer (`render_depth(true)`, [RENDERING.md](RENDERING.md)) has its opaque faces
ordered per pixel by depth, whatever bucket or order they were submitted in; only faces whose
depths at a pixel are within about two steps of the depth key (2/4,096 of the depth, more at a
grazing angle) still tie, and a tie still goes to the later packet. So the rule above, and the
recipe orders that rely on it ("a sign before its wall"), apply only without depth; a decal on a
coplanar wall needs the decal offset instead. Semi-transparent faces are not depth-written and
are still drawn by the table. A world says it is drawn with depth in its recipe
(`"runtime": {"depth": true}`, [WORLDKIT.md](WORLDKIT.md#depth-mode)), and the World Checker
then judges it so.

**Entities.** A tracked area is the cells within a radius (0–2) of a point. An entity is active
while its cell is in the area and it is present. Each update retires the entities that stopped
being active (their cell left, or their layer went off), then spawns the ones that started.

## Validation

`decode()` in `tools/worldkit/pack.py` checks everything a reader might trip over, and is the
reference for a tool's own checks: the magic, versions and flags; that the size matches; that every
table lies inside the pack and is aligned; that every index entry's cell names its own square;
layer ids and masks against the cell's layer list; that ground placements come first in their
cells and agree with `ground_count` and the header's flag; region, mesh, string and parameter
references; paths (1.2): distinct names, point counts, that each point's `s` and `len` add up,
that the last point has no segment, a closed path ends where it starts, the box holds every point
and the length is the last `s`; levels of detail (1.3): the header's size and `near_far`, each LOD
table and set in the pack, level counts, that only the last level may be the cull mark, that
`in2` ≤ `at2` ≤ `out2` and each level's band clear of the next, every level mesh, and each cell's
slots within `lod_slots`;
region extensions (1.4): the header's size, every run's colours and variant lists, every
animation's fields and that its rows lie in the texture area, the sky's stops, increasing
elevations, colour lists and flags;
occlusion zones (1.5): each cell's zone table in the pack, its count and offset agreeing, each box
not empty and within its cell's square, reserved fields 0, layer ids, stand-in bits only for cells
that exist within 3, masks only for near cells that exist and have placements, in the pack, and
with no bit past the cell's placements;
every mesh's header, vertex and face extents; every collision block's grid, buckets and list
entries; and that entity numbers, back-references and the directory agree. Any failure raises
`PackError`; random corruption never makes it fail any other way (tested).

The console reader checks only the magic, the version and flags, the cell shift and the grid
(`wp_open()`), since a pack in ROM was validated when it was built. The encoder refuses what the
format cannot hold: degenerate triangles, coordinates past the limits, placements or entities
outside their cell, placements that overhang by more than `overhang`, more than 8 layers in a cell,
unknown or duplicate layers, too many triangles in a bucket; paths with fewer than 2 points (3 when
closed), a segment of no length, more than 4,096 stored points, longer than 16,384 units, or a
name used twice; LOD sets with no levels or more than 8, a cull mark that is not last, switch
distances closer than twice the band or past 1,400 units; a `near_far` of 0 or past 2,048; an
occlusion zone whose box is empty or reaches past its cell, names an unknown layer, or hides a
stand-in more than 3 cells away or a placement of a cell that is not a near cell.

## Precision

Measured by `tests/test_worldpack.py`, which runs the console reader over random worlds (a
heightfield across six cells, floors and ceilings at random heights including slivers 0.02
radians wide, leaning walls, slopes within 0.001° of the 45° threshold, some triangles in a layer,
queries on and a hair either side of cell seams) at cell sizes 32, 64 and 128, and compares every
answer with exact rational arithmetic over the same quantized triangles. Answers whose decisions
lie within 0.003 units of changing (a point on an edge, two surfaces at the same height) are not
compared; about three quarters are.

| Query | Agreement | Largest error seen |
|---|---|---|
| floor, ceiling | same triangle, same surface, every time | height 9.4 × 10⁻⁵ units |
| floor on a heightfield, at vertices, on shared edges and on cell seams | always found | height 7.6 × 10⁻⁵ |
| wall push | same walls | position 1.1 × 10⁻⁴ units |
| segment | same triangle | *t* × (distance across the plane) 9.4 × 10⁻⁴ |
| an entity's own block (floor, ceiling, push, segment) | same | as above |

Paths are compared the same way (`PathTests`): 900 nearest-point and point-at-length queries on
random paths of 1–8 segments in and around a 64-unit cell, some closed, against
`pack.path_nearest()` and `pack.path_at()` in exact arithmetic, skipping answers within 0.003
units of changing (about a quarter): the same segment every time, and positions, lengths along
and squared distances within 7.7 × 10⁻⁴ units.

A segment's hit position is **a** + (**b** − **a**) *t* with *t* from one `fdiv`, so it carries
about (segment length) × 2⁻¹⁶ of error (a ray straight down 11 units onto a roof at 3.5 reports
3.50014); a floor query at that point gives the exact height.

## Costs

Measured on the console's clock by `tests/worldpack/bench.akr` (run it with
`WORLDPACK_VERBOSE=1`) in a 3 × 3 world of 64-unit cells, each with a heightfield ground of
2-unit quads, 40 box buildings and 100 small props: per cell 2,128 floors, 320 walls and 80
ceilings, filed in a 32 × 32 grid (2-unit buckets: on average 2.7 floors, 2.5 walls and 0.7
ceilings a bucket). Means over 400 random points, cycles:

| Query | Cycles | For comparison |
|---|---|---|
| `wp_cell_at` | 74 | |
| `wp_floor` | 448 | Tsumiki's `tk_floor_at` among 41 solids: about 2,000 |
| `wp_floor_across`, span 0.4375: a floor in the window / none, nothing bridged | 512 / 11,478 | the second is 25 floor queries: the body in the air |
| `wp_ceiling` | 312 | |
| `wp_push`, radius 0.5 | 382 | |
| `wp_ray`, 3.7 units | 3,078 | Tsumiki's `tk_raycast`: about 900 short, 4,400 across 41 solids |
| `wp_ray`, 15 units | 8,924 | |

Paths, measured by `tests/test_worldpack.py` (`PathTests.test_costs`, with
`WORLDPACK_VERBOSE=1`) on rails of 1, 4 and 16 segments, the call itself taken off, cycles:

| Query | Cycles |
|---|---|
| `wp_path_nearest`, the point out of reach (the box test) | 117 |
| `wp_path_nearest`, a grind check by the rail (reach 0.6): 1, 4, 16 segments | 297, 437, 942 (about 255, and 43 a segment) |
| `wp_path_at`: 1, 4, 16 segments (a binary search) | 183, 212, 241 |

A per-frame grind check against the rails near the player costs a few hundred cycles each;
checking every path of a level of tens of paths, most rejected by the box, a few thousand.

A segment visits about (length / bucket size) × 2 buckets and tests each triangle in them (about
45 cycles a triangle that it misses), so camera rays are the expensive query: a follow camera's
one or two rays a frame cost 1–4 % of the CPU.

Drawing, cycles:

| | Cycles |
|---|---|
| culling a placement (its sphere against six planes) | about 60 |
| a placement drawn: fixed cost beyond its vertices and faces | about 500 (a one-triangle mesh costs 562; `mesh_at()` 755) |
| a 12-triangle box placement drawn | 1,445 (`mesh_at()`: 1,637) |
| the demonstration views: 4 near cells, 8–11 placements (ground of 64 quads a cell), a stand-in | 84,000–93,000 for 310–460 triangles |
| the ground pass, in a view that draws ground (the flush, a second look at the near cells) | about 2,000 (2,068 and 2,289 on average over the example worlds' views) |
| a 1.1 pack without ground, against the 1.0 reader | 58–88 more a view (the example worlds) |
| choosing a placement's level of detail (in view, with a LOD set) | about 135 a placement drawn (`LodTests.test_drawing_and_cost`: 45 placements drawn, 84,945 cycles against 78,864 with the same meshes at every level) |
| a 1.3 pack without levels, against the 1.2 reader | 53–471 more a view (a test of `lod_off` a cell and of the mesh a placement; the example worlds and the garden: 239 on average over the garden's 600 views, whose peak is 476,000), the same triangles, GPU cycles and pictures in every view |
| `wp_draw_object()` with the bounds known, against `mesh_at()` (the example coin: 22 vertices, 40 triangles) | 5,052 against 4,801 drawn; 235 culled (`mesh_at()` out of view: 2,603) |
| `wp_mesh_bounds()` | about 17 a vertex and 260 more (the coin: 710) |
| `wp_draw_entities()`, per entity with a mesh (the cell walk, layer test, bounds and `wp_draw_object()`) | the coin: 6,201 drawn, 1,384 culled |
| (1.5) occlusion: a view from a zone behind a wall (`OcclusionTests.test_costs`: 11 of 22 placements and 2 stand-ins hidden, 10 of them in view) | 27,802 against 43,108 with `wp_occlusion` false |
| (1.5) a zone whose hidden placements are all out of view (22 placements bit-tested) | 248 more (38,330 against 38,082): about 11 a placement looked at |
| (1.5) the eye in no zone (one zone looked at), against the same world without zones | 43 more (38,020 against 37,977) |

The table predates the loops for meshes with nothing to clip and the cache of entity bounds
(2026-10). With them, `tests/test_worldpack.py`'s cost cart (100 small boxes as placements; run
with `WORLDPACK_VERBOSE=1`) draws its street view in 288,066 cycles instead of 330,949 and its view
from above in 884,664 instead of 1,021,530; with its detailed assets, the movement garden's
heaviest World Checker view (2,003 triangles) takes 432,968 instead of 556,288, and its 600 views
197,009 on average instead of 238,294, with the same pictures.

The fixed cost per placement drawn matters for budgets: 100 small props drawn cost 50,000 cycles
before their faces. A level of detail pays when its mesh saves more than its choice costs (135
cycles, about one visible face), and a cull mark saves the whole draw (about 500 cycles plus the
faces): in the same test, 60 boxes with levels and a cull mark drew 29 of 45 in view, 61,958
cycles against 78,864 at full detail. Placements should be assets of tens of faces or more; scatter of tiny props is
better merged into one mesh per cell (see [Extensions](#extensions-not-made)).

## The console reader (`stdlib/worldpack.akr`)

Not part of the prelude: `import "worldpack.akr"`. It holds one pack open, keeps no storage per
entity (spawning is by callback, drawing straight into the packet arena), and has two fixed
capacities: `WP_MAX_TRACK` = 25 cells, which is every cell `wp_track()` can reach at its largest
radius (2), and `WP_MAX_LOD` = 2,048 bytes of level memory, one per placement slot (`lod_first` +
*k*), for the hysteresis; a placement whose slot lies past it is drawn at the plain level. World positions in and out are `fixed` world coordinates.

| | |
|---|---|
| `wp_open(pack) -> bool` | open a pack (checks magic, version, flags, grid); layers start as the pack says |
| `wp_cell_size()`, `wp_cell_index(x)`, `wp_cell(i, j)`, `wp_cell_at(p)`, `wp_cell_centre(c)` | the grid |
| `wp_layer_count()`, `wp_layer_name(id)`, `wp_layer_find(name)`, `wp_layer_on(id)`, `wp_layer_set(id, on)`, `wp_cell_mask(c)` | layers (exclusive groups applied) |
| `wp_pad()` | the header's `pad`: how far walls are copied past a cell, the largest radius `wp_push` answers for exactly |
| `wp_draw(eye, yaw, pitch)` | the far, ground and near passes; leaves the near camera set, relative to `wp_view_origin()`. In depth mode one pass into the depth tables, no ground pass ([Objects](#objects), "In depth mode") |
| `wp_draw_object(m, pos, yaw, radius, base) -> bool` | after `wp_draw()`: an object's mesh at a world position, culled by its sphere, keyed at its nearest point, nearer while the eye is above `base` ([Objects](#objects)); in depth mode without the key and the bias |
| `wp_draw_entities() -> s32`, `wp_entity_draw(e) -> bool` | the live entities' meshes in the near cells (or one entity's mesh) through `wp_draw_object()`; how many were drawn |
| `wp_mesh_bounds(m) -> vec2` | a mesh's radius around its origin and its lowest vertex's height (a scan) |
| `wp_view_origin()` | where this frame is drawn around: draw the game's own meshes at `pos − wp_view_origin()` |
| `wp_clip_near`, `wp_near_far`, `wp_far_ring`, `wp_region_loaded`, `wp_ground_first` | settings (0.1, the pack's `near_far` or 1.5 cells, 3, −1 = any, true; false draws ground in the near pass, as 1.0 did) |
| `wp_occlusion` | (1.5) occlusion zones on (true; false draws what they hide too, as 1.4 did) |
| `wp_lod`, `wp_lod_fine`, `wp_lod_reset()` | levels of detail (1.3): on (true; false draws every placement's level 0, as 1.2 did); the finest level the band allows, without memory (false; the World Checker's worst case); forget the levels drawn (after the camera jumps) |
| `wp_object_bias`, `wp_object_squash` | `wp_draw_object()`'s settings: units nearer from above (1.5); squash of the object's own depths (2; 1: no key, the bias alone) |
| `wp_stats` | near cells, placements looked at and drawn, stand-ins drawn, ground placements drawn, placements drawn at a coarser level (`coarse`) and culled by their LOD set (`lod_culled`), placements and stand-ins skipped by the eye's occlusion zone (`occluded`, `standins_occluded`) and the zone's number in its cell (`zone`, −1 for none), last `wp_draw` |
| `wp_floor(p, above)`, `wp_ceiling(p, below)`, `wp_push(p, radius)`, `wp_ray(a, b)` | collision in the world; answers in `wp_hit` |
| `wp_floor_across(p, above, below, span)` | `wp_floor()` bridging cracks narrower than `span`: where it finds no floor at or above `p.y - below`, the higher of two floors in that window on either side of `p`, at most `span` apart along x, z or a diagonal ([WORLDKIT.md](WORLDKIT.md#cracks)) |
| `wp_coll_floor`, `wp_coll_ceiling`, `wp_coll_push`, `wp_coll_ray` | the same against one block, in its frame (an entity's: `wp_entity_coll(e)`) |
| `wp_hit_normal()` | the unit front normal of what was hit |
| `wp_entity(n)`, `wp_cell_entity(c, k)`, `wp_entity_pos(e)`, `wp_entity_live(e)`, `wp_entity_params(e)`, `wp_entity_mesh(e)`, `wp_entity_coll(e)` | entities |
| `wp_track(p, radius, spawn, retire)`, `wp_track_clear(retire)` | spawn and retire as the area and layers change |
| `wp_region_count()`, `wp_region_name(k)`, `wp_variant_name(k, v)` | region and palette variant names (the name accessors answer null for an index out of range) |
| `wp_region(k)`, `wp_palette_load(k, v)`, `wp_palette_blend(k, va, vb, t)`, `wp_textures_load(k)`, `wp_texture_load(k, t)` | region palettes (the main run) and textures (spreading a swap over frames is the game's: one `wp_texture_load` a frame) |
| `wp_region_enter(k, v)`, `wp_variant_load(k, v)`, `wp_variant_blend(k, va, vb, t)`, `wp_backdrop_load(k)`, `wp_region_ext(k)` | (1.4) entering a region: its texture set, variant *v* of every palette run, its backdrop art, its animations restarted, `wp_region_loaded = k`; variants over every run (a 256-colour run blends in about 9,700 cycles) |
| `wp_animate(t) -> s32`, `wp_anim_copied` | (1.4) the entered region's animated textures at tick *t*: frames copied into their tiles when they change; how many changed, and the rows copied (about 125 cycles and 70 an animation whose frame did not change; a change copies its rows: 2 rows of 4 bytes about 140 cycles, the night market's neon sign, 17 rows of 17 bytes not word-aligned, about 2,800) |
| `wp_backdrop_show(k)`, `wp_backdrop_draw(yaw, pitch)`, `wp_backdrop_variant(va, vb, t)`, `wp_backdrop_hide()`, `wp_backdrop_focal` | (1.4, `import "wpbackdrop.akr"`, which imports planes.akr) the region's sky and silhouette on the plane chip: compositor on, BG1 set up; each frame's lines and scroll (about 5,500 cycles); the sky's colours blended between variants |
| `wp_path_count()`, `wp_path(n)`, `wp_path_find(name)`, `wp_path_name(p)`, `wp_path_points(p)`, `wp_path_point(p, k)`, `wp_path_length(p)` | paths (1.2; none in an older pack) by number or name (null when there is none), their points and length; `p.flags` (`WP_PATH_RAISED`, `WP_PATH_CLOSED`) and `p.surface` |
| `wp_path_nearest(p, pos, reach)`, `wp_path_at(p, s)` | the nearest point on a path within reach (a grind check), the point at a length along it (a mover); answers in `wp_near`: `pos`, `dir`, `seg`, `t`, `s`, `dist2` |
| `wp_path_draw(p, colour)` | the path as lines over the frame, after `wp_draw()` (a debug view) |

**Depth mode** (`import "depth.akr"`, `render_depth(true)`): `depth.akr` replaces `wp_draw()` and
`wp_draw_object()` (it imports `worldpack.akr` for that), as [Objects](#objects) describes. On
the Movement Garden's scripted runs (`tests/depth/garden.sh`) it costs 1.4–4.6 % more CPU a
frame than the ordering table (mean: 155,461 → 157,583 on the tour of the park, 304,639 →
318,686 in the kick alley, 209,136 → 217,593 sweeping the camera at the spawn): the faces with
depth cost 14–24 cycles more each, less the two `ot_flush()` table resets it no longer makes.
The GPU figures are in [LANGUAGE.md](LANGUAGE.md#the-depth-buffer-and-perspective-depthakr).

Not implemented: reading audio banks, swapping a region's textures across frames by itself
([WORLDKIT.md](WORLDKIT.md#region-seams)), character control, cameras, goals and saving (the
game's).

## Extensions not made

Each was left out because version 1.3 is clearly sufficient without it; each fits as a minor
version (a reserved field or a flag) unless noted.

- **Pitch, roll and scale on placements.** Yaw covers buildings and props on level ground; a
  tilted asset is modelled tilted. Adding them changes the placement record (a new major).
- **A merged static mesh per cell**, for scatter too small to be worth a placement each (the
  fixed draw cost above).
- **Analytic shapes** (boxes, cylinders) beside triangles, and **heightfields** as a grid of
  heights rather than triangles. Triangles were fast enough.
- **Collision layers that are not draw layers**, and per-triangle flags (one-sided walls, forced
  kinds). The surface byte and the tag can carry game meaning meanwhile.
- **Occluder fusion.** A zone hides what one occluder hides alone (WORLDKIT.md, "Occlusion"); the
  sets are the format's, so a kit that joins shadows needs no new version.
- **Non-uniform cells** (quadtrees, irregular districts): out of scope; the grid is uniform.
- **Ordered ground** (several ground passes, lowest first, so a raised floor could be ground over
  a lower one) and ground per face rather than per placement. Neither would stop ground from
  being drawn under what it truly hides, which is the larger limit ([Ground](#ground)).
- **Compression.** ROM is read in place, so packs are stored as they are used.
- **Entity bounds.** The entity record's reserved words could hold its mesh's radius and lowest
  point, which `wp_entity_draw()` finds by scanning the mesh (710 cycles for the example coin,
  about an eighth of drawing it); the reader keeps the last scan of up to 16 meshes (by address,
  emptied by `wp_open()`), so it scans a mesh again only when another evicts it. A minor version:
  a reader would scan where they are zero.
- **A sort hint per entity or placement** (a bias of its own). The reader's rule needs none for
  the cases it handles, and a hint on the object would not fix the thin wall in front of it, which
  depends on the wall.
