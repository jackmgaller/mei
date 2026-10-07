# Shrine town: design specification (A + C)

The whole shrine of direction A (courtyard, terraced precinct, ridge and pagoda, west woods and
their treetop walkway, the sacred cedar's basin, the fox grove and its torii tunnel, the back
mountain with its stage, the falls and the stream) placed unchanged in shape inside the temple
town of direction C (a station plaza, a covered shopping street to the great torii, back alleys,
a canal with machiya and a sento, a park, a schoolyard, cemetery terraces and an elevated railway
that wraps the south and east). It is one level of the future city world: 320 × 384 m, 30 cells,
five stars.

Written as a paper design, now built as a grey box: the world `shrinetown` in the movement
garden (README.md). Every height, gap and glide below was checked against the player's moves in
`carts/garden/tuning.akr` and `carts/garden/shrine/STYLE.md`; the coordinates and checks live in
`layout.py`, the pictures are drawn from it by `tools/draw.py`:

- `design/top.png`: the map: zones, contours, routes by layer, stars, red coins, shortcuts,
  glides, numbered places, the edges and the 64 m cell grid.
- `design/oblique.png`: the level from the south-east.
- `design/sections.png`: three cuts: south-north on the axis (x = 160), west-east through the
  basin (z = 296) and west-east through the town (z = 70).
- `design/assets.md`: the asset list and how to split it.

**Where the grey box changed the plan,** this document says so in place (marked *Grey box:*)
and section 12 lists every change, with the cart scenarios that measured it. Where a number
below and section 12 disagree, section 12 and `layout.py` are the level as built.

Numbers in brackets like (23) are the numbered places on `top.png`; ★1–★5 are the stars.

![The plan](design/top.png)

![From the south-east](design/oblique.png)

---

## 1. Design philosophy

### 1.1 A playground, not a path

The built shrine is one trail with a mandatory pond. This level has no required order and no
single trail. Concretely:

- From the spawn there are seven directions within 10 seconds (section 4.1).
- Every zone touches at least three others on the ground, and most also on a roof or tree layer.
  The only places with a single way in are deliberate: the sacred cedar's hollow (★4) and the
  sento chimney's top (a red coin).
- The precinct has five ways in (main gate, west gate, east water gate, north gate, over the
  4.4 m retaining wall); the mountain has five ways up (section 5, ★3).
- The pond is optional: it is the shortest way from the east gate to the road, not a gate.
- Shortcuts (A–E) shorten loops that already exist. None of them is needed to reach any star.
- No zone is a dead end except a goal. Where a walk ends (the bamboo grove's top, the falls
  cave), it ends on a view or a secret, and a glide or a drop takes you back.

### 1.2 One spine, two grains

The axis x = 160 runs from the station (1) up the shotengai (5), through the great torii (15),
the gate (17), the temple (19) and the north gate (22) to the pagoda terrace (23), and on in line
to the basin (32) and the stage (35). It is the one route you can always find: stand anywhere on
it and look north or south and you see its next landmark.

Across it the town has a rectangular grain (alleys east-west, the canal north-south, the
viaduct as the south and east frame) and the forest an organic one (contours, trails that follow
them, clearings). The player learns two kinds of navigation in one place: counting blocks in the
town and following landmarks and slopes in the forest.

### 1.3 Landmarks and sight lines, one per quarter

| Landmark | Height | Where | Seen from |
|---|---|---|---|
| Pagoda | 45 m (base 15; *grey box:* the real pagoda on a terrace cut 5 m into the ridge) | (178, 262) | everywhere south of the ridge; from the spawn only its finial's top shows over the arcade gate (below) |
| Stage hall | deck 60, roof about 78 (set by the asset) | (154, 360) | the whole level (far stand-in from the town) |
| Falls | 48 → 12 m white line | (214, 340) | the east half, the cemetery, the pond |
| Sacred cedar | 58.8 m (base 13) | (154, 296) | the ridge, the walkway, the stage; the only tree taller than the pagoda |
| Sento chimney | 18.2 m | (23.5, 68.5) | the west half of the town |
| Fire tower | 15.2 m | (102, 74) | the alleys and the danchi |
| Building | 18.3 m, 58 m long | x 186–200 | the plaza, the courtyard, the school |
| School | 18.9 m | (273, 71) | the east and the cemetery |
| Viaduct with its trains | deck 9 m | south and east edges | everywhere in the town; it is the level's frame |

The spawn sight line, checked: eye 1.6 m at z 22 looking north. The arcade gate's top (8.3 m at
z 62) cuts the view at a rise of 0.167; the pagoda (z 262, 240 m away) is visible above
1.6 + 0.167 × 240 = 41.8 m, so its fifth roof (44.0) and finial (50.0) show over the gate.
*Grey box:* with the real pagoda (roof 5 at 19.4 above its base) on the terrace at 15, roof 5
is at 34.4 and the finial's top at 45: only the finial's top 3.2 m clears the gate, and the
reader's far ring of three (`wp_far_ring`) does not draw row 4 from row 0 at all (section 12). The
temple ridge (29.5 m at z 218) is just hidden behind the gate; the torii's red frame sits inside
the arcade's mouth. The stage hall's roof (about 78 m, 343 m away) is above everything (rise
0.22).

### 1.4 Three layers and a summit

| Layer | Heights | What it is made of | How you get onto it |
|---|---|---|---|
| Ground | 0 (town), 0.6 (courtyard), 5.0 (terrace), 13–20 (basin, ridge) | streets, gravel, trails, water (wading) | walking |
| Roofs | town 5.6–9.5 (shops, konbini, alleys, machiya, arcade, viaduct 9), towers 15–19; shrine 11.6–29.5 | flat or ≤ 28° roof collision, wires and lantern strings as rails | bounce awnings, vending machines, poles, ladders, double jump + grab |
| Trees | decks 9–28 m | treetop decks on giant cedars, rope bridges, the rope to the cedar | the walkway's foot at the courtyard, the ridge's west end, a trunk pole |
| Summit | 44–64 | the stage, the falls' top, the shoulder | stairs, kicks, ladder, the long trail |

**Up is earned, down is free.** Every climb uses a move (double jump and grab, a pole, kicks, a
bounce); every high place has a glide line down that lands somewhere useful (section 4.4). The
glider sinks 2 m/s at 8 m/s, 4 m out per metre down, and opens at the apex of a double jump, so
every glide starts 3.4 m above its take-off.

### 1.5 Town and forest: contrast, then blend

The town is low, dense, horizontal, busy and loud: roofs at 6–9 m, people, trains every 90 s, a
grain of 10 m shop frontages. The forest is high, sparse, vertical and quiet: cedars of 25–41 m,
decks, water you hear before you see. Crossing from one to the other always goes through a
threshold you can name: the great torii, the precinct's gates, the arched canal bridge (26), the
cemetery's gate, the bamboo. Each is a small version of the seamless edges between levels
(section 7): the scene changes behind something, and you know you are somewhere new.

Where they blend, on purpose:

- **The canal lane** (x 52–60): machiya backs on one side, the west woods on the other, stone
  lanterns along it.
- **The courtyard's open sides**: west into the woods trail, east onto the pond bank.
- **The cemetery terraces** climb out of the town's grid into the mountain's east shoulder.
- **The bamboo grove** grows from the park and the sake brewery up to the north-west edge.

### 1.6 How the player learns the space

1. The spawn shows the goal: the pagoda over the arcade, the stage on the skyline.
2. The first roof is 3 seconds away and teaches the roof layer (the awning bounce onto the
   shotengai roofs).
3. Coins are breadcrumbs on lines that are not obvious: along the wires, up the pagoda's tiers,
   across the kick pair, on the glide line from the temple ridge.
4. Each star teaches a skill the next can use: ★2 rails and roofs; ★1 tier climbing and the
   glide from height; ★3 three faces of one mountain; ★4 seeing something from one place and
   reaching it from another; ★5 the whole map at speed.
5. Things are seen before they are reached: the cedar's glow through its roots, the rope with
   its white paper streamers from the walkway, the falls' cave from the stream.

### 1.7 Rewarding curiosity

- Secrets sit at the end of side lines (section 6.3): the cave behind the falls, the culvert
  under the road, the crown deck's view, the sake brewery's roof.
- Every summit has a view and a way down.
- Shortcuts open from the far side, so finding the far side is the reward.

### 1.8 What "open" means here

Measurable: seven directions in the first 10 s; every star reachable by at least two routes
except ★4 (one, by design); at least three ways into every zone; no invisible walls. The level's
boundaries are things: the viaduct (south, east), the canal's culvert grille (south-west),
road-works barriers (west road), the mountain's rims (north). Open does not mean empty: inside
the town, alleys and shop rows still frame views and hide what is behind them, which both reads
as a real town and keeps the frame budget (section 8).

### 1.9 Built for the budget

Heavy zones are kept apart (the shotengai and the precinct are 60 m apart across the front road
and the courtyard); high places have nothing heavy within 30 m; streets dog-leg so no view runs
more than about 64 m along a dense street except the axis, whose contents are budgeted.

---

## 2. Overview

### 2.1 Size, coordinates, heights

- **320 × 384 m**, x east 0–320, z north 0–384, heights in metres above the street (0).
- **Cells:** 64 m (WORLDKIT.md recommends 64 until stage 2 measures; the shrine uses 64), so
  **5 × 6 = 30 cells**, `c{col}_{row}` with col = x / 64, row = z / 64. The built shrine has 15.
- Direction A's shrine sits at A's x + 64, z = 280 − A's y; its internal numbers are unchanged
  except where this document says so.
- Lowest: −1.2 (canal and pool beds); highest ground 64 (north-east summit); highest things:
  the stage hall's roof (about 78), the sacred cedar (58.8), the pagoda (45; the plan's 50).

| Level | Height (m) |
|---|---|
| Canal water / bed | −0.4 / −1.2 (0.8 m deep: wading, jumping allowed) |
| Pond water / bed | 0 / −1.1 to −1.7 (as built) |
| Town, front road | 0 |
| Courtyard, park | 0.6 |
| Precinct terrace | 5.0 (retaining wall 4.4 above the courtyard; white wall 2.6 on top) |
| Temple podium / ridge | 8.6 / 29.5 |
| Cemetery terraces | 1.8 to 16.2 in nine steps of 1.8 m |
| Basin / fox grove / falls pool | 13 / 15 / 12 |
| Ridge / pagoda terrace | 20–22 / 15 (*grey box:* cut into the ridge, section 12) |
| Torii tunnel landing | 54.5 |
| Stage deck | 60.0 (stilts 12 m at the front) |
| Falls lip | 48 |
| North-east summit | 64 |

### 2.2 Zones and cells

| Row (z) | c0 (x 0–64) | c1 (x 64–128) | c2 (x 128–192) | c3 (x 192–256) | c4 (x 256–320) |
|---|---|---|---|---|---|
| r5 (320–384) | bamboo top, soft edge | torii tunnel top, landing | stage, hall, ladder A | falls, kick chimney, rope bridge | shoulder top, path out |
| r4 (256–320) | bamboo, canal spring | fox grove, decks 5–6, rope deck | pagoda, ridge, basin, sacred cedar | gorge, falls pool, dead cedar C | east shoulder trail |
| r3 (192–256) | bamboo foot, sake brewery | west woods, decks 3–4, crown deck, west gate | temple, corridor halls, north gate | bell, east gate, stream | cemetery top |
| r2 (128–192) | park, yagura, watermill | west woods, decks 1–2 | courtyard, side halls, gate | side hall E, pond, zig-zag bridge | cemetery, viaduct leaving |
| r1 (64–128) | sento, machiya, road W | alleys N, fire tower, woods' foot | shotengai N, arcade, torii | building, gym, pond S, culvert | school, overpass, underpass seam |
| r0 (0–64) | machiya, canal, viaduct | danchi, pachinko, alleys S | station, plaza, shotengai S | konbini, building S, pool | sports ground, viaduct curve |

Two texture regions, `town` (rows 0–1) and `shrine` (rows 2–5), each with palette variants `day`
and `night` (section 6.5): [TEXTURES.md](TEXTURES.md).

---

## 3. Zones

Each zone: purpose, layout, heights, landmarks, ways in and out, secrets, what you see.

### 3.1 Station and plaza (1)–(4), c1_0–c3_0

- **Purpose:** the spawn, the hub of the town, the conventional exit (trains).
- **Layout:** the viaduct runs east-west along z 2–14 (deck 9.0, parapet top 10.2, 12 m wide,
  piers every 16 m). The station is the stretch x 136–184: a 40 m island platform on the deck
  (`station_platform`), canopy 12.8, a concourse under the deck with ticket gates, and two
  stairs from the plaza (18 m long, 9 m rise, 26.6°). The plaza (x 108–214, z 16–44) holds the
  spawn (160, 26) facing north, the koban (122, 24), the bus stop (140, 36), the konbini
  (x 178–214, z 18–32, roof 5.6, its door the way back to the garden), the pachinko parlour
  (x 92–108, roof 9.1) and the danchi (x 70–86, z 18–34, roof 18.8, outside stair), a phone
  booth, a newsstand, bike racks and a taxi rank.
- **Out:** north up the shotengai; the stairs to the platform; the awning bounce at the
  shotengai's mouth; the konbini roof and its pole; west into the alleys and to the canal; east
  to the school lane.
- **Seen:** the arcade and the torii in its mouth; the pagoda's top over it; the stage on the
  skyline; the building's long flank to the right; the trains overhead.
- **Secret:** the station canopy's top (12.8) holds a red coin; from the platform, double jump
  and grab (3.8 m up).

### 3.2 Shotengai (the sando) (5), c2_0–c2_1

- **Purpose:** the town's spine and its rooftop highway.
- **Layout:** the street x 154–166 from z 44 to the front road at z 104; six shops a side at
  10 m frontage on x 140–154 and x 166–180. Two-storey roofs 6.5 m; three-storey 9.5 m (west
  z 54–64 and 94–104; east z 64–74 and 94–104). An arcade roof covers z 62–94 (eaves 7.0, ridge
  8.5, walkable 15°), with arcade gates (8.3 m) at z 60 and z 96. Six shops have awnings at
  2.6 m tagged `bounce` (+4.5 m: 18 m/s, apex 18² / 72 = 4.5), which land on their own 6.5 m
  roofs. Service lanes 2.5–3 m behind both rows; the west lane opens into the alleys.
- **Heights to remember:** 6.5 → 9.5 is a 3.0 m step (double jump); shop roof to arcade eave
  0.5 m; the gaps between neighbouring shops are 1 m.
- **Seen:** down the street, the torii framed by the north arcade gate; from the roofs, the
  whole precinct and the pagoda.

### 3.3 Back alleys (6)–(7), c1_0–c1_1

- **Purpose:** close, twisting ground; a dense roof layer at 6–8 m; the fire tower.
- **Layout:** 24 houses of about 9.5 × 8.5 m on x 66–136, z 44–104, roofs 6, 6.5, 7 or 8 m,
  alleys 2.5–3 m. Three empty yards break every straight line, so no alley runs more than two
  houses straight. The fire tower (`fire_tower`, 15.2 m) stands in its yard at (102, 74), its
  ladder a pole. The dagashi shop with a gachapon and a jizo at the corner (126, 46).
- **Roof layer:** neighbouring roofs differ by at most 2 m and stand 2.5–3 m apart: a running
  jump. The fire tower's top is 7.2 m above the highest roof: ladder only, or kicks between the
  tower and the house 3 m east of it (two good kicks, +3.4 m each).
- **Camera:** the alleys are narrower than the camera distance (6.5 m), so each alley is a
  `camera_zone` (`rail` along the alley, raised to look down).
- **Out:** the front road; the canal lane; the danchi; the shotengai's service lane.

### 3.4 Canal and machiya (8)–(9), c0_0–c0_1

- **Purpose:** the west edge of the town, water you can wade, the sento chimney.
- **Layout:** the canal x 44–52 from the spring (48, 292) south to under the viaduct (z 0):
  water at −0.4, bed −1.2, stone banks 1.2 m. 0.8 m deep: the player wades (slowed by depth, as
  built) and can still jump (no jump only from deeper than 1 m), and climbs out with any jump.
  Bridges: a footbridge at z 60, the front road's bridge, the arched bridge at z 160 into the
  park, a plank bridge by the watermill at z 196. Machiya in two rows (x 4–18 and x 24–40, roofs
  7.5 and 7.0) from z 18 to 104. The sento (x 8–30, z 60–73, roof 8) with its chimney (18.2 m)
  at the back: an iron ladder (a pole) from the boiler-room roof (5 m) is the only way up.
- **Seen:** the woods across the canal; the chimney from the whole west; the viaduct crossing
  the canal at z 8.

### 3.5 The front road (13)–(14), c0_1–c4_1

- **Purpose:** the east-west street joining every zone along the shrine's south face.
- **Layout:** z 104–118, two lanes and sidewalks. Utility poles every 30 m (9 m, poles) carry
  wires at 8 m (rails, grind or hang). The great torii stands just north of it. The pedestrian
  overpass (`overpass`, deck 7) crosses at x 256–268 from the school to the cemetery lane. A
  culvert takes the pond's outflow under the road at x 230–242. East, the road passes under the
  viaduct (the seamless edge, 7.1); west, it crosses the canal and ends at road works (7.3).

### 3.6 Outer courtyard (15)–(16), c2_1–c3_2

- As direction A: raked gravel at 0.6 m (x 110–210, z 118–167), the great torii (13.2 m, posts
  are poles), two side halls (roofs 11.6) at x 122–134 and 186–198, open on both sides.
- **Lantern strings** (rails): from each end of the torii's top beam down to the nearer side
  hall's north-west or north-east roof corner, and from each side hall to the gate's lower roof
  (11.0). Hang (2.5 m/s) or grind (6–14 m/s).
- New dressing: a chozuya (water pavilion), komainu, an omikuji rack, an ema board, the shrine
  office.

### 3.7 Inner precinct (17)–(22), c1_3–c3_3

- As direction A: the 5.0 m terrace (x 114–214, z 167–234) behind a 4.4 m retaining wall and a
  2.6 m white wall; the two-storey gate (lower roof 11.0, upper roof 18.6); corridor halls (roofs
  15); the temple on its 8.6 m podium (ridge 29.5); the bell pavilion (9.7) at (204, 226).
- **Four gates:** south (the main gate), west (114, 200) to the woods, east water gate
  (214, 192) onto the zig-zag bridge, north (160, 236) to the ridge stair, barred until
  shortcut B is lifted from the ridge side.
- **Over the wall:** the retaining wall is 4.4 m from the courtyard (double jump 3.4 + grab:
  about 5 m). From the woods, where the ground is about 3 m, the wall's top (7.6) is 4.6 m up;
  mossy boulders (1.7–2.8 m) mark the three places where it is easy.

### 3.8 Ridge and pagoda (23), c2_4

- The ridge (crest 20–22 m at z 262) runs from the west woods (x 84) to the gorge (x 252). The
  pagoda (A's, moved; `arch_pagoda` is 30 m) stands on a 13 m terrace at (178, 262), base 20.
  Its five roofs at 24.8, 29.6, 34.4, 39.2 and 44.0 m (4.8 m apart; each eave 1.8 m deep, each
  tier 0.5 m narrower), the finial a pole from 44.0 to 50.0.
  *Grey box:* the pagoda is the shrine's real one (owner, 2026-10-05), with its climbing
  collision `arch_pagoda_town_col`: eave tops 5.0 / 8.6 / 12.2 / 15.8 / 19.4 above its base (3.6 m
  apart), eave half widths 5.4 / 4.7 / 4.0 / 3.3 / 2.6, a 0.7 m strip of each roof outside the
  eave above (27.9°), the dew basin's flat top at 21.19, the finial a pole 8.8 m from it. Its
  terrace is cut into the ridge at 15 (G5, section 12): roofs at 20.0, 23.6, 27.2, 30.8 and 34.4,
  the dew basin at 36.19, the finial's top at 45. A stone lantern (top 16.4) stands in front of
  its south face: the step to roof 1.
- A stone stair dog-legs from the north gate (5 m) to the terrace (20 m): 50 m of steps, 17°.
  *Grey box:* a straight stair on `layout.py`'s line, (160, 5, 234) to (172, 15, 254), 23 m at
  23°.
- Two cedars stand 3.2 m apart, trunk face to face, west of the pagoda at x 164 and x 169
  (z 262): the kick pair (★1). *Grey box:* north and south of each other at x 171.35 (z 259.5
  and 264.5, faces 3.2 m apart along z), their faces 1.05 m west of roof 2's eave line; trunks
  to 34.5, crowns 34–38, under the glides G6 and G8.
- From here: the whole precinct below, the town beyond, the cedar's crown and the stage above.

### 3.9 West woods and the treetop walkway (29)–(31), c1_1–c1_4

- Ground 1–3 m sloping up to 8 at the ridge's west end; the trail from the front road
  (104, 112) north along the woods to the fox grove; the canal lane on its west side.
- **Decks** (A's, on giant cedars): 9 m at (94, 152), 12 (82, 180), 15 (80, 208), 18 (88, 234),
  21 (102, 252), 22 (114, 264), joined by rope bridges that rise 3 m over 25–30 m (≤ 7°). The
  last deck is 3.2 m above the ridge's west end (18.8): a jump and grab from the ridge.
- **The crown deck** (70, 220) at 28 m: a spur from the 15 m deck, a 13 m trunk pole
  (climb 3 m/s, 4.3 s). The best view in the woods.
- **The rope deck** (130, 282) at 24 m (`forest_platform` on a giant cedar 10 m above the
  ground): a rope bridge from the 22 m deck (24 m long, 2 m up). From it, a rope with white paper
  streamers runs to the sacred cedar: ★4's only way in.
- The foot of the walkway: a stair round a cedar at the courtyard's west edge (102, 118) up to
  the 9 m deck.

### 3.10 The sacred cedar's basin (32), c2_4

- A clearing of 15 m radius at 13 m, where the forest paths cross: from the ridge (north
  slope), from the fox grove (west), from the falls pool by the hollow log (east), and from the
  rope ladder's foot (north, shortcut A).
- The sacred cedar (`tree_cedar_sacred`, 45.8 m; top 58.8) stands in its middle with its
  shimenawa. Nothing within 12 m of its trunk. At its foot, on the west side, a curtain of roots
  with a gold light behind it (★4's root door, D).

### 3.11 Fox grove and the torii tunnel (33)–(34), c1_4–c1_5

- The grove (90, 294) at 15 m: the fox shrine, fox statues.
- The senbon torii tunnel: switchback stone steps from the grove up to a landing at 54.5 m
  (122, 346), 86 m long (average 24.6°, as a stair sweep), under about 60 small torii
  (`forest_fox_torii`, 3.6 m tall, every 1.4 m). Their top beams make a parallel line for the
  confident: 0.3 m wide, 1.4 m apart, 3.6 m above the steps.
- From the landing a stone stair rises 5.5 m over 16 m to the stage's west end.

### 3.12 Back mountain, stage, falls (35)–(38), c2_5–c3_5

- **The stage** (138–170, z 340–354), deck 60, on stilts 12 m tall at its front (the ground
  under its front edge is 47.7). The hall behind it (`forest_stage_hall`). The bell hangs under
  the hall's eaves at (154, 358).
- **The cliff band** z 316–340, from about 24 to 46 m, in front of and below the stage. Shortcut
  A, the rope ladder, hangs on it at x 154 from the ledge at 44 m (z 336) to the slope at 24 m
  (z 322): 20 m, climb 6.7 s. *Grey box:* the ladder hangs plumb (the real
  `forest_rope_ladder`) at z 317.85 from a shelf at 24 (x 148–160, z 314–318, steps up from the
  basin floor) to the ledge at 44, whose south face is sheer above the shelf; its pole runs 1.2 m
  past the lip. Climbed in 6.1 s; at the top, let go and push at the rock: the hands catch the
  lip (scenario 424).
- **The falls** at x 210–218, lip 48 m, pool 12 m (214, 322): 36 m. The cave behind them at
  14–17 m.
- **The kick chimney** (196, 330–338): two rock faces 3.0 m apart from the pool's west terrace
  (16 m) to the cliff top (46 m), with a rest ledge at 31. Good kicks gain 3.4 m each
  (15.6² / 72); 30 m is nine kicks, four and five either side of the ledge.
- **The rope bridge** from the falls' top (222, 346, about 52) to the stage's east end (170, 347,
  60): 52 m long, 8 m up (9°).

### 3.13 East valley: pond, stream, gorge (24), (36), (41), c3_1–c3_4

- **The pond** (x 219–251, z 125–182) with the built crossing pieces (stones, bobbing logs,
  lily pads, the zig-zag bridge from the east water gate), now optional.
- **The stream** from the falls pool (12) south along the gorge to the pond (0).
- **The gorge's east wall:** the valley floor is about 11 m at z 300 and the shoulder 34 m; the
  wall between them (x 244–256) is rock, not climbable. Shortcut C crosses it.
- **The culvert** (41): the pond's outflow under the front road, 14 m long, 0.8 m of water.

### 3.14 Cemetery and the east shoulder (39)–(40), c4_1–c4_5

- Nine terraces of 12 m, 1.8 m apart (x 256–316, z 130–250), 1.8 to 16.2 m. A 1.8 m step is a
  plain jump (2.1 m apex); a stone stair runs up the middle. Graves in rows, a small jizo hall
  at the top.
- **The east shoulder trail** from the top terrace (16.2) by switchbacks to the falls' top
  (about 52): about 150 m, no grade over 14°. Beyond, the mountain path north-east out of the
  level (42).
- **Shortcut C:** a dead cedar on the shoulder's rim (256, 306, 34 m), pounded, falls west across
  the gorge onto a rock shelf above the falls pool (226, 318, 20 m): a log 32 m long, 1.2 m wide,
  falling 14 m (24°, walkable).

### 3.15 Schoolyard (11)–(12), c3_0–c4_1

- The school (`schoolhouse`, 29 × 30 × 18.9) at x 258–288, z 56–86, with an outside fire stair
  to the roof; the gym (x 214–238, z 64–94, roof 9); the pool (x 214–240, z 22–40, 0.9 m of
  water); the sports ground (x 244–292, z 18–52) with tyre steps, a climbing frame and goals.
- School roof (18.9 + 3.4) north over the road: the glide meets the rising terraces about 67 m
  out, on the second or third terrace (3.6–5.4).
- The overpass joins the school's north gate to the cemetery lane over the road.

### 3.16 Park and festival ground (25)–(26), c0_1–c0_2

- x 0–44, z 118–206 at 0.6: six ginkgo, a playground (a slide tagged `slide`, a jungle gym,
  swings), a public toilet, benches, the festival yagura (8 m) at (22, 160), the watermill
  (`watermill`) on the canal at (48, 196) and the arched bridge to the woods at z 160.

### 3.17 Bamboo grove and the sake brewery (27)–(28), c0_3–c0_5

- From the park north (x 0–44, z 206–384) the ground rises to 22 m in the north-west corner.
  The sake brewery (`sakagura`, roof 16.2) at (15, 218), the canal's spring at (48, 292).
- Maples and cedars thin out, tall bamboo thickens; this is the soft edge to the bamboo level
  (7.2).

---

## 4. Routes

### 4.1 The spawn and the first 10 seconds

The player appears at (160, 26) facing north, 9.6 m/s on foot (96 m in 10 s).

| | Direction | What happens | Time |
|---|---|---|---|
| A | North on foot | the shotengai, the arcade, the torii at 98 m | 10 s |
| B | Station | the stair foot at 14 m, up 9 m to the platform; the viaduct's parapet is a rail 300 m long east and west | 5 s |
| C | Roofs | the first east shop's awning (20 m), bounce +4.5 onto its roof (6.5), then the shop roofs and the arcade | 3 s |
| D | Konbini | the vending machine (1.9), double jump and grab to the roof (5.6, 3.7 up), the corner pole (9 m), the wire north along x 207 to the front road | 6 s to the wire |
| E | Alleys | the alley mouth at (118, 44); or the danchi's outside stair to 18.8 | 3 s / 9 s |
| F | School | the school lane (206, 44) and the sports ground | 6 s |
| G | Canal | the plaza's west side to the canal lane (106 m) | 11 s |

Every one of them leads somewhere with a goal in it: A to the shrine, B to the parapet and red
coins 3 and 8, C to red coin 1, D to the front road's wires (red coin 6), E to red coins 2 and
4, F to the cemetery and the mountain, G to the sento (red coin 7) and the park.

### 4.2 The loops

1. **The axis** (272 m to the pagoda): plaza, shotengai, torii, courtyard, gate, precinct, north
   gate (or round by the west or east gate until B is open), stair, pagoda.
2. **The west loop:** front road, woods trail, fox grove, torii tunnel, stage; back by the
   ladder (A) or a glide.
3. **The east loop:** school lane, overpass, cemetery, shoulder trail, falls top, rope bridge,
   stage; back down the stream and the pond to the road.
4. **The canal loop:** canal lane, park, watermill, bamboo grove, back along the woods' west
   edge or wading the canal.
5. **The town roof loop:** awning, shop roofs, arcade, front-road wire, alley roofs, fire tower,
   danchi, glide down to the canal lane, back across the plaza.
6. **The shrine roof loop:** side hall, lantern string, gate, corridor hall, temple ridge, glide
   to the pagoda's first roof (G5).
7. **The tree loop:** walkway foot, decks 9 to 22, the ridge, back down the woods trail; spurs
   to the crown deck and the rope deck.

### 4.3 Rails and poles

| Rail or pole | Where | Use |
|---|---|---|
| Front-road wires | z 104, poles every 30 m, 8 m | grind east-west 290 m; red coin 6 |
| Service-lane wires | x 118 and x 150 (z 44–104), x 207 (konbini to road) | from the plaza's poles to the road |
| Viaduct parapet | the whole viaduct, 10.2 m | grind from the platform west over the canal (red coin 8) or east round the curve |
| Lantern strings | torii top beam ↔ side halls ↔ gate's lower roof | hang or grind; the way to the torii top (★2) |
| Rope bridges | the walkway, falls → stage | walk |
| The cedar rope | rope deck → knot hole | hang only (★4) |
| Poles | utility poles 9, torii posts 12.6, fire tower ladder 15, sento chimney ladder 13.2, pagoda finial 6, crown-deck trunk 13, rope ladder A 20 | climb 3 m/s |

### 4.4 Glides

Each starts at the double jump's apex (take-off + 3.4) and loses 1 m per 4 m.

| Glide | From | To | Distance | Arrives | Lands on |
|---|---|---|---|---|---|
| G1 | building roof 18.3 (193, 102) | east side hall (192, 126) | 24 m | 15.7 | the side hall's roof (11.6) |
| G2 | danchi roof 18.8 (78, 34) | canal lane (56, 80) | 51 m | 9.5 | anywhere in the alleys or the lane |
| G3 | sento chimney 18.2 | the park (22, 138) | 68 m | 4.6 | over the canal into the park |
| G4 | fire tower 15.2 | courtyard's west side (112, 140) | 64 m | 2.7 | the courtyard, over the front road |
| G5 | temple ridge 29.5 | pagoda roof 1 (174, 256) | 33 m | 24.6 at the centre, 26 at the eave | roof 1 (24.8) |
| G6 | stage 60 (162, 340) | pagoda (179, 266) | 76 m | 44.4 | roof 5 (44.0) at the west eave, roof 4 (39.2) easily |
| G7 | pagoda roof 5, 44 | cemetery top (282, 244) | 102 m | 21.8 | the top terrace (16.2) |

*Grey box (scenarios 410–418, section 12):* every glide lands where it should with the default
tuning. G5 starts from the real temple's ridge (27.5) and lands on roof 1 only with the pagoda's
terrace at 15; G6 comes down on roof 3 (27.3) after circling off its height; G7, from roof 5
(34.4), lands on the cemetery's top terrace at x 263 (from the plan's roof 5 at 39.4 it reached
x 284).
| G8 | stage 60 (170, 340) | the arcade (160, 98) | 242 m | 2.8 | inside the arcade (★5's fast line) |
| G9 | school roof 18.9 (273, 86) | cemetery terraces | about 67 m | 5.6 | terrace 2 or 3 (3.6–5.4) |

G8's line, checked along its length: at the cedar (z 296) it is 14 m east of the trunk and at
52.4 m, under the crown's widest part but clear of it; at the pagoda (z 262) 5 m west of its
eaves at 43.9; over the temple ridge at 32.9 (3.4 m clear); over the gate's upper roof at 20.1
(1.5 m clear); through the torii between its posts at 9.4 m, about 1 m under the lower beam;
under the arcade gate (8.3) at about 3 m; down onto the arcade's floor near z 86.

**Rims:** a glide from the stage covers up to 254 m, which reaches every part of the level
except the north-east summit. No glide leaves the level: south of the town is the viaduct (9 m
deck, 1.2 m parapet) and the neighbour beyond; the east and north rims are higher than any glide
arrives there.

### 4.5 Shortcuts (open once, stay open; saved)

| | What | Opened from | Joins | Mechanism |
|---|---|---|---|---|
| A | Rope ladder | the cliff ledge under the stage (44 m): kick it down | basin's north slope (24) ↔ stage (60) | layer `ladder_a`, a pole when down |
| B | North gate bar | the ridge side: lift it (press at the bar) | precinct ↔ ridge stair | layer `gate_b_open` swaps the barred gate for the open one |
| C | Dead cedar | the shoulder rim: ground pound its base | shoulder (34) ↔ falls-pool shelf (20) | layer `cedar_c_down` |
| D | Root door | inside the cedar: ground pound the root bulge | basin ↔ the root chamber | layer `root_d_open` |
| E | Fire-escape ladder | the building's roof: kick it down | front road ↔ building roof 18.3 (G1) | layer `ladder_e`, a pole when down |

Five layers in all; the most in one cell is two (c2_4: D; c2_5: A). The kit allows eight a cell.
*Phase 2 (12.5):* each is a `trigger` with `keep` (saved) that switches its layer: A, B and E by a
press of B in the box, C and D by a ground pound.

---

## 5. The five stars

Each needs a `star` entity (saved); the game has `coin` and `red_coin` today and no star type.

### ★1 The pagoda finial (50 m)

- **Fantasy:** climb the landmark you have been looking at since the spawn.
- **Where:** 1 m above the finial (178, 262, 51); reached by a pole jump from the finial's top
  (12.6 m/s, +2.2 m).
- **Approaches:**
  1. *The tiers* (the teaching line): from the terrace (20.0) to roof 1 (24.8) is 4.8 m, a
     double jump (3.4) and a grab (to about 5 m); the same for each of the four roofs above;
     the finial pole from roof 5 (44.0) to 50. Coins on each roof's south eave show it. About
     25 s. *Grey box (scenario 422):* the chained jump measures 3.0 m, and the grab needs the
     body against the 0.35 m fascia, so roof 1 (5.0 above the terrace) is out of reach from the
     ground: a stone lantern in front of the pagoda (top 16.4) is the first step, and from it
     and from each roof's strip the next eave is 3.6 up. The finial pole's top (feet at 43.8)
     puts star 1 (at 45.5 in the grey box) in reach. Coins are on the west strips.
  2. *The kick pair:* two cedars 3.2 m apart west of the pagoda; from the terrace four good
     kicks (+3.4 each) reach about 33.6 m; a kick east carries 7.2 m/s across to roof 2's west
     eave (29.6, 3.2 m away). Skips two tiers. *Grey box (scenario 420):* a kick mirrors the way
     the body came in, so between faces north and south of each other it goes north and south;
     after four kicks (13.6 m gained) the stick east drifts the body, the next touch kicks it
     east, and it lands on roof 4 (31.5).
  3. *From the temple:* G5, ridge (29.5) to roof 1 (33 m, arrives 26 at the eave). *Grey box:*
     from the real ridge (27.5) to roof 1 at 20.0 (scenario 414).
  4. *From the stage:* G6, to roof 4 or, with a perfect line, roof 5; then the finial.
- **Learns:** the tier rhythm (double jump and grab), and that height is a store of distance.
- **Needs:** `star` (new). The finial pole uses `pole` (built). `arch_pagoda`'s collision is
  reworked so each eave is a walkable strip (≤ 28°) and each storey wall a grabbable ledge.

### ★2 Eight red coins over the shotengai (star on the torii, 13.2 m)

- **Fantasy:** run the town's roofs and wires like a cat.
- **Where:** the eight red coins are in the town; the star appears on the great torii's top beam
  (160, 124, 13.2) when the eighth is taken.

| Red coin | Where | Height | Reach |
|---|---|---|---|
| 1 | arcade roof's ridge (160, 78) | 8.5 | awning bounce to a shop roof, 0.5 m up to the eave, the ridge |
| 2 | fire tower's top (102, 74) | 15.2 | its ladder, or kicks between the tower and the house 3 m east |
| 3 | station canopy (172, 8) | 12.8 | from the platform (9), double jump and grab, 3.8 m up |
| 4 | danchi's water tank (78, 26) | 20.8 | the outside stair to the roof (18.8), a jump onto the 2 m tank |
| 5 | konbini's roof sign (196, 30) | 7.0 | vending machine, roof, a jump to the sign's top |
| 6 | front-road wire, mid-span (130, 104) | 8.0 | climb a pole, grind or hang along the wire |
| 7 | sento chimney's top (23.5, 68.5) | 18.2 | the chimney's ladder from the boiler-room roof: one way up |
| 8 | viaduct parapet over the canal (48, 8) | 10.2 | grind the parapet west from the platform (112 m) |

- **Approaches to the star:** climb either torii post (a pole, 12.6 m, 4.2 s); or hang along a
  lantern string from either side hall's roof (11.6) to the end of the top beam; or grind the
  string down from the gate's lower roof.
- **Learns:** the roof layer is continuous, and rails join its pieces.
- **Needs:** `red_coin` (built, saved); a count of eight that makes the star appear (new, small);
  `star` (new).

### ★3 The stage bell (60 m)

- **Fantasy:** the pilgrimage to the top of the mountain; ring the bell and the whole valley
  hears it.
- **Where:** the bell under the hall's eaves (154, 358); touching its rope rings it and the star
  drops onto the deck.
- **Approaches:**
  1. *West, the torii tunnel* (ground, the intended first time): fox grove (15), 86 m of steps
     under 60 torii to the landing (54.5), the stair to the deck. About 25 s from the grove.
  2. *East, the shoulder trail* (ground, long and easy): cemetery top (16.2), about 150 m of
     switchbacks to the falls' top (52), the rope bridge (52 m) to the deck.
  3. *Centre, the kick chimney* (hard): the falls pool, the cave behind the falls, the
     chimney's nine good kicks with a rest ledge at 31 to the cliff top (46), a scramble to the
     rope bridge.
  4. *North face, the rope ladder* (after shortcut A): basin, the slope to 24 m, the ladder to
     44 m, the stair up through the stilts.
  5. *The torii tops* (variant of 1): running the top beams of the tunnel's torii.
- **Learns:** one mountain, three faces, three skills.
- **Needs:** a bell (a touch switch) that releases the star (new); `star` (new); shortcut A's
  layer and saved flag (new game logic; layers are built in the kit).

### ★4 Inside the sacred cedar (the one way in)

- **Fantasy:** a secret that you see long before you understand it.
- **Where:** the root chamber inside the cedar at the basin floor (154, 296, 13).
- **The one way in:** the rope deck (130, 282, 24) → the rope, 24 m long, falling 2.5 m, hung
  hand over hand at 2.5 m/s (9.6 s) → the knot hole on the cedar's west face (150.5, 295,
  21.5; 1.4 m wide, 2.2 m tall) → down the hollow trunk (8.5 m drop inside a 4 m shaft) → the
  chamber and the star. *Grey box (scenario 423):* the rope runs from the deck into the hole's
  mouth (it ends 0.5 m into the trunk's wall, under the hole's top): hung to its end in 8.9 s,
  let go, the feet are on the sill. A glide from the rope deck along the rope's line also enters the hole
  (27.4 m at take-off, 21.4 at the hole); it is the same way in, from the same deck.
- **Why there is no other:** the trunk stands alone (nothing within 12 m, no branches below
  30 m), so it cannot be kicked up; a bark lip 1.2 m deep over the hole (at 24 m) stops anything
  dropping in from above; the hole faces west towards the rope deck, and every other high place
  is on the wrong side or too far (a glide from the 22 m deck arrives at 13.4, from the stage at
  about 51, from the pagoda's second roof on the east side). The root curtain at the foot is
  solid from outside.
- **How it is found:** from the basin floor the root curtain shows a gold glow (a cutout
  texture); from the 22 m deck the rope and its white streamers are 18 m away.
- **Out:** ground pound the root bulge inside: the root door opens (shortcut D) onto the basin.
- **Learns:** look from one place, reach from another; the tree layer has an end.
- **Needs:** the rope as a `rail` path in hang mode (built); `tree_cedar_sacred_hollow`, a new
  version of the cedar with the shaft, hole, lip and chamber; the root door's layer and saved
  flag (new); `star` (new).

### ★5 The last train (timed)

- **Fantasy:** the priest's daughter is leaving for the city on the 17:52; her omamori is still
  on the stage. Get it to her before the train leaves.
- **Start:** the omamori on the stage's south-east corner (168, 342). Taking it starts a clock of
  70 s (4,200 ticks). The two-car train comes in from the west at 45 s, stops at the platform at
  55 s, and leaves at 70 s. Stand in the marked spot on the platform (or on the train's roof)
  before it leaves: the star.
- **Approaches** (times for a good player; the limit is tuned so that the walking route works at
  85% of run speed with 8 s to spare):
  1. *The glide line* (G8): 242 m of glide (30 s), 60 m of arcade on foot, the station stair: about
     41 s.
  2. *Two glides:* G6 to the pagoda's roof 4 (about 10 s), then a second glide from it (39.2 + 3.4
     reaches 170 m) south over the temple (2 m clear) and just east of the gate to the front road
     (21 s), then the shotengai on foot: about 43 s.
  3. *The west ground route:* the stair, the torii tunnel down, the fox grove, the woods trail,
     the front road, the shotengai, the station: about 420 m, about 55 s.
  4. *By the ladder and the axis* (after A and B): ladder, basin, ridge, north gate, precinct,
     gate, torii, shotengai, station: about 380 m, about 50 s.
  5. *East* (the shoulder trail, 575 m): about 68 s. Too slow; the race teaches which way is
     down.
- **On failure:** the train leaves, the omamori goes back to the stage. No penalty.
- *Phase 2 (section 12.5):* the clock is **85 s** (5,100 ticks), not 70: the train comes in from
  the west at 60 s, stands at the platform from 70 s and leaves at 85 s. Measured in the grey box
  (scenarios 452 and 454): the G8 line 47.1 s, the west ground route 60.6 s to the deck; with the
  real station's inside stair (about 35 m, 4.5 s more) the walking route is 65.1 s, which at 85%
  of the run speed is 76.6 s, and 8 s to spare gives 84.6. The spec's 70 s assumed a 55 s walk.
  With the real station placed (12.6) the walking route up the inside stair measures 63.7 s and
  the G8 line 50.2 s: 63.7 at 85% and 8 s to spare is 82.9, inside the 85.
- **Learns:** the level is one place; height is speed.
- **Needs:** a switch that starts a challenge (new; PLATFORMER.md plans "switches that start
  challenges"), a timer on the HUD (new), the train as a `mover` on the viaduct's path (built:
  the garden's train is a mover) started by the switch (new: a mover that waits for a trigger),
  a platform zone (new: a trigger box), `star` (new).

### What is new for the stars, in one list

| Need | For | Today |
|---|---|---|
| `star` entity (saved), its count, its pickup | all | built (phase 2): the hanafuda moon card in its glint |
| Red-coin count releases a star | ★2 | built: the flag `red_coins`, star 2's `appear` |
| Touch switch (bell, omamori, bar) | ★3, ★5, B | built: `trigger` (`how: touch`, or `press` for B) |
| Timer on the HUD; fail and reset | ★5 | built: a trigger's `timer` |
| Mover started by a trigger | ★5 | built: a mover's `start` flag and `delay` |
| Trigger box (platform zone) | ★5 | built: `trigger` (with `needs` and `ends`) |
| Saved flags that switch layers | A–E | built: a trigger's `keep`, `on` and `off` |
| Ground pound on a target (root bulge, dead cedar) | C, D | built: `trigger` with `how: pound` |
| Hang on a sloping rope | ★4 | built (`rail`, St.Hang) |
| Poles, bounce, wading, slide surfaces | everywhere | built |
| A ladder held on its front (A, E) | ★3, A, E | built (phase 2): `pole` with `front` |

*Phase 2 (section 12.5):* every row is built; the entities are in `game.py`.

---

## 6. Coins, secrets, life, time of day

### 6.1 Coins (100)

| Where | Coins | Line they show |
|---|---|---|
| Plaza and station stairs | 6 | the stairs, the bus stop's roof |
| Shotengai roofs and arcade | 10 | awning → roof → arcade |
| Front-road and lane wires | 9 | three on each of three spans |
| Alley roofs | 8 | the dog-leg roof run to the fire tower |
| Canal (in the water) | 6 | wading is allowed and faster than it looks |
| Viaduct parapet | 8 | the grind west to red coin 8 |
| Courtyard lantern strings | 8 | two on each string |
| Gate, halls and temple roofs | 6 | the shrine roof loop (as built) |
| Pagoda eaves | 5 | one per roof (★1) |
| Treetop decks | 7 | one per deck to the rope deck |
| Torii tunnel tops | 8 | the top-beam line |
| Stream and pond stones | 8 | the optional crossing |
| Cemetery steps | 5 | the stair |
| The cave behind the falls | 6 | a secret (6.3) |

100 coins and the 8 red coins. A reward for 100 coins would be a sixth star; it is not in this
spec (open question 3).

### 6.2 Red coins

Eight, in the town (★2; table above).

### 6.3 Secrets (no star)

- **The cave behind the falls** (14–17 m): six coins, the view out through the water, the foot
  of the kick chimney.
- **The culvert under the front road:** wade 14 m under the road from the pond's outflow to the
  school's ditch; a sleeping cat at the far end.
- **The crown deck** (28 m): the woods' best view; a coin ring.
- **The sake brewery's roof** (16.2): the canal, the park and the bamboo below; the cedar ball
  (sugidama) under the eaves is a bounce.
- **The torii tops:** the parallel line over the tunnel.
- **The school's roof** (18.9): the water tank, a lost ball, G9 to the cemetery.

### 6.4 Small life

| Life | Count | How | Cost |
|---|---|---|---|
| Train (two cars) | 1, every 90 s | `mover` on the viaduct path, loop | L0 1,200, 400 from 40 m |
| Bus | 1, every 120 s | `mover`, plaza ↔ east edge, pingpong | `city_bus` adapted, 300 from 30 m |
| Pedestrians | 8 (shotengai 4, plaza 2, canal lane 1, courtyard 1) | `mover` paths at 1.2 m/s, no collision | 80 each, culled at 50 m |
| Cyclist | 1 on the front road | `mover` | 120 |
| Schoolchildren | 4 on the sports ground | `mover` loops | 80 each |
| Priest sweeping | 1, courtyard | still with a loop of two poses | 80 |
| Cats | 3 asleep (konbini roof, alley wall, culvert) | still | 60 each |
| Crows | 6 on the wires; fly off when near | new: a two-state prop | 30 each |
| Pigeons | 8 on the plaza; scatter | new: a two-state prop | 20 each |
| Koi | 5 in the pond | `mover` loops under the surface | 30 each |
| Heron | 1 at the canal | still | 60 |
| White fox | 1, fox grove; runs off along a path when approached | `mover` started by proximity (new) | 80 |

Budget for life: at most 400 triangles and 10 placements drawn in any view. Movers exist; the
"flies off" and "runs off" behaviours are new and small. No NPC talks.

Sound (no audio banks yet): station chimes and the train, the shotengai's music, cicadas giving
way to a crow and the falls in the forest, the falls heard from the basin before it is seen, the
bell (★3) heard everywhere.

### 6.5 Day and night

The level is built for an autumn afternoon (the shrine's `day`) and carries the region's `night`
variant (surfaces × `#4a5884`, emissives for lanterns, windows, signs, shopfronts). No star
depends on the time. When the game has a clock, a `festival` layer at night adds lantern lines
over the shotengai and the courtyard (more rails), yatai and takoyaki stalls (`yatai`,
`takoyaki_stall`) in the courtyard and the park, the yagura lit, and pedestrians in yukata; it
adds no star in this spec. Day and night switching is new (the shrine's README: "nothing switches
it yet").

---

## 7. Connective tissue

### 7.1 The seamless edge: under the viaduct, east to downtown (14), c4_1

**The idea.** You walk east along the front road past the school and the cemetery's gate. The
viaduct crosses the road on a skew at x 296–308; you pass under it, and on the other side is a
four-lane avenue with six- to ten-storey buildings, blue guardrails and sodium lights: downtown.
There is no gate, no loading and no stop.

**The geometry.**
- The road dog-legs under the viaduct: 25° north at x 290, 25° back at x 316. From the town side
  the view down the road ends on the viaduct's concrete abutment; from the downtown side it ends
  on the flank of a building. Neither side sees more than about 40 m into the other at street
  level.
- The underpass is 12 m long under the deck (9 m high), with the two pier rows; the dog-legs add
  about 20 m each side. Walking through takes about 5 s (300 ticks).
- On the north side the cemetery's retaining wall (3 m) and on the south side the school's
  boundary wall (3 m) and a row of six zelkova close the sides.

**What hides the change.** The deck fills the top of the view; the walls and trees fill the
sides; the dog-legs end the straight view. From the town side, before the underpass, the next
district shows only above the viaduct's deck: the upper storeys of the tall buildings, a
department store's rooftop sign and a TV mast, at 60–150 m. They are drawn as stand-ins (no
textures), which reads as silhouette and lit signs against the sky, especially at dusk. From
downtown looking back west: the viaduct, the school's roof, the cemetery terraces climbing to
the mountain, the pagoda, the stage and the falls' white line.

**The texture swap.** The two districts are separate regions with separate texture sets. The
underpass and the walls seen from inside it use only the common set (asphalt, kerb, concrete,
the viaduct, guardrails, road signs). While the player is between the two dog-legs (300 ticks at
walking speed) the region's eight slots are swapped one a tick (about 56,000 cycles a slot, about
6% of the CPU, over 8 ticks), then its palettes and backdrop. The World Checker needs a check
that no view between the dog-legs draws a region-textured cell (proposed in WORLDKIT.md, "Region
seams"; not built). A player gliding or grinding along the viaduct's parapet crosses the same
line 9 m higher: the parapet's views are the deck and the sky, and the swap runs the same way.

**The stand-in this level shows to downtown.** From the neighbour's streets most of this level
is 100–400 m away. The kit's per-cell stand-ins (made at 128 m) would cost up to 30 × 90 =
2,700 triangles, too much for the neighbour's far pass. Proposed: a second, coarser stand-in
level per cell at 256 m (`standins` with a second distance and trees thinned to a quarter: a new
kit option), which totals about 450 triangles for this level:

| Part | Triangles |
|---|---|
| Ground on a 32 m grid (30 cells) | 120 |
| Canopy: two-card trees thinned to one in six (about 60) | 120 |
| Pagoda (coarsest) | 30 |
| Stage and hall | 30 |
| Temple, gate, side halls (roof planes) | 40 |
| School and gym | 20 |
| Viaduct (as a ribbon) | 30 |
| Shotengai and alley roofs as strips | 40 |
| Machiya roofs, sento chimney, danchi, fire tower, building | 20 |
| **Total** | **450** |

### 7.2 The soft edge: the bamboo grove, north-west (28), c0_3–c0_5

The bamboo grove level (an Arashiyama-like path) lies beyond the north-west corner. Over a band
of about 40 m (x 0–44, z 250–384) maples and cedars thin out and tall bamboo thickens; the leaf
litter changes to bamboo leaves. The canal lane's path bends north-west round the grove's rise at
(8, 350), so there is never a straight view into the next level. Both are in the same region
(bamboo, earth and foliage are in this level's set), so no swap is needed; it is a scatter blend.
From inside the grove the pagoda's top shows above the canopy behind you.

### 7.3 Conventional joins

- **The station:** a `door` entity at the train's doors, live while a train stands at the
  platform, opens the line's other levels. Until those exist, it opens the garden.
- **The konbini:** its door leads back to the garden, as built.
- **The front road west:** road-works barriers (`street_barrier`) and a detour sign at x 0 until
  the shopping-street level exists (it is the second candidate for a seamless edge: the road bends
  north-west behind the machiya).
- **The canal south:** a grille where it passes under the viaduct.
- **The mountain path** north-east (42): a stone stair over the shoulder to the next hill, a door
  (or later a seam) at (252, 380).
- **The train itself:** a roof rider is swept off by the signal gantries at the level's two
  rail ends onto a maintenance walkway (a gantry 0.5 m above the roof); later the train is the
  connection.

---

## 8. Performance plan (1997 budgets)

### 8.1 The budgets

Per view (World Checker): 4,000 triangles, 600,000 draw CPU cycles (about 500 a placement and
110 a triangle), 1,600,000 GPU cycles. Texture VRAM: 16 slots of 32 KB, 14 for worlds.
Near pass to 192 m (the 3 × 3 cells around the camera); far cells as stand-ins. The engine has
no occlusion culling: everything in the frustum and in range is drawn.

**This level's targets:** 3,600 triangles per view (near pass 2,600, far pass 700, entities and
life 300), at most 220 placements drawn (110,000 cycles) so the draw CPU stays near 510,000.
The built shrine's worst measured view (the stage, scenarios 310 and 314) is 2,785 triangles and
590,756 cycles; the town is where the new cost is.

### 8.2 Density limits for the town

| Kind | L0 | L1 | L2 | Notes |
|---|---|---|---|---|
| Shop (10 m frontage) | ≤ 250 | ≤ 70 from 20 m | ≤ 20 from 50 m | awning, sign, noren in the mesh; awning collision tagged `bounce` |
| Alley house | ≤ 120 | ≤ 30 from 16 m | ≤ 12 from 40 m | mostly seen from above |
| Machiya | ≤ 200 | ≤ 50 from 20 m | ≤ 14 from 50 m | |
| Lab "hero" pieces | ≤ 600 after adapting | ≤ 200 from 24 m | ≤ 40 from 60 m | the lab models are 700–1,800 today and have no levels except `sakagura` |
| Small props | merged per cell | | | culled at 40 m, ≤ 300 per merged chunk |

- At most 12 shops within 40 m of any point of the shotengai (six a side).
- At most two hero pieces within 40 m of any point on a main route.
- Per town cell: at most 40 placements drawn from inside it; the cell's L0 total at most 7,000
  triangles; its stand-in at most 90.
- Stand-in caps elsewhere: forest cells 60, landmark cells (c2_3 temple, c2_4 pagoda and cedar,
  c2_5 stage) 140.

### 8.3 The worst views (estimates, to be measured first)

| View | Near pass | Far pass | Total | What keeps it in |
|---|---|---|---|---|
| V1 Arcade roof, north end, looking south (160, 94, 10) | 4 shops L0 1,000; 8 shops L1 560; 15 alley houses 240; arcade 300; south gate 150; plaza and station 450; building 60; ground 400; props 150; wires 60; life 150 = 3,520 | about 80 | **3,600** | shop L0 ≤ 250; plaza heroes at L1/L2 |
| V2 Pagoda finial looking south (178, 262, 52) | temple L1 285; corridor halls 220; bell 100; walls (merged, with levels) 400; trees 1,000; ground 750; pagoda 200; entities 100 = 3,055 | rows 0–2 (town, courtyard) 9 cells × 90 = 810 | **3,865** | walls merged and levelled; trees thinned from 56 m (as built) |
| V3 Stage looking south (154, 345, 62) | as the built summit (2,785 incl. far) less the old far, plus the basin and cedar | about 10 town cells × 90 | **3,500** | stand-in caps |
| V4 Danchi roof looking north-east (78, 30, 20) | 6 houses L0 720; 14 houses L1 420; fire tower 200; shops L2 240; arcade 150; pachinko, koban 100; machiya 320; ground 400; props 100; wires 60 = 2,710 | about 10 cells × 80 = 800 | **3,510** | alley houses ≤ 120 at L0; three yards remove three houses |
| V5 Spawn looking north (160, 26, 1.6) | 2 shops L0 500; 10 shops L1 700; arcade and gates 750; konbini 160; bus stop 150; koban 300; ground 400; props 150; life 200 = 3,310 | rows 2–5 in the frustum, 12 cells × 60 = 720 | **4,030** | the risk: see below |
| V6 Cemetery top looking west (286, 244, 18) | graves (merged) 300; pond pieces 250; trees 600; side and corridor halls 260; ground 600 = 2,010 | about 12 cells × 90 = 1,080 | **3,090** | |

**V5 is the risk.** From the spawn the far ring must reach row 5 (the stage) to keep the
skyline. Options, in order: (1) cap stand-ins of rows 3–5 seen from row 0 at 40 (the kit's
second stand-in level, 7.1, solves this too); (2) adapt the arcade gate to ≤ 300 and the koban to
≤ 200; (3) a far ring of 4 and the Horizon Engine backdrop painted with the mountain and the
stage's roof line at their true bearing from the plaza (no triangles; at most about 6° of
parallax error while the player is in row 0, where the mountain is 300 m away).

GPU: depth mode and textured fill are about 24% of the 1.6 M at 2.5 screens of overdraw; the
risks are cutout foliage stacked in the woods (as built, within budget) and the arcade's roof.
The arcade roof is opaque with cutout ribs, not blended.

### 8.4 Sight-blockers, on purpose

On this machine a wall saves nothing by itself: what is behind it in the frustum is drawn. Blockers
are designed to do three other things.

1. **Put heavy zones into each other's far set.** The building (18.3 m, 58 m long) stands between
   the shotengai and the school, so neither needs detail for the other; the gym hides the school
   from the plaza; the viaduct caps every southward view.
2. **Hide coarse levels and pops.** Alley houses behind the shop rows are seen from the street
   only over the shops' roofs, so their L1 (30 triangles) can start at 16 m. The three yards and
   the dog-legs mean no alley shows more than two houses at L0.
3. **Make a visibility table worth having.** Proposed for the kit: the World Checker already
   renders sampled views from every cell; it can write, per camera cell, a 30-bit mask of the
   cells that never contribute a pixel (120 bytes for this level), and the reader skips them. At
   street level in the town (alleys, the canal lane, the shotengai's floor) the precinct, the
   mountain and the far side of the town are hidden; the estimate is a 25–40% saving there. The
   level's budget does not depend on it.

### 8.5 Texture VRAM (14 slots, 448 KB)

*Superseded by [TEXTURES.md](TEXTURES.md) (2026-10-05):* the real assets need 595 KB
deduplicated before the ground, so the level is two regions, the town and the shrine, each with
its own 14 slots, split at z = 128; the World Kit has no common set. With VRAM at 2 MB (the same
day) each region may use 29 slots; the town's budget is 668 KB and the shrine's 460 KB
(TEXTURES.md, "The budgets").

The built shrine uses 13 slots (326 KB), 272 KB of it for 16 ground tiles. The town adds
shopfronts, signs, concrete and rail. Plan:

| Set | Slots | KB | What |
|---|---|---|---|
| Common (shared with every city level) | 6 | 192 | asphalt, kerb and paving, concrete, roof tile, glass and windows, street furniture sheet, signs |
| Ground (region) | 3 | 96 | forest floor ×2, moss, gravel, ashlar, steps, rock, earth, pond bed (12 tiles, from 16; asphalt and paving move to the common set) |
| Architecture | 2 | 64 | as STYLE.md |
| Foliage and bamboo | 2 | 64 | as STYLE.md, bamboo added |
| Forest structures and water | 1 | 32 | 48 + 32 KB cut to 32 |
| **Total** | **14** | **448** | |

Tight. The cuts are the ground (272 → 96 + its share of the common 192) and forest structures
plus water (80 → 32). If the forest's textures do not fit, the town's shopfront variety comes
from palette variants of one sheet, not new tiles.

### 8.6 Collision and camera

- Small roofs make many seams: the shop and alley roofs are flat-topped in collision (≤ 15°)
  with 0.2 m lips at the eaves for grabbing.
- Alleys (2.5–3 m) and the shotengai's service lanes get `camera_zone`s; the arcade (12 m wide,
  7 m high) gets a raised follow camera.
- The kick chimney and the kick pair get camera zones that look along the wall pair (as the
  garden's kick shafts).

---

## 9. Build order

Each phase ends with a playable build and a World Checker report.

1. **Grey box the playground** (the first thing to test is the feel). The heightfield from
   `layout.py`, every building and roof as a box at its final footprint, height and collision,
   the viaduct as boxes, the trees as poles with canopy boxes, rails as paths, the stars as
   coins. Exit: a playtest of the first 10 seconds and of every loop; a cart scenario per glide
   (G1–G9), per kick line (kick pair, chimney) and per tier climb, as the shrine's scenarios
   300–316; the six worst views measured with boxes (placement counts) and stand-ins on.
2. **The game features the stars need:** `star`, the red-coin count, switches, the timer, a
   mover started by a trigger, a trigger box, saved flags switching layers, the pound hook.
   With grey boxes, all five stars can be played. *Built (12.5).*
3. **The shrine core:** move the built shrine in (A's changes: the pagoda's place and collision,
   three wall gates, the north stair, the bamboo fence removed, the hollow cedar, the rope deck,
   the rope ladder, the kick pair, the chimney). Most of its 50 assets are reused as they are.
4. **The town:** the shop, alley-house and machiya families first (they carry the budget), then
   the adapted lab pieces (levels and collision added), then the viaduct and station. Measure V1,
   V4 and V5 after each family.
5. **Texture split** into common and region sets (8.5); the far stand-in caps; decide the far
   ring (8.3).
6. **Life, coins, secrets, sound hooks.**
7. **The seams:** the east underpass with a placeholder downtown block (a few boxes in a second
   region) to prove the swap; the bamboo blend.
8. **Night and the festival layer** (optional).

---

## 10. Open questions for the owner

1. **Size.** 320 × 384 m (30 cells) is twice the built shrine and several Mario 64 levels in
   area. Is that the scale for one level of the city? A smaller cut (drop the bamboo grove and
   the school: 256 × 384, 24 cells) keeps everything else.
2. **The race (★5).** Is a timed goal welcome as one of five? The alternative is a night
   festival goal (the yagura, lantern-line grinds), which needs day and night first.
3. **A 100-coin reward:** a sixth star, or nothing?
4. **Stars in an open world:** after taking a star the player stays where they are (no exit to a
   hub, unlike Mario 64)?
5. **The far ring (8.3, V5):** spend triangles on seeing the stage from the spawn, or paint the
   mountain into the backdrop for the station plaza?
6. **One region or two:** this spec keeps town and shrine in one region (one texture set, 14
   slots, tight). Splitting them would need a swap seam inside the level (at the torii or the
   front road), which the open layout does not have.
7. **Lab models:** adapt them (levels, collision, the shrine's palette) as written, or remodel the
   town pieces at town density and keep the lab models for showcase places only?
8. **Life:** are walking pedestrians wanted, or a quieter town with animals only?
9. **Train roofs:** riding the train inside the level (as a moving platform to the platform) is in
   ★5's approach 1 as an option; should it be general?
10. **Which neighbour** is east (downtown, the electric town) and which is north-west (bamboo)?

---

## 11. Risks

- **The spawn view (V5) and the high views (V2)** sit at 3,850–4,050 estimated triangles; the
  town's density is the variable. Measure in phase 1 with boxes.
- **Lab models are heavy** (700–1,800 triangles, one with levels); adapting them is real work,
  not reuse.
- **Texture VRAM** is at 14 of 14 slots in the plan.
- **Region seams** (the swap spread over ticks, the checker's seam check, a second stand-in level)
  are not built; the east edge depends on them.
- **G8's line** threads the gate (1.5 m) and the torii (about 1 m): if the torii asset's lower
  beam is lower than 10.4 m, the line moves 2 m east to pass beside the post.
- **Glide reach** from the stage is 254 m: every rim must be higher than the glide arrives
  there, and the north-east summit's edge needs a check.
- **Collision seams** on 100+ small roofs and the alleys' cameras.

---

## 12. The joined grey box (2026-10-05)

The three regions were built in parallel (town z 0–128, core 128–256, mountain 256–384) and then
joined into one world, `shrinetown`, in the movement garden. What follows is what changed from
sections 1–11 while building it; the region notes (`notes/town.md`, `notes/core.md`,
`notes/mountain.md`) have each region's reasons in full. The cart scenarios 400–446
(`carts/garden/tests/shrinetown_cases.akr`) are the measurements.

### 12.1 Owner decisions

- The pagoda is the shrine's real one, its tiers 3.6 m apart (section 3.8), with the climbing
  collision `arch_pagoda_town_col`.
- Rope ladder A is the real `forest_rope_ladder`: plumb, 20 m, on a sheer face (section 3.12).
  A pole let the body go round it, into the rock; since phase 2 it is a front pole, held on the
  ladder's front (12.5).
- The circling glide into the knot hole is an accepted expert route; the rope stays the way in.
- The viaduct deck is 9.0 everywhere, the platform floor 10.0 (the station's wider spans are
  for the real assets; the grey-box deck is 12 m wide).
- Utility pole wires at 8.0 m.
- Stand-ins capped (8.3, option 1): 90 triangles a town cell, 140 the landmark cells (c2_3,
  c2_4, c2_5), 60 every other, the ground on a 32 m grid (the World Kit's `standins.triangles`,
  `ground` and `cells`). The pond's cell keeps its water whole: 110.
- The cart holds 128 poles and 128 rails, and a world with more fails to load.

### 12.2 Changes the 3D made (with the scenario or check that found them)

| Where | Plan | Built | Why |
|---|---|---|---|
| Pagoda terrace | 20 | 15, cut into the ridge (banks eased over 16 m) | G5 from the real temple (27.5) came down 3.6 m under roof 1's eave (414). Open for the owner: keep 15, or keep 20 and end G5 on the terrace |
| Step to roof 1 | none | stone lantern, top 16.4, in front of the south face | the chained jump is 3.0 m measured; roof 1's fascia is 5.0 up (422) |
| Kick pair | x 164 / 169, one KICK_CEDAR south of the pagoda | x 171.35, z 259.5 / 264.5; trunks to 34.5, crowns 34–38 | roof 1's eave closed the single cedar's shaft; the body crosses to roof 2 by drifting east between kicks (420); taller crowns caught G6 |
| Star 1 | 51 | 45.5, 0.5 m over the finial's top | the pole's top holds the feet 1.2 under it; a pole jump goes away from the pole (422) |
| The cedar rope | ends 1.2 m short of the hole | ends 0.5 m into the hole's mouth | a hang jump from 1.2 m out bumped the lip and fell short (423) |
| Rope ladder A | 20 m from a slope at 24 | plumb from a shelf at 24, steps to it from the basin; the face at z 318, off the row seam | the slope there rises 11 m in 6 m; at z 320 (a seam) the face was missing from the body's collision |
| Road wire poles | every 30 m from x 10 | the one at x 160 split into x 152.5 and 167.5 | it stood on the axis, in the way of the walk north (400) |
| Strings from the torii | from 13.3 | from the kasagi's top, 13.8 | the town's torii |
| Viaduct | segments per region | one deck and parapet sweep along the whole line, to x 315.5, closed there by a wall | the parapets reached past x 320; walking off its end left the level |
| Canal | per region | one cliff, z 0–292 | two cliffs at a seam made a wall across it |
| Culvert | bed −2.0 to z 128 | the bed rises to the pond's (−1.4 at z 134) | it ended in a step under the pond's water |
| Level's frame | fences 3 m; rims north, west (rows 4–5), east (rows 4–5) | the neighbours' backs (22–28 m) beyond the south, east and west of the town; hoardings 5.5 m at the front road's ends; rims west (rows 2–3) and east (rows 1–3). Sized for a double jump and grab (5.15 m); re-sized by the frame's rule in 12.9 | a jump or glide off the viaduct, the danchi or the chimney left the level |
| Walkway foot | a stair round a cedar (102, 118) | a stair from the bridge's end (6.0) east along z 120 into the courtyard | not built by any region |
| Woods trail, canal path, stream | a path per region | one path each across the seams | |
| Sake brewery | the core's box | the mountain's `gbm_sakagura` (bounce sugidama) at (15, 0.66, 218) | |
| Temple ridge | 29.5 | 27.5, the real temple's | G5 judged against it |
| Pond tip | the town's water circle | the core's | two water surfaces |

The regions' own changes (alley rows, machiya rows, the chimney at (30.5, 67.5), the station,
the overpass, the terrace edge at z 166, the gate at z 172, the wall line, the fox shrine, the
ledge and chimney, the falls' lip and top, the rope bridge) are in their notes.

### 12.3 What it costs

The World Checker, full (600 views, depth mode, report), the whole level: before the stand-ins
were capped, peak 3,116 triangles, 593,006 draw CPU cycles, 647,334 GPU cycles; capped, 1,808,
410,083 and 584,668. Budgets 4,000 / 600,000 / 1,600,000. 44 collision cracks (gaps up to
0.25 m where sweeps, bridge ends and 2 m banks meet floors), as the shrine's. The worst views of 8.3 with every row
present (`tools/views.py`): README.md, "What it costs".

### 12.4 Open

- **The far ring.** From the spawn (row 0) the reader's far ring of three does not reach rows 4
  and 5: neither the pagoda nor the stage is drawn (spec 8.3 V5, 10.5). A far ring of 4, or the
  backdrop painted with the mountain, is the owner's choice.
- **The pagoda from the spawn.** With the real pagoda on the terrace at 15, only its finial's
  top clears the arcade gate (section 1.3).
- **G5** (12.2, the pagoda terrace).

### 12.5 Phase 2: the game features (2026-10-05)

The stars, the triggers and the shortcuts are entities of the garden's game schema
(`../world/garden.game.mochi`: `star`, `trigger`, a mover's `start` and `delay`, a pole's `front`;
`../README.md`, "Entities" and "Goals"), listed in `game.py`, which the three region generators
add to their cells. Scenarios 450–467 (`../tests/goals_cases.akr`) play them.

| What | Built | Scenario |
|---|---|---|
| Stars | the hanafuda moon card turning in its glint, drawn by the cart from texture slot 14; taken is saved and shows the card's back | 422 (★1), 423 (★4), 450–452 |
| ★2 | the eighth red coin sets `red_coins`: star 2 comes down onto the torii's top beam | 450 |
| ★3 | the bell's rope: a touch box 1.2 m square (0.6 m round the rope); star 3 comes down 2.4 m in front of it | 451 |
| ★5 | the omamori (touch, `timer` 85 s, hidden while it runs) starts the clock and the train (`game_train`, two grey-box cars on track 2, z 12.1, from x 2 to x 160); the platform's box (x 144–176, z 3.5–14, 6 m high from the platform's floor: the platform and the roofs of trains standing at it) wins | 452 (won by G8), 453 (lost), 454 (the walking route, timed) |
| A | press (B) at the ledge's lip (44) over the ladder: layer `ladder_a` | 460, 467 |
| B | press (B) on the ridge side of the bar (z 233.6–236.4): layer `gate_b_open` (its group's `gate_b_barred` goes off) | 461 |
| C | ground pound on the root plate, east and south-east of the trunk (the trail's side; the rim west of it is too steep to stand on): layer `cedar_c_down` | 462 |
| D | ground pound inside the chamber at the root door: layer `root_d_shut` off | 463 |
| E | press (B) at the roof's north edge over the ladder: layer `ladder_e` | 464, 467 |
| Saved | every shortcut stays open when the world is opened again, and on the memory card across a restart | 460–466 |
| Ladders A, E | front poles: held on the face away from the rock or wall, not gone round, not grabbed while their layer is off | 467 |

The placement agents' real assets: the rolled-up ladder A, the folded ladder E and the barred
gate go in a layer of the same group as the down/open one (`ladder_a_up` with `ladder_a`, and so
on), so switching the open layer on puts the shut one off; a real ladder's pole keeps `front: true` and,
as its yaw, the direction from the ladder to the side it is climbed on. A trigger's placement is the centre of its box's base, set 5 cm over
the floor (the World Checker reports an entity in a solid). With the real station (12.6) the
race's last legs (`RACE_TOWN` in the scenarios) go up its inside stair, and star 5 and the
platform's box stand on the real platform's floor (10.0).

### 12.6 Placing the real assets (by zone, PLACE_SPLIT)

Each zone's grey boxes are swapped for the real assets by its own module, `place/ZONE.py`, which
the region generators and `make_world.py` call just before they write (`place/__init__.py`).

#### Station (z < 40, x ≥ 64, and the whole viaduct: `place/station.py`)

What stands now: the viaduct as real pieces along its whole line; the station
(`station_concourse` with its two outside stairs and the inside stair, `ticket_gates`,
`station_platform`, the three station spans and two tapers); a two-car `train_emu_car` standing
at track 1; two `signal_gantry`s, each with a pole on its ladder; the plaza's danchi, pachinko
parlour, koban, konbini (the shrine's `street_konbini`), bus stop, newsstand, four bike shelters
with eight `mamachari`, a taxi rank, a phone booth, a postbox, three of the shrine's
`street_vending_machine`s, two benches, two planters and the konbini's corner pole
(`town_utility_pole_transformer`). `city_bus` is left out (OVERNIGHT_DECISIONS 16).

| Where | Grey box | Real | Why |
|---|---|---|---|
| Viaduct line | swept deck and parapets along layout's polyline; the north run at x 302 | 16 m pieces: spans from x -8 (joints at x = 8 mod 16), the station x 136-184, tapers either side, three 30-degree curves (R 30.56) from x 280, the north run at x 310.56, the underpass, two curves east out of the level | the pieces join only end to end and turn by 30 degrees; x 310.56 keeps the bend and the piers off the sports ground and the school |
| Piers | 1.6 x 8 under each grey span | each piece's two-column bent; at x 48 one stands in the canal | the station's joints fix every span west of it |
| Underpass | a span over the straight road | `viaduct_underpass` at (310.56, 114.56), yaw 90: the road 25 degrees north of east between abutments, asphalt painted along the skew | the asset is built for the dog-leg (7.1); the straight road meets its west wing wall at x 293-300 (z 114.6-118) and walks on east into the corridor |
| Deck's east end | wall at x 315.5 | the same wall (`gbc_viaduct_end`) where the centre line reaches x 315, heading 58.8 degrees; the second curve runs on past it out of the level | the line leaves between the rims (z 132-154) |
| Parapet rails | 10.2, 5.85 m off the line, the north one open over x 146-178 | 10.2 on the real parapets: 5.875 off the line, 7.475 through the station (tapering between), the north one in three with gaps at the outside stairs only (x 148.35-151.65, 168.35-171.65) | `parapet_n_m` is new: the concourse's parapet between the stairs |
| Outside stairs | x 150-154 and 170-174, foot z 32 | x 148.5-151.5 and 168.5-171.5, foot z 34.6, landing 9.0 at z 15.6-16.6, roofed | the asset's; they reach the walkway, not the platform (no track crossing) |
| Platform | the deck (9.0), canopy 12.8 | floor 10.0, canopy top 13.47 (middle) to 13.72 (edges) | GREYBOX_SPLIT; the inside stair is the way up |
| Stair coins | on the grey ramps at x 152, 172 | on the real treads at x 150, 170: y = 0.5 (34.6 - z) + 0.7 | they were inside the real steps |
| Red coin 3 | 13.5 | 14.17 on the canopy | the real canopy |
| Star 5, the platform's trigger (`game.py`) | 10.4; box from 9.05 | 11.4 (1.4 over the floor); the box from 10.05, over both tracks, the walkway north of track 2 outside it | the real platform's floor, 10.0 |
| Konbini | box 36 x 14, roof 5.6 | `street_konbini` (36 x 14, deck 4.7, coping 5.0), front to the plaza; the door entity at (187.5, 33), on the real door (x 186–189) | the same footprint; the door moved at the join (scenario 431 starts before it) |
| Konbini roof sign | 5.6-7.0 | the same grey sign, 4.7-7.0, on the real roof's deck; red coin 5 on top | no real asset has a roof sign |
| Danchi | 16 x 16 box, ramps round it | `danchi` 16.2 x 13.4 (z 19.4-32.8), its own stair tower on the north face to the roof (18.8) | |
| Koban | 12 x 10 box, 5.9 | `koban` 4 x 3 (5 x 4 with eaves) at (122, 24), front east, eave 3.35 | the asset's size |
| Pachinko | 16 x 16, 9.1 | 11.4 x 10.3 at (100.5, 26), front east, antenna 8.85 | |
| Vending machine (route D) | at x 177.4 | `street_vending_machine` at (179.1, 29.8) against the konbini's west end, 1.9 | the konbini's roof is 3.1 up |

Scenario changes: 401 walks the inside stair (through a ticket gate's aisle at x 158.6, west of
the middle bent's column at x 160) onto the platform (10.0); G2 (411) takes off from the real
roof at (78, 22) with no run-up (from (85, 20) it stood on the top balcony at 16.1, and a
run-up's first jump carried it off the roof's north edge). The race's cases (452, 454) walk the
same stair (`RACE_TOWN`); the platform's box is reached at the stair's head (8.5), and 454 no
longer adds the stair's 4.5 s to the measured route, which now includes it.

Costs (World Checker, full, the whole level with the other zones still grey): peak 2,148
triangles, 598,458 draw CPU, 591,544 GPU. The peak is the ticket hall looking west, with the
platform and the train over its ceiling; it is kept in by the train's level 1 from 9 m (band 1)
and the plaza's small props culled sooner (`lod.assets`, set in `world()`). Texture cuts made
(TEXTURES.md): the zone's 8-bit textures 4-bit (koban, danchi facade, pachinko storefront, bus
stop, bike shelter sign), the ticket gates' floor a repeating 32 x 32, the newsstand's goods,
sign and sides at half width, the postbox's cap a 32 x 32 pattern, `street_vending_machine` for
`vending_machine`.

#### Street (40 ≤ z < 128, 64 ≤ x < 210: `place/street.py`)

`place/street.py` (called by `notes/gen_town.py` and `make_world.py` through `place/__init__.py`)
takes out the zone's grey boxes, all but the great torii (the shrine zone's), and places the real
assets. What differs from the grey box:

| Where | Grey box | Real | Why |
|---|---|---|---|
| Shops | boxes 14 × 9 m, roofs 6.5 / 9.5 | west row yaw 270, east row yaw 90; 2F roofs 5.0–6.5 (gables and terraces), the record shop's back room 7.3, the 3F's roof 9.3 inside a 9.5 parapet | the assets. West: corner C (left, no awning), 3F, tobacco, record, ramen, 3F; east: corner C (no awning), A (no awning), 3F, A, B, 3F |
| Bounce awnings | six 1.5 m boxes at 2.6 | `town_awning_bounce` (top 2.7–2.9) on the street fronts of w0, e0, e1 and the back walls of w2, e3, w4 | the record shop's back roof (7.3) is above a bounce from 2.9 (7.4), so it has none behind it |
| Arcade | roof z 62–94, gates at z 60 and 96 | roof z 61–93 (two `arcade_roof_16`, columns at z 65/73/81/89), gates on the plot lines at z 54 and 94 | at z 60 and 96 the gates' pillars went through shop awnings; at 54 and 94 no awning reaches |
| North gate | beam 7.0–8.3 | the name board's underside at 5.11; its collision is the pillars only (`arcade_gate_posts_col`) | G8 comes in under it with its feet at about 4.3 and struck the board (417) |
| Alley houses | 24 boxes, 6–8 m | `town_alley_house_a` for 6 (roof 4.8–5.9), `_b` for 6.5 and 7 (6.5–7.0), `_c` for 8 (6.0–7.1, platform 8.0); doors to the plaza in the first row, to the road in the last, alternating between | |
| Fire tower | box at (102, 74), pole at z 70.55 | `fire_tower` yaw 0, the ladder's pole at (102, 72.08), 15.2; the alley plot west of it (x 90–99.5, z 66–74.5) left to its yard | its hose shed (x 97.6–100.3, z 73.3–75.4) stood in that plot's house (x 89.7–99.8, z 65.4–74.9 with its eaves); moved, the house would meet its neighbours, and the tower stays at (102, 74) for G4 (413). Done at the join |
| Kura | box x 108–111, 8.0 | `town_kura` (new; the town's common plaster and kawara, no texture of its own) at x 106.3–109.3, z 70–78, roof 7.5–8.0 at 15° | the kick pair (FOLLOWUPS): kura roof, the railing (12.9), the eave (14.6), the cap |
| Dagashi, coin laundry | a box; no laundry | `dagashi_shop` at (128.5, 46.5) facing the plaza's walk, two gachapon and a jizo; `coin_laundry` at (130.75, 100.6) facing the road | |
| Building | box 18.3, a ramp up its east face | `street_building` at (193, 73) yaw 90: roof deck 15.2, parapet 16.0, tank 18.2; its own stair at its south end (z 44–48) | the ramp is gone; G1 from 15.2 comes down on the east side hall's south half (z 134): 410's target is now (192, 138) |
| Shortcut E | a 17.9 m ladder box, pole 18.3 | the escape's stair in no layer (with the collision), its ladder folded (`town_fire_escape_up`, layer `ladder_e_up`) or down (`town_fire_escape_down`, `ladder_e`), group `shortcut_e`; the pole at (198.5, 103.95), 7.6, front, yaw 0; the trigger on the roof at 15.25 (`game.py`) | two copies of the stair's collision, one a layer, overfilled the pack's collision lookup (270 triangles of one kind in a bucket, at most 255) |
| Wires | one rail per line through the poles | `town_utility_pole_transformer` everywhere; two wires per line, 0.8 m either side, at 8.0, each a rail drawn as a thin sweep (`wire_*_a`, `_b`, material `wire`, no collision) | the asset (GREYBOX_SPLIT's decisions) |
| Front-road poles | z 104 | z 106, yaw 90 (wires at 105.2 and 106.8), the whole road from x 10 to 280 | at 104 the south wire (103.2) went through the 3F shops at the shotengai's mouth and grazed the fire escape |
| Wire coins | on the old lines | the road's on the south wire (z 105.2), the service lane's on its east wire (x 138.55), the konbini wire's on its east wire | |
| Floor coins | 0.7 over the boxes | 0.7 over the real roofs (from the collision) | |
| North verge | four cedar boxes (x 66–92) | `tree_zelkova` (the town's street tree, as the east zone's) | the shrine's `tree_cedar` is 5.6 KB the town's set does not have |
| Props | none | lamps (`town_street_lamp` in the shotengai, poles to 3.8; the shrine's `street_lamp` along the road's north side), signs, curve mirrors, a firepost, a crane game, kanban, bikes, crates, aircon units, plants, laundry poles, the kei truck, the recycling station, a bench | spec 8.2; not merged (a merged chunk has no levels or cull and drew 360 triangles from 97 m) |
| Delivery van | — | left out | 14 KB of the town's shared set for one prop; its right side mirrored from the left would read backwards |

Levels of detail sooner than the recipes' (`lod.assets`): the ramen shop from 16 m, the record and
tobacco shops from 20, the building from 30, the arcade gates from 30; the small props culled at
40–70 m. The worst views (`tools/views.py`, every row present, the other zones still grey): V1
1,711 triangles, 541,156 draw CPU, 557,187 GPU; V5 1,298 / 454,162 / 358,995; V4 1,573 / 458,832
/ 420,689; the platform looking north 1,630 / 556,198 / 392,100. The street's textures: 146,816
of its 147,456 bytes (`tools/textures.py`).

#### East (the school, the overpass, the front road's east part, the culvert)

`place/east.py`. It also places the pool and the sports ground. They lie south of z 40, but they
are the school's.

| Where | Grey box | Real asset | Why, and what it changes |
|---|---|---|---|
| School | a 30 × 30 box to 18.9; one 26° ramp up its east face from z 48 (x 288–290.5) | `schoolhouse` at (273, 71): an L. The classroom block is x 259–283, z 75–86, roof 18.9; the wing x 259–267, z 59–75, roof 15.18; the clock tower rises to 22.3; the fire stair is on the east end | The roof to stand on is the block's 11 m depth. The fire stair's foot is at (283.8, 76.3), reached from the sports ground across open yard. A paved strip (x 281–287, z 52–76) marks the way. The flagpole is a pole at (279, 69), 9.1 m |
| G9 | take-off at (273, 70) after a 4 m run | take-off at (273, 80), a jump on the spot (`shrinetown_cases.akr`) | (273, 70) is now the porch's roof (6.0). From (273, 80), a run-up carries the first jump over the north parapet. Scenario 418 lands at (276, 150), height 3.6 |
| Gym | box x 214–238, z 64–94, 9.0 | `school_gym` at (226, 79), yaw 270, entrance east | The same footprint, crown 9.0. Its roof is a bonus route (canopy 3.45, eave 7.4) |
| Pool | terrain cut x 214–240, z 22–40 to −1.2 | `school_pool` at (227, 31); cut x 216–238, z 26–36 to −1.3; water −0.3 | The cut is the asset's tank opening. The liner's floor is 0.1 above the cut, so the two do not z-fight |
| Tyre steps | two boxes, 0.8 and 1.6 | `sports_tyre_steps` × 2 at (249, 25) and (249, 28) | Tops 0.35–0.67 |
| Climbing frame | box to 2.6 | `sports_climbing_frame` at (269, 33) | Four climbing poles to 4.38. The overhead ladder's hang rail is at 2.2, not the generator's 2.3, which is inside its collision (2.24–2.48) |
| Goals | none | `sports_goal` at (247, 35) yaw 270 and (289, 35) yaw 90 | The crossbars (2.25) are rails |
| Overpass | deck and two ramps, no rails | `overpass` at (262, 111), yaw 90 | The same deck (7.0) and stair feet. Two handrail rails at 8.12: each runs down one stair, along one side of the deck and down the other stair. The deck's collision is split where the stairs meet it, so there is no T-junction. The sign's texture is 128 × 48 (TEXTURES.md) |
| Road poles at x 220, 250, 280 | boxes at z 104 | `town_utility_pole_transformer` at z 106, yaw 90 | On the street zone's road line: its wires (8.0, z 105.2 and 106.8) run from x 10 to 280. Moved from z 104 at the join |
| Trees | maples at (216, 122) and (248, 121); zelkovas at z 100, x 280–316 | `tree_zelkova` in the maples' places, and four at z 97, x 268–289 | One leaf sheet for the whole zone. At z 100, and east of x 290, the 6 m crowns reached the wires and the viaduct's deck |
| Props | none | school-zone signs at (244, 101.5), a curve mirror at the gym's corner, a hydrant, and two benches by the sports ground | |
| Culvert | road slab and channel | unchanged | No real asset |

The school's collision is split where the fire stair's top landing meets the roof, so there is
no T-junction. Scenarios 400–446 pass. The worst view measured in the zone is 1,145 triangles,
296,281 draw CPU cycles and 606,074 GPU cycles. The zone's textures are 24,864 bytes of its
26,624. The pool and the sports ground add 4,352 bytes, which `tools/textures.py` counted as the
station's because they are south of z 40; since the join it counts them as the east's (18,304 of
26,624 with the other zones' shared tiles out).

#### Canal (x < 64, every row: `place/canal.py`)

| Where | Grey box | Real | Why |
|---|---|---|---|
| Machiya | ten boxes, rows x 4–18 (7.5) and 24–40 (7.0) | `town_machiya_a` (ridge 8.0) west, `_b` (7.0) east, turned to face the lane x 18–24 (yaw 270 and 90); the east row's backs at x 38.3 | the asset's frontage is 10 m along its X: a row along z needs it turned; b is 14.3 deep in the 16 m row, so the bank's strip is 5.7 m |
| Sento | box x 8–30, z 60–73 (8.0), boiler room x 32–36 (5.0), chimney at (30.5, 67.5) | `sento_front` at (21.7, 0, 63.25): x 10.9–32.9, z 56.8–69.7; its boiler room (5.0) and chimney (18.2) at (30.5, 67.5) as before | the asset agents' origin (14.7, 64.25) puts the chimney at layout's (23.5, 68.5); glide G3 (scenario 412) and red coin 7 start at the grey box's (30.5, 67.5), so the sento moves 7 m east instead. The lane past its front (z 52.4–56.8) is 4.4 m |
| Chimney ladder | pole at (32.45, 5.0, 67.5), 13.2, east face | pole at (30.5, 5.02, 66.7), 13.18, the iron ladder on the chimney's south face | the asset's ladder |
| Road bridge | slab −0.5–0 | `canal_road_bridge`, humped (crown 1.0, parapets 2.1); its two lamps are poles (48, 2.1, 104.2 / 117.8), 2.75 | |
| Footbridge | slab 0.1–0.3, z 59–61.5 | `canal_footbridge` at (48, 0, 60.25), crown 0.8, parapets 1.55 | yaw 0, not PLACEMENT_NOTES' 90: the walk runs along the asset's X, across the canal |
| Grille | bars 0.4–0.8 | `canal_grille` at (48, 0, 1), yaw 180 (its front upstream), its slab across the canal at 0.2 and fence rails 1.33 | |
| Arched bridge | the core's plank sweep `core_canal_arch` | `canal_arched_bridge` at (48, 0.6, 160), yaw 0; its two top rails are rails (`canal_arch_rail_0/1`); the ground at its east foot (x 53–56, z 156–164) set to 0.6 | the woods' edge there is about 1.0 |
| Park | boxes | `festival_yagura` (ladder poles at (23.2, 0.6, 163.1) 3.3 and (21.4, 3.05, 162.0) 2.95), `park_toilet` (front east), `park_slide` (yaw 180, tower south; ladder pole (12, 0.6, 137.75) 2.4), `park_jungle_gym`, `park_swings` (origin z 139.9; top bar and safety rail are rails at 3.22 and 1.27) | |
| Watermill | house and wheel boxes | `watermill` at (42.27, 0.6, 196): its bank edge on the canal's wall (x 44), the wheel in the canal | z 196, not PLACEMENT_NOTES' 200.5: there the mill would stand in the plank bridge (z 203.5) |
| Sake brewery | `gbm_sakagura` at (15, 0.66, 218) | `sakagura` at (15, 0.7, 218) on a pad (x 5–25, z 210.5–225.5, set to 0.7, falloff 3) | the bamboo's foot rises 0.6–1.3 under it |
| Trees | ginkgo boxes; town ginkgo at (14, 124), (32, 122) and a cedar at (58, 122) | the shrine's `tree_ginkgo`; the town's three moved north of z 128: ginkgo (12, 130), (39, 130), cedar (59, 131) | in the town's rows they would load the shrine's tree tiles into the town's texture set |
| Bamboo | `gbc_bamboo` and `gbm_bamboo` scatters | `tree_bamboo_tall` in three scatters (loose on a 6 m lattice, two clump sets on 9 m held near their squares' centres: twos and threes) and `plant_sasa` under them, x 2–44, z 206–380 | |
| Canal's spring | slab `gbm_spring` | three of the shrine's boulders round the canal's head | |
| Road's west end | road works box (x 0.5–1.5) | two of the shrine's `street_barrier` across the road, facing east | |
| Utility poles x 10, 40 | boxes at z 104 | the shrine's `street_utility_pole` at z 106, yaw 90 (crossarm across the road) | the street zone's road poles and wires: two wires 0.8 m either side of the poles, clear of the shops at z 104 |

Props, culled at 40–50 m and placed one by one (a merged placement draws its level 0 at any
distance): potted plants, bicycles, a laundry pole, air conditioners and bins along the machiya
lane and the bank; a hokora and a jizo at the footbridge's west end; a bench on the canal lane;
in the park benches round the dance ground, three of the shrine's lamps, shrubs behind the toilet,
a stone lantern at the arched bridge's foot, a shishi-odoshi by the mill and a tanuki at the
brewery's door.

Textures (`tools/textures.py`): the canal's town part 25,472 bytes of 26,624, its shrine part
32,640 of 36,864. The cuts: the footbridge's waterway and year plates are the road bridge's (it
keeps its own name, 湯屋橋), the sakagura's two 8-bit textures (sign board, barrels) are 4-bit,
and the zone places no `firepost` (its alarm is 8-bit) and no reeds.

#### Shrine (z ≥ 128, x ≥ 64: `place/shrine.py`)

`place/shrine.py` (the zones' hook, make_world.py's `world` stage) takes the zone's grey boxes out
of the generators' cells and places the real assets: the shrine's (`../shrine/assets`: halls,
gate, temple, pagoda, white wall, great torii, lanterns, the walkway's cedars and platforms, fox
shrine, statues and torii, the stage hall, the falls, stepping stones, lily pads, trees,
undergrowth) and the level's own (`assets/NAME/`), with three small pieces of the zone's own in
`assets/shrine_extras/` (the north wall's plinths, the stage's stilt ladder, the rock the falls
pour from). What changed from the grey box:

| Where | Grey box | Placed | Why |
|---|---|---|---|
| White wall | chamfered corners, x 115–213, z 167–233 | 8 m and 4 m modules with corner posts: x 117.6–210.4, z 168.6–237.4; west gate at z 201, east at 193, north at x 162 | the modules tile only in runs of 4 m between gates and corners |
| Terrace | z 166–234 | 166–238 | the wall and the temple moved north |
| Temple | terrain podium (134–186, 208–228), stair, a box | `arch_temple` (its own podium, 52 × 24, and stair) at (160, 5, 221.75): its ridge (27.5) on G5's take-off line (414) | the real ridge is a 1.1 m line; the grey box's top was a 10 m flat |
| North wall | 2.6 m | on a 1 m plinth: 3.6 m over the terrace (decision #5); the north gate's own module stays 2.6 | a double jump (3.4) cleared it |
| North stair | from (160, 233.6) | from (162, 237.9) to (174, 15, 256.5), 25° | the gate and the terrace moved |
| Treetop decks | boxes 6 × 6 | `forest_platform` (7 × 7, railing gaps mid-side) on `tree_cedar_giant`; each turned so its gaps face its bridges, the bridges running gap to gap; the crown's landing a platform on the crown deck's cedar at 15 | the railings closed the bridges' ends |
| Kick pair | grey trunks | `tree_cedar_giant` drawn, the grey trunks (`gbm_cedar_kick_*_col`) their collision, turned by 90° only | two flat faces 3.2 m apart (420) |
| Sacred cedar | west-facing box | `tree_cedar_sacred_hollow` turned 59.7° so the knot hole faces the rope deck; the rope ends 0.5 m into the hole's mouth (151.6, 23.25, 294.6); `forest_shide_rope` along it; the root curtain in the door below | (423) |
| Fox torii | grey frames | `forest_fox_torii` drawn at the same places, the grey frames (`gbm_fox_torii`) their collision | the real posts are 2.5 m apart, inside the 3 m steps: the walking route (454) caught on them at the switchbacks |
| Stage | deck 138–170 × 340–354, hall behind to 374 | `forest_stage_hall` at (154, 60, 350): deck z 340–360, the hall on it x 144–164; the pad behind at 59.5 | the real stage is 22 m deep |
| G6 take-off | (162, 353) | (166.5, 353), beside the hall (scenario 415) | (162, 353) is under the hall's eaves |
| Stage stairs | landing stair and falls bridge at z 347 | at z 345, the side railings' gaps (and 454's route) | |
| Bell, star 3 | (154, 353.9) | `forest_stage_bell` under the hall's front eave, its rope at (154, 347.15) (game.py's BELL; 451's positions) | (154, 353.9) is inside the real hall |
| Stilt ladder | pole 16 m | 18.3 m, over the deck's front railing (61), with `shrine_stilt_ladder` | the railing |
| Falls | a water sheet in front of a box (17.5–48) | `water_falls` (34.2 m), `forest_falls_cave` and `shrine_falls_cliff` at (214, 12, 330); the lip 48.3, a notch to 46.15 where the water pours; the stream's last 6 m drop into it; the cave's 6 coins moved into the real cave (z 332–335) | the real falls are 1.8 m shorter than the drop |
| Great torii | grey | `arch_torii_great`, posts as poles at x ±5 (9.9 m); its top beam 13.1 in the middle (450 reads 13.1) | the real kasagi |
| G1 | lands ≥ 9 on the east hall | ≥ 7.5 (410) | the real hall's roof slopes from 10.9 to 4.85 |
| Coins | over the grey roofs | 1 m over the real ridges (side halls 11.9, corridor halls 15.3, gate 18.8, temple 28.5 at z 221.75); the crown deck's off its trunk (+1.5, +1.5); the lantern strings' coins with their strings | |
| Cemetery | grey rows 20 m, no walls, no first flight, gate at z 130 | per terrace 4 `cemetery_terrace_wall_12` (x 256–280, 292–316) and 4 grave rows 5.5 m behind the edge, a sotoba rack; the middle stair 12 m wide (x 280–292) at every edge, the first from the lane (z 126.4, FOLLOWUPS); `cemetery_gate` at the head of the first flight on terrace 1 (286, 1.8, 131.4), in the shrine's texture region; the jizo hall at (299, 16.2, 241) | the walls stop at the stair |
| Komainu | one pair asset | each lion alone (`arch_komainu_a`, `_un`, from gen_komainu.py) either side of the gate stair's foot | the pair stands 1.1 m apart |
| Dead cedar | boxes | `forest_dead_cedar` / `_fallen` at (256, 306), −Z across the gorge (yaw 111.8) | |
| Rope ladder A | a box | `forest_rope_ladder` (`ladder_a`) and `_rolled` (`ladder_a_up`, on, the same group) | |
| North gate | boxes | `arch_wall_gate_shut` + `arch_wall_gate_bar` (`gate_b_barred`), `arch_wall_gate` + `_bar_lifted` (`gate_b_open`); shortcut B's trigger at (162, 5.05, 239) | |
| Forest | grey trees, fill 0.8, thinned from 56 m | the shrine's maples, ginkgo and cedars, fill 0.68, thinned from 44 m; undergrowth (fill 0.3, cull 36) and leaf litter (cull 24) as the shrine's; reeds round the pond | the draw CPU in the woods (below) |

Not merged though planned so: the grave rows, the terrace walls, the lanterns, the komainu, the
koi and the jizo have repeating textures, which a merged mesh cannot keep. The kick chimney stays
the grey box's rock. **Open:** G8 (scenario 417) now comes down on the great torii's top beam at
z 124.5 instead of in the arcade (it flew under the grey box's beam, 11.0–13.8; with the torii
switched off it lands at z 80 as before); the last train (452) still passes, landing on the torii.
**Costs** (`tools/views.py` and the World Checker, full): every view under budget, the checker's
peak 2,635 triangles, 588,731 draw CPU, 885,098 GPU; the heaviest views are the woods' (deck 3
looking east 515,958 CPU). The zone's textures 50,816 bytes of its 90,112 (`tools/textures.py`),
the shrine region 93,088 of 307,200, no 8-bit textures.

#### The join (the five zones together, 2026-10-05)

The five zones' branches merged on `shrinetown-join` (station, street, east and canal, then the
shrine). What the join changed:

| What | Change |
|---|---|
| The hook | one `place/__init__.py` (`apply(STAGE, globals())`); in `gen_core.py` and `make_mountain.py` the game's entities first, then the zones |
| Grey-box recipes | a region generator no longer writes a grey-box recipe its cells and part do not name (`place.unused()`), and `make_world.py` deletes those the world stage swapped out (the shrine zone's); of 218, 31 are left |
| Asset directories | `make_world.py` lists `assets/greybox/core`, `assets/greybox/mountain`, `assets/*` and `../shrine/assets`; a zone adds a folder only when no glob holds it (`place.add_dir()`) |
| Front road poles | east's three at z 106, yaw 90, on the street zone's line; the station's konbini corner pole (210, 33) at yaw 0, as the konbini wire runs |
| Konbini door | the door entity at (187.5, 33) on the real door (x 186–189), in cell c2_0; scenario 431 starts at (187.5, 36) |
| Fire tower | the alley house west of it left out (its plot is the tower's yard): the tower's hose shed stood in it |
| Textures | `tools/textures.py` counts the railway as the station's wherever it runs, the schoolyard south of z 40 as the east's, and the shrine zone's placements (`sh_*`) as the shrine's wherever they stand: the great torii (c2_1) in the town's set, from 1 KB the street's allowance gave up (TEXTURES.md, "As placed") |
| G8 (417, 452) | from the deck (60) the glide came down on the real great torii's top beam (13.7, z 124.5); it now takes off from the slope east of the stage, (174, 61.7, 356), and lands in the arcade at (160, 84). The race (452) walks off the deck's back (z 362) and round onto the slope: the platform at 50.7 s |
| Views | the street's real assets put the views from the inside stair, the canopy and the air over the station at 620,000–725,000 draw CPU; levels and culls sooner (below) bring the full check's peak to 616,847 |

Levels and culls set at the join (`lod.assets`): the train's level 1 from 6 m (was 9); the ticket
gates' from 12, the newsstand's and the bicycle shelters' from 14, the tapers' from 20, the
koban's level 2 from 45; the dagashi shop's levels from 20 and 45, the shops' (`town_shop_2f_*`,
`town_shop_3f`) level 2 from 40; culls at 36 (potted plants), 40 (crates), 45 (benches) and 56
(the utility poles, with the wires' sweeps). `gachapon`, `jizo`, `town_kanban_set` and
`town_road_signs` had no `lod`, so the street's culls for them did nothing (the World Kit's
`lod_unused`): their generators now give them `"lod": {"cull": 50}`.

The full check (600 views), five zones: peak 2,266 triangles, 617,020 draw CPU, 908,916 GPU; one
view over the draw CPU budget, on the canopy (165.7, 15.1, 6.1) looking west-north-west, 617,020,
where the canopy's faces are clipped at the near plane and the standing train is at level 0 6.3 m
off; and 5 pixels drawn in the wrong order at the seam view (16, 15.9, 320). With the street's
assets alone over the station (four zones) these views were 620,000-725,000 before the levels
above. The ticket hall looking west with the race train standing at the platform is
484,000-549,000; the camera over the station (149.7, 16.8, 2.5) looking north 623,000. Each zone's
worst draw CPU: station 617,020, shrine 509,988, street 494,590, canal 453,902, east 394,599. 50
hard failures, all cracks.

The view scenarios (`sh_view`: 440–446, and the shrine's 310–316) count late frames from frame
30: the frame after a view jumps to V1 or V4 loads the cells round it and took about 1.1 million
cycles (one late frame), which walking there never does at once; each view's own frames are
636,000–652,000 at most.

### 12.7 Far views (2026-10-05)

The owner, from the courtyard wall looking north: far off the view was still brutal. The near
cells' trees were already crossed cut-out cards past 16–20 m; what read as boxes were the
stand-ins (the far ring, from about 96 m), which drew every textured face in a flat far colour,
so each tree's two cards became two dark slabs (the cedars) or yellow and orange blocks (the
ginkgos and maples), and nothing faded with distance. Three changes, in the World Kit and the
world's settings (WORLDKIT.md, "Stand-ins made by the kit" and "Haze"):

| What | Where | Effect |
|---|---|---|
| The stand-ins' texture set | `make_world.py`: `standins.textures` `{"slots": "0"}` | the trees' far cards and the lattices (15 tiles, 23,764 bytes, 27,488 on the grid) in slot 0, held by both regions' sets: stand-ins keep them cut out (TEXTURES.md) |
| Haze | `make_world.py`: `haze` `{"start": 20, "end": 280, "amount": 0.55, "standins": 0.38}` | levels after level 0 and stand-ins fade toward the sky at 2° (day `#c6ccc2`, night `#24213e`): the stand-ins' far colours and cards exactly per variant, the levels through their tints |
| Later last levels | `place/shrine.py`, `SHRINE_LOD` | temple and pagoda 40/130 (were 30/90), gate 30/110 (30/80), great torii 40 (30), walls 28 (24), stage hall 18/90 (18/60), giant cedar 22/110 (22/80), the four trees' cards from 64 (44–52) |

Measured with the full check (600 views; before → after): peaks 2,266 → 2,392 triangles, 617,020
→ 617,020 draw CPU (the station canopy, unchanged), 908,916 → 903,706 GPU; the shrine zone's
worst draw CPU 509,988 → 531,976, its 90th percentile 435,508 → 444,527; one view over a budget,
as before. `tools/views.py`'s heaviest: deck 3 looking east 510,694 → 532,375, the courtyard
toward the gate 477,539 → 477,976, V3 stage looking south 324,643 → 343,791. With the halls'
level 1 at 36 and the walls' at 32 the courtyard view was 576,583 and deck 3 552,388, so they
stay at 30 and 28; the trees' level 1 stays where the zones put it (16–20: a tree's level 0 is
60–90 triangles, its cards 4–6).

The far views (`tools/shots.py`; `screenshots/far/before/` and `after/`), World Checker at the
same cameras (triangles, draw CPU, GPU), before → after: courtyard wall north 1,382, 308,256,
435,086 → 1,500, 328,368, 459,083; pagoda north 1,242, 347,477, 459,446 → 1,242, 347,461,
461,553; stage 1,333, 336,505, 402,855 → 1,403, 348,464, 391,151; station plaza 1,350, 415,031,
391,185 → 1,336, 412,739, 388,860; canal by the watermill 1,736, 346,810, 528,387 → 1,774,
352,422, 531,829. The pack is 11,480,668 bytes (11,456,388 before).

### 12.9 Alpha fixes (2026-10-06)

#### The cart, game and camera

From the alpha review (`ALPHA_REVIEW.md`; reviewers 03, 04, 06, 08, 14 and 19). Each fix has a
case in `carts/garden/tests/` (`make test-carts`).

| What | Change | Case |
|---|---|---|
| B5: entering the town was a tick late (1.09M cycles) | `water_cycle_find()` finds each region's water palettes once, when the world opens (from the region's day colours in ROM, about 240,000 cycles); a crossing only copies them. The town's entry is 456,000 cycles (was 642,500), the shrine's 301,000 (377,300) | 402 |
| The water did not cycle | The old search took the first palette holding a ramp's phase 0, which in the town was another texture's: the canal never moved. It also wrote the shrine's water (bank 1, colours 4096 on) past palette bank 0. Now the palette holding most of a ramp is taken, and colours go through `palette_ptr()` | 402, 403 |
| Night water (r03 #8) | Found in the day colours, so the places hold in any variant; a crossing at night cycles the night's colours | 403 |
| Night in play (r19 #12) | The tuning menu's last row, "night" (0/1), loads the variant in both regions with its backdrop, fog and water | 403 |
| B6: Y during ★5 won it in 9 s | A respawn (Y, or falling 40 m under the spawn) loses a challenge running (`goals_respawn()`) | 455 |
| ★5's train came in at 60 s, after a fast win | It comes in at 30 s, stands at the platform from 40 s to 85 s and leaves when the clock runs out (`game.py`: `TRAIN_DELAY` 1,800, `TRAIN_PAUSE` 2,700) | 452, 453 |
| A win parked the train | A started mover's first cycle (its delay included) runs to the end whatever its flag does (`attach.akr`), so the train leaves as the reward | 452 |
| Retaking the omamori just after a loss ran the old timeline | The start flag's rising edge sets the mover's clock to 0 | 456 |
| The platform's box took the trackbed and the canopy roofs | The island platform's floor only: x 144–176, z 5.5–10.5, 3 m up from 10.05 | 457 |
| Taken stars 2, 3 and 5 vanished after a reload | A taken star is at its place, its back shown, whatever its `appear` flag | 458 |
| Finding the cards (r19 #6) | A touch trigger that leads to a star not taken yet (the bell's rope; the omamori, which the platform needs) has the star's glint, 1.25 m over its base | 459 |
| The opening shows only paving (r19 #6) | For 150 ticks after a world opens the camera looks level up the spawn's facing, then eases back; the stick, L or a run ends it sooner | 407 |
| Only 8 of 13 camera zones were read (r19 #2) | `CAM_MAX_ZONES` 24; a world with more fails to load | 404 |
| The alley rail cameras faced the robot (r19 #3) | A rail zone looks the way the player runs along its axis (chosen on entry; turned round after 40 ticks running back); the zone held is kept until the feet leave it, and a change of zone turns the view (0.06 rad a tick) instead of jumping. Case 405: 726 frames running in the alleys' zones, none with the eye ahead of the runner (r19: 86 off-centre frames, 9 reversals) | 405 |
| The camera inside the robot (r19 #8) | The body is not drawn while the eye is within 0.8 m of the head | 406 |
| Wall slide onto an awning did not bounce (r08 #8) | The wall slide's landing goes through `land()` | 408 |
| HUD (r19 #10, #11; r06 #9) | A half-blend strip behind the counters; the timing readout off at the start (SELECT: timing, state, nothing) | 25 |
| Cases 461 and 463 probed the wrong place (r09 #5, r10 #5) | They probe the north gate's gateway (162, 5.6, 237.4) and the root door (151.6, 13.6, 294.6), and expect walls there while shut | 461, 463 |

Not done here: the race train's own mesh and its path along track 2 (the station's; `game.py`
takes them through `RACE_TRAIN` and `RACE_PATH` once they exist; until then the grey-box train
runs the straight line at z 12.1), a tunnel camera zone (the shrine's; the cart now holds 24
zones), and case 414's start on the temple's ridge (waits for the shrine's climbable roofs).

#### Collision and checker kit (alpha-fix-kit)

- **Steep ground (B3).** Terrain steeper than the game's 40° floor limit was walls only, and a
  body falling into a crease between two steep faces sank through the world (45 places by the
  new drop check). The World Kit now has a heightfield key, `slide_floor_degrees`: faces up to
  it are floors as well as walls, so a falling body lands and slides down. At 70 the drop check
  finds none, and r13's walks and grid drops no longer fall through (the pond bridge, the fox
  tunnel's end, the falls' top, the north wall's bank). A body walking into a 40–63° bank now
  steps on and slides back instead of standing against it. Not set yet: `make_world.py` gives
  the ground field `"slide_floor_degrees": 70`, and the crack baseline is written again (one
  known crack goes, one 0.125 terrain crack at (102.1, 40.9, 334.1) appears).
- **Drop check.** The World Checker drops a body over every steep up-facing point (1 m grid);
  one that falls through is a hard failure (`drop_through`; in report mode the pack is still
  built). Shrine town: 45 now, 0 with slide floors at 70.
- **Sampling.** 8 yaws instead of 4; layer sets only where their placements are drawn; vantage
  points from `verification.vantage_points`, checked on every build on top of the 600. The list
  for the town and the shrine (42 points, 126 views, from r01 and r02) is ready for
  `make_world.py`; with it the check flags 43 positions over 600k draw CPU, worst 786,145 (the
  follow camera over the platform).
- **Kit fixes.** s6's missing facade triangle (a sliver paired first into a quad); merged meshes
  keep a cull all their props share (the sotoba racks now cull at 84.8 and 86.9 m: the racks'
  60 plus their spread), else warn (`cull_merged`: `sh_omikuji_terr` in c2_3);
  `palette.reserved` (give it `[254]`, the star's); the stand-ins' common set is stored once and
  copied on the first crossing only (61,824 bytes, about 58,000 cycles a crossing); the camera
  error names the bad camera name. The fire stair's opaque slab is not a kit fault: it is
  `street_building`'s level 1, a solid box, drawn from 30 m in the town.

#### Workstream 7: occluders

**What was built.** Hand-placed occluders in the World Kit (WORLDKIT.md, "Occlusion"): a recipe
declares occluder boxes or quads and camera zones; the kit works out, per zone, the placements of
the near cells and the stand-ins of the far ring that one occluder hides from every point of the
zone; the pack stores those sets (WORLDPACK.md 1.5, "Occlusion zones"); the reader finds the
eye's zone once a frame and skips what it hides; the World Checker draws with the zones, judges
its pictures against what is in sight without them, and casts rays from every zone to what it
hides (the occlusion check). The scheme is a potentially visible set per zone rather than a
screen-space test per frame because the test would cost about 66,000 cycles a frame with 20
occluders and 130 placements in view; the set costs about 40 cycles a zone looked at and 11 a
placement looked at in a cell the zone has a mask for. Worlds without `occlusion` build the same
packs as before.

**Applied to shrine town** in `place/occluders.py`: the viaduct deck's slab round the platform
stair's opening, the station's facade above the door and the concourse's end walls; zones under
the two tapers and in the plaza west of the station's door, at camera heights. They hide the two
train cars (256 faces each at level 0) from under the tapers and the west car from the plaza; the
leak check casts 3,600 rays and finds no leak.

**What it saves: almost nothing.** Measured with the World Checker at 70178b4's world against the
same world with the zones (the level-of-detail changes of the other workstreams not included):

| Cameras | Draw CPU before → after |
|---|---|
| r01's 20 worst cameras (`worst_cams.json`) | +15 to +47 each: no camera is in a zone |
| r02's 9 worst cameras (the viaduct deck 711,057 among them) | +16 or +17 each |
| 60 of r01's sweep views at camera heights under 6 m and over 450,000 | 30,625,567 → 30,618,586 in all; 5 views in a zone: −6,266, −5,385, +1,051, +1,051, +967 |

Why, from what was tried (the notes in `place/occluders.py`):

- Most of the cost r01 found "behind walls" is placements that are partly in sight: the
  concourse (484 faces) is the wall; the platform (366) and the train cars are 20-48 m long and
  show over or through the facade's door and windows. A placement is skipped only when all of it
  is hidden, and the kit joins no shadows, so these need occluders larger than any solid piece
  of the station (or the station split into pieces: the level-of-detail workstream's fix).
- A box in each of the town's 67 buildings and a zone every 8 m over the town hid 3,284
  placements over 640 zones, but almost none of them in view from where they are hidden: the
  views look along the streets, and what stands behind a row is beside the view. Net +500
  cycles a view (the zones' tests).
- The viaduct's parapet over the cemetery is 1.2 m over the deck; the cemetery is hidden by the
  deck and the parapet together, never by either alone. The follow camera (about 13 m there,
  r02's case 447) sees the cemetery over the parapet anyway.
- The woods decks look over cut-out tree cards (holes), which cannot occlude.

So the draw CPU overruns are for the levels of detail (r01 findings 1-3, r02 finding 1), not
for occluders. The feature stays for worlds with closed rooms and corridors (interiors, the
ticket hall from inside), where a zone hides a whole room's contents.

#### Workstream 4: the station zone and its draw CPU

The alpha review's dense sweep found 195 views round the station over the 600,000 draw-CPU
budget (worst 783,327); the owner chose levels of detail first, then occluders (another
workstream). What changed (`place/station.py` and the station's assets):

| What | Before | Now | Why |
|---|---|---|---|
| `train_emu_car` | a parked pair on track 1, level 1 from 6 m; level 0 454 triangles, 216 of them the emissive glass over the windows | no train on track 1 (the lead's decision: the last train is the one train); level 0 262 triangles, the windows the livery's glass at every level | the car changed colour at its level switch (pale emissive glass, then the texture's dark glass); the windows no longer glow at night |
| `station_concourse` | one asset: level 0 785 triangles, level 1 from 30 m | two: the shell (front, outside stairs, parapet: level 0 628, a middle level of 448 from 14 m without the posters and the roofs' posts and with the stair walls' faces only, the old level 1 from 30, the impostor from 70) and `station_hall` (the ticket hall's room and the platform stair: level 0 170, level 1 of 63 from 16 m without signs and lights, culled from 40) | the shell's bounding sphere is out over the plaza (the stairs reach z 34.6), so the plaza sees its middle level, which keeps the front, the stairs and the sign; the hall's sphere is in the hall, so a player inside sees its level 0 |
| The hall's walls | flat beige (`interior`) | the cladding's cream panels (`panel`), the void under the first flight too | the hall read as a void (r19 #9, r14 #8) |
| `station_platform` | one asset: level 0 674, level 1 from 30 | the structure (level 0 280; a middle level from 22 m: the floor's bands without the stairwell, the canopy on columns; then 34, 70) and two fittings assets, `station_platform_fittings_w` (name board, soba stand, clock, two benches) and `_e` (name board, track signs, bench, vending machine, bins, cat), each level 1 from 12 m and culled from 24 | from the plaza the parapet hides the platform's floor; a player on the platform is at most 20 m from its middle |
| Other levels (`LOD`) | mamachari cull 30; bike rack 14/30; newsstand 14/40; koban 24/45; ticket gates 12/40; planters cull 36 | mamachari level 1 from 8 m; bike rack 10/30; newsstand 8/40; koban 14/45; ticket gates 8/40; station spans 24/100; planters cull 28 | r01's measured set |
| Konbini roof sign | the grey box's block | `konbini_roof_sign`: a lightbox with the konbini's logo (the shrine's `kon_sign` cell) on two posts, its collision the grey block (top 7.0) | grey-box leftover (r14 #4); case 436 takes red coin 5 from the roof |
| Gantries' ladders | poles, held from any side | front poles, yaw 270 (gantry 0) and 180 (gantry 1) | the body went round into the column and was grabbed from the parapet rail (r08 #4); case 434 |
| Red coin 8 | 10.9 over the parapet west of the station | 11.3 (1.1 over the rail) | taken walking the deck (r05 #3); case 435 walks past it, then grinds the rail and takes it |
| The last train | `game_train`, grey boxes, on a straight line at z 12.1 from x 2 | `train_emu_pair` (two cars at `train_emu_car`'s level 1, 160 triangles; collision `train_emu_pair_col`) along the path `race_track2`: its middle on track 2 from x 24 (z 10) through the taper's S (x 120–136) to the platform's middle, x 160, z 12.1 (`place/race_train.py`; game.py's `RACE_PATH`, `RACE_TRAIN`) | it ran on the cable trough beside track 2 and stood through gantry 0 (r14 #1, r06 #3); case 453 checks it comes in at z 10 |

The danchi's balconies: only the first is reached (a double jump from the ground). Each slab is
right over the one below and a rail top is 1.44 m under the next slab, so there is no jump from a
balcony to the next; accepted (r08 #9), the back stair is the way to the roof.

Measured with the World Checker at the review's worst cameras (`r01/worst_cams.json`), draw CPU
before → after (with the parked train gone): canopy 490 642,195 → 553,662; air 523 627,618 →
578,689; over the station 623,999 → 556,482; follow camera over the platform, north-west
783,327 → 683,086, north 717,357 → 654,531, west 723,250 → 628,172; platform's east end
729,927 → 671,426, west end 649,899 → 573,820; ticket hall 656,824 → 597,090, over it 728,420 →
649,104; the passage between the concourse and the konbini 736,477 → 631,384 and 734,411 →
618,414; plaza west 716,147 → 557,214, by the bike shelters 683,085 → 631,838; deck west
727,795 → 580,231. The full check (600 views): peak 642,195 → 576,628 draw CPU, 0 views over a
budget (2 before); the pack 12,078,148 → 12,068,704 bytes. The review's sweep over the station block (its 2,158 views with x 128–196,
z 0–40): over 600,000 195 → 58, over 650,000 86 → 10, over 700,000 21 → 0, worst 784,048 →
683,388, median 386,732 → 344,738. Still over 600,000 (for the occluders): 23 views over the
platform and its canopy (follow cameras, y 12 and up), 20 in or under the hall, 8 on the
platform and the deck, 7 in the plaza and the passage east of the concourse. While the last
train stands at the platform (40–85 s of a race) it adds its 160 triangles to these views.

The fix round after the 20-reviewer alpha review (`ALPHA_REVIEW.md`), by workstream.

#### Look: the z 128 boundary, far views and level-1 roofs

| What | Change | Where |
|---|---|---|
| The boundary | The two regions' texture sets are in disjoint slots: the town's 13–1 and 16–18 (512 KB; it uses 376 KB), the shrine's 19–29 (352 KB; it uses 212 KB), the stand-ins' set 0, 31 and 30. Both can be resident at once. With the cart entering both regions once and drawing with `wp_region_loaded = -1` (a cart change, not on this branch), every near cell draws at its own levels on both sides of the line: the great torii is the real one from the courtyard, the shotengai is not grey boxes one step north of z 128, the cemetery's first flight and walls are drawn from the front road, and crossing copies no textures. A cart that enters a region at a time works as before | `make_world.py` `TEXTURE_SLOTS`, `TEXTURE_BUDGETS` |
| The backdrop | One backdrop for both regions (`art/backdrop/backdrop.png`, 1,024 × 128, 40 rows under the horizon), so nothing in it moves at the line; the ranges' and the city's feet fade into the haze, and under the horizon far low town and fields thin out into the fog colour | `art/backdrop/draw_backdrop.py`, `APPLY.md` |
| Day fog | `#d6dede` (the sky 3° up, a pale blue-grey; at 1° far hills went cream in front of the blue ranges), 20–240 (was 30–380): 87 % at 192, where the far ring may end, whole at 240. The sky's −8° stop and the backdrop's band under the horizon are the fog colour | `make_world.py` `FOG_RANGE`; `backdrop.json` `fog` |
| Night fog | `#181842` (the sky's 9° stop; was `#4e3c61`, the purple at 1°, which made far hills and tree cards glow), 16–220 as before. The stand-ins' haze takes each variant's fog colour (`haze.colors`) | the same |
| Level-1 roofs | The temple's, gate's and pagoda's level 1: a quad facing down under each roof at the eave's height (in `lacquer`, level 0's red), and the walls raised to it, so the roofs are closed from below: temple 224 → 230 triangles, gate 80 → 84, pagoda 89 → 99 | `../shrine/assets/art/make_roof_levels.py` |
| The pagoda's impostor | A star of four cards through its axis (front, side, and level 0 turned 45° on both diagonals, `arch_pagoda_diag.png`) in place of the box, which showed two towers side by side from a diagonal; still 4 double-sided quads. The temple and the gate keep the box. The stand-ins' set needed a third slot for the picture (50,702 bytes in 0, 31 and 30) | `../shrine/assets/art/make_impostors.py` |
| Edge neighbours | Level 1 (from 60 m) keeps the façade as a 16 × 16 far tile (each 4 × 4 block of the 64 × 64 tile in its commonest colour) and the stair house: 8 → 18 triangles. At night their lit panes glow, near and far (`texels` in the town's night variant) | `assets/edge_neighbour/make_edge_neighbour.py`, `make_world.py` `NEIGHBOUR_NIGHT` |
| Courtyard stand-ins | Caps: c2_2 220 and c3_2 270, so that the side and corridor halls are in them (at 140 the halls were left out and popped in under the pagoda); c1_2 140. The World Checker's `standin_triangles` threshold follows (270) | `make_world.py` `COURTYARD` |
| Coarse ground | Measured, not changed: the field's coarse level stays at 22 units and 2.5. At 40 and 1.5 the draw CPU rose by a median 13,000 cycles a view, and the views over 600,000 in a sweep along the line (x 72–312, z 112–152, 16 yaws, 2 pitches, 2 heights) went from 21 to 84 of 6,144; at 30 and 1.5, a median 3,500 and 41. At 1.2 and 1.0 the kit leaves a hole in level 0's floor under the giant cedar at (102, 252). A textured coarse level would cost no triangles | `make_world.py` `GROUND_LOD` |

The fix round after the 20-reviewer alpha review of 70178b4 (reviewer numbers in brackets: r08 is
reviewer 08's report). One subsection a workstream.

#### Street, east and canal (branch `alpha-fix-town`)

Scenarios 480-487 (`../tests/town_route_cases.akr`) prove each fix.

| What | Was | Now | Scenario |
|---|---|---|---|
| Ladder E (shortcut E) | pole 7.6 m: its top held the feet 1.2 m under the escape's lowest landing, so it led nowhere up (B7; r08 #2, r09 #1) | pole 9.0 m (`LADDER_E_H`): at its top the feet are at 7.8; let go and push south and the body is on the landing (7.6); then the five flights and a jump over the parapet onto the roof (15.2) | 480 |
| Fire tower's ladder | a pole the body went round, into the tower's eave and roof (r08 #4) | a front pole climbed from the south (yaw 180); let go at the top and push north: a ledge hang on the eave, the roof at 14.66 | 481 |
| Kura → fire tower kicks | 12.6 and `notes/town.md` said two kicks from the kura's roof reach the tower's top | not so as built: the pair gives four kicks from the ground (to about 9.8), and from the kura's roof one kick off the tower goes back onto the kura (r08 #5). The docs are corrected (`notes/town.md`); the tower's top is its ladder's. A kura tall enough for the route (about 13 m) would not read as a storehouse | — |
| Arcade's north gate | collision on its pillars only: a walk north off the arcade roof fell through the board and crest to the road (r08 #7) | `arcade_gate_posts_col` keeps the board's top 0.3 m (6.51-6.81) and the crest (6.75-8.15) too, all above G8's body (top about 5.9) | 482, 417 |
| Back awnings (w2b, w4b, e3b) | the inner half lay under the shops' eaves: a bounce struck the eave at 4.0 (r08 #8) | `town_awning_bounce_back_col`: the inner 0.85 m is a steep face (a wall) up to the shop's wall, which moves a body out onto the outer part; dropped on the middle and steering at the roof, each bounces to 7.07 onto its roof | 483 |
| Red coin 7, G3's take-off | the sento chimney's ladder ended at the chimney's top (18.2), the feet 1.2 m under it and out of a ledge's reach; the top was reached only by going round the pole (r05 #2) | the pole runs to 19.4 (the iron ladder's stiles drawn 1.2 m over the cap): from the boiler room's roof, up, let go and push north, on the top at 18.2 with the coin taken; G3 starts there | 484, 412 |
| Road wires at the overpass | 8.0, through the deck's handrails 1 m over the deck (r16 #1, r08 #3) | the poles at x 250 and 280 are `town_utility_pole_tall` (11.5 m, wires at 10.5): the span is 3.5 m over the deck; a hop from the deck catches nothing | 485 |
| Lane and konbini wires | ended on poles at z 104, 2 m short of the road's line (r08 #11) | their last poles stand on the road's line (z 106), between the road's two wires | 487 |
| Road works' barriers | the shrine's `street_barrier_col`, a 3 m wall over a 1.26 m barrier (r09 #6) | `road_works_barrier_col`, the drawn box | 486 |
| Machiya fronts | the body stopped 0.5 m into the inuyarai at the front's foot (r12 #7) | the inuyarai are in `town_machiya_a/_b_col` | 486 |
| Shop fronts | a flat collision front 0.4-0.6 m in front of the recessed glass (r12 #8) | the recess is in the collision (`gen_shops.py` `recess_col`): shops A, C (front and side) and the 3F; the record shop's (0.35 m, with its bin and gachapon in front) is left | 486 |
| School's bars | no collision (r12 #9) | two thin walls, their tops floors | 486 |
| Shop signs | 12 shops, 7 names: Ryokkoen four times, Hikari-do and Maruju twice (r15 #1) | each family's second shop is another trade in the same building, its lettering drawn as masks: the east corner Maruya's general store (`town_shop_2f_c_store_noawning`), e3 Takagi's cameras (`town_shop_2f_a_camera`), w5 Kikuya's kimono and e2 Bun'eido's books (`town_shop_3f_kimono`, `_books`, without the tea shop's rooftop sign and side advert; their glass fronts in `town_shop_3f/art/more.png`). Eleven names | — |
| North verge | the zelkovas at y 0 on a bank 1-1.6 m high, the road lamps on the tactile strip's slope (r15 #3) | the trees on the ground (`ground()`, the heightfield's 2 m grid); the lamps at z 115.8, on the flat sidewalk | — |
| The building's north end and roof | a blank end wall and a bare roof (r15 #4) | `street_building_dressing`: windows west of the fire escape, a painted advert (丸栄ビル, tenants wanted) high on the end wall, three condensers on a stand and an aerial on the roof, clear of G1's line (x 193) | — |
| The alleys | unlit at night, little dressing (r15 #5) | eleven `town_wall_lamp`s (an emissive bulb under a shade, 2.4 m up on side walls), and four potted plants, two bicycles and two air conditioners more | — |
| The school's tree | two flat-coloured spheres on the way to the fire stair (r16 #4) | the shrine's `tree_maple_small` at (278.5, 63.5), off the paved strip; the schoolhouse's own tree and leaf disc are gone | — |
| The canal's plank bridge | flat colour (r16 #5) | its own material `canal_planks`, the walkway's plank texture | — |
| The culvert's deck | a flat dark grey-box slab, the road's rows and kerbs stopping at it (r16 #6) | `culvert_deck`: the road's rows in their textures, the kerbs across it, a 0.6 m parapet over each mouth; 0.15 m thick, so the culvert keeps 1.85 m under it | — |

**Draw CPU in the shotengai** (r01 #3: looking north from (160, 1.5, 64), 668,111). Levels sooner
(`place/street.py` `LOD`): every shop's level 1 from 12 m (the two- and three-storey shops' and
the record and tobacco shops' were 20, the ramen shop's 16), the crane game's from 12, the arcade gates' from 22
(was 30), the kanban sets culled at 32 (45), gachapon and jizo at 26 (40); the utility poles have
a level 1 from 30 m (a square shaft and the crossarm, 14 triangles) and are culled at 56 with the
wires' sweeps (`gen_town_utility_pole_transformer.py`); the bicycle in the street's middle moved
to the east service lane. `mei_world.py check --cameras` at r01's cameras, every layer set, before
→ after: (160, 1.5, 64) north 668,111 → 571,215; (160, 1.5, 66) north 631,849 → 554,300; the
arcade roof (160, 10, 66) north 659,182 → 520,441; (160, 1.5, 94) south 600,942 → 566,328;
(168, 1.5, 88) south-west 614,505 → 581,649; (168, 7.8, 88) south-west 626,763 → 582,713. A sweep
of the shotengai (x 152-168 every 4 m, z 44-104 every 6 m, eye height, 8 yaws, every layer set:
4,040 views) has none over 600,000; its peak is 566,179, at (160, 1.5, 92) looking south.

Textures (`tools/textures.py`): the street zone 168,448 of its 196,608 bytes, the east 34,272 of
49,152 (the maple and the culvert's deck), the shrine region's terrain 112,224 of 155,648 (the
planks).

**Left for others** (their workstreams' files): the landing after a wall slide skips `land()`, so a
slide down a shop's front onto a street awning does not bounce (r08 #8: the cart); the danchi's
balconies above the first are a dead end, the body's head in the slab above (r08 #9: the station's
`make_danchi.py`); the alleys' rail cameras (r19 #3: the cart).

#### The level's frame (workstream 8)

The alpha review (reviews 08, 12 and 13) found about eight ways out of the level. One cause: the
frame was sized for a double jump and grab (5.15 m), but a backflip and a ledge grab reach
6.55 m, a running triple jump starts a glide 4.5 m up at a glide ratio of 4, and the rims were
measured from the ground at the rim, not from the floors beside them.

**The rule.** At every point of the edge the frame (a rock wall, a neighbour's back) stands at
least 6.6 m over any floor within 4 m of it, less 1 m for every 5 m farther:
`top >= F + 6.6 - max(0, d - 4) / 5` for every floor at height F, d metres from the point. 6.6 is
the backflip (4.8) and the ledge grab (1.75). The glide sinks 1 m in 4 at its steady speed, but a
running third jump's speed carries it farther: the explorer bot (`tools/explore`, on branch
`explore-bot`) took a body 99 m from the plateau (61.8) onto a wall top at 46.5, 1 m in 4.8, so
the rule uses 5. Every floor counts, however far: the mountain's plateau (62–70 m) reaches every
edge north of the front road by a glide, and glides of 270 m are designed (G8). Nothing between is
taken to stop a glide. A floor on the frame itself (a fence's top) counts as a floor to start from
when the rule lets a body reach it. **Nothing on the frame is a floor by the edge**: a reachable
top beside the void is a way out whatever its height, so the rock walls' tops are caps too steep to
stand on.

North of the town the rule asks 25–72 m, so the rims carry rock walls (`assets/edge_rock`,
`make_edge_rock.py`, `ROCKS`; placed by `place/art.py`): a step per 16 m of rim, 51 in 13 walls
(one per cell's edge: a placement costs the draw about as much as its triangles), the rim's depth
thick (2 m west and east, 4 m north). Each face rises from the rim's lowest corner to
the rule's height and 0.5 m, and at least 1 m over the rim's highest corner (a sliver of rim above
the face's top was a floor by the edge); its cap rises 1.5 times the depth to the back (56
degrees, a wall to the body: nothing stands or grabs there); its face goes on down in a flat
colour to y -200, so that a body falling through the mountain's steep terrain (review 13 #3) meets
it at the edge. The terrain's rock texture, a flat level from 60 m, culled from 120 m: past the
stand-ins' 128 m, so the far cells' stand-ins leave them out (in them, the walls cost the shrine's
views 30,000–66,000 cycles of draw CPU; far off, the rims are drawn as before). Raised as terrain (a `fill` on
the rims' cliffs) the rims were drawn as ramps tens of metres long by the far levels and the
stand-ins, whose grid points on the field's edge take the rim's top; a placement stays upright.

`tools/frame.py` checks a built world against the rule from the pack's floors and walls and the
terrain's top (`--tops`: the top each 8 m of edge needs, the reach and 0.5 m; `--rocks`: the rock
walls' table), and writes the frame scenarios' probes (`--probes`).

| Where | Was | Now | Why |
|---|---|---|---|
| East rim, z 154–384 | 8 m over the ground (8.4–9.9 by the cemetery) | rock walls to 45.5–72.5 m (`edge_rock_e*`) | terraces 5–9 (9.0–16.2) walked and glided off it; the plateau's glides arrive at 45–65 |
| North rim | 8 m over the ground; 9.0 at the canal's spring (x 42–54) | rock walls to 60–73 m (`edge_rock_n*`) | from the bamboo (14.6) the spring's rim was climbed; the path-out torii's beam (65.2) is 1.5 m from it; the plateau beside the canal's gorge (62) glides over it |
| West rim, z 128–384 | 10 m over the ground (10.6), 14 m in rows 4–5 | rock walls to 25.5–56.5 m (`edge_rock_w*`) | the sake brewery's roof (16.9) and the plateau's glides |
| East, z 104–156 | hoarding 5.5 m (z 104–118); rim 8 m (118–132); open where the viaduct left (132–154) | neighbours' backs `edge_neighbour_e3` (z 104–128, 41 m) and `e4` (128–156, 46.5 m), the hoarding in front | the deck (9.0) glided over the hoarding; terrace 1 walked out under the viaduct; the plateau's glides arrive at 40–45 |
| East neighbours e1, e2 (z 36–104) | 22, 27 m | 31, 36 m | the plateau's glides arrive at 30.5 and 35 |
| West, z 104–128 | hoarding 5.5 m; nothing behind it; rim 10 m from z 118 | `edge_neighbour_w3` (24 m) behind the hoarding; the rock walls from z 128 | the edge fence (3.0) is a step to the hoarding's top, and nothing stood behind it |
| West neighbour w1 (z 36–72), south s1 (x 32–64) | 18, 22 m | 22, 24 m | the sento's chimney (18.2) and the danchi's roof (20.8) |
| The viaduct's east end | two curves out of the level at z 132–154, closed on the deck by a grey wall 5.5 m tall at x 315 | the line ends at the underpass's north end (z 126.56), closed by `viaduct_end_wall` (concrete, 13.2 m wide over both parapets); the parapet rails stop 2 m short of it | the end wall's backflip and grab; the parapet rails ran through the wall (riding ignores collision); the deck's outer face crossed the neighbour's face, and a body sliding down it was pushed through the face (scenario 580) |
| Edge fences and hoardings | 0.4 m thick, against the neighbours' faces (x 0–0.4, 319.6–320, z 0–0.4) | the same, straddling the edge (centre 0.05 m inside it) | a body falling past a fence's top was pushed through the neighbour's face by the fence's outer face (scenario 583) |
| Underpass view (r14 #3) | an untextured rock cliff (`rock_far`) at x 318–320, z 118–128 | the neighbour's back (`e3`), its façade textured; `rock_far` is no longer drawn | the front road's view should end on concrete (7.1) |
| Edge fences' look (r16 #7) | flat olive bands (`gbt_edge_fence*`) | `edge_fence_12/34/40/44/64`: the hoarding's ribbed panels, 3 m, their backs open, one flat colour from 40 m | |
| The end wall's look (r17 #5) | `gbc_viaduct_end`, grey, unlit at night | `viaduct_end_wall`, the viaduct's concrete | |

Texture bytes added: none. The fences use the hoarding's panel tile, the end wall the viaduct's
concrete sheet, the new neighbours the neighbours' façade tiles, and the rock walls the terrain's
rock image, one tile with the terrain's (`tools/textures.py`: town 366,816 bytes, as before; shrine
124,896, from 126,560: the viaduct's curves in c4_2 are gone).

**Tests.** `carts/garden/tests/frame_cases.akr`, scenarios 580–584 (`make test-carts`), after
`tools/frame.py` on the built world: 580 the 29 ways out the review found, each by the move that
found it; 581–584 the south, north, west and east edges, every 8 m a walk (hopping and climbing
when stopped), a backflip and grab from the highest floor near the edge, and a glide from the
floor that gets highest there. A probe fails when the body gets 0.5 m past the edge. They run four
ticks of every five between frames, with the camera on the sky, about 200 probes a minute. The
explorer bot (`tools/explore/mei_explore.py`), run on this branch: 0 escapes from the frame (at
the base, 58 places, 42 confirmed in the cart; with ratio-4 walls whose tops were floors, 42).

**For the owner.** The rule makes the frame tall: north of the town the rock walls stand 25–73 m
(a ridge round the valley; 61 m over the canal's spring), the neighbours behind the front road's
east end 41–46.5 m. A lower frame there needs a lower plateau, a glide that ends sooner, or a frame
that is not a wall (a slope outside the level, which the terrain field does not reach today). The
viaduct no longer curves out of the level: it ends at a wall after the underpass.

#### The shrine zone

From the alpha review (reviewers 02, 04, 05, 07, 09, 10, 11, 13, 17 and 19) and the explorer bot
(`tools/explore`, branch explore-bot). Each fix has a case: 700–789 are shrine town's shrine-zone
routes and 790 the shrine world's (`carts/garden/tests/shrinezone_cases.akr` and `.sh`); 414, 417
and 422 are in `shrinetown_cases.akr`.

| What | Change | Case |
|---|---|---|
| B2: the walkway decks let the body fall into the trunk | `forest_platform_col` (`carts/garden/shrine/assets`, so the shrine world too): the inner hole round the trunk 1.2 → 0.6 m from the trunk's axis | 700, 701, 790 |
| B4: the rope bridge, stage to falls' top, ended in a lip | A flat 52.0 at its east end (x 216–222, z 345–349) | 702, 703 |
| The woods trail up the west ridge slid | `ramp_trail()` (`make_mountain.py`): each leg a ramp between its ends, 21° at most, a level landing (r 3.5) at each hairpin; the trail's last leg runs to (91.15, 255.5) | 704 |
| The east shoulder trail slid at its switchbacks | The same `ramp_trail()`; at the hairpin at (260, 303) a point 1.5 m up each leg at the hairpin's height, so the swept trail's mitre meets level sections (it met the sections up the legs in a 31° crease); the legs beyond it are 22° | 705 |
| A grind down a lantern string pinned the body at the hall; a grind up overshot the torii | One path a side (`core_string_torii_{w,e}`): 2 m along the torii's top beam from its middle, the torii, the hall, the gate (its end at 12.4, 0.5 m over the gate's lower eave, which stopped a body grinding up to it at 12.0); the rail entity at the hall | 706, 707 |
| The north wall's top could be grabbed | The raised north run's collision is `shrine_wall_coping_{8,4,corner}_col`: 2.45 m sides and a 2.95 m ridge, no flat top | 708 |
| The gate's and temple's roofs could not be climbed (G5's take-off was reached only by gliding) | The gate's roofs: a double jump from its skirt reaches the lower roof as built. The temple: `arch_temple_town_col` (`assets/arch_temple/make_arch_temple_col.py`), the shrine's collision with walls under the three front eaves and the ridge walk widened to 2.5 m | 709, 710, 414 |
| Case 414 started on the temple's ridge | It climbs there from the terrace (`SHZ_TEMPLE_ROOFS`), then glides G5 | 414 |
| Star 1 was taken in mid-air by G6's glide (lead: star and finial to about 48 m) | Star 1 at 51.5, the finial pole to 51.0 (the feet at its top 49.8), `shrine_finial_top` drawing the spire 6.0 m on. At 48.3, the first try, the explorer bot still glided to it from the 65.4 m slope at (150, 350), 92 m off; at 51.5 it finds only the pole | 722, 422 |
| Star 4: a body dropped onto the cedar rope ground along it into the knot hole (lead: hang only) | The rail type's `hang` (the game schema, `attach.akr`): a hang rail is never ground and is not caught falling faster than 3 m/s. Its `catch` 3.0: it is caught only in its first 3 m, at the rope deck | 724, 423 |
| Shortcut D bypassed: a wall kick up the trunk, the hands on the rope's end in the knot hole (the explorer bot) | The rope's `catch` (above). The bot still reports it, as its confirmer puts the body on the rope directly and knows neither `hang` nor `catch`; flown whole in the cart, no kick gets in | 725, 726 |
| Shortcut B bypassed: a side flip from the terrace onto the barred north gate's 26° roof (the explorer bot) | The barred gate's collision is `arch_wall_gate_shut_town_col` (`assets/arch_wall_gate/make_arch_wall_gate_town_col.py`): the roof a 64° gable to 6.6 (1.9 m over the drawn ridge), the wings a 56° coping. Open: the bot then went over the wall from the temple's back podium (8.6, 3.3 m south of the wall's 8.95 coping): a wall kick up to it and a long jump north (8.3 s) | 727 |
| G8 (lead: a flat pad, routed east of the torii) | A 5 × 5 m pad at 61.8 (x 171.5–176.5, z 353.5–358.5), kept clear of scatter; a standing jump from it glides east of the great torii (x ≥ 167) to the front road at (163, 97.5), the feet 2.1 m clear of the wires at z 106 | 417, 730–733, 452 |
| The stilt ladder's top was hard to leave | Its pole 1.15 m in front of the deck, a front pole held on its north side: at its top (feet 61.1) a pole jump goes onto the deck | 711 |
| Lips at the torii tunnel's foot and ladder A's first riser | The ground at each foot set just under the first tread (14.75, 12.85) | 712, 713 |
| The landing stair's last riser at the stage's west gap | It ends in a level landing 0.1 m under the deck, slipping 0.6 m under it | 714 |
| The steps into the cave ended in a 0.65 m lip | `steps_pool_cave` reaches the cave's floor at its front (13.95 at z 328.6) | 715 |
| The cave's west passage ended under the terrace | `forest_falls_cave`'s west buttress trimmed (x from −7.7); the ground cut to 14 west of the cave, with steps (`steps_cave_terrace`) up to the terrace | 716 |
| Shortcut C's fallen cedar: a hole where the log meets the root plate, and the log not walkable from the stump | `forest_dead_cedar_fallen_col`: the stump to the log's top (1.26) and a join block; a ramp up to the stump; the cedar placed at 34.7 | 717, 718 |
| The zig-zag bridge's hump, and its 32° corner (the explorer bot) | The corner at (218, 168) moved to x 219.5; no leg steeper than 22° (each point within 0.4 m a metre of its neighbours), and each corner level with the points 2 m either side (sloping, the planks met the corner's mitre in a 34° crease) | 719, 728 |
| The stream's mouth: its east bank too steep to leave | The bank lowered 0.4 m and smoothed (x 232–253, z 182–216) | 720 |
| No path to the way-out torii | `trail_way_out` from the falls' top (238, 349) to the torii (252, 376.5), ramped | 721 |
| The crown pole could not be seen | `shrine_crown_ladder` drawn on it | 723 |
| The north gate's sawtooth: a gully behind the moved wall | A strip at 5.0 behind it (x 114–214, z 238–243) | 708 |
| The kick chimney was grey box | `shrine_kick_chimney` (and `_col`): its rock faces textured, so it takes the night's colours | — |
| The koi could not be seen | At −0.15 (was −0.5), brighter | — |
| Draw CPU over 600k (r02 #1) | r02's measured levels: `arch_temple` and `arch_pagoda` level 1 from 26 m, `tree_cedar_sacred_hollow` from 30, `bell_pavilion` from 20, `cemetery_grave_row` from 12 and culled at 30; every sweep wholly in the zone culled at 40 (`SWEEP_CULL`); the sotoba racks unmerged, so their cull holds; `tree_cedar_giant` level 1 from 16 (was 22) | below |

Draw CPU at r02's positions afterwards, the worst of 24 yaws × 3 pitches (−30, −10, 5; the World
Checker at fixed cameras, the backdrop drawn), against r02's worst before (72 yaws × 7 pitches):

| Position | r02 before | Now | Views over 600k |
|---|---|---|---|
| deck 5 (102, 22.6, 252) | 636k | 599k (yaw 180, pitch −30) | 0 of 72 |
| pagoda terrace (184, 19, 264) | 667k | 599k (yaw 255, −10) | 0 |
| rope deck (130, 25.6, 282) | 663k | 581k | 0 |
| cemetery terrace 2 (312, 7.6, 152) | 659k | 576k | 0 |
| cemetery terrace 1 (286, 3.3, 135) | 641k | 564k | 0 |
| pagoda climb (178, 34, 262) | 640k | 558k | 0 |
| basin east (184, 15.8, 296) | 655k | 545k | 0 |
| pagoda terrace (184, 18.5, 248) | 649k | 544k | 0 |
| the courtyard (165, 7, 200) | 521k | 444k | 0 |
| the viaduct deck (312, 10.5, 136) | 713k | 657k (yaw 300, −10) | 2 |

The viaduct deck (the station's, over the cemetery) is still over. Those numbers are before the
merge with the other workstreams. After it, the World Checker's vantage points (each with 11 layer
sets) put six shrine-zone cameras over 600k: the viaduct deck 674k, the pagoda climb 623k, the
rope deck 620k, cemetery terrace 1 610k, deck 5 606k and cemetery terrace 2 601k. At the pagoda
climb the merge added one stand-in (the look's stand-in caps): 2,052 → 2,214 triangles, 572k →
602k in the default layers.

Not done here: the race train (the cart); a rail camera zone per torii tunnel switchback; the kick
cedars drawn at their trunks' size. (The level-1 roofs are the look's; the fall-through spots the
kit's `slide_floor_degrees`, above.)

### 12.10 Features

#### Alpha follow-ups (branch `alpha-followups`)

What the alpha fix round left (the leads' handoffs and the explorer bot's run at 509ba61). Each fix
has a case, 680-688 (`../tests/fu_cases.akr` and `.sh`, `make test-carts`).

| What | Change | Case |
|---|---|---|
| Shortcut B's bypass: from the temple's back podium (8.6, 3.3 m south of the north wall's 8.95 coping) a hop and a dive, or a wall kick and a long jump, cleared the wall | The podium's back strip is a slope, `back_strip` in `arch_temple_town_col` (`assets/arch_temple/make_arch_temple_col.py`): from the hall's back wall just under the back pent roof (12.6) down to the podium's back edge (8.6), 49 degrees, across the podium's whole width (x 134-186, z 230.25-233.75). A wall to the body: nothing stands on it, and a body landing there slides off onto the terrace (5.0). Its ends face south over the side strips; jumps from the side strips' back ends, north and 45 degrees out, come down south of the wall | 680 |
| A grind up a steep rail never slowed: on any slope it went on up at the grind's minimum speed (6 m/s) | Uphill, gravity slows a grind under the minimum too, and through zero it slides back down at the minimum (`attach.akr`, `st_rail()`); a grind stopped on a slope goes back down it. The overpass's handrail (26 degrees): put on it 2 m along it grinding up at the minimum, it turns back 0.4 m higher and is off its foot in 1.0 s (the stick held up it: 0.7 m and 1.3 s). A rail gentler than GrindAccel over Gravity (9.6 degrees) is still climbed with the stick | 681 |
| Hangs held the feet in the floor: the overpass's handrails and the arched bridge's kasagi come down to less than the hang's 1.75 m over the ground; a hang at their ends (the bot: a glide down onto the handrail) and a drop from it fell through the world | A hang only where the hanging feet are no more than 0.1 m under the floor under the rail (`attach.akr`, `hang_clear()`: no grab there, and a hang is not moved along into there). The bot's hang drops at (246.3, 96.05), (277.7, 123.05), (53, 159.2) and (43, 159.2) | 682 |
| `coin_alley3` at (107, 0.7, 74) was inside the kura (the grey box's alley house, on the ground once the yard went to the tower) | On the kura's ridge, (107.8, 8.7, 74) (`place/street.py`), the kick pair's landing: kicks between the kura and the fire tower from the alley take it in 1.5 s | 683 |
| `trail_canal_west` ran through the sake brewery's pad into its wall at z 218.7 | `core_park_path` (`gen_core.py`) round its east side: (26, 198), (29.5, 208), (29.5, 228), (24, 250), 2.5 m clear of the pad | 684 |
| `stairs_ridge_basin`'s head lay 0.6-0.9 m under the ridge's crest in its own bed, under a 40-degree bank: walked down, not up (the bot: "unknown" at its start) | Its head a landing at the crest's height (22.0, x 147.5, z 263-264.4, on the crest's flat west of x 149), the ground under it set to 21.9: the bed's 2 m samples left a 33-degree dip in front of it (`make_mountain.py`) | 685 |
| The fox shrine's plinth (13.05) lay 1-2 m under the grove's bank: the kit set it on the low side of its slope at (84, 307). A body on it walked into the hill and fell through the world (the bot's confirmed glide let-goes from (84, 13.05, 305)) | On the grove's floor at (85.5, 300.5), its plinth at 15.45, the ground under it set to 15.0 (`place/shrine.py`) | 686 |
| The bot's drop through at (225, 327) started inside the falls' east face (a wall from 19.2 to 23.3 over the feet there: 3 m over the floors round it is inside the hill) | The bot's fault (below). The face itself holds: dropped down it from 42 m every 1.5 m, a body comes down on a floor | 687 |
| The north stair's west edge: the ground's 2 m samples across its diagonal line left the bank beside the treads 0.2-0.6 m over them, outside its 8 m bed; a gentle face, so no wall. A body stepping off the edge fast went into the bank and fell through the world (the bot: a glide off the temple's ridge let go over the stair) | The stair's bed 10 m wide (`gen_core.py`): the bank beside the treads is under them | 688 |

**The explorer bot** (`tools/explore/`; tests in `tests/test_explore.py`):

- Rails: the rail entity's `hang` (never ground, not caught falling faster than 3 m/s) and `catch`
  (caught only within it of the first point), and `hang_clear()`, in the flights and in the rail
  nodes (no grind nodes on a hang rail; a hang moves along only where it hangs clear). Shortcut D
  is no longer reported bypassed: the kick up the trunk does not catch the rope's far end. Uphill
  grinds only where the stick beats gravity.
- Walking up stairs: the wall test at the step's top, not the feet's old height (the riser beyond,
  within the body's radius when the treads are shallower than it, only slows the controller):
  `steps_pool_shelf`, `steps_pool_cave` and `steps_cave_terrace` walk end to end.
- A floor with the ground over it inside the body's height (the falls cliff's top, 48.3, under the
  hill at z 345) is not walked to, stood on or landed on: the controller steps up onto the ground.
  The walk graph went under the hill there, and the confirmer, put on the buried floor, fell.
- A body pushed out of a wall is not pushed under the ground: the false glide let-goes through the
  world over the precinct and the mountain (a column keeping a thin face's back normal pushed a
  glide 0.6 m up into the bank, and it flew on under the hill).
- The drop check starts over a column's own faces where they stand higher than 3 m over the floors
  round it.
- The confirmer stands a take-off on a crack (a terrain vertex at even metres) as the controller's
  crack bridge does, or a few centimetres off a seam (it was put at -1000 and reported falling).

**The bot on this branch:** 0 escapes; 0 of 226 drops through; flights through the world 20 spots,
0 of the first 20 confirmed; every collectible reached; shortcuts A-E the long way; of 39 paths only
`core_north_stair` stops (at the shut north gate, as meant, and at the pagoda's wall at its top).
Star 4's chamber: a third jump's glide from the ridge west of the cedar (122, 22.6, 274) into the
knot hole, a route the cart repeats; not looked into here (the shrine's).

**Two stale notes:** `art/preview_scratch.py --cycle` finds each region's water palettes and
enters the region as the garden does (`water_cycle_find()`, then `water_cycle_enter(k)`), and
`gen_core.py`'s viaduct note no longer gives the old 5.15 m reach.

**Costs.** No textures. The World Checker, full (855 views): peaks 2,785 triangles, 704,850 draw
CPU, 907,048 GPU cycles (509ba61: 2,781, 705,219, 905,293), 129 over thresholds as before; the
pack 12,445,372 → 12,441,124 bytes. At cameras on the changes (`mei_world.py check --cameras`,
draw CPU / GPU, 509ba61 → now): the ridge stair's head looking north 332,479 / 469,109 → 341,304
/ 491,689 (its landing: the stair's sweep 176 → 192 faces); the fox grove looking at the shrine
320,830 / 480,924 → 321,286 / 494,803; the grove from the bank 599,532 → 576,618; the park path at
the brewery 444,657 → 430,669 and from the bamboo 426,802 → 402,055; the temple's back, the north
stair's west edge and the kura's ridge within 3,300 of before.
