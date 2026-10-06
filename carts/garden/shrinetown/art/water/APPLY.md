# Shrine town: the water, authored and not yet applied

Textures for the canal, the school pool, the two ponds, the falls pool, the brook and the
waterfall, that move without costing VRAM. Authored 2026-10-05 and proved on a scratch copy of
the world (`../preview_scratch.py`), not applied: `shrinetown.world.json`, its generators and the
placement zones are untouched. The edits are below, exactly; `../apply_patch.py` makes the same
edits to a loaded world file as code (it is what the pictures were built from), and
`cart.patch` is the cart's.

| File | What |
|---|---|
| `water.png` | 32 × 32, 15 colours: the canal, the pool, the culvert, the brook's upper reach |
| `pond_water.png` | 32 × 32, 15 colours: the two ponds and the falls pool (11 cycled colours, 4 fixed: an orange, a gold and a red-brown leaf, a lily pad) |
| `falls.png` | 16 × 32, 15 colours: the waterfall (12 cycled, 3 fixed) |
| `draw_water.py` | Draws the three PNGs and writes `water_ramps.akr`. `--preview DIR` tiles them |
| `water_ramps.akr` | Generated (do not edit): each texture's cycled colours, which `water_cycle.akr` looks for |
| `water_cycle.akr` | The colour cycling: `water_cycle_enter()`, `water_cycle_update()`, `water_cycle_sync()` |
| `cart.patch` | The garden cart's 26 changed lines (`ground.akr`, `game.akr`) that call it |
| `preview/` | Before and after, day and night, at 320 × 240; four frames of the motion; the textures tiled |

## How it moves

A texel of each PNG is a phase of a wave, not a colour: its 15-bit colour is one of N phase
colours that go once round (a dull body that swells and fades, one bright crest). Rotating those
colours in palette memory one place moves every crest one texel-phase on, so the ripples travel
across the canal and the falls run down. The still texture is what is in VRAM (the kit's own
terrain texture, frame 0); nothing is copied into a tile and no animation is in ROM (the Asset
Kit's `frames` copy a whole frame into the tile, and terrain textures may not have them). Every
water texture has exactly 15 colours so the kit's packer gives it a 4-bit palette of its own.
`water_cycle_enter()` finds them in palette memory by their colours, so it does not matter where
the packer puts them.

Speeds (`WATER_CYCLE_TICKS` in `water_cycle.akr`): the canal a step every 7 frames (a crest
moves 0.1 m a step: 15 steps, 1.6 m and 1.75 s a cycle), the ponds every 10, the falls every 3, downwards.

Measured on the console (`cycle_count()`, the shrine region): `water_cycle_enter()` 15,228 cycles
once, a frame that changes a step up to 1,951, one that does not 261, 583 on average over 420
frames. Without the cart patch the water is textured and still; the world edits stand alone.

## The world's edits

`shrinetown.world.json` is `make_world.py`'s output; the places in the generators are named. A
textured water material is the kit's ordinary textured terrain material
([WORLDKIT.md](../../../../../docs/WORLDKIT.md#textured-terrain)) with `water: true`.

### 1. Materials: `terrain.materials` (`make_world.py`'s `materials`, joined from the parts)

`water` and `falls` get a `texture`; `stream_water` and `pond_water` are new. Spans are 23 for
all of them: water is flat or a sweep, its faces are big and all windowed, so the span saves
nothing and costs bytes. Scales are in metres a repeat. They are set by reach, not taste: a
water rectangle is up to a tile (32 m) and starts anywhere in its first repeat, so 32 texels at
4.8 m (6.7 texels a metre) reach 33 m before a texel coordinate passes 255 (the build says
`terrain_texture_stretched` or refuses an edge if not). The falls' sheet is 36 m tall and 9 m
wide: 16 × 32 at [3.0, 6.4].

```json
"water":        {"color": "#3f7393", "water": true, "tag": "water",
                 "texture": {"image": "art/water/water.png", "scale": [4.8, 4.8], "span": 23}},
"stream_water": {"color": "#3f7393", "water": true, "tag": "water",
                 "texture": {"image": "art/water/water.png", "scale": [7.2, 7.2], "span": 23}},
"pond_water":   {"color": "#2f4c46", "water": true, "tag": "water",
                 "texture": {"image": "art/water/pond_water.png", "scale": [4.8, 4.8], "span": 23}},
"falls":        {"color": "#dce8f0", "water": true,
                 "texture": {"image": "art/water/falls.png", "scale": [3.0, 6.4], "span": 23}}
```

`stream_water` is the same image as `water` at a coarser scale: the same tile in VRAM (equal
tiles are packed once), but the brook's 4 m cross-sections stay within the texture's reach, so
the sweep is not cut into twice the triangles (246 stay 276, not 486; `wp_water()` tests every
water triangle).

### 2. Which water uses which: the operations and paths

| Where (generator → part) | Now | Becomes |
|---|---|---|
| `parts/town.json` ops 12, 16, 21: the canal (rect 44,0 → 52,292), the pool (214,22 → 240,40), the culvert (234,96 → 238,124) | `water` | unchanged |
| `parts/core.json` ops 29, 30: the ponds (circles 234,140 r 16.8 and 236,166 r 17.92) | `water` | `pond_water` |
| `parts/mountain.json` op 19: the falls pool (circle 214,322 r 7.5, level 12.0) | `water` | `pond_water` |
| `parts/mountain.json` path `stream_upper` (sweep material) | `water` | unchanged |
| path `stream` (`make_world.py` joins `stream_gorge` and `core_stream`: both are `water`) | `water` | `stream_water` |
| path `falls_sheet` | `falls` | unchanged (now textured by 1) |

**One more operation** (`make_world.py`, appended after the parts' operations; water is last
operation wins per quad). The north pond's circle reaches z 123.2, south of the region boundary
(z 128), so its southern cap is drawn in the town region, and the town cannot pay 2,080 bytes for
a second water texture (the town's allowance is 2,112 over the ground's). The cap is drawn in
`water`, the town's, again:

```json
{"op": "water", "area": {"polygon": [[222.242, 128.0], [245.758, 128.0], [244.799, 127.13],
  [242.4, 125.451], [239.746, 124.213], [236.917, 123.455], [234.0, 123.2], [231.083, 123.455],
  [228.254, 124.213], [225.6, 125.451], [223.201, 127.13]]}, "level": 0.0, "material": "water"}
```

(`apply_patch.py` computes it from the circle; the polygon is the circle's part with z < 128.)

### 3. Night: `regions.*.variants.night.colors`

Both regions' `night` variants carry `"colors": {"water": "#1c3050"}`, which recolours a
palette-backed material; a textured one has no palette entry and the build refuses it ("No
palette-backed material 'water' is drawn in region 'town'"). Delete that key (`make_world.py`
copies the shrine world's variants for both regions: delete it from the copies). The night's
`surface.multiply` `#4a5884` tints the water textures like everything else, crests included.

### 4. Cells, regions, budgets

No cell changes. The regions' `textures.budget` stay (389,120 and 307,200: the world builds
inside them). Nothing is placed by the zones: the water is terrain.

### 5. The cart

From the repository root, `patch -p1 < carts/garden/shrinetown/art/water/cart.patch` (a dry run
checks clean on this branch; the patched cart was built and run for 120 frames in a scratch copy). It imports `water_cycle.akr` by path from
`ground.akr`, calls `water_cycle_enter(0, 0)` when a world opens (none cycling), and after every
`wp_region_enter(k, 0)` in the shrine town (`follow_region()` and `world_load()`) a new
`world_region_entered(k)` that also shows that region's backdrop (see `../backdrop/APPLY.md`);
`update()` calls `water_cycle_update(frame())`. A cart that changes variants calls
`water_cycle_sync()` after `wp_variant_load()` and `wp_variant_blend()` (they rewrite the
palettes); the garden does not change variants.

## What it costs

Measured on the scratch world (`B=build-ws`), with the ground not yet textured. Texture VRAM, the
kit's bytes on its 8-texel grid (`report.json` `regions.NAME.textures.vram_bytes_allocated`):

| Region | Tiles | Bytes | Of |
|---|---|---|---|
| town | `water` 32 × 32 at span 23: 1,568 stored + 512 as loaded | **2,080** | 2,112 free after the ground (GROUND.md: ground 38,848 of 40,960): **32 spare** |
| shrine | `water` 2,080, `pond_water` 2,080, `falls` 16 × 32 (40 × 56 stored 1,120 + 256) 1,376 | **5,536** | 16,384 free after the ground (106,496 of 122,880): 10,848 spare; with the ground's two optional additions (concrete 2,080, planks 7,712) 1,056 spare |

`tools/textures.py --report` counts them under `terrain`: 2,080 of 40,960 and 5,536 of 122,880 on
their own; with GROUND.md's, 40,928 and 112,032 (121,824 with concrete and planks).

Also: one 4-bit palette in the town and three in the shrine (against the 180 and 60 allowed);
terrain pieces with a texture window: 55 pieces and 159 triangles (about 55 cycles a piece and 10 a
triangle when visible); `wp_water()`'s water triangles 449 → 479 (+360 cycles a query);
`pond_water`'s leaves are fixed colours, so a variant that recolours the texture recolours them.

## Documents

AGENTS.md's Generators table (not edited here, to leave the integration branch's table to its
merges) needs two rows: `art/water/draw_water.py` writes `carts/garden/shrinetown/art/water/`
(`water.png`, `pond_water.png`, `falls.png`, `water_ramps.akr`) and `art/backdrop/draw_backdrop.py`
writes `art/backdrop/` (`town_backdrop.png`, `shrine_backdrop.png`, `backdrop.json`); the second
is not on the command line `python3 tools/NAME.py`, they are run by path. TEXTURES.md's regions
table says "the shrine's `day`, `night`; its mountains" under "Palette variants, backdrop": each
region has its own backdrop now, and its allowances: the town's ground 40,960 includes the water's
2,080, the shrine's 122,880 its 5,536.

## Checking it

```sh
B=build-ws python3 carts/garden/shrinetown/art/preview_scratch.py --tag after --water --backdrop --cycle
B=build-ws python3 carts/garden/shrinetown/art/preview_scratch.py --tag before --none     # the world as it is
B=build-ws python3 carts/garden/shrinetown/art/contact.py                                  # sheets of both
```

After applying, `report.json` `terrain.textures` must list `water`, `stream_water`, `pond_water`
and `falls` with `stretched` 0, and the regions' textures must be 2,080 and 5,536 bytes over
what they were.

## With the larger VRAM

- A pool of its own for the school (bright tile-blue with the lane lines and caustics, 32 × 32
  or 64 × 32: 2,080 to 3,000 bytes): the town has 32 spare now, so this is the first thing the
  bump should buy; the pool reuses the canal's murky water today.
- 64 × 64 at a 2.4 m repeat (finer ripples, no visible tiling on the canal's long runs;
  5,920 bytes each region), or a second canal texture for the south reach (the town) and the
  woods reach (the shrine).
- Span 87 on the water so the pond's big rectangles need no texture window (7,200 stored a piece
  instead of 2,080: only worth it if windows show in the checker's counts).
- Animated *tiles*, with the kit change that lets terrain textures have `frames`: a four-frame
  pond with koi shadows and rings, the falls' spray as foam moving along the pool's rim (each
  frame 512 bytes of ROM, not VRAM).
- A splash decal for the falls' foot, as an Asset Kit asset with a real animated sheet.
