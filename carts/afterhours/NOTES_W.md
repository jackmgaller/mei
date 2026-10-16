# Agent W's notes: the moving water

The owner's note: "the water needs to move." Every body of water was still: the tanks and their
glow, the ocean window, the tank tops' open water, the plant's sumps, the painted caustics on the
aquarium's floors, the puddles on the roof and at the station's stair. This pass makes it move.
Kept current. Nothing is committed.

## What moves now

| Room (stage) | What moves | How |
|---|---|---|
| The ocean gallery (aquarium, room 4) | The caustic net on the floor in front of the window, on the tank's sand and up its back wall; the ripple on the coral cube's and the glass column's surfaces | Overlay `aq_water` (93 triangles); the cube's and column's ripple tile animated in `aq_tanks` |
| The tank tops (room 8) | Glints on both tanks' surfaces round the work lamps, faint ripples elsewhere; the net on the turtle pool's sand and in the shark tank's black | Overlay `at_wwater` (67) |
| The great tank (room 2) | The net on the floor in the window's light box, on the sand behind the glass, the ripples' light on the back wall over the back walk; glints on the surface under the catwalks | Overlay `ag_wwater` (64) |
| The entrance hall (room 1) | The net in the welcome tank's light boxes and in the great tank's blue at the east door; the tank's surface ripple | Overlay `ah_wwater` (21); the tank's ripple animated in `ah_props` |
| The jellyfish gallery (room 3) | A net of each column's hue on the floor round its plinth; the columns' surface ripple | Overlay `aj_wwater` (44); ripple animated in `aj_columns` |
| Quarantine (room 5) | The violet net beside each row of tanks; the tanks' violet sheen | Overlay `qt_wwater` (40); sheen animated in `qt_tanks` |
| The life-support plant (room 6) | Glints on the sumps and the channel, brightest where each lamp's reflection lies | Overlay `ap_wwater` (67) |
| The fish kitchen (room 7) | The feed tank's surface ripple; rings spreading in the west basin under the dripping tap | `ak_glass` (2 more triangles) |
| The roof (tower, room 5) | Wind on the four puddles, glints in the sky's light, red in the one holding the warning light | Overlay `rf_wwater` (32) |
| The passage (station, room 3) | Rain falling down the stair to the street (it was 14 still streaks); rings in the lost umbrella's puddle; the rain's sheen inside the way out | Overlay `r3_wwater` (28) |

Captures in `water/shots/` (`water/capture.py`): per room `NAME.gif` (every 2nd frame for 72
frames, as the game draws it), `NAME_strip.png` (four frames 6 ticks apart) and `NAME_crop.png`
(the strip cropped to the water, twice the size); `NAME_before_strip.png` the same frames from
the worlds before this pass; `compare.png` before, after and after 12 ticks for six rooms.

## The technique, and why

**Animated repeating tiles.** Everything that moves is a small 4-bit tile whose frames the Asset
Kit keeps in ROM (a sheet's `frames` and `ticks`, ASSETKIT.md "Animated textures"), packed by
the World Kit with the region's set; `dr_water.akr` copies a frame into the tile in VRAM when it
changes. Meshes never change. Four tiles (`water/wateranim.py`):

| Tile | Size, frames, ticks | Loop | A frame's copy | ROM a region |
|---|---|---|---|---|
| `w_caustic`: the net, the edges of cells round seeds wobbling on small circles (a Voronoi net wrapped round the tile, the edges warped) | 64 x 64, 24, 6 | 2.4 s | 64 rows of 32 bytes, about 3,900 cycles | 48 KB |
| `w_ripple`: glints, a finer net lit in stretches where two swells crest | 64 x 64, 16, 6 | 1.6 s | the same | 32 KB |
| `w_drip`: rings from three drops a loop | 32 x 32, 16, 4 | 1.07 s | 32 rows of 16 bytes | 8 KB |
| `w_rain`: streaks falling two tiles a loop (5 m/s) | 32 x 32, 8, 3 | 0.4 s | the same | 4 KB |

Each tile is seamless in space (whole numbers of waves and cells across it, so it repeats through
a texture window) and in time (whole numbers of cycles a loop, so its last frame runs into its
first). No random numbers. The caustic repeats every 2 m (32 texels a metre, about a texel a
pixel at the game's camera), the ripple every 2 m (1 m on the roof's puddles), the drip every
0.5 m in the basin and the puddle, the rain 0.5 x 1 m.

**Grey tiles, coloured by light.** The tiles are grey, from black. Each room's overlay is a
recipe of flat quads (3 cm over a floor, the cones' height; 3 cm over a surface) in `add`, lit
only by point lights of its own with ambient 0: where no light falls the tile adds nothing, and
the net is exactly as bright and as blue, violet, green or warm as the light there. One tile
serves every room and colour; the light's pool shapes the net (the kit's refinement follows it,
at most 32-64 triangles). Surfaces that were already a repeating ripple texture (the tanks in the
ocean gallery, the hall, the jellyfish columns, quarantine, the kitchen's feed tank) keep their
blend and get a coloured ripple tile in its place: no new geometry.

**The still paint keeps its light, not its net.** Where a floor or a surface had the net painted
in (`caustics()` in the dress scripts), the painting now uses the net's average there (0.12-0.16,
a little under its mean of 0.16), so the light pool stays and the overlay adds the net that
moves. The painted lamp streaks on the plant's sumps keep their shape and lose their breaking up,
which the glints at the same place now do.

**What I weighed:**

- **Palette cycling** is nearly free on the CPU (about 38 cycles a colour), and the classic way.
  Its motion is a contour sweeping through a phase field: good for ripples, poor for a caustic
  net (the net breathes in and out instead of drifting). It also needs the cart to know which
  4-bit palette and entries the World Kit gave a tile, and the tile its own entries: the packer
  shares palettes between tiles while their colours fit and recolours them for night variants.
  Animated frames need neither: the kit already packs them, region by region.
- **Texture-window scrolling and UV changes** are out: a mesh's window table and its UVs are in
  ROM, read in place.
- **Animating the painted floors' frames** (220 x 126 8-bit) would cost 27 KB a frame of ROM and a
  copy of 15,000-30,000 cycles a change. The overlay costs a 2 KB copy and its triangles.
- **Vertex colours a frame** would mean meshes in RAM, and only light at corners.

The GPU pays: an overlay pixel is textured and blended, 4 cycles. That is the largest cost
(below), and the GPU has the room (its worst frame is 39 % of its budget).

## The runtime (`dr_water.akr`, mine) and the hook (agent A's files)

`water_tick()` once a frame: for every region of the open world with animated tiles whose
tiles are in VRAM now, the frame of each tile at `frame()` (staggered by tile and region) is
copied when it changed, at most two copies a frame (`W_COPIES`; the rest a frame late). A
slot holds region k's tile when the reader last copied k's set there (`__wp_slot_src`, then frame
0) or when `water_tick()` last wrote one of k's frames there and nothing was copied since; a
region whose slots another region took is left alone, so nothing is written over another room's
textures. It does not use `wp_animate()`, which advances only the region last entered with
`wp_region_enter()`: H's transition draws two rooms, the next one's textures copied in a slot at
a time, and both rooms' water moves through the transition. A world without tiles (the store)
costs a compare.

**Determinism:** the frame shown is a function of `frame()` alone; nothing the rules read
changes, so every tape plays the same (all 47 of A's scenarios and E's 13 pass, nothing
re-recorded). The water does not jump when a catch restarts the room's clock.

**The hook (for A, `aedb8992d04d91177`; three lines, each marked "agent W"):**

- `dr_hooks.akr`: `weak fn water_tick() {}` (a section "W" at the end);
- `dr_game.akr`: `water_tick()` as the second line of `update()`, every frame in every mode;
- `dr_world.akr`: `import "dr_water.akr"` after `dr_levels.akr`, so the cart and every harness
  that imports `dr_world.akr` (A's, E's, H's, mine) get it.

A: if you would rather call it from elsewhere (it must run once a frame, before the frame is
drawn), move the call; `water_enabled()` (weak, true) lets a scenario still it.

## What I changed in the builders' scripts (each change marked "agent W")

| Script | Change |
|---|---|
| `rooms/aquarium/make_aquarium.py` | Imports `wateranim`; `paint_floor()` and `paint_sand()` keep the net's average; the tanks' `surface` and `column_surface` use the ripple tile; `water_recipe()` (new) writes `aq_water`; `main()` writes it and its placement `r5_water` |
| `rooms/aq_tops/dress_aq_tops.py` | `paint_surface()` and `paint_deep()` keep the ripples' and the net's average; `wwater_recipe()` (new); placement `at_wwater` |
| `rooms/aq_great/dress_aq_great.py` | `paint_floor()`, `paint_back()`, `paint_sand()`, `paint_water()` keep the average; `wwater_recipe()`; placement `ag_wwater` |
| `rooms/aq_hall/dress_aq_hall.py` | `paint_floor_tile()` keeps the net's average (tank and door); the tank's `water_cut` and `surface` use a coloured ripple tile (emissive, as before); `wwater_recipe()`; placement `ah_wwater` |
| `rooms/aq_jelly/dress_aq_jelly.py` | The bays' shimmer keeps its average; the columns' `surface_K` use a ripple tile; `wwater_recipe()`; placement `aj_wwater` |
| `rooms/aq_quar/dress_aq_quar.py` | `floor_shade()` keeps the net's average; the tanks' `surface` uses a violet ripple tile; `wwater_recipe()`; placement `qt_wwater` |
| `rooms/aq_plant/dress_aq_plant.py` | `paint_water()` keeps the ripples' average and the streaks unbroken; `wwater_recipe()`; placement `ap_wwater` |
| `rooms/aq_kitchen/dress_aq_kitchen.py` | `strips_recipe()`: the feed tank's `surface` gets the ripple tile, a `drip` quad in the west basin |
| `rooms/roof/dress_roof.py` | `PUDDLES` (the paint's four), `wwater_recipe()`; placement `rf_wwater` |
| `rooms/passage/dress_passage.py` | The still rain streaks left out of `street_stair()`; `wwater_recipe()`; placement `r3_wwater` |

Run as their builders run them (`--placements` for the hall, the jellyfish gallery and the
roof), then the stage's level script (`levels/aquarium/make_aquarium.py`,
`levels/station/make_station.py`, `levels/tower/make_tower.py`), which only adds the new
placements to the world recipes. Before changing them I checked that each script regenerated its
files byte for byte. Side effects: the hall's, the jellyfish gallery's and the plant's 8-bit art
is quantised together, so their other pictures moved by a level here and there (mean 0.0-2.7 of
255). The ocean gallery's `art/ripple.png` is still written and no longer used.

## Numbers

Release builds (`TRAP=0`); budgets 1,000,000 CPU and 2,000,000 GPU cycles. **Before**: the worlds
as they were (a copy of `build-ah-H/cart-worlds`, made before this pass) and the water still;
**after**: these worlds, the water moving. Both with the same cart code, side by side, in my
scenario 97 (`tests/water/`: each stage's solution tapes through the front end's transitions,
the worst frame per room in play from its clock 3 and per transition; `tests/water/measure.sh`
with `BASE_WORLDS`).

| Room, in play (worst frame) | CPU before | after | GPU before | after |
|---|---|---|---|---|
| Aquarium 1, the hall | 473,064 | 505,516 | 489,517 | 539,275 |
| 2, the great tank | 549,282 | 571,676 | 550,577 | 703,960 |
| 3, the jellyfish | 454,085 | 468,641 | 448,130 | 549,237 |
| 4, the ocean gallery | 417,442 | 442,133 | 415,201 | 531,670 |
| 5, quarantine | 361,431 | 377,601 | 410,699 | 450,473 |
| 6, the plant | 407,181 | 424,675 | 403,200 | 498,382 |
| 7, the kitchen | 311,147 | 317,393 | 366,219 | 368,663 |
| 8, the tank tops | 343,653 | 366,408 | 435,385 | 620,579 |
| Tower 5, the roof | 176,148 | 185,946 | 315,720 | 321,018 |
| Station 3, the passage | 238,348 | 239,679 | 354,700 | 355,639 |
| Every other room | | +1,000 or less | | unchanged |

| Transitions, worst frame | CPU before | after | GPU before | after |
|---|---|---|---|---|
| The aquarium (9) | 619,131 | 648,653 | 617,047 | 770,887 |
| The station (2) | 335,062 | 346,207 | 343,135 | 343,135 |
| The tower (5) | 505,401 | 505,791 | 422,868 | 422,868 |
| The store (7) | 515,598 | 515,609 | 475,466 | 475,466 |

Each aquarium transition gains 20,000-55,000 CPU (two rooms' overlays and their copies) and up to
195,000 GPU. H's scenario 95: the aquarium's worst transition frame 648,606 CPU, 770,887 GPU; E's
(with its checks in the frame) 791,607 debug. Every check's margin holds.

**The heaviest frames, loading a room** (A's scenarios, the only frames near the budget, which
H is reducing): the great tank's load in scenario 85, 780,334 → 797,948 release (882,649 →
900,353 debug); a stage's start in scenario 88, 744,977 → 761,547 release (839,243 → 855,900
debug). About 17,000 more: the room's larger slot images and its overlay drawn that frame.

**`water_tick()` itself:** at most 11,364 cycles (two 64-row copies, the cap); 1,000-2,000 on
a frame that copies nothing; a compare in a world without water. The overlays: about 120 cycles a
submitted triangle, 21-93 triangles a room.

**VRAM:** the slots each region uses are unchanged (`check_slots.py`: no joined rooms share a
slot; E's `check_worlds.py`: slot 7 and palettes 250-251 left alone). Each region's set grows by
its tiles: 2-4 KB (the ocean gallery 60,541 → 64,125 bytes, the great tank 174,471 → 178,567).

**ROM:** the frames, kept per region: 32-80 KB a region with water. The aquarium world 2,273,572
→ 2,900,720 bytes, the station 611,472, the tower 1,435,816; the cart 11,699,978 → 12,416,586
bytes (of 64 MB).

## Checks (all in `build-ah-W/`)

- Asset Checker in depth mode: every new and changed recipe passes (24: the ten overlays and
  every recipe whose art or materials changed).
- World Checker: the aquarium, the station and the tower, 0 hard failures, 0 over thresholds.
- `tests/check.sh`: all 47 After Hours scenarios and E's 13; `tests/trans/check.sh`: slots,
  scenario 90 and 95 for the four stages.

## For the owner

1. **Is it the right amount?** The ocean gallery's and the great tank's nets are as strong as
   their painted ones were; the tank tops' black water now has glints only round the lamps. The
   roof's puddles are small and dark: their wind ripples read only up close.
2. **The loading frames** gain about 17,000 cycles (2 %); they were already the cart's heaviest.
3. **The GPU** gains up to 185,000 cycles in the tank tops and the great tank's catwalk (the
   overlays cover much of the picture there): the worst frame is 39 % of its budget.
4. **Not moving yet:** the fish (meshes in ROM: they would need the cart to draw them), the
   ocean window's painted backdrop and light shafts, the glass's glow (it could pulse with the
   palette, but the cart would need each emissive entry's place in the region's palettes), the
   roof's panel tanks' cut water, the station stair's rain mostly off the picture (the camera
   stops at the room's end). The tank tops' bridge lamp runs on a timer; its glints do not
   follow it (a baked light cannot), so they stay at half strength, as its painted glints were.
5. `AGENTS.md`'s Generators table could list `water/wateranim.py` with the rooms' dress scripts
   (J's follow-up asks the same for the dress scripts).

## Files (mine)

| File | What |
|---|---|
| `dr_water.akr` | The runtime: `water_tick()` |
| `water/wateranim.py` | The tiles (`--preview DIR` writes their frames), the `Overlay` recipe builder, the helpers the dress scripts call |
| `water/capture.py` | The captures in `water/shots/` (`--still --worlds DIR --suffix _before` for the before) |
| `tests/water/harness.akr`, `run.sh`, `measure.sh` | Scenario 97, and the before and after |

```sh
make B=build-ah-W build-ah-W/carts/afterhours.mei
MEIC=build-ah-W/meic RUN=build-ah-W/mei-headless WORLDS=build-ah-W/cart-worlds/afterhours \
  BASE_WORLDS=DIR carts/afterhours/tests/water/measure.sh      # BASE_WORLDS optional
python3 carts/afterhours/water/capture.py --build-dir build-ah-W
```
