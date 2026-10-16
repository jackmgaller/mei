# The tower, the trading floor (6F): dressing notes

A securities house's dealing room at night in 1990. The city comes in cold through the window
(off-frame, at the front) and its blinds, in slats across the carpet tiles; the quote board on the
back wall is stopped at the close (amber, red and green rows); two dealers' screens are left on,
green; the back office has a green-shaded lamp on its desk; the hall's glass doors stand open
beyond the east doorway and the service stair is lit green beyond the back one.

## Signature props (once in the stage)

- **The quote board**, painted on the back wall (x −5.4 … 9, 0.3 … 2.3 m), its rows stopped.
- **The dealers' desks**: four rows back to back, the screens in pairs (two left on, green), the
  phones and the chairs (one box each, the backrest drawn on the top).
- **The meeting room**: its glass (cut at 1 m, closed), table, five chairs and an ashtray.
- **The back office's desk, its green-shaded banker's lamp, the safe and the filing cabinets.**
  The hall has a reception lamp; this one is a different lamp (brass, green shade, 6-sided) on a
  different desk. If the stage wants one lamp only, this is the one to drop.
- **The window's blinds**, only as light (the slats' shadows across the floor).

No plant (the hall's ficus is the stage's one), no sofa, no medallion, nothing brass at the lifts.

## What stays as the plan says

The partition, its doorway, the back office's desk and stair door, the camera's place; the
meeting room's glass closed and see-through; the columns where they were; the desks low (screens
dark and under 0.9 m but the two lit ones); the front strip east of the meeting room, the strip
north of it and the west end clear; the front cut at 1 m with the tower's granite spandrel and
bronze glass in section. `trading.play.json` is untouched.

## How it is made

`dress_trading.py [--no-placements]` writes the recipes, `art/` and `trading.placements.json`, with
`../passage/diorama.py`'s light and painting. `../passage/capture.py trading --build-dir B
[--verify]` writes `shots/` and `numbers.json`.

| Recipe | Triangles | What |
|---|---|---|
| `tf_floor` | 1,285 | everything but the meeting room's glass (refine cap 240) |
| `tf_glass` | 88 | the meeting room's glass and posts, corners only (`max_added` 0) |
| **room** | **1,373** | of the 2,500 allowed |
| `tf_floor_col` | | the floor, the walls without tops, the partition, the desks, the columns, the meeting room |

Placements: `tf_floor` (collision `tf_floor_col`), `tf_glass` (collision `none`). Both pass the
Asset Checker in depth mode. Slots 13-8,6-0 (the assembler's set for this room); 134,604 bytes
of VRAM; the 8-bit paintings are quantised together, so the room takes one 8-bit palette.

Lights (10): `city_w`, `city_e` (shadows through the window posts and slats), `night`, `board`,
`lamp`, `screen_0`, `screen_1`, `hall`, `stair`, `exit_sign`.

At the game's camera (60°, three pans, 2026-10-15): full 860–903 triangles drawn, CPU
179,878–184,122, GPU 321,837–325,855 cycles; bare 700–729, CPU ~147–150k, GPU ~296–299k.

## What fought me

- Triangles: the first pass was 2,163. The monitors became one box per back-to-back pair with
  screen faces, the desk turrets were painted into the desk tops, and the chairs became single
  boxes with their backs drawn on top.
- Coplanar overlaps in depth mode (the stair's back against its steps, the hall's leaves on the
  hall's floor, the glass's cut strips): 1 cm offsets and opened faces.
- The front face came out one colour: a mesh with hand UVs needs them on every quad.
