# Shrine town grey box: the town (rows z 0–128)

> **Joined (2026-10-05).** This region's notes from the parallel build. Its test world is gone: the
> level is built only as the world `shrinetown` (`../README.md`), and the generator writes no test
> world; the build commands below that name one are history. What the joining changed is in
> `../DESIGN.md`, section 12.

Region `town` of the grey box (spec section 9, phase 1): cells `c0_0`–`c4_1`, zones 3.1 station
and plaza, 3.2 shotengai, 3.3 alleys, 3.4 canal and machiya, 3.5 front road, 3.15 schoolyard, the
viaduct in these rows, the great torii (its origin is in `c2_1`) and the ground of the strip
z 118–128 north of the road.

## Files

| File | What |
|---|---|
| `notes/gen_town.py` | Writes everything below from the plan's `layout.py` (import, not a fork) |
| `cells/c{0..4}_{0,1}.cell.json` | 156 placements, 98 entities |
| `assets/greybox/town/gbt_*.asset.json` | 105 recipes: boxes and their `_col`, `gbt_coin`, `gbt_coin_red`, `gbt_star` |
| `parts/town.json` | World-level entries: paths (rails, the viaduct's sweeps), layer `ladder_e`, terrain materials and operations, collision surfaces, vantage points |
| `parts/town_heights.txt` | `layout.height()` on a 2 m grid over x 0–320, z 0–128 (the test world's field) |
| `test_town.world.json` | The throwaway world `town_gb` over these rows |
| `notes/town_checks.json` | Counts, glides and step checks computed by the generator |
| `notes/town_views.py` | The World Checker at the vantage points only, as a table |
| `notes/town_shots.py` | Pictures from the real reader into `screenshots/town_*.png` |

```sh
python3 carts/garden/shrinetown/notes/gen_town.py --layout PATH/layout.py   # or put layout.py beside test_town.world.json
make B=build-gbt build-gbt/meic build-gbt/mei-headless build-gbt/mei-asset-probe build-gbt/mei-scene-probe
python3 tools/mei_world.py build carts/garden/shrinetown/test_town.world.json -o build-gbt/worlds/town_gb \
    --compiler build-gbt/meic --runner build-gbt/mei-headless --probe build-gbt/mei-asset-probe
B=build-gbt python3 carts/garden/shrinetown/notes/town_views.py
B=build-gbt python3 carts/garden/shrinetown/notes/town_shots.py
```

`--plain` writes the boxes as plain boxes (10 triangles each) instead of at their budgets.

## How the boxes stand in

Every building is a box at its final footprint, height and collision (`_col`: a plain box). Its
render mesh carries the budget of the asset that replaces it (spec 8.2, assets.md): every face
cut into a grid of patches (edge counts follow edge lengths, so no T-junctions), with the same
levels and switch distances. So a view's placements and triangles are about what the real
assets will cost. Kinds: shop 250 / 70 from 20 / 20 from 50 (3-storey 300); alley house 120 /
30 from 16 / 12 from 40; machiya 200 / 50 / 14; heroes at their assets.md targets (danchi 600,
pachinko 450, koban 300, konbini 300, building 450, fire tower 600, sento 700, school 800, gym
500, overpass 600, arcade gate 300, arcade roof 400, station platform 900, concourse with gates
1,200, torii 160) / 200 from 24 / 40 from 60; viaduct span 120 / 40 from 48 / 12 from 100;
trees 90 / 30 / 12. Utility poles 30, culled at 110 like `street_utility_pole`.

Colours are flat, a hue per zone: warm plaster and grey tile (shotengai), brown-grey and dark
tile (alleys), dark wood (machiya), concrete (viaduct, danchi), vermilion (torii, arcade gates,
fire tower), the zone's ground painted (asphalt road, paving plaza, sando, clay sports ground,
gravel courtyard strip, grass, forest floor).

The viaduct's deck (9.0, 1.5 thick, 12 m) and its two parapets (to 10.2, 0.3 wide) are sweeps
along `layout.VIADUCT` and its offsets (paths `viaduct_deck`, `parapet_s`, `parapet_n_w`,
`parapet_n_e`; exact mitres, collision from the kit). Each ~16 m span is a placement: a pier
(8 × 1.6) and two girders under the deck, with `viaduct_span_16`'s budget. The span over the
front road has no pier. The parapets are also the grind rails.

## Measured views

World Checker in depth mode on `town_gb`, near pass 192, far ring 3, levels of detail at their
finest (worst case). Triangles are the GPU's count (front-facing, in the frustum, after
clipping): the number the 4,000 limit is checked against. Budgets: 4,000 / 600,000 / 1,600,000.

| View (spec 8.3) | Triangles | Draw CPU | GPU | Placements | Plain boxes: tris / CPU |
|---|---|---|---|---|---|
| V5 spawn (160, 26, 1.6) looking north (brief: "V1") | 757 | 290,609 | 301,766 | 94 | 451 / 184,596 |
| V5, pitched up 5° | 766 | 291,160 | 307,307 | 94 | 463 / 185,317 |
| V1 arcade roof north end (160, 94, 10) looking south | 1,587 | 366,077 | 466,388 | 96 | 623 / 235,580 |
| V4 danchi roof (78, 30, 20) looking north-east | 1,566 | 358,018 | 413,241 | 110 | 1,109 / 281,907 |
| Shotengai floor (160, 50) looking north | 882 | 223,790 | 391,533 | 54 | 352 / 143,468 |
| Shotengai floor (160, 100) looking south | 1,130 | 291,033 | 406,823 | 103 | 538 / 205,259 |
| Platform (160, 8, 10.5) looking north | 1,434 | 442,103 | 363,184 | 126 | 869 / 272,030 |
| Parapet over the canal looking east | 1,314 | 242,624 | 384,375 | 45 | 912 / 198,321 |
| Fire tower top looking east | 1,667 | 343,066 | 445,590 | 82 | 1,083 / 241,412 |
| Building roof looking west | 1,744 | 285,471 | 458,331 | 46 | 1,060 / 190,486 |
| School roof looking west | 1,250 | 248,455 | 363,642 | 53 | 904 / 174,413 |
| Front road looking east | 874 | 192,493 | 279,124 | 33 | 620 / 159,200 |
| Sento chimney looking east | 1,380 | 248,155 | 357,339 | 84 | 1,093 / 217,075 |

Placements include the ground's 16 m tiles (16 a cell) and the coins (entities, about 20 in a
view). The full check (600 sampled views, every kind): worst view 2,631 triangles, 514,409
draw CPU, 588,533 GPU (a follow camera over the station canopy at (149.7, 13, 2.5) looking
north-north-east over the plaza and the shotengai). No view over a budget, no wrong-order or
coverage pixel, no collision crack or edge mismatch: the checker passes. Its only reports are
four cells' stand-ins over the world's 400-triangle threshold (below).

What this says against the spec's estimates:

- **V5 is not the risk the spec feared, in the near pass.** The spec sums the assets' whole
  budgets (3,310 near); what reaches the GPU from the spawn is 757 triangles and 290,609 draw
  CPU cycles with every building at its budget. The arcade gate and the shops' facades turn
  half their faces away, and the levels from 20 m do the rest. CPU is the budget that sees
  every face (back faces cost about 48 cycles each): 48% of 600,000.
- **The far pass from the spawn is not measured here.** From row 0 the cells of rows 2–5 are
  the far ring, and this world has no rows 2–5. The spec's 720 assumes 60 a stand-in.
- **The town's own stand-ins are 4–6 times the spec's cap.** The kit's stand-ins at 128 m are
  182–540 triangles per town cell (c1_0 492, c2_0 540, c2_1 438, c4_1 428, c0_0 336), against
  90 in spec 8.2; with plain boxes they are still 130–213 faces. Most of it is the boxes' last
  level (10–20 triangles each, 20–40 placements a cell) and the 16 m ground with the canal's
  and pool's cliffs. From the pagoda (V2) or the stage (V3) about ten town cells are stand-ins,
  so the far pass there could be 2,000–4,000 triangles before culling, not 810–900. Spec 7.1's
  second, coarser stand-in level (or authored stand-ins: roof strips per block) is needed.
- Draw CPU is the tightest number in the town: 514,409 at worst, with no props and no life. The
  spec's props (150) and life (150–200) add about 40,000–60,000 cycles and 10–20 placements.

## Changes to layout.py (for the connector)

1. **Alley houses:** `range(44, 102, 11)` makes a sixth row at z 99–107.5, 3.5 m into the front
   road; the spec counts 24 houses, which rows 44–88 give exactly. The z 99 row is left out
   (`range(44, 99, 11)`).
2. **Machiya:** the loop's z 54 row runs into the sento (z 60–73) and its z 102 row into the
   road. Rows here: z 18, 30, 42 (to 52), 78, 90: ten machiya. A lane at z 52–60 runs from the
   footbridge west past the sento.
3. **The fire tower's kick pair:** "the house 3 m east" does not exist (the yard's nearest house
   is 9 m away). Added a storehouse (kura) at x 108–111, z 70–78, 8.0 m: 3 m east of the tower.
   From its roof two good kicks (6.8) and a grab reach the tower's top (7.2 up). **Not so, as
   built** (alpha review r08 #5): the real kura (x 106.3-109.3, walls to 7.6, roof 8.0) gives the
   pair four kicks from the ground (to about 9.8), and from its roof one kick off the tower reaches
   13.0 moving away from it, back onto the kura. The tower's lookout and roof are reached by its
   ladder (a front pole: let go at the top and push north, a ledge hang on the eave).
4. **The sento chimney** moves from (23.5, 68.5) to (30.5, 67.5), on the sento's east wall,
   over the boiler room (x 32–36, z 63–72, roof 5.0) its ladder (pole, 13.2) starts from. Red
   coin 7 moves with it. G3 from there: 71 m, arrives 3.8 over the park (0.6).
5. **Service-lane wires:** layout's x 118 and x 150 run over houses and over the west shops'
   roofs (9.5 m shops reach above an 8 m wire). Moved to the alley at x 112.75 and the west
   service lane at x 137.75 (z 44–104, poles at both ends).
6. **The konbini wire** starts at a pole at the roof's north-east corner (210, 33), not
   (210, 40): that is the spec's "corner pole" the roof reaches (route D).
7. **Red coin 6** sits mid-span at x 145 (layout's x 130 is a pole). **Red coin 8** sits on the
   north parapet's line (48, 10.2, 13.85), not on the deck's centre line.
8. **Station:** layout's solid box 136–184 × 2–14 × 12.8 became the deck (platform at 9.0), a
   concourse box under it (x 136–184, z 3–13, 5 m), the canopy (x 140–180, z 5–11, top 12.8) on
   four posts, and two stairs from the plaza at x 150–154 and 170–174 (z 32 → 14, 26.6°; the
   west stair's foot is 10 m from the spawn). The north parapet is open over x 146–178.
9. **Arcade gates** are frames: posts on the street's edges (x 154–155, 165–166), a beam 7.0–8.3
   over x 152–168, 2 m deep. **The great torii** is a frame: posts 1 × 1 at x 155–156 and
   164–165 (pole entities 12.6 at x 155.5 and 164.5), kasagi 153.5–166.5 at 13.0–13.8, nuki
   10.4–11.0 (G8 passes under it). Its base is the courtyard's 0.6, so its top beam is at 13.8
   absolute (★2's star at 14.7).
10. **Overpass:** layout's solid box (256–268 × 106–116, 7 m) would close the road. Built as a
    deck x 260–264, z 96–126 at 7.0 over the road, a ramp down west along z 96–100 (to x 246)
    and one down east along z 122–126 (to x 278), four piers.
11. **Awnings (bounce, 2.6):** only three 6.5 m shops lie outside the arcade (west z 44, east
    z 44 and 54): under the arcade a bounce (to 7.1) hits its underside (6.7). The other three
    awnings are on the service-lane side of shops under the arcade (west z 64 and 84, east
    z 74), each landing on its own roof.
12. **Fire escapes and stairs**, grey box: the building's is one 27° ramp up its east face
    (x 200–202.5, z 44 → 80); the school's one 26° ramp up its east face (x 288–290.5,
    z 48 → 86); the danchi's four flights of 4.7 m round the block (16–21°) with corner landings,
    the last beside the roof's south-west corner. Shortcut E's ladder hangs on the building's
    north face at x 199–200 in layer `ladder_e` with its pole (18.3).
13. **The culvert** (41) is a channel x 234–238 from z 96 (the school's ditch, south of the
    road) to z 128: bed −2.0, water −1.2 (0.8 m), under a road slab 0.15 thick (1.85 m of
    headroom). Layout has none.
14. **The canal** has vertical 1.2 m banks (a cliff), bed −1.2, water −0.4, a grille at its south
    end (z 0.4–0.8), a road bridge flush with the road (x 44–52, 0.5 thick) and a footbridge at
    z 59–61.5 (top 0.3). Neither bridge leaves headroom to wade under (1.6 m body): the canal
    is walked along, not under the road.
15. **The level's frame:** 3 m fences along z 0 (under the viaduct; open at the canal's grille),
    x 0 (behind the machiya) and x 320 south of the road; road-works barriers at x 0–1.5 on the
    road. The road's east end under the viaduct (the seamless edge, 7.1) is left open.

## Crossings with the core region (z = 128)

| Route or thing | Crossing (x, z, height) | Note |
|---|---|---|
| The axis (R_AXIS) | (160, 128, 0.6) | courtyard gravel from z 118 |
| West route (R_WEST) | (100.2, 128, 2.0) | woods floor; the walkway foot (102, 118) is left to the core with the rest of the walkway |
| East route (R_EAST) | (274, 128, 0.0) | cemetery lane; the overpass's east ramp ends at (278, 124) |
| Canal lane (R_CANAL) | (56, 128, 1.1) | |
| Canal | x 44–52 at z 128: bed −1.2, water −0.4, banks 1.2 | cliff op over the canal's rect; continue it to z 292 |
| Culvert channel | x 234–238 at z 128: bed −2.0, water −1.2 | must rise into the pond (bed −1.4, water 0); the pond's tip (water op circle (234, 140, 14), level 0) is in `parts/town.json` |
| Park | x 0–44 at z 128, 0.6 | grass |
| Viaduct (deck, spans, parapets) | ends at (306, 134), deck 9.0; parapet ends (311.7, 10.2, 132.6) and (300.3, 10.2, 135.4) | the last town span is (302, 118)–(306, 134) (its origin is in c4_1); the core adds (320, 146). Better: one path each for deck and parapets over the whole line |
| Lantern strings from the torii | (155, 13.8, 124) → (134, 11.6, 158); (165, 13.8, 124) → (186, 11.6, 158) | in `parts/town.json` (first point in c2_1); the core keeps STRINGS[2:] |
| G1 building roof → east side hall | (193, 102, 18.3) → (192, 126): 24 m, arrives 15.7 over 11.6 | |
| G2 danchi → canal lane | (78, 34, 18.8) → (56, 80): 51 m, arrives 9.5 | within the town |
| G3 sento chimney → park | (30.5, 67.5, 18.2) → (22, 138): 71 m, arrives 3.8 over 0.6 | |
| G4 fire tower → courtyard | (102, 77, 15.2) → (112, 140): 64 m, arrives 2.7 over 0.6 | |
| G9 school roof → cemetery | (273, 86, 18.9) → (276, 150): 64 m, arrives 6.3 over 3.6 | |

## Checks against the moves (tuning.akr, STYLE.md)

All from `notes/town_checks.json` (margins in metres):

- Awning 2.6 + bounce 4.5 = 7.1 over a 6.5 roof: +0.6. Shop roofs 6.5 → 9.5 by double jump: +0.4.
- Vending machine 1.9 → konbini 5.6 (double jump and grab, 5.15): +1.45. Platform 9.0 →
  canopy 12.8: +1.35. Deck → parapet 1.2: +1.0. Danchi roof → tank 2.0: +0.2.
- Ground → sento boiler room 5.0 (double jump and grab): +0.15, the tightest; boiler → sento
  roof 8.0: +0.4. (Storehouse 8.0 → fire tower 15.2 by kicks: no, as built; the ladder.)
- Alley roofs: neighbours 2.5 m apart at most, rising 2 m at most (6, 6.5, 7, 8): a running
  jump. Alley column x 126 → west shops: 4.5 m flat or up 3.5 (double jump). Shop rows: 1 m
  gaps. Arcade eave 0.5 m over the 6.5 m roofs.
- Stairs and ramps 16–27°, under the 28° walkable limit and the 30° slide angle.
- Not reachable without a glide or a route not in this region: the koban (5.9, 0.75 over a
  double jump and grab from the ground), the pachinko (9.1; from the danchi's second landing,
  3 m across and 0.3 down), the gym (9.0), the machiya rows across their 6 m street.

## For the connector

- **`carts/garden/attach.akr` holds 16 poles and 16 rails** (`MAX_POLES`, `MAX_RAILS`) for the
  whole world. The town alone has 21 poles (10 road, 4 lane, 2 konbini, fire tower, chimney,
  two torii posts, ladder E) and 9 rails (4 wires, 3 parapets, 2 lantern strings).
- The game schema lists `worlds garden, shrine`: `town_gb` builds with a `world_not_listed`
  warning. No door here (the konbini's and the station's are the connector's).
- Stars are coins (`star_2_torii`, `star_5_platform`, the `gbt_star` mesh) until a `star` type
  exists; the eight red coins are `red_coin`. 47 ordinary coins on spec 6.1's town lines.
- The terrain is one field per region here, which the kit cannot join (fields may not touch):
  sample `layout.height()` over the whole level and apply `parts/town.json`'s operations
  (paints, the canal's, pool's and culvert's cliffs and water) in that field.
- Camera zones: the five north-south alleys, four east-west alleys, the west service lane
  (`rail`) and the arcade (`follow`, 12 × 7 × 32).
- Not built (later phases or another region): the trains and the bus (movers), the walkway's
  foot, props and life, the downtown placeholder beyond the underpass, the school's boundary
  wall, the sports ground's goals.

## Problems

- The kit's stand-ins for town cells are far over the spec's 90 (above). Not fixable with
  boxes; it needs the coarser stand-in level or authored stand-ins.
- The far pass from the spawn can only be measured once the core and mountain cells exist.
- A glide or a jump off the south parapet leaves the level over z 0 (the fence under the deck
  is 3 m); spec 4.4 assumes the neighbour beyond. A parapet-height screen or the neighbour's
  cells are needed before playtests of ★5's race along the viaduct.
- The canal under the road bridge and the footbridge is too low to wade through (by design here;
  the spec's "wading the canal" loop runs north of the road).
