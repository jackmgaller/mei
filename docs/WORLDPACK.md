# The world pack format

**Version 1.0.** A world pack (`*.world.bin`) is the contract between the World Kit
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
| Collision blocks (cells and entities) | specified | yes, with an exact oracle | yes: floor, ceiling, wall push, segment |
| Entities and parameter records | specified | yes | yes: iteration, tracking, lookup by number |
| Regions: palette variants, texture set | specified | yes | palettes loaded and blended; textures loaded at once only |
| Regions: audio bank, backdrop | specified | yes | **specified, reader not yet implemented** |
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
11. [Entities](#entities)
12. [Collision blocks](#collision-blocks)
13. [Meshes and strings](#meshes-and-strings)
14. [What a reader does](#what-a-reader-does)
15. [Validation](#validation)
16. [Precision](#precision)
17. [Costs](#costs)
18. [The console reader](#the-console-reader-stdlibworldpackakr)
19. [Extensions not made](#extensions-not-made)

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

The header holds a major and a minor version; this document is 1.0.

- A reader refuses a pack whose **major** version it does not know.
- A reader accepts a pack with the same major and a **higher minor** version and reads it as the
  minor version it knows. A minor version may only add: data reached through fields that are
  reserved (zero) in earlier minors, header bytes past the 64 this version defines (the header
  says its own size), and flag bits. It never changes the size or meaning of an existing field or
  record.
- Header **flags** bits 0–3 mark features a reader may ignore; bits 4–7 mark features a reader
  must understand, so a reader refuses a pack with a bit 4–7 set that it does not know. Version
  1.0 defines none of them.

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

## Layout

```
header         64 bytes at offset 0
index          w x h u32: the offset of each grid square's cell, or 0
layers         layer_count x 8 bytes
regions        region_count x 32 bytes, each pointing at its textures, samples, palettes, backdrop
cells          96 bytes each, pointing at their placements, entities and collision block
  placements   48 bytes each
  entities     64 bytes each
  collision    a 48-byte block header, floor, wall and ceiling records, buckets, a u16 list
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
| 6 | `u16` | `minor` | 0 |
| 8 | `u32` | `size` | the pack's length in bytes, a multiple of 4 |
| 12 | `u8` | `cell_shift` | 4–7 |
| 13 | `u8` | `flags` | see [Versions](#versions); 0 in 1.0 |
| 14 | `u16` | `header_size` | 64 in 1.0; at least 64 |
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
| 20 | `u16` | `first_colour` | the palette memory colour (0–4,095) the variants load to |
| 22 | `u16` | `backdrop_count` | |
| 24 | `u32` | `palette_off` | `variant_count` × `u32` name offsets, then `variant_count` × `colour_count` `u16` colours |
| 28 | `u32` | `backdrop_off` | `backdrop_count` × 12 bytes |

**Texture** (12 bytes): `u8 slot` (0–15), `u8 flags` (bit 0: 4-bit), `u16` reserved,
`u32 data` (offset), `u32 bytes`. The bytes are copied to the slot as `load_texture()` copies
them (the GPU's layout, spec p. 11); a texture larger than one slot runs into the next slot, as an
8-bit texture does.

**Palette variants.** Variant *v*'s colours are the `colour_count` `u16` 15-bit colours at
`palette_off` + 4 × `variant_count` + 2 × `colour_count` × *v*. Loading variant *v* writes them to
palette memory from colour `first_colour`; blending between two is `palette_lerp()`.
`first_colour + colour_count` ≤ 4,096.

**Sample** (20 bytes; *specified, reader not yet implemented*): `u32 name`, `u32 data` (offset of
the sample bytes, read in place: channels play from ROM), `u32 samples` (length in samples),
`u32 loop_start`, `u32 flags` (the `play_sample()` flags: `SND_16BIT`, `SND_ADPCM`, `SND_LOOP`,
`SND_REVERB`).

**Backdrop copy** (12 bytes; *specified, reader not yet implemented*): `u32 address` (a VRAM
address: an atlas page, a plane map, a line table, `planes.akr`'s layout), `u32 data`,
`u32 bytes`. A backdrop is the list of copies that put a region's plane-chip art in VRAM. How the
planes are then set up (`plane()`, scroll rates) is the game's.

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
| 76 | `[5]u32` | reserved | |

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
| 45 | `u8` | `flags` | reserved |
| 46 | `u16` | `tag` | the encoder's number for it (for reports and tests) |

The sphere must contain every vertex of the mesh as drawn with the stored `cos` and `sin`. The
reference encoder takes the centre of the vertices' box and the largest distance from it, plus
2/65,536. The mesh's vertices may reach at most `overhang` past the cell's square, and `pos`
lies in the square.

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
a save remembers is `saved_bit`.

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

**Drawing** (two passes, [WORLDKIT.md](WORLDKIT.md), "Sight lines and stand-ins"). The frame's
origin is the centre of the camera's cell; the camera and everything drawn are relative to it,
so the vertex transform never sees a large coordinate. First the **far pass**: the stand-ins of
the cells 2 .. *R* cells from the camera's cell (Chebyshev distance), with the clip range
[*S*/2, 3*S*(2*R* + 1)/4], each culled by its stand-in sphere, flushed (`ot_flush()`) so the near
pass draws over it. Then the **near pass**: the 3 × 3 cells around the camera's cell, with the
range [0.1, 1.5 *S*] by default, each cell culled by its `bounds`, then each present placement by
its sphere. A sphere is culled when it lies wholly outside one of the six planes of the view
volume. The near set is convex, so along any line of sight near geometry comes before far; it is
chosen around the camera, which may trail the player. A near cell whose region is not loaded is
drawn as its stand-in.

**Entities.** A tracked area is the cells within a radius (0–2) of a point. An entity is active
while its cell is in the area and it is present. Each update retires the entities that stopped
being active (their cell left, or their layer went off), then spawns the ones that started.

## Validation

`decode()` in `tools/worldkit/pack.py` checks everything a reader might trip over, and is the
reference for a tool's own checks: the magic, versions and flags; that the size matches; that every
table lies inside the pack and is aligned; that every index entry's cell names its own square;
layer ids and masks against the cell's layer list; region, mesh, string and parameter references;
every mesh's header, vertex and face extents; every collision block's grid, buckets and list
entries; and that entity numbers, back-references and the directory agree. Any failure raises
`PackError`; random corruption never makes it fail any other way (tested).

The console reader checks only the magic, the version and flags, the cell shift and the grid
(`wp_open()`), since a pack in ROM was validated when it was built. The encoder refuses what the
format cannot hold: degenerate triangles, coordinates past the limits, placements or entities
outside their cell, placements that overhang by more than `overhang`, more than 8 layers in a cell,
unknown or duplicate layers, too many triangles in a bucket.

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
| `wp_ceiling` | 312 | |
| `wp_push`, radius 0.5 | 382 | |
| `wp_ray`, 3.7 units | 3,078 | Tsumiki's `tk_raycast`: about 900 short, 4,400 across 41 solids |
| `wp_ray`, 15 units | 8,924 | |

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

The fixed cost per placement drawn matters for budgets: 100 small props drawn cost 50,000 cycles
before their faces. Placements should be assets of tens of faces or more; scatter of tiny props is
better merged into one mesh per cell (see [Extensions](#extensions-not-made)).

## The console reader (`stdlib/worldpack.akr`)

Not part of the prelude: `import "worldpack.akr"`. It holds one pack open, keeps no storage per
placement or entity (spawning is by callback, drawing straight into the packet arena), and has one
fixed capacity, `WP_MAX_TRACK` = 25 cells, which is every cell `wp_track()` can reach at its
largest radius (2). World positions in and out are `fixed` world coordinates.

| | |
|---|---|
| `wp_open(pack) -> bool` | open a pack (checks magic, version, flags, grid); layers start as the pack says |
| `wp_cell_size()`, `wp_cell_index(x)`, `wp_cell(i, j)`, `wp_cell_at(p)`, `wp_cell_centre(c)` | the grid |
| `wp_layer_find(name)`, `wp_layer_on(id)`, `wp_layer_set(id, on)`, `wp_cell_mask(c)` | layers (exclusive groups applied) |
| `wp_draw(eye, yaw, pitch)` | the two passes; leaves the near camera set, relative to `wp_view_origin()` |
| `wp_view_origin()` | where this frame is drawn around: draw the game's own meshes at `pos − wp_view_origin()` |
| `wp_clip_near`, `wp_near_far`, `wp_far_ring`, `wp_region_loaded` | settings (0.1, 1.5 cells, 3, −1 = any) |
| `wp_stats` | near cells, placements looked at and drawn, stand-ins drawn, last `wp_draw` |
| `wp_floor(p, above)`, `wp_ceiling(p, below)`, `wp_push(p, radius)`, `wp_ray(a, b)` | collision in the world; answers in `wp_hit` |
| `wp_coll_floor`, `wp_coll_ceiling`, `wp_coll_push`, `wp_coll_ray` | the same against one block, in its frame (an entity's: `wp_entity_coll(e)`) |
| `wp_hit_normal()` | the unit front normal of what was hit |
| `wp_entity(n)`, `wp_cell_entity(c, k)`, `wp_entity_pos(e)`, `wp_entity_live(e)`, `wp_entity_params(e)`, `wp_entity_mesh(e)`, `wp_entity_coll(e)` | entities |
| `wp_track(p, radius, spawn, retire)`, `wp_track_clear(retire)` | spawn and retire as the area and layers change |
| `wp_region(k)`, `wp_palette_load(k, v)`, `wp_palette_blend(k, va, vb, t)`, `wp_textures_load(k)`, `wp_texture_load(k, t)` | region palettes and textures (spreading a swap over frames is the game's: one `wp_texture_load` a frame) |

Not implemented: reading audio banks and backdrops, swapping a region's textures across frames by
itself, character control, cameras, goals and saving (the game's).

## Extensions not made

Each was left out because version 1.0 is clearly sufficient without it; each fits as a minor
version (a reserved field or a flag) unless noted.

- **Pitch, roll and scale on placements.** Yaw covers buildings and props on level ground; a
  tilted asset is modelled tilted. Adding them changes the placement record (a new major).
- **A merged static mesh per cell**, for scatter too small to be worth a placement each (the
  fixed draw cost above).
- **Analytic shapes** (boxes, cylinders) beside triangles, and **heightfields** as a grid of
  heights rather than triangles. Triangles were fast enough.
- **Collision layers that are not draw layers**, and per-triangle flags (one-sided walls, forced
  kinds). The surface byte and the tag can carry game meaning meanwhile.
- **A potentially-visible set per cell** (WORLDKIT.md, question 2): a reserved cell field could
  point at it.
- **Non-uniform cells** (quadtrees, irregular districts): out of scope; the grid is uniform.
- **Compression.** ROM is read in place, so packs are stored as they are used.
