# Agent J's notes: the aquarium stage

J leads the aquarium stage: its route (`levels/aquarium/ROUTE.md`), its world
(`levels/aquarium/`), each new room's floor plan (`rooms/aq_*/PLAN.md`), the greyboxes, the
puzzles and the solution tapes, and the review of every dressed room. Three room builders (R1-R3,
Opus) dress the rooms. Kept current; newest first in each section.

## State (2026-10-15, evening)

- **The stage clears end to end in the cart with every room dressed.** A's scenario 85 (the ten
  legs as one run) and 86 (through the front end's transitions) pass in `build-ah-J`: 8,693
  ticks (2 min 25 s), every leg out by its door, never caught; the cart's ticks match the model's
  leg for leg (within 3). `tests/check.sh` passes in `build-ah-J`: all 47 After Hours scenarios
  (83, 85, 86 the aquarium's), then all 10 of E's (67: the aquarium from the select, nine
  transitions, the end, the save).
- **The world**: `levels/aquarium/aquarium.world.json`, 8 cells, 2,273,572 bytes, 0 warnings;
  World Checker 0 hard failures, 0 over thresholds in 110 views (peaks 1,502 triangles, CPU
  437,620, GPU 591,101 cycles). Stand-ins: each dressed room is a shell and its props, so the
  700 cap keeps every room's shell.
- **Rooms dressed** (each room's `NOTES.md`; captures in each room's `shots/`, and in the cart in
  `levels/aquarium/shots/`, made by `shots.py`):

  | Room | Builder | Triangles | Texture VRAM |
  |---|---|---|---|
  | The entrance hall | R1 | 1,380 | 147,584 |
  | The great tank | R2 | 1,117 | 185,984 |
  | The jellyfish gallery | R1 | 1,108 | 121,536 |
  | The ocean gallery | the sketch's builder (its stage change relayed) | 1,657 | 61,009 |
  | Quarantine | R3 | 1,460 | 181,799 |
  | The life-support plant | R3 | 2,123 | 177,643 |
  | The fish kitchen | R3 | 1,046 | 199,119 |
  | The tank tops | R2 | 452 | 119,616 |

- **Budget** (A's measures, release, play only: ticks after a room's clock 2): the worst frame
  in play is 491,703 CPU (the entrance hall), 532,857 GPU (the great tank); the others 195-469k
  CPU; the rules' tick is under 50k everywhere. Scenario 85's 888k (debug) / 782k (release) is the
  frame that loads the great tank; loads are spread by E's `stage_prepare` and H's transition.
  Standing in each room, the worst is 530k CPU, 506k GPU (debug).
- **Answers given to the builders**: the welcome tank's glass rises through both floors; the
  jellyfish columns are 2.3 m glass; the plant's sand filters stand whole (against the back
  wall); quarantine has no sharks; the kitchen's buckets are A's (drawn as buckets of fish in the
  aquarium since 2026-10-15).
- **Follow-ups, not done**: quarantine's UV tubes switching with their lights (A: a light's
  `off_variant` palette, B's field, R3's variant; declined for now, budget first); the column
  lamps pulsing with their bays (the same mechanism); `AGENTS.md`'s Generators table should list
  the rooms' dress scripts (below).

## Files (mine)

| File | What |
|---|---|
| `levels/aquarium/ROUTE.md` | The route, the legs, the rules, the World Kit layout, the builders' rules |
| `levels/aquarium/aqroom.py` | A room of the aquarium in greybox from a description: s2room's rooms of doors with lights, water and a second level (`upper`, `walks`, `upper_props`) |
| `levels/aquarium/make_aquarium.py` | The stage's world (through B's `assemble.py`), with the three texture slot sets |
| `levels/aquarium/solutions.py` | The ten legs on the model; writes the tapes |
| `levels/aquarium/sketch.py`, `sketch.png` | The layout sheet |
| `levels/aquarium/ocean/make_ocean_play.py` | The ocean gallery's play file for this stage (the tower's, as doors) |
| `rooms/aq_*/make_aq_*.py`, `PLAN.md` | Each new room's description (greybox, play file) and floor plan |
| `levels/rules_model.py` (B's) | Extended: dark rooms, lights, levels (below) |

## Runtime, agreed with A (2026-10-15)

A proposed, J answered; A builds it (NOTES_A.md, "The aquarium stage", is the runtime's side and
the truth for names and numbers). Schema fields go into `afterhours.game.mochi` with B.

1. **Dark rooms** (`room.dark: bool`). `light` entities: boxes in plan (`size` x/z, yaw), on a
   `level`, steady or on a cycle (`period`, `on`, `offset` on the room's clock). A watcher without
   a torch sees the thief only when his centre is inside the fan **and** inside a lit light on his
   level; that clipped fan is drawn as danger, the rest of the fan a faint dotted outline (drawn =
   tested). `guard.torch: bool`: the whole fan sees, as today. A torch lights only for its holder.
   The thief standing in no light is drawn dimmed when a dark-eyed watcher is on his level. A
   draws each light's patch as a faint tint too. Touch, hearing and trains unchanged.
2. **Water**: no type of its own. Water and the open air beside a catwalk are `wall` with
   `blocks: false` (solid, cones cross). No deep water (no falling in) in v1.
3. **Two levels**: `room.upper` (metres, 3.2 in this stage). `level` (0 floor, 1 upper; default 0)
   on wall, guard, waypoint, spawn, door, light, hide_spot, fragile (and keycard, exit). The thief
   is on the level of the door (spawn) he came in by; he collides with his level's walls; doors,
   spots, fragile things are his only on his level. A watcher sees only his own level (fans cast
   against his level's walls, catching only a thief on it); the other level's cones are drawn at
   their height. Noise is heard across levels (a guard walks to the point on his own level). No
   stairs inside a room; cross-level sight left out of v1. The camera frames both levels.
4. Tapes and ghosts per room and entry door, as in the store.

**J's model of it** (`levels/rules_model.py`, B's file, extended additively; every room without
`dark`, `upper` or `level` plays as before: the station's, the tower's, the store's and the
platform's plans give the same ticks): the thief's level is his spawn's; walls, doors, cards,
hiding places and fragile things are his only on his level; each watcher's fan is cast against
his own level's walls and tests only a thief on it; in a dark room a watcher without a torch
sees him only inside a light that is on (`(clock - offset) mod period < on`, at the tick's
clock, A's order); noise is heard on every level. `planner.py`'s margins and pictures know the
lights and the levels too.

## Requests

- **A**: (a) the aquarium stage in `dr_levels.akr` between the tower and the store (stage order
  below); (b) a scenario in `tests/check.sh` playing the stage's ten legs
  (`tests/tapes/aquarium_solution.akr`, `SOLUTION_AQUARIUM_LEG_0 .. 9`, `AQUARIUM_LEGS`,
  `AQUARIUM_LEG_ROOM`, `AQUARIUM_LEG_DOOR`, the store's format), as 63 does for the store, and one
  through the front end's transitions, as 64.
- **B**: (a) the stage order: station, tower, aquarium, department store, then Gate 1's platform;
  (b) J extends `levels/rules_model.py` for the rules above, additively (nothing changes for a
  room without `dark`, `upper` or `level`); (c) the sketched aquarium room moves from the tower to
  this stage (DESIGN.md, Decided: "the tower gets a top of its own"); its play file for this stage
  is J's (`levels/aquarium/ocean/`), and `levels/level1/aquarium/` stays as it is for the tower
  until the tower's roof replaces it.
- **E**: a stage-select row for the aquarium after the tower (proposed name "THE AQUARIUM"); the
  rooms' captions come from the world's `room.name`.
- **F**: ambiences for the new rooms (proposals; `au_room()` numbers are A's):
  the entrance hall (`AMB_AQUARIUM` would do: the pumps' hum, bubbles), the great tank (a deeper
  hum, the big tank's slow surge), the jellyfish gallery (almost nothing: a soft filter trickle,
  a low tone), the ocean gallery (`AMB_AQUARIUM`), quarantine (many small airstones bubbling, a
  UV ballast's buzz), the life-support plant (loud: pumps, the sand filters' rush, water
  falling into the sumps), the fish kitchen (fridges' compressors, a dripping tap), the tank tops
  (open water lapping, the echo of a high roof, a skimmer's gurgle). The catwalk and the
  mezzanine use their room's.
- **H**: doors on the upper level: a door's height is the room's floor plus `upper` when its
  `level` is 1 (the great tank's catwalk to the hall's mezzanine is level to level, the tank
  tops' door down to the catwalk 0.8 m down). The stage's doors form a cycle of seven rooms
  (great tank, jellyfish, ocean, quarantine, plant, kitchen, tank tops, back to the great tank),
  so H's option 1 (disjoint texture slots for rooms a door joins) needs three slot sets here.

## Stage order

Proposed with the coordinator: station, tower, **aquarium**, department store, Gate 1's platform.
