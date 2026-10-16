# The aquarium: the route

A stage of After Hours (DESIGN.md, "The premise"): one property, a bay-front aquarium of 1990,
assessed after hours. The aquarium lies about its size. The public galleries the plans declare
are a fraction of it: behind and above them are the quarantine tanks, the life-support plant in
the basement, the keepers' kitchen, the open tops of the big tanks and the catwalks over the
galleries. The assessor goes in by the main doors, down the public route, through the staff door
behind the ocean window, round the back of house from the basement to the tank tops, and back out
over the galleries he walked at the start, on the keepers' catwalk and the restaurant's
mezzanine, looking down on where he was.

The stage's ideas (the owner's, 2026-10-15): **depth** (rooms through the building's height, two of
them re-entered on a level above the one first crossed), **dark galleries lit only by the tanks**
and **narrow walkways above the water**. No tools. The dash (NOTES_G.md) works and is never
needed: every leg clears walking and running. It sits after the tower and before the department
store: a step up from the tower, without the store's keycards.

Lead: agent J (NOTES_J.md). The runtime for darkness, water and two-level rooms is agent A's
(NOTES_A.md, "The aquarium stage"); the rules as agreed are below.

## The rooms

Eight rooms, ten legs. The rooms join by doors (the store's way), with no keycards; two rooms are
entered twice, each time on another level.

| Cell | Room | Folder | Floor | Size (m) | Lit | Builder |
|---|---|---|---|---|---|---|
| 0 | **The entrance hall**: ticket gates, the welcome tank (a cylinder through both floors), the restaurant's mezzanine along the back | `rooms/aq_hall/` | 1F, y 0; mezzanine +3.2 | 16 × 9 | dark | R1 |
| 1 | **The great tank**: the public gallery in front of the big acrylic window; the keepers' catwalk over it | `rooms/aq_great/` | 1F, y 0; catwalk +3.2 | 20 × 9 | dark | R2 |
| 2 | **The jellyfish gallery**: jellyfish columns whose lamps change on a cycle | `rooms/aq_jelly/` | 1F, y 0 | 14 × 8 | dark | R1 |
| 3 | **The ocean gallery**: the sketched room (the ocean window, the jellyfish column, the coral cube) | `rooms/aquarium/` | 1F, y 0 | 12.1 × 8 | lit | its sketch's builder |
| 4 | **Quarantine**: rows of holding tanks, UV lamps on timers | `rooms/aq_quar/` | 1F, y 0 | 13 × 8 | dark | R3 |
| 5 | **The life-support plant**: sand filters, pumps, open sumps crossed by grated walkways | `rooms/aq_plant/` | B1, y −4 | 18 × 9 | lit | R3 |
| 6 | **The fish kitchen**: prep tables, buckets of feed, the walk-in freezer | `rooms/aq_kitchen/` | 2F, y 4 | 13 × 8.5 | lit | R3 |
| 7 | **The tank tops**: the open water of the big tanks, walkways across it | `rooms/aq_tops/` | 2F, y 4 | 18 × 9 | dark | R2 |

Sizes are the greyboxes' (each room's `PLAN.md` has the exact plan). The cells' x order is the
section, as the store's. Every room is dressed (each room's `NOTES.md`); captures of each leg in
the cart are in `shots/` (`shots.py`, from A's scenario 85).

## The run (ten legs)

| Leg | Room, in → out | Teaches | Watchers | The way through (`solutions.py`) | Model ticks |
|---|---|---|---|---|---|
| 0 | Entrance hall, floor: the main doors → the great tank | **The dark**: a watcher without a torch sees you only in light | the desk guard (posted, no torch) | across the welcome tank's light while he looks at the east door; through the door's blue while he looks back | 504 |
| 1 | Great tank, floor: the hall → the jellyfish | **Torches**: a lamp sees its whole cone | the night guard with a torch round the gallery; a camera on the window's band | behind the torch along the front; at the column while he walks the far end; out when he turns up it | 935 |
| 2 | Jellyfish gallery: the great tank → the ocean gallery | **Lights on a cycle** | a posted guard down the gallery, a keeper (no torch) on the back aisle | down the front aisle in the dark behind the wave, a bay at a time; up the never-lit far end | 814 |
| 3 | Ocean gallery: the way in → the staff door | Glass (the tower's idea, again) | the watchman, the keeper round the cube (the sketch's puzzle, unchanged) | the pillar's shadow, as in the tower | 768 |
| 4 | Quarantine: the staff door → the stair down | The dark, a torch and timers together | a keeper with a torch on his rounds; a camera over the stair door | the middle aisle while its UV is off; behind the keeper down the east end; out while the camera looks away from its lamp | 854 |
| 5 | Life-support plant: the stair → the service stair | **Water**: sight crosses it, he does not; machinery is cover | the plant engineer round the west half; a camera at the front walkway's end | behind the engineer; in a pump's shadow at the top of the middle walkway; down and along the front while the camera looks over the sumps | 974 |
| 6 | Fish kitchen: the service stair → the tank tops | The breather: a lit room, buckets are noise | the cook round the prep tables | behind his back round the tables, clear of the buckets | 703 |
| 7 | Tank tops: the kitchen → the catwalk down | Walkways over water in the dark | a keeper with a torch round the shark tank; a camera on the lamps | up the middle through its lamp while the camera looks at the back; through the back lamp when it looks at the middle and the keeper has gone down the west side | 1,239 |
| 8 | Great tank, **catwalk** (level 1): the tank tops → the mezzanine | **Two levels**: over the gallery of leg 1 | a keeper with a torch on the back walk; a camera on the rim's two lamps | the middle lamp while the camera looks at the west one; wait out the keeper's turn; the west lamp while the camera looks at the middle | 879 |
| 9 | Entrance hall, **mezzanine** (level 1): the catwalk → out | Everything: dark, a torch, hiding | the mezzanine's guard with a torch; a camera on the tank's lit top | behind the torch across the tank's top while the camera looks away; the west booth while he turns at the end; out behind him | 1,013 |

The stage is **8,693 ticks (2 min 25 s)** on the model played perfectly, between the tower's 77 s
and the store's 170 s; nothing needs the dash or running. Tight places on the model (the nearest
a cone comes to his centre on the way through): 0.11-0.24 m in legs 2, 3, 5, 7, 8 and 9;
checked in the cart by A's scenarios 85 (the ten legs as one run: 8,693 ticks, the same as the
model's, leg for leg within 3) and 86 (through the transitions), and E's 67 (from the select).

```
 in ▶ [0 hall, floor] ─▶ [1 great tank, floor] ─▶ [2 jellyfish] ─▶ [3 ocean gallery] ─▶ [4 quarantine]
                                                                                            │ down
 out ◀ [0 hall, mezzanine] ◀─ [1 great tank, catwalk] ◀─ [7 tank tops] ◀─ [6 kitchen] ◀─ [5 plant, B1]
```

## The rules (agreed with A; NOTES_J.md, "Runtime, agreed with A")

- **Dark rooms** (`room.dark`): a watcher without a torch sees the thief only where his centre is
  inside the fan *and* inside a light (`light`: a box in plan on a level, steady or on a cycle).
  The fan clipped to the lights is drawn as danger, the rest as a faint outline: drawn = tested.
  A guard with a torch (`guard.torch`) sees his whole fan, lit or not; his torch lights nobody
  for anyone else. Touch, hearing and the trains are unchanged in the dark.
- **Water** is a `wall` with `blocks: false`: it stops the thief and the guards, and cones cross
  it. The open air beside a catwalk is the same. Nobody falls in.
- **Two levels** (`room.upper`, the upper level's height; `level` 0 or 1 on walls, watchers,
  waypoints, spawns, doors, lights, hiding places and fragile things): the thief is on the level
  of the door he came in by. Each level has its own walls; a watcher sees only his own level;
  noise is heard on both. The levels join only through other rooms' doors: no stairs inside a
  room.

## How it sits in the World Kit

One world, `aquarium` (`levels/aquarium/aquarium.world.json`, written by `make_aquarium.py` here
through `levels/assemble.py`, B's): each room in its own 32 m cell side by side along x in the
section's order, at its floor's height; one region per room; kit-made stand-ins; texture slot 7
and 4-bit palettes 250-251 left to the front end. The two-level rooms are one cell each, both
levels in it. The rooms' greyboxes are written by `levels/aquarium/aqroom.py` (s2room's rooms
of doors, with lights, water and a second level).

**Texture slots** (the owner's choice: two rooms a door joins are both drawn textured in the
transition, so they may not share slots): the doors make a cycle of seven rooms, so three sets:
A `13-9,16-19` (the entrance hall, the jellyfish gallery, quarantine, the kitchen), B
`8,6-3,20-24` (the great tank, the ocean gallery, the plant), C `2-0,25-31` (the tank tops).

## Commands

```sh
python3 carts/afterhours/rooms/aq_hall/make_aq_hall.py      # each room's play file and greybox (and the other rooms/aq_*)
python3 carts/afterhours/levels/aquarium/ocean/make_ocean_play.py   # the ocean gallery's play file
python3 carts/afterhours/levels/aquarium/make_aquarium.py   # the stage's world
python3 carts/afterhours/levels/aquarium/solutions.py       # the ten legs on the model; the tapes
python3 carts/afterhours/levels/aquarium/solutions.py --check --pictures /tmp/aquarium
python3 carts/afterhours/levels/aquarium/sketch.py          # the layout sheet, sketch.png
make B=build-mine build-mine/carts/afterhours.mei           # the worlds (World Checker) and the cart
```

## Rules for every room (for the room builders)

As `levels/store/ROUTE.md`, "Rules for every room" (the 1 m cut, doorways open and framed with a
way on beyond, 2,500 triangles, recipes verified in depth mode with collision companions,
placements in the room's own `NAME.placements.json`), and for this stage:

- **Light is the puzzle.** In a dark room, the floor's lit areas are the play file's `light`
  boxes: paint the tanks' glow onto the floor where they are and keep the rest of the floor dark,
  so what looks lit is lit. A builder may round a box's corners in the paint, not move it.
- **The upper level** stands at +3.2 m: the back and end walls of a two-level room go up to
  5.6 m; the mezzanine and catwalks are grated or slatted where they pass over the floor, and
  railed at 1 m. At 60° anything 3.2 m up hides the floor 1.85-2.75 m behind it: keep the floor's
  routes out of that band (the plans do).
- **Signature props once per stage**: a thing that is the stage's (the welcome tank, the great
  window, the jellyfish columns, the ocean window, the sand filters, the turtle) appears in one
  room only.
- **Fonts** from `tools/fonts/` only.
