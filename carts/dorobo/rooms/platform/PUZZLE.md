# The subway platform: the puzzle (Gate 1; kept for a later level)

**2026-10-15, after the level 1 rules** (caught only at the centre; cones see into a train through
its open doors): train A has two doors a carriage, not three, stands 12 s instead of 10, and the
camera reaches 8.2 m instead of 9.5 (it no longer sees into train A from across the room).
Solution 1 now waits inside train A between its last two doors, where no cone reaches. The tapes
are re-recorded and pass the cart's scenarios 1, 14 and 15. Level 1 is in `levels/level1/`.

The greybox platform's layout, timetables and watchers, and the solutions the room was built
around. `make_platform.py` writes the room from the numbers at its top; `solutions.py` plays the
solutions on a model of the rules (`rules_model.py`) and writes them as the cart's tapes
(`carts/dorobo/tests/tapes/platform_solution.akr`).

## The room

x runs along the platform (right on the screen), z away from the camera; the platform's top is
y = 0.

- **The island platform**, x 1–31, z 3.4–7.6, between **track A** (near, z 1.0–3.4) and
  **track B** (far, z 7.6–10.0). Five pillars on its centre line (x 8, 13, 18, 23, 28), three
  benches between them (x 10.5, 20.5, 25.5; they stop the thief, not the cones), the closed
  **kiosk** at x 15.5 (open at the back: a hiding place), and newspaper bundles behind it (fragile).
- **The way in**: the stair down from the concourse at the platform's west end. The thief starts
  at its foot. Behind it, between the stair and track B, is a nook the platform patrol cannot see
  into.
- **The staff walkway** along the back wall, x 1–31, z 10.0–11.2, across track B. The **staff
  door** (the exit, green) is at its east end, x 29–30. The staff **cupboard** (a hiding place,
  blue) is set into the back wall at x 24.5–25.5. A mop bucket (fragile) stands by train B's last
  door, at x 21.4.
- **The only way onto the walkway is through train B** while it stands with its doors open: its
  doors open on both sides.

## The watchers

| Watcher | Where | What it does |
|---|---|---|
| `guard_platform` (patrol) | the platform's west half | A loop: west along the front, a second's look at the stair, back east behind the pillars, a look east at x 14, round. 1.2 m/s, a lap in about 21 s |
| `guard_kiosk` (posted) | the platform's front, beside the kiosk (17.6, 4.3) | Looks west along the platform 2 s, turns 1.5 s, looks east 2 s, turns back: 7 s a cycle. 6.5 m |
| `camera_far` (camera) | the back wall above the walkway, x 16 | Sweeps the platform across track B, 150° to 210°, 7 s a cycle, 8.2 m. Blind while train B stands in front of it; its foot watches the walkway under it, so the walkway cannot be walked past it |
| `guard_walkway` (patrol) | the walkway, x 17.6–28 | Up and down at 1 m/s, 2 s at each end looking across track B (at the platform's east end, which train B does not reach). About 25 s a lap |

## The timetables

Ticks are 60 a second; times from the room's clock (0 at the stair).

| Train | Runs | Doors open | Stands at | Period |
|---|---|---|---|---|
| **A** (near track) | east, 2 cars of 10 m, 2 doors a car, on the platform side only | 12–24 s, then every 40 s | x 3–23 | 2,400 ticks: `offset` 480, `arrive` 240, `dwell` 720, `leave` 300 |
| **B** (far track) | west, 2 cars of 10 m, doors on both sides | 24–34 s, then every 45 s | x 3.75–23.75 | 2,700 ticks: `offset` 1,140, `arrive` 300, `dwell` 600, `leave` 300 |

Train A's cars have two doors a side, at 2.5 and 7.5 m along each: x 5.5, 10.5, 15.5, 20.5.
Train B's have three, at 1.67, 5 and 8.33 m: x 5.42, 8.75, 12.08, 15.42, 18.75, 22.08.

## The idea

Every run ends the same way: through train B onto the walkway and along it to the door. The
puzzle is getting to train B's doors by 24 s, which door to take, and the walkway guard, who walks
east as the doors open and back west a few seconds later; the cupboard is between them and the
exit. The trains do three things: train A is a corridor nobody can see into, train B is the only
bridge, and train B blinds the camera while it stands. The tools are shortcuts and rescues: the
bell calls a guard to it (here the walkway guard, back past the cupboard), the toys lead one
along.

What a new player tries first, and what stops it (all checked on the model):

- Walking along the platform at once: the platform patrol, within 1 s.
- Waiting behind the stair, then through train B from its first door: 7 s along the train, and
  the walkway guard is coming back west when he steps out.
- Through train B's last door straight to the staff door: the walkway guard is standing at the
  walkway's east end (touched).
- Out of train B at a middle door: the camera's foot.

## The solutions

Times are where the model has them; the cart is within a few ticks.

1. **The trains** (`SOLUTION_PLATFORM`, 36 s). Into the nook behind the stair as the patrol
   comes. When he has turned east behind the pillars, round the stair's foot to x 9.8, out of the
   posted guard's reach; when train A's doors are open and the posted guard looks east, in at its
   second door (x 10.5) and east inside the train to between its last two doors (x 19.4), where
   no cone reaches through a door. When the posted guard looks west, out at the last door (x 20.5),
   between the bench and pillar 4 to train B's last door (x 22.08), and in as it opens (24 s). Through and out
   onto the walkway behind the walkway guard, who is walking east; into the cupboard (A) before
   he turns at the end; when he has gone back west past it, out and along to the staff door.
2. **On foot** (`SOLUTION_PLATFORM_ON_FOOT`, 36 s). The nook, then east behind the patrol along
   the platform's far side to x 9.5. When he is at the east end of his loop looking south, on to
   the kiosk and hide in it from the camera. Out as train B comes in and blinds the camera, past
   the newspapers to train B's last door, and the walkway as in 1.
3. **The bell** (`SOLUTION_PLATFORM_BELL`, 33 s). Solution 1, but the pocket bell is set down on
   the walkway at train B's door. It rings 3 s later and calls the walkway guard back west from
   the walkway's end, past the cupboard, so the thief leaves the cupboard 3 s sooner.

Others the room allows but were not drafted as tapes: train A's corridor with the kiosk instead
of waiting inside the train; a toy set walking west on the walkway to lead the walkway guard
off (it is heard 4 m round, so it has to be set close to him); train B's next stop (69 s) for a
player who missed the first.

## Changing the room

Edit the numbers at the top of `make_platform.py` and run it; then
`python3 carts/dorobo/rooms/platform/solutions.py` to replay the plans and rewrite the tapes (it
refuses if a plan no longer clears), and check them in the cart (`carts/dorobo/tests/run.sh 1`,
NOTES_B.md). A plan waits on what the room does (a guard past a point, a train's doors), not on
fixed times, so small changes to the timetables often need no change to the plans.
