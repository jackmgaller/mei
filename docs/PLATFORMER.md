# The platformer

**Status: design intent, not implementation.** Nothing in this document is built. It records what
the project owner has decided about the first open-world game (from 2026-10-03), and the
movement ideas to try. The tools it needs are the World Kit ([WORLDKIT.md](WORLDKIT.md)) and the
Asset Kit ([ASSETKIT.md](ASSETKIT.md)); the game, its character control and its cameras are its
own ([WORLDKIT.md, "Goals and non-goals"](WORLDKIT.md#goals-and-non-goals)).

## The game

A 3D platformer in a 1990s Japanese metropolis: downtown, shrines, parks, an electric-town
district and a mall. The city is one open world of several regions with many small goals, a
single collectible unit and switches that start challenges. The mall is an interior reached
through doors. The same kit must also serve games built from discrete levels.

- **Time of day** changes, and some goals exist only at certain times (a shrine festival at
  night). To the World Kit, a goal's time window is an ordinary game-defined parameter.
- **Pace** is Mario 64's: brisk and precise, on foot throughout. There is no vehicle and no
  second movement mode.
- **No combat.** There are no enemies to fight, so the attack button is a movement move.
- **Goals come from traversal:** reaching a place, collecting, time trials, and courses that a
  switch starts.

## Moves

Mario 64's base set, with a glider in place of the triple jump. Rails to grind, poles and bounce
surfaces are in. Riding traffic is wanted later and not designed yet.

### The wall jump

Central to the game. It is to sit between two references:

- **Mario 64:** a window of a few frames after touching the wall. Satisfying, and too hard.
- **Mario Sunshine:** slide down the wall and kick off at any time. Too easy.

The idea to try: touching a wall starts a **short slide that decays**, so a late press still
kicks off; a press in the **first few frames** gives a **better kick**, with more height and the
run speed kept. The slide's length, the length of the early window and the two kicks are the
numbers to tune.

### The glider

Replaces the triple jump. To explore:

- how it deploys: on the third jump, or by holding the button at the apex of the second;
- updrafts from rooftop vents;
- cancelling it into a ground pound or a dive;
- the glide range, as the number to tune. It sets how far apart rooftops can be, and the World
  Checker's air views sample the space between rooftops for it ([WORLDCHECKER.md, "Sampled
  views"](WORLDCHECKER.md#sampled-views-check-2)).

### Timing

The timing windows above will be counted in frames, so the game's frame rate must be confirmed
before any of them is written down. The console ticks 60 times a second, but a frame that is
shown late lasts more than one tick ([DECISIONS.md, "Lag"](DECISIONS.md#lag)), so the same
number of frames can be a longer time.

## The movement garden

The first level is a small **movement garden** cart, built with the World Kit: a slope, a ledge,
a wall, one collectible and one camera zone to begin with (much like the World Kit's `test_room`
example), growing as the moves need. It is where movement is tuned, so it has:

- a **live tuning menu** for the movement numbers;
- a **frame-timing readout**;
- **wall-kick shafts of several widths**, to tune the wall jump against.

## Build order

1. The movement garden.
2. One small district block: a few cells of one region, with stand-ins, a layer and palette
   variants.
3. A second region, to force the texture-swap seam.

[WORLDKIT.md, "Build order"](WORLDKIT.md#build-order) says what each stage proves and what the
kits need first.
