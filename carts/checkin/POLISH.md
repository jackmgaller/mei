# Check-In! polish audit (2026-10-01)

The player's verdict was *"it needs a LOT more polish and love… it feels very janky… it looks
visually crowded."* They said the worst offenders were **(1) the cursor and building**:
moving the cursor, dragging rooms, placing and rotating objects. Next came **(2) people**
moving oddly. They picked the art direction **"Calm & clean"**: muted, harmonious palettes,
subtle textures, and bright accents only on what matters.

This document is the plan for three parallel workstreams:

- **A**: art direction and rendering.
- **B**: UI, UX and controls feel.
- **C**: simulation, people movement and balance.

Each finding comes with evidence: screenshots, frame sequences, and per-frame logs from the
scripted harness. Each also names its likely cause in the code. No code was changed. A scratch
copy of the cart was used for the logs and the mock-up.

**How it was audited.**

- About 60 static shots: title, new game, empty lot, room building, every room type, every
  floor, all three zooms and four rotations, the atrium, dawn, day, dusk and night, a busy
  hotel, every menu, overlay and pause page.
- Seven frame sequences, dumped every 1–4 frames, covering:
  - the cursor;
  - a room drag;
  - object placement;
  - people in the lobby;
  - the elevator;
  - view changes;
  - a room edit in a busy hotel.
- Per-frame CPU, people and cursor logs.
- Two simulated days in the demo and grand hotels, with state histograms.

The tooling is in the appendix. All evidence is in
`/private/tmp/claude-501/-Users-gallerdude-Documents-Projects/4d21ea8c-cfb2-4140-856f-98718c97d94d/scratchpad/checkin-polish/`.
The ten most telling images are `carts/checkin/screenshots/audit_*.png`.

**Good news first.** The engine has plenty of headroom.

- **CPU:** a steady frame at x1 costs 105–118k of the 500k cycles, even in the grand hotel
  with 60 guests.
- **Triangles:** 1,100–1,460 of the 2,000 budget.

So most of the polish below is affordable. The static-geometry cache, the object art at zoom 2,
the sound effects and the menu structure are solid foundations. Keep them.

---

## 1. Top 10 issues (what makes it feel janky and crowded)

Listed in the order the player weighted them: cursor and building first, then people, then
looks and UI.

### 1. The d-pad moves the cursor along screen diagonals, so rooms are hard to drag, and the camera fights it
**Evidence:** `screenshots/audit_02_dpad_drag_skews.png`, plus the scratch log `seq100/s.log`.

- Holding RIGHT moves the cursor along the world diagonal (−x, +z).
- Pressing DOWN mid-drag changes *both* room dimensions: 4×6 became 2×9 and then 3×10. You
  cannot draw a 4×4 room by pressing RIGHT and then DOWN.
- The camera is a dead zone (x 90–230, y 70–165). The cursor travels freely, then slams into
  the box edge and stays pinned there while the world drags at 4 px/frame.
- There is a one-frame overshoot: the cursor's screen x goes 230 → 232 → 231.
- At the lot edge, the world-space clamp makes a diagonal move slide sideways.

**Cause:**

- `build.akr` `cursor_update()` converts the stick into world deltas through `cam_yaw` (screen
  space).
- Diagonal input isn't normalised, so it is 1.41× faster.
- `camera_follow()` uses a hard box plus `dx/3 + sgn(dx)` chasing.
- `drag_rect()` spans the raw cursor tiles.

### 2. The cursor is barely visible and looks out of sync
**Evidence:** `scratchpad/checkin-polish/sh_cursor_zoom.png`, `sh_cursor_a.png`, and
`screenshots/audit_02…`.

- The cursor is a dim, additively blended tile fill, rgb(70, 70, 110), plus a 0.24-unit
  "dot". The dot is a flat world quad, so it renders as a 2–3 px yellow smear.
- On grass or marble the cursor nearly vanishes.
- The dot slides continuously inside the tile while the highlight snaps from tile to tile. It
  reads as jitter: the dot jumps from the left of the tile to the right and back.

**Cause:** `build.akr` `draw_build_overlay()`, in the `Inspect` branch and at "the cursor dot
itself". The generated diamond cursor frame `UV_CURSOR_U/V` (`gen.akr`) is never used.

### 3. Placing and rotating objects has no weight and gives wrong feedback
**Evidence:** `screenshots/audit_03_place_ghost_rotate.png`.

- **Ghost:** a featureless translucent box, not the object.
- **Rotation:** pivots on the footprint's corner tile, so the ghost jumps a tile at every turn.
- **Front marker:** the white front strip is invisible.
- **Placing:** the object appears instantly, with no drop, dust or cost popup. Then the ghost
  stays on top of the new desk and turns **red**, signalling "can't" right after a success.
- **Checklist:** while furnishing (the Object tool), the room panel hides its checklist and
  shows only "Lobby? 48 tiles quality 25".

**Cause:**

- `build.akr` `ghost_box()`.
- `place_commit()`: the origin is `cur_tx, cur_tz` and the footprint extends +x/+z through
  `obj_gw/obj_gd`.
- `rooms.akr` `draw_info()`: `if tool == Tool.Object { return }` before the "Needs" list.

### 4. Every build edit freezes the whole crowd and spikes the frame
**Evidence:** a measured log (scenario 123, the busy grand hotel).

- One plant was placed at frame 150. Walkers moving went 31 → 8 for about 10 frames.
- Those frames cost 348–448k cycles, and one frame overran.
- Even without edits, every ~23 frames 10–16 of 30 walkers stall for a frame. This is
  field-cache churn, and it shows as a periodic stutter.

**Cause:**

- `build.akr` `world_changed()` → `rooms_update()` → `paths_invalidate()` throws away every
  flow field.
- `people.akr` `person_move()` then stands everyone still, with `POSE_STAND`, until `path.akr`
  rebuilds fields under `BFS_CYCLES = 70000` a frame.
- `NFIELD = 64` with LRU eviction causes the steady churn.

### 5. People stack on top of each other and march in lockstep
**Evidence:** `screenshots/audit_04_people_stacked_lockstep.png` and
`screenshots/audit_05_elevator_queue.png`.

In 552 logged frames of the lobby, there were on average **29 overlapping pairs per frame**,
with a maximum of 120. Groups that shared the *exact* same position:

- 7 staff on the elevator door tile, for 151 frames;
- 16 people on one road tile at the shift change;
- housekeepers walking in identical pairs.

**Cause:**

- **Same speed:** all staff walk at exactly `p.speed = 0.045` (`person_new`).
- **Same spawn tile and time:** `staff_arrive()` uses `place_at(i, entrance_tile())`, one road
  tile (16, 0), for everyone on the same minute.
- **Reception queue:** every arriving guest goes to `spot_tile(desk, 0)` (`guests.akr`
  GS_ARRIVE), one tile.
- **Elevator queue:** everyone waits on `elev_door_tile()` (`transport.akr`).
- **Companions:** they walk *to the leader's tile* (`companion_tick`: `go_to(i, lt)`).
- **Idle staff:** they wander to random public tiles on any floor, 25% of the time
  (`staff.akr` `staff_idle` → `random_public_tile`). This overloads the single elevator: by day 6–15 (up to 16)
  people waited for it at any time in the two-day run.

### 6. Movement and animation are robotic: grid snaps, a global walk clock, teleports
**Evidence:** `audit_04`, `sh_people_walk.png`, and the person logs.

- **Grid snapping:** people walk tile-centre to tile-centre, in Manhattan steps only. They turn
  90° instantly at each centre, and long diagonals become staircases. One walker made 13 turns
  in 420 frames.
- **Walk cycle:**
  - It runs off `tick_count / 7`, not distance, so feet slide at x2/x4.
  - People keep "walking" in place while the game is paused (speed 0, pose WALK).
  - Walkers flip to the STAND frame whenever a field isn't ready.
- **Teleports:**
  - into the pool (`start_use` `place_at`);
  - in and out of the elevator, where people vanish and reappear;
  - at the end of stairs;
  - companions catching up after 60 frames.
- **Sprite scaling:** sprites draw at 0.67× (zoom 0) and 1.39× (zoom 2) of the 16×24 art. The
  uneven scaling makes texels shimmer.
- **Clipping:** billboards are cut by furniture in front of them (the planter in `audit_04`).

**Cause:**

- `people.akr` `person_move()`, which uses a per-axis clamp toward the next centre.
- `draw_sprite()` (`fr = WALK1 + (tick_count / 7 …)`, `h = ppu * 1.45`, `bucket - 3`).
- `guests.akr` `start_use()` / GS_SWIM.
- `transport.akr` `elev_exchange()`.

### 7. The world is a wall of saturated, high-contrast texture with no hierarchy
**Evidence:** `screenshots/audit_01_default_view_crowded.png`,
`audit_06_upper_floor_checkerboard.png`, `audit_08_zoom0_texture_aliasing.png`.

- **Floors:**
  - Carpets ramp from near-black (#2A0608) to mid red, with gold motifs (#F0C060).
  - The corridor carpet is plum with pink motifs.
  - Terrazzo has random high-contrast chips on about 14% of texels.
  - Grass has random noise and daisies.
- **Upper floors:** a red/blue/green/purple checkerboard, boxed by dark wardrobes and cyan
  shower glass.
- **Zoom 0:** 16-texel tiles drawn at 11 px alias into moiré speckle.
- **Measured:** the mean absolute Laplacian of the view ("HF" in the appendix) is 56–89.
  Saturation is 33–48%.
- **Seam:** the lot's textured grass doesn't match the flat-colour surroundings (`newgame.png`).

**Cause:**

- `tools/gen_checkin_art.py`: the floor blocks (`floor_block` carpet, terrazzo, grass) and the
  `CARPETS`, `tile_pal`, `marble_pal` palettes.
- The floor-key mapping in `art_link.akr` sends "Corridor: carpet" → `CARPET_PLUM`.
- `render.akr` `build_surroundings()` draws flat colours.

### 8. UI that is always on screen, and flickers
**Evidence:** `audit_01`, `sh_people_a.png` (frame 188), `dayreport.png`, `hud_top.png`.

- **Room panel:** shows whenever the cursor is inside a room. It is 112 × 70–110 px in the
  top-right, about 13% of the screen, even for a finished room ("Needs: ✓ ✓").
- **Hover flicker:** when anyone walks under the cursor, the panel switches to that person and
  back.
- **A does nothing on rooms:** `info_open` only affects objects.
- **Top bar:** 50% transparent, so the world shows through behind the money and stars, and the
  unlit stars are nearly invisible.
- **Hint bar:** always on. Its text is cut off ("…Y+Up/Down: z") because the string is 49
  characters and the `nb()` buffers stop at 46.
- **Overlaps:** the day report sits under the room panel.

**Cause:**

- `rooms.akr` `draw_info()`.
- `game.akr` `draw_hud()` (`ui_grad(…, 0)` uses blend mode 0).
- `ui.akr` `sappend()` (the `n < 46` limit).
- `overlays.akr` `draw_ticker()`.

### 9. The build menu covers the place you're building on, and truncates its own items
**Evidence:** `screenshots/audit_07_build_menu.png`, `menu_x3.png`, `sh_menu.png`.

- The panel is 304×112 px at y = 118, covering 47% of the screen, including the cursor, which
  the camera keeps at y ≈ 120.
- Names are cut off: "Room: red carpe", "Room: green carpe".
- The lock badge ("3★") is drawn over the item name.
- There is no scroll indicator. The Rooms tab has 13 items and shows 9.
- Tabs are tiny dots plus "< L … R >".
- The hot-pink selection pill is the loudest thing on screen.
- Rooms are listed as *floor finishes* ("Room: marble"), not room types, so "build a lobby"
  has no matching item.

**Cause:** `build.akr` `draw_build_menu()`, `menu_fill()`, `MENU_COLS/ROWS`.

### 10. Cutaway and occlusion: tall walls in front of rooms, monolithic furniture, a box elevator, a murky atrium
**Evidence:** `screenshots/audit_10_tall_walls_occlude.png`, `audit_05`, `sh_atrium.png`.

- **Full-height walls in front of rooms:** any wall whose camera-side tile is indoor and whose
  far side is outdoor is drawn at full height. So a corridor's wall facing a 2-tile gap becomes
  a 2.75-tall beige slab *in front of* the suite behind it.
- **Monolithic furniture:** wardrobes (dark-brown monoliths) and shower glass sit at the room
  fronts and hide the guests.
- **Elevator car:** an untextured flat box that pops over the shaft. A lilac wedge sticks out
  of the shaft door.
- **Atrium:** the floors below are drowned under a 50% navy haze, rgb(24, 34, 70).

**Cause:**

- `render.akr` `build_walls()`, the `full` predicate.
- `draw_lower()`.
- `transport.akr` `draw_elevators()` (`mb_box`, flat colours).

### Also noticed (in the punch list below)
- **View changes are hard cuts.**
  - Rotate, zoom and floor change happen in one frame, with a cache-rebuild spike.
  - The demo hotel's floor change costs 440k cycles.
  - In the grand hotel, floor changes cost 370–470k cycles (94% of the budget) on F1–F5.
- **x4 speed drops frames:** about 9% of frames after init on the grand hotel's F3 at dusk
  (1,143 of 1,300 ticks presented, about 46 of them init), and about 2% on the ground floor.
- **The time of day reads flat.**
  - Dawn and dusk look identical.
  - The interior barely changes at night.
  - Glows are round blobs.
  - During dawn and dusk the cache rebuilds every 30 game minutes (2 s at x4) to relight the
    flat colours, which is another hitch.
- **The hotel feels empty.** The restaurant is empty at 13:20 and the bar nearly empty at 22:20
  in the grand hotel with 60 guests. At any time, 7–11 guests are waiting for food and 18–25
  are walking somewhere.
- **The economy is flat.** The demo hotel loses about $460 a day at x4. Reviews average
  2.5–2.7★.
- **Guests "sleep" sitting upright next to the bed** (`POSE_LIE` uses the SIT frame on the
  use-spot tile).

---

## 2. Full punch list

**Priority:**

- **P0:** fixes the janky or crowded feel. Do these first.
- **P1:** clearly visible polish.
- **P2:** nice to have.

**Effort:**

- **S:** under 2 h.
- **M:** half a day.
- **L:** 1–2 days.

File names are relative to `carts/checkin/` unless they start with `tools/`. Files marked
*(new)* are created by the shared-first step in section 5.

### Workstream A: art direction and rendering

| ID | P | Effort | Fix | Files |
|---|---|---|---|---|
| A1 | P0 | M | **Calm floor palettes** per the art-direction table (section 3): one hue family per surface, at a mid-light value, with saturation ≤ 25%. Turn the corridor carpet from plum to greige. Guest-room carpets become sage, slate and dusty rose. The lobby marble becomes cream with soft veins. | `tools/gen_checkin_art.py` (`CARPETS`, `tile_pal`, `marble_pal`, wood/deck/grass/sand palettes) |
| A2 | P0 | S | **Texture noise caps:** pattern contrast ΔL ≤ ±8% around the base. Motifs are tone-on-tone (ΔL ≤ 6%), with no single-texel speckle: drop the terrazzo chips, grass daisies, sand shells and carpet dots, or keep them within ±4%. Grout and plank lines ≤ 12% darker than the base. | `tools/gen_checkin_art.py` (`floor_block` carpet, terrazzo, grass, sand, wood, deck, marble) |
| A3 | P0 | M | **Zoom-0 aliasing:** add a low-detail 64×64 block per floor (an average colour plus at most a 2-tone tile or plank hint) and use it at zoom 0 and for the floors below. | `tools/gen_checkin_art.py`, `render.akr` `build_floor_surfaces()` |
| A4 | P0 | S | **Readable cutaway:** lowered walls get a light face and a **dark warm cap** (about #4A4038), and are slightly thicker (`WALL_T` 0.07 → 0.09). That outline is what separates rooms, so floors no longer need loud colours to do it. Mark door gaps with a threshold strip. The mock-up proves the cap alone helps (`audit_09`). | `render.akr` (`WALL_IN`, `CAP_COL`, `low_wall_*`) |
| A5 | P0 | M | **Full-height wall rule:** raise a wall to full height only on the building's real back edge: B is outdoor *and* no indoor tile of that floor lies within 4 tiles beyond it along the view direction. Otherwise lower it. This fixes `audit_10`. | `render.akr` `build_walls()` |
| A6 | P1 | M | **Furniture that doesn't wall rooms in:** in-room furniture max height about 1.5 units. Wardrobes become lighter wood. Showers become a thin light frame with pale glass rather than cyan blocks. Lift the darkest object values to L ≥ 18% and cap saturation at about 45%. Accents stay on interactive or important items (reception bell, bar lights). | `tools/gen_checkin_art.py` (object palettes, wardrobe/shower/shelves meshes) |
| A7 | P1 | S | **Ghost the floors below** instead of the navy haze: mix toward a light cool grey (#C8CCD4 at about 40%) so the atrium reads as architecture, not a pit. | `render.akr` `draw_lower()` |
| A8 | P1 | M | **Time of day:** make dawn (peach) and dusk (amber, then violet) different, the night exterior dark (#3A4878), and the night interior warm. Glows get a smaller radius (about 0.8 tile) and alpha ≤ 40%. To remove the 30-minute relight rebuild: draw the flat-coloured geometry (low walls, caps, slab edges, surroundings) with solid palette cells, so relighting is palette-only and never sets `cache_dirty`. | `lighting.akr` (`LK_*`, `lights_update`, `draw_glows`), `render.akr` |
| A9 | P1 | S | **Lot edge:** draw off-lot ground with the same textured blocks (or a calmer flat colour that matches). Outline the buildable area (z 2..17) with a low curb or hedge line so a new player sees where to build. | `render.akr` `build_surroundings()` |
| A10 | P1 | M | **Elevator art:** draw the cab with the existing `glass_elevator_cab` mesh (textured), animate the door leaves from `e.door` / `elev_vis[k].door_t`, and fix the lilac wedge at the shaft door. Show the cab only where visible: a glass shaft, or an open door. | `people_draw.akr`, `tools/gen_checkin_art.py` |
| A11 | P1 | M | **People rendering:** use integer sprite scales. Zoom 1 = 1:1. Zoom 2 is 1:1 (people slightly smaller), or authored 32-px frames. Zoom 0 gets authored 12×16 mini frames. Add a 1-px dark outline palette entry and a soft shadow at every zoom (currently zoom 0 has none). Sort from the foot point pulled 0.5 tile toward the camera, so furniture in front doesn't slice sprites. People get the highest saturation in the scene. | `people_draw.akr`, `tools/gen_checkin_art.py` (people sheet) |
| A12 | P1 | S | **Glows:** only on lamps that are on, none on floors under the ghosting, warmer, and smaller. | `lighting.akr` `draw_glows()` |
| A13 | P1 | M | **View-change cost:** floor change and rotate rebuilds cost up to 470k cycles. Get them under 300k: keep the lower-floor ordering table per view floor, or split the rebuild across the 2–3 dark frames of B8's transition. | `render.akr` `rebuild_cache()` |
| A14 | P2 | M | **Back walls:** the plain beige full-height walls fill the top of many views. Add a baseboard, a 2-tone wainscot or per-room paint tints at ≤ 4% noise, and consider 2.0-unit-tall back walls at zoom 0. | `tools/gen_checkin_art.py` (`wall_cell`), `render.akr` `wall_piece_*` |
| A15 | P2 | S | **Zoom-2 LOD pop:** `draw()` flips *all* objects to `_LO` meshes when the triangle count goes over 1,930. Fall back per object by distance from the screen centre instead. | `game.akr` (`draw()`; ask B), `render.akr` |
| A16 | P2 | S | **Water:** lower the saturation of the pool and sea and the frequency of caustic sparkles. They twinkle noisily at zoom 0. | `tools/gen_checkin_art.py` (`water_frames`, the `pool_water` and `sea` blocks) |
| A17 | P2 | S | **Sleeping and sitting sprites:** add a lying frame (or a "head on pillow" overlay) for beds, and seat offsets per object, for C10. | `tools/gen_checkin_art.py`, `art.akr` exports |

### Workstream B: UI, UX and controls feel

| ID | P | Effort | Fix | Files |
|---|---|---|---|---|
| B1 | P0 | M | **Grid-stepping cursor on the d-pad.** Each d-pad direction steps one tile along a grid axis, rotated per `view_rot` so UP is the axis pointing screen up-right and RIGHT points screen down-right. Repeat after 12 frames, then every 4. The analog stick keeps free movement but eases (4 frames) to the tile centre when released. Normalise diagonals. Dragging RIGHT then DOWN must make an exact W×H rectangle. | `build.akr` `cursor_update()`, `drag_rect()` |
| B2 | P0 | M | **Camera follow:** replace the dead-zone box with a critically damped follow toward `cursor + velocity × lookahead`, with a small soft zone (±24 px). Accumulate sub-pixel motion so the integer `pan_x/y` (cache shifts) stay whole pixels. No overshoot or bounce. Clamp so the view never pans to empty void past the lot plus 6 tiles. | `build.akr` `camera_follow()`, `view_recentre()` |
| B3 | P0 | M | **Cursor visuals:** a crisp 2-px warm-yellow (#FFE88C) tile outline with corner ticks, plus a small floating marker above the tile that bobs 1 px. It stays visible over objects (draw it in the UI layer). Ease the highlight between tiles over 3 frames. Remove the flat dot. **Drag rectangle:** outline + per-tile dots + a preview of where the walls will rise + red ✕ on invalid tiles, with the size and cost chip pinned above the far corner. Use the unused `UV_CURSOR` art or line quads. | `build.akr` `draw_build_overlay()` |
| B4 | P0 | M | **Placement juice and correctness:**<br>1. The ghost is the **real mesh**: `bake_mesh` into the per-frame list with `FACE_SEMI`, tinted green or red.<br>2. Pivot about the **footprint centre**, so the anchor tile stays fixed when rotating.<br>3. Show a visible front arrow and the use-spot markers.<br>4. On A: draw the new object dynamically for 8 frames before it is baked into the cache. It drops 0.3 units with a 1-frame squash, gets a dust puff and a "−$1,200" float-up.<br>5. Hide the ghost for about 12 frames after a placement, or until the cursor moves; never show red over what you just placed.<br>6. Keep the room checklist visible while furnishing (compact, with icons). | `build.akr` (`ghost_box`, `place_commit`, `draw_build_overlay`), `hud.akr` (new) |
| B5 | P0 | S | **Quiet default HUD:**<br>1. The room, person and object card opens only on A and closes on B, or when the cursor leaves the room.<br>2. No hover switching.<br>3. Opaque slim top bar.<br>4. No hint strip in Inspect mode; tools show a one-line strip with button glyphs.<br>5. Fix truncation: raise the `nb()` buffers to 96 bytes and keep hints short. | `hud.akr` (new: moved `draw_hud`, `draw_info`), `ui.akr` (`nb`, `sappend`) |
| B6 | P1 | M | **Build drawer:**<br>1. At most 88 px tall, at the bottom.<br>2. Tab strip of 16-px icons with the tab name on the selected one.<br>3. A single row of 24×24 item icons (6–7 visible) with ◀ ▶ scroll arrows.<br>4. One detail line: name, price, size, "completes: Lobby".<br>5. Lock shown as a small padlock plus ★ count, never over text.<br>6. Calm selection: 1-px warm outline + 15% fill.<br>7. When the drawer opens, the camera nudges the cursor to y ≈ 80. | `build.akr` `draw_build_menu()`, `menu_*` |
| B7 | P1 | M | **Room-type-first building:** the Rooms tab lists *room types* (Lobby, Guest room, Restaurant…), each with a default floor finish (the finish can be changed later in a sub-row). After the drag, the room's checklist stays pinned and the furniture tab opens filtered to its required items. When the room becomes valid: a "ding", the label pops up over the room, and the checklist chip turns green and fades. | `build.akr`, `hud.akr`; room data from C (`tools/checkin_data.py`) |
| B8 | P1 | M | **View transitions:** hide rotate, zoom and floor changes behind a quick 8-frame transition. Fade to an ambient tint over 3 frames, rebuild during the covered frame, then fade in over 4. For floors, also slide the new floor 12 px vertically (via `pan_y`). A tiny HUD floor indicator animates G → F1. | `build.akr` (`rotate_view`, `zoom_view`, `set_floor`), `hud.akr` |
| B9 | P1 | S | **Controls:** SELECT tap cycles the speed (Pause/x1/x2/x4) with a HUD flash. SELECT held + d-pad picks overlays. Keep Y tap = turn (the object in the Object tool, else the view). Y + ←/→ turns the view and Y + ↑/↓ zooms everywhere. Show these in a START → "Controls" card. | `game.akr`, `build.akr`, `screens.akr` |
| B10 | P1 | S | **Toasts:** slide in under the top bar over 6 frames, stack (max 2) and fade out. Colour by kind: info is cream, money is gold, an error is red with a small shake of the cursor marker. The day report becomes a toast card that never overlaps the info card. | `hud.akr`, `overlays.akr` `draw_ticker()` |
| B11 | P1 | S | **Panel style:** flat charcoal (#20222C, about 90%), 1-px light top edge, cut corners, no glossy gradient, no hot pink (section 4). | `ui.akr` (`panel`, `panel_glass`, `ui_sel`) |
| B12 | P1 | M | **Pixel fonts:** a hand-made small font with 7-px caps and a 10-px line (it replaces Arial Rounded 9 with its 13-px line). Title font 11–12 px. 1-px drop shadow. This frees about 25% of every panel's height. | `tools/gen_checkin_assets.py` (`render_font` → a bitmap glyph table) |
| B13 | P1 | S | **Edge feedback:** at the lot edge the cursor marker bumps (a 2-px shake and a soft click) instead of sliding silently along the clamp. | `build.akr` |
| B14 | P1 | S | **First-time flow:** on a new lot, show the lot outline (A9), an entrance arrow at the lobby door spot, and a first-goal card: "Build a Lobby: X → Rooms → Lobby". | `screens.akr` `new_game()`, `hud.akr` |
| B15 | P2 | S | **Pause pages:**<br>1. Rating: numbers on the score bars; fix the review-star overlap (8-px steps for 16-px icons); fill the empty lower half or shrink the panel.<br>2. Staff: role icons and a clearer cursor.<br>3. Ledger: right-aligned columns with subtle row shading.<br>4. Day report: no title clipping ("Day 1 is done" overruns the panel). | `screens.akr`, `overlays.akr` |
| B16 | P2 | S | **Overlays:** fade in over 6 frames, add a legend chip, de-collide the labels, and use calmer tints (≤ 35% alpha). | `overlays.akr` |
| B17 | P2 | S | **Title:** restyle the panel to the new style, keep the logo clear of the hotel, and slow the backdrop drift. | `screens.akr` `draw_title()` |

### Workstream C: simulation, people movement and balance

| ID | P | Effort | Fix | Files |
|---|---|---|---|---|
| C1 | P0 | M | **No crowd freeze on edits:** double-buffer the flow fields. A stale field stays usable until its replacement is ready. Only invalidate floors whose `pass` changed. Someone at a tile centre with no field keeps the current heading if the next tile is walkable, instead of freezing. Target: an edit frame ≤ 250k cycles and ≤ 2 stalled walkers. | `path.akr` (`paths_invalidate`, `field_for`, `paths_update`), `people.akr` |
| C2 | P0 | M | **Field churn:** remove the periodic 10–16-walker stalls. Share fields per destination class (a station object or a room door), raise `NFIELD` if RAM allows, and prefetch the field of the *next* goal. Never drop to `POSE_STAND` while waiting a few frames for a field. | `path.akr`, `people.akr` |
| C3 | P0 | M | **Spread people out:**<br>1. Reception **queue slots**: a line of tiles extending from the desk spot; guest k stands at slot k and advances.<br>2. Elevator **waiting slots** around the door (3×2).<br>3. Companions take an **offset** beside the leader (formation), not the leader's tile.<br>4. A personal **lane offset** (±0.2 tile, perpendicular to travel, from `look`).<br>5. **Speed variance** for staff (±10%).<br>6. Light **separation**: slow or yield when someone is within 0.35 ahead. | `guests.akr` (GS_ARRIVE/QUEUE, `companion_tick`), `transport.akr`, `people.akr`, `staff.akr` |
| C4 | P0 | M | **Smooth paths:** steer toward a look-ahead point along the path, with a corner-cut radius of about 0.35 tile. Ease in and out over about 6 frames at starts and stops. Hold a facing for at least 6 frames. Allow 8-neighbour steps in open areas, with corner checks, to kill staircase diagonals. | `people.akr` `person_move()`, `path.akr` (`bfs_floor` neighbours, `path_next`) |
| C5 | P0 | S | **Walk cycle by distance:** advance `people_vis[i].anim` by the distance moved this frame, and pick the frame from it. It freezes when not moving or when paused, and scales correctly at x2/x4. | `people.akr`, `sim_vis.akr` (C writes `anim`), `people_draw.akr` (A reads it) |
| C6 | P1 | M | **No teleports:**<br>1. Pool: a 12-frame hop arc in, and climbing out.<br>2. Elevator: board by stepping onto the door tile, then a 6-frame fade; exit with a fade-in and a step out.<br>3. Stairs: keep walking off the top (no snap).<br>4. Companions catch up with a fade.<br>5. Spawn and despawn with a fade at the street edge. | `guests.akr` (`start_use`, GS_SWIM), `transport.akr` (`elev_exchange`), `people.akr` (`stairs_step`, `place_at`) |
| C7 | P1 | M | **Calmer staff:**<br>1. Stagger shift arrivals by a random 0–20 game minutes.<br>2. Enter via the lobby door or a service door, not one road tile.<br>3. Idle staff go to the staff room, or to a "home" spot in their department on their own floor.<br>4. Only security patrols.<br>5. No cross-floor trips while idle; this is the source of most elevator crowding. | `staff.akr` (`staff_arrive`, `staff_idle`), `sim.akr` (`entrance_tile`) |
| C8 | P1 | M | **Elevator feel:** ease the car's velocity (accelerate, cruise, decelerate). Capacity 6 → 8, or speed it up when queues pass 6. The dispatcher prefers the floor with the most waiting. Give the grand demo hotel a second elevator. Hand A `e.door` and `e.pos` for the art. | `transport.akr`, `scripted.akr` |
| C9 | P1 | M | **Lively public spaces:** guests should be *seen*. Mealtime restaurant visits (7–9, 12–14, 18–21). Lingering activities in the lobby (sofa, fountain, chatting in pairs), bar evenings and the pool afternoon. Fewer long in-room idles during the day. Target: in scenario 110 at 15:00, at least 15 guests on screen on G. | `guests.akr` (`guest_decide`, `want_food`, `want_fun`), `sim.akr` |
| C10 | P1 | M | **Use poses on the furniture:** sleeping guests are drawn *in* the bed (an offset onto the bed footprint, the lie frame from A17). Sitting guests are on the chair, stool or sofa seat. They stand back on the use spot when done. | `guests.akr` (`start_use`, `finish_use`), `people.akr` (a visual offset field) |
| C11 | P1 | M | **x4 without frame drops:** spread per-guest minute work over frames, and cap `sim_tick` cost per frame (when over budget, carry ticks into the next frame instead of dropping a frame). Target ≥ 99% of frames presented at x4, grand hotel F3, 17:00–21:00. | `sim.akr` `sim_tick()`, `people.akr` `people_tick()` |
| C12 | P1 | M | **Economy and reviews:** the demo hotel loses about $460/day, and reviews average about 2.5★. 7–11 guests are waiting for food at any time. Tune waiter throughput, room-service time, wages vs prices and guest budgets, so a sensible demo hotel profits about 10–20% a day and reviews average 3.5★ or more. | `tools/checkin_data.py` (new), `sim.akr`, `guests.akr`, `jobs.akr` |
| C13 | P2 | S | **Entrance:** spawn guests at the street edge in front of the lobby's outside door (not a fixed (16, 0)). Drivers too. | `sim.akr` `entrance_tile()` |
| C14 | P2 | S | **Sleeping at night:** light sleepers' noise complaints are fine, but have sleepers who are woken briefly sit up (a visual cue), and keep corridors quieter after 23:00 (staff idle off-floor). | `guests.akr`, `staff.akr` |

---

## 3. Art direction: "Calm & clean"

**The principle:** a quiet, light, harmonious world, so that people, the cursor or selection,
and problems are the only things that pop. This is Theme Hospital's clarity at PlayStation
resolution. The mock-up `screenshots/audit_09_calm_mockup.png` shows the current build on the
left and a 30-minute palette-only experiment on the right. It drops HF from 67.5 to 47.1 and
saturation from 48% to 31% on the demo hotel, and from 84.5 to 51.4 and 33% to 30% in the busy
lobby at zoom 2.

### Value and colour hierarchy (back to front)

| Layer | Value (L) | Saturation | Texture contrast | Notes |
|---|---|---|---|---|
| Outdoors (grass, sand, road, sea) | 35–75% | ≤ 30% | ±6% | Recedes; same texture on and off the lot |
| Floors below (atrium, lower floors) | ghosted | −50% | n/a | Mix 40% toward #C8CCD4 (not the navy haze) |
| Floors of the viewed floor | 60–85% | ≤ 25% | ±8%, motifs ≤ 6% | One hue family per room type |
| Cutaway walls | face 75–85%, cap 25–30% | low | flat | The dark cap is the room outline |
| Back (full-height) walls | 75–85% | ≤ 20% | ≤ 4% + a baseboard | Never in front of rooms (A5) |
| Furniture | 25–75% | ≤ 45% | baked shading only | Darkest value ≥ 18%; in-room height ≤ 1.5 units |
| People | full range | highest in scene | n/a | 1-px outline + soft shadow |
| Selection, cursor, problems | bright | accent | n/a | Warm yellow #FFE88C, red #F07060, green #7CD892 |

### Palette per floor and room type
These are the mock-up values (`work/mock/checkin/art/pal_obj.bin`), as base colours. Generate
each palette as a ramp of ±8% around the base.

| Floor / room | Surface | Base | Notes |
|---|---|---|---|
| **G public** | Lobby marble | #E0D9CC | Veins #CFC6B6, joints 8% darker |
| | Public corridor terrazzo | #D4CEC4 | Chips ±4%, no black or red flecks |
| | Restaurant wood | #B48E64 | Planks ±10% |
| | Bar wood (new variant) | #8C6A4E | Cosy, darker; give the bar its own floor key |
| | Spa tile | #B7D3CF | Pale aqua |
| | Gym | #8C9096 | Rubber |
| **G service** | Kitchen, laundry, staff concrete and tile | #AEACA6 / #D6DADB | Cool, neutral: back of house reads as quieter |
| **Outdoor** | Deck | #A8845E | |
| | Pool | #5FB4C8 | Less saturated than now |
| | Sea | #3E7FA8 | |
| | Grass | #76935E | |
| | Sand | #DCC89E | |
| | Pavement | #BDB7AB | |
| | Road | #5E5E64 | |
| **F1–F4 guest floors** | Corridor carpet | #B4A898 | Greige, tone-on-tone border |
| | Rooms | sage #9AAB8C, slate #8A9BB0, dusty rose #B88C84 | One per room, or one per floor as a floor "theme" |
| **F5 suites** | Floor | walnut #8C6A4E, or deep teal carpet #5E8A86 with cream marble baths | |
| **Walls** | Cutaway face | #E6DED2 | |
| | Cutaway cap | #4A4038 | |
| | Back-wall paint | #E2D6C4 | With a #B8A890 baseboard |
| | Facade stucco | #E8DCC8 | Windows #6C88A0 by day, #FFD890 lit at night |

### Lighting
- **Day (8–17):** neutral white inside and out.
- **Golden hour (17–19):** exterior #FFD8A8.
- **Dusk (19–20:30):** exterior #9890C8; interior lamps on (#F8E4C0).
- **Night:** exterior #3A4878; interior #F0D8B0 at about 95%; glows small and soft.
- **Dawn (5–7):** exterior peach #F0C0A0, with no violet, to distinguish it from dusk.
- **Implementation:** relight palettes only (A8). Nothing should rebuild the cache because the
  clock moved.

### How much UI is visible by default
A 14-px top bar and the cursor. Nothing else until the player asks, or something needs their
attention: a toast, a problem icon over a person or object.

### The mock-up (how it was made, to reproduce or extend)
The scratch copy is `work/mock/checkin` in the scratchpad.

1. **Palettes:** `pal_obj.bin` and `palettes.bin` were re-generated per floor palette. Each
   colour was set to `base × (1 + k × (L − median L) / median L)`, with k = 0.10–0.30 and a
   clamp of 0.75–1.18. That keeps each texture's structure but shrinks its range to one calm
   hue. Furniture palettes 55–82 got a 6% value lift and ×0.85 saturation; the dark woods and
   sofas got 18%.
2. **Code:**
   - `draw_info()` returns unless `info_open`.
   - Opaque 16-px HUD bar.
   - No hint bar in Inspect mode.
   - Only the lit stars are drawn.
   - `WALL_IN` = 0x9AA6B4, `CAP_COL` = 0x3A4250 (BGR).
   - The Inspect cursor is a 4-quad outline with no dot.
   - Haze rgb(40, 44, 60).

---

## 4. UI and HUD redesign (320×240)

```
┌──────────────────────────────────────────────────────────────┐ y=0
│ $ 12,345 (+120)        ★★★☆☆          Day 3  14:20  ▶▶   F2 │ 14-px opaque bar (#1C1E28),
├──────────────────────────────────────────────────────────────┤ 1-px #3C4050 divider
│  [toast: "Lobby complete! +reputation"]  ← slides in, y=18     │
│                                                              │
│                     (world, ~210 px tall)                     │
│   info card (on A) ┌────────────┐  ← opens on the side away  │
│                    │ Lobby  ✓   │    from the cursor,        │
│                    │ 80 tiles q78│    max 120×72              │
│                    └────────────┘                            │
│                                                              │
│ [A Place  Y Turn  B Done]  ← tool strip, only with a tool    │ y=228, 12 px
└──────────────────────────────────────────────────────────────┘ y=240
Build drawer (X): y=152..240 (88 px): tab icons row (16 px) / item carousel (24-px icons) /
detail line "Reception desk  $1,200  3×1  completes: Lobby"
```

- **Always on:** the top bar (money with a delta flash, lit stars only plus half stars, the
  clock, a speed glyph, a floor badge) and the cursor.
- **On demand:**
  - the info card (A);
  - the build drawer (X);
  - overlays (SELECT hold);
  - the pause pages (START);
  - toasts (events, 3 s);
  - problem markers over people or objects: small 8-px icons from the existing unused `IC_*`
    set (bed, food, broom, wrench, zzz).
- **Fonts:** a small pixel font with 7-px caps and a 10-px line (body); a 12-px title font.
  1-px shadow. No sizes in between. Numbers use tabular widths.
- **Panel style:**
  - Flat charcoal #20222C at about 90%, a 1-px #5A5E70 top edge, 2-px cut corners and 4-px
    padding.
  - Text cream #F4EEDC, secondary #A8A8B4, gold #FFD860, good #7CD892, bad #F07060.
  - Selection: a 1-px warm outline (#FFE88C) plus a 15% fill. No gradients or gloss.
  - The art agent's `ART_UI_*` kit (panel, buttons, moods, build, demolish, rotate) is unused.
    Either adopt it in the new style or remove it from ROM.
- **Cursor and placement feedback:**
  - Tile outline + floating marker (B3).
  - Highlight eases between tiles.
  - The ghost is the real mesh, pivoting at its centre (B4).
  - A drop, a puff and a cost float-up on placing.
  - A drag rectangle with a wall preview.
  - Invalid tiles show ✕ with a short reason toast: "Can't build on the road".
  - A "room complete" celebration.
- **Speed and pausing:** SELECT cycles the speed; the HUD speed glyph flashes.

### Controls review

| Input | Now | Proposed | Why |
|---|---|---|---|
| D-pad | Moves the cursor in screen space (diagonal in the world) | **Steps along grid axes, tile by tile** | Rectangles and furniture rows become straight; this is the #1 complaint |
| Stick | Free cursor | Free cursor, eases to the tile centre on release | Precision without twitchiness |
| A | Act / drag | Same; in Inspect, opens the info card | Gives A a visible result on rooms |
| B | Back | Same; also closes the info card | |
| X | Build menu | Build drawer | |
| Y tap | Turns the object (Object tool) or the view | Same | Context is shown in the tool strip |
| Y + ←/→, Y + ↑/↓ | Turn the view / zoom | Same (the hint is no longer truncated) | The chord is fine once it's documented |
| L / R | Floor down / up | Same, with a slide transition (B8) | |
| START | Pause menu: speed, staff, prices, rating, ledger, save | Same, plus a Controls card | |
| SELECT | Cycles overlays | **Tap: speed** (Pause/x1/x2/x4). **Hold + d-pad:** overlays | Speed is the most frequent sim action; it's now buried 2 levels deep |

**Awkward today:**

- The d-pad diagonals.
- A does nothing on rooms.
- Changing speed needs START → Speed → ←/→.
- The zoom chord appears only in a truncated hint.
- The menu's L/R tab dots are unreadable.

---

## 5. File ownership and shared-first changes

### Shared-first changes: done (2026-10-01, before parallel work)
They are pure restructuring. With the original harness, every frame and every log line
(including the cycle counts) of the 33 scenario runs and of the real cart (title → new hotel
→ build menu → pause) is bit-identical before and after. With the new split harness, all
`SHOT=1` frames are identical. Only the harness's own dispatch overhead (+82 cycles a frame)
shows, in the CPU counters (`SHOT=0`).

- **SF1 Test tooling.**
  - `mei-headless --dump-every N PREFIX [--dump-from F]` saves `PREFIX_00012.ppm` (tick
    number).
  - `tests/run.sh` takes `SEQ="N FROM"` and converts the frames to PNG.
  - `tests/harness.akr` keeps the infrastructure: fixtures, `script_from`, periodic logs.
  - The scenarios moved to `tests/scen_ui.akr` (B: 1–7, 40, 48, new 300–399),
    `tests/scen_art.akr` (A: 21, 25, 41–47, new 200–299) and `tests/scen_sim.akr` (C: 10–15,
    20, 22–24, 30, 90–95, new 400–499).
  - Each `scen_*` file provides `scen_<ws>_init()`, `scen_<ws>_pad(f)` and
    `scen_<ws>_hook()`.
  - The audit scenarios (appendix) are *not* ported yet. Each workstream ports the ones its
    acceptance checks need into its own range.
- **SF2** `hud.akr` (B) now holds `draw_hud`, `goal_text`, `goal_update`, `money_s` and
  `draw_debug` (from `game.akr`), and `draw_info` (from `rooms.akr`).
- **SF3** `people_draw.akr` (A) now holds `SKIN`, `person_col`, `people_drawn`,
  `draw_people`, `spr_dir`, `sprite_dirs`, `STAFF_PK`, `person_kind`, `sprite_quad`,
  `draw_person`, `draw_sprite`, `carry_col`, `world_quad`, `lo_insert` (from `people.akr`) and
  `draw_elevators` (from `transport.akr`).
  - The new visual state is in **`sim_vis.akr`** (C writes, A reads): `people_vis[128]:
    PersonVis { anim, face, lane, fade, vx, vz, ox, oz }` and `elev_vis[16]: ElevVis { vel,
    door_t }`, indexed like `people[]` and `elevs[]`. They are zero, and nothing uses them yet.
  - They are parallel arrays imported last rather than new `Person`/`Elev` fields. Growing
    `Person` changed the cycle counts (the larger `memset` at every reset and spawn) and
    shifted the frame timing. Growing `Elev` shifted the global layout by a cycle in the
    cache rebuild.
  - When C starts writing them, clear `people_vis[i]` in `person_new()` and `elev_vis[k]` in
    `elevs_rebuild()`.
- **SF4** `tools/checkin_data.py` (C) holds `USES`, the object flags, `TABS`, `OBJ`, `FLOORS`,
  `SURF`, `ROOMS`, `GUESTS`, `STAFF` and `REVIEWS`. `tools/gen_checkin_assets.py` (B) imports
  it and keeps the string interning and output. The regenerated `gen.akr`, `gen/` and
  `art_link.akr` are byte-identical.
- **SF5** `style.akr` (B) holds the `ST_*` colour tokens from sections 3 and 4. Nothing uses
  them yet; switch over piece by piece.
- **CONTRACT.md** "Files" now has the A/B/C table below, plus the stable interfaces and the
  test number ranges.

### Ownership after the shared-first changes

| Owner | Files (in `carts/checkin/` unless noted) |
|---|---|
| **A: art and rendering** | `tools/gen_checkin_art.py`; `art/`, `art.akr`, `art_load.akr` (generated); `render.akr`; `lighting.akr`; `objects.akr` (B and C call its footprint and bake functions but don't edit them); `people_draw.akr`; `tests/scen_art.akr` |
| **B: UI, UX and controls** | `build.akr` (cursor, camera follow, tools, ghost, drawer); `ui.akr`; `hud.akr`; `style.akr`; `screens.akr`; `overlays.akr`; `game.akr` (frame loop and input; A and C request changes); `audio_link.akr` (UI sound hooks); `tools/gen_checkin_assets.py` (fonts, icons, panels, cursor; writes `gen.akr`, `gen/`, `art_link.akr`); `tests/scen_ui.akr`; `src/platform/headless.c` (`--dump-every`) |
| **C: simulation and people** | `people.akr`; `sim_vis.akr`; `path.akr`; `transport.akr`; `guests.akr`; `staff.akr`; `jobs.akr`; `sim.akr`; `rooms.akr`; `world.akr`; `save.akr`; `scripted.akr`; `tools/checkin_data.py`; `tests/harness.akr` and `tests/run.sh` (infrastructure); `tests/scen_sim.akr` |

**Interfaces to keep stable:**

- A keeps the `mb_*` / `bake_mesh` / `project` / `set_camera` / `depth_bucket` / `lo_insert`
  APIs stable; B uses them for the ghost and cursor.
- B owns the camera's *feel* (`camera_follow`, `view_recentre`, transitions). A owns the
  rebuild *cost*.
- C writes `people_vis[]` and `elev_vis[]` (`sim_vis.akr`). A only reads them, plus `Person`
  and `Elev`.
- B's room-type-first flow (B7) reads room requirements from C's data. B doesn't edit the data.
- Generated files (`gen.akr`, `art_link.akr`, `art.akr`) are never hand-edited.

---

## 6. Acceptance checks

Run each check with the SF1 tooling (`tests/run.sh`, `SEQ=`, `--dump-every`). "Before" numbers are from this audit.

### A: art and rendering
- **Noise and saturation metric** (appendix script; scenarios 118 and 110):

  | View | HF now | HF target | Saturation now | Saturation target |
  |---|---|---|---|---|
  | Demo hotel G, zoom 1 | 67.5 | ≤ 45 | 48% | ≤ 30% |
  | Grand hotel F2, zoom 1 | 55.9 | ≤ 42 | 39% | ≤ 26% |
  | Grand lobby, zoom 2 | 84.5 | ≤ 50 | n/a | n/a |
  | Grand hotel G, zoom 0 | 88.8 | ≤ 50 | n/a | n/a |

- **Side by side with `audit_09`:** the new art must look at least as calm as the mock-up.
  People must be the most saturated objects in frame.
- **`audit_10` re-shot** (showcase scenario 117 at zoom 2): no full-height wall in front of the
  suite.
- **Atrium** (harness 44 and 45): the lobby fountain and tree are recognisable through the void
  from F3.
- **Time of day** (scenario 110 at 6, 13, 19 and 22 h): dawn ≠ dusk. At night the exterior is
  clearly darker than the interior. Zero `cache_cycles` changes between 17:00 and 21:00 at x4
  (per-frame PERF log).
- **Rebuild cost:** floor up and down G → F5 at zoom 0 and 2 (scenario 108) has every frame
  ≤ 300k cycles.
- **Elevator** (scenario 103 at the elevator, 26, 9): the cab is textured, the doors animate,
  and there is no lilac wedge.
- **People** at zoom 0/1/2: crisp (integer scale), shadowed, never sliced by furniture in front.

### B: UI, UX and controls
- **Grid stepping:** from a new game, Paint tool, press A, RIGHT×3, DOWN×3, release. The result
  is exactly a **4×4** room. Same with RIGHT×5 then DOWN×2 → 6×3. Check every `view_rot`.
- **Camera:** in a cursor log over 300 frames of held RIGHT then UP+RIGHT (scenario 100):
  - the screen position stays within ±30 px of the centre;
  - the screen x never reverses direction while input is held (no 230 → 232 → 231);
  - the pan acceleration is ≤ 1 px/frame².
- **Cursor sheet** (`sh_cursor_zoom`-style, every 2 frames): the outline is visible on grass,
  marble and carpet, with no dot drifting inside the tile.
- **Placement sequence** (scenario 102): the ghost is the desk mesh, and its anchor tile is
  unchanged across 4 rotations. On A: the drop and the cost float-up play, and the ghost is
  never red over the new desk. The checklist is visible in the Object tool.
- **Default screen** (scenario 118, Inspect): only the top bar is visible. With 60 people
  walking past the cursor for 600 frames, the info card changes 0 times.
- **Strings:** a test scenario passes every UI string (hints, menu names, panel lines) through
  `text_w()` and checks it against its box. It prints any overflow, and there must be 0.
- **Drawer** (scenario 113 for all 9 tabs): ≤ 88 px tall, the cursor tile visible above it, no
  truncated names, the scroll arrows show when there are more items.
- **Transitions** (scenario 105, every frame): the rotate, zoom and floor changes show the
  8-frame transition. No visible hard cut.
- **SELECT** cycles the speed, and the HUD speed glyph updates in the same frame.

### C: simulation and people
- **Overlap** (scenario 103 lobby log, 552 frames):
  - average pairs within 0.3 tiles: 29 now, target **≤ 3**;
  - exact-position groups larger than 1 that last more than 30 frames: many now, target
    **0**, except companions seated together.
- **Edit freeze** (scenario 123): stalled walkers after the edit ≤ 2 for ≤ 2 frames (was 23
  for about 10). The edit frame is ≤ 250k cycles (was 448k).
- **Steady stalls:** no frame with more than 3 walkers waiting for a field (was 10–16 every
  ~23 frames).
- **Smoothness** (person logs):
  - facing changes only at path turns, held ≥ 6 frames;
  - frame-to-frame screen speed varies ≤ 1 px except at starts and stops, which ease over
    ≥ 4 frames;
  - zero `place_at` teleports more than 0.6 tiles while visible (log them).
- **Paused:** at speed 0 over 120 frames, the sprite frame of every person is unchanged.
- **Elevator** (scenario 121, two days): the number of people waiting for the elevator is ≤ 6
  at peak (was up to 16), with no staff idle trips.
- **Liveliness:** scenario 110 at 13:00 has at least 4 diners in the restaurant. At 22:00 the
  bar has at least 4 guests. At 15:00, at least 15 guests are visible on G.
- **x4:** scenario 124 (F3, 18 h, x4, 1,300 frames) presents ≥ 99% of frames after init (was
  about 91%).
- **Economy** (scenario 122, demo hotel at x4 for 3 days): the daily profit is > 0 and the
  review average is ≥ 3.5★ by day 3.

---

## Appendix: the audit tooling

**Frame sequences** (SF1, done):

- `build/mei-headless cart.mei --frames N --dump-every K PREFIX [--dump-from F]`.
- `SEQ="K F" tests/run.sh SCENARIO FRAMES OUT` writes `OUT_seq_00012.png` and so on.
- Tile the frames into contact sheets with Pillow. The audit's helpers `sheet.py` and `up.py`
  are in the scratch `checkin-polish/tooling/` folder.

**Audit scenarios** (scratch `work/checkin/tests/audit.akr`). Pad scripts are `(frame, pad)`
pairs with A = 16, B = 32, X = 64, Y = 128, L = 256, R = 512, ↑ = 1, ↓ = 2, ← = 4, → = 8.

| ID | Setup | Input / log |
|---|---|---|
| 100 | New game | → 20–80, ↑→ 80–140, ↓← 200–260. Logs `cur_x/z`, the cursor's screen position and `pan_x/y` every frame |
| 101 | New game | X, →, →, ↓, A (marble), ← 60–76, A 90, A+→ 96–130, A+↓ 130–150, release 160 |
| 102 | Marble room 10,3–17,8; tool Object = reception desk at 12.5, 5.5 | Y at 30/50/70, → 80–96, A 110, ↓ 120–136 |
| 103 | `scen_grand(f, 60, h)`, zoom 2, cursor (x, z) | Logs every person each frame: kind, mode, pose, dir, x, z, screen position, state |
| 105 | `scen_hotel(1)` | Y+← (rotate) at 32, Y+↑ (zoom) at 62, R at 90, L at 120. Per-frame PERF (`cpu_used`, triangles, `cache_cycles`) |
| 108 | `scen_grand(0, 60, 15)` | R every 20 frames from 40 (G → F5) with PERF |
| 110 | `scen_grand(f, guests, h)`, zoom, rot, cursor x | Static shots |
| 111 | `scen_grand(0, 60, 15)` | Pause page 0–4 at `scen_t` 60 (run 200 frames) |
| 112 | `scen_grand(0, 60, 15)` | Overlay 1–4 |
| 113 | `scen_hotel(1)` | Build menu open on tab 0–8 |
| 114 | `scen_grand(0, 60, 15)`, zoom 2 | Info card: room, person, object |
| 117 | Showcase on an empty lot | Conference, storage, suite with jacuzzi, terracotta dining with piano, two guest rooms |
| 118 | `scen_hotel(1)` | Floor, zoom, hour |
| 121 / 122 | Grand / demo hotel at speed s | State histogram every 240 frames (guest and staff states, modes, stacked pairs, money, reviews) |
| 123 | `scen_grand(0, 60, 15)` | `s_obj(OB_PLANT, 0, 18, 8, 0)` at frame 150; logs walkers moving vs stalled and `cpu_used` per frame |
| 124 | `scen_grand(f, 60, h)` at speed s | Per-frame PERF |

Note: the audit used IDs 100–124 in a scratch copy. Renumber them into your workstream's range
when porting. Scenarios ≥ 100 must call `new_hotel_state(); start_play()` first. The harness only does
that for IDs < 90. The grand hotel's setup takes about 45 updates, so allow more frames.

**Noise and saturation metric (Pillow + numpy):**

```python
a = np.asarray(Image.open(f).convert('L').crop((0, 20, 320, 224)), float)
hf = np.abs(4*a[1:-1,1:-1] - a[:-2,1:-1] - a[2:,1:-1] - a[1:-1,:-2] - a[1:-1,2:]).mean()
sat = np.asarray(Image.open(f).convert('HSV').crop((0, 20, 320, 224)), float)[..., 1].mean() / 2.55
```
