# Room 1, the last train: dressing notes

The far end of a side platform at Tsukinoura (fictional) after midnight. Fluorescent tubes along
the platform, painted into the floor as pools with the props' soft shadows. Across the track: two
backlit ads, the station's name board and an amber departure board reading 0:12. The stair at the
east end has warm light falling down it from the concourse. The guard reads an amber timetable on
the front wall: the section cuts it, so it shows as a lit line in the wall's cut top, with its glow
on the floor around him. The front wall's section face is hatched like a drawing.

## Files (mine)

| File | What |
|---|---|
| `dress_arrival.py` | Writes `dressed/*.asset.json`, `dressed/art/*.png` and, with `--placements`, `arrival.placements.json`. Imports `make_arrival.py` for the plan's numbers only. Needs NumPy and Pillow |
| `dresskit.py` | Helpers shared with room 2: nodes, recipes, and light painted with the kit's formula |
| `capture.py` | `python3 carts/dorobo/rooms/arrival/capture.py arrival\|gates --verify`: the Asset Checker, then the room at the game's camera (the new framing, NOTES_A.md) into `shots/` |
| `dressed/` | **The recipe folder for `make_level1.py`'s `ROOMS`**, in place of `rooms/arrival/greybox` |

## Signature props (once in the level)

- **Trackside ad lightboxes**: a night sea and a can of coffee. The level's only lightbox ads.
- **The station's name board** with the line's teal band, and the teal band along the wall.
- **The amber departure board.**
- **Moulded platform seats**: blue shells on a steel beam.
- **A smoking corner** at the west end: a standing ashtray and its dashed floor zone.
- **Recycling bins** against the front wall.
- **The timetable** in the front wall.
- **Painted boarding marks** at the train's doors.

Not here: a vending machine (room 3 has it), a clock (room 2's office has the level's clock).

## Numbers

| Recipe | Triangles | Placed |
|---|---|---|
| `r1_station`: platform, track bed, walls, stair, boxes, bins, ashtray. 135 triangles of light refinement (cap 180, not reached) | 397 | once |
| `r1_bench_1`, `r1_bench_2`: the same bench, each lit for its own spot | 144 each | once each |
| `r1_pillar` | 10 | once |
| **Room** | **695** of 2,500 (the greybox: about 260) | |

Collision: `r1_station_col` is the greybox's shell collision, with its shapes, under a new name.
`r1_bench_col` is one solid block of the bench's footprint: with `self`, the gaps between the
seats were cracks in the World Checker. The pillar is `self`.

- **Asset Checker:** all four recipes pass in depth mode.
- **Textures:** 68,846 bytes of VRAM (region `arrival`).
- **Drawn at 60° by `capture.py`**, the room alone: 364 triangles, 77,799 CPU cycles, 260,475
  GPU cycles. With a stand-in thief, guard and cone: 520 triangles, 108,995 CPU, 284,832 GPU.
- **In the cart** (scenario 41, the room's ticks, with the train, the HUD and the cone): at most
  559 triangles, 125,947 CPU and 309,986 GPU cycles a frame. The greybox drew 355, 87,254 and
  269,069.
- **Checks:** the World Checker passes (0 hard failures). `solutions.py --check` clears the room
  (tick 384). All 25 scenarios of `tests/check.sh` pass on a private build of level 1 with rooms
  1 and 2 dressed.

## For the level lead

- `ROOMS` in `make_level1.py`: `rooms/arrival/dressed` instead of `rooms/arrival/greybox`.
  `arrival.placements.json` now names only `r1_*` recipes in `dressed/`. Until `ROOMS` changes,
  rerunning `make_level1.py` breaks the level's build.
- Not in the wall map, so the thief walks through them: the bins (x −1.95 … −0.85, z −4.25 …
  −3.95) and the timetable box (x 5.4 … 6.2, z −4.25 … −4.17). Both sit in the 0.3 m band his
  centre cannot reach. The ashtray, r 0.15 at (−5.95, −3.95), is mostly in that band too. Add
  non-blocking walls for them if you like.
- The benches' moulded backs reach 0.82 m (the wall map says 0.45). They are still low, and cones
  still pass over them.
- Glass is not used here. The cut colour is the aquarium's `#76849e`.

## What fought me

- **The kit's falloff, `(1 − (d/range)²)²`, is steep.** A tube 2.6 m up with range 3.1 put only
  9 % of its light on the floor under it, and the first floor came out black. Pools need a range
  well over the height (4.2–4.7 here). They are therefore broad and soft, so the tubes' sheen is
  painted in.
- **Shadows for the kit are not worth it on the props.** A soft light's shadows on the stair spent
  the whole refinement cap on the balustrades' shadow edges. The kit's lights now have no shadows.
  Shadows are only painted on the floor, where they are free.
- **The front section is in view now** (agent A's new framing). A 2.4 m band of pale cut colour
  took over the bottom of the picture, so the section face is now a darker hatched texture with
  the floor's line. Only the 1 m cut top stays pale.
- **Collision with `self` on a bench of separate seats** made cracks (above).
