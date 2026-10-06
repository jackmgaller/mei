# The explorer bot

The explorer works out where the garden's robot can get to in a World Kit world and what it should
not get to: places outside the level's frame, spots where a falling body passes through the world,
sealed places entered another way, collectibles nobody can take, cards taken in mid-air, shortcuts
that bar nothing, paths that do not walk end to end and glides with a narrow take-off. Then it
flies each suspicious find again in the real cart, headless, and writes a scenario for each one
it reproduces.

```sh
make B=build-explore                     # meic, mei-headless and the cart's worlds
python3 tools/explore/mei_explore.py carts/garden/shrinetown/shrinetown.world.json --build-dir build-explore
```

It writes into `BUILD/explore/WORLD/` (or `--out DIR`):

| File | What |
|---|---|
| `report.json` | Everything: the reach graph's size, every find with its take-off, its route from the spawn and the headless outcome |
| `map.png` | The frame from above, north up, 2 pixels a metre: reachable floors green, the rest grey, finds marked (legend at the bottom) |
| `summary.txt` | The short summary, also printed |
| `cases/*.akr` | A scenario per confirmed find, to paste into the cart's tests (below) |

Options: `--no-confirm` (the reach map alone), `--deep` (the overnight mode: launches every half
metre, 16 headings, three chained wall kicks, six tries a find, a denser drop check),
`--lattice N`, `--tries N`, `--seed N`, `--processes N`, `--max-confirm N`, `--config FILE`,
`--run-case CASE` (below). It needs NumPy and SciPy, and Pillow for the map; the confirmer needs
meic, mei-headless and the cart's worlds in the build directory (`make B=...`).

## Two parts, one model of the moves

`moves.py` is the robot's move set. Each move is a take-off state, the stick held in the air and the
pad script that makes the controller do it, with every number read from the cart by `tuning.py`:
the tuning table's defaults (`carts/garden/tuning.akr`), the controller's constants
(`player.akr`: the push heights, the ledge hang; `attach.akr`: the pole hold, the hang depth),
the surface map (`ground/ground.akr`) and the body (the game schema's probe: radius 0.3, height
1.6, step 0.32).

| Move | Take-off (default tuning) |
|---|---|
| `walk_off` | run off an edge at 9.6 m/s |
| `hop`, `jump` | 12.6 m/s up standing; running, 15.0 up and 9.6 forward (apex 3.0 m) |
| `double`, `double_stand` | the chained jump: 18.0 up running (4.35 m), 15.6 standing (3.25 m) |
| `third` | 20.4 up running (5.61 m) |
| `double_glide`, `third_glide` | the same, A held through the apex: the glider (8 m/s, sinking 2 m/s, ratio 4) |
| `long` | crouch slide and jump: 9 up, 14.4 forward |
| `backflip` | crouch and jump: 18.6 up (4.65 m), 4.8 m/s backwards |
| `side_flip` | from a skid: 18.6 up, 2.4 m/s toward the stick |
| `jump_dive`, `double_dive` | the jump, then a dive at the apex (+4.5 m/s, up to 14.4) |
| `wall_kick` | off a wall met at 2 m/s or more, upright within 20 degrees: 15.6 up, at least 7.2 out |
| `glide_release` | letting go of a glide (every half second of it) |
| `pole_jump`, `pole_drop` | off a pole (12.6 up, 6 out, away from it), or letting go |
| `grind_off_end`, `grind_jump`, `hang_jump`, `hang_drop` | off a rail: at its end, a jump (12.6), a hang jump (9) or a drop |

`sim.py` flies them: one tick is one of `player_tick()`'s, in its order (the glider at the
apex, air control, gravity or the glider's easing, the horizontal move against walls, the vertical
move, the head at ceilings, the feet onto floors), then `attach.akr`'s grabs from the plain air
states (a pole within 0.65 m of its axis, a rail under the feet or at the hands). Into a wall it
does what `air_wall()` does: a ledge in reach (a gentle floor 0.8 to 1.75 m above the feet just
beyond, with room to stand) is grabbed unless the jump is still rising past it; a wall upright
enough met fast enough is a wall slide, which the next pass kicks off.

`confirm.py` drives the real controller with the same moves: it stands the body at the take-off,
puts the controller in the state the move starts from (the run speed, the chain window after a
landing, a crouch, a crouch slide, a skid, a pole held), presses the move's buttons, and makes the
later presses the flight made (A at a wall slide, letting go of the glide after the same number of
ticks, B at the apex).

## The reach map (`world.py`, `reach.py`)

The pack's collision is laid on a grid of columns 0.25 m apart. Each column keeps every floor
triangle over it (the reader's own edge and height rows, all of them, not only the highest), every
ceiling, and the feet heights at which a wall would push the body (`wp_coll_push()`'s test,
solved for y at each of the three push heights), as sorted arrays that one numpy search answers in
bulk.

- **Nodes:** every floor entry (2.77 million in the shrine town), a node a metre up each pole and a
  node a metre along each rail (grinding either way, and hanging).
- **Walking:** to the next column's floor within a step, where no wall pushes; never uphill off a
  floor steeper than the slide angle (30 degrees); a drop off an edge lands on the next column's
  highest floor below.
- **Flights:** every move from each floor at a boundary (a wall, a drop or a rise within half a
  metre), toward it, on a lattice (1 m; `--deep` half a metre), plus glides aimed at each star and
  red coin from every floor high enough to glide to it. Then the later passes: wall kicks off the
  wall slides met (two deep), letting go of each glide, jumps and drops off every pole level and
  rail sample, grinds to a rail's end.
- **Costs** are seconds (run time, flight time, a little setup per move), so the cheapest route from
  the spawn is a plausible one, printed move by move in the report.

## What it finds (`finds.py`)

| Find | How |
|---|---|
| Escapes | flights from a reachable floor that cross the frame (the cells' rectangle), clustered by where they leave |
| Falls through the world | flights over a column with no floor under the feet that fall below every floor |
| The drop check | floorless columns (faces steeper than a floor) within 4 m of a reachable floor: the real controller dropped over each, every 1.5 m (`--deep` 1 m), from 3 m over the floors round it; the drops that fall below every floor, clustered |
| Sealed places | edges into a region of the world's notes (cylinders or a box) by moves other than its intended ways in; then, with the intended ways taken out of the graph, a route in that the real cart repeats |
| Collectibles | for every coin, red coin and star: taken walking, on a pole, grinding, hanging, or by which flight (in the air, gliding or diving); those nobody reaches |
| Cards taken gliding | a star whose box a glide passes through, flown headless from up to five take-offs |
| Shortcuts | with the shortcut shut, a route from its near end to its trigger that the real cart repeats; bypassed when that route stays within 12 m of the line between the two ends (the long way strays further) |
| Paths | each walkable sweep (a trail, a bridge, a stair) walked end to end both ways on the walk graph alone, within its width, from 1.5 m before its ends: where it stops and why (a wall and what it belongs to, a lip, a steep floor) |
| Traps | connected floors reachable from the spawn from which it cannot be reached again; the 12 largest tried headless with five moves toward eight headings |
| Glide windows | each glide case of the world's cases file flown with the case's own inputs from its take-off, moved up to 2 m along x and z, and aimed 10 and 20 degrees off: the take-offs that land |

## The world's notes (`worlds/NAME.json`)

What the geometry cannot say: the sealed places (cylinders or a box, and the moves meant to enter
them), the shortcuts (the trigger and the near end), and the cases file whose glides to measure.
`worlds/shrinetown.json` has star 4's chamber (the chamber and shaft, and the knot hole's sill),
shortcuts A to E and glides G1 to G9. The garden and the shrine have none.

## The confirmer (`confirm.py`)

The probes run in a copy of the garden's scenario harness in the build directory
(`BUILD/explore/WORLD/`): `carts/garden/tests/*.akr` copied, four hook lines added to the copy of
`harness.akr`, the probes as `explore_cases.akr` (scenario 990), and a copy of `game.akr` whose
`draw()` returns at once, so a probe costs the controller's ticks and not the renderer's (about
1,300 ticks a second a process against 50 drawing). The cart's own files are imported through
`meic -I`. Nothing in `carts/` is edited. The probes are split over up to eight `mei-headless`
runs.

Each find is tried up to `--tries` times: first exactly as found, then moved by up to 0.25 m and
turned by up to 5 degrees by a random generator seeded with `--seed`. The seed, the try and the
probe row are the repro.

**Routes.** A find's own flight is flown from where it took off. The route the reach map gives to
that take-off is checked too, flight by flight: each leg is flown from its own take-off and must
come down within 1.5 m of where the map says. For the shortcuts and the sealed places a leg the
cart does not repeat is taken out of the graph and the route found again (up to four rounds), so
what is reported is a route the real controller flies. A leg that starts on a rail's end is flown
with the leg that put the body on the rail (the controller grinds on by itself); a leg off a hang
is not flown.

**Cases.** For each confirmed find `cases/FIND.akr` is a complete cases file: the probe driver, the
probe, and the check that fails while the bug is there (`expect(!ex_out, ...)` for an escape,
`expect(ex_through < 0, ...)` for a fall through the world, and so on). Run one in the real cart,
drawn, with

```sh
python3 tools/explore/mei_explore.py --run-case build-explore/explore/shrinetown/cases/escape-3.akr --build-dir build-explore
```

(exit status 2 while the bug is there, 0 once it is fixed), or copy it into
`carts/garden/tests/explore_cases.akr`, hook it in `harness.akr` the way `confirm.patch_harness()`
does, and run `tests/run.sh 990 FRAMES out` (the frames are in its first lines).

## Time

On the shrine town (30 cells, 2.77 million floor entries), on a shared 8-core machine with other
builds running: the reach map 3 to 5 minutes (about 5.6 million flights, 70 % of it the first
pass), the confirmer 4 to 7 minutes (about 1.8 million headless ticks: 2,000 drops, 189 glide
probes, 400 to 800 route legs), 8 to 12 minutes in all. The garden: 35 s. Compiling a world into
the kit cache the first time adds its compile (the shrine town about 6 minutes, once).
`--no-confirm` stops after the reach map. `--deep` (half-metre launches, 16 headings, three kicks,
denser drops, six tries) is the overnight mode: several times longer.

## Limits

- The reach map is a model. Walls are column intervals 0.25 m apart, so a wall's push is
  approximated, and a body that comes down into a sloped face is pushed off it along the face's
  normal; how a body slides along walls, the crack bridge and the movers are not modelled. Bounce
  surfaces and water depth are not modelled. What it finds is a candidate until the confirmer
  repeats it; what it does not find is not proof that it cannot be done.
- Moves are flown from floors at a boundary on a 1 m lattice toward the boundary (8 headings), plus
  glides aimed at each star and red coin; a move that needs a precise take-off between lattice
  points, a run-up longer than the run speed gives at once, or a heading between the eight can be
  missed (`--deep` halves the lattice and doubles the headings). Air control is the stick held
  toward the heading (or neutral for the backflip); shortened jumps are only the standing ones.
- Wall kicks chain two deep (three with `--deep`), and come off walls met at the flight's heading;
  the reach map's kicks are its least reliable flights (most route legs the cart does not repeat
  are kicks).
- Flags are ignored: stars that appear on a flag (the race, the bell, the red coins) are taken as
  there, triggers do not fire, layers stay as the world starts (the shortcuts shut).
- The confirmer starts each flight in the controller state the move needs (the run speed, the
  chain window) rather than running up to it, and cannot start on a hang. A find it does not
  repeat may still be real (a take-off it did not hit); one it repeats is real.
- The traps of the reach map are mostly its own misses: the 12 largest are tried headless and
  marked when a move gets out.
- Escapes are judged against the cells' rectangle; a world with a smaller playable area needs a
  frame in its notes (not done).

## Tests

`tests/test_explore.py`: the numbers are the cart's; flights over a hand-made column world match
the controller's per-tick arithmetic (a running jump's ticks and distance, a ledge grab, a
backflip grab a hop cannot make, leaving the frame, falling through a hole); the harness hooks fit;
the reach map on the garden world reaches every coin; one probe flown headless; a written case run
in the real cart passes where the robot stays in the level and fails where it leaves.

```sh
B=build-explore python3 -m unittest discover -s tests -p test_explore.py -v
```
