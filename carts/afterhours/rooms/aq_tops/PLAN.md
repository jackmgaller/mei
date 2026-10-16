# The aquarium, room 7: the tank tops (floor plan)

Leg 7 (`levels/aquarium/ROUTE.md`). The second floor over the big tanks, where the public never
goes: the open water of **the shark tank** (west) and **the turtle pool** (east) under a dark roof,
crossed by narrow walkways and a bridge, life-support housings at two corners, a few work lamps
hung over the walkways (the bridge's on a cycle). A keeper with a torch walks round the shark
tank; a camera at the east end looks across the water and sees only the lamps' light. In from the
kitchen (east, front), out by the stair down to the great tank's catwalk (west, back). Walkways
over water in the dark.

## Must stay

- The walls and doorways (east z −4.2 … −3.0, west z 3.1 … 4.3).
- The water: the shark tank x −7.6 … −1.4, z −3 … 3, cut by the bridge x −4.9 … −3.9; the turtle
  pool x 1.4 … 7.6, z −3 … 1.6. Everything else is walkway.
- The housings (block) where they are.
- The lights: the middle walkway's lamp (x −1.4 … 1.4, z −1.2 … 1.2), the bridge's (on 210 ticks of
  420), the front walkway's (x 2 … 5) and the back's (x −6.4 … −3).

## Free to dress

The sharks' fins and the turtles under the surface, the water's ripples lit by the lamps, the
tanks' rims and their life-support pipes, a keeper's skiff tied up, nets and poles, the roof's
trusses (above the section's cut), the stair down beyond the west door.

## For the builder

- **The numbers** are `ROOM` in `make_aq_tops.py` (this folder): walls, doorways, props, water,
  walkways, lights, hiding places, fragile things and watchers, in the room's frame (x right, z
  away from the camera, the floor y = 0, the origin in the middle of the floor; metres). Run it to
  rewrite `greybox/` and the play file; it never overwrites your `aq_tops.placements.json`.
  `levels/aquarium/sketch.png` shows the room's plan with the route through it.
- **The play file** (`aq_tops.play.json`) is the level lead's (J): the wall map, the lights and the
  watchers. Don't edit it; if a footprint must change, ask J first.
- **Recipes**: Asset Kit recipes in this folder or a subfolder of it, names starting with the
  room's prefix (`at_`) and not the greybox's own (`at_shell`, `at_shell_col`), built in
  the room's frame, placed at yaw 0, verification required in depth mode
  (`"verification": {"required": true, "depth": true, "perspective": true}`). Every placement has
  a `collision`: a companion recipe with the floor (and the upper level's walkways) and the walls
  without tops, as `greybox/at_shell_col.asset.json` is (its walkway floor is cut into a grid
  so that edges meet end to end: the World Checker fails an edge ending in the middle of
  another), or `self` for small things, or `none`. Placements in `aq_tops.placements.json` (format
  `after-hours-placements`, ids with the prefix).
- **Budget**: 2,500 triangles for everything placed. Textures: this room's region uses texture
  slots `2-0,25-31` (10 slots of 32 KB); keep its textures within about 280 KB, and never touch
  slot 7 or 4-bit palettes 250-251 (the front end's fonts).
- **The section cut**: everything in the play area is cut at 1 m above its own level with a light
  cut top; only the back and end walls stand full height. Doorways stay open and framed, with a
  way on beyond them (the next room's stair, landing or corridor).
- **Light is the puzzle in a dark room**: the lit floor is the play file's `light` boxes. Paint
  the glow on the floor (as `rooms/aquarium/make_aquarium.py`'s `paint_floor()` does) where they
  are and keep the rest dark: what looks lit is lit. Round a box's corners in the paint, never
  move it. A light on a cycle (`period`, `on`, `offset` ticks) is drawn by A's runtime as a wash
  when on; paint its patch as the lamp's colour at half strength, so it reads lit or unlit by the
  wash. A lit room is lit as you like.
- **Fonts** from `tools/fonts/` only. No readable words: signs are lit shapes and pictograms.
- **Signature props once per stage** (the welcome tank, the great window, the jellyfish columns,
  the ocean window, the sand filters, the turtle, the shark): only in the room this plan gives
  them.
- **Checks**: `python3 tools/mei_assets.py verify RECIPE --build-dir YOUR_BUILD_DIR`;
  `python3 carts/afterhours/levels/aquarium/make_aquarium.py` then
  `make B=YOUR_BUILD_DIR YOUR_BUILD_DIR/carts/afterhours.mei` builds the stage's world with the
  World Checker (0 hard failures, 0 over thresholds); captures at the game's camera with a copy
  of `rooms/corridor/capture.py` adapted to this room (until the stage plays in the cart: J will
  say when, and which scenario plays the room's legs). Put your notes and captures in `NOTES.md`
  and `shots/`.
