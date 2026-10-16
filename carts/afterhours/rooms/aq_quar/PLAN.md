# The aquarium, room 4: quarantine (floor plan)

Leg 4 (`levels/aquarium/ROUTE.md`). Behind the public galleries, through the staff door: the
quarantine room. Two long rows of holding tanks on stands (glass: cones pass), their filter
cabinets at the east ends, the keepers' desk in the front corner. Dark but for **ultraviolet
sterilisers** over the rows, which switch between the rows every three seconds, and the stair
door's lamp. A keeper with a torch does his rounds; a camera over the stair door down to the
plant sees only what the lamps light. In from the ocean gallery (west, back), out down the stair
(east, front). The dark, the torch and the timers together.

## Must stay

- The walls and doorways (west z 1.8 … 3.0, east z −3.4 … −2.2); the tank rows (glass, x −4.2 …
  4.2; back row z 1.2 … 2.0, front row z −1.4 … −0.6), the filter cabinets (block) and the desk
  (low) where they are.
- The lights: the back row's UV (x −4.4 … 4.4, z 1.0 … 3.2) and the front row's (z −1.8 … 1.0),
  each on 180 ticks of 360, alternately; the stair door's lamp (x 5 … 6.5, z −4 … −1.6).

## Free to dress

The holding tanks' occupants (a sick ray, small sharks, labelled tubs as shapes), airlines and
tubing, the UV tubes' violet, buckets, a whiteboard of pictograms, the stair down beyond the door.

## For the builder

- **The numbers** are `ROOM` in `make_aq_quar.py` (this folder): walls, doorways, props, water,
  walkways, lights, hiding places, fragile things and watchers, in the room's frame (x right, z
  away from the camera, the floor y = 0, the origin in the middle of the floor; metres). Run it to
  rewrite `greybox/` and the play file; it never overwrites your `aq_quar.placements.json`.
  `levels/aquarium/sketch.png` shows the room's plan with the route through it.
- **The play file** (`aq_quar.play.json`) is the level lead's (J): the wall map, the lights and the
  watchers. Don't edit it; if a footprint must change, ask J first.
- **Recipes**: Asset Kit recipes in this folder or a subfolder of it, names starting with the
  room's prefix (`qt_`) and not the greybox's own (`qt_shell`, `qt_shell_col`), built in
  the room's frame, placed at yaw 0, verification required in depth mode
  (`"verification": {"required": true, "depth": true, "perspective": true}`). Every placement has
  a `collision`: a companion recipe with the floor (and the upper level's walkways) and the walls
  without tops, as `greybox/qt_shell_col.asset.json` is (its walkway floor is cut into a grid
  so that edges meet end to end: the World Checker fails an edge ending in the middle of
  another), or `self` for small things, or `none`. Placements in `aq_quar.placements.json` (format
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
