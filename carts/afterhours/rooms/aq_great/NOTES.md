# The great tank, dressed (R2)

No questions for J at the moment: every footprint, wall, doorway, walkway, water edge and light box
is where `make_aq_great.py` puts them. One thing to look at: `aq_great.play.json` (17:45) has the
keeper on the back walk patrolling between `ag_wp_keeper_e` and `ag_wp_keeper_w`, while
`make_aq_great.py` (17:48) has him posted. The dressing does not depend on either.

## What it is

The cathedral of the building, on two levels.

- **Below:** the long dark gallery.
  - A blue-black terrazzo floor with brass strips. Its only light is the window's blue band,
    painted with caustics exactly over the light box (z −0.7 … 1.0, the whole width). The rest
    of the floor is dark.
  - Two low dark benches, silhouetted against the band, and the column, cut at 1 m.
- **The window:** one acrylic wall, the whole width, from the floor to the catwalk (glass
  0.3 … 3.0 m).
  - A dark steel sill, piers at both ends and a head under the rim, with three panel seams.
  - The glass adds a blue glow that is strongest at its head.
  - Behind it is the great tank: sand that fades into blue with distance, rock, kelp, a sardine
    school wheeling by the glass, groupers and an eagle ray low down.
- **Above (+3.2 m):** the keepers' catwalks.
  - The rim is grated (cutout slots) with a yellow kick line, railed on both sides.
  - Its three clamp lamps sit on the back rail at 0.84–0.98 m. Their warm pools are painted on
    the grating exactly over `rim_w` and `rim_m`.
  - The two grated bridges and the feeding platform are railed, with the hopper (a funnel cut by
    the section, feed showing) and its chute.
  - The back walk is solid concrete coping with a yellow edge line, feed buckets and a coiled
    hose.
  - The back wall (to 5.6 m) carries board-marked concrete with faint ripple light, a water
    main with red valves, hoses on hooks, nets, a life ring and a gauge (shapes only).
- **The water seen from above** is a half-blended near-black surface with ripples and the lamps'
  warm glints, over the dark tank. It reads as water, not as a second window: the window is the
  bright face seen from below, the surface the dark one seen from above. A manta swims under the
  open water and a second sardine school near the surface at the east end.
- **Beyond the doors:** the corridor to the hall and the jellyfish gallery's violet at the floor;
  the mezzanine's landing and four steps up to the tank tops at +3.2.

## Recipes and placements (`aq_great.placements.json`)

| Placement | Recipe | Triangles | Textures (stored / allocated) | Collision |
|---|---|---|---|---|
| `ag_room` | `dressed/ag_room.asset.json` (shell, window frame, catwalks, rails, hopper, lamps, benches, column) | 498 | 123,175 / 129,632 B | `ag_room_col` |
| `ag_tank` | `dressed/ag_tank.asset.json` (sand, tank back, glass, surface, rock, kelp, fish) | 619 | 51,296 / 56,352 B | none |
| | `dressed/ag_room_col.asset.json`: `aqroom.shell_nodes(collision=True)` from `make_aq_great.ROOM`, the same as the greybox's `ag_shell_col` (walkway floor in a grid) | 280 | | |
| **Room** | | **1,117** of 2,500 | **174,471 / 185,984 B** of about 280 KB | |

- Both recipes pass the Asset Checker in depth mode (`python3 tools/mei_assets.py verify RECIPE
  --build-dir build-ah-R2`).
- Textures are in slots `8,6-3,20-24`; no slot 7 and no palettes 250-251.
- No fonts and no words.
- Signature props: the great window only. There is no shark and no turtle here: they are in the
  tank tops.

## How it is made

- `dress_aq_great.py` writes `dressed/*.asset.json`, `dressed/art/*.png` and
  `aq_great.placements.json`. It is rerunnable. It imports `make_aq_great.py` for its numbers,
  and `s2dress.py` and `dresskit.py` for their helpers.
- **Light:** the floor band and the rim pools are painted. They are full a little inside the box,
  about half on its edge and gone 4 cm outside (`pool()`), and the band's corners are not
  rounded since it runs wall to wall. The kit's point lights (the window and the lamps) only
  shade the props.
- **Section:** everything in play is cut at 1 m above its level (rails, lamps, hopper, column).
  The end walls and the back wall stand at 5.6 m. The window is the gallery's back wall and
  stands floor to catwalk (PLAN.md's must-stay list). At 60° it hides only the tank behind it.
- `capture.py ROOM` (also used by `../aq_tops/capture.py`) is `rooms/corridor/capture.py` for
  two levels and the z pan:
  - The camera stands at both ends of the z pan: 'lo', the front edge on line 222, and 'hi', the
    catwalk's back edge on line 16.
  - It pans in x by 3.65 m either way.
  - A dark-eyed watcher's cone is not drawn, since the game draws it only where it is lit.

## World Checker (`make B=build-ah-R2 build-ah-R2/carts/afterhours.mei`, after `make_aquarium.py`)

- **The aquarium world:** 110 views, **0 hard failures, 2 over thresholds**.
  - Both are `standin_missing` for cells (0, 0) and (2, 0): the entrance hall (1,380 triangles)
    and the jellyfish gallery (1,108), which R1 dressed in the meantime. They are not this
    room's.
  - J's build of the greybox (`build-ah-J`) had 0 and 0.
- **This cell (1, 0):** 2 placements, 1,129 triangles, a stand-in of 498.
- **The game's three vantage points:** 813–818 triangles, 161,498–162,011 draw-CPU cycles and
  185,921–186,367 GPU cycles.

## Shots (`shots/`)

| File | What |
|---|---|
| `aq_great_floor_60.png`, `_x3`, `_pan_x3` | Leg 1. The z pan at the front: the thief at the front row, the night guard with his torch at the window, the gallery, the window and the rim above |
| `aq_great_catwalk_60.png`, `_x3`, `_pan_x3` | Leg 8. The z pan at the back: the thief on the rim, the keeper's torch from the back walk, the floor guard below |
| `numbers.json` | Costs per view |

At the game's camera, with the middle pan and the stand-ins:

| View | Triangles drawn | CPU cycles | GPU cycles |
|---|---|---|---|
| Floor | 996 | 198,736 | 418,108 |
| Catwalk | 1,108 | 219,446 | 461,485 |
| Room alone | 849–854 | 168,352–168,801 | 398,758–428,606 |

## Not done

- No exit pictograms over the doors. The way on beyond each door is a short landing (and the
  stair up to the tops) that is only just on screen at the ends of the x pan.
- The rim lamps are drawn as clamp lamps on the back rail at the cut height. A lamp hung from
  the roof would be above the section's cut.
