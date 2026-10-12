# Shrine town: the backdrop

A sky and a far view round the level, on the Horizon Engine's tile plane
([WORLDKIT.md](../../../../../docs/WORLDKIT.md#backdrops), [PLANES.md](../../../../../docs/PLANES.md)):
no triangles and no GPU cycles. **One backdrop for both texture regions** (`town` and `shrine`)
since the alpha fixes (DESIGN.md 12.9): until then each region had its own, and crossing z = 128
moved the ranges by up to 45 rows, rearranged the clouds and moved the radio tower by 5 degrees.

| File | What |
|---|---|
| `backdrop.png` | 1,024 × 128, 15 colours: the silhouette, both regions |
| `backdrop.json` | The sky (6 stops, day and night), the silhouette's `horizon` (40 rows under it), the night's exact colours, and `fog`: each variant's fog colour, which `make_world.py` reads |
| `draw_backdrop.py` | Draws the PNG and `backdrop.json`. `--preview DIR` draws the panorama on its sky, day and night |
| `preview/` | `backdrop_day.png`, `backdrop_night.png` (2.84 pixels a degree, the horizon at row 200). `town_views.png` and `shrine_views.png` are the world before and after the first backdrops (2026-10-05), kept as history |

## What is in it

Column 0 is north and the picture runs east: 256 is east, 512 south, 768 west. The bottom 40 rows
stand under the horizon line (`"horizon": 40`).

- **Above the horizon:** mackerel cloud; three ranges, a pale far one, a blue-green second and a
  dark forested ridge with the autumn's red and gold crowns in its top rows, highest to the north;
  to the south the city: far blocks in haze, the middle rows with windows, the near rows with
  tiled roofs, a red-and-white radio tower at 198°, chimneys at 135° and 232°, a crane at 248°,
  and low danchi to the east and west. The ranges' and the city's feet fade into the haze (an
  ordered dither on the 4-pixel grid, so it costs few tiles).
- **Under the horizon** (seen from the pagoda, the walkway and the stage, where the drawn world ends
  190–260 m off): far low town (south) and fields as haze marks, thinning out downward, then the
  fog colour alone. The day fog is whole at 240 units and the sky's stop below the horizon is the
  fog colour too, so the fogged end of the drawn world meets the backdrop in one colour.
- **Night:** the sky's second set; the PNG's colours take the night's `surface.multiply`
  (`#4a5884`), and exact colours after that: about a third of the windows glow (`#566680` →
  `#f2cf78`), the clouds go a moonlit blue, the tower's bands brighten, the crowns go dull, and the
  haze and fog colours become the night fog's (`#181842`, near the sky's 9° stop).

The fog colours are in `draw_backdrop.py`'s `FOG`, exact in 15 bits, so the GPU's fog and the
plane's pixels are the same colour: by day the sky 3° up (`#d6dede`, a pale blue-grey that the
blue ranges recede into), by night `#181842`.

## The world: `make_world.py`

Both regions' `backdrop` is `{"elevations", "sky", "silhouette": {"image":
"art/backdrop/backdrop.png", "horizon": 40, "repeat": 1}}`, the sky's −8° stop replaced by the
variant's fog colour; each region's `variants.night.backdrop` is `backdrop.json`'s night colours;
`variants.*.fog` takes `backdrop.json`'s `fog` colours; the haze (`haze.colors`) too.

The garden cart shows the entered region's backdrop (`world_region_entered(k)` in
`../../../ground/ground.akr`); with one image for both, crossing the line changes nothing in it.

## Limits and bytes

| | Limit | Backdrop |
|---|---|---|
| width, height | 256, 512 or 1,024; at most 128 | 1,024 × 128 |
| colours | 15 in one 4-bit palette of the region's range | 15 |
| distinct 8 × 8 tiles (atlas, plane page 12) | 1,024 | 718 |

The tiles are at 70 % of the page. To stay under 1,024, add detail in the city's rows (regular
grids repeat; random marks do not) rather than in the clouds or the ridge crowns.
