# The projection booth: dressing notes

A long low room over the cinema's back, the last reel running to nobody. The two 35 mm machines
are cut at 1 m. Their section shows the insides:

- the lamp house glowing orange (it also lights the room);
- the gate and lens;
- the film's path;
- the reels.

Their beams cross the dark to two lit ports in the west wall: additive sheets, unlit. Also here:

- the rewind bench under a warm work lamp, with a light box, a splicer, cans, and two reels
  standing on their rewinds, facing the camera;
- racks of film cans against the back wall, some labelled;
- two posters of old films as shapes: a moon over a sea, and a road at sunset;
- a red light over the door that says a show is running;
- floor worn bare where the projectionist walks round his west machine, with scraps of leader.

## Files (mine)

| File | What |
|---|---|
| `dress_booth.py` | Writes `dressed/*.asset.json` and `dressed/art/*.png`; with `--placements`, also `booth.placements.json`. Imports `make_booth.py` for its numbers only |
| `dressed/` | **The recipe folder for `make_level2.py`'s `ROOMS`**, instead of `rooms/booth/greybox` |

## Signature props (once in the stage)

- **The 35 mm projectors**, their beams and ports.
- **Film-can racks.**
- **The rewind bench with standing reels.**
- **Film posters**: the stage's only posters.
- **The "show running" red light.**

## Numbers

| Recipe | Triangles |
|---|---|
| `pb_room`. Includes light refinement (cap 220) | 332 |
| `pb_beams`: unlit, additive, collision `none` | 2 |
| **Room** (budget 2,500) | **334** |

- **Collision:** `pb_room_col` is the greybox's shell collision under a new name.
- **Asset Checker:** both recipes pass in depth mode.
- **VRAM:** 51,008 bytes of textures.
- **At 60° by `capture.py`:**
  - the room alone: 177 triangles, 40,332 CPU and 213,741 GPU cycles;
  - with the projectionist and his cone: 336 triangles, 71,788 CPU and 232,315 GPU cycles.
- **In the cart (scenario 63, leg 4):** at most 419 triangles, 97,138 CPU and 238,901 GPU
  cycles.
- **Checks:** leg 4 clears, on the model and in scenario 63.

## For the level lead

- **`ROOMS`:** `rooms/booth/dressed`.
- **The projectors:** each is a 0.55 m pedestal under a body cut at 1 m (the wall map says 1.6 m
  and blocking: unchanged). A lens 0.18 m long sticks out west at 0.86 m: the thief can walk
  through it.
- **The red card:** the bench's west end is kept plain, so A's card reads on it.

## What fought me

- **Too dark.** The first light (lamp houses, bench lamp, one dim tube) left the floor
  unreadable. I added a second tube and lightened the floor.
- **The rooms beyond the doorways.** Their side walls (emissive) were too pale at the picture's
  edge, so I darkened them.
