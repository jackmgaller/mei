# The aquarium, room 2: the jellyfish gallery (floor plan)

Leg 2 (`levels/aquarium/ROUTE.md`). A narrow dark gallery of jellyfish: **four glass columns** down
its middle and a row of small wall tanks along the back. Each column's lamp comes up and fades on
its own cycle, one after another from the west, so a wave of light runs down the gallery every
eight seconds; each lamp lights its whole bay, front to back. A guard stands in the far front
corner looking back up the gallery; a keeper without a torch walks the back aisle. In from the
great tank (west, front), out to the ocean gallery (east, back), walking in the dark behind the
wave. Teaches lights on a cycle.

## Must stay

- The walls and doorways (west z −3.2 … −2.0, east z 1.6 … 2.8); the columns (glass, 1 m square
  at x −4.5, −1.5, 1.5, 4.5, z −0.5 … 0.5; round inside the square); the wall tanks along the back
  (glass, z 3.6 … 4.0, x −5.5 … 5.5).
- The four bays' lights, x −6 … −3, −3 … 0, 0 … 3, 3 … 6, the whole depth (z −4 … 3.6), each on
  for 240 ticks of 480, 120 ticks after the one west of it. The ends (x beyond ±6) are never lit.

## Free to dress

The jellyfish themselves (moon jellies, sea nettles; violet, pink, pale), the columns' rims and
bases, the lamps' colour (each bay its own hue is welcome), the wall tanks' small lives, a
bench, the floor's reflections in the lamps' colours.

## For the builder

- **The numbers** are `ROOM` in `make_aq_jelly.py` (this folder): walls, doorways, props, water,
  walkways, lights, hiding places, fragile things and watchers, in the room's frame (x right, z
  away from the camera, the floor y = 0, the origin in the middle of the floor; metres). Run it to
  rewrite `greybox/` and the play file; it never overwrites your `aq_jelly.placements.json`.
  `levels/aquarium/sketch.png` shows the room's plan with the route through it.
- **The play file** (`aq_jelly.play.json`) is the level lead's (J): the wall map, the lights and the
  watchers. Don't edit it; if a footprint must change, ask J first.
- **Recipes**: Asset Kit recipes in this folder or a subfolder of it, names starting with the
  room's prefix (`aj_`) and not the greybox's own (`aj_shell`, `aj_shell_col`), built in
  the room's frame, placed at yaw 0, verification required in depth mode
  (`"verification": {"required": true, "depth": true, "perspective": true}`). Every placement has
  a `collision`: a companion recipe with the floor (and the upper level's walkways) and the walls
  without tops, as `greybox/aj_shell_col.asset.json` is (its walkway floor is cut into a grid
  so that edges meet end to end: the World Checker fails an edge ending in the middle of
  another), or `self` for small things, or `none`. Placements in `aq_jelly.placements.json` (format
  `after-hours-placements`, ids with the prefix).
- **Budget**: 2,500 triangles for everything placed. Textures: this room's region uses texture
  slots `13-9,16-19` (9 slots of 32 KB); keep its textures within about 250 KB, and never touch
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
