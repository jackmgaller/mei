# The shrine town

A temple town of the 1990s wrapped round a shrine and its forested back mountain: a station
plaza and a covered shopping street up to a great torii, back alleys, a canal with machiya and a
sento, a park, a schoolyard, cemetery terraces and a railway viaduct round the south and east;
then the shrine (courtyard, terraced precinct, ridge and pagoda, the west woods' treetop walkway,
the sacred cedar's basin, the fox grove's torii tunnel, the back mountain's stage, falls and
chimney). 320 × 384 m, 30 cells of 64 m, five stars. The design, and every change the building
made to it, is [DESIGN.md](DESIGN.md); the plan in numbers is `layout.py`.

![Over the precinct, north](screenshots/overview_north.png) ![From the stage](screenshots/from_stage.png)

## What is built

**A grey box** (DESIGN.md, section 9, phase 1): every building and roof a box at its final
footprint, height and collision, in flat colours, the trees boxes, the rails paths, the stars
coins. It is the world `shrinetown`, the movement garden's third (`../world/garden.game.mochi`:
`worlds garden, shrine, shrinetown`), on the garden's controller and camera.

**Getting in.** Walk into the road works at the west end of the shrine's road (the shrine is
the garden's second world: the torii at the foot of the garden's shrine hill): the road goes on
into the shrine town, to the spawn in the station plaza. The shrine town's konbini door leads to
the garden; its road works at the front road's west end lead back to the shrine. A picture
without playing (the world is built with the garden cart):

```sh
make B=build-mine build-mine/carts/garden.mei
B=build-mine python3 carts/garden/shrinetown/tools/shots.py spawn               # screenshots/spawn.png
B=build-mine python3 carts/garden/shrinetown/tools/shots.py --at 160 1.6 20 0 3 here   # any view
```

**The ground.** One heightfield over the level at 2 m, from the three regions' heights files
(`shrinetown.heights.txt`), with cliffs for the canal (z 0–292), the school pool, the culvert,
the precinct's terrace and the temple's podium, the cemetery's nine terraces, the mountain's
flats (the ledge at 44, the ladder's shelf at 24, the pool's terrace at 16, the cave at 14, the
falls' top at 52) and the rims; water for the canal, the pool, the culvert, the pond and the
falls' pool; the trails, the stream, the stairs and the bridges as paths.

**The frame.** No jump or glide leaves the level: the north, east and west rims are rock walls
(8–14 m); south of the viaduct, east of the school and west of the machiya stand the backs of
the neighbours' buildings (22–28 m, placeholders until those levels exist); the front road's two
ends are road works behind 5.5 m hoardings; the viaduct's east end is closed by a wall on the
deck. The road's east end under the viaduct is the seamless edge to downtown (DESIGN.md 7.1), a
hoarding until downtown exists.

**Tests.** `carts/garden/tests/shrinetown_cases.akr`, scenarios 400–446, run by `check.sh`
(`make test-carts`), each on the default tuning:

| Scenario | What it proves |
|---|---|
| 400 | The spawn faces north; running north reaches the front road in 10 s (z 115.8) and the great torii at 10.9 s |
| 401 | From the spawn up the west station stair onto the platform (9.0) |
| 410–418 | Each glide G1–G9: jump, chained jump held through its apex, glide, land at its target (G5 on roof 1 at 21.3; G6 on roof 3; G7 on the cemetery's top terrace at x 263; G8 in the arcade at z 80) |
| 420 | The kick pair: four good kicks between the cedars (13.6 m), a fifth drifting east, onto the pagoda's roof 4 |
| 421 | The kick chimney: nine kicks from the terrace (16) to the cliff top (46) |
| 422 | The pagoda: from the lantern each roof's eave is 3.6 m up, five chained jumps and grabs, the dew basin, the finial pole, star 1 |
| 423 | The rope from the rope deck into the knot hole (8.9 s), the sill, down the hollow trunk to star 4 |
| 424 | Rope ladder A: the shelf (24) to the ledge (44), 6.1 s up, let go and catch the lip |
| 430 | All 111 coins: 84 on floors, 26 over rails, 1 at a pole's top, each taken there; the 8 red coins |
| 431–433 | The doors: konbini → garden, road works → shrine, the shrine's road works → shrine town |
| 440–446 | The views V1–V6 in the game, and turning round on the pagoda: no late frame |

```sh
make B=build-mine build-mine/carts/garden.mei
WORLDS=build-mine/cart-worlds/garden MEIC=build-mine/meic RUN=build-mine/mei-headless \
  carts/garden/tests/run.sh 422 2400 build-mine/s422        # one scenario; SHOT=1 SEQ=10 for frames
```

## What it costs

The World Checker, full (600 sampled views, depth mode, report), the whole level: peak **1,808
triangles, 410,083 draw CPU cycles, 584,668 GPU cycles** (budgets 4,000 / 600,000 / 1,600,000);
before the stand-ins were capped, 3,116 / 593,006 / 647,334. 44 hard failures, all collision
cracks of the kind the shrine has (gaps of 0.02–0.25 m where sweeps, bridge ends and steep
banks meet floors; two on seams). 6.96 MB pack, 165 entities, 2,141 meshes.

**Stand-ins** (DESIGN.md 12.1): capped at 90 a town cell, 140 the landmark cells and 60 the
rest, the ground on a 32 m grid: 28–140 triangles a cell, 2,204 in all (uncapped: 66–520,
7,918).

**The worst views** (`tools/views.py`, the checker at fixed cameras, every row present):

| View | Triangles | Draw CPU | GPU | Placements | Stand-ins | Uncapped: triangles / CPU |
|---|---|---|---|---|---|---|
| V1 arcade roof, north end, looking south | 1,585 | 370,877 | 495,810 | 91 | 0 | 1,585 / 372,176 |
| V2 pagoda top (47) looking south | 756 | 160,952 | 278,176 | 34 | 9 | 1,916 / 296,118 |
| V2 at the spec's 52, looking south | 673 | 147,966 | 259,354 | 29 | 9 | 1,863 / 284,666 |
| V3 stage looking south | 982 | 236,209 | 262,988 | 65 | 10 | 1,914 / 354,925 |
| V4 danchi roof looking north-east | 1,439 | 357,298 | 422,612 | 110 | 12 | 2,545 / 503,607 |
| V5 spawn looking north | 995 | 341,884 | 329,076 | 95 | 10 | 1,689 / 447,534 |
| V6 cemetery top looking west | 1,098 | 280,529 | 357,060 | 70 | 11 | 1,911 / 402,896 |
| Platform looking north | 1,522 | 471,523 | 383,869 | 129 | 10 | 2,431 / 605,417 |
| Deck 3 looking east | 1,522 | 333,973 | 369,218 | 95 | 13 | 2,740 / 491,810 |
| Shoulder top looking south-west (the whole level) | 1,385 | 323,632 | 377,227 | 99 | 12 | 2,328 / 455,149 |

The town's boxes carry the triangle budgets of the assets that will replace them (spec 8.2);
the shrine's and the mountain's are plain boxes, cheaper than the real buildings and trees, so
V2 and V3 will rise with real assets (the spec's estimates: V2 3,700–3,900, V3 3,500, with the
far pass at the caps). With the far ring of three, the spawn's view draws no row beyond row 3:
not the pagoda, not the stage (DESIGN.md 12.4).

## How it is made

Generated, nothing hand-edited. Each region's generator writes its cells, its grey-box recipes
and its world-level part; `make_world.py` joins the parts into the world:

```sh
python3 carts/garden/shrinetown/notes/gen_town.py                     # cells c*_0, c*_1; assets/greybox/town
python3 carts/garden/shrinetown/assets/greybox/core/gen_core.py         # cells c*_2, c*_3; assets/greybox/core
python3 carts/garden/shrinetown/assets/greybox/mountain/make_mountain.py   # cells c*_4, c*_5; assets/greybox/mountain
python3 carts/garden/shrinetown/make_world.py                         # shrinetown.world.json, shrinetown.heights.txt
python3 carts/garden/shrinetown/tools/draw.py                         # design/*.png from layout.py
B=build-mine python3 carts/garden/shrinetown/tools/views.py             # the worst views, as a table
```

All of them read `layout.py`. The world's assets are the town's folder and, through the World
Kit's `asset_dirs`, the core's, the mountain's and `assets/arch_pagoda` (the real pagoda's
climbing collision; its look is `../shrine/assets/arch_pagoda`, which the grey box draws in a flat
colour). `notes/` keeps each region's notes from the parallel build (their test worlds are gone:
the level is built only as `shrinetown`).

## Open

- The far ring from the spawn, the pagoda's height from the spawn and G5 (DESIGN.md 12.4).
- A ladder mode that holds the body on a ladder's front (rope ladder A, the fire escape's ladder
  E): a pole lets it go round into the wall.
- The 44 cracks (above), where sweeps, bridge ends and 2 m banks meet: the shrine accepted 44 of
  the same kind. Overlapping three sweeps into what they meet (the walkway stair, the north stair,
  ladder A's steps) closed an edge mismatch but only moved their cracks; the scenarios walk over
  all three.
- Phase 2 on: the stars, switches, the timer, the train, life, textures (DESIGN.md 9).
