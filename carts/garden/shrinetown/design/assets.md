# Shrine town: asset list

Approximate, for splitting among asset workers. The level is in [spec.md](spec.md); zones are
its section 3 numbers. Size classes by footprint: **S** under about 2 m, **M** 2–8 m, **L**
larger. Triangle targets are level 0 and follow the guides (S 300, M 800, L 1,500) **capped by the
town's density limits** (spec 8.2): a shop is 250, an alley house 120, a machiya 200, so many
targets here are below the guide. Every asset bigger than a person has `lod` levels and a `_col`
companion, as STYLE.md requires; "L1" below is the first coarse level.

Footprints and triangle counts of the lab models were read with `python3 tools/mei_assets.py
inspect` on 2026-10-05.

## 1. Reused as they are (carts/garden/shrine/assets/)

No work beyond placement, except where noted.

| Recipe | Zone | Count here | Note |
|---|---|---|---|
| `arch_torii_great` | 3.6 | 1 | posts are poles |
| `arch_side_hall` | 3.6 | 2 | |
| `arch_corridor_hall` | 3.7 | 2 | |
| `arch_gate` | 3.7 | 1 | |
| `arch_temple` | 3.7 | 1 | |
| `arch_pagoda` | 3.8 | 1 | **collision reworked** (see 2) |
| `arch_wall_8`, `arch_wall_4`, `arch_wall_corner` | 3.7 | about 30, 8, 8 | merged per cell, levels added (spec V2) |
| `forest_platform` | 3.9 | 9 | six walkway decks, the crown deck, the rope deck, the walkway foot's landing |
| `forest_bridge_post` | 3.9, 3.12 | about 34 | rope bridges and the cedar rope's anchor |
| `forest_fox_shrine`, `forest_fox_statue` | 3.11 | 1, 4 | |
| `forest_fox_torii` | 3.11 | about 60 | the tunnel |
| `forest_stage_hall` | 3.12 | 1 | |
| `forest_stone_lantern` | 3.6, 3.7, 3.4 | about 24 | also along the canal lane |
| `forest_fallen_log`, `forest_hollow_log` | 3.9, 3.13 | 2, 1 | |
| `forest_boulder`, `forest_boulder_big` | woods, gorge | about 20, 8 | mossy boulders mark the wall's easy places |
| `tree_cedar`, `tree_cedar_giant` | forest | about 110, 12 | giant: 7 decks, crown, rope deck, kick pair (2), walkway foot |
| `tree_maple`, `tree_maple_small`, `tree_ginkgo` | forest, park, courtyard | about 70, 40, 41 | 6 ginkgo in the park |
| `tree_cedar_sacred` | — | 0 | replaced by the hollow version (3.2) |
| `plant_*` (5), `litter_*` (2) | forest | about 350, 100 | scattered, as built |
| `water_falls`, `water_stepping_stone_a/b/c`, `water_bob_log`, `water_lily_pad(_flower)`, `water_reeds`, `water_zigzag_bridge` | 3.13 | 1, 14, 2, 6, 40, 1 | the pond crossing, now optional |
| `fence_bamboo_8` | 3.3, 3.4 | about 12 | garden fences in the alleys and behind machiya |
| `street_konbini` | 3.1 | 1 | door back to the garden |
| `street_building` | 3.1–3.2 | 1 | turned 90°; gets the fire escape (3.1) |
| `street_utility_pole`, `street_lamp`, `street_guardrail`, `street_barrier`, `street_vending_machine` | town | about 18, 16, 24, 4, 12 | the cheap versions for bulk |
| `coin`, `coin_red` | everywhere | 100, 8 | |

## 2. Changed (existing recipes)

| Recipe | Change | Size | Who |
|---|---|---|---|
| `arch_pagoda_col` | each eave a walkable strip (≤ 28°), each storey wall a grab ledge 4.8 m above the eave below; finial as a pole entity | L | with batch O1 |
| `street_building` | a fire-escape stair on its north end (or the new `town_fire_escape` beside it) | L | with batch O3 |

## 3. Reused from the lab (examples/assets/lab/NAME), adapted

All lab models need: `lod` levels (only `sakagura` has any), a `_col` companion, the
verification policy of STYLE.md, the shrine palette where they clash, and most need their level
0 cut to the density limit (spec 8.2: heroes ≤ 600, L1 ≤ 200 from 24 m, L2 ≤ 40 from 60 m).
"Now" is the model's triangles today.

| Folder | Size | Zone | Now | Target L0 | Count | Note |
|---|---|---|---|---|---|---|
| `station_platform` | L (40 × 13) | 3.1 | 1,546 | 900 | 1 | on the viaduct deck |
| `ticket_gates` | M | 3.1 | 824 | 400 | 1 | in the concourse |
| `koban` | M | 3.1 | 823 | 300 | 1 | spawn view (V5) |
| `bus_stop` | M | 3.1 | 354 | 150 | 1 | |
| `pachinko_parlour` | L (9.2 × 7.4) | 3.1 | 876 | 450 | 1 | |
| `danchi` | L (16 × 13) | 3.1 | 1,064 | 600 | 1 | outside stair to the roof; red coin 4's tank |
| `newsstand` | M | 3.1 | 628 | 250 | 1 | |
| `phone_booth` | S | 3.1 | 795 | 150 | 2 | |
| `bike_rack` | M | 3.1, 3.2 | 334 | 150 | 4 | merged |
| `mamachari` | S | town | 471 | 120 | 10 | merged, culled at 40 m |
| `vending_machine` | S | 3.1 | 308 | 200 | 2 | hero pair at the plaza; bulk uses `street_vending_machine` |
| `arcade_gate` | L (12.7) | 3.2 | 1,064 | 300 | 2 | spawn view: the tightest cut |
| `street_lamp` (lab, shotengai lamp) | S | 3.2 | 442 | 100 | 12 | |
| `recordshop`, `tobacco_shop`, `ramen_shop` | M | 3.2, 3.5 | 656, 858, 1,700 | 450, 450, 600 | 1 each | the shotengai's hero shops, spaced 40 m apart |
| `coin_laundry` | M | 3.5 | 746 | 400 | 1 | front road |
| `dagashi_shop` | M | 3.3 | 668 | 400 | 1 | alley corner |
| `gachapon`, `crane_game` | S | 3.3, 3.2 | 282, 781 | 120, 200 | 2, 1 | |
| `jizo`, `hokora` | S | 3.3, 3.9 | 382, 300 | 150, 150 | 3, 2 | |
| `tanuki` | S | 3.2 | 408 | 150 | 2 | shop mascots |
| `postbox`, `firepost`, `traffic_mirror` | S | town | 306, 266, 296 | 100 each | 2, 3, 3 | |
| `recycling_station` | M | 3.3 | 436 | 200 | 1 | |
| `vegstand` | S | 3.4 | 354 | 150 | 1 | canal lane |
| `fire_tower` | M | 3.3 | 1,296 | 600 | 1 | ladder as a pole; red coin 2 |
| `sento_front` | L (22 × 13) | 3.4 | 1,417 | 700 | 1 | chimney 18.2 with its ladder; red coin 7 |
| `sakagura` | L (17.5 × 11.7) | 3.17 | 1,440 | 700 | 1 | has levels already |
| `watermill` | M | 3.16 | 1,320 | 500 | 1 | |
| `shishi_odoshi` | S | 3.4 | 446 | 150 | 1 | a machiya garden |
| `schoolhouse` | L (29 × 30) | 3.15 | 1,308 | 800 | 1 | outside fire stair added (or 4.1) |
| `overpass` | L (20 × 8.5) | 3.5 | 1,362 | 600 | 1 | over the front road |
| `bell_pavilion` | M | 3.7 | 830 | 400 | 1 | the precinct's bell |
| `kei_truck`, `delivery_van` | M | 3.3, 3.5 | 648, 396 | 300, 300 | 1, 1 | parked |
| `city_bus` | L (11.4) | 3.1 | 986 | 600 | 1 | a mover |
| `yatai`, `takoyaki_stall` | M | festival layer | 860, 922 | 400 | 4, 2 | night only, later |

39 lab models (and the two festival stalls later), about 75 placements.

## 4. New assets

### 4.1 Town buildings and structures

| # | Name | Size | Zone | Tris L0 | Count | Textures | Reuse |
|---|---|---|---|---|---|---|---|
| 1 | `town_shop_2f_a` (10 × 14 × 6.5, awning at 2.6) | M | 3.2, 3.5 | 250 | 6 | common shopfront sheet; signs by palette variant | — |
| 2 | `town_shop_2f_b` (open front, shutters) | M | 3.2, 3.5 | 250 | 5 | same sheet | — |
| 3 | `town_shop_2f_c` (corner shop, two faces) | M | 3.2, 3.5 | 250 | 3 | same sheet | — |
| 4 | `town_shop_3f` (9.5 m, flat roof with a sign frame) | M | 3.2 | 300 | 4 | same sheet | — |
| 5 | `town_alley_house_a` (9.5 × 8.5 × 6) | M | 3.3 | 120 | 8 | roof tile, plaster (common) | — |
| 6 | `town_alley_house_b` (6.5 / 7) | M | 3.3 | 120 | 8 | same | — |
| 7 | `town_alley_house_c` (8, with a drying platform) | M | 3.3 | 120 | 8 | same | — |
| 8 | `town_machiya_a` (10 × 14 × 7.5, lattice front) | L | 3.4 | 200 | 7 | wood lattice, roof tile | — |
| 9 | `town_machiya_b` (7.0, with a side garden wall) | L | 3.4 | 200 | 7 | same | — |
| 10 | `arcade_roof_16` (16 × 16, eaves 7, ridge 8.5, walkable) | L | 3.2 | 200 | 2 | steel and opaque panels, cutout ribs | — |
| 11 | `viaduct_span_16` (16 × 12, deck 9, parapet 10.2, a pier) | L | 3.1 | 120 | 22 | concrete (common) | — |
| 12 | `viaduct_curve_16` | L | 3.1, 3.15 | 160 | 4 | concrete | — |
| 13 | `viaduct_underpass` (the skew span over the road, abutments, side walls) | L | 3.5, 7.1 | 600 | 1 | common set only (the seam) | — |
| 14 | `station_concourse` (under the deck: hall front, two stairs) | L | 3.1 | 800 | 1 | common | `station_platform` sits on it |
| 15 | `signal_gantry` (sweeps roof riders off) | L | 3.1 | 150 | 2 | common | — |
| 16 | `school_gym` (24 × 30 × 9) | L | 3.15 | 500 | 1 | common | — |
| 17 | `school_pool` (26 × 18, fence, 0.9 m water) | L | 3.15 | 300 | 1 | water | — |
| 18 | `canal_road_bridge` (14 × 14) | L | 3.4 | 300 | 1 | stone, concrete | — |
| 19 | `canal_footbridge` (10 × 2.5) | L | 3.4 | 120 | 2 | stone | — |
| 20 | `canal_arched_bridge` (10 × 3, vermilion) | L | 3.16 | 200 | 1 | architecture | — |
| 21 | `canal_grille` (8 × 2) | M | 7.3 | 60 | 1 | common | — |
| 22 | `town_fire_escape` (stair and drop ladder, 2 states) | M | 3.1 | 250 | 1 | common | — |
| 23 | `cemetery_terrace_wall_12` (12 × 1 × 1.8) | L | 3.14 | 24 | 45 | stone | merged |
| 24 | `cemetery_grave_row` (8 graves, 8 × 2) | L | 3.14 | 160 | 40 | stone | merged, culled at 40 m |
| 25 | `cemetery_jizo_hall` (5 × 5 × 5) | M | 3.14 | 300 | 1 | architecture | — |
| 26 | `cemetery_gate` | M | 3.14 | 150 | 1 | stone, wood | — |
| 27 | `park_slide` (`slide` tag) | M | 3.16 | 150 | 1 | common | — |
| 28 | `park_jungle_gym` | M | 3.16 | 150 | 1 | common | — |
| 29 | `park_swings` | M | 3.16 | 100 | 1 | common | — |
| 30 | `park_toilet` | M | 3.16 | 200 | 1 | common | — |
| 31 | `festival_yagura` (6 × 6 × 8) | M | 3.16 | 300 | 1 | wood, cloth | — |
| 32 | `sports_tyre_steps` | M | 3.15 | 100 | 2 | common | — |
| 33 | `sports_climbing_frame` | M | 3.15 | 150 | 1 | common | — |
| 34 | `sports_goal` | M | 3.15 | 60 | 2 | common | — |
| 35 | `train_emu_car` (20 × 3 × 4, a mover) | L | 3.1 | 1,200 (L1 400) | 2 | train livery (common) | — |
| 36 | `tree_zelkova` | M | 3.5, 7.1 | 90 | 16 | foliage | built like `tree_maple` (`make_foliage.py`) |

### 4.2 Town small things

| # | Name | Size | Zone | Tris L0 | Count | Textures | Reuse |
|---|---|---|---|---|---|---|---|
| 37 | `town_awning_bounce` (`bounce` tag) | S | 3.2 | 40 | 8 | shopfront sheet | — |
| 38 | `town_kanban_set` (three standing and hanging signs) | S | 3.2, 3.3 | 60 | 20 | sign sheet | merged |
| 39 | `town_aircon_pipes` | S | town | 40 | 30 | common | merged |
| 40 | `town_potted_plants` | S | 3.3 | 60 | 20 | foliage | merged |
| 41 | `town_crates_bins` | S | 3.2, 3.3 | 50 | 16 | common | merged |
| 42 | `town_laundry_pole` | S | 3.3 | 30 | 10 | common | merged |
| 43 | `town_road_signs` | S | 3.5 | 40 | 12 | sign sheet | — |
| 44 | `town_utility_pole_transformer` | S | 3.5 | 60 | 4 | common | variant of `street_utility_pole` |
| 45 | `town_bench` | S | 3.1, 3.16 | 40 | 8 | common | — |
| 46 | `town_taxi_rank` | S | 3.1 | 60 | 1 | common | — |
| 47 | `cemetery_sotoba_rack` | S | 3.14 | 40 | 10 | wood | merged |
| 48 | `tree_bamboo_tall` (12 m, cards) | S | 3.17 | 12 | about 400 | foliage | scattered; `plant_bamboo` is 2.5 m |

### 4.3 Shrine and forest

| # | Name | Size | Zone | Tris L0 | Count | Textures | Reuse |
|---|---|---|---|---|---|---|---|
| 49 | `arch_wall_gate` (5 m opening, small roof; barred variant by a layer) | M | 3.7 | 250 | 3 | architecture | matches `arch_wall_8` |
| 50 | `arch_chozuya` (water pavilion) | M | 3.6 | 300 | 1 | architecture | — |
| 51 | `arch_shrine_office` | L (8 × 6) | 3.6 | 400 | 1 | architecture | — |
| 52 | `tree_cedar_sacred_hollow` (shaft, knot hole, bark lip, root chamber) | L | 3.10 | 600 | 1 | foliage, bark | from `tree_cedar_sacred` |
| 53 | `forest_dead_cedar` (standing and fallen, two layers) | L | 3.14 | 120 | 1 | bark | from `tree_cedar` |
| 54 | `forest_falls_cave` (rock arch and cave behind the falls) | L | 3.13 | 300 | 1 | rock | — |
| 55 | `forest_rope_ladder` (20 m, rolled and down) | M | 3.12 | 80 | 1 | rope, wood | — |
| 56 | `arch_wall_gate_bar` (the north gate's bar) | S | 3.7 | 30 | 1 | wood | — |
| 57 | `arch_komainu` | S | 3.6 | 120 | 2 | stone | — |
| 58 | `arch_omikuji_rack` | S | 3.6 | 60 | 1 | wood, paper | — |
| 59 | `arch_ema_board` | S | 3.6 | 60 | 1 | wood | — |
| 60 | `forest_root_curtain` (the root door, layer D) | S | 3.10 | 60 | 1 | bark cutout, glow | — |
| 61 | `forest_stage_bell` (bell and rope) | S | 3.12 | 120 | 1 | bronze, rope | — |
| 62 | `forest_omamori` (★5's switch) | S | 3.12 | 40 | 1 | cloth | — |
| 63 | `forest_shide_rope` (streamers on the cedar rope) | S | 3.9 | 60 | 1 | paper | — |

### 4.4 Life

| # | Name | Size | Zone | Tris L0 | Count | Textures | Reuse |
|---|---|---|---|---|---|---|---|
| 64 | `life_pedestrian_a/b/c` (three in one recipe family) | S | town | 80 | 8 | common people sheet | — |
| 65 | `life_schoolchild` | S | 3.15 | 80 | 4 | same | — |
| 66 | `life_priest` (two poses) | S | 3.6 | 80 | 1 | same | — |
| 67 | `life_cyclist` | S | 3.5 | 120 | 1 | same | rides a `mamachari` copy |
| 68 | `life_cat` (asleep, sitting) | S | town | 60 | 3 | animals sheet | — |
| 69 | `life_crow` (perched, flying) | S | wires | 30 | 6 | animals | — |
| 70 | `life_pigeon` | S | 3.1 | 20 | 8 | animals | merged flock |
| 71 | `life_koi` | S | 3.13 | 30 | 5 | animals | — |
| 72 | `life_heron` | S | 3.4 | 60 | 1 | animals | — |
| 73 | `life_white_fox` | S | 3.11 | 80 | 1 | animals | — |

## 5. Totals

| | S | M | L | All |
|---|---|---|---|---|
| New recipes (section 4; `life_pedestrian_a/b/c` counted as three) | 32 | 23 | 20 | **75** |
| Their level-0 triangles, one copy each | 1,882 | 4,100 | 6,654 | 12,636 |
| Lab models adapted (section 3, without the festival stalls) | 14 | 16 | 9 | **39** |
| Shrine recipes changed (section 2) | | | 2 | 2 |
| Shrine recipes reused as they are (section 1) | | | | about 50 |

- New S (32): #37–#48, #56–#63, #64 (three), #65–#73.
- New M (23): #1–#7, #21, #22, #25–#34, #36, #49, #50, #55.
- New L (20): #8–#20, #23, #24, #35, #51–#54.
- Adapted lab S (14): `phone_booth`, `mamachari`, `vending_machine`, `street_lamp`, `gachapon`,
  `crane_game`, `jizo`, `hokora`, `tanuki`, `postbox`, `firepost`, `traffic_mirror`,
  `vegstand`, `shishi_odoshi`.
- Adapted lab M (16): `ticket_gates`, `koban`, `bus_stop`, `newsstand`, `bike_rack`,
  `recordshop`, `tobacco_shop`, `ramen_shop`, `coin_laundry`, `dagashi_shop`,
  `recycling_station`, `fire_tower`, `watermill`, `bell_pavilion`, `kei_truck`, `delivery_van`.
- Adapted lab L (9): `station_platform`, `pachinko_parlour`, `danchi`, `arcade_gate`,
  `sento_front`, `sakagura`, `schoolhouse`, `overpass`, `city_bus`.
- Later (festival layer): `yatai`, `takoyaki_stall`, a lantern-string lantern (S).

Every new asset with collision gets its `_col` companion from the same worker; merged props and
life use `"self"` or none.

## 6. Suggested batching

Three assets per agent. Large and medium to Opus, small to Sonnet (the team rule). Batches keep
a family together so one agent owns a texture sheet; the sheet's owner is named.

### Opus: new L and M (15 agents)

| Batch | Assets | Owns |
|---|---|---|
| O1 | `town_shop_2f_a`, `town_shop_2f_b`, `town_shop_2f_c` | the common shopfront sheet |
| O2 | `town_shop_3f`, `arcade_roof_16`, `town_awning_bounce` (S, rides with its shops) | |
| O3 | `town_alley_house_a`, `_b`, `_c` | roof tile and plaster in the common set |
| O4 | `town_machiya_a`, `town_machiya_b`, `canal_road_bridge` | wood lattice |
| O5 | `viaduct_span_16`, `viaduct_curve_16`, `viaduct_underpass` | concrete (common) |
| O6 | `station_concourse`, `signal_gantry`, `train_emu_car` | train livery |
| O7 | `school_gym`, `school_pool`, `town_fire_escape` | |
| O8 | `canal_footbridge`, `canal_arched_bridge`, `canal_grille` | |
| O9 | `cemetery_terrace_wall_12`, `cemetery_grave_row`, `cemetery_jizo_hall` | stone |
| O10 | `cemetery_gate`, `festival_yagura`, `park_toilet` | |
| O11 | `park_slide`, `park_jungle_gym`, `park_swings` | |
| O12 | `sports_tyre_steps`, `sports_climbing_frame`, `sports_goal` | |
| O13 | `tree_cedar_sacred_hollow`, `forest_dead_cedar`, `forest_falls_cave` | |
| O14 | `arch_wall_gate`, `arch_chozuya`, `arch_shrine_office` | (architecture sheet, existing) |
| O15 | `forest_rope_ladder`, `tree_zelkova`, `arch_pagoda_col` rework | |

### Opus: lab adaptations, L and M (8 agents)

| Batch | Assets |
|---|---|
| OL1 | `station_platform`, `ticket_gates`, `arcade_gate` |
| OL2 | `danchi`, `pachinko_parlour`, `koban` |
| OL3 | `sento_front`, `sakagura`, `watermill` |
| OL4 | `schoolhouse`, `overpass`, `city_bus` |
| OL5 | `recordshop`, `tobacco_shop`, `ramen_shop` |
| OL6 | `coin_laundry`, `dagashi_shop`, `fire_tower` |
| OL7 | `bus_stop`, `newsstand`, `bike_rack` |
| OL8 | `bell_pavilion`, `recycling_station`, `kei_truck` + `delivery_van` (two small vehicles as one) |

### Sonnet: S (15 agents)

| Batch | Assets |
|---|---|
| S1 | `town_kanban_set`, `town_road_signs`, `town_taxi_rank` (the sign sheet) |
| S2 | `town_aircon_pipes`, `town_crates_bins`, `town_laundry_pole` |
| S3 | `town_potted_plants`, `town_bench`, `town_utility_pole_transformer` |
| S4 | `cemetery_sotoba_rack`, `tree_bamboo_tall`, `forest_shide_rope` |
| S5 | `arch_komainu`, `arch_omikuji_rack`, `arch_ema_board` |
| S6 | `arch_wall_gate_bar`, `forest_root_curtain`, `forest_stage_bell` |
| S7 | `forest_omamori`, `life_white_fox`, `life_heron` |
| S8 | `life_pedestrian_a`, `_b`, `_c` (the people sheet) |
| S9 | `life_schoolchild`, `life_priest`, `life_cyclist` |
| S10 | `life_cat`, `life_crow`, `life_pigeon` (the animals sheet) |
| S11 | `life_koi` + lab `jizo`, `hokora` (adapt) |
| S12 | lab `phone_booth`, `vending_machine`, `postbox` (adapt) |
| S13 | lab `mamachari`, `gachapon`, `crane_game` (adapt) |
| S14 | lab `street_lamp`, `firepost`, `traffic_mirror` (adapt) |
| S15 | lab `tanuki`, `vegstand`, `shishi_odoshi` (adapt) |

Order: O1–O5 and OL1–OL2 first (they carry the town's budget and the spawn view), then the
shrine and forest batches (O13–O15), then the rest; life last. The grey box (spec 9, phase 1)
comes before all of them, so every asset replaces a box of the same footprint, height and
collision.
