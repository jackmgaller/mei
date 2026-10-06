# Shrine town: the two backdrops, authored and not yet applied

A sky and a far view for each texture region, on the Horizon Engine's tile plane
([WORLDKIT.md](../../../../../docs/WORLDKIT.md#backdrops), [PLANES.md](../../../../../docs/PLANES.md)):
no triangles and no GPU cycles. Today both regions carry the shrine world's backdrop (one flat
green `mountains` pattern of 1,024 × 48 in three colours, under one sky): the far view in the
grey box is a single dark ridge against the blue. These replace it. Proved on a scratch copy of
the world (`../preview_scratch.py`); nothing in the generators, the cells or the cart is changed.

| File | What |
|---|---|
| `town_backdrop.png` | 1,024 × 112, 15 colours (14 used): seen from the streets, region `town` |
| `shrine_backdrop.png` | 1,024 × 112, 15 colours: seen from the shrine's grounds, woods and mountain, region `shrine` |
| `backdrop.json` | Both regions' skies (6 stops, day and night), the silhouettes' `horizon`, and the night's exact colours |
| `draw_backdrop.py` | Draws the PNGs and `backdrop.json`. `--preview DIR` draws each panorama on its sky, day and night |
| `preview/` | `*_backdrop_day/night.png`: the panoramas on their skies (2.84 pixels a degree); `town_views.png` and `shrine_views.png`: the world drawn by the reader, before and after, day and night |

## What is in them

Column 0 is north and the picture runs east: 256 is east, 512 south, 768 west (checked from the
pagoda: looking at 195° the tower drawn at 198° is just right of the middle). The bottom 6 rows
stand under the horizon line (`"horizon": 6`).

- **The town's** (from the streets and the roofs): a thin mackerel sky of flat cream clouds; three
  ranges, a pale far one, a blue-green second, and a dark forested ridge with the autumn's red
  and gold crowns in its top rows, highest to the north (the shrine's mountain), low east and
  west; and the city to the south and south-east: three rows of blocks (far in haze, the middle
  ones with windows, the near ones with water tanks and stair houses), a red-and-white radio tower
  at 203°, a banded chimney at 131° and a crane at 244°, and two low clusters of danchi to the east
  and west.
- **The shrine's** (from the courtyard up to the stage): the same sky with more cloud; the same
  three ranges but higher, because from the mountain they are the horizon (the far range up to 93
  pixels, 26°, to the north; the town's, up to 61, 17°); and to the south the town as it looks from above: rows of low
  tiled roofs, apartment blocks behind them, the city behind those, the tower at 198°, two
  chimneys and the crane.
- **Night:** the sky's second set (a purple haze at the horizon under the city's light, dark blue
  above); the PNG's colours take the night's `surface.multiply` (`#4a5884`), and exact colours
  after that for what should look different: about a third of the windows glow (`#566680` →
  `#f2cf78`; the other glass colour, `#4e5e78`, stays dark), the clouds go a moonlit blue, the
  tower's bands brighten, the autumn crowns go dull.

Windows are 2 × 2 pixels on a 4-pixel grid in one of two glass colours that differ by a hair by
day, which is how only some are lit at night; the grid and the buildings' edges are on 4-pixel
steps so that the 8 × 8 tiles of wall repeat and the atlas stays small.

## The world's edits: `make_world.py`

`regions` is built there for both regions from the shrine world's `variants` and `backdrop`
(lines "regions = {r: {...} for r in L.REGIONS}"). Per region, from `backdrop.json`
(`BD = json.loads((ST / 'art/backdrop/backdrop.json').read_text())`, `BD[r]`):

```python
regions[r]['backdrop'] = {
    'elevations': BD[r]['elevations'], 'sky': BD[r]['sky'],
    'silhouette': {'image': f'art/backdrop/{r}_backdrop.png', 'horizon': BD[r]['horizon'], 'repeat': 1}}
regions[r]['variants']['night']['backdrop'] = BD[r]['variants']['night']   # a copy of the variants, per region
```

So the keys that change in `shrinetown.world.json`: `regions.town.backdrop`,
`regions.shrine.backdrop` (a new sky and an `image` silhouette in place of the `pattern`) and
`regions.town.variants.night.backdrop`, `regions.shrine.variants.night.backdrop` (new; 7 colours
each). The variants must be separate dicts per region (today both point at one copy of the shrine
world's). Image paths are relative to the world file; `art/backdrop/*.png` are its dependencies.
`../apply_patch.py` `patch_backdrop()` does the same to a loaded world.

The skies' stops are in degrees above the horizon: `[-8, 0, 3, 9, 26, 70]`; day `#7d8456` (the
plain below the horizon, olive) up through `#ecdcb4` (warm haze at 0°), `#d3dfdc`, `#9cc4e0`,
`#6a9fd2` to `#3a6cb0`; night `#141420`, `#5a4466`, `#352c58`, `#1c1e42`, `#0c1028`, `#04060f`.

## The cart: shown per region

The garden shows the backdrop of region 0 once, when the world opens (`wp_backdrop_show(0)` in
`ground.akr`), which was right while both regions had the same. With two, `wp_backdrop_show(k)`
must follow `wp_region_enter(k, 0)`. `../water/cart.patch` does it (`world_region_entered(k)` in
`ground.akr`, called from `world_load()` and `follow_region()`), together with the water's. It is
needed for the shrine's backdrop to appear in the shrine; without it the town's stays up.

## Limits and bytes

Checked against `tools/worldkit/backdrop.py` and `report.json` `regions.NAME.backdrop`:

| | Limit | Town | Shrine |
|---|---|---|---|
| width, height | 256, 512 or 1,024; at most 128 | 1,024 × 112 | 1,024 × 112 |
| colours | 15 in one 4-bit palette of the region's range | 14 | 15 |
| distinct 8 × 8 tiles (atlas, plane page 12, `0x460000`) | 1,024 (32,768 bytes) | 624 (20,480 bytes) | 717 (23,552 bytes) |
| map (`0x452000`) | 128 × 32 entries, 8,192 bytes | 8,192 | 8,192 |
| rate against the camera (`against_the_camera`) | 1.0 is exact | 0.784 | 0.784 |

The art is in the plane pages (`0x460000` on), not the regions' texture slots: the region texture
budgets are untouched. It is copied by `wp_region_enter()`: with the water, entering costs
about 34,700 (town) and 37,500 (shrine) cycles in the scratch world, against 11,500 now; the
backdrop's share is 20–24 KB of the copy (about 23,000 and 26,000 cycles more). The frame costs
what it did: `wp_backdrop_draw()` is about 5,500 cycles with a silhouette and its line table
(six stops now, not five). The palette is one more 4-bit palette in each region's range, as the
old silhouette's was.

The tiles are at 61 to 70 % of the page. To stay under 1,024, add detail in the city's rows
(regular grids repeat; random marks do not) rather than in the clouds or the ridge crowns, which
are the unique tiles.

Pictures: `preview/town_views.png` (the town from 24 m up, four ways) and `shrine_views.png` (the
precinct both ways, from the pagoda and from the stage); each row is before day, after day, before
night, after night.

## With the larger VRAM

The kit has one silhouette on BG1 and the page budget is not the limit (three of the four 4-bit
pages are free); the limits are the kit's. What I would add, in order:

- **A second plane for the clouds**, on BG2 or BG0 at its own scroll rate: a slow cloud deck in
  front of the ranges, drifting by `yaw` and `frame()`, which makes the far view move without the
  camera. It needs a `backdrop.clouds` entry in the kit (about 15 KB: 1,024 × 48 in one page).
- **An 8-bit silhouette** (the atlas is then two pages of 8-bit tiles; 255 colours): the ranges
  and the city shaded in real gradients instead of 3 flat tones and haze, and the clouds with
  soft edges. Also a kit feature; the region needs one 8-bit palette of 16 (it has 180 and 60 of
  its 4-bit ones to spare).
- **A moon and stars in the night variant only**, which needs the sky to take a second picture
  per variant (today a variant recolours the one silhouette).
- **A dusk variant**: the windows lit and the ridge in orange, with the sky's stops moved (a
  variant is its own sky already; it needs only its `backdrop` colours).
- **More height for the mountain's viewpoints**: 128 pixels tall instead of 112, so that the
  shrine's far range is not close to the top (it is at 93 of 105 above the horizon).
