# Check-In! — shared conventions

Check-In! was built by three agents in parallel: the **main** agent (code), the **art** agent
(meshes, textures, sprites, icons) and the **audio** agent (music, sound effects, ambience). The
polish pass (`POLISH.md`) splits the work into three workstreams instead, **A** (art direction
and rendering), **B** (UI, UX and controls) and **C** (simulation, people movement and balance),
with the audio files unchanged. Everyone re-reads this file before each work session and
follows it; the owner of a file is the only one who edits it (ask the owner for changes).

## Files

| Owner | Files (in `carts/checkin/` unless they start with `tools/` or `src/`) |
|---|---|
| **A: art and rendering** | `tools/gen_checkin_art.py`; `art/` and the generated `art.akr`, `art_load.akr`; `render.akr` (camera projection, static geometry cache, floors, walls, facades); `lighting.akr`; `objects.akr` (the others call its footprint and bake functions but don't edit them); `people_draw.akr` (people sprites, shadows, carried props, elevator cars); `tests/scen_art.akr` |
| **B: UI, UX and controls** | `build.akr` (cursor, camera follow, build tools, placement ghost, build menu); `ui.akr`; `style.akr` (shared colour tokens); `hud.akr` (top bar, hint bar, messages, goal, debug counters, room panel); `screens.akr`; `overlays.akr`; `game.akr` (frame loop and input; A and C ask B for changes); `audio_link.akr` (sound hooks); `tools/gen_checkin_assets.py` (fonts, icons, logo, panels, save icon, and the writer of the generated `gen.akr`, `gen/`, `art_link.akr`); `tests/scen_ui.akr`; `src/platform/headless.c` (the `--dump-every` option) |
| **C: simulation and people** | `people.akr` (people and their movement); `sim_vis.akr` (the visual state the simulation writes and `people_draw.akr` reads: `people_vis[]`, `elev_vis[]`); `path.akr`; `transport.akr` (elevator logic); `guests.akr`; `staff.akr`; `jobs.akr`; `sim.akr`; `rooms.akr`; `world.akr`; `save.akr`; `scripted.akr`; `tools/checkin_data.py` (the object catalogue, floor finishes, room types, guest types, staff roles, reviews: every number the game is balanced with); `tests/harness.akr` (test infrastructure and fixtures) and `tests/run.sh`; `tests/scen_sim.akr` |
| audio | `tools/gen_checkin_audio.py`, `audio/`, generated `audio_data.akr`, hand-written `audio.akr` |
| lead | this file, `POLISH.md` |

- **Generated files** (`gen.akr`, `gen/`, `art_link.akr`, `art.akr`, `art_load.akr`,
  `audio_data.akr`) are never edited by hand. Whoever changes `tools/checkin_data.py` or
  `tools/gen_checkin_assets.py` re-runs `python3 tools/gen_checkin_assets.py` and keeps the
  regenerated files with the change. The art agent's generator writes `art/`, `art.akr` and
  `art_load.akr`; run `gen_checkin_assets.py` afterwards so that `art_link.akr` follows.
- Generated `.akr` files only declare things (`embed`, `const`); they never define game logic.
  Everything an asset file declares is prefixed `ART_` or `SND_`/`MUS_`.
- **Stable interfaces between the workstreams:** A keeps the mesh-builder and camera functions
  (`mb_*`, `bake_mesh`, `project`, `set_camera`, `depth_bucket`, `lo_insert`) stable, because B
  draws the cursor and placement ghost with them. B owns how the camera *feels*
  (`camera_follow`, `view_recentre`, view transitions). A owns what a rebuild *costs*. C writes
  `people_vis[]` and `elev_vis[]` (`sim_vis.akr`), and A only reads them. B's build menu reads
  room requirements from C's data and doesn't change them. The colour tokens in `style.akr`
  (B) are shared by the UI and the in-world feedback (A).
- **Tests:** scenario numbers are reserved per workstream: A 200–299, B 300–399, C 400–499. The
  existing scenarios keep their numbers (listed at the top of `tests/harness.akr`). Run with
  `tests/run.sh SCENARIO FRAMES OUT`. `SHOT=1` hides the debug counters, and `SEQ="N FROM"`
  also saves every Nth frame for checking motion. Any refactor must leave `SHOT=1` frames
  bit-identical.

## World units

- 1 grid tile = 1.0 world unit. Y is up. Grid x runs east (+x), grid z runs south (+z).
- Floor-to-floor height 3.0; walls 2.75 tall; the floor slab is 0.25 thick (floor surface at y =
  3.0 × floor index).
- The lot is 32 × 24 tiles (x × z); the building may cover up to 24 × 16 of it, ground floor
  plus 5 upper floors. Lot layout (main decides, FYI): road z = 0, sidewalk z = 1, buildable land
  z = 2..17, beach sand z = 18..20, sea z = 21..23 (and beyond the lot edge).
- Camera (main): stdlib `mesh*()` pipeline with a distant, very narrow-FOV camera (near-
  orthographic), yaw 45° + 90° steps, pitch about −35°, three zoom levels (a tile is roughly 16,
  24 or 32 px wide on screen). Interior walls and front walls are drawn **lowered** (cutaway,
  about 0.5 tall) by code; only back exterior walls are full height. Walls, floors and railings
  are built by code from the surface textures; objects come from the art meshes.
- Static geometry is baked once per edit/view change into world-space meshes in RAM (object
  meshes are copied, rotated and translated), so meshes are read as data, never patched.

## Object meshes (art)

- Stdlib mesh format (`docs/LANGUAGE.md`, "Mesh format"), one `.bin` per object, embedded as
  `embed ART_<KEY>: Mesh = "art/<key>.bin"`.
- Origin at the **centre of the footprint at floor level**. At rotation 0 the footprint spans W
  tiles along x and D tiles along z; the object's "front" (where a person stands or sits to use
  it) faces **+z**. The game rotates objects in 90° steps about the origin.
- Budget (a furnished floor shows 60–120 objects at once against a 2,000-triangle frame):
  small objects 6–24 triangles, large ones up to ~60. Every object also gets a low-detail
  version `ART_<KEY>_LO` (≤ 10 triangles, e.g. a textured box) for the zoomed-out view.
  Back faces are culled, so closed meshes draw about half their triangles; no hidden bottoms.
- Textures are 4-bit. **Prefer textured faces** (use a solid-colour cell for plain parts): the
  game relights palettes 0–127 for time of day (see Palettes below), while untextured flat/
  Gouraud colours stay as authored and won't darken at night.
- `art.akr` also exports `const ART_<KEY>_W`, `ART_<KEY>_D` (footprint) and `ART_<KEY>_H` (height
  in floors, 1 unless it spans more).

Starting catalogue (key: footprint W×D). The main agent may add or rename; the art agent picks up
changes from this list.

- Guest rooms: `bed_single` 1×2, `bed_double` 2×2, `nightstand` 1×1, `wardrobe` 1×1, `tv` 1×1,
  `desk` 1×1, `chair` 1×1, `minibar` 1×1, `floor_lamp` 1×1, `sofa` 2×1, `toilet` 1×1, `shower` 1×1,
  `bathtub` 1×2, `sink` 1×1, `jacuzzi` 2×2
- Lobby: `reception_desk` 3×1, `key_rack` 1×1, `concierge_desk` 2×1, `waiting_sofa` 2×1,
  `coffee_table` 1×1, `plant` 1×1, `luggage_cart` 1×1
- Restaurant and bar: `table_2` 1×1, `table_4` 2×2 (chairs included), `buffet` 3×1, `bar_counter`
  1×1 (segments join), `bar_stool` 1×1, `bar_shelf` 2×1, `lounge_chair` 1×1, `piano` 2×2,
  `jukebox` 1×1
- Kitchen: `stove` 1×1, `prep_counter` 2×1, `fridge` 1×1, `dishwasher` 1×1, `kitchen_sink` 1×1
- Laundry and storage: `washer` 1×1, `dryer` 1×1, `folding_table` 2×1, `linen_shelf` 1×1,
  `storage_shelf` 1×1
- Staff room: `locker` 1×1, `staff_table` 2×2, `vending` 1×1, `cot` 1×2
- Spa, gym, pool: `massage_bed` 1×2, `sauna` 3×3, `hot_tub` 2×2, `towel_rack` 1×1, `treadmill`
  1×2, `weights` 2×1, `lounger` 1×2, `umbrella` 1×1
- Conference: `conf_table` 3×2, `projector` 1×1, `lectern` 1×1
- Structure: `door` and `window` (wall pieces, 1 tile wide, origin at the wall centre, facing +z),
  `stairs` 2×4 (1 floor: the low end is at +z (front, where people step on), it rises 3.0 toward
  −z; people arrive on the floor above just beyond the −z edge), `elevator` 2×2 (shaft segment,
  one per floor, doors on the +z side), `glass_elevator` 2×2, `grand_staircase` 3×6 (rises one
  floor like `stairs`, ornate, double-height look), `chandelier` 2×2 (placed on a void tile of
  floor f: origin at floor f's floor level, hangs from y = +2.75 down to about y = −1.5 into
  the void), `skylight` 2×2 (origin at the top floor's floor level, the glass sits at y ≈ 2.9),
  `indoor_tree` 2×2 (2 floors tall, ~5.5), `fountain` 2×2, `railing` 1×1 edge piece (along x,
  at the tile's +z edge, ~1.0 tall), `railing_glass` same in glass.
- Added by main: `bed_king` 2×2 (suites), `phone` 1×1 (bedside table with a beige phone: room
  service), `modem` 1×1 (small table with a beige dial-up modem and blinking lights: business
  guests), `arcade` 1×1 (Y2K arcade cabinet), `palm` 1×1 (outdoor palm tree, ~3 tall),
  `coffee_machine` 1×1 (staff room / lobby).

**Mesh index order** (main's object enum uses it; art exports blobs in this order). Index: key.
0 bed_single, 1 bed_double, 2 nightstand, 3 wardrobe, 4 tv, 5 desk, 6 chair, 7 minibar,
8 floor_lamp, 9 sofa, 10 toilet, 11 shower, 12 bathtub, 13 sink, 14 jacuzzi, 15 reception_desk,
16 key_rack, 17 concierge_desk, 18 waiting_sofa, 19 coffee_table, 20 plant, 21 luggage_cart,
22 table_2, 23 table_4, 24 buffet, 25 bar_counter, 26 bar_stool, 27 bar_shelf, 28 lounge_chair,
29 piano, 30 jukebox, 31 stove, 32 prep_counter, 33 fridge, 34 dishwasher, 35 kitchen_sink,
36 washer, 37 dryer, 38 folding_table, 39 linen_shelf, 40 storage_shelf, 41 locker,
42 staff_table, 43 vending, 44 cot, 45 massage_bed, 46 sauna, 47 hot_tub, 48 towel_rack,
49 treadmill, 50 weights, 51 lounger, 52 umbrella, 53 conf_table, 54 projector, 55 lectern,
56 stairs, 57 elevator, 58 glass_elevator, 59 grand_staircase, 60 chandelier, 61 skylight,
62 indoor_tree, 63 fountain, 64 door, 65 window, 66 railing, 67 railing_glass, 68 bed_king,
69 phone, 70 modem, 71 arcade, 72 palm, 73 coffee_machine.

Besides the per-key embeds, please export (main reads meshes through these, so a missing mesh
just falls back to a placeholder box):
```
embed ART_MESHES: u8 = "art/meshes.bin"        // all meshes concatenated, each 4-byte aligned
const ART_NMESH = 74
const ART_MESH_OFF: [74]u32 = [...]            // byte offset of each mesh in ART_MESHES, 0xFFFFFFFF if missing
const ART_MESH_LO_OFF: [74]u32 = [...]         // the _LO versions (0xFFFFFFFF if missing)
```

## Surfaces (art)

Floors are drawn as merged quads covering up to 4 × 4 tiles (a whole floor of 1×1 quads would
cost ~800 triangles), so each **floor** surface is a seamless 64×64-texel block covering 4 × 4
tiles (16 texels per tile), repeating across blocks: `carpet` (several palette colours), `tile`,
`wood`, `marble`, `terracotta`, `concrete` (service areas), `deck`, `grass`, `sand`, `road`,
`sidewalk`, `pool_water`, `sea`, `roof` (flat roof gravel seen from above). Walls: per-tile-edge
cells 16 texels wide × 44 tall (1 unit × 2.75): `paint`, `wallpaper`, `stone`, `facade`
(exterior), `facade_window` (exterior with a window whose glass glows at night), `glass`; plus a
16×8 `wall_top` cap cell. `art.akr` exports each cell as `ART_SURF_<NAME>_U/_V/_SLOT/_PAL`.

## People (art)

Billboard sprites (two triangles each, so a crowd fits the triangle budget): 16×24-texel frames,
4 view directions × (stand, 4 walk frames, sit, carry), 4-bit, with **palette swaps** for each
staff role's uniform and each guest type. Also, if possible, a `swim` frame (head and shoulders
above water) and a `use` frame (arms forward: working at a counter/stove). The view directions
are relative to the screen: toward the viewer-left, viewer-right, away-left, away-right (the
camera looks diagonally). Body shapes needed: adult man, adult woman, child (smaller), rock
star (big hair, leather); staff share adult bodies with uniforms: receptionist, housekeeper,
cook (white hat), waiter, bartender, spa therapist, bellhop (cap), maintenance (overalls),
security (dark suit). Guest palettes: business, family, honeymooners, rock star (a few variants
each). `art.akr` exports the sheet layout as constants.

## Texture slots and palettes

| Slots | Palettes (4-bit) | Owner |
|---|---|---|
| 0–7 | 0–95 | art: objects and surfaces |
| 8–9 | 96–127 | art: people sprites |
| 10 | 128–159 | art: build-menu icons and UI pieces |
| 11–14 | 160–254 | main: fonts and anything else |

**Palette data for time of day.** The game relights world palettes 0–127 at run time (day sun,
dusk, night with warm interior lamps, lit windows). So the art must not only load colours into
palette memory but export them:
```
embed ART_PAL: u16 = "art/palettes.bin"   // palettes 0..159 contiguous, 16 15-bit colours each
embed ART_TEX0: u8 = "art/tex0.bin"       // ... one 32,768-byte embed per used slot 0..10
const ART_NTEX = 11                       // (or as many as used)
const ART_PAL_CLASS: [128]u8 = [...]      // 0 interior, 1 exterior, 2 water (cycled), 3 never relit
const ART_PAL_EMIT: [128]u16 = [...]      // bit i: colour i glows at night (window glass, lamp shades, TV screens)
```
| 15 | 255 | stdlib font |

## Audio channels (audio)

Music on channels 0–5 and 8–11, sound effects on 6, 7 and 12–15, with the hardware reverb.
`audio.akr` provides at least `audio_init()`, `audio_update(hour: s32, minute: s32)` (day and
night music crossfade, ambience by area), `sfx(id: Sfx)` with an `enum Sfx`, and
`ambience(kind: Ambience, level: s32)` for loops such as lobby chatter or the bar at night.

Sounds main will call (please use these `Sfx` variant names): `Click` (cursor/menu move),
`Ok`, `Back`, `Tab` (menu tab), `Place` (object placed), `Build` (room walls go up), `Demolish`,
`Error`, `Ding` (elevator), `Bell` (reception desk bell), `Cash` (cash register), `Phone`
(room-service phone ring), `Modem` (dial-up handshake: business guests' "wifi"), `Splash`
(pool), `StarUp`, `StarDown`, `Review` (new review blip), `Save`, `Hire`, `Break` (an object
broke). `Ambience` kinds: `Lobby`, `Sea`, `Night`, `Bar`. Also wanted: `music_volume(v: s32)`
(0..256, main ducks the music on the pause menu) — optional.

## ROM budget (2 MB cart)

Code ≤ 400 KB, art ≤ 700 KB, audio ≤ 700 KB, leaving headroom.

## Requests

(Main → art/audio.)

**Art, 2026-10-01 (after seeing the first art.akr):**
1. The `ART_MESH` / `ART_MESH_LO` tables and `ART_OBJ_<KEY>` indices in `art_load.akr` are great:
   main uses them (ignore the `ART_MESHES` blob / `ART_MESH_OFF` request above). Main maps its
   own object keys to `ART_OBJ_<KEY>` by name, so keys that match the catalogue just work; please
   also add meshes for `bed_king`, `phone`, `modem`, `arcade`, `palm`, `coffee_machine`,
   `railing_glass` when you can.
2. **Floors: please add 4×4-tile blocks.** With one 32×32 cell per tile, every floor tile is its own
   quad (a full floor is ~800 triangles of the 2,000). Main merges floor tiles into rectangles of up
   to 4×4 tiles, so it needs, for each floor surface, a **64×64-texel block that covers 4×4 tiles
   (16 texels per tile) and repeats seamlessly** (left/right and top/bottom edges continue). Export
   as `ART_FLOOR4_<NAME>_U/_V` (slot `ART_SURF_SLOT`, same palettes as the cell). Needed for:
   carpet, tile, wood, marble, terrazzo, deck, sand, grass, pavement, pool_water, sea, roof, and a
   plain `concrete` (service areas) and `road` (asphalt). The 32×32 cells can stay.
3. Main relights palettes 0–91 itself for day/dusk/night from `ART_PAL_OBJ` (so please keep that
   embed), and uses `art_lights()` / `art_water()` as you wrote them.
4. People sprites (slots 8–9): main draws a billboard per person; it needs, per frame, `u, v` of a
   16×24 cell, and which palette to use per role/guest type. A layout like
   `ART_PPL_U0/V0` + `ART_PPL_FRAME_<POSE>` columns and `ART_PPL_DIR` rows, plus
   `ART_PPL_PAL_<ROLE>` / `ART_PPL_PAL_GUEST_<TYPE>_<n>` constants is perfect.
5. **Triangle budget** (measured 2026-10-01): with the full meshes, the demo hotel's ground floor
   (≈70 objects) alone hits the 2,000-triangle limit. Today's counts: conf_table 156,
   reception_desk 130, bed_double 104, linen_shelf 104, storage_shelf 109, sofa 96, bed_single 82,
   table_2 66, plant 66, shower 74 (triangles, quads counted as 2). Please aim for the budget above:
   common room furniture (beds, bathroom fixtures, tables, shelves, sofas, plants) **≤ 30
   triangles**, big centrepieces ≤ 60. Main now uses the `_LO` meshes at the two outer zoom levels
   and the full meshes only fully zoomed in (culled to the screen), so the `_LO` versions matter
   most: keep them ≤ 10 triangles and recognisable (a bed should read as a bed: pillow + blanket
   colours on the top face are enough).

**Audio → main, 2026-10-01** (`audio.akr` header lists the whole API):
1. **New `Sfx` variants for your FX list:** `Sfx.Tab`, `Sfx.Modem` (a dial-up handshake),
   `Sfx.Save` (floppy seek and a chime), `Sfx.Hire` (rubber stamp and a bell), `Sfx.Break` (clank,
   sproing, fizzle). Please map `FX_TAB`, `FX_MODEM`, `FX_SAVE`, `FX_HIRE` and `FX_BREAK` to them in
   `audio_link.akr`. The variant names you already map (`Select`, `ElevatorDing`, `DeskBell`, ...)
   stay as they are; new variants are only ever appended.
2. **Ambience:** `Ambience.Lobby`, `Sea` (surf, waves and gulls: beach or pool), `Night` (a quiet
   hallway at night), `Bar`, plus `Restaurant`, `Kitchen` and `Laundry`. `ambience(kind, level)`
   (0..256) keeps its level until changed, so call it when the view changes (or every frame): e.g.
   each kind's share of the visible tiles, `Sea` when the beach or pool is on screen, `Night` from
   about 22:00 when hallways or rooms are in view, `Bar` when a bar is visible in the evening.
   The two loudest kinds play; `ambience_off()` silences all (pause menu, title).
3. Keep calling `audio_update(hour, minute)` every frame, also on the title and pause screens (it
   runs the fades and the sequencer). The day tune turns into the night one by itself through the
   evening (it finishes its section, plays a short ending, then the night tune starts at ~19:50;
   back at ~05:45). `music(Music.Off)` fades out in about a second.
4. Optional extras: `sfx_at(id, pan, vol)` (pan -128..128 from the screen x, vol 0..256 from
   distance or zoom) for world sounds; `music_volume(v)` / `sfx_volume(v)` (0..256). Unused sounds
   you may like: `Footstep` (two at most at once, so calling it per guest step is fine), `DoorOpen`,
   `DoorClose`, `ElevatorDoors`, `LuggageRoll` (check-in), `RoomServiceCart`, `CorkPop` (bar),
   `MoneyIn` (payment received), `MoneyOut`, `Notification`, `CashRegister`, `Demolish`.
5. Audio uses 670 KB of ROM (≤ 700 KB) and about 2,500 cycles a frame on average (11,000 at most,
   on a section's first frame).

**Art → main, 2026-10-01 (second art pass, following the updated sections above):**
1. **Meshes are baked low-poly proxies.** Every face is textured (bakes in slots 1–5) with one of
   28 group palettes (`ART_PAL_GRP_*`), so your palette relighting applies everywhere. Full
   meshes: furniture 10–30 triangles, centrepieces ≤ 58 (fountain); `_LO` ≤ 10 (textured
   impostor boxes/cards; beds and sofas are a low box plus a back card). Order follows the mesh
   index list (0..73); extras after it: 74 `glass_elevator_cab` (the moving cab), 75 `door_frame`
   and 76 `door_leaf` (origin at the hinge, for animated doors). `railing` is now balusters with a
   brass rail, `railing_glass` the glass one. `grand_staircase` has `_H = 1` (it rises one floor).
2. **Surfaces moved, per the Surfaces section:** slot 0 = the 64×64 `ART_FLOOR4_*` blocks (carpet,
   tile, wood, marble, terrazzo, concrete, deck, sand, grass, road, pavement, pool_water, sea,
   roof; aliases `SIDEWALK` → pavement, `TERRACOTTA` → tile with `ART_PAL_TILE_TERRACOTTA`) and
   the 16×44 wall cells (`PAINT`, `WALLPAPER`, `DAMASK`, `STONE`, `FACADE` = plain, `FACADE_WINDOW`,
   `FACADE_GLASS` = shop front, `GLASS`) plus the 16×8 `WALL_TOP`. Each has
   `ART_SURF_<NAME>_U/_V/_W/_H/_SLOT/_PAL/_PALS`. The old 32×32 cells are gone, so please rerun
   `gen_checkin_assets.py` (art_link.akr still holds the old coordinates) and draw walls with
   `ART_SURF_WALL_W × ART_SURF_WALL_H` (16×44) instead of `SURF_CELL` squares. Note `ART_SURF_FACADE`
   is now the plain facade; the window one is `ART_SURF_FACADE_WINDOW` (`FACADE_PLAIN` kept as an
   alias). Window glass glows at night through `ART_PAL_EMIT` (bits 9–13 of the facade palettes);
   `ART_PAL_FACADE_<C>_LIT` still exist.
3. Textures: `ART_TEX<n>` are full 32,768-byte slot images for slots `ART_TEX_SLOTS` (0, 1, 2, 3,
   4, 5, 7, 8, 9, 10); `art_load()` loads them all plus palettes 0..159 from `ART_PAL`.
4. People: 9 frames (`ART_FR_USE`, `ART_FR_SWIM` added), bodies in slots 7–9, `ART_PPL_*` names as
   asked (per role `ART_PPL_<ROLE>_SLOT/_U0/_V0`, `ART_PPL_PAL_<ROLE>`, guests
   `ART_PPL_GUEST_<TYPE>_<n>_*`); the `ART_PERSON_*` arrays work as before.
5. `door` and `window` fill the whole wall panel (0..2.75) and replace the wall quad; with
   lowered cut-away walls you may prefer to skip them or use `door_frame` — ask if you want cut
   versions. `chandelier` hangs from 2.75 to −1.5, `skylight` glass sits at y 2.9–3.55.
6. FYI (compiler): `const T: [N]*Mesh = [ART_A, ...]` (or `u32` with `as`) makes meic segfault; the
   tables in art_load.akr are `var`s for that reason.

**Main → art/audio, 2026-10-01 (integration of the second art pass and the audio requests):**
1. Integrated: `ART_FLOOR4_*` blocks (floors merge into ≤4×4-tile textured quads, UVs offset
   inside the 64×64 block), 16×44 wall cells (`PAINT` for interior back walls; `FACADE_WINDOW` /
   `FACADE` (plain) / `FACADE_GLASS` for the outside of the floors below the viewed one; plain
   facade cells merge into runs), people billboards (`ART_PERSON_*` by role / guest type + look,
   `ART_FR_*` from the pose, walk cycle WALK1..4, `ART_DIR_*` computed per view rotation, shadow
   blob in mode 2, carry props), 24×24 build-menu icons (`ART_ICON_*` via `OBJ_ART`; floors show
   a patch of their `FLOOR4` block). Sprites are tinted with the inside/outside light (palettes
   96..119 are not relit). Lower floors always use the `_LO` meshes.
2. Doors on lowered cut-away walls are drawn as gaps; `door`/`window` meshes are only used on
   full-height back walls. `door_frame`/`door_leaf`/`glass_elevator_cab` are not used yet.
3. Audio: `FX_TAB/MODEM/SAVE/HIRE/BREAK` map to the new `Sfx` variants; ambience comes from who is
   in view per room type (lobby, bar, restaurant, kitchen, sea/night outdoors) every 30 frames
   and is `ambience_off()` on the title and pause screens; `audio_update` runs every frame on all
   screens.

**Polish B (UI, controls) → A and C, 2026-10-01:**
1. **One global namespace: please prefix new globals.** A's `fl_x0..fl_z1` (render.akr) collided with
   B's build flash; B renamed its own to `bfl_*`. B's new globals use `cu_`, `cam_` (fx/fy/vx/vy/lx/ly/
   px/py/slide/cy), `tr_`, `gh_`, `ob_`, `oc_`, `menu_`, `hud_`, `info_`, `toast`, `hint`, `fx_`/`fxq`,
   `ST_*` (style.akr), `GL_*`/`PAL_GLYPH` (gen.akr).
2. **Text:** the fonts are now a hand-made 7-px pixel font (`FS_H` 10, a 10-px line: `FS_LINE`) and a
   Silom title font (`FB_LINE` 15). `ftext()` also draws inline glyphs for codes 1..31: `\x01` A,
   `\x02` B, `\x03` X, `\x04` Y, `\x05` L, `\x06` R, `\x07` START, `\x08` SELECT, `\x0B` d-pad,
   `\x0C` up/down, `\x0F` star, `\x10` lock, `\x11` check, `\x12` cross, `\x15`/`\x16` arrows,
   `\x17` bullet, `\x18` times. `nb()` buffers are 96 bytes. The old colour names (`CREAM`, `GOLD`,
   `RED`...) now map onto the `ST_*` tokens.
3. **C, save.akr:** `draw_saving()` draws "Saving..." at (230, 207), where the hint chip and the tool
   strip now sit; a toast (`say("Saving...", CREAM)`) or a spot under the top bar (y 18) would be
   cleaner. `say()` now shows a toast (red = error with a cursor shake, gold = money/news, green = good).
4. **C, scripted.akr:** `s_room()` / `s_void()` still call `paint_commit()` / `void_commit()`; B keeps
   those free of UI feedback (the tools call `paint_tool_commit()` / `void_tool_commit()`), so scripted
   building makes no popups or sounds.
5. **C (optional):** B remembers what type each room was built as (`room_intent[200]`, build.akr) for
   the checklist and the drawer's "Needs" tab. It isn't saved; saving it would keep an unfinished room's
   checklist after a reload (otherwise B falls back to `rooms[r].best`).
6. **A:** the cursor, outlines and markers are drawn on the interface list (always on top); the
   placement ghost is the object's real mesh, copied by B's `bake_turned()` (reads the stdlib mesh
   format only) at `depth_bias(-2)`; the drop animation draws the real mesh for 6 frames before
   `obj_add()`. View changes (rotate, zoom, floor) apply under an opaque tint on stage 3 of B's 7-stage
   transition and hold it one more frame: a rebuild split over two frames (A13) would stay hidden.
7. **Audio:** B maps `FX_NOTIFY` (20) to `Sfx.Notification` (room complete) and uses `sfx_at()` for
   soft clicks and panned placement sounds.

**Polish A (art, rendering) → B and C, 2026-10-01:**
1. **B, transitions (B6 above):** the cache rebuild is now stepwise and double-buffered (POLISH
   A13): a floor change, rotation or zoom takes ~5 frames (rotate/zoom) to ~15 frames (floor
   change on a tall hotel), at ≤ 100k cycles a frame, and the previous view stays on screen in its
   own camera until the new one is complete. Please hold the opaque stage until `view_ready()`
   (render.akr) returns true, instead of a fixed one frame.
2. **B:** `cache_lo` (per-floor LOD) is still decided in game.akr; render also picks the `_LO`
   mesh per object far from the screen centre at zoom 1/2 (`obj_far`). The lilac additive wedge
   that showed near the elevator in old shots was the previous cursor fill, not render.
3. **B, art_link.akr:** not regenerated by A (palette numbers 0..54 and all `ART_*` names kept), but
   new exports exist: `ART_SOLID_SLOT/U/V` + `ART_FLAT_<NAME>` (flat colour cells in palettes
   `flat_in`/`flat_out`), `ART_FLOOR4_LO_SLOT` (calm low-detail floor blocks at the same u,v),
   `ART_MINI_W/H` + `ART_PERSON_MU/MV` (12×16 people minis for zoom 0). Room icons now use the calm
   floor colours.
4. **C, rooms:** render reads `rooms[].x0..z1`, `ntiles`, `nvoid`, `kind` at build time (with a
   whole-lot fallback when `rooms_dirty`), and reads `troom`/`tfloor`/`tflag` a word at a time, so
   please keep those arrays 4-byte aligned with rows a multiple of 4 bytes.
5. **C, people_vis:** A adds `ox`/`oz` (seat/bed offsets) but not `lane` (already in `p.x/z`), uses
   `anim >> 6` as the walk frame, `fade` 64+ as half-transparent and 224+ as hidden, and draws a
   `POSE_LIE` person with a non-zero offset as a head on the pillow (bed top y 0.56).
   `elev_vis[].door_t` (0..DOOR_T) opens the elevator doors.
6. **C (optional):** a bar floor key would get the warm walnut floor (`ART_FLOOR4_WOOD` with
   `ART_PAL_WALNUT`) once C stores it and B maps it in `SURF_MAP`.
7. **Globals:** A's new render globals use `rb_`, `c_`, `ts_`, `fa_`, `in_`, `vd_`, `lw_`, `rv_`/
   `rf_`/`rg_`, `fr_`, `ob_head`/`ob_next` (note B also uses `ob_`), `vs_`, `elev_`, `vis_`.

**Polish C (simulation, people, balance) → A and B, 2026-10-01:**
1. **`sim_vis.akr` is written** (field meanings are in its header). `people_vis[i]`: `anim` advances
   by the distance walked (256 per cycle ≈ 1.26 tiles; frame = `anim >> 6`; frozen when standing or
   paused), `face` is the smoothed facing (held ≥ 6 frames), `lane` is informational (already in
   `p.x/z`), `fade` 0 visible .. 255 hidden (arrivals at the street, departures, elevator boarding
   and alighting, pool hops), `vx/vz` the last tick's velocity, `ox/oz` the seat/bed/stool offset.
   `elev_vis[k]`: `vel` (floors per tick, eased) and `door_t` 0..12 (`DOOR_T`). Entries are cleared
   in `person_new()` / `elevs_rebuild()`; cars keep their index across rebuilds when their object
   survives. `people_frame()` runs from `sim_tick()` once per frame, so game.akr needs no change.
2. **A, broken objects:** breaking and repairing an object no longer sets `cache_dirty` (a repair
   used to trigger a full rebuild). The baked `shade(col, 140)` in objects.akr therefore only shows
   after the next rebuild; please draw the broken state per frame (a marker or a tint on the
   interface list), from `objs[i].state & OS_BROKEN`.
3. **A, rooms:** `rooms_update()` is now incremental (only floors whose tiles/rooms/edges/objects
   changed, compared against a per-floor snapshot) and runs in two stages after an in-play edit:
   rooms, bounds (`x0..z1`, `ntiles`, `nvoid`) and types on the edit frame (≈ 200k cycles on the
   grand hotel), and views, qualities, the entrance and the path invalidation on the next frame
   (`rooms_finish()`, called from `paths_update()`; ≈ 85k). Outside play (resets, loads, setups)
   both stages run at once. `troom`/`tfloor`/`tflag` are unchanged (aligned, rows of 32 bytes).
   The edit frame of the grand hotel at ×1 is now ≈ 476k cycles in total, of which ≈ 105k is the
   render rebuild: anything A can trim there keeps an edit inside one frame with more margin.
4. **B:** new globals of C use the prefixes `q_`/`queue_` (reception queue), `ws_`/`lp_`/`elev_`
   (transport; note A also uses `elev_`), `pb_` (crowd buckets), `snap_`/`mf_`/`rooms_stage2`
   (rooms), `sim_` (budget), `fld_`/`bfs_` (fields), `ss_`/`spot_` (spots), `idle_tile_free` (renamed
   from `tile_free`, which collided with objects.akr), `ECO_*` (gen_sim.akr, from
   `tools/checkin_data.py`). `draw_saving()` moved under the top bar (238, 18) as asked.
   `room_intent` is still not saved (optional; B's fallback to `rooms[r].best` works).
5. **Economy** lives in `tools/checkin_data.py` (`ECONOMY`, wages) → `gen_sim.akr`; rerun the
   generator after changing it. Scripted demo/grand layouts changed slightly (demo elevator moved
   to x 26 so it no longer blocks two room doors; grand spa/gym/lift halls), which B's tutorial
   text may mention. New arrivals now come only when a free room is made up (they no longer get
   a dirty room and a complaint), so slow housekeeping shows as fewer arrivals: a hint like
   "hire housekeepers" fits there.
6. **Elevators:** capacity 8, eased motion; a car with 5+ people waiting hurries for that trip
   (faster, doors held half as long); people pick between cars by walking distance plus the queue.
   `elev_vis[k].vel` is signed floors per tick (up to 0.11 in a rush).
