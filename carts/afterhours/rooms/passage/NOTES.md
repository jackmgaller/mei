# Room 3, the passage: dressing notes

The passage under the street at night, dressed on the level lead's plan (`PLAN.md`). Cool tube
light in pools down its length, three small shops with their shutters down and their fascia
signs lit (white, amber, pink), the vending machine blazing at the front, a payphone, a fire hose
cabinet's red lamp at the west end, the camera's red lamp at the east, and the way on lit warm
from the stair up to the lobby. In the ground in front of the cut wall, the services that run
beside a passage under a street (a duct bank, water and gas mains, drains), drawn in section.

## Signature props (so that rooms 1 and 2 do not repeat them)

- **The vending machine** (the level's only one), cut at 95 cm to show its lit columns of cans,
  its recycling bin, and its light on the floor.
- **Three shop fronts with their shutters down**, each shutter painted with its shop's sign: a
  key (the key cutter), a cup (the coffee shop), a flower (the florist); lit fascia signs above.
- **The coffee shop's window of food models** on the pier beside its shutter: an omelette on
  rice, spaghetti, a cream soda with its cherry, a slice of cake. Its crate of empties and the
  morning's papers, tied, by its shutter; the florist's green buckets by hers.
- **A green payphone** on its shelf between two shops.
- **One paper poster repeated five times** along the back wall (a fictional film: a crescent moon
  over a figure on a roof's edge). Paper, not lightboxes (room 1 has the level's lightbox ads).
- **A fire hose cabinet** with its red lamp, and a route map (coloured lines) by the way in.
- **A lost clear umbrella**, open on its side by the first pillar, with its puddle and a trail of
  drips from the way on.
- **The tactile paving line** from door to door, and the ground's services in section on the
  front.

No bench, clock, plant or lightbox ad here.

## What stays as the plan says

The walls, the doors and the wall map are the plan's (`passage.play.json` is untouched). The
four pillars are 0.8 m square, opaque, cut at 1 m, where they were; the vending machine is
x −0.6 … 0.6, z −3.4 … −2.9, 0.95 m high; the exit is under the camera. Nothing new stands in
the east half but against the back wall (the crate, the papers, the buckets: 0.3–0.42 m, out of
every route), and nothing on the front strip but the bin, west of the machine (x −1.02 … −0.7,
z −3.38 … −3.1, 0.74 m). Everything in the play area is under 1 m; only the back wall and what
hangs on it (signs, payphone, hose cabinet, the food window) go higher.

## How it is made

`dress_passage.py` writes the recipes, the textures in `art/` and `passage.placements.json`
(`--no-placements` leaves the placements alone). `diorama.py` holds what it shares with the
lobby's script: recipe pieces, the kit's light formula evaluated on painted surfaces, painting.
`capture.py passage|lobby [--verify]` draws a room through Mei at the game's camera (the framing
of `dr_view.akr`'s `frame_room()` as of 2026-10-15: the floor between lines 16 and 222) and writes
`shots/` and `numbers.json`. Needs Pillow and NumPy.

| Recipe | Triangles | Vertices | What |
|---|---|---|---|
| `r3_passage` | 609 | 429 | the painted floor and back wall, the cut walls, the pillars, the machine and bin, signs, payphone, hose cabinet, umbrella, crate, papers, buckets; 191 of its triangles are light refinement (cap 220, not reached) |
| `r3_showcase` | 246 | 162 | the food window: its own recipe, lit by its own lamp, corners only (`max_added` 0), so no light refines its glass |
| **room** | **855** | | of the 2,500 allowed |
| `r3_passage_col` | 74 | | collision: the floor, the walls without tops, the pillars, the machine |

Placements: `r3_passage` (collision `r3_passage_col`) and `r3_showcase` (collision `none`: it
hangs on the back wall, inside the wall's collision). All recipes pass the Asset Checker in depth
mode. Textures: 100,252 bytes of VRAM; the five 8-bit paintings (three floor strips, two wall
strips) are quantised together to one set of 255 colours, so the region takes **one** 8-bit
palette (31 in my build) of the level's 16.

**Light.** One list, `room_lights()`, 16 lights (the kit's limit): four ceiling tubes (painted as
1.1 m tubes, baked as points), the three fascia signs, the vending machine, a dim blue night fill,
the hose cabinet, the camera's lamp, the two stairs' spill through the doors, the payphone, a
light over the posters, the food window. The kit bakes it into the walls' ends and the props; the
floor and the back wall are painted from the same list by the kit's formula, with soft shadows
from the pillars, the machine and the walls (24 samples a light, for smooth penumbrae), and are
emissive, so the kit refines nothing on them. The floor adds what corners cannot carry: the
tubes' and the machine's reflections in the polished tiles (offset toward the camera as a 60°
view sees them), the tactile line, the drips.

## Costs (`shots/numbers.json`), the game's camera, depth mode

| View (pan x) | Room alone: drawn / CPU / GPU | With the thief, the camera's cone |
|---|---|---|
| west end (−4.65) | 428 / 104,485 / 251,772 | 503 / 119,500 / 264,346 |
| middle (0) | 417 / 103,578 / 249,100 | 491 / 118,501 / 275,508 |
| east end (+4.65) | 445 / 106,307 / 250,466 | 517 / 121,046 / 283,962 |

About 10.5 % of the CPU and 12.5 % of the GPU for the room. In the level's world (built privately
with these placements): the cell is 855 triangles, its stand-in 246; the World Checker reports 0
hard failures and 0 over thresholds in 81 views. The cart's 25 scenarios pass on that world
(41–47 among them), and `levels/level1/solutions.py --check` clears the passage on tick 936.

## Shots

- `passage_60.png`: the three views of the pan side by side (x2); `passage_60_K.png` and
  `_x3`: each view, 320 × 240 as the console draws it, the thief stand-in in the last pillar's
  sight shadow (4.6, −2.3) and the camera's cone at 235° (16 rays, cut by the play file's walls).
- `passage_game.png`: the cart itself (scenario 43 at tick 560) on the dressed world.

## What fought me

- **Painted walls meet the kit's shadows.** The first back wall was dark: its shutters stand
  0.2 m back inside the wall's own blocker box, so every light was shadowed. The walls the
  painting stands on are not blockers now.
- **Eight samples band.** The kit's eight soft-shadow samples, painted at 24 texels a metre, drew
  stepped ghosts of the pillars in the signs' pools; the painting takes 24 samples spread through
  the light's sphere instead.
- **The framing moved under me** (agent A, 2026-10-15): the whole floor and the cut front wall are
  now in the picture, with a band of void below. The front wall's face got the ground's section.
- **Sixteen lights is a wall.** The list is exactly at the kit's limit; another light means
  folding two together (the stairs' spills, say).
- The usual: flush faces where lintels meet their walls and a phone stands on its shelf, fixed by
  insetting 1 cm.

## Stage change (2026-10-15): the way out is the station's stair to the street

Stage 1 is now the station alone, so the east doorway leads up to the street. Only what is seen
beyond it changed (`street_stair()` in `dress_passage.py`; the play file and the puzzle did not):

- **The stair up to the street**: 12 wet steps rising east from the doorway, its stairwell's
  wall and handrail, its front cut at 1 m like the passage's; a few streaks of rain coming down
  it (additive, under the section's ceiling).
- **The street's cold light** (`street`, blue-white, soft shadows through the doorway) in place
  of the lobby's warm one; the floor inside the doorway painted wet, with the street's light in
  it.
- **The exit pictogram** (a figure running out through a doorway, on green) on a flag sign under
  the lintel. Its glow on the floor is painted only (a `paint` light): the kit's 16 are taken.

`r3_passage` is now 792 triangles (the room 1,038 of 2,500). The room alone draws 593–613
triangles, about 136,000 CPU and 262,000 GPU cycles. The game's pan stops with the doorway at
the picture's edge, so in play only the flag, the cold light and the wet floor show; the stair
reads in the pull-back and in `shots/passage_60_beyond.png` (`capture.py passage --beyond 9`).

## For the level lead

`make_level1.py`'s `ROOMS` entry for the passage: asset folder **`rooms/passage`** (the greybox
folder can stay or go: no name is in both). `make_*.py` was not rerun.
