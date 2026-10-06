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
`--lattice N`, `--tries N`, `--seed N`, `--processes N`, `--config FILE`. It needs NumPy and SciPy;
Pillow for the map.

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
| The drop check | floorless columns (faces steeper than a floor) within 4 m of a reachable floor: the real controller dropped over each from 3 m above; the ones that fall through, clustered |
| Sealed places | edges into a box of the world's notes other than its intended ways in |
| Collectibles | for every coin, red coin and star: taken walking, on a pole, grinding, hanging, or by which flight (in the air, gliding or diving); those nobody reaches |
| Cards taken gliding | a star whose box a glide passes through |
| Shortcuts | with the shortcut shut, the cheapest route from its near end to its trigger; under 30 s it is bypassed |
| Paths | each walkable sweep (a trail, a bridge, a stair) walked end to end both ways on the walk graph alone, within its width: where it stops and why (a wall and what it belongs to, a step up, a steep floor) |
| Traps | reachable floors from which the spawn cannot be reached again without a respawn |
| Glide windows | each glide case of the world's cases file flown from its take-off, moved up to 2 m along x and z and aimed 10 and 20 degrees off: the window of take-offs that land |

## The world's notes (`worlds/NAME.json`)

What the geometry cannot say: the sealed places (a box and the moves meant to enter it), the
shortcuts (the trigger and the near end), and the cases file whose glides to measure.
`worlds/shrinetown.json` has star 4's chamber, shortcuts A to E and glides G1 to G9.

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

**Cases to paste.** `cases/explore_driver.akr` is the probe driver (the `ExProbe` struct and the
`ex_*` functions); each `cases/FIND.akr` gives the probe row and the check that fails while the bug
is there (`expect(!ex_out, ...)`, `expect(ex_through < 0, ...)`, ...). Paste the driver once into
a cases file with its rows as `EX_PROBES`, give it a scenario number, hook it as `harness.akr`
hooks the others, and add it to the run list.

## Time

## Limits

## Tests

`tests/test_explore.py`: the numbers are the cart's; flights over a hand-made column world match
the controller's per-tick arithmetic (a running jump's ticks and distance, a ledge grab, a
backflip grab a hop cannot make, leaving the frame, falling through a hole); the harness hooks fit;
the reach map on the garden world reaches every coin; one probe flown headless.

```sh
B=build-explore python3 -m unittest discover -s tests -p test_explore.py -v
```
