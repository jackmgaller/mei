# The shrine's style sheet

How the shrine slice's assets look and are built. The world lead owns this file; asset workers
follow it. The level's design is [README.md](README.md); the tools are the Asset Kit
([docs/ASSETKIT.md](../../../docs/ASSETKIT.md)) and the World Kit
([docs/WORLDKIT.md](../../../docs/WORLDKIT.md)). The movement garden's sheet
([../world/STYLE.md](../world/STYLE.md)) is the older sibling: its rules on hidden faces, slivers
and collision floors hold here too.

## The place

An autumn shrine in Kyoto, late October, mid-afternoon: red maples, gold ginkgo, dark cedars,
mossy stone, vermilion wood, white plaster, dark roofs, raked pale gravel, a waterfall you hear
before you see. The player walks in off a city road, through a great torii, into a precinct on a
stone terrace, and out into a forest that climbs a mountain behind it. The look is a 1997 console
game at its best: low-polygon, strong silhouettes, colour doing most of the work, textures where
they pay (leaves, bark, roof tiles, wood grain, moss), and cutouts for foliage.

What it is for comes first: this is a platformer level. A surface the player uses (a roof to
climb, a platform, a stone to land on, a ledge to grab) must read as one at a glance.

## Scale and coordinates

- 1 unit = 1 metre; y is up. World x is east, world z is north. The level is 192 x 288 m.
- The player is 1.6 m tall, 0.3 m in radius, steps up 0.32 m. A door is 2.1 m.
- **An asset's origin is the centre of its footprint at its base (y = 0), its front (the
  entrance, the side a visitor sees first) faces -Z.** The world turns it with its yaw.
- Every asset has the footprint and height its brief gives (give or take 0.3 m for eaves, trims
  and railings); the layout is built to those numbers.

## What the player can do (carts/garden/tuning.akr)

Run 9.6 m/s. Jump apex 2.1 m, double jump 3.4 m, third jump about 4.4 m (running); a long jump
covers about 7 m. Grabs a ledge up to 1.75 m above where its hands reach (so a double jump and a
grab reach a ledge about 5 m above the ground). Wall kicks off any wall. A glider: about 8 m/s
forward, sinking 2 m/s (4 m forward for each metre down). Climbs poles. Collision floors steeper
than 30 degrees are slid down; steeper than 40 are walls.

So: **a step up the player must make without help is at most 4.5 m; a gap it must jump is at most
5 m edge to edge on the level, less when the landing is higher.** Walkable roofs and slopes are at
most 28 degrees in their collision (the render may be steeper by a few degrees).

## Lighting, palette and materials

- Every asset bakes `"lighting": {"mode": "vertical", "ambient": 0.5}` (foliage may use 0.55).
- **Every material is palette-backed (`"palette": true`) or textured.** The night variant
  multiplies every surface colour by `#4a5884`; emissive materials (`"class": "emissive"`) keep
  their colour at night. Emissives only for light: lantern lights (`lantern`), lit windows
  (`window`), signs (`sign`), the konbini's front (`shopfront`).
- At most 8 surface colours and 3 emissive ones per asset, preferably from this palette:

  | Use | Colours |
  |---|---|
  | Vermilion lacquer (torii, halls, gate, pagoda, bridge) | `#d8462a` body, `#a8321e` shade, `#ece4d2` white plaster, `#2c2a28` black lacquer |
  | Roofs | `#3e4248` dark tile, `#565c64` tile, `#6b4a3a` cypress bark, `#7a8a70` old copper |
  | Gold fittings | `#d8b048` |
  | Wood | `#8a6446` aged, `#5a3e2c` dark, `#b08a5e` new planks |
  | Stone | `#b4ae9e` light, `#8e887c` mid, `#6a665e` dark, `#7a8050` mossy |
  | Gravel and earth | `#d4ccb8` raked gravel, `#8a6a48` path, `#6a4a30` earth, `#9a5a2e` leaf litter |
  | Maple | `#c8301e` red, `#e0502a` scarlet, `#e8782a` orange, `#8a2418` deep |
  | Ginkgo | `#f0c030` gold, `#fad85a` pale, `#d89a20` amber |
  | Cedar and evergreens | `#24382a` deep, `#2e4a2e` dark, `#3c5a34` mid, `#4f6a3a` light |
  | Moss and grass | `#5f7a34` moss, `#6f8a3c` light moss, `#7c8a3c` dry grass |
  | Bark | `#4a3a2e` cedar (reddish brown `#6a4632`), `#5a4a3e` maple, `#8a8278` ginkgo |
  | Water | `#3f7393` pond, `#5a8aa0` shallow, `#dce8f0` foam and falls |
  | Bamboo | `#a8b860`, `#8a9a48`, `#c8c890` dry |
  | Street | `#4a4a50` asphalt, `#a8a69e` kerb, `#eceae4` white, `#c8c4b8` concrete, `#3a6ab0` blue, `#40a060` green |

- **Textures** ([ASSETKIT.md, Textures](../../../docs/ASSETKIT.md#textures)) are welcome where
  they make the thing: leaf clusters with cutouts, bark, roof tiles, planks, moss on stone. Keep
  them small (16 to 64 texels; 4-bit unless a texture truly needs 8), and texels about 2 to 8
  cm at the size the player sees them from. Sources: patterns, texel grids, or PNGs in
  `carts/garden/shrine/assets/art/` (authored art, committed; a script that drew one is kept
  beside it as `art/draw_NAME.py`). PNG textures need Pillow to build the cart.
- **Cutouts** (holes in a texture) need the depth buffer: such an asset's verification policy is
  `{"required": true, "depth": true, "perspective": true}`. Every asset in this world uses that
  policy anyway.
- **Scattered assets** (trees, undergrowth, leaf litter, boulders) are merged per chunk and may
  not use repeating textures: only `fit`, `disc`, or hand UVs inside 0 to 1.
- Texture VRAM per family, a ceiling: architecture 64 KB, foliage 64 KB, forest structures 48
  KB, water 32 KB, street 32 KB (`report.json`'s `textures.vram_bytes_allocated`).

## Collision

Every placed asset has a companion collision asset `NAME_col` (made by the asset's worker,
reviewed by the world lead), or `"self"` for a simple prop whose mesh is its own collision.
Collision is simple: boxes and slabs, roofs as a few planes. Floors where the player stands, walls
where it must be stopped, nothing else. No long thin floor triangles (more than about 10 : 1),
nothing thinner than 0.2 m. A roof the player is meant to climb has walkable collision (at most
28 degrees) even where the render is steeper. Tag nothing unless the brief asks for it.

## Budgets

The World Checker binds per view: at most 4,000 triangles, 600,000 draw CPU cycles (about 500
cycles a placement plus about 110 a triangle) and 1,600,000 GPU cycles. From the courtyard the
player sees the halls, the gate, the temple, the pagoda and the forest at once. Each brief gives an
asset's `"budget"` (triangles at level 0), which is a ceiling. **Anything bigger than a person
has `lod`**: a coarser level from about 30 to 60 m, a third of the triangles or fewer, and a
`cull` for small things (a lantern need not be drawn past 60 m).

## Naming and files

- Recipes in `carts/garden/shrine/assets/NAME.asset.json`; collision `NAME_col.asset.json`.
- Families: `arch_` (shrine buildings), `tree_`, `plant_` and `litter_` (foliage), `forest_`
  (forest structures), `water_` (pond and falls), `street_`.
- Node IDs name the part (`kasagi`, `east_post`, `eave_2`); materials name what they are
  (`lacquer`, `tile`, `plaster`, `leaves`).

## Done

An asset is done when:

- its recipe sets `"budget"`, `lod` where the size asks for it, and the verification policy
  above;
- `python3 tools/mei_assets.py verify` passes for it and for its `_col`;
- its preview contact sheet (`mei_assets.py preview ... --depth --perspective`) has been looked
  at by its worker and by the world lead: it reads as the thing from the player's height and from
  above, its colours are the palette's, and it looks like late October in Kyoto;
- and the world still builds with it.
