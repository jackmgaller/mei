# Shrine town: texture regions

How the shrine town's textures fit in VRAM: what the real assets need, the two texture regions,
where the boundary runs, each zone's allowance for placing the real assets, and the cuts that
make the town fit. Measured 2026-10-05 on the 110 asset recipes in `assets/` (not `greybox/`) and
the shrine's 52 in `../shrine/assets/`; the zones are those of the placement split (station,
street, east, canal, shrine).

## The real need

Bytes are the World Kit's: a region's set is packed once, each distinct tile once (the same tile
in two assets is one tile: `worldkit/textures.py`), on the packer's 8-texel grid with a tile's
1-texel gutter (`allocated()`), which is what a region's `textures.budget` counts.

| What | Summed per asset | Deduplicated |
|---|---|---|
| The 110 shrine town recipes (variants included) | 623,808 | 556,608 (629 tiles) |
| With the shrine's 52 recipes the level reuses | 737,728 | 609,664 (695 tiles) |
| The town's planned placements (zones station, street, east and canal south of z 128) | | 484,832 |
| The shrine's planned placements (shrine zone, the canal from z 128, the viaduct in c4_2) | | 135,296 |
| Tiles in both | | 10,208 (14 tiles: street lamp, bench, jizo, a few sheet tiles) |

Shared sheets count once, which is most of the difference between the two columns:

| Sheet | Assets | Summed | Once |
|---|---|---|---|
| `shrine/assets/art/foliage.png` | 15 | 60,064 | 33,120 |
| `shrinetown/assets/town_shop_2f_a/art/shopfront.png` | 14 | 27,840 | 11,648 |
| `shrinetown/assets/viaduct_span_16/art/concrete.png` | 12 | 19,040 | 4,000 |
| `shrinetown/assets/town_alley_house_a/art/town_common.png` | 13 | 12,800 | 3,072 |
| `shrine/assets/art/arch_bay_doors.png` | 6 | 12,288 | 2,048 |
| `shrine/assets/art/arch_tile.png` | 15 | 7,680 | 512 |

The ground is not textured yet. The shrine's textured ground is 15 materials, 272 KB, mostly
32-texel textures stored with a span of 223 (32,768 bytes each). A 32-texel 4-bit texture costs
8,192 bytes at span 88 (120 + 1 texels a side: 16 × 16 cells of 8 × 8), 9,248 at the default 96,
2,048 at span 24, plus 512 for the tile as loaded when some faces reach past the span (they are
drawn through a texture window: about 55 cycles a mesh and 10 a visible face more). WORLDKIT.md,
"Textured terrain", has the rules.

**One region cannot hold it:** 595 KB of assets before the ground, against 448 KB in slots 13–0.

## The regions

| Region | Cells | Slots | Budget | Free | Palette variants, backdrop |
|---|---|---|---|---|---|
| `town` | rows 0–1 (z < 128): 10 cells | 13–0 (458,752) | 389,120 (380 KB) | 15% | the shrine's `day`, `night`; its mountains |
| `shrine` | rows 2–5 (z ≥ 128): 20 cells | 13–0 (458,752) | 307,200 (300 KB) | 33% | the same |

`layout.py`'s `region_of(i, j)` says which region a cell is in; the three generators write it into
the cells and `make_world.py` writes the regions, their `textures` (`slots`, `budget`) and the
shrine's variants and backdrop for both, so the sky does not change at the boundary. The budget is
a hard limit: over it the world does not build, and the error lists every asset's share.

**There is no common set.** The World Kit packs each region's set by itself: a tile drawn in both
regions is in both sets and loaded with each. DESIGN.md 8.5's common set (asphalt, kerb, concrete,
signs, shared with the city levels) is a plan, not a kit feature; here it is the 10 KB in both.

**Entering a region.** The garden cart enters the region of the cell the player stands in when it
changes (`game.akr`, `follow_region()`): `wp_region_enter()` copies the region's whole set, about
56,000 cycles a 32 KB slot, at once. The town's set will be 12 slots or so (about 670,000 cycles),
the shrine's about 9 (500,000): the frame of a crossing is late. Near cells of the region not
entered draw as their stand-ins.

**Stand-ins.** A stand-in is drawn whichever region is loaded, so in a world with two regions the
kit's stand-ins draw every textured face in its tile's far colour, a flat colour of its own
region's palette (WORLDKIT.md, "Stand-ins made by the kit"; built for this level). Far trees are
solid cards in their foliage's colour.

**The grey box** has no textures, so the World Checker still judges every view with every cell
drawn in full; its numbers are unchanged (README.md). With the first textured asset in the pack it
enters each view's camera cell's region and draws the other region's near cells as stand-ins, as
the game does.

## The boundary: z = 128

Cells are 64 m, so the boundary is a cell line. It is the line between rows 1 and 2, 10 m north
of the front road's kerb (z 118), the whole width of the level.

**Why there.** The content changes there: south of it the town (station, shotengai, alleys,
school, machiya), north of it the shrine, its woods and mountain, the park and the cemetery. Only
10 KB of tiles are in both sets; any other cell line puts town and shrine assets in one region.
The line runs through 24 m of open, low ground that has no building of either region: the front
road (z 104–118) and the courtyard's south edge (118–128). The town's nearest buildings face the
road from z 104 (the shop rows' north ends, the coin laundry); the shrine's nearest stand from
z 130 (the cemetery's first graves at 134, lanterns at 132, the playground at 133, the chozuya at
138, the side halls at 144). In the band itself there are only poles, trees, the great torii, the
culvert's deck, the overpass and the viaduct (and the real cemetery gate, at z 125.8).

**What a player sees.** The reader cannot draw both sets at once, so the other region's cells in
the near ring (the 3 × 3 cells round the camera) are stand-ins. On the front road and in the
shotengai, the courtyard's row is drawn as stand-ins (the halls, the gate, the chozuya: from 10 m
to 60 m, where they would be drawn in full); in the courtyard and on the cemetery's lower
terraces, the road's row is (the shops' north ends from 24 m). From the precinct's terrace the
white wall hides the town; from the mountain the town is beyond the near ring anyway. Crossing
the line swaps which side is coarse, with one late frame.

This is not a hidden seam. A hidden one needs what WORLDKIT.md "Region seams" lists as not built:
cells along a boundary drawn in full from both regions (their tiles in both sets at the same
places), a swap spread over frames while nothing on screen uses the slots being replaced, and the
World Checker's seam check. Until then, options for the owner:

- raise the stand-in caps of the cells either side of the line (c0_1–c4_1, c0_2–c4_2) from 60 or
  90 to the landmark cells' 140, since they are seen from close: about 80 more far triangles for
  each one in a far view;
- move the great torii to z ≥ 128 so it is the shrine's (it is now in c2_1, the town's): from
  the courtyard it is then drawn in full, and walking through it is the crossing.

The future downtown district (DESIGN.md 7.1) would be a third region, entered under the viaduct.

## Palettes

Regions get disjoint palettes and every region's are loaded at once (WORLDKIT.md, "Palettes per
region"). A world has 255 4-bit palettes (0–254; 255 is the fonts'), and each 8-bit palette takes
16 of them from 14 downward (8-bit palette 14 is 4-bit palettes 224–239). The planned placements
need, by the kit's own packing (`kitcore/texpack.py`, `assign_palettes`; entries are the assets'
palette-backed colours, 15 to a palette):

| Region | Entries (253 / 61 colours) | Far colours | Backdrop | Texture palettes, 4-bit | 8-bit palettes |
|---|---|---|---|---|---|
| town | 17 | at most 3 | 1 | 141 (486 tiles) | 4 (38 tiles) |
| shrine | 5 | at most 3 | 1 | 45 (179 tiles) | 1 (4 tiles) |

That is 216 4-bit palettes, which must stay below 8-bit palette 10's 160: **the planned assets do
not fit the palettes either.** With no 8-bit textures (the cuts below) the 4-bit palettes may run
to 254: about 180 for the town and 56 for the shrine (an estimate: the 42 tiles made 4-bit take
some palettes of their own), about 20 to spare. So:

- **No 8-bit textures in the shrine town.** Each costs 16 palettes for one region.
- Allowances: the town 180 4-bit palettes, the shrine 60. `report.json`'s
  `regions.NAME.palette.palettes` lists them.
- The kit change that removes the limit (not built): the regions' texture palettes in one range,
  loaded with the region's set, so only the entries, far colours and backdrop stay disjoint.

## Allowances for the placement agents

Each zone's own tiles, its share of the region's shared set and the ground's, against the region's
budget. A tile of a shared prop (the list below), or one two zones use, is the shared set's; a
zone's own bytes are its other tiles. `tools/textures.py` measures it from the cells:

```sh
python3 carts/garden/shrinetown/tools/textures.py                                 # what is placed now
python3 carts/garden/shrinetown/tools/textures.py --try street:town:dagashi_shop  # as if placed
```

It exits 1 when a part or a region is over. The world build enforces the region's budget.

| Region | Part | Measured (plan) | Allowance | Cut |
|---|---|---|---|---|
| town | ground textures | 0 | 40,960 (40 KB) | |
| town | shared props | 70,432 | 49,152 (48 KB) | −21,280 |
| town | station zone | 155,008 | 98,304 (96 KB) | −56,704 |
| town | street zone | 204,704 | 147,456 (144 KB) | −57,248 |
| town | east zone | 26,848 | 26,624 (26 KB) | −224 |
| town | canal zone (rows 0–1) | 27,840 | 26,624 (26 KB) | −1,216 |
| town | **total** | **484,832** | **389,120** | **−136,672** |
| shrine | ground textures | 0 | 122,880 (120 KB) | |
| shrine | shared props | 44,896 | 49,152 (48 KB) | |
| shrine | shrine zone | 55,904 | 90,112 (88 KB) | |
| shrine | canal zone (rows 2–5) | 32,640 | 36,864 (36 KB) | |
| shrine | station zone (the viaduct in c4_2) | 1,856 | 8,192 (8 KB) | |
| shrine | **total** | **135,296** | **307,200** | |

"Measured (plan)" is `tools/textures.py --try` with every asset in the zone where PLACE_SPLIT and
PLACEMENT_NOTES put it. The canal zone straddles the boundary and has an allowance in each region.

**Shared props.** Town: `town_street_lamp` (the shotengai's lamp, shrine town's own, renamed from
`street_lamp`), the shrine's `street_lamp`, `vending_machine`, `postbox`, `town_road_signs`,
`delivery_van`, `traffic_mirror`, `mamachari`, `town_potted_plants`, `town_laundry_pole`,
`town_aircon_pipes`, `town_utility_pole_transformer`, `street_utility_pole`, `street_barrier`,
`street_guardrail`, `street_vending_machine`, `town_bench`, `firepost`, `jizo`, `hokora`,
`tanuki`, `town_crates_bins`. Shrine: the shrine's plants, litter and trees (`plant_*`,
`litter_*`, `tree_cedar`, `tree_cedar_giant`, `tree_maple`, `tree_maple_small`, `tree_ginkgo`),
`tree_zelkova`, `tree_bamboo_tall`, `forest_stone_lantern`, `shishi_odoshi`, `jizo`, `hokora`,
`tanuki`, `street_lamp`, `town_street_lamp`, `town_bench`.

**The ground.** The town's 40 KB: about four materials at span 88 (asphalt, sidewalk and paving,
the sando's stone, the canal's stone: 32 KB) and two small ones at span 24 (concrete, gravel). The
shrine's 120 KB: about twelve at span 88 (forest floor, litter, moss, gravel, ashlar, steps, rock,
earth, path, pond bed, cemetery stone, bamboo floor: 96 KB), the most seen with a larger span, or
fewer windows.

## Cuts (the town)

Not made: they are the asset owners' and the zone agents' to make. Exact where a texture goes from
8-bit to 4-bit (half its bytes) or is replaced; "about" where it is halved, which depends on the
art. Each list is more than its zone needs.

**Every zone: 8-bit to 4-bit.** Required for the palettes as well. The town's 8-bit tiles are
125,248 bytes; 4-bit, 62,624.

**Shared props** (need −21,280):

| Cut | Saves |
|---|---|
| `vending_machine` (14,336, nine textures): the shrine's `street_vending_machine` (1,600) where a plain machine will do | 12,736 |
| `postbox`'s `cap`, 128 × 128 repeating, to 32 × 32 | 7,680 |
| `delivery_van`'s `side_r`: `side_l` mirrored | 4,704 |
| 8-bit to 4-bit: `street_lamp` banner 2,080, `traffic_mirror` 1,600, `delivery_van` windshield 1,152, `firepost` alarm 960 | 5,792 |
| **Total** | **30,912** |

**Station** (need −56,704):

| Cut | Saves |
|---|---|
| `city_bus` (33,344, 85% of it 8-bit windows): no placement plans it; leave it out (or 4-bit: 14,240) | 33,344 |
| 8-bit to 4-bit: `koban` 5,440, `danchi` facade 4,096, `pachinko_parlour` storefront 4,032, `bus_stop` 1,664, `bike_rack` sign 672 | 15,904 |
| `ticket_gates`' `floor`, 144 × 48 drawn once, as a repeating 32 × 32 | 3,744 |
| `newsstand` (19,936): its goods, sign and sides at half width | about 8,000 |
| **Total** | **about 61,000** |

**Street** (need −57,248):

| Cut | Saves |
|---|---|
| 8-bit to 4-bit: `dagashi_shop` 11,200, `crane_game` 8,256, `fire_tower` 4,288, `gachapon` 2,944 | 26,688 |
| `fire_tower`'s `lattice`, 64 × 240, as a repeating 64 × 64 if it repeats | 6,880 |
| `town_shop_3f`'s `roof_a` and `roof_b` (96 × 32 each) as one repeating 32 × 32 | 3,648 |
| `arcade_gate`'s `name` and `back` (192 × 30 each) as one image | 3,200 |
| `dagashi_shop`'s `shelf_a` and `shelf_b` as one image (after 4-bit) | 2,016 |
| `crane_game`'s `sign` (160 × 40, after 4-bit) at half width | 2,016 |
| `town_shop_2f_c`'s `kanban` and `kanban_side` as one image | 1,632 |
| `kei_truck`'s `sidewin_r`: `sidewin_l` mirrored | 1,440 |
| `recordshop`'s `glass` (144 × 64) and `kanban` (176 × 32) at half width | about 4,600 |
| `coin_laundry`'s `glass` (96 × 64) and `sign` (160 × 32) at half width | about 3,500 |
| `recycling_station`'s `board` (80 × 96) at half height | about 2,300 |
| **Total** | **about 57,900** |

**East** (need −224): `overpass`'s `sign`, 128 × 56, at 128 × 48 (512).

**Canal, rows 0–1** (need −1,216): `canal_road_bridge` and `canal_footbridge` carry four 32 × 64
name plates each that are not the same images; the same four for both saves 5,760.

The shrine region needs no cuts: its plan is 135 KB of assets and 120 KB of ground in a 300 KB
budget, with 148 KB of the slots free besides.

## Notes for placing

- Asset names must be unique across the world's asset directories: `street_lamp` was both
  `assets/street_lamp/` and the shrine's `../shrine/assets/street_lamp.asset.json`; shrine town's
  is now `town_street_lamp` (`assets/town_street_lamp/`), and shrine town's pagoda collision
  `arch_pagoda_town_col` (the shrine's own is `arch_pagoda_col`).
- A placement belongs to the cell holding its origin, and its textures to that cell's region:
  the viaduct's spans in c4_2 are in the shrine's set, the great torii (c2_1) and the cemetery's
  gate (c4_1) in the town's.
- Entities' meshes are drawn in whichever region is loaded: keep them untextured (the coins are).
- `tools/shots.py` enters the camera's region, as the game does.
