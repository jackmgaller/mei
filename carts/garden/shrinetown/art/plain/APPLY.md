# Shrine town: the far plain, authored and not yet applied

From the high points (the pagoda, the stage, the walkway crown, the building roof) the world past
the level's drawn edge was the backdrop's flat colour under the horizon: cream by day, purple at
night, up to the skyline, with a hard line where the far ring's ground stops at 192–256 m
(review r18, findings 1 and 2). This fills it with ground: a painted plain on the Horizon Engine's
affine plane BG2, a Mode 7 floor at the streets' height ([PLANES.md](../../../../../docs/PLANES.md)),
fogged per screen line to match the GPU's fog. It shows only in the holes the polygons leave, so
inside the level nothing changes; past the edge the drawn ground runs on into the plain at the same
fog. No triangles, no GPU cycles, no texture slots, no change to the world recipe.

Proved by drawing the built world with the real reader (`preview_plain.py`), and by the garden's
scenarios with `cart.patch` applied (below). Nothing in the cart is changed on this branch.

| File | What |
|---|---|
| `draw_plain.py` | Paints the plain and writes the four files below (seeded: rerun only to change it). `--preview DIR`: the painting as rebuilt from the tiles, and a map of its zones |
| `plain.png` | The painting: 1,024 × 1,024 texels of 2 m (2,048 m square, wrapping), north up, 15 colours |
| `plain_atlas.bin` | Its 8 × 8 tiles: 13,884 distinct, reduced to 1,023 by k-means (each cluster drawn by its member nearest the centre): one 4-bit plane page, 32,768 bytes |
| `plain_map.bin` | The 128 × 128 map of tile numbers, 32,768 bytes |
| `plain_data.akr` | Generated: the two embeds, the colours by day and by night, where world (0, 0) is on the map |
| `plain.akr` | The runtime: `plain_show()`, `plain_variant(v)`, `plain_draw(eye, pitch)`, `plain_hide()` |
| `cart.patch` | The garden cart's five lines (`ground/ground.akr`, `game.akr`) |
| `preview_plain.py` | Draws the views before and after, day and night, and prints the CPU cost |
| `preview/` | `NAME.png`: before (left) and after (right), day (top) and night (bottom), for `pagoda_s`, `pagoda_w`, `stage_s`, `stage_se`, `crown_s`, `roof_w` and `road_w` (street level); `costs.txt` |

## What is on it

World metres; the level is x 0–320, z 0–384, and sits at the map's centre (texel (432, 416) is
world (0, 0), 0.5 texels a metre). The palette is the level's: the road's asphalt, its concrete,
kawara in two slopes, teal and rust tin, rice stubble and straw, ploughed earth, a green crop,
cedar, maple, ginkgo gold, water and gravel. Night is the day's colours times the world's night
multiply (`#4a5884`), as the level's palettes are.

- **The town** carried on south of the station (an oval to about z −500) and east and west along
  the front road: blocks between lanes and streets, two rows of lots a block, each a roof (kawara
  with a lit and a shaded slope, tin, a flat concrete roof) beside a strip of garden, a yard or a
  tree; a few larger flat-roofed blocks. The front road (z 113) and the axis south of the station
  go on as asphalt.
- **Fields** east, west and further south: harvested paddies in 32 × 96 m parcels with levees
  (stubble, ploughed earth, a green crop in rows, rice on drying racks, greenhouses, gathered
  straw), gravel farm roads with a channel beside them, and homesteads, two or three roofs in a
  ring of cedar and maple.
- **The railway** west from the station (z 8) and east from the viaduct (z 143), on ballast.
- **A river** 260 m west, water in gravel banks between grass levees with a road on each crest,
  bridged by the front road, the railway and a ring road.
- **Forested hills** to the north from about z 380 (and a little lower far east and west):
  cedar with clumps of maple and ginkgo and a gold-and-green edge, as the backdrop's ridges are.

The seams of the wrapping map are 830–860 m from the level, where the plain is all but fully fogged.

## How it is drawn

- **Layers.** BG2 at the default priorities: behind every polygon and behind the silhouette (BG1),
  in front of the backdrop's sky. The silhouette's rows below the horizon stand on the plain.
- **The floor.** `plane_floor()` each frame from the camera `wp_draw()` leaves set (relative to
  `wp_view_origin()`, which `plain_draw` adds back into the offsets): every line down to depth
  3,000 below the horizon, the plane at y 0 (`plain_y`, the town's streets). The mountain is
  higher than that: from the stage the plain shows past the ridge as a valley, from below it does
  not show at all.
- **Fog per line.** The GPU fogs by view depth, linear from near to far; on the plane a screen line
  is one depth, so 16 copies of the palette, each 1/15 nearer the fog colour, and a line table on
  BG2's mode word (channel 3, at `LT_FREE`) pick one a line. The fog colour and range are read back
  from `GPU_FOG` and `GPU_FOG_RANGE`: the plain follows whatever fog `world_shrinetown_fog()` sets,
  so the look branch's new fog needs nothing here. Up to the depth where the fog reaches
  `plain_cap` (0.85: 328 m by day, 189 m at night with today's fog) the plain is fogged exactly as
  the polygons; past it the rest of the fog is spread over `plain_tail` (900) more metres, so the
  far fields stay faintly there up to the horizon instead of ending in a flat band of fog colour.
  `plain_cap = 1.0` gives the GPU's fog exactly (full at 380 m by day): then a band of plain fog
  colour some 10–25 lines high is left under the silhouette from the pagoda and the stage.
  Where the far ring ends beyond the cap's depth (at night, 192–256 m) the plain is up to 15% less
  fogged than the ground it meets; in the night shots this does not show.
- **Low eyes.** Below `plain_min_eye` (10 m above the plain) it is not drawn (BG2's window is
  empty): from the streets it would show only at the horizon, in full fog (`road_w.png`), and the
  floor's lines would cost 16,500 cycles a frame for nothing.

## Costs

Measured with `preview_plain.py` on `build-plain` (`preview/costs.txt`), CPU cycles:

| | Cycles |
|---|---|
| `plain_draw()` a frame, eye 10 m or more up (the eight high views) | 17,900–20,200 (about 2% of the 1,000,000 a tick; 3% of the World Checker's 600,000 draw budget) |
| `plain_draw()` a frame, eye under 10 m | about 100 |
| the fog palettes, on the first frame after `plain_variant()` or a fog change | about 8,600 more |
| `plain_show()`, once when the shrine town opens (two 32 KB copies) | 61,700 |

Most of `plain_draw()` is `plane_floor()`, about 100 cycles a line below the horizon (the
standard library's figure; the fog table is about 1,500). The worst views in the review were
near the draw budget (`crown_e` 532,028 → 550,393, `pagoda_w` 516,831 → 535,592 in this
harness); a `plane_floor()` that stopped at a nearest depth (nothing nearer than about 80 m is
ever a hole) would save a quarter of it, but needs a change to `stdlib/planes.akr`.

- **GPU:** none. No triangles; the plane chip composes at vsync. The emulator spends about
  0.5 ms a frame on the host for BG2 (PLANES.md's bench: BG2 alone 0.54 ms).
- **VRAM, 70,336 bytes, all in the plane pages, no texture slot:** the atlas in plane page 13
  (`ATLAS_1`, `0x468000`, 32,768), the map at `MAP_BG2` (`0x458000`, 32,768), the affine table
  (`LT_AFFINE`, 3,840) and the palette table (`LT_FREE`, 960). The silhouette keeps page 12
  (`0x460000`; 717 tiles of 1,024 for the shrine's) and `MAP_BG1`; pages 14–15 and `MAP_FREE`
  stay free.
- **Palettes:** 16 four-bit palettes of bank 0 (planes read bank 0 only), 232–247
  (`plain_palette`). Today the town region's palettes are 0–197, the shrine's silhouette palette
  198, the star 254 and the fonts 255. If the town ever needs more than 231, cap it in the recipe
  (`regions.town.palettes = {"first": 0, "count": 232}`) or move `plain_palette`.
- **Line channels:** 7 (`plane_floor()`) and 3. The backdrop uses 0; nothing else in the cart or
  the reader uses any.
- **ROM:** 65,536 bytes of art and 128 of colours.

## The changes

1. **The cart** (`cart.patch`, `git apply carts/garden/shrinetown/art/plain/cart.patch`):
   - `ground/ground.akr`: `import "../shrinetown/art/plain/plain.akr"`; `plain_hide()` at the top
     of `world_load()`; `plain_show()` after `world_shrinetown_load()`; `plain_variant(world_variant)`
     after `world_shrinetown_fog(k, world_variant)` in `world_region_entered()`.
   - `game.akr` `draw()`: `plain_draw(cam.eye, cam.pitch)` right after `wp_draw(...)` (it does
     nothing outside the shrine town).
2. **The world:** nothing. `make_world.py` and `shrinetown.world.json` are untouched; the plain
   reads the fog the world declares.
3. **With the look branch** (`alpha-fix-look`: backdrop, fog, haze): apply after it. The plain
   follows a new fog colour or range by itself, sits behind a taller or repainted silhouette, and
   covers the band the backdrop's −8° stop used to show (so the colour of that stop matters only
   above `PLAIN_FAR`, 3,000 m, which is the horizon line itself). Rerun `preview_plain.py` on the
   merged build and look at `plain_cap`: with a farther fog, 1.0 may be enough; with a nearer one,
   lower it. Check that the look branch takes none of plane page 13, `MAP_BG2`, `LT_FREE`, line
   channel 3 or palettes 232–247.
4. **To check after applying:** `make B=... test-carts` (the garden's scenarios passed with the
   patch on this branch), and the views:
   `B=... python3 carts/garden/shrinetown/art/plain/preview_plain.py`.
