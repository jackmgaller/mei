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

The console ticks 60 times a second, and a frame that is on budget is shown every tick, so the
target is 60 frames a second and one frame is 1/60 s. Measured on 2026-10-03 over 1,200 ticks
each with `mei-headless --gpu-stats`: Sun & Moon Orbs and Lantern Lake both present a frame on
every tick (Orbs: CPU median 256,000 of 500,000 cycles, GPU median 525,000 of 1,000,000).

A frame that is over budget is shown late and lasts more than one tick
([DECISIONS.md, "Lag"](DECISIONS.md#lag)), and the pads are only read when a frame is presented.
So timing windows are to be counted in ticks (the `FRAME` register advances every tick), not in
presented frames: a three-tick window is then the same length of time whether or not a frame was
late, though a late frame still means one fewer chance to read the button inside it. The garden's
frame-timing readout should show both.

## The movement garden

The first level is a small **movement garden** cart, built with the World Kit: a slope, a ledge,
a wall, one collectible and one camera zone to begin with (much like the World Kit's `test_room`
example), growing as the moves need. It is where movement is tuned, so it has:

- a **live tuning menu** for the movement numbers;
- a **frame-timing readout**;
- **wall-kick shafts of several widths**, to tune the wall jump against.

The character and the collectible are drawn with the reader's `wp_draw_object()` (the
character's bounds from `wp_mesh_bounds()` once, its feet as the base), not `mesh_at()`, so that
the platform under them is not drawn over them ([WORLDPACK.md, "Objects"](WORLDPACK.md#objects)
has the rule and what it does not handle).

## Build order

1. The movement garden.
2. One small district block: a few cells of one region, with stand-ins, a layer and palette
   variants.
3. A second region, to force the texture-swap seam.

[WORLDKIT.md, "Build order"](WORLDKIT.md#build-order) says what each stage proves and what the
kits need first.

## Ideas under consideration

These are not decided. They are recorded so they are not lost, and each says what it would ask
of the kits.

### Elevated train lines

The city has a lot of rail, and none of it is underground: the lines run above the streets on
viaducts, each line in its own colour. The player can jump onto a train and off it again. Whether
the inside of a train can be entered is open, and the roof is where the play is; a walkable
interior that is also moving is a hard case and may not be worth it.

What it gives the game: coloured lines are landmarks visible from anywhere, which is how a player
finds their way around an open world; train roofs are moving platforms; a viaduct is a long rail
to grind; stations are hubs. This is the "riding traffic" move in its intended form.

What it asks of the kits: a viaduct is a path (the World Kit's swept path, not yet built), and the
same line can be the track mesh, the train's route and a grind rail. A train is an entity with
collision in its own moving frame, which the pack format already carries. A station concourse is
a natural seam for the texture swap between districts.

### A second city

After the first city (Tokyo-like), a second (Kyoto-like): a Johto to its Kanto. The game becomes
twice as large, with two areas of different character: low-rise streets, temples, hills, a river
and bamboo against rooftops and neon. The first city would hold some fixed number of the
collectible (65 was mentioned; undecided) before the second opens.

It should not feel disconnected. A portal was the first thought; a long-distance train between the
two cities would make the transition feel like travel and fits the elevated lines above.

What it asks of the kits: nothing new in the format. A second city is a second world, and a door
in one world can already name another. It leans on terrain (heightfields and paths) far more than
the first city does. The cost is content, so the first city should be designed so that nothing
assumes it is the only world, and the second decided once a district of the first exists.
