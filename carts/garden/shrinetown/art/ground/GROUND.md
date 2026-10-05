# Shrine town: ground textures and edges

The textures for the shrine town's ground (terrain materials of `shrinetown.world.json`) and for
the level's edges, authored and not yet applied: what each one is, what it costs in each texture
region against TEXTURES.md's ground allowances (town 40,960 bytes, shrine 122,880), what the
shrine world's set lends, and where each one goes.

| File | Makes |
|---|---|
| `draw_ground.py` | The PNGs here (16 textures). `--preview DIR` writes a contact sheet |
| `../../assets/edge_neighbour/make_edge_neighbour.py` | The neighbours' backs: `art/facade_a.png`, `art/facade_b.png`, 15 recipes |
| `../../assets/edge_hoarding/make_edge_hoarding.py` | The road-works hoarding: `art/panel.png`, `art/sign.png`, its recipe |
| `preview_ground.py` | A 128 × 128 m test world of all of it, built and drawn on the console, day and night |
| `preview/ground_contact.png` | Every texture at 1:1, 4×, tiled, its far colour and shrunk, day and night |
| `preview/views.png` | 14 views of the test world at 320 × 240, day and night |

All are 4-bit (15 colours at most), repeat seamlessly, use STYLE.md's colours where it has them,
and are drawn from fixed seeds (authored art: rerun only to change them). No 8-bit textures.

## Costs

Measured with `preview_ground.py` (`B=build-gt`): each region's `textures.vram_bytes_allocated`
in the test world's `report.json`. A terrain texture is stored repeated `span` texels further
each way plus a 1-texel gutter, on the 8-texel grid, and once more as loaded (its tile size) when
any of its faces needs a texture window (WORLDKIT.md, "Textured terrain"):

| Texture | Span | Stored | Window tile | Bytes |
|---|---|---|---|---|
| 32 × 32 | 23 | 56 × 56: 1,568 | 512 | 2,080 |
| 32 × 32 | 71 | 104 × 104: 5,408 | none (see Markings) | 5,408 |
| 32 × 32 | 87 | 120 × 120: 7,200 | 512 | 7,712 |
| 16 × 16 | 23 | 40 × 40: 800 | none on sweeps (128 on the field) | 800 |
| 64 × 64 | 23 | 88 × 88: 3,872 | 2,048 | 5,920 |

Spans are chosen so that span + size + 1 is a multiple of 8 (23, 31, ..., 71, 79, 87); one
texel more costs a whole row of cells. On flat ground the span saves no windows: the kit merges
a material's quads into rectangles up to its windowed reach (13.9 m at a scale of 2), far past
any span but 223, so the town, which is flat, uses 23 throughout. The shrine keeps 87 for its
surfaces on the mountain, where slopes keep faces small and a larger span keeps more of them
windowless (fewer than 7 windows a piece, below).

### Town region (z < 128): 38,848 of 40,960

| Material | Image | Size | Scale | Span | Far colour | Bytes |
|---|---|---|---|---|---|---|
| `asphalt` | `asphalt.png` | 32 | 2.0 | 23 | `#4a4a51` | 2,080 |
| `asphalt_line` | `asphalt_line.png` | 32 | 2.0 | 23 | `#53535a` | 2,080 |
| `asphalt_zebra` | `asphalt_zebra.png` | 32 | 2.0 | 23 | `#969696` | 2,080 |
| `asphalt_stop` | `asphalt_stop.png` | 32 | 2.0 | 71 | `#6b6b6f` | 5,408 |
| `sidewalk` | `sidewalk.png` | 32 | 2.0 | 23 | `#b2aea2` | 2,080 |
| `sidewalk_tactile` | `sidewalk_tactile.png` | 32 | 2.0 | 23 | `#b8ab8a` | 2,080 |
| `kerb` | `kerb.png` | 16 | 1.0 | 23 | `#bbb7ab` | 800 |
| `plaza` | `plaza.png` | 64 | 4.0 | 23 | `#bebaaa` | 5,920 |
| `concrete` | `concrete.png` | 32 | 2.0 | 23 | `#b7b2a7` | 2,080 |
| `ground` (sports ground) | `ground.png` | 32 | 2.0 | 23 | `#c39a6a` | 2,080 |
| `ground_line` | `ground_line.png` | 32 | 2.0 | 23 | `#c6a173` | 2,080 |
| `canal_wall` | `canal_wall.png` | 32 | 1.6 | 23 | `#807b70` | 2,080 |
| `pond_bed` (reused) | `../../../shrine/assets/art/terrain_pond_bed.png` | 32 | 2.4 | 23 | `#4b4332` | 2,080 |
| **Ground** | | | | | | **32,928** |
| `facade_a`, `facade_b` (the neighbours) | `assets/edge_neighbour/art/` | 64 | 6 m | | `#9e9d9a`, `#a09f9a` | 4,096 |
| `panel`, `sign` (the hoardings) | `assets/edge_hoarding/art/` | 32 × 64, 32 | 2 × 5.5 m, once | | | 1,824 |
| **Town total** | | | | | | **38,848** |

2,112 bytes spare. `asphalt_stop` at span 23 instead is 2,080 (35,520 in all) where the
7-window rule allows it (Markings). The town's textures took 6 of its 4-bit palettes in the test
world: each family (road; sidewalk, kerb, plaza and concrete; the sports ground; stone; the
façades; the hoarding) shares one set of colours, so the packer puts it in one palette.

### Shrine region (z ≥ 128): 106,496 of 122,880

| Material | Image | Scale | Span | Far colour | Bytes |
|---|---|---|---|---|---|
| `floor` (forest floor) | shrine `terrain_floor.png` | 2.4 | 87 | `#594325` | 7,712 |
| `litter` | shrine `terrain_litter.png` | 2.4 | 87 | `#7b4825` | 7,712 |
| `moss` | shrine `terrain_moss.png` | 2.4 | 87 | `#56732d` | 7,712 |
| `earth` | shrine `terrain_earth.png` | 2.4 | 87 | `#65452f` | 7,712 |
| `path` (dirt trail) | shrine `terrain_path.png` | 2.4 | 87 | `#906f4c` | 7,712 |
| `gravel` (raked) | shrine `terrain_gravel.png` | 2.4 | 87 | `#d4cbb9` | 7,712 |
| `paving` (the sando's slabs) | shrine `terrain_paving.png` | 2.4 | 87 | `#aba294` | 7,712 |
| `steps` | shrine `terrain_steps.png` | 2.4 | 87 | `#908b7f` | 7,712 |
| `stone` (ashlar) | shrine `terrain_stone.png` | 3.2 | 87 | `#848072` | 7,712 |
| `rock` | shrine `terrain_rock.png` | 4.8 | 87 | `#686157` | 7,712 |
| `cemetery_gravel` | `cemetery_gravel.png` | 2.4 | 87 | `#9b938a` | 7,712 |
| `bamboo_floor` | `bamboo_floor.png` | 2.4 | 87 | `#897a4a` | 7,712 |
| `park_grass` | `park_grass.png` | 2.4 | 87 | `#688436` | 7,712 |
| `canal_wall` | `canal_wall.png` | 1.6 | 23 | `#807b70` | 2,080 |
| `pond_bed` | shrine `terrain_pond_bed.png` | 2.4 | 23 | `#4b4332` | 2,080 |
| `park_sand` | `park_sand.png` | 2.4 | 23 | `#d7c69d` | 2,080 |
| **Shrine total** | | | | | **106,496** |

16,384 bytes spare, for two the plan may add: `concrete` (span 23, 2,080) if the viaduct's
pieces in c4_2 are textured, and the shrine's `art/forest_planks.png` (32 × 32, the walkway
decks' texture) as a `planks` terrain material for the walkways and bridges (span 87, 7,712);
both: 116,288. 11 of the region's 4-bit palettes in the test world.

The shrine region's `canal_wall` and `pond_bed` are at span 23 because the canal (x 44–52,
z 0–292) and the culvert cross the boundary: one material is one span, and the town cannot pay
7,712 for either.

### Reused from the shrine world

Eleven of the shrine's 13 ground textures, unchanged, at the shrine world's own scales:
`terrain_floor`, `terrain_litter`, `terrain_moss`, `terrain_earth`, `terrain_path`,
`terrain_gravel`, `terrain_paving`, `terrain_steps`, `terrain_stone`, `terrain_rock`, and
`terrain_pond_bed` (in both regions). Not reused: its `terrain_asphalt` and `terrain_sidewalk`
(the town's own are drawn for the 2 m grid and its markings). Referenced from
the world file as `../shrine/assets/art/terrain_NAME.png`.

### The edges

- **Neighbours' backs** (`assets/edge_neighbour/`): one recipe per grey-box neighbour,
  `edge_neighbour_s0`–`s8`, `_e0`–`e2`, `_w0`–`w2`, at its width and height (west ones 4 m lower,
  as in `notes/gen_town.py`). A box whose level-facing side carries one repeating 64 × 64 façade
  tile (6 m a repeat: two 3 m bays, two 3 m storeys, 9.4 cm a texel), aligned so a slab edge is
  the roof line; ends and roof are palette colours; a 4 × 3 × 4 m stair house on the roof.
  Facade A is an apartment block's balcony side (sliding windows behind solid parapets, air
  conditioners on brackets, laundry, an airing futon, a drain pipe), B an office's back (tall
  windows with mullions, rust streaks, spandrels, pipes); they alternate along each edge.
  23–57 triangles each (the kit splits the façade every 18 m), 8 from 60 m (a plain box in the
  façades' mean colour). 4,096 bytes for all 15, one palette.
- **Hoarding** (`assets/edge_hoarding/`): 14 × 5.5 × 0.4 m, white ribbed steel panels, a blue
  top rail, a green kick plate, road grime; the bowing-worker sign as a 1.6 m decal on its
  front. 18 triangles, 1,824 bytes.
- **Canal walls**: `canal_wall`, kenchi-ishi (squarish granite laid on the diagonal, pyramid
  faces, moss and wet streaks in the joints), for the canal's and the culvert's banks and the
  cemetery's terrace walls.
- **Rock rims**: the shrine's `terrain_rock` (`rock`), grey strata with lichen; its bands are
  horizontal on the box projection's walls.

### How it reads

`preview/views.png` (320 × 240, left day, right night: the World Kit's `night` multiply
`#4a5884`): the road with its centre line, the shotengai-style crossing with its stop lines and
tactile strips, the plaza, the canal from the bank, the neighbours from the plaza and from 26 m
up, the hoarding, the shrine-region strips from 3 m and 30 m. Large surfaces are low contrast and
have no single bold mark (a 2 m repeat turns any mark into a grid: the first sidewalk's coloured
pavers and a 2 m plaza did, and were redrawn); within the field's coarse-level distance (22 m)
the asphalt and sidewalk shimmer little; beyond it the ground is drawn in the far colours above.
The reused raked gravel shows a moiré of its furrows from high up, as in the shrine.

## Application plan

### Rules

1. **Town cells use town textures only.** Every textured material drawn in a cell at z < 128
   joins the town's set (a sweep's piece belongs to the cell holding its strip's middle; a cliff
   op's faces to the cells they fall in). So:
   - shrine-type ground south of z = 128 (the strip z 118–128: the park's `grass`, the woods'
     `floor`, the courtyard's `gravel`; the rims' `rock` at x 0–2 and 318–320; the sweeps that
     start south of the line: `core_canal_lane`, `trail_west`, `core_walkway_stair`,
     `core_walkway_foot`) is drawn with **untextured materials in the textures' far colours**
     (`grass_far` `#688436`, `floor_far` `#594325`, `gravel_far` `#d4cbb9`, `rock_far`
     `#686157`, `earth_far` `#65452f`, `path_far` `#906f4c`, `steps_far` `#908b7f`):
     split the paint, cliff and path at z = 128 (a path in two, meeting at the boundary's
     cross-section). Seen from the town region, everything beyond the line is a stand-in in flat
     colours anyway, so the strip matches what is beyond it;
   - the canal's and the culvert's `bank` and `bed` are textured on both sides (`canal_wall`
     and `pond_bed` at span 23; each region pays 2,080 for each).
   - The field's `steep` material is `rock`: a quad steeper than 38° in a town cell adds `rock`
     to the town's set. After the build, `report.json` `regions.town.textures.by_asset.terrain`
     must be 32,928 bytes (24 tiles); more means a shrine material reached a town cell.
2. **At most 7 windowed textures a terrain piece** (a field tile is 16 quads, 32 m). Every
   textured face on the town's flat ground is windowed. The busiest tiles are the front road's
   at the shotengai's mouth (x 128–160 and 160–192, z 96–128): asphalt, line, zebra, stop,
   sidewalk, tactile, plaza and concrete, 8. `asphalt_stop` at span 71 is never windowed on a
   2 m quad, which makes it 7; the alternative is to leave stop lines out of those tiles (span
   23, 3,328 bytes less). The build fails with "draws more than 7 textured materials through
   texture windows" where a tile has more.
3. **Names.** The material names below are the world's (make_world.py joins the regions' parts;
   a name two parts define keeps the first). Where one name means two things it is split:
   the town's `paving` (the plaza) becomes `plaza`; the shrine's approach paving is `paving`.

### By world material

Scale is `[s, s]`; `rotate` is the texture's (a texture's v runs along world z: a marking or
strip along x is `rotate: 90`). Projection: the default `box`.

| World material (now) | Texture | Scale | Span | Where |
|---|---|---|---|---|
| `street` (the town's base) | `concrete` | 2 | 23 | alleys, service lanes, yards, under buildings |
| `asphalt` | `asphalt` | 2 | 23 | the front road's carriageway (below) |
| `paving` → `plaza` | `plaza` | 4 | 23 | the station plaza (x 100–216, z 14–44) |
| `sando` (the shotengai) | `plaza`, `offset: [0.5, 0]` | 4 | 23 | x 154–166, z 44–104: the bands fall on x 154, 158, 162, 166 |
| `clay` | `ground` | 2 | 23 | the sports ground (x 244–292, z 18–52), with its lines (below) |
| `pooldeck` | `concrete` | 2 | 23 | the pool's deck |
| `bank` | `canal_wall` | 1.6 | 23 | the canal's, pool's and culvert's banks (cliff walls) |
| `bed` | `pond_bed` | 2.4 | 23 | the canal's, pool's and culvert's beds |
| `viaduct`, `viaduct_under`, `deck`, `parapet` | `concrete` | 2 | 23 | the viaduct's sweeps (the shrine pays 2,080 for c4_2) |
| `grass` | `park_grass` | 2.4 | 87 | the park (x 0–44, z 128–206), the north-east meadow; `grass_far` south of 128 |
| `floor` (the field's default) | `floor` | 2.4 | 87 | woods and mountain; `floor_far` south of 128 |
| `gravel` | `gravel` | 2.4 | 87 | the courtyard (x 110–210, z 128–166); `gravel_far` south of 128 |
| `ashlar` (the terrace's top) | `gravel` | 2.4 | 87 | the precinct's terrace: raked gravel, with `paving` paths |
| `canal_stone` | `stone` (precinct) / `canal_wall` (cemetery) | 3.2 / 1.6 | 87 / 23 | split: the terrace's retaining wall and the temple's podium in ashlar; the cemetery's nine terrace walls in kenchi-ishi |
| `podium` | `stone` | 3.2 | 87 | the temple's podium top |
| `cemetery` | `cemetery_gravel` | 2.4 | 87 | the cemetery's terraces (x 256–316, z 130–250) |
| `bamboo_floor` | `bamboo_floor` | 2.4 | 87 | the bamboo grove (x 0–44, z 206–384) |
| `litter` | `litter` | 2.4 | 87 | the mountain's top (x 44–244, z 320–384) |
| `moss` | `moss` | 2.4 | 87 | the sacred cedar's basin |
| `fox_earth` | `earth` | 2.4 | 87 | the fox grove's clearing |
| `earth` | `earth` | 2.4 | 87 | trail and stair sides (sweeps); `earth_far` south of 128 |
| `path`, `lane` | `path` | 2.4 | 87 | trails, the canal lane (sweeps); `path_far` south of 128 |
| `steps` | `steps` | 2.4 | 87 | every stair sweep; `steps_far` south of 128 |
| `stone` | `stone` | 3.2 | 87 | the mountain's ledges, shelf and stair sides |
| `rock` | `rock` | 4.8 | 87 | cliffs, rims, the field's steep quads; `rock_far` south of 128 |
| `planks` | (optional) shrine `forest_planks.png` | 2 | 87 | walkways, bridges; else flat |
| `rope`, `water`, `falls` | untextured | | | |

New paints the plan adds:

| Paint | Material | Area |
|---|---|---|
| the shrine's sando | `paving` | x 156–164, z 128–152 (torii to the gate stair); `gravel_far`'s strip south of 128 stays gravel-coloured |
| the playground's sand | `park_sand` | under the slide, jungle gym and swings (from the park's placements), quad-aligned |
| the front road's sidewalks, lines and crossing | below | |
| the sports ground's lines | below | |

### Markings

Every town texture is drawn for a 2 m repeat (the plaza 4 m), and the ground's quads are 2 m on
even coordinates, so a marking painted on a row of quads lies at the same place in every quad of
the row. In `asphalt_line` the line is at texels 15–16, so with no offset its middle is at the
middle of the quad row (an odd coordinate); `asphalt_stop`'s band and `sidewalk_tactile`'s strip
are centred the same way, `asphalt_zebra`'s bars are at texels 4–11 and 20–27 (50 cm bars, 50 cm
apart). `offset` moves a marking within its row (a quarter repeat is 0.5 m).

**The front road** (z 104–118, x 0–320; driving on the left: the north lane is eastbound):

| Rows (z) | Material | rotate |
|---|---|---|
| 104–106 | `sidewalk_tactile` (strip at z 105) | 90 |
| 106–108 | `sidewalk` | |
| 108–110 | `asphalt` | |
| 110–112 | `asphalt_line` (the centre line at z 111) | 90 |
| 112–114 | `asphalt` | |
| 114–116 | `sidewalk` | |
| 116–118 | `sidewalk_tactile` (strip at z 117) | 90 |

- Kerbs: sweeps along z 108 and z 114, profile `[[-0.1, 0], [-0.1, 0.15], [0.1, 0.15], [0.1,
  0]]`, material `kerb` (span 23; a sweep is never windowed), broken at the canal's bridge
  (x 44–52), the culvert (x 234–238) and the crossing. 0.15 m: the body steps over it.
- The crossing at the shotengai's mouth: `asphalt_zebra`, `rotate: 90` (the bars run with the
  traffic), x 158–162, z 108–114; the tactile rows across the sidewalks at x 158–162 with
  `sidewalk_tactile` at rotate 0. Stop lines (`asphalt_stop`, rotate 0, the band at an odd x):
  eastbound x 154–156, z 112–114; westbound x 164–166, z 108–110.
- The edge lines are left out: a kerbed town road has none. `asphalt_line` with an offset makes
  them if wanted.

**The sports ground** (x 244–292, z 18–52): `ground_line` rows x 246–248 and 288–290 (rotate 0:
lines at x 247 and 289), z 20–22 and 48–50 (rotate 90: lines at z 21 and 49), and the halfway
line x 266–268 (x 267). Corner quads take one direction (the later paint): a gap of under a
metre at each corner. One tile for both rotations, so one window.

### Edges

| Grey box (cells) | Replace with | Position | Yaw |
|---|---|---|---|
| `neighbour_s0`–`s8` (`gbt_neighbour*`) | `edge_neighbour_s0`–`s8` | the same (z 0.2) | 180 |
| `neighbour_e0`–`e2` | `edge_neighbour_e0`–`e2` | the same (x 319.8) | 90 |
| `neighbour_w0`–`w2` | `edge_neighbour_w0`–`w2` | the same (x 0.2) | 270 |
| `hoarding_w` | `edge_hoarding` | (0.2, 0, 111) | 270 |
| `hoarding_e` | `edge_hoarding` | (319.8, 0, 111) | 90 |

Yaw turns the asset's front (-Z) to the level (`mesh_at()`: yaw 90 faces it -X). Collision
`"self"`. Add `assets/edge_neighbour` and `assets/edge_hoarding` to the world's `asset_dirs`.
Optional at night: light some windows with a variant's `texels`, per asset,
`"edge_neighbour_s0.facade": {"#3e4a5e": "#e8c878"}` (the lit-window glass is its own colour in
both façades).

## Checking the application

```sh
B=build-gt python3 carts/garden/shrinetown/art/ground/preview_ground.py   # this set, measured
make B=build-gt build-gt/carts/garden.mei                                # the world, with the checker
python3 -c "import json; r = json.load(open('build-gt/worlds/carts/garden/shrinetown/report.json')); \
  [print(k, v['textures']['vram_bytes_allocated'], v['textures']['by_asset'].get('terrain')) \
   for k, v in r['regions'].items()]"
```

The town's terrain must be 32,928 bytes and the shrine's 106,496 (plus 2,080 for concrete,
7,712 for planks, if added).
