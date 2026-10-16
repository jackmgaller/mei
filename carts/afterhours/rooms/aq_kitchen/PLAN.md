# The aquarium, room 6: the fish kitchen (floor plan)

Leg 6 (`levels/aquarium/ROUTE.md`). The keepers' kitchen where the animals' food is made: steel
prep tables in an island, sinks along the back, **the walk-in freezer** in the west corner (its
doorway is a hiding place), a tank of live feed, shelves on the east wall, and **buckets of fish**
on the floor (fragile: a knock is a noise the cook comes to). The brightest room in the building:
a lit room, and the stage's breather. The cook walks round the prep tables and hears a knocked
bucket from anywhere in the room; the way through is behind his back. In up the service stair from the plant (west), out by the door in the back wall
to the tank tops.

## Must stay

- The walls and doorways (west z −3.2 … −2.0; back x 3.8 … 5.0).
- The island (low, x −3 … 2, z −1.2 … 0.2), the sinks (low), the freezer (block, x −6.5 … −4.6, z
  0.6 … 3.0) and its doorway's hiding place (x −4.6 … −3.8, z 1.2 … 2.4), the feed tank (glass),
  the shelves (block), the three buckets' places and sizes (radius 0.35).

## Free to dress

Steel and tile, hanging scales, knives as shapes, boxes of capelin and squid, the freezer's frosted
door, the feed tank's shrimp, rubber aprons on hooks, the stair to the tank tops beyond the door.

## For the builder

- **The numbers** are `ROOM` in `make_aq_kitchen.py` (this folder): walls, doorways, props, water,
  walkways, lights, hiding places, fragile things and watchers, in the room's frame (x right, z
  away from the camera, the floor y = 0, the origin in the middle of the floor; metres). Run it to
  rewrite `greybox/` and the play file; it never overwrites your `aq_kitchen.placements.json`.
  `levels/aquarium/sketch.png` shows the room's plan with the route through it.
- **The play file** (`aq_kitchen.play.json`) is the level lead's (J): the wall map, the lights and the
  watchers. Don't edit it; if a footprint must change, ask J first.
- **Recipes**: Asset Kit recipes in this folder or a subfolder of it, names starting with the
  room's prefix (`ak_`) and not the greybox's own (`ak_shell`, `ak_shell_col`), built in
  the room's frame, placed at yaw 0, verification required in depth mode
  (`"verification": {"required": true, "depth": true, "perspective": true}`). Every placement has
  a `collision`: a companion recipe with the floor (and the upper level's walkways) and the walls
  without tops, as `greybox/ak_shell_col.asset.json` is (its walkway floor is cut into a grid
  so that edges meet end to end: the World Checker fails an edge ending in the middle of
  another), or `self` for small things, or `none`. Placements in `aq_kitchen.placements.json` (format
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
