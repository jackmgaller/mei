# Stage 2: the route

After Hours' second stage: keycards and backtracking. Five rooms of a department store at night,
from the cinema on its eighth floor down to the food hall in its basement, joined by doors as a
graph, not a line. Two staff doors are locked: a blue one in the staff corridor (up to the
projection booth) and a red one on the shop floor (the service lift down to the food hall). Each
card lies beyond a door the thief has already passed, so he goes back for it. The run is eight
legs through five rooms; the staff corridor is crossed three times, each time between another
pair of doors, from its clock 0. No tools. Every room is dressed (each room's NOTES.md), plays,
and its legs' solution tapes clear in the cart (A's scenario 63). The floor plans for the room builders are
each room's `PLAN.md`.

## The rooms and the graph

| Room (`next` order) | Folder | Floor | Size (m) | Doors | Watchers |
|---|---|---|---|---|---|
| 0 The cinema | `rooms/cinema/` | 8F, y 36 | 22.5 × 9.5 | behind the screen (the stage's start, from the aquarium's corridor); the staff door to the corridor | usher (patrol), cleaner (patrol), the projector's window (a cone that never moves) |
| 1 The projection booth | `rooms/booth/` | 9F, y 40 | 12.5 × 6.5 | its stair down to the corridor | projectionist (patrol round his west machine) |
| 2 The staff corridor | `rooms/corridor/` | 8F, y 36 | 25.5 × 7.5 | from the cinema; **blue** door up to the booth; the staff stair down to the shop floor | porter (patrol round the roll cages), office guard (posted, behind glass), stair camera |
| 3 The shop floor | `rooms/shopfloor/` | 7F, y 31 | 24.5 × 10 | the staff stair; **red** door, the service lift down to the food hall | night guard (a long round), lift camera |
| 4 The food hall | `rooms/foodhall/` | B1, y −4 | 24.5 × 10 | the service lift; the shutter door out to the underground mall (the stage's end) | cleaner (patrol round all the cases), melon counter guard (posted), middle camera |

```
           [1 booth] ──(blue)──┐
                               │
 start ▶ [0 cinema] ──────── [2 corridor] ──────── [3 shop floor] ──(red, lift)── [4 food hall] ▶ end
```

## The run (8 legs)

| Leg | Room, in by → out by | What happens | Model ticks |
|---|---|---|---|
| 0 | cinema: the screen → corridor door | behind the usher, past the cleaner's aisle | 1,280 |
| 1 | corridor: cinema door → stair | passes the blue door (shut); the column's shadow; the stair camera | 1,237 |
| 2 | shop floor: stair → stair | passes the red door (shut); takes the **blue card** at the watch counter, back out | 1,752 |
| 3 | corridor: stair → blue door | the column's shadow the other way; the blue door opens | 924 |
| 4 | booth: its door → its door | takes the **red card** at the bench's end, back out | 1,380 |
| 5 | corridor: blue door → stair | the third crossing | 1,235 |
| 6 | shop floor: stair → red door | behind the night guard; the red door opens onto the lift | 1,401 |
| 7 | food hall: lift → the way out | round the gift boxes, a dash past the melon counter | 1,002 |

The whole stage is 10,219 ticks (2 min 50 s) played perfectly, against level 1's 4,786: longer
and harder, as the owner asked (level 1 was right for stage one). The corridor is the stage's
clockwork to learn: its office guard turns his head on a 480-tick cycle, the column in the back
lane has a shadow he never sees into, and each crossing uses it differently.

**Why a hub.** The cards are where they are so the player sees both locked doors before he can
open either: the blue one on the first crossing of the corridor, the red one on the first visit
to the shop floor, where the blue card is. The blue door leads to the red card. So every return
is to a room he knows, entered from another door at its clock 0: the same clockwork, a new
puzzle. The dead ends (the booth, the card's end of the shop floor) are where the cards lie,
in and out by one door, and the rule that a card is the run's only when he leaves the room with
it (A's rule 4, below) keeps the way out a real half of the puzzle.

## The rules (agreed with A; NOTES_A.md has the runtime's side)

- A **door** (`door` in the schema) is a box in a gap of the wall map. He goes through it when
  his centre is inside it, into the room of its `to`, at that door's spawn, the clock at 0; or,
  with `end`, out of the stage.
- A **card door** (`card` blue or red) is shut until he walks into it holding that colour (his
  centre within 0.38 m of its box). Shut, it is a wall that blocks cones and stops everyone.
  Opened, it stays open, and its `to` with it.
- A **keycard** is picked up when his centre comes within 0.5 m. It opens every door of its
  colour and is not used up.
- **Caught, or START**: back at the spawn of the door he came in by, the room's clock at 0, and
  the room as it was when he came in. Cards and doors become the run's only when he leaves the
  room.
- **Re-entering a room** starts its clock at 0, as any entry does.

## How it sits in the World Kit

One world, `level2` (`levels/level2/level2.world.json`, in `worlds.txt` after level1), built by
`make_level2.py` from the rooms' files exactly as level 1 is (`levels/level1/ROUTE.md`, "How the
rooms join"): each room in its own 32 m cell, side by side along x in the `next` order, at its own
floor's height; one region per room; kit-made stand-ins (whole rooms: the caps are 700 a cell,
and 720, 1,600 and 1,400 for the dressed cinema, shop floor and food hall, whose main recipes are
larger). The doors
join the rooms; `next` only orders them, left to right, and the `first` room (the cinema) holds
the stage's start.

**The section.** The cells' x order is the building's section: the cinema, the booth over the
back of it, the corridor behind both, the shop floor a floor down, the food hall in the basement.
Every door joins rooms one or two cells apart, so the pull-back between any two rooms a door joins
holds both (E's transition frames the room left and the room entered, wherever they are). The
widest pull-backs are the corridor to the cinema (one cell between them, the booth, raised 4 m)
and the shop floor's lift to the food hall (35 m down, which the packed model closes up to 9).

**The section model** (E's `dr_section.akr`) orders the rooms by `first`/`next`, draws the
route between the doors a door joins (a room of a door stage has no `exit`), and captions each
room with its `room.name`, a World Kit name (`the_cinema`, shown THE CINEMA).

## The difficulty, room by room

- **Cinema**: two moving watchers and a fixed cone. One wait, one walk. The gentlest; it opens
  the stage.
- **Corridor**: three watchers, timed against each other. The office guard's cycle and the column
  are what the stage teaches; the porter and the camera set the windows.
- **Shop floor**: a long round and a camera on the lift. The card leg is a walk behind the round
  with one timed step in front of the camera; the lift leg is the reverse.
- **Booth**: one watcher in a small room, two machines to hide behind; a breather with a card.
- **Food hall**: three watchers and three stacks of gift boxes (a noise if brushed; the melon
  guard comes to look). A wait by the column, then one dash with about 3 s of window.

## Commands

```sh
python3 carts/afterhours/rooms/cinema/make_cinema.py        # each room's play file and greybox (and booth, corridor, shopfloor, foodhall)
python3 carts/afterhours/levels/level2/make_level2.py       # the stage's world
python3 carts/afterhours/levels/level2/solutions.py         # the eight legs, played on the model; the tapes
python3 carts/afterhours/levels/level2/solutions.py --check --pictures /tmp/s2   # each leg from above
make B=build-mine build-mine/carts/afterhours.mei           # builds the worlds (World Checker) and the cart
MEIC=build-mine/meic RUN=build-mine/mei-headless WORLDS=build-mine/cart-worlds/afterhours carts/afterhours/tests/run.sh 63 12000 /tmp/s2run
```

## Rules for every room (for the room builders)

- **The 1 m cut**: everything in the play area is cut at 1 m (the front wall, pillars, counters,
  machines), its cut top drawn light like a section. Only the back wall, the end walls and what
  stands against the back wall go up to 2.4 m. At 60° a 2.4 m thing hides 1.4 m of floor behind
  it, and the thief with it.
- **Doorways**: leave each doorway open in its wall, framed and lit (a lintel over it, as the
  greybox's). Agent A draws a staff door's leaf (in its card's colour, shut or open) and the
  keycards; build nothing across a doorway. A doorway leads somewhere: dress the space just
  beyond it (a landing, a stair, the lift car) so it reads as a way on.
- **Triangle budget**: the room and everything placed in it, 2,500 triangles (DESIGN.md,
  Budgets). The greyboxes are 100-200.
- **Recipes**: Asset Kit recipes in the room's folder (any subfolder), names starting with the
  room's prefix (`cn_`, `pb_`, `sc_`, `sf_`, `fh_`), built in the room's frame and placed at yaw 0,
  verification required in depth mode (`"verification": {"required": true, "depth": true,
  "perspective": true}`). Point lights are welcome (`lighting.lights`). Every placement needs
  `collision`: a companion recipe with the floor and the walls (walls without tops, as
  `greybox/*_shell_col.asset.json`), or `self` for small things, or `none`.
- **Placements**: list them in the room's `NAME.placements.json` (the same format; ids with the
  room's prefix). Rerunning the room's `make_*.py` never overwrites it once it exists. Tell the
  level lead which folders your recipes are in, for `make_level2.py`'s `ROOMS`.
- **Checks**: `make B=build-mine build-mine/carts/afterhours.mei` builds the stage with the World
  Checker; `python3 carts/afterhours/levels/level2/solutions.py --check` plays the legs on the
  model; scenario 63 (`tests/run.sh 63 12000 OUT`) plays the tapes in the cart.
