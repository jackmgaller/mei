# The aquarium, room 5: the life-support plant (floor plan)

Leg 5 (`levels/aquarium/ROUTE.md`). The basement, as big as the galleries over it: **open sumps of
sea water** crossed by grated walkways, **sand filters** like boilers along the back, pumps standing
in the water and on the front walkway. Lit by work lamps: a lit room. The water carries every
sight across it; the machinery is the only cover. The plant engineer walks his round of the west
half; a camera at the front walkway's east end looks back along it. In from quarantine's stair
(west, onto the back walkway), out up the service stair (east, off the front walkway). Teaches
water.

## Must stay

- The walls and doorways (west z 1.4 … 2.6, east z −3.4 … −2.2).
- The water: the front channel (z −4.5 … −3.4), the four sumps (z −2.2 … 1.4, between the cross
  walkways), all as open water a little below the walkways.
- The walkways: front z −3.4 … −2.2, back z 1.4 … 2.6, cross walkways x −5.2 … −4.0, −0.2 … 1.0,
  4.8 … 6.0; the back zone z 2.6 … 4.5 between the filters.
- The sand filters (block, x −7.2 … −5.2, −1.6 … 0.4, 3.6 … 5.6, z 3.0 … 4.5); the pumps (block):
  two on the front walkway's north half (x −2.0 … −1.4 and 3.0 … 3.6, z −2.7 … −2.2), two in the
  sumps by the cross walkways.

## Free to dress

Pipework overhead and along the walls (kept off the play area or cut at 1 m), valves and gauges,
the filters' manways, the sumps' bubbling and foam, protein skimmers, work lamps' cages, a
clipboard on a hook, the stairs beyond the doors.

## For the builder

- **The numbers** are `ROOM` in `make_aq_plant.py` (this folder): walls, doorways, props, water,
  walkways, lights, hiding places, fragile things and watchers, in the room's frame (x right, z
  away from the camera, the floor y = 0, the origin in the middle of the floor; metres). Run it to
  rewrite `greybox/` and the play file; it never overwrites your `aq_plant.placements.json`.
  `levels/aquarium/sketch.png` shows the room's plan with the route through it.
- **The play file** (`aq_plant.play.json`) is the level lead's (J): the wall map, the lights and the
  watchers. Don't edit it; if a footprint must change, ask J first.
- **Recipes**: Asset Kit recipes in this folder or a subfolder of it, names starting with the
  room's prefix (`ap_`) and not the greybox's own (`ap_shell`, `ap_shell_col`), built in
  the room's frame, placed at yaw 0, verification required in depth mode
  (`"verification": {"required": true, "depth": true, "perspective": true}`). Every placement has
  a `collision`: a companion recipe with the floor (and the upper level's walkways) and the walls
  without tops, as `greybox/ap_shell_col.asset.json` is (its walkway floor is cut into a grid
  so that edges meet end to end: the World Checker fails an edge ending in the middle of
  another), or `self` for small things, or `none`. Placements in `aq_plant.placements.json` (format
  `after-hours-placements`, ids with the prefix).
- **Budget**: 2,500 triangles for everything placed. Textures: this room's region uses texture
  slots `8,6-3,20-24` (10 slots of 32 KB); keep its textures within about 280 KB, and never touch
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
