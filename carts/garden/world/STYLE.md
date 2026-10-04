# The garden's style sheet

How the movement garden's assets look and are built. The world lead owns this file; asset workers
follow it. The contract between the teams is [../README.md](../README.md); the tools are the Asset
Kit ([docs/ASSETKIT.md](../../../docs/ASSETKIT.md)) and the World Kit
([docs/WORLDKIT.md](../../../docs/WORLDKIT.md), [docs/WORLDCHECKER.md](../../../docs/WORLDCHECKER.md)).

## The place

One city block of a 1990s Japanese city, about 1994: low concrete flats with balconies and an
outside fire escape, a tiled bathhouse with a tall chimney, a glass-and-panel office tower with a
water tank and air-conditioning units on its roof, a building site with a steel frame and a tower
crane, an elevated railway on concrete pillars with a small station, a convenience store under a
striped awning, utility poles and their wires, a shrine on a stone hill with a vermilion torii and
a five-tier pagoda, and a small park. The look is a PlayStation game: flat-coloured, low-polygon,
readable shapes, strong silhouettes, few details placed where the player's eye is. No textures yet
(the Asset Kit has none): colour, shape and the baked shading do all the work.

What it is for comes first: the garden is where the movement is tuned. A surface the player can
use (a wall to kick, a pole, a ledge, a bounce or slide surface) must read clearly as one.

## Scale and coordinates

- 1 unit = 1 metre; y is up. The player is 1.6 m tall with a 0.3 m radius; a step up is 0.32 m.
- World x is east, world z is north (`z = 128 - y` of `layout.py`'s map).
- A storey is about 3.5 m (offices 4 m). A door is 2.1 m, a window 1.2-1.5 m tall.
- Every asset keeps the **origin, footprint and height of its grey box** (the tables in the
  briefs, from the recipes in `assets/`): the same local bounds, give or take 0.3 m for trims,
  eaves, signs and railings that stick out. Things the player stands on or kicks off do not move.

## Lighting, palette and materials

- Every placed asset bakes `"lighting": {"mode": "vertical", "ambient": 0.5}`: tops lit, walls in
  the middle, undersides dark, the same at any yaw. Walls are told apart by colour, not light.
- **Every material is palette-backed** (`"palette": true`), so the night variant (the world
  multiplies surface entries by `#4a5884`) darkens it. A material that is not palette-backed stays
  at its day colour at night: do not use any.
- **Emissive** (`"class": "emissive"`) only for light sources: lit windows, signs, lanterns, lamp
  heads, the vending machine's front. They keep their colour at night. Name them by what they
  are, with these material names, so the world can give them a night colour by name:
  `window` (day `#8fa6b8`, a pale sky reflection), `sign`, `lantern`, `lamp`, `vending_front`.
- Each asset uses at most **8 surface colours and 3 emissive ones**, preferably from the shared
  palette below, so the region's palettes stay small. Surface materials of the same colour share
  an entry; that is fine.
- Shared palette (day colours). Pick from these first; a near miss of one of them should be it.

  | Use | Colours |
  |---|---|
  | Concrete, from light to dark | `#c8c4b8` `#a8a69e` `#8c8a84` `#6c6862` |
  | Tile and plaster (flats, bathhouse) | `#d8ccb0` `#cdb89c` `#c8c0b0` |
  | Roofs and metal | `#7e8790` `#5e6a74` `#4e5660` `#3c4048` |
  | Glass and panels (office) | `#9fb2c4` `#7d8fa4` `#5c6c80` |
  | Rust, steel, safety | `#c0703a` `#e8c020` `#d04030` |
  | Wood | `#a07850` `#6b4a3a` |
  | Shrine | vermilion `#d04a2a`, white plaster `#e8e0d0`, dark roof `#4e5660` |
  | Greens | `#86a868` `#6f9a58` `#4f8a40` |
  | Train line | car body `#7cc060` (the line's colour), roof `#c8ccc8` |
  | Store | white `#eceae4`, stripe blue `#3a6ab0`, stripe green `#40a060` |

- **Gameplay colours** are reserved: bounce surfaces are `#f04880` (pink-red), slide surfaces
  `#f0c838` (yellow). Nothing else uses them. Poles the player can climb are a warm colour
  (`#d8a040` scaffold, `#6c6862` utility poles with a lighter band at the top).

## Surface tags

Tags matter only on **collision** assets, which the world lead owns. Render materials carry no
tag except `bounce` and `slide` on the faces that are those surfaces, so the tag shows up in the
manifest where it is meant. The surface bytes are the contract's: `bounce` 1, `slide` 2, everything
else 0.

## Collision

Every placement has a companion collision asset `NAME_col` (the grey box's simple shape, owned by
the world lead) or `"self"` for the ground. Workers do not edit `*_col` recipes. If the detailed
shape needs a different collision (a new ledge, a railing to stop the player), say so in the
report; the world lead changes it. Collision floors are kept free of long thin triangles (more
than about 10 : 1): the World Checker's edge test misreads them.

## Drawing order: what the World Checker taught the grey box

Mei has no depth buffer: faces sort by their average depth into 1,024 buckets. The grey box went
from 16,044 wrong-order pixels in its worst view to 1,991 by following these rules; detailed
assets must keep to them, and the Asset Checker (zero wrong pixels) enforces most of them.

1. **No hidden faces.** Leave out every face nothing can see: bottoms of things on the ground
   (`box` `"open": ["bottom"]`), the top of a body under a roof, the faces of two parts pressed
   together. A hidden face still sorts and can be drawn over what covers it.
2. **Nothing under what stands on you.** Where another placement stands on an asset (the water
   tank and AC units on the office roof, the pagoda and the hall on the shrine hill, the ramps on
   the car park's decks), the asset has no face under it: cut the top around the footprint.
3. **No parts through parts.** Posts do not pass through beams; a beam sits between posts or on
   top of them. Use one `mesh` with shared edges for bands of colour on one surface (windows,
   signs, stripes are bands of the wall, as `face_materials`, never panels in front of it).
4. **Split big faces near small things.** A wall more than about 8 m across with something in
   front of it (a fire escape, an awning, a stall) is split into panels or bands where the small
   thing meets it. Large roofs that things stand on are tiled at about 8 m, edges meeting edge to
   edge (no T-junctions).
5. **Gaps, not slivers.** Two parts closer than 0.05 m sort unpredictably; touch exactly or keep
   0.1 m apart.

## Budgets

Measured on the grey box (`verification/world-check.json`, 600 views): drawing costs about 2,500
CPU cycles per placement drawn plus about 160 per triangle on screen, and from most places the
whole 128 m block is in view. The World Checker's draw limit is 300,000 cycles (60% of the CPU),
so the **whole block may hold about 5,500 triangles** with every layer on: about **1,400 per
cell**, against the kit's placeholder of 1,600. Each asset's recipe sets `"budget"` to its row
below, which is a ceiling, not a target.

| Family | Asset (triangles) |
|---|---|
| Residential | apartments 260, fire escape 200, bathhouse 200, car park 400 |
| Office | tower 260, water tank 60, AC unit 24 (placed 4 times), gondola 60 |
| Construction | steel frame 400, scaffold pole 16 (x4), crane 220, hook 48 |
| Train | viaduct 120 per half, pillar 16 (x8), station 220, station stairs 140, overpass 60 per half, overpass stairs 100 each, train car 140 |
| Street | utility pole 24 (x5), konbini 200, awning 40, vending machine 24 (x2), street lamp 24 (x4) |
| Shrine | torii 80, pagoda 300, hall 200, stall 60 (x4, festival layer) |
| Park | kick wall 16 (x4), mounds 24 each, slide 100, trampoline 24, tree 40 (x4), bench 24 (x2) |
| Ground (world lead) | ground 80 per cell, shrine hill 200, shrine steps 140 |

Repeated props (poles, lamps, AC units, trees) are cheap and may later be merged (`"merge":
true`) to save the per-placement cost.

## Naming

- Assets are `family_thing`: `residential_`, `office_`, `construction_`, `train_`, `street_`,
  `shrine_`, `park_`, `ground_`. Collision companions are `family_thing_col`.
- Node IDs name the part (`west_wall`, `balcony_2`, `jib`); materials name what they are
  (`concrete`, `glass`, `window`, `rust`).

## Done

An asset is done when:

- its recipe in `carts/garden/world/assets/NAME.asset.json` keeps the grey box's name, origin,
  footprint and height, and sets `"budget"` (its row above) and a required `"verification"`
  policy (`{"required": true}`, the default 144 views);
- `python3 tools/mei_assets.py verify` passes (zero wrong pixels, no cycles, no geometry errors);
- its preview contact sheet (`mei_assets.py preview`) has been looked at: it reads as the thing
  from the player's height and from above, its gameplay surfaces read, its colours are the
  palette's, and it is shaded with the vertical bake;
- and the world still builds with it (the world lead checks; workers may too).
