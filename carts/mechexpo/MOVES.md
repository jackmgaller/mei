# Mech Expo 2000: the moves

The two mechs' moves, their timing and what each is for. The animator (F) animates from this
page; the fight (`fight.akr`, `fighter.akr`, `moves.akr`, `meter.akr`, `cpu.akr`) owns what a hit
does. The split is the contract's ([README.md](README.md#interfaces)): **timing, boxes, root
motion and marks are in the animations; damage, hitstun, blockstun, chip, meter, knockback and
cancels are in the fight.** The frame counts below are the design F works to; F may move them
by a frame or two for the motion's sake, and the fight reads whatever the animations say. A
change of more than that comes back to C.

Until A's `anim.akr` and F's animations land, `moves.akr` holds stand-in timings and boxes with
these numbers, so the fight plays and the test cases run with boxes for mechs.

## Reading the tables

- **60 frames a second.** *Startup* is the frames before the first active frame (startup 7: the
  hit box first appears on frame 8). *Active* is the frames with a hit box. *Recovery* is the
  frames after the last active frame until the mech can act again. *Total* is the animation's
  length (`anim_len`).
- **Distances** are metres in fight-local coordinates: x forward from the root (the floor under
  the pelvis), y up. A box written `x 2.0–7.2, y 6–9` spans those ranges. The mechs are about 12 m
  tall; the Hero's sword is about 7 m from grip to tip.
- **Damage** is out of 1,000 health (the Hero has 1,000, the Double-blade Hero 950). A round
  should turn on five to eight clean hits.
- **On block** and **on hit** are the frame advantage when the first active frame connects
  (against a standing mech): negative means the attacker recovers later than the defender.
  Around −3 is safe; −8 or worse can be punished by the other mech's neutral attack, −15 by
  almost anything. They are measured from the fight itself (`tests/run.sh 17`, with the
  stand-in timings), so they include the frame the fight takes to return a mech to neutral.

## Rules every move shares

**Controls.** Stick or d-pad: walk forward or back, crouch (down). A attack, B special, X jump
(with forward or back for a diagonal jump), Y grab, R block, A + B super. A move is the
direction held when the button is pressed plus the button: A alone is the neutral attack,
forward + A the forward attack, down + A the down attack, A in the air the air attack; B the same
way for neutral, forward, up and down specials. Back + A is the neutral attack, back + B the
neutral special. No motion inputs, no dashes.

**Input buffer.** A button press is kept for 8 frames: pressed during a move's last frames (or
in hitstun, blockstun or a landing), it comes out on the first frame the mech can act. A and B
pressed within 3 frames of each other is the super; a move started by the first of the two
within those frames becomes the super.

**Blocking.** Hold R. Block stops every attack from either side (no high or low, no cross-up).
The mech stands still while it holds R, and it can release it at any time outside blockstun.
Normal attacks do no damage through a block; **specials and the super do chip damage** (the
chip column). Chip cannot finish a round except from the super. A blocked hit pushes the
defender back; at a wall, or at the 36 m separation limit, the attacker is pushed back instead.

**Grabs.** Y: a short reach, a quick startup. A grab catches a standing or crouching mech that
is idle, walking, crouching or **blocking**: grabs beat block. It misses a mech in the air, in
hitstun, in blockstun, knocked down or getting up, and a mech in the startup of its own move
(it is not "standing"; strikes beat grabs). **Breaking a grab:** press Y within 10 frames after
being grabbed (or up to 3 frames before): both mechs play `grab_break` and are pushed apart. Two
grabs that connect on the same frame break each other.

**Chains.** A move can be cancelled into another during its cancel window (an animation mark,
from its first active frame to a few frames after the last) only after it made contact, on hit
or on block. The chain is A, then forward + A, then a special (or the super):

| From | Cancels into |
|---|---|
| neutral attack | forward attack, any special, super; the Double-blade Hero also into a second neutral attack, once |
| forward attack | any special, super |
| down attack, air attack, specials, grabs | nothing |

So the Hero's longest chain is three hits (A, forward A, a special), the Double-blade Hero's four
(A, A, forward A, a special). Damage in a combo is scaled: the second hit does 80 %, the third
and later 65 %.

**Hitstop and shake.** Both mechs freeze on contact, the defender shaking in place: 8 frames for
a light hit, 11 medium, 14 heavy, 20 for the super; 7 on block. The camera shakes in proportion.

**Hit reactions.** A hit on a standing mech plays `hit_high`, on a crouching one `hit_low`, for
the hitstun's frames (the animation is stretched to fit). A hit in the air, and any move marked
*knockdown*, plays `hit_air` (thrown up and back) until the mech lands, then `knockdown` (32
frames on the floor) and `getup` (20 frames). Knocked down and getting up, a mech can't be hit.
Each hit pushes the defender back along the floor (the knockback slide).

**The separation limit and the walls.** The mechs are never more than 36 m apart, on every
stage, and the stage's edges are its own: the hangar's walls are at x = ±36. A wall or the
limit stops a mech walking, jumping or being knocked further; both are corners. An open edge
is a lip, with ring-outs ([Stages and ring-outs](#stages-and-ring-outs)).

**Facing.** A mech turns to face the other whenever it is on the ground and idle, walking,
crouching or blocking; during a move or in the air it keeps its facing (a jump over the other
mech lands facing the wrong way and turns on landing).

## Stages and ring-outs

A stage (`stages.akr`, [README.md](README.md#stages)) has a half-width and two edges, each a
**wall** or **open**. The demo hangar has walls at x = ±36; the rooftop showcase has the
stairwell's housing (a wall) at x = −26 and an open edge at x = +26; the container port has its
open edge at x = −30 (the quay over the water, behind 1P at the start) and a wall of stacked
containers at x = +30. The rules at an open edge (`fighter.akr`, the ring-out block at its end):

- **The lip.** A mech stops at an open edge as at a wall, its push box against it (x = 26 − 1.5
  for the Double-blade Hero): walking, jumping, a move's root motion, a blocked hit's pushback
  and a hit's knockback slide all stop there, and a sliding defender stopped at the lip passes
  the rest of the slide to its attacker, as at a wall. **A blocked hit never rings out, and
  neither does a hit that leaves the mech standing** (`hit_high`, `hit_low`).
- **Over the edge.** Only a mech carried by a knockdown, a launch or a throw goes over: one in
  `hit_air` (a knockdown hit, a hit in the air, a throw's or a slam's release). It flies its
  arc unhindered by the lip, and once its root is past the edge there is no floor: it falls, out
  of the camera's sight within about 40 frames, and **its side loses the round, RING OUT**, at
  once, whatever the health bars say. Both sides over on the same frame is a draw. The throws
  carry furthest (the Hero's throw lands the other about 10 m in front of the thrower, the
  Vault Throw about 5 m behind it), a knockdown hit 2–4 m (the Low Sweep 2 m, a super's launch
  4 m): near the open edge every knockdown and every throw is a threat.
- **A knocked-out mech** (health gone) may fly off the edge too; the KO stands.
- **The Twins** are one fighter with one health bar: **either twin falling costs the round**.
  Twin B's leash (8 m) does not save it (a falling twin is not pulled back); since the leash
  keeps it within 8 m of twin A, twin B is only at risk when twin A is near the edge.
- **The separation limit and the camera** still apply. The camera may look up to 10 m past an
  open edge (a metre past a wall), so the drop is in view when a mech is near it.
- **Training:** a mech that falls is put back on the deck 10 m inside the edge after 100
  frames; the round goes on.
- **The CPU** (`cpu.akr`, its end): backed up within 7 m of an open edge with the other in
  reach, it jumps out over the other, blocks, throws it or walks out; within 11 m it walks out
  more often; it blocks a coming attack more often at the lip; with the other within 9 m of the
  edge it throws it up close and uses a knockdown (its down attack) when the other is near the
  lip, and walks the other toward the edge from further out. Its dice are rolled only on a
  stage with an open edge, so the hangar's matches are unchanged.

Events: `Ev.RingOut` (side: the winner; x: where the mech went over), and `fight.ringout` (the
side rung out this round, −1 none, 2 both); the HUD shows RING OUT as it shows K.O.

## The meters

One bar of power, shown as a gauge, spent all at once on the super (A + B).

**Kinetic (the Hero, Momentum Robotics): fills by landing hits.** About +10.4 % of a bar (125) for each hit
that lands (+10 % for the wave), +5 % for a hit the other blocks, nothing for being hit or for
missing. A bar takes about ten landed hits, about a round's worth. The meter carries over between rounds. Rewards
pressing forward.

**Antimatter (the Double-blade Hero, Umbral Research): borrows.** The reactor fills the meter by
itself, one bar in 20 seconds, plus 5 % for each hit that lands. **The super is available
whenever the meter is at zero or above**: it costs a bar, and if the meter had less, it goes
below zero, down to at most one bar of debt. While the meter is below zero the mech **takes 25
% more damage**, until the reactor climbs back to zero. Saving a full bar first means a super
without debt; borrowing means a super now and a dangerous 20 seconds after.

**Chemical (Beam, Raikō Chemical Group): primes a reaction.** Down + B is Beam's Reaction Prime
instead of an attack: 30 exposed frames, then the reaction runs for 300 frames (5 seconds) and
fills the meter by itself, +2 a frame, half a bar in all. A reaction cannot be started while
one is running (down + B does nothing until it burns out), and a hit before the prime's release
frame spoils it (no reaction). Hits give no meter. The reaction keeps running whatever Beam does
(walking, attacking, in hitstun); it stops only in the freezes and burns out at the end of the
round. The meter carries over between rounds; the super costs a bar. Rewards committing at the
right moment, then fighting freely.

**The Siphon (Shadow's curse).** A mech hit by Shadow's Hex Bolt is cursed for 6 seconds: the
meter it would gain goes to Shadow instead, whatever its source (antimatter's at half; of
nuclear's Shadow takes a quarter and the cursed Tank keeps the rest)
([Shadow](#hex-bolt-sp_n-and-the-siphon)).

**Fusion (the Twins, Binary Mechanica): fills only combined.** +2 a frame while the twins are
combined, +5 % for each combined hit that lands, more from Fusion Focus; nothing while split.
The super exists only combined ([the Twins](#the-fusion-meter)). Rewards switching forms at the
right times.

## Movement

| | Hero | Double-blade Hero |
|---|---|---|
| Health | 1,000 | 950 |
| Walk forward | 0.075 m a frame (4.5 m/s) | 0.095 m a frame (5.7 m/s) |
| Walk back | 0.060 m a frame (3.6 m/s) | 0.075 m a frame (4.5 m/s) |
| Walk cycle | 48 frames, two steps (3.6 m forward) | 40 frames, two steps (3.8 m) |
| Jump | 4 frames' crouch, then 38 in the air, 6.5 m high at the top | 3 frames, then 34 in the air, 5.5 m high |
| Diagonal jump | 0.16 m a frame across (6.1 m) | 0.19 m a frame (6.5 m) |
| Landing | 5 frames (8 after an air attack) | 4 frames (7 after an air attack) |
| Push box | 1.6 m either side of the root, 11.5 m tall (7.5 crouching) | 1.5 m, the same heights |

The walk cycles are slow and heavy: the whole mech dips as each foot plants (a `step` mark on
the plant, for the thud). The jump is short and heavy, not floaty: a deep crouch, a hard
launch, the legs tuck at the top, and the landing compresses the knees. The fight moves the
root through the jump (up, forward and back share one animation); `land` plays on touchdown.

## The Hero (Momentum Robotics, kinetic)

An all-rounder with one long sword: spacing at the tip, a reliable anti-air, nothing extreme.
Its stance is upright and square, the sword held out in front at chest height in a guard.

### Attacks (A)

| Move | Startup | Active | Recovery | Total | Damage | Hitstun / blockstun | On block / hit | Hit box |
|---|---|---|---|---|---|---|---|---|
| `atk_n` Guard Cut | 7 | 3 | 14 | 24 | 70 | 18 / 13 | −4 / +1 | x 2.0–7.2, y 6–9 |
| `atk_f` Tip Thrust | 13 | 4 | 21 | 38 | 100 | 26 / 18 | −7 / +1 | x 4.0–10.4, y 6.5–8.5 |
| `atk_d` Low Sweep | 11 | 4 | 24 | 39 | 90, knockdown | — / 16 | −12 / KD +42 | x 2.0–8.0, y 0–2 |
| `atk_air` Falling Cleave | 8 | 6 | to landing | 30 | 100 | 20 / 15 | by height | x 1.0–6.5, y −2–4 (from the root, in the air) |

- **Guard Cut** (`atk_n`): the fastest button and the chain's start. A short horizontal snap
  from the guard at chest height: the sword arm extends, the blade sweeps across, and it is
  pulled straight back into the guard. Little body motion. For stopping a walk-in and starting a
  chain.
- **Tip Thrust** (`atk_f`): the Hero's footsie tool. A half step forward (1.2 m over frames 4–13)
  and a full-length thrust, arm straight, the sword level at 7–8 m high: only the last metres of
  the blade should touch the other mech. During the thrust the arm is hurtable to 5 m out, so a
  whiffed thrust can be hit back on the arm. Slow to retract (the arm comes back in the last
  10 frames). Safe at the tip because the pushback leaves the mechs out of reach; close up,
  −7 is punishable.
- **Low Sweep** (`atk_d`): from a crouch, a low sweep of the sword across the shins, the body
  low and leaning in. Knocks down. Slow and very punishable when blocked or missed; for catching
  a mech that walks back or holds still.
- **Falling Cleave** (`atk_air`): in the air, a downward diagonal cut from over the shoulder,
  in front and below. The sword stays out until landing. Hitting late in a jump leaves time to
  land and Guard Cut (a jump-in combo). Once per jump.

### Specials (B)

| Move | Startup | Active | Recovery | Total | Damage | Chip | Hitstun / blockstun | On block / hit |
|---|---|---|---|---|---|---|---|---|
| `sp_n` Kinetic Wave | 16 | the wave | 32 | 48 | 80 | 16 | 20 / 16 | −16 / −12 at the mech; safe far |
| `sp_f` Charge Slash | 16 | 4 | 26 | 46 | 95, knockdown | 19 | — / 16 | −14 / KD +43 |
| `sp_u` Rising Arc | 6 | 8 | 28 | 42 | 120, knockdown | 24 | — / 14 | −22 / KD +48 |
| `sp_d` Parry | 3 | stance 21 | 18 | 42 (+24 riposte) | riposte 110, knockdown | — | — | — |

- **Kinetic Wave** (`sp_n`): the sword drags along the floor and an upward cut on frame 17
  releases a low wave of force along the floor (a box 1.6 m wide and 3 m tall, from 4 m in front,
  travelling 0.22 m a frame, 13 m/s). One wave each at a time; it vanishes at a wall, after 150
  frames, or against the other mech's wave (both go). The mech stays crouched over the sword
  for 32 frames after. Slow wave, slow recovery: a tool for making the other mech jump or block,
  not a fireball war.
- **Charge Slash** (`sp_f`): a lunging dash, the sword held low behind, travelling 5.5 m over
  frames 4–16, then an upward diagonal slash across the body (x 1.0–7.0, y 3–10). Knocks down.
  The chain's ender; a gap closer from far. Very punishable on block.
- **Rising Arc** (`sp_u`): the anti-air. The mech crouches slightly and springs upward with the
  sword sweeping up from low in front to high overhead (the box follows it, x 0.5–5.0, y 4–14),
  the root rising 5 m during the active frames, then it falls and lands. Invulnerable on frames
  1–7, so it beats a jump-in started in time. Knocks down. On block or a miss it is the
  Hero's most punishable move.
- **Parry** (`sp_d`): a sharp guard stance, sword vertical in front, from frame 4 to 24. A strike
  or a wave that touches the Hero in those frames is parried: the attacker freezes for 20 frames,
  and the Hero's animation jumps to its riposte (24 frames at the end of the same animation:
  a step and a hard horizontal cut, startup 5, active 3, recovery 16, x 1.5–7.5, y 4–10). Grabs
  and the super are not parried. If nothing comes, the stance drops slowly (18 frames): a read,
  not a panic button.

### Grab and throw (Y)

`grab`: startup 5, active 2 (x 1.0–3.6, y 2–10), a missed grab plays `grab_whiff` (22 frames,
the arms closing on nothing and the mech off balance). On a catch: `throw` (44 frames) on the
Hero and `thrown` (44) on the other: the Hero takes the other by the shoulders, lifts, and
hurls it forward on frame 30: 140 damage, the other lands about 8 m away and is knocked down.
The break window is the first 10 frames of the throw.

### Super (A + B): Momentum Drive

The super flash (frames 1–40: the world freezes, the Hero alone moves: it plants, draws the
sword back over the shoulder and the reactor flares), then startup 6, a dash with the sword
straight out that crosses 14 m (root motion) with active frames 47–56 (x 0–8, y 3–10), and 40
frames of recovery (the mech skids to a stop, the sword dragging). Invulnerable from frame 1 to
the first active frame. 340 damage, knockdown; chip 85 through a block (which can finish a
round). On block, −30: whoever blocks it has a free punish. Use it to punish a whiff from far,
or at the end of a chain.

## The Double-blade Hero (Umbral Research, antimatter)

The Hero's frame reworked for rushdown: two short blades, one in each hand. Faster walk,
faster buttons, an extra link in the chain, less reach, 5 % less health. The stance is low and
leaning in, both blades forward. It shares the Hero's move set except the neutral and down
specials, the throw's direction and the super.

### Attacks (A)

| Move | Startup | Active | Recovery | Total | Damage | Hitstun / blockstun | On block / hit | Hit box |
|---|---|---|---|---|---|---|---|---|
| `atk_n` Twin Cut | 5 | 3 | 11 | 19 | 65 | 17 / 12 | −2 / +3 | x 1.8–5.8, y 5.5–9 |
| `atk_f` Cross Lunge | 10 | 4 | 18 | 32 | 110 | 24 / 17 | −5 / +2 | x 2.5–7.6, y 5–9 |
| `atk_d` Low Sweep | 9 | 4 | 22 | 35 | 75, knockdown | — / 15 | −11 / KD +44 | x 1.8–6.6, y 0–2 |
| `atk_air` Scissor Drop | 6 | 6 | to landing | 26 | 85 | 19 / 14 | by height | x 0.8–5.2, y −2.5–3.5 |

- **Twin Cut** (`atk_n`): a quick horizontal cut with the leading blade. It can be chained into
  itself once: the second press cuts with the other blade (the same animation works if the two
  cuts read alike from the side; F may ask for an `atk_n` second variant).
- **Cross Lunge** (`atk_f`): a lunge forward (1.8 m over frames 3–10) and both blades crossing
  in an X in front of the chest.
- **Low Sweep** (`atk_d`): the Hero's, quicker and shorter, with the leading blade.
- **Scissor Drop** (`atk_air`): both blades cut down in a scissor in front and below.

### Specials (B)

| Move | Startup | Active | Recovery | Total | Damage | Chip | Hitstun / blockstun | On block / hit |
|---|---|---|---|---|---|---|---|---|
| `sp_n` Void Step | — | — | 10 | 28 | — | — | — | — |
| `sp_f` Charge Slash | 13 | 4 | 24 | 41 | 120, knockdown | 24 | — / 15 | −13 / KD +45 |
| `sp_u` Rising Arc | 5 | 8 | 26 | 39 | 100, knockdown | 20 | — / 14 | −20 / KD +47 |
| `sp_d` Antimatter Slide | 5 | 17 | 18 | 40 | 90, knockdown | 18 | — / 14 | −21 (first frame) / KD +35 |

- **Void Step** (`sp_n`, new): a teleporting step. The mech sinks into a dark flicker (frames
  1–6), is gone on frames 7–18 (no hurt box, no push box: it passes through the other mech and
  through the wave) while its root moves 9 m forward, and reappears with 10 frames of recovery.
  No attack. Cancelled from a blocked Cross Lunge it keeps the pressure on (reappearing behind,
  or in front for a grab); in neutral it is the way past the Hero's wave. The extra mobility the
  rushdown mech gets instead of a dash.
- **Charge Slash** (`sp_f`): the Hero's, shorter (5 m) and quicker, with both blades.
- **Rising Arc** (`sp_u`): the Hero's, both blades sweeping up together; invulnerable on frames
  1–5; less damage.
- **Antimatter Slide** (`sp_d`, new): the mech drops into a slide along the floor, 7 m over
  frames 4–22, leading blade low (x 0.5–4.0, y 0–2.5, active the whole slide). Its hurt box is
  only 4 m tall during the slide, so it passes under the Hero's Guard Cut and Tip
  Thrust: the answer to a Hero sitting at the tip of its sword. Very punishable on block,
  less so if only its last frames touch.

### Grab and throw (Y): Vault Throw

As the Hero's grab (startup 5, the same reach), but the throw (40 frames) vaults: the
Double-blade Hero hooks the other's shoulders, swings it over its own head and slams it down
behind (the sides swap, the other ends about 5 m behind): 120 damage, knockdown. For putting
the other in the corner.

### Super (A + B): Antimatter Rend

The flash (frames 1–40, the blades crossed in front of the face, the violet glow flaring), then
the mech vanishes and reappears 12 m ahead mid-slash (startup 3 after the flash, root motion
12 m in one jump on frame 43), active 44–51 (x 0–6, y 2–10), recovery 36. Invulnerable from frame
1 to the first active frame. 320 damage, knockdown, chip 80; −24 on block. Available any time the meter is at
zero or above: the borrowing super.

## Beam (Raikō Chemical Group, chemical)

Raikō's base mech: the roster's zoner, the Tank's natural nemesis. A heavy, square mech built
round one weapon, the **Raikō Arc Cannon** in its right hand: a capacitor body on the fist and a
long barrel wound with copper coils, held like a pistol, level at chest height.
Two green reaction tanks stand on its back. It keeps the other mech out
with electric orbs and a long-range beam, answers jumps with a pillar of lightning and keeps
one quick jab for when something gets close. Slow on its feet, no lunges: once the other mech
is in, Beam has to block, jab and throw its way out. Its stance is upright and planted, legs
wide, the cannon pointed at the other mech.

Code name `Beam` (`enum Mech`); shown as BEAM MECH, model RC-03 (a proposed product name is in
the open questions). Built on the Hero's skeleton: the same part ids and joints
([For the animator](#for-the-animator-beam)).

### Movement and stats

| | Beam |
|---|---|
| Health | 1,000 |
| Walk forward | 0.062 m a frame (3.7 m/s): the slowest |
| Walk back | 0.058 m a frame (3.5 m/s) |
| Walk cycle | 52 frames, two steps (3.2 m forward) |
| Jump | 5 frames' crouch, then 40 in the air, 6.0 m high at the top (45 frames in all) |
| Diagonal jump | 0.14 m a frame across (5.6 m) |
| Landing | 6 frames (9 after an air attack) |
| Push box | 1.7 m either side of the root, 11.5 m tall (7.5 crouching) |

The walk is the heaviest of the three: a long plant on each step, the cannon kept level and
steady while the body dips under it (it is an instrument: it does not swing). The jump is
short and late off the ground.

### Attacks (A)

| Move | Startup | Active | Recovery | Total | Damage | Hitstun / blockstun | On block / hit | Hit box |
|---|---|---|---|---|---|---|---|---|
| `atk_n` Arc Jab | 6 | 3 | 15 | 24 | 65 | 19 / 14 | −4 / +1 | x 1.8–9.0, y 6–9 |
| `atk_f` Static Lance | 14 | 4 | 22 | 40 | 100 | 26 / 19 | −7 / 0 | x 3.5–10.0, y 6–8.5 |
| `atk_d` Ground Spark | 12 | 5 | 24 | 41 | 85, knockdown | — / 16 | −13 / KD +41 | x 1.5–7.5, y 0–2 |
| `atk_air` Down Arc | 9 | 6 | to landing | 32 | 90 | 20 / 15 | by height | x 0.5–5.5, y −3–3 (from the root, in the air) |

(The on-block and on-hit columns are measured by `tests/run.sh 17` with the stand-in timings and
boxes, against a standing Hero.)

- **Arc Jab** (`atk_n`): Beam's answer up close and the chain's start. The cannon is short-armed
  straight forward, muzzle first, a stab with a crackle at the muzzle (frames 1–5: the elbow
  draws back 20°, the cannon tilts up a little; 6–8: the arm punches out level, the muzzle at
  about 9 m; then it is pulled back to the guard by frame 20). Little body motion: the torso
  turns into it 10°. The hit box is the whole cannon, fist to muzzle (the owner's call,
  2026-10-13: the jab reaches as far as it looks). The arm is hurtable to about 4 m out from
  frame 7 until it is back, and the cannon to its muzzle on frames 6–14, so a jab thrown from
  too far can be hit on the barrel.
- **Static Lance** (`atk_f`): the footsie poke, shorter than the Hero's Tip Thrust. A half step
  (0.8 m over frames 4–13, the right foot sliding forward) and the cannon thrust out at full
  length, both arms (the left hand leaves the barrel and pushes the cannon's body), an arc
  jumping from the muzzle to the target: the hit box is the arc, not the barrel. Hold the
  thrust on 15–18, then a slow pull back (the last 12 frames). The arm is hurtable to 4.5 m out
  from the first active frame until 10 frames after the last.
- **Ground Spark** (`atk_d`): from a crouch, the muzzle is pushed down onto the floor ahead and
  discharges along it: a low knockdown. Frames 1–11: the knees bend, the cannon dips to point at
  the floor 4 m ahead; 12–16: contact, the body jolts with the recoil; then the long recovery
  rising from the crouch. Punishable on block or a miss.
- **Down Arc** (`atk_air`): in the air, the cannon pointed down and forward at 45°, a short
  discharge below and in front; the cannon stays pointed until landing. Once per jump.

### Specials (B)

| Move | Startup | Active | Recovery | Total | Damage | Chip | Hitstun / blockstun | On block / hit |
|---|---|---|---|---|---|---|---|---|
| `sp_n` Volt Orb (tap) | 18 | the orb | 26 | 45 | 70 | 14 | 20 / 16 | −11 / −7 at 6 m; safe far |
| `sp_n` Volt Orb (charged) | 18 + 20–49 held | the orb | 26 | 65–94 | 90 | 18 | 22 / 18 | |
| `sp_n` Volt Orb (full) | 18 + 50 held | the orb | 26 | 95 | 120, knockdown | 24 | — / 20 | |
| `sp_f` Arc Lance | 18 | 6 | 20 | 44 | 85, knockdown | 17 | — / 18 | −8 / KD +44 (at 7 m) |
| `sp_u` Thunder Pillar | 7 | 8 | 27 | 42 | 110, knockdown | 22 | — / 14 | −21 / KD +49 |
| `sp_d` Reaction Prime | — | — | 14 after the release | 44 | — | — | — | — |

- **Volt Orb** (`sp_n`): the projectile, and the charge attack. Frames 1–10: the left hand comes
  off the barrel, the cannon is levelled at chest height, the coils light from the grip to the
  muzzle, and the cannon is lowered to the hip. **Frame 11 is the charge frame** (the `charge` mark): while B is held, the move holds
  there, up to 50 frames, the muzzle glowing brighter; letting go (or 50 frames) carries on.
  Frames 12–18: recoil builds (the body leans in), the orb leaves on frame 19 (the `release`
  mark, frame 18 counted from 0), and the cannon kicks up 15° with the recoil; 26 frames to settle
  back to the guard. The orb is a ball of lightning in front of the chest: it starts 4.5 m ahead
  and flies at **mid height**, a box from y 4.8 to 6.6, so it hits a standing or crouching mech
  (8 m tall crouching), passes over the low middle of the Antimatter Slide (its animation is 4.6
  m tall while it slides, but its head trails 6 m behind and rises as it ends, so a slide through
  an orb is usually caught at the end) and under the top of the Hero's jump. Held under 20 frames it is a **tap** (0.24 m a frame, 1.4 m wide),
  20 to 49 frames a **charged** orb (0.30 m a frame, 1.8 m wide), 50 frames a **full** orb (0.36
  m a frame, 2.2 m wide, knockdown). It lasts 130 frames and vanishes at a wall. One orb at a
  time: B while Beam's orb is out does nothing.
  - **Against the Kinetic Wave** (decided here): two projectiles that meet both stop unless one
    is stronger. The wave is strength 2; a tap orb is 1 (it is cancelled and the wave goes on),
    a charged orb 2 (both go), a full orb 3 (the wave is cancelled and the orb goes on). So the
    Hero answers taps with the wave; Beam answers the wave by charging, which costs it time.
  - **The Parry catches an orb** like the wave (the orb vanishes, the Hero ripostes if Beam is
    close enough to reach). The Void Step passes through it (scenario 38).
- **Arc Lance** (`sp_f`): the long-range beam, and the chain's ender. No root motion: Beam plants,
  levels the cannon with both hands on frames 1–12 (anticipation: the body sinks 0.4 m, the
  coils charge), and the beam fires from the muzzle on frame 19: a straight bolt out to 15 m (a
  box from x 2.5 to 15, y 6 to 8), held for 6 frames, the body pushed back by the recoil, then
  20 frames of recovery with the barrel smoking. The arm and the muzzle are hurtable to 5.5 m
  out from the first active frame until 10 after. Knocks down. Too slow to use on reaction from
  close; it catches a mech walking or jumping in at mid range. The Antimatter Slide (4.6 m tall)
  passes under the beam; the Parry catches it.
- **Thunder Pillar** (`sp_u`): the anti-air. No jump: Beam points the cannon straight up in
  front of its head and a column of lightning goes up from just in front of it (x 0.5–5, y
  6–16) on frames 8–15. Frames 1–7: the cannon swings up from the guard (it passes the head on
  the far side: the cannon must clear the antenna), the knees bend; the body is invulnerable on
  frames 1–7, so it beats a jump-in started in time. 27 frames of recovery bringing the cannon
  back down. Knocks down. Punishable on block or a miss.
- **Reaction Prime** (`sp_d`): the chemical meter's prime, not an attack. Frames 1–12: Beam
  plants the cannon's butt against its hip, reaches back over its shoulder with the left hand
  and turns the valve between the tanks; 13–30: it holds still, braced, the tanks flaring (the
  exposed moment: any hit spoils it); **frame 31 (the `release` mark, 30 from 0) the reaction
  starts**: a jolt through the body, the tanks glow; 14 frames back to the guard. A
  reaction lasts 300 frames and fills half a bar ([The meters](#the-meters)). Down + B during a
  reaction does nothing.

### Grab and throw (Y): Shock Grip

As the Hero's grab (startup 5, the same reach and whiff). On a catch, `throw` (46 frames) on Beam
and `thrown` (46) on the other: Beam takes the other by the shoulder with its left hand, jams
the muzzle into its chest (frames 6–28: the other shakes in the current), and on frame 33 (the
`release` mark, 32 from 0) the shock throws it off backwards: 130 damage, the other lands about
9 m away and is knocked down. The break window is the throw's first 10 frames. For getting a
rushing mech back out to orb range.

### Super (A + B): Raikō Overload

The flash (frames 1–40: the world freezes, Beam alone moves: it plants its feet wide, both hands
on the cannon, the tanks and the coils flare and the head's antenna sparks), then startup 8
(the cannon levelled, the body braced back), and the beam: active frames 49–64, a bolt the
height of a mech across the hangar (x 2–30, y 4.5–9), then 36 frames of recovery (the recoil
skids Beam back a little, the barrel glowing). Invulnerable from frame 1 to frame 48. 300
damage, knockdown; chip 75 through a block (which can finish a round). −30 on block at 8 m, KD
+35 on hit. Very punishable when blocked close (the other recovers long before Beam does); from far it is safe. A full-screen
answer to a mech that is zoning back, or to a whiff anywhere.

### Chains

Beam's chain is the shared one: Arc Jab, then Static Lance, then a special. The Arc Lance and the
Volt Orb both combo from a Static Lance that hits; the Thunder Pillar does not reach a standing
mech pushed back by the lance; the Reaction Prime can be cancelled into (the other recovers
long before the release: a gamble).

### Reaction lengths (Beam)

As the shared table below, except: `walk_f`, `walk_b` 52; `jump` 45; `throw` and `thrown` (by
Beam's Shock Grip) 46. `win` (120): the cannon pointed up and fired once into the hangar's
roof, a shower of sparks. `intro` (90): walks out with the cannon on its shoulder, then lowers
it into the guard.

### For the animator (Beam)

- **The skeleton is the Hero's**: the same part ids and joint offsets
  (`models/beam/beam.rig.json`), so a Hero pose reads on Beam. The proportions differ only in the
  armour: Beam's chest and shoulder blocks are broader and squarer (the joints are where the
  Hero's are), its back carries two tanks and its head an antenna 1.3 m tall, raked back.
- **`weapon_r` is the Arc Cannon**, on the right hand's mount (the same mount as the Hero's
  sword), but held like a pistol: the grip runs up through the fist (the mount's +Y, the thumb
  side), the capacitor body sits on top of the fist and **the barrel runs along the mount's −Z**,
  the line of the forearm. So with the hand straight (`hand_r` near 0) the cannon points where
  the forearm points: a forearm held level aims it at the other mech; the guard holds the
  upper arm at the side and the forearm level (`upper_arm_r` 2°, `forearm_r` 86°). It is a gun,
  not a blade: aim it and let it recoil; keep it out of the floor (it reaches 4.8 m past the
  fist). **`weapon_l` is empty** (the left hand is a fist, raised in front of the chest in the
  guard).
- **The muzzle** is the effects' anchor: the point (0, 0.8, −4.4) in `weapon_r`'s frame. The orb,
  the beam, the pillar and the arcs start there (the fight's boxes are in fight-local metres; keep
  the muzzle near where the boxes say: about x 4.5, y 5.7 for the orb, so the cannon is lowered to
  the hip for the Volt Orb, and level at the chest, y 7, for the Arc Lance and the Static Lance).
- **Joint ranges** (degrees, the kit's X/Y/Z on each joint, as the rig file says): pelvis ±25 X,
  ±30 Y; torso −30..35 X, ±40 Y, ±15 Z; head ±35 X, ±45 Y; upper arms −60..170 X, −10..80 Z
  outward; forearms 0..140 X (the elbow bends one way); hands ±60 X, ±30 Z; thighs −50..100 X,
  ±25 Z; shins −140..0 X (the knee bends one way); feet ±45 X. The pauldrons follow the upper
  arms by about a third in X and half in Z, as the Hero's do. The flex pose
  (`beam_flex.asset.json`) bends every joint near these ends and passes the Asset Checker.
- **Marks** (anim.akr's `MARK_*`): `cancel` on atk_n frames 6–14 and atk_f 14–23 (from 0);
  `invuln` on sp_u 0–6 and the super 0–47; `flash` on the super's 0–39; `release` on sp_n 18
  (the orb), sp_d 30 (the reaction) and throw 32 (the shock); **`charge` (new) on sp_n 10**, the
  frame held while B is held; `step` on the walks' plants.
- **The guard** (`_body.anim.json`, the rig's `guard` pose) is the stance every stand-in holds.

## Tank (Heartland Atomic Company, nuclear)

The grappler. Heartland Atomic are the atomic era's veterans, keeping old reactors running with
salvage and patches; Tank is their base mech, available from the start. Short (10.2 m) and wide
(9.5 m across the fists), on two tread units instead of legs, with forearms bigger than the
Hero's thighs. It has the slowest walk and the worst jump of the roster, and makes up for them
with **super armour** on its three big attacks, a **command grab** that beats block and cannot
be broken, the longest grab range, and a **nuclear meter** that fills from the damage it takes,
in plain view of both players. Up close it beats the Double-blade Hero's rushdown (armour eats
the pokes; a mech that blocks gets clinched); at range it struggles against the Hero's wave and
Tip Thrust, and has to walk in through them. Its stance is hunched forward over the treads, head
up, both clamp fists low and out in front like a wrestler about to tie up.

"Tank" is the code identifier (`Mech.Tank`, `models/tank/`, `anims/tank/`). Its product name is
open (see the open questions at the end).

### Movement

| | Tank |
|---|---|
| Health | 1,150 |
| Walk forward | 0.055 m a frame (3.3 m/s) |
| Walk back | 0.045 m a frame (2.7 m/s) |
| Walk cycle | 32 frames, a loop with **no `step` marks**: the treads glide, nothing plants |
| Jump | 6 frames' crouch, then 34 in the air, 4.5 m high at the top (`jump` is 40 frames) |
| Diagonal jump | 0.13 m a frame across (4.4 m) |
| Landing | 7 frames (10 after an air attack) |
| Push box | 2.4 m either side of the root, 10 m tall (6.5 crouching) |
| Hurt box (standing) | the body 2.4 m either side, 10.2 m tall; the treads 2.7 m either side, 2.2 m tall |

**The glide.** Tank does not step: its walks slide the root at a constant speed while the
drive sprockets (`foot_r`, `foot_l`) turn, about 4° a frame forward in `walk_f` (the track's
speed over the sprocket's 0.78 m radius) and 3.3° a frame backward in `walk_b`. The body sways
very little, a slow 2° roll of the torso over the cycle and the fists bobbing a little out of
phase, so the motion reads as an engine idling under load rather than a gait. The treads stay
flat on the floor in every ground move. The fight plays no step sound for Tank; the game plays
a tread rumble while it glides (`tank_fx.akr`'s `tank_sfx`).

**The jump** is a heave: a 6-frame squat (the torso pitches forward 15°, the arms swing back),
a launch with both arms thrown up, the treads hanging level in the air, and a hard landing that
pitches the torso forward and rocks the treads nose-down 8°.

### Attacks (A)

| Move | Startup | Active | Recovery | Total | Damage | Hitstun / blockstun | On block / hit | Hit box |
|---|---|---|---|---|---|---|---|---|
| `atk_n` Rivet Jab | 8 | 3 | 14 | 25 | 80 | 18 / 13 | −4 / +1 | x 1.8–6.4, y 5–8.5 |
| `atk_f` Piston Haymaker | 16 | 4 | 22 | 42 | 150 | 26 / 18 | −8 / +0 | x 2.0–7.6, y 5–9 |
| `atk_d` Track Hook | 11 | 4 | 24 | 39 | 90, knockdown | — / 16 | −12 / KD | x 1.8–6.8, y 0–2 |
| `atk_air` Body Drop | 7 | to landing | landing 10 | 28 | 110 | 20 / 15 | by height | x −1.5–4.0, y −2.5–2.5 (from the root, in the air) |

- **Rivet Jab** (`atk_n`): the chain's start, a frame slower than the Hero's Guard Cut and
  shorter. The leading (right) fist snaps straight out at chest height from the guard and back;
  the shoulder drives it, the torso turns 10° into it. Cancel window frames 9–17 (the first
  active frame to six after the last). The arm is hurtable out to 4 m from the first active
  frame until 10 frames after the last.
- **Piston Haymaker** (`atk_f`): **super armour on frames 4–20** (from the wind-up to the last
  active frame). Anticipation: frames 1–12, the right arm cocks back past the hip, the torso
  turns 35° away and leans back, the left fist comes up to cover the face; the treads glide
  Tank 1.6 m forward over frames 5–14 (root motion, 0.16 m a frame), the sprockets spinning
  hard. Frames 13–16, the swing: the torso unwinds and the right fist travels in a wide hook to
  full extension at frame 17 (contact pose: arm straight, fist at 7 m, chest-high, the torso
  turned 30° into it, the left arm pulled back for balance). Recovery 22 frames: the arm swings
  through past the centre line and is hauled back to the guard, the torso settling over the
  treads. The heavy footsie tool: it walks through a poke (the armour) and lands. −8 on block,
  so a blocked one is punished by a neutral attack. Cancel window frames 17–26. Arm hurtable
  to 5 m.
- **Track Hook** (`atk_d`): from a crouch (the torso pitched 30° forward over the treads), a low
  hook of the right fist along the floor in front of the treads, knuckles dragging. Knocks
  down. Slow and very punishable when blocked or missed, like the Low Sweeps.
- **Body Drop** (`atk_air`): in the air, Tank pulls both fists in against the chest, tucks the
  head and drops its whole weight, the hull leading; the box sits under and in front of it and
  stays out until landing. Once per jump. Tank's jump is short and slow, so this is a
  read, not a habit: a Rising Arc or a Smokestack Uppercut takes it.

### Specials (B)

| Move | Startup | Active | Recovery | Total | Damage | Chip | Hitstun / blockstun | On block / hit |
|---|---|---|---|---|---|---|---|---|
| `sp_n` Reactor Vent | 12 | 5 | 26 | 43 | 100, knockdown | 20 | — / 16 | −15 / KD |
| `sp_f` Atomic Clinch (command grab) | 13 | 6 | 30 (whiff) | 49 + 56 slam | 180, knockdown | — | unblockable | — |
| `sp_u` Smokestack Uppercut | 9 | 6 | 28 | 43 | 120, knockdown | 24 | — / 14 | −20 / KD |
| `sp_d` Bulldozer | 12 | 16 | 20 | 48 | 90, knockdown | 18 | — / 14 | −22 (first frame) / KD |

- **Reactor Vent** (`sp_n`): **super armour on frames 1–17** (all its startup and the first
  active frame). Tank plants, both fists slam down to the floor either side of the treads
  (frames 1–11, the torso hunching 25° forward, the reactor's window flaring), and the reactor
  vents: a burst of superheated steam from the gaps all round the hull and the vessel on frames
  13–17. The hit box covers both sides (x −4.0–5.8, y 0–9.5), so it also catches a mech that
  crossed over. Recovery: the fists come up off the floor, steam trailing (frames 18–43).
  The answer to the Double-blade Hero's pressure: its Twin Cut or Cross Lunge lands on the
  armour and the vent knocks it down; a Void Step behind gets hit by the back half. A mech that
  waits it out punishes the 26-frame recovery.
- **Atomic Clinch** (`sp_f`, the command grab): Tank throws both arms wide (frames 1–4) and
  glides forward 4.5 m on the treads over frames 4–15 (root motion 0.375 m a frame, sprockets
  spinning flat out), the arms closing on frames 14–19: the catch box x 0.5–4.2, y 1–10 on
  frames 14–19. It catches what Y's grab catches (a mech standing, walking, crouching or
  blocking, not in block- or hitstun) **and a mech in an armour frame**; it misses a mech in the
  air, knocked down, getting up, invulnerable or in the startup of its own attack (strikes beat
  grabs). How it differs from Y's grab: it reaches about 8.7 m from where it starts against
  Y's 4 m, it is slower (13 frames to Y's 5, so it can be seen and jumped), it **cannot be
  broken**, and it does 180 to the throw's 150. A miss is a 30-frame stagger (frames 20–49:
  the arms close on nothing, Tank lurches forward over the treads and hauls itself upright),
  punishable by anything.
  On a catch the animation jumps to its **slam section** (frames 50–105, 56 frames, marked
  `riposte` on its first frame, as the Parry's riposte is): Tank hauls the other mech up by the
  shoulders, swings it overhead (frames 50–64, the other's root lifted 6.5 m off the floor
  over Tank's head, Tank's fists at the other's shoulders), holds it there a moment while the reactor
  flares (65–74), then slams it down in front (75–83) and lets go: `release` on frame 83 (the
  slam section's 34th frame), the damage and the slam's hitstop (12). It ends with Tank
  straightening up (84–105). The other
  plays `thrown_slam` (below) and lands knocked down, about 3.6 m in front.
- **Smokestack Uppercut** (`sp_u`, the anti-air): **super armour on frames 1–15** (startup and
  active). Tank stays planted (no root motion: it is too heavy to leave the floor) and drives
  the right fist up from the hip to straight overhead, the torso stretching up 15° back, the
  exhaust stacks belching (the box follows the fist, x 0.5–5.0, y 5–14). Where the Hero's Rising
  Arc beats a jump-in with invulnerability, this beats it with armour: the falling attack lands
  on the armour, then the uppercut hits. A jump without an attack, or one that lands late,
  beats it on recovery (−20 on block, 28 frames of the fist coming down).
- **Bulldozer** (`sp_d`): Tank drops its shoulder and charges low along the floor on the
  treads, 8 m over frames 10–27 (root motion 0.444 m a frame), the hull and both forearms
  forward in a ram (box x 0.5–4.0, y 0–5, active frames 13–28). Startup is the wind-up: the
  torso pitches forward 35°, the fists come together in front of the hull, the sprockets spin
  up (frames 1–9). **No armour**: it is Tank's only way to cover ground fast, and it is very
  punishable on block (−22 at the first frame, less if only its last frames touch) and goes
  under nothing: a wave or a Tip Thrust stops it. Recovery 20: Tank skids, the treads rocking
  nose-down 10°, and straightens.

### Grab and throw (Y): Scrap Heave

`grab`: startup 5, active 2 (the catch box x 1.0–4.0, y 2–10: Tank's arms are long), 7 frames;
a miss plays `grab_whiff` (22 frames). Breakable as every Y grab (Y within 10 frames). On a
catch: `throw` (44 frames) on Tank and `thrown` (44, the Hero's throw's victim move) on the
other: Tank clamps both fists on the other's shoulders (frames 1–10, the break window), lifts
it to 4 m (11–24, the other's root rising 0.3 m a frame), heaves it back over its right
shoulder and then hurls it forward with both arms on frame 30 (`release`): 150 damage,
knockdown, the other flying about 10 m. The fight places the other at Tank's fists (3.8 m in
front while held), so `thrown` from the Hero's throw reads right; the Hero lifts higher, Tank
holds lower and closer.

### Super (A + B): Chain Reaction

A command-grab super. The flash (frames 1–40: the world freezes, Tank alone moves: it plants,
both arms spread wide, the reactor's window and the vent slot glare white-green and the stacks
belch). Then the treads glide 6 m forward in 8 frames (41–48, 0.75 m a frame) and the arms
close: the catch box x 0.5–4.5, y 0–11, on frames 47–54. Invulnerable from frame 1 to 46. It
catches everything the Atomic Clinch does and also **a mech in hitstun or blockstun** on the
ground, so it ends a chain (A, forward A, super) and punishes a blocked string; it misses a mech
in the air or knocked down. A miss: 40 frames of recovery (55–94), the arms crashing together
on nothing and Tank skidding to a stop. On a catch the animation jumps to its slam section
(frames 95–150, 56 frames, `riposte` on 95, the same timing as the Clinch's so the victim's
`thrown_slam` serves both): lift overhead, the reactor going critical (the hold at 110–119 is
where the flare peaks), the slam on frame 128 (`release`, the section's 34th frame): 360 damage (scaled in a chain like
any hit), knockdown, the super's hitstop (20). Unblockable; no chip, since it is a grab. Grabs
are not parried, so neither is this.

### Super armour (`MARK_ARMOUR`)

- **What it absorbs.** A strike (a normal, a special, an air attack) or a wave that touches
  Tank on a frame marked `armour` lands, but does not interrupt: Tank takes the hit's damage,
  in full (an absorbed hit is not part of a combo, so it is not scaled), the nuclear meter
  fills from it, and both mechs freeze for the hit's hitstop (8, 11 or 14 frames) while Tank
  flashes. There is no hitstun, no knockback and no knockdown; Tank's move carries on from the
  same frame.
- **How many.** Every hit while the marks last. The attacker's hit is spent (that hit box does
  not hit again) and it does **not** count as contact for the attacker's chain, so a chain
  cannot follow it: in practice one strike, or a strike and a wave.
- **The attacker.** Gets the meter of a blocked hit (kinetic +5 %), not of a landed one.
- **What breaks it.** Grabs: Y grabs and command grabs catch a mech on an armour frame even
  though it is in the middle of a move (a mech's own attack's startup otherwise beats a grab).
  Supers: a super's hit is never absorbed and lands as usual. A hit that takes Tank's health to
  zero knocks it out as usual. Armour never applies in the air (no air move has it).
- **The Parry** still parries an armoured attack (the armour is Tank's defence, not its
  attack's).
- The fight reports an absorbed hit as the event `Armour` (side: the attacker, at the contact,
  the hit's power), for a clank and a spark instead of the hit's.

### The nuclear meter

Fills by **taking damage**: 3 meter for every point of damage Tank takes, so a bar takes
400 damage (about 35 % of its health, about four clean hits or a combo and a throw). Everything
that costs health counts: hits, chip, absorbed hits, throws. Nothing else fills it: not
landing hits, not blocking (a blocked normal does no damage), not time. It **carries over
between rounds**, so a lost round leaves Tank with a bar or most of one for the next: the
comeback the pitch asks for. The super costs the whole bar.

**Shown to both players.** The HUD's gauge on Tank's side is the reactor: a green fill that
heats toward white as it climbs, with a slow pulse from half a bar and hazard hatching across it
once full, and "SUPER" beside it like the others'. On the mech itself the reactor's window and
the chest vent glow brighter with the meter (drawn by `tank_fx.akr`), so the opponent sees the
threat on the fighter, not only in the corner of the screen. `MeterFull` is the usual event.

### `thrown_slam`: the Atomic Clinch's and Chain Reaction's victim (every mech)

A new victim move, added to the end of `Mv` (so the numbering of the rest stays), animated for
**every** mech (the Hero, the Double-blade Hero and Tank itself, for the mirror match): 56
frames. The fight places the root (Tank's fists are at the victim's shoulders throughout):

| Frames | The victim |
|---|---|
| 1–14 | hauled up by the shoulders: the root rises from the floor to 6.5 m, moving from 3.0 m in front of Tank to 0.8 m in front (over its head); the victim's legs dangle and kick, its arms flail at Tank's wrists |
| 15–24 | held overhead, horizontal, face up (its body pitched back 90°), struggling |
| 25–34 | slammed down in front: the root comes down to the floor 3.6 m in front of Tank, the body rotating back to land flat on its back on frame 34 (the slam, `release` on Tank's side) |
| 35–56 | flat on its back, a bounce on 36–40, then still: the fight takes it into `knockdown` from here |

### Reactions and the rest

As the list below, with Tank's lengths: `idle` 60 (the engine idling: a slow rise and fall of
the shoulders, the reactor's window breathing), `walk_f` and `walk_b` 32 (the glide), `crouch`
8 (the torso pitches 30° forward and the fists drop to the floor: the treads cannot crouch),
`jump` 40, `land` 10, `block` 4 (both forearms crossed in front of the head and chest, the
cooling packs outward: Tank blocks with its arms), `hit_high` and `hit_low` 20, `hit_air` 30,
`knockdown` 32 (it topples backwards off its treads onto its back, the treads in the air),
`getup` 24 (it rocks forward and drops back onto the treads with a thud), `ko` 90 (the reactor
gutters, it topples back and the glow goes out), `win` 120 (both fists raised, the stacks
belching, then a thumbs-up), `intro` 90 (it rolls out of the booth's spot lights into the
stance), `grab_whiff` 22, `grab_break` 20, `thrown` 44 and `thrown_vault` 40 (Tank as the
victim: dead weight, the treads hanging), `thrown_slam` 56.

### For the animator (Tank's rig)

- **The parts are the shared skeleton with Tank's meanings** (`models/tank/tank.rig.json`; each
  part's `role` and `range` are written there): `pelvis` the lower hull and hip axle; `torso`
  the chest, the reactor vessel and the stacks; `head` the cab head; `pauldron_*` the shoulder
  domes (follow the upper arm part way: about 0.35 of its x and 0.5 of its z, as the Hero's);
  `upper_arm_*`, `forearm_*`, `hand_*` the arms and clamp fists; `thigh_*` the suspension
  struts; `shin_*` the tread units (the joint is the suspension pivot at the top); `foot_*` the
  drive sprockets at the back of the treads. `weapon_r` and `weapon_l` are empty mounts at the
  middle of each fist: where a held mech's shoulders go.
- **No knees.** The treads stay flat on the floor in every ground move: don't drop the pelvis
  (the guard pose's `drop` is 0) and keep `shin` pitches within ±14° (a rock fore and aft, the
  nose lifting on a lunge, dipping on a stop). Weight and anticipation go into the torso
  (pitch −40° to +25°, turn ±60°) and the arms.
- **Spin the sprockets** (`foot_*` about X) for every glide: about 4° a frame in `walk_f`,
  −3.3° in `walk_b`, 30° a frame in the Atomic Clinch and the Bulldozer, 55° in Chain
  Reaction's dash. Keys every 8 frames or so keep the spin readable (a key per 90° at most).
- **The fists are big**: about 1.4 m across. The guard holds them at chest height out to about
  5.4 m; keep the active frames' fists inside the hit boxes above, and the pull-back clear of
  the pauldrons (a forearm folded past 120° meets the upper arm's ram).
- **Armour frames** read in the pose: plant, brace, the shoulders squared, the torso low. The
  fight flashes Tank when a hit is absorbed; the animation needn't flinch.
- **Marks:** `cancel` on `atk_n` (9–17) and `atk_f` (17–26); `armour` on `atk_f` (4–20), `sp_n`
  (1–17), `sp_u` (1–15); `riposte` on the first frame of the slam sections (`sp_f` 50, `super`
  95); `release` on the slams (`sp_f` 83, `super` 128) and on `throw` 30; `invuln` on `super`
  1–46; `flash` on `super` 1–40. No `step` marks anywhere (frame numbers here count from 1, as
  the tables do; the animation files count from 0).
- **The throws place the victim**: Tank's fists should meet the victim where the fight puts its
  root (the tables above); the victim moves (`thrown`, `thrown_vault`, `thrown_slam`) follow
  the thrower's hands.
- Tank is 10.2 m tall and 9.5 m wide in its guard; the depth buffer sorts the two mechs, but a
  grab's arms should pass in front of the other mech's chest (−z) rather than through it.

## The Twins (Binary Mechanica, fusion)

Binary Mechanica's base mech, and its founding idea: two small mechs that fight side by side
and lock together into one. **Split**, the player steers twin A and twin B follows a few frames
behind, copying it (the Ice Climbers' way): every button comes out twice, a beat apart, so the
twins press hard and are safe on block, but each hit is light and the **fusion meter does not
fill**. **Combined**, the two are one mid-weight brawler with full-weight hits, the meter fills
and the super is there. **L switches** between the two, a move each way. Unlocked by clearing
the arcade with each base mech ([roster.akr](roster.akr)).

"Twins" is the code identifier: `Mech.Twins` is the combined form and the mech the player picks
(the fighter's `mech` all match long); `Mech.TwinA` and `Mech.TwinB` are the split form's two
bodies, for the animations and the drawing only (never in the roster, never a fighter's `mech`).
The fighter's `body` says which one is drawn and timed: `Twins` combined, `TwinA` split (twin
B is the partner, a second body of the same fighter). All three are on the shared skeleton
(`enum Part`), from `models/twins/make_twins.py`. Twin A's accent is cyan, twin B's the model's
second accent; names for the two are an open question at the end.

### The two forms

| | Split (each twin) | Combined |
|---|---|---|
| Health | 1,000: one bar for the fighter, whichever body is hit | (the same bar) |
| Height | about 7.2 m | about 12 m |
| Walk forward | 0.100 m a frame (6.0 m/s): the quickest | 0.080 m a frame (4.8 m/s) |
| Walk back | 0.080 m a frame (4.8 m/s) | 0.065 m a frame (3.9 m/s) |
| Walk cycle | 32 frames, two quick steps (3.2 m) | 44 frames, two steps (3.5 m) |
| Jump | 3 frames' crouch, then 34 in the air, 6.0 m high (`jump` 37) | 4 frames, then 38 in the air, 6.0 m high (`jump` 42) |
| Diagonal jump | 0.20 m a frame across (6.8 m) | 0.17 m a frame (6.5 m) |
| Landing | 4 frames (6 after an air attack) | 5 frames (8 after an air attack) |
| Push box | 1.1 m either side of the root, 7.0 m tall (4.8 crouching) | 1.6 m, 11.5 m tall (7.5 crouching) |
| Hurt box (standing) | 1.2 m either side, 7.4 m tall (5.0 crouching) | 1.8 m either side, 12 m tall (8 crouching) |
| Meter | does not fill | fills (below) |
| Super | none | Fusion Burst |

The twins are light: a quick, bouncing walk with short steps (`step` marks on the plants), a
springy jump, the arms held high and close like a boxer's. Twin A and twin B move the same way
(the same move set, the same timing): one is the other's echo a beat late. The combined form
is heavier and squarer, a boxer's stance, both fists up at the chin, the waist coupling glowing.

### Split: attacks (A), each twin

The numbers are one twin's. The partner's copy lands six frames after the leader's, as a
second hit (a combo: the second does 80 %). A knockdown lands once: the partner's copy misses a
mech already falling (knocked down, a mech can't be hit).

| Move | Startup | Active | Recovery | Total | Damage | Hitstun / blockstun | Hit box |
|---|---|---|---|---|---|---|---|
| `atk_n` Bit Jab | 4 | 2 | 10 | 16 | 50 | 15 / 11 | x 1.0–4.4, y 3.8–6.2 |
| `atk_f` Byte Kick | 9 | 3 | 15 | 27 | 76 | 22 / 16 | x 1.2–5.8, y 2.4–4.8 |
| `atk_d` Low Bit | 7 | 3 | 18 | 28 | 68, knockdown | — / 14 | x 1.0–5.0, y 0–1.6 |
| `atk_air` Drop Kick | 5 | to landing | landing 6 | 24 | 60 | 16 / 12 | x 0.3–3.8, y −2.0–1.8 (from the root, in the air) |

- **Bit Jab** (`atk_n`): a straight jab with the leading fist at head height of a crouching
  big mech, and back. Frames 1–4 the shoulder turns in; 5–6 the arm is straight; 7–16 it comes
  back to the guard. The pair is two jabs, rat-tat. The chain's start (cancel window frames 5–12).
  The arm is hurtable to 2.5 m out from the first active frame until 10 frames after the last.
- **Byte Kick** (`atk_f`): a hop forward (1.0 m over frames 3–10) into a straight front kick at
  the other's thigh. The twin leans back from the hips, the kicking leg chambered on 6–9 and
  snapped out on 10–12. Cancel window frames 10–18. The leg is hurtable to 3.5 m out.
- **Low Bit** (`atk_d`): from a crouch, a low spinning sweep with the leading leg along the
  floor, the hands on the floor. Knocks down. Punishable on block or a miss.
- **Drop Kick** (`atk_air`): in the air, both feet out ahead and down, the body laid back. Out
  until landing; once a jump.

### Split: specials (B), each twin

| Move | Startup | Active | Recovery | Total | Damage | Chip | Hitstun / blockstun |
|---|---|---|---|---|---|---|---|
| `sp_n` Pulse Spin | 8 | 10 | 16 | 34 | 56 | 11 | 18 / 14 |
| `sp_f` Dash Kick | 10 | 4 | 18 | 32 | 100, knockdown | 20 | — / 14 |
| `sp_u` Rising Kick | 4 | 8 | 22 | 34 | 88, knockdown | 18 | — / 12 |
| `sp_d` Low Roll | — | — | 8 | 28 | — | — | — |

- **Pulse Spin** (`sp_n`): the twin plants and spins on the spot, arms straight out, a ring of
  cyan light round its waist: the box covers both sides (x −3.2–3.2, y 1.5–6.0) on frames 9–18,
  so it hits a mech that jumped over. Two turns in the active frames; 16 frames of wobbling
  back to the guard. The pair's spins overlap into one long spinning wall: a way to stop a
  rush on both sides. No knockdown.
- **Dash Kick** (`sp_f`): a low skating dash, 5.5 m over frames 3–12, into a flying side kick
  on frames 11–14 (x 0.8–4.6, y 2.0–5.5). Knocks down: the chain's ender, and the leader's
  usually lands alone (the partner's arrives at a mech already falling). Punishable on block.
- **Rising Kick** (`sp_u`): the anti-air. A crouch on frames 1–4 and a spring straight up, one
  leg kicking up over the head (the box x 0.3–3.6, y 2.0–8.0 from the root, which rises 4.5 m
  over the active frames 5–12), then the fall. **Invulnerable on frames 1–5.** Knocks down.
- **Low Roll** (`sp_d`): a forward roll along the floor, 6 m over frames 3–20, curled up: the
  hurt box only 3.0 m tall (it rolls under the Hero's Guard Cut and Tip Thrust, Beam's orb and
  Arc Lance, and the Double-blade Hero's Cross Lunge), no hit box. It stops at the other
  mech's push box (it doesn't pass through). 8 frames to stand up. The way in.

### Split: grab and throw (Y): Tag Toss

Only the leader grabs: the partner never copies Y. `grab` startup 4, active 2 (x 0.8–3.2,
y 1–7), 6 frames; a miss plays `grab_whiff` (18 frames). On a catch, `throw` (36 frames) on twin
A and `thrown` on the other: twin A grabs the other mech's wrist and waist (frames 1–10, the
break window), turns its hips and swings it overhead (11–23: the fight lifts the other's root to
2 m, 2.6 m in front), and slings it forward on frame 24 (`release`): 120 damage, knockdown, the
other flying about 8 m. Twin B carries on following meanwhile.

### Combined: attacks (A)

| Move | Startup | Active | Recovery | Total | Damage | Hitstun / blockstun | Hit box |
|---|---|---|---|---|---|---|---|
| `atk_n` Coupler Jab | 6 | 3 | 14 | 23 | 75 | 18 / 13 | x 1.8–6.6, y 6.0–9.0 |
| `atk_f` Fusion Straight | 12 | 4 | 20 | 36 | 125 | 26 / 18 | x 2.5–8.4, y 6.0–8.5 |
| `atk_d` Sweep Kick | 10 | 4 | 23 | 37 | 90, knockdown | — / 16 | x 1.8–7.4, y 0–2 |
| `atk_air` Hammer Drop | 7 | to landing | landing 8 | 30 | 100 | 20 / 15 | x 0.5–5.5, y −2.0–3.5 (from the root, in the air) |

- **Coupler Jab** (`atk_n`): a quick lead-hand jab at chest height from the chin guard, the
  shoulder plate rolling in; the chain's start (cancel window frames 7–15). Arm hurtable to
  3.5 m.
- **Fusion Straight** (`atk_f`): a step in (1.0 m over frames 4–12) and a full straight with
  the rear fist, hips and shoulders turned through, the waist coupling flaring on contact.
  Cancel window frames 13–22. Arm hurtable to 5 m.
- **Sweep Kick** (`atk_d`): drops to one knee and sweeps the far leg round along the floor.
  Knocks down; punishable on block.
- **Hammer Drop** (`atk_air`): both fists clasped overhead and brought down in front as it
  falls; out until landing; once a jump.

### Combined: specials (B)

| Move | Startup | Active | Recovery | Total | Damage | Chip | Hitstun / blockstun |
|---|---|---|---|---|---|---|---|
| `sp_n` Binary Lariat | 10 | 10 | 22 | 42 | 100, knockdown | 20 | — / 16 |
| `sp_f` Coupling Rush | 14 | 4 | 24 | 42 | 130, knockdown | 26 | — / 16 |
| `sp_u` Twin Drill | 5 | 8 | 27 | 40 | 120, knockdown | 24 | — / 14 |
| `sp_d` Fusion Focus | — | — | 12 | 20 + held | — | — | — |

- **Binary Lariat** (`sp_n`): both arms straight out, the combined form spins once on its
  heel, drifting 1.5 m forward over the active frames 11–20; the box covers both sides (x
  −5.0–5.0, y 4.0–9.0), so it catches a mech that crossed over. The big body's answer to
  pressure up close; a mech that waits out the spin punishes the 22 frames of recovery.
- **Coupling Rush** (`sp_f`): a shoulder-first charge, 5 m over frames 4–13, into a rising
  elbow (x 1.0–6.5, y 4.0–9.0) on 15–18. Knocks down; the chain's ender and the gap closer.
- **Twin Drill** (`sp_u`): the anti-air. A spinning uppercut that drills straight up, the root
  rising 4.5 m over the active frames 6–13 (the box x 0.5–5.0, y 4.0–13.0 from the root), then
  the fall. **Invulnerable on frames 1–6.** Knocks down. Very punishable on a miss.
- **Fusion Focus** (`sp_d`): the meter's charge, not an attack. Frames 1–7: the combined form
  plants its feet, fists together in front of the waist coupling. **Frame 8 is the charge
  frame** (the `charge` mark, as Beam's Volt Orb): while B is held the move holds there, up to
  50 frames, filling the fusion meter +6 a frame (a quarter bar at most); letting go (or 50
  frames) carries on into 12 frames back to the guard. Fully exposed the whole time: a read
  for a knockdown or a far-away opponent.

### Combined: grab and throw (Y): Binary Buster

`grab` startup 5, active 2 (x 1.0–3.8, y 2–10), 7 frames; `grab_whiff` 22. On a catch, `throw`
(44 frames) and `thrown` (44): both hands on the other's shoulders (frames 1–10, the break
window), lifted overhead (11–29, the root lifted to 3 m, 3.4 m in front) and thrown forward on
frame 30 (`release`): 140 damage, knockdown, about 9 m.

### Combined: super (A + B): Fusion Burst

Only combined, a bar. The flash (frames 1–40: the world freezes, the combined form alone
moves: it plants, crosses its forearms in front of the face, and both twins' accent colours
race along the seams to the core, which flares white), then a dash, 12 m over frames 41–47
(root motion), into a two-fisted hammer blow, active frames 47–56 (x 0–7.5, y 2.0–10.5), and
38 frames of recovery (it skids to a stop and the plates vent). Invulnerable from frame 1 to 46.
330 damage, knockdown; chip 80 through a block (which can finish a round); about −28 on block.

### Switching forms: L

L is a move each way. It is accepted when the fighter can act (on the ground: idle, walking,
crouching, or blocking outside blockstun), buffered 8 frames like the other buttons; split, the
partner must be free too (on the ground and not in a reaction or a move), else L does nothing.
Both moves are appended to `enum Mv`: `combine` and `split`.

**`combine`** (split, 36 frames; twin A and twin B each play it, then the combined form):

| Frames | Twin A (the leader) | Twin B (the partner) |
|---|---|---|
| 1–12 | crouches, arms up, looking back for its twin | runs to twin A: **the fight slides its root** from where it is to twin A's root, evenly over these frames |
| 13–23 | springs up (its pelvis rises about 5 m over its root, which stays on the floor), its legs fold up against its back; lands on twin B's shoulders on 23 | under twin A, it crouches and folds: arms in along the thighs, head tucked down into the chest: it becomes the legs |
| **24** | **the flash** (`release`): the bodies swap. The twins are hidden, the combined form drawn from here, on the twins' root | |
| 24–36 | the combined form, from the docked crouch: stands up into its guard, the combined-only plates (the waist coupling, the shoulder and back plates) sliding out, the seams flaring | |

Vulnerable on frames 1–23: a hit on either twin stops it (that twin plays its reaction, the
other stands back up into its guard). **Invulnerable on 24–30** (the flash). Actionable after 36.
So the end of twin A's and twin B's `combine` (frame 23) must be the pose the combined form's
`combine` starts in (its frame 24, the same frame), and the combined form's last frame is its
guard.

**`split`** (combined, 30 frames; the combined form plays it, then the twins):

| Frames | The combined form | Twin A | Twin B |
|---|---|---|---|
| 1–12 | crouches, the combined-only plates fold in, the seams flare | | |
| **13** | **the flash** (`release`): the bodies swap. From here the twins are drawn | docked on top of twin B, as in `combine`'s frame 23 | folded as the legs |
| 13–30 | | springs up off twin B's shoulders and lands in front on frame 22 at the root's spot (its root stays put), into its guard | unfolds and stands, then hops back 1.5 m: **the fight moves its root** to its spot behind twin A over frames 13–24 |

Vulnerable on frames 1–12 (a hit there stops it: it stays combined). **Invulnerable on 13–18.**
Actionable after 30.

The rounds start split (the twins walk out of the booth as two, twin B 1.5 m behind twin A).
The form is kept through the round and resets to split at the start of the next.

### The partner (twin B)

- **Delay.** Twin B plays the leader's pad **6 frames late**: the directions, A, B, X and R.
  Never Y (the leader's grab), L or A + B. Directions are copied as forward and back (relative
  to the facing), so a twin on the far side still attacks the right way. The delay counts
  frames of play: the hitstop and the super's freeze do not eat into it.
- **Its spot** is 1.5 m behind twin A (close enough that its copy of a jab still reaches a mech
  twin A is touching). When twin B can act and the copied stick holds no
  direction, it walks back to its spot if it is more than 1 m away; more than 4 m away, it
  walks to its spot whatever the stick says (it still copies the buttons).
- **Leash.** Never more than 8 m from twin A (a hard stop, like the separation limit), never
  more than 36 m from the other mech, and inside the walls.
- **Push boxes.** The twins pass through each other. Twin B's push box keeps it out of the
  other mech, but it **never moves the other mech**: on the ground twin B is moved out of the
  way, to its own side. The other mech pushes and is pushed by twin A only.
- **Depth.** Twin B is drawn 1.2 m behind the fight plane (further from the camera), so
  where the two twins overlap they read as two, side by side.
- **Its hits** are the fighter's (events, chains, combo scaling). Each hit box hits one body
  of the other side, the first it touches, and the other mech's whole hit hits **one twin**:
  the leader if it touches both.
- **Being hit.** Twin B has its own hurt boxes and its own reactions (hitstun, blockstun,
  knockdown, getting up); the damage comes off the fighter's one bar. In a reaction it ignores
  the copied pad (presses then are lost) and picks up the copy when it is free again.
- **Thrown.** Either twin can be grabbed (the leader if both are in reach) and thrown, slammed
  by Tank's command grabs, or vaulted. The player's Y breaks a grab on either twin. The other
  twin carries on (the thrower can't be hit while it throws, as always).
- **Knocked away**, twin B flies, lands, gets up and walks back to its spot.
- **KO.** One bar: when it is empty, both twins fall (`ko`), whichever took the last hit.
  There is no separate KO of the partner.
- **The camera** frames all three bodies.

### The fusion meter

Fills **only while combined**: +2 a frame (a bar in 10 seconds of being combined), +60 (5 %)
for each combined hit that lands, and Fusion Focus +6 a frame held (a quarter bar at most).
**Nothing while split**: not by time, not by hits. It does not drain while split either, and
it carries over between rounds. The super, Fusion Burst, costs a bar and exists only combined;
split with a full bar, the HUD shows the bar dimmed with "L COMBINE" beside it.

The HUD's gauge (`twins_fx.akr`) is a bright cyan fill with a white leading edge and two
shimmer bands running along it (one cyan, one twin B's colour: the two reactors meeting),
quickening as it fills, "SUPER" and a white pulse when full; while split it greys to a dim
silver, with no shimmer.

### Balance intent

Combined is the reward form: full-weight hits, a meter that fills and the super. Split is the
form of pressure and position: every button twice, a beat apart, a quick walk, the roll and
the spin; on block the partner's late copy extends the blockstun, so a split string is safe
where the combined form's is not; but each twin's hit is light, a knockdown lands only once,
and the meter stands still. Switching is a commitment (36 frames in, 30 out, vulnerable before
the flash), so the right moments are the safe ones: after a knockdown, far away behind a jump,
or split to press after the combined form's chain ender knocked the other down. A player who
never switches is choosing between no meter and no pressure.

### Frame advantage (measured)

From the fight itself (`tests/run.sh 17`, the stand-in timings, against a standing Hero, one
body alone: the partner's late copy is not counted, so a split string is safer than this):
combined Coupler Jab −4 on block / +1 on hit, Fusion Straight −6 / +2, Sweep Kick −11, Binary
Lariat −16, Coupling Rush −12, Twin Drill −21, Fusion Burst −28; twin A's Bit Jab −1 / +3,
Byte Kick −2 / +4, Low Bit −7, Pulse Spin −12 / −8, Dash Kick −8, Rising Kick −24.

### Chains

The shared chain in both forms: neutral attack, forward attack, a special (or, combined, the
super). Split, each twin cancels on its own contact, so the partner follows the leader's chain
whenever its own copies connect.

### Reactions and the rest (the Twins)

As the shared list below, with these lengths: split `walk_f` and `walk_b` 32, `jump` 37,
`land` 6, `grab` 6, `grab_whiff` 18, `throw` 36; combined `walk_f`, `walk_b` 44, `jump` 42.
Every one of the three bodies has the whole list, `thrown`, `thrown_vault` and `thrown_slam`
included (a twin can be thrown). `super` is the combined form's only; the twins' `super` is never
played (the stand-in is fine). `intro` (90): split, the two twins walk out of the booth side by
side, twin B half a step behind, and bump fists; `win` (120): split, they high-five and land
back to back; combined, it raises one fist, the seams flaring; `ko` (90): each body falls on
its own.

### For the animators (the Twins)

- **Three rigs on the shared skeleton** (`models/twins/twins.rig.json`,
  `models/twin_a/twin_a.rig.json`, `models/twin_b/twin_b.rig.json`), the same part ids. Twin A
  is the combined form's upper body (head, torso, arms; its legs fold up against its back),
  twin B its lower body (pelvis, legs; its torso and arms fold into the hips and thighs). The
  model agent writes where each sits inside the combined rig.
- **The swap.** `combine`'s frame 24 and `split`'s frame 13 (0-based 23 and 12: the `release`
  mark) is the frame the drawing changes body. The twins' `combine` ends (frame 23) in the
  docked pose: twin A's pelvis about where the combined torso joint is, twin B folded where the
  combined pelvis and legs are, both on the same root; the combined form's `combine` holds that
  docked crouch until frame 24 and stands from there. The combined form's `split` reaches the
  same docked crouch on frame 12; the twins' `split` starts docked on frame 13. Frames a body is
  not drawn on (the twins after the swap in `combine`, the combined form before it; the reverse
  in `split`) can hold any pose: hold the docked one.
- **Root motion.** None in `combine` and `split`: the fight places twin B's root (sliding it
  in, then back out to its spot). Keep twin A's root still; its leap is the pelvis rising.
- **Marks** (frames from 0, as the files count): `combine`: `release` 23, `invuln` 23–29;
  `split`: `release` 12, `invuln` 12–17. Split: `cancel` on `atk_n` 4–11 and `atk_f` 9–17;
  `invuln` on `sp_u` 0–4. Combined: `cancel` on `atk_n` 6–14 and `atk_f` 12–21; `invuln` on
  `sp_u` 0–5 and `super` 0–45; `flash` on `super` 0–39; `charge` on `sp_d` 7; `release` on the
  `throw`s (split 23, combined 29). `step` on the walks' plants. The rest as the shared list.
- **Twin B plays the same moves as twin A** (its own file each: `anims/twin_a/`,
  `anims/twin_b/`), with its own accent; the timing must match, frame for frame, since the fight
  times both twins from the same numbers.
- **Each twin is 7.2 m tall:** keep the boxes in the tables above (the hurt box 7.4 m tall, the
  jab at y 3.8–6.2, a crouching big mech's head height). The partner is drawn 1.2 m further
  from the camera: nothing to do in the animation.

## Shadow (Umbral Research, antimatter)

Umbral Research's base mech, the roster's trickster: it plants things, makes the other mech
respect them, and punishes impatience. It controls the floor with the **Rift Mine**, makes an
approach cost something with the slow **Hex Bolt**, steals the other mech's meter with the
bolt's **Siphon** curse, and punishes from far with **Shadow Sneak**. Block still stops every
attack from either side (no high or low, no cross-ups), so its tricks come from timing, grabs,
space and the meter, never from appearing behind a mech that is blocking. In exchange it has
the lowest health in the game, light hits and few combos. Its stance is tall and leaning
forward, both claws held low and wide like a mantis, the talons nearly touching the floor in
front of it; the single violet eye looks over them.

Code name `Shadow` (`enum Mech`, index 7, appended after `TwinB`); shown as SHADOW, model UR-01.
On the shared skeleton (`enum Part`); the claws are the weapon parts
([For the animators](#for-the-animators-shadow)). Its power source is Umbral's antimatter, the
Double-blade Hero's: the super is there at zero or above, debt down to one bar, 25 % more
damage taken in debt.

### Movement and stats

| | Shadow |
|---|---|
| Health | 900: the lowest |
| Walk forward | 0.085 m a frame (5.1 m/s): between the Hero's and the Double-blade Hero's |
| Walk back | 0.068 m a frame (4.1 m/s) |
| Walk cycle | 44 frames, two steps (3.7 m forward) |
| Jump | 4 frames' crouch, then 36 in the air, 6.2 m high at the top (`jump` is 40 frames) |
| Diagonal jump | 0.17 m a frame across (6.1 m) |
| Landing | 5 frames (8 after an air attack) |
| Push box | 1.4 m either side of the root, 11.5 m tall (7.5 crouching): the thinnest |
| Hurt box (standing) | 1.6 m either side, 12.5 m tall (8 crouching) |

The walk is a long, gliding stride: the knees stay bent, the body barely rises and falls, the
claws trail low and sway a little out of phase with the steps (a `step` mark on each plant, but
a light one). The jump is a crouch deep onto the claws and a spring; the cape plates lift at the
top and settle on landing.

### Attacks (A)

| Move | Startup | Active | Recovery | Total | Damage | Hitstun / blockstun | Hit box |
|---|---|---|---|---|---|---|---|
| `atk_n` Claw Jab | 3 | 2 | 12 | 17 | 50 | 15 / 11 | x 1.6–5.6, y 6.5–9.5 |
| `atk_f` Lunging Claw | 12 | 4 | 20 | 36 | 105 | 25 / 18 | x 3.0–9.4, y 5.5–8.5 |
| `atk_d` Fade Sweep | 10 | 4 | 22 | 36 | 80, knockdown | — / 16 | x 1.5–7.2, y 0–1.8 |
| `atk_air` Diving Claw | 7 | to landing | landing 8 | 26 | 85 | 19 / 14 | x 0.5–5.0, y −3.0–2.0 (from the root, in the air) |

- **Claw Jab** (`atk_n`): the game's fastest button (startup 3) and the chain's start. The
  leading (right) claw flicks straight out at chest height and back, the talons opening as they
  reach: frames 1–3 the elbow drops and the wrist cocks, 4–5 the arm is straight, the claw open,
  6–17 it draws back to the guard. Light damage; its job is to stop a walk-in and to start the
  chain (cancel window frames 4–11). The arm is hurtable out to 3 m from the first active frame
  until 10 frames after the last.
- **Lunging Claw** (`atk_f`): the footsie tool. A long glide forward (2.0 m over frames 3–11,
  the body dropping low and leaning in, the cape plates streaming back) into a full-length thrust
  of the right claw, talons together like a spear point, at 7 m high: frames 13–16 the contact
  pose (the arm and the claw in one straight line, the left claw drawn back by the hip). The
  claw's tip does the hitting; the arm is hurtable out to 5.5 m until 10 frames after the last
  active frame. Recovery: the claw is drawn back and the body rises (frames 17–36). Cancel window
  frames 13–22.
- **Fade Sweep** (`atk_d`): from a crouch, the left claw rakes along the floor in a wide arc in
  front (frames 11–14, the talons scraping), knocking down. Then **it dissolves**: through the
  recovery (frames 15–36) Shadow stays sunk low into its own shadow, the body folded over the
  claws and the cape plates spread over it like a shell, rising only at the end. The hurt box in
  the recovery is 4 m tall (x −1.6–1.6, y 0–4), so a punish has to be low or reach the floor:
  a Guard Cut or an Arc Jab passes over it, a Low Sweep or a Charge Slash does not. Slow and
  punishable on block (−10, measured) by anything that reaches it.
- **Diving Claw** (`atk_air`): in the air, both claws swing down and forward together, talons
  first, and **Shadow dives**: on its first active frame the fall steepens (the fight sets the
  fall to at least 0.30 m a frame and adds 0.04 m a frame forward), so it comes down sooner and
  further than the jump would. Out until landing; once a jump. A jump-in that is hard to time an
  anti-air against, but it lands sooner, so it lands close: blocked, the 8-frame landing leaves
  Shadow in reach.

### Specials (B)

| Move | Startup | Active | Recovery | Total | Damage | Chip | Hitstun / blockstun |
|---|---|---|---|---|---|---|---|
| `sp_n` Hex Bolt | 15 (fired on 16) | the bolt | 24 | 40 | 40, curses | 8 | 18 / 14 |
| `sp_f` Shadow Sneak | 24 (tapped) to 48 (held) | 4 | 22 | 50 to 74 | 110, knockdown | 22 | — / 16 |
| `sp_u` Eclipse Rise | 8 | 8 | 28 | 44 | 110, knockdown | 22 | — / 14 |
| `sp_d` Rift Mine | — | — | 14 after the mine | 26 | — | — | — |

#### Hex Bolt (`sp_n`) and the Siphon

Frames 1–15: Shadow draws the right claw back past its hip and cups it; violet light gathers
between the talons (the eye flares on 12). **Frame 16 (the `release` mark, 15 from 0)**: the
claw sweeps forward and opens, flinging the bolt. 24 frames back to the guard.

- **The bolt**: a slow ball of shadow with a violet core and a ragged dark halo, at chest height:
  it starts 3.5 m in front and flies at **0.14 m a frame** (8.4 m/s: slower than the Hero's
  wave, 0.22, and a tapped Volt Orb, 0.24), a box **1.6 m wide (x ± 0.8), from y 4.5 to 7.5**,
  for **200 frames** (28 m), and vanishes at a wall. So it hits a standing or crouching mech
  (8 m tall crouching) and either split twin (7.4 m), and passes over the Antimatter Slide
  (4.6 m), the Twins' Low Roll (3.0 m) and Shadow Sneak's travelling shadow (1 m).
- **One bolt at a time**: B while Shadow's bolt is out does nothing (the Hero's and Beam's rule).
- **Against the other shots** (they meet when their boxes overlap in x, as the wave and the orb
  do): the bolt is **strength 1**. The Hero's wave (2) and a charged (2) or full (3) Volt Orb
  dissolve it and carry on; a tapped orb (1) and the bolt both go; two bolts both go. Shadow's
  bolt does not win a projectile war: it is a hex, not a fireball.
- **What it does on hit**: 40 damage, a short hitstun (18), no knockdown, and the **Siphon**
  curse. On block it chips 8 and curses nothing (block stops every attack). **The Parry catches
  it** like the wave (no curse). The Void Step passes through it. **Tank's armour absorbs the
  hit but not the curse**: an absorbed bolt still curses (the hex is in the touch, not the
  impact).
- **The Siphon**: for **360 frames (6 s)** of play (not counting the hitstop, the super's freeze
  or the time between rounds), every bit of meter the cursed mech would gain goes to Shadow
  instead. A second bolt that lands **refreshes** the curse to 360; curses never stack, and a
  curse ends with the round. Shadow's meter stops at one bar as always (what does not fit is
  lost). Exactly what is siphoned, by power source:

  | Source | What the cursed mech would gain | What Shadow gets |
  |---|---|---|
  | Kinetic (the Hero) | +125 a hit that lands, +120 the wave, +60 a blocked hit | all of it |
  | Antimatter (the Double-blade Hero, a Shadow) | the reactor's +1 a frame, +60 a hit | **half** (+1 every other frame, +30 a hit): the cursed mech gains nothing, so one in debt stops climbing out |
  | Chemical (Beam) | a running reaction's +2 a frame (the reaction keeps burning) | all of it: curse Beam during a reaction and the reaction is Shadow's |
  | Nuclear (Tank) | 3 for every point of damage it takes | **a quarter**: 3 for every 4, and the cursed Tank keeps the other three quarters. Shadow's own hits already pay Shadow; the curse only skims the reactor |
  | Fusion (the Twins) | combined only: +2 a frame, +60 a combined hit, Fusion Focus +6 a frame held | all of it. Split, the Twins gain nothing, so nothing is siphoned: **splitting is how the Twins sit a curse out** |

  Training's meter refill is not a gain and is never siphoned.
- **How it shows.** On the cursed mech: a violet glow pulses at its chest and violet motes rise
  off it and drift toward Shadow; in the curse's last second the glow flickers. On the HUD: the
  cursed mech's meter is overlaid with violet chain hatching that marches toward the screen's
  centre, its label reads **SIPHON**, a thin violet bar under the gauge shrinks with the curse's
  time, and whenever meter is taken, violet motes stream along the bottom of the screen from the
  cursed mech's gauge to Shadow's, which flashes where they land.

#### Shadow Sneak (`sp_f`)

Shadow sinks into its own shadow, a dark shadow races forward along the floor, and Shadow erupts
from its end with a rising claw. **Holding B sends the shadow farther.**

| Frames (tapped) | |
|---|---|
| 1–8 | **the sink**: Shadow folds down into a pool of shadow at its feet, the cape plates closing over it last. Vulnerable: the hurt box is a crouching one |
| 9–20 | **the travel**: Shadow is gone (the `hide` mark); only its shadow moves, **0.5 m a frame**, flat on the floor. The fight moves the root (no root motion in the animation). **Frame 20 is the charge frame** (the `charge` mark, Beam's): while B is held the move holds there, up to **24 frames**, the shadow still travelling |
| 21–24 | **the eruption**: Shadow rises out of the shadow claws first, the talons leading |
| 25–28 | active: a rising two-claw rake from the floor upward, x 0.5–4.5, y 0–9 |
| 29–50 | recovery (22): the claws come down and it settles into the guard |

- **Distance**: tapped, the shadow travels **6 m** (12 frames); held the whole 24 frames,
  **18 m**. Held less, anything between: 6 m + 0.5 m a frame held.
- **The shadow stops at the other mech's feet**: it never passes through or under it (the
  push boxes, as in a walk), nor through a wall. So Shadow always erupts in front of the other
  mech, never behind it, and a strike that reaches is blocked as any other.
- **The travelling shadow can be hit**, low: its hurt box is x −1.5–1.5, y 0–1 (and its push
  box is that low too). Low attacks, sweeps, slides and the Hero's wave (y 0–3) hit it and knock
  Shadow out of it (it reappears in its hit reaction); anything higher passes over it: Beam's
  Volt Orb (y 4.8–6.6), the Hex Bolt, every standing attack. So **the Sneak goes under a Volt
  Orb**, and is stopped by a wave.
- The strike: 110 damage, knockdown, chip 22. On block −10 (measured): punishable by a jab.
- **Afterimages** (visual only): as Shadow erupts, two violet afterimages of it stand along the
  shadow's path behind it, fading over 12 frames.
- What it is for: a punish from far (it reaches a whiffed Charge Slash or a blocked Bulldozer
  from 18 m), and a way past a Volt Orb. Read on reaction it is very punishable: the shadow is
  plain to see on the floor for 12 frames or more before the strike.

#### Eclipse Rise (`sp_u`)

The anti-air. Frames 1–4: Shadow drops straight down into its shadow (it is **invulnerable
on frames 1–9**: the sink, the time under the floor and the first active frame). Frames 5–8:
under the floor (`hide`), its shadow slides **3.6 m forward** (root motion 0.9 m a frame; the
push boxes stop it at a mech on the ground, but it goes on under a mech in the air), then
frames 9–16 it **erupts straight up** under the other mech, both claws raised overhead, talons
together: the box x −1.0–3.5, y 2–13 from the root, which rises 5 m over the active frames
(root motion 0.625 m a frame), then falls back to the floor over the 28 frames of recovery,
cape plates spread. 110 damage, knockdown.

- **Reach**: it hits up to about 7 m in front of where Shadow started and 18 m up at the top of
  the rise: further out than the Rising Arc, so it takes a jump-in that would land in front of
  Shadow, not only one that lands on it. The invulnerability covers 9 frames against the Rising
  Arc's 7, but it is 2 frames slower to hit (startup 8).
- Very punishable on block or a miss (about −22).

#### Rift Mine (`sp_d`)

Frames 1–11: Shadow crouches and drives the left claw's talons into the floor in front of its
feet; a violet sigil spreads out from them. **Frame 12 (`release`, 11 from 0): the mine is
laid**, on the floor at Shadow's root. Frames 13–26: back up into the guard. Not an attack.

- **The mine**: a flat violet sigil on the floor. It **arms 45 frames** after it is laid (the
  sigil's ring closes and it glows); before that it does nothing.
- **Its trigger**: the floor around it, **x ± 1.0 m, y 0–1 m**. An armed mine is set off by a
  mech of the other side whose push box touches it while that mech is on the ground: standing,
  walking, crouching, blocking, attacking or landing on it; either of the split Twins. It is
  not set off by a mech in the air, in hitstun or blockstun, knocked down or getting up, thrown,
  invulnerable, or with no push box (the Void Step); nor by Shadow (**Shadow never sets off its
  own mine**, and Shadow's attacks never destroy it).
- **The snare**: the mech that sets it off is **held in place for 30 frames** (half a second):
  whatever it was doing stops (the move is cut, it stands), and it cannot move or act; violet
  shadow binds its legs. It can be hit (the hit lands as a hit: it is not blocking) and grabbed
  (it is standing). The first hit or catch frees it into its reaction at once; a snare is not a
  hit, so a combo started on a snared mech is not scaled for it.
- **What destroys it**: any hit box of the other side that touches the mine's box (x ± 1.0,
  y 0–1): the low attacks, the sweeps, the slides, the Bulldozer, the Reactor Vent (not the
  Pulse Spin, which starts 1.5 m up); and the other side's shots at floor height (the Hero's
  wave). A mine set off or destroyed is gone. It also fades after **600 frames (10 s)**
  and at the round's end.
- **One mine at a time**: laying a new one removes the old one.
- What it is for: Shadow lays it between itself and the other mech and steps back; the other
  must walk over it, jump it (and meet Eclipse Rise), or clear it with a low attack (a slow,
  punishable one). Snared, it eats a Lunging Claw, a Sneak or a Phantom Grip.

### Grab and throw (Y): Phantom Grip

`grab`: startup 5, active 2 (the catch box x 1.0–3.8, y 2–10: the claws are long), 7 frames;
a miss plays `grab_whiff` (22). Breakable as every Y grab (Y within 10 frames). On a catch,
`throw` (44 frames) on Shadow and `thrown` (44, the Hero's throw's victim move) on the other:
Shadow pulls the other into its shadow and comes up **behind it**: the sides swap.

| Frames | Shadow | The other (the fight places it) |
|---|---|---|
| 1–10 | the claws close on the other's shoulders (the break window) | 3.0 m in front, lifted to 1.5 m |
| 11–16 | Shadow sinks into its shadow, dragging the other down | lowered to the floor |
| 17–24 | gone (`hide`): its shadow slides **6 m** under the other to its far side (0.75 m a frame; the fight moves the root, stopped by a wall) | held standing where it was, shadow binding its legs |
| 25 | Shadow erupts behind it and **turns** to face it; the other is turned round to face Shadow | placed 3.0 m in front of Shadow's new spot |
| 25–30 | the claws hook into its back and lift | lifted to 3 m |
| 31 (`release`, 30 from 0) | the claws fling it away | 110 damage, knockdown, about 5.5 m (it lands about 8.5 m from Shadow), **toward the side Shadow came from** |
| 32–44 | recovery into the guard | |

So a cornered Shadow that grabs leaves the corner and puts the other mech in it: the Vault
Throw's corner escape, by shadow instead of a vault. Against a wall behind the other there is
no room behind it: Shadow comes up at the wall and the other is moved back 3.0 m in front of it
(the sides still swap). Less damage than the other throws; the side swap is the point.

### Super (A + B): Total Eclipse

The flash (frames 1–40: the world freezes, Shadow alone moves: it rises to full height, spreads
both claws wide, the cape plates fanning out, and the eye flares white; **the stage goes dark**,
the hall and the floor darkened with Umbral's violet through the colour offset). The dark stays
until the last hit. Then:

| Frames | |
|---|---|
| 41–44 | Shadow lunges 8 m forward (root motion 2.0 m a frame), stopping at the other mech |
| 45–47 | hit 1: a right-claw slash across, x 0–6, y 3–10 |
| 50–52 | hit 2: a left-claw slash back |
| 55–57 | hit 3: right |
| 60–62 | hit 4: left |
| 66–70 | hit 5, the finisher: both claws rake up from the floor, x 0–6.5, y 0–12, knockdown |
| 71–106 | recovery (36): the claws come down, the cape plates settle, the stage lights return |

- **Invulnerable from frame 1 to 44.** Each hit is its own (the boxes' `hit` index 0–4).
- Hits 1–4: 70 damage each, chip 14, hitstun and blockstun 30 (the other stays in reach and in
  its reaction between the hits), a short hitstop (6), knockback 0.02. Hit 5: 120 damage, chip 24,
  knockdown, the super's hitstop (20), blockstun 20. Scaled as any combo: 70 + 56 + 45 + 45 + 78
  = **294** from a clean start. Chip through a block: 80 in all, which can finish a round.
  −21 on block (measured).
- **Afterimages** (visual only): on each hit a violet afterimage of Shadow appears on alternate
  sides of the other mech, mid-slash, and fades over 10 frames, so in the dark it looks struck
  from everywhere at once. Shadow itself stays in front: the hits are blocked as any other.
- **The debt**: it costs one bar, as every antimatter super. From zero that is a full bar of
  debt: 25 % more damage taken until the reactor (a bar in 20 s) climbs back to zero. Each hit
  that lands repays 5 % (antimatter's hit gain), a quarter of a bar if all five land; the Siphon
  is the other way out of debt.

### Chains

The shared chain: Claw Jab, then Lunging Claw, then a special or the super. **The Hex Bolt
combos from a Lunging Claw** up close (the bolt starts 3.5 m out and touches at once): the
chain's payoff is the curse, not the damage. Eclipse Rise combos from a Claw Jab close up. The
Sneak never combos (the shadow is too slow); the Rift Mine can be cancelled into (a blocked
Lunging Claw into a mine at the other's feet: it arms after it recovers).

### Frame advantage (measured)

From the fight itself (`tests/run.sh 17`, the stand-in timings, against a standing Hero): Claw
Jab −3 on block / +1 on hit, Lunging Claw −6 / +1, Fade Sweep −10 (knockdown on hit), Hex Bolt
−11 / −7 at 6 m (safe from further out), Shadow Sneak −10 (tapped, at 7 m), Eclipse Rise −22,
Total Eclipse −21.

### Balance intent

A setup character: it controls space (the mine), taxes an approach (the slow bolt, which
cannot win a projectile war but does not need to), steals meter (the curse) and punishes
impatience from far (the Sneak). Its weaknesses are plain: the lowest health (900), light hits
(a clean round takes Shadow eight to ten hits where the Hero takes six to eight), short buttons
apart from the Lunging Claw, a bolt that loses to the wave and a charged orb, and specials that
are very punishable when read. The curse is its meter plan: antimatter lets it spend first and
the Siphon pays the debt back. Against Tank it wants the mine (the Bulldozer and the Clinch's
dash set it off) and the curse (a quarter of the nuclear meter); against the Twins the curse forces
them to stay split; against Beam the curse steals the reaction and the Sneak goes under the orbs.

### Reactions and the rest (Shadow)

As the shared list below, with Shadow's lengths: `walk_f`, `walk_b` 44; `jump` 40; `land` 8;
`throw` 44; `thrown` 44, `thrown_vault` 40, `thrown_slam` 56 (Shadow as the victim: long and
light, the claws dragging). `idle` (60): a slow sway, the talons flexing one by one, the eye
dimming and brightening. `block` (4): both claws crossed in front of the head and chest, the
cape plates swung forward round it. `knockdown` (32): it folds and drops like cloth, the plates
clattering. `win` (120): it sinks into its shadow and rises again behind its own spot, claws
spread, the eye flaring. `intro` (90): its shadow slides out of the booth's spot lights and
Shadow rises out of it into the stance.

### For the animators (Shadow)

- **The skeleton is the shared one** (`enum Part`; `models/shadow/shadow.rig.json` from
  `models/shadow/make_shadow.py`). Long thin arms; the hands as big as the forearms. **The claws
  are `weapon_r` and `weapon_l`**, on the hand mounts, their talons running along the part's +Y
  (as the Hero's blade does) and glowing violet at the tips: the effects' claw trails sample
  the points (0, 0.3, 0) to (0, 2.8, 0) in each claw's frame, so a talon tip should be about
  2.8 m from the mount. The cape plates hang rigid from `pauldron_r`, `pauldron_l` and `torso`
  (no joints of their own): keep them clear of the thighs in the crouch, the Fade Sweep and the
  sinks.
- **Sinking into the shadow.** The Sneak, Eclipse Rise and Phantom Grip sink Shadow into the
  floor: there is no floor to hide behind (the floor is a plane drawn behind the mechs), so a
  sink is a fold: the knees and hips collapse, the torso folds over, the cape plates close over
  the top, the whole body ending under 3 m tall by the last frame before a `hide`. The fight
  hides the mech on `hide` frames and the effects draw the shadow. Rising is the same in reverse,
  claws first.
- **Root motion**: `atk_f` 2.0 m over frames 3–11; `sp_u` 3.6 m forward over 5–8 (0.9 a frame),
  then up 5 m over 9–16 (0.625 a frame) and back down over the recovery; `super` 8 m over 41–44
  (2.0 a frame). **None** in `sp_f` and `throw`: the fight moves the root in the Sneak's travel
  and the Grip's slide.
- **Marks** (frames from 0, as the files count): `cancel` on `atk_n` 3–10 and `atk_f` 12–21;
  `invuln` on `sp_u` 0–8 and `super` 0–43; `flash` on `super` 0–39; `release` on `sp_n` 15 (the
  bolt), `sp_d` 11 (the mine) and `throw` 30; `charge` on `sp_f` 19; `hide` on `sp_f` 8–19 (the
  travel), `sp_u` 4–7 and `throw` 16–23; `step` on the walks' plants. Not `nopush` on any of the
  `hide` frames: the shadow keeps a push box (it must stop at the other mech) and, in the Sneak,
  a low hurt box.
- **Boxes**: the Fade Sweep's recovery (frames 14–35 from 0) has a hurt box only 4 m tall; the
  Sneak's travel a hurt box x −1.5–1.5, y 0–1 and a push box as low; Total Eclipse's five hit
  boxes carry `hit` 0 to 4 (the fight's damage table is by that index).
- **The throw's turn**: Shadow's facing turns on `throw` frame 25 (24 from 0): animate the
  rise behind the other as if still facing the same way and the fight turns the root; the other
  mech's `thrown` is played from the same frame number, and is turned round too.
- Shadow is about 12 m tall: tall and thin, the claws dominating the silhouette, reading apart
  from the Double-blade Hero (also black and violet) by its height, the cape, the single eye and
  the claws in place of blades.

## Seraph (Momentum Robotics, kinetic)

Momentum Robotics' echo of Shadow, the paladin: SERAPH, model MR-02, in the echo slot under Shadow
(unlocked by clearing the arcade with Shadow). Where Shadow is the trickster, Seraph is Momentum's
honest boxer with an angel's wings: it goes **over** the floor where Shadow goes under it, sends
shots **back** where Shadow steals meter, and **marks** where Shadow curses. It taxes an approach
with a slow bolt of light, the **Mark of Judgement**, which marks the other mech for six seconds;
it answers the other's shots with the **Wing Ward**, which sends them back as light; it crosses
the stage over waves and mines with the **Seraph Dive**; and it cashes the mark in with its super,
**Judgement**, a column of light that falls wherever the other mech stands. Block still stops
every attack from either side. In exchange its fists are short (about 2.5 m less than Shadow's
talons), its specials are slow and readable, and nothing it has is invulnerable for long. Its
stance is a boxer's: upright, the right fist leading at chin height, the left by the jaw, elbows
in, the wings folded behind like a cloak, the halo resting on the helm.

The design is the owner's
([Decided by the owner (2026-10-14)](#decided-by-the-owner-2026-10-14-seraph-momentums-angel)); the
numbers below are this section's, to tune in play. Phase 1 (mx-seraph) has the mech in the game
with Shadow's moves as placeholders ([Phase 1](#phase-1-what-is-in-the-game-now)); phase 2 builds
this section in three parts at once: the fight and the CPU, the animations, the effects and sound.
Each part's list is at the end ([For the animators](#for-the-animators-seraph),
[For the effects and sound](#for-the-effects-and-sound-seraph),
[Engine work needed](#engine-work-needed-seraph)). The fight and the CPU are in (mx-seraph-fight):
every rule below plays, from stand-in timings and boxes with this section's numbers wherever
Seraph's animation is still Shadow's placeholder.

Code name `Seraph` (`enum Mech`, index 8, appended after `Shadow`). The model is
`models/seraph/make_seraph.py` (concept A, round 4b, 1,892 triangles): Shadow's skeleton and joint
offsets, the gauntlet fists with gold knuckle guards as the weapon parts, and three joints appended
to the shared skeleton: `wing_l`, `wing_r` (the torso's, folded at 0, spread at x −122, y 50,
z −24, the right wing mirrored) and `halo` (the head's: turning it x 0..60 lifts the ring 0.9 m).
Power source: Momentum's kinetic meter, the Hero's (+125 a landed hit, +120 a shot that lands, +60
a blocked hit; the super needs a full bar; no debt).

### Movement and stats

| | Seraph |
|---|---|
| Health | 1,000 (the Hero's; Shadow has 900) |
| Walk forward | 0.080 m a frame (4.8 m/s): a little slower than Shadow's 0.085 |
| Walk back | 0.064 m a frame (3.8 m/s) |
| Walk cycle | 44 frames, two steps (3.5 m forward) |
| Jump | 4 frames' crouch, then 36 in the air, 6.2 m high at the top (`jump` is 40 frames): Shadow's |
| Diagonal jump | 0.17 m a frame across (6.1 m) |
| Landing | 5 frames (8 after an air attack) |
| Push box | 1.4 m either side of the root, 11.5 m tall (7.5 crouching): Shadow's |
| Hurt box | follows the parts (`anims/seraph/_body.anim.json`, Shadow's boxes on Seraph's parts): about 1.6 m either side of the body, 12.5 m tall standing, 8 crouching; the guard holds the fist's box out to about 3.3 m in front, and the Wing Ward's first frames reach about 3.7 m at a bolt's height (scenarios 172-175 time the ward from these boxes). The wings and the halo have no hurt boxes |
| Height | 13.55 m to the top of the halo (the roster's 135) |

These are the numbers in the game now (`moves.akr`'s `STATS` row). The walk is a boxer's: upright,
a short gliding step with the weight on the balls of the feet, the guard held steady, a light
`step` mark on each plant; the folded wings settle a few degrees on each plant. The jump is
Shadow's timing with the wings half opening at the top (to steady it) and folding on landing.

### Attacks (A)

| Move | Startup | Active | Recovery | Total | Damage | Hitstun / blockstun | On block / hit | Hit box |
|---|---|---|---|---|---|---|---|---|
| `atk_n` Jab | 3 | 2 | 12 | 17 | 50 | 15 / 11 | −3 / +1 | x 1.7–3.2, y 6.6–7.8 |
| `atk_f` Lunging Straight | 12 | 4 | 20 | 36 | 105 | 25 / 18 | −6 / +1 | x 2.6–6.8, y 6.7–8.3 |
| `atk_d` Reaping Kick | 10 | 4 | 22 | 36 | 85, knockdown | — / 16 | −10 / KD (+44) | x 1.4–6.2, y 0–1.8 |
| `atk_air` Double-fist Dive | 7 | to landing | landing 8 | 26 | 85 | 19 / 14 | by height | x 0.5–3.6, y −1.0–2.4 (from the root, in the air) |

(The on-block and on-hit columns are measured with `tests/run.sh 17` against a standing Hero,
from the stand-in timings above (mx-seraph-fight); KD (+44) is a knockdown, the attacker free 44
frames before the other is up. Measure again once the animations land.)

- **Jab** (`atk_n`): the game's fastest button with the Claw Jab (startup 3), and the chain's
  start. Shadow's timing and the reach phase 1 measured (the fist to 3.2 m), but **lower**: the
  right fist snaps straight out at chest height, not face height, so the box is **y 6.6–7.8**
  and it hits a crouching mech (8 m tall) and either split twin (7.4 m). Frames 1–3 the right
  shoulder rolls in and the fist leaves the chin; 4–5 the arm is straight, the fist level at about
  7.2 m (its front 3.2 m out); 6–17 it snaps back to the chin. The torso turns 10° into it, the
  wings stay folded. Cancel window frames 4–11. The arm is hurtable out to 2.5 m from the first
  active frame until 10 frames after the last. It passes over the Antimatter Slide (4.6 m) and
  the Twins' Low Roll (3.0 m).
- **Lunging Straight** (`atk_f`): the footsie tool, a lead-hand straight with the whole body
  behind it. Shadow's timing and its glide (2.0 m over frames 3–11, the rear foot driving), the
  reach phase 1 measured (x 2.6–6.8, y 6.7–8.3): the right arm and fist in one straight line at
  about 7.5 m on frames 13–16, the left fist kept at the jaw, the torso turned 30° into it, the
  folded wings swinging back with the lunge. Recovery: the fist drawn back to the chin and the
  weight back over the rear foot (frames 17–36). Cancel window frames 13–22. The arm is hurtable
  out to 4.5 m until 10 frames after the last active frame. About 2.6 m shorter than the Lunging
  Claw: Seraph has to walk closer to poke, which is what the Dive is for.
- **Reaping Kick** (`atk_d`, new; the Fade Sweep does not carry over): from a crouch, a low
  sweeping kick with the right leg along the floor in a wide arc in front, the hands down for
  balance, knocking down. Frames 1–10: the body drops (the pelvis down about 3 m), the left knee
  bends deep, the right leg is chambered back; 11–14: the right leg sweeps through at full length,
  the foot a hand's width off the floor (the box follows the right shin and foot); 15–36: the leg
  comes back under and Seraph rises into the guard, the wings flaring 10° for balance as it
  rises. The leg is hurtable to 4 m out from the first active frame until 10 frames after the
  last. No dissolve: the recovery's hurt box is an ordinary crouching one (8 m), so anything
  punishes it. For catching a mech that walks back or sits still; the answer to a Low Roll; and,
  a hit box at the floor, it clears a Rift Mine it touches.
- **Double-fist Dive** (`atk_air`): in the air, both fists clasped together over the head and
  driven down and forward as Seraph pitches into a dive, the wings swept back. Shadow's timing and
  **its dive** (the fall steepens on the first active frame: at least 0.30 m a frame down, 0.04
  m a frame more forward: `has_dive` stays true for Seraph). The box follows the clasped fists:
  about x 0.5–3.6, y −1.0–2.4 from the root (the talons' box less about 1.5 m forward and 1.6 m
  down; the animator measures and keeps the fists in it). Out until landing; once a jump.

### Specials (B)

| Move | Startup | Active | Recovery | Total | Damage | Chip | Hitstun / blockstun | On block / hit |
|---|---|---|---|---|---|---|---|---|
| `sp_n` Mark of Judgement | 16 (fired on 17) | the bolt | 24 | 41 | 45, marks | 9 | 18 / 14 | −11 / −7 at 6 m; safe far |
| `sp_f` Seraph Dive | 28 (tapped) to 52 (held) | 4 | 22 | 54 to 78 | 110, knockdown | 22 | — / 16 | −10 / KD (+50) |
| `sp_u` Ascension | 7 | 8 | 28 | 43 | 120, knockdown | 24 | — / 14 | −22 / KD (+48) |
| `sp_d` Wing Ward | 4 | the ward, 20 | 16 | 40 (12 after a reflect) | — | — | — | — |

(Measured with `tests/run.sh 17` against a standing Hero, from the stand-in timings: the bolt from
6 m, the Dive from 7 m (where the glide meets the Hero after a frame and dives onto it), Ascension
from 3.6 m. They match the estimates from the moves with the same recovery: the Hex Bolt's,
the Sneak's, Eclipse Rise's.)

**Against the defences** (the details are in each move's section):

| Seraph's move | The Parry | Wing Ward (a mirror Seraph) | The Void Step | Tank's armour |
|---|---|---|---|---|
| Mark of Judgement | caught: the bolt vanishes, no mark; the riposte if Seraph is in reach | sent back as the warder's Mark: it marks the first thrower | passes through | absorbs the 45; **the mark lands** |
| Seraph Dive | parried: Seraph frozen 20 frames in the air, the riposte knocks it down | not caught (a strike) | passes through | absorbs the 110; Seraph lands in front of Tank with 22 frames to recover |
| Ascension | parried | not caught | passes through | absorbs; Seraph falls above Tank for 28 frames |
| Wing Ward | not an attack | not an attack | | |
| Heaven's Arc (Y) | misses: a parrying Hero is in a move (and grabs are never parried) | misses: a warding Seraph is in a move | misses: gone | catches: grabs break armour |
| Judgement | not parried (no super is) | not caught (not a shot) | escapes, started on the first frame after the flash | never absorbs a super |

The normals are ordinary strikes: parried, absorbed, passed through, not caught by a ward.

#### Mark of Judgement (`sp_n`) and the mark

Frames 1–16: Seraph draws the right fist back to the shoulder, the left guard forward; light
gathers in the knuckle guard and the halo lifts a little (x 0 to 20, 0.3 m). **Frame 17 (the
`release` mark, 16 from 0)**: the right fist punches straight forward at belly height and the
bolt leaves it. Frames 18–41: 24 frames back to the guard, the halo settling.

- **The bolt**: a slow lance of white-gold light, at mid height: it starts **3.5 m** in front
  and flies at **0.16 m a frame** (9.6 m/s: a little quicker than the Hex Bolt's 0.14, slower than
  the wave's 0.22), a box **1.6 m wide (x ± 0.8), from y 5.0 to 7.4**, for **180 frames** (29 m),
  and vanishes at a wall or an open edge. So it hits a standing or crouching mech (8 m) and
  either split twin (7.4 m), and passes over the Antimatter Slide (4.6 m), the Twins' Low Roll
  (3.0 m), Shadow Sneak's travelling shadow (1 m) and the Hero's wave.
- **One shot at a time**: B while Seraph's shot is out does nothing (every shot's rule). A shot
  Seraph reflected (the Wing Ward, below) is Seraph's shot too, so no bolt until it is gone.
- **Against the other shots** (they meet when their boxes overlap in x): the bolt is
  **strength 1**, as the Hex Bolt. The wave (2) and a charged (2) or full (3) Volt Orb dissolve
  it and carry on; a tapped orb (1), a Hex Bolt (1) or another Mark bolt and the bolt both go. It
  does not win a projectile war; it does not need to.
- **On hit**: 45 damage, hitstun 18, no knockdown, and **the mark**. Kinetic meter +120 (a shot).
  On block: chip 9, blockstun 14, +60 meter, **no mark** (block stops every attack).
- **The mark**: for **360 frames (6 s)** of play (not the hitstop, the super's freeze or the time
  between rounds), the other mech is marked. **Judgement does 50 % more to a marked mech**
  (below); the mark does nothing else: no damage of its own, no meter, nothing on Seraph's other
  moves. A second bolt that lands **refreshes** the mark to 360; marks never stack, and a mark
  ends with the round. The mark is on the fighter (`Fighter.mark`), so the Twins carry it through
  switching forms, whichever twin was hit. It is not spent by Judgement: it runs its time.
- **The Parry catches the bolt** as it catches the wave: the bolt vanishes, no mark, the Hero
  ripostes if Seraph is in reach. **The Void Step** passes through it. **Tank's armour absorbs the
  hit, not the mark**: an absorbed bolt still marks (as the Hex Bolt still curses: the mark is in
  the touch). **Wing Ward** (a mirror match): the bolt is sent back as the warding Seraph's own
  Mark and marks its first thrower ([Wing Ward against each shot](#wing-ward-against-each-shot)).
- **How the mark shows**, the Siphon's presentation in light gold instead of violet
  (`seraph_fx.akr`, [For the effects and sound](#for-the-effects-and-sound-seraph)). **On the
  marked mech**: a light-gold sigil glows at its chest, pulsing once a second (a ring with a
  cross, Momentum's chevron at the top); a thin gold ring turns slowly 1.5 m above its head (the
  halo's echo); gold motes rise straight up off it (nothing is taken, so they do not drift to
  Seraph, as the Siphon's motes do); in the mark's last second (60 frames) the sigil and the ring
  flicker. **On the HUD**, the marked mech's side: the label **MARKED** in light gold where the
  Siphon writes SIPHON (13 px above its meter gauge, aligned outward), a thin gold bar under the
  gauge shrinking with the mark's time (the Siphon's bar), the label flickering in the last
  second; a light-gold shine sweeping across the marked mech's **health bar** toward the screen's
  centre every 30 frames (where the Siphon marches chains over the meter: the mark is about
  damage, so it lives on the health bar); and while Seraph's super is ready and the other is
  marked, Seraph's SUPER label pulses gold. A new mark (not a refresh) flashes the health bar
  gold for 8 frames.

#### Seraph Dive (`sp_f`)

A hop, a glide on spread wings, then a diving straight. **Holding B glides farther.** In the air
from the hop to the touchdown: it passes over anything on the floor, and **anything that hits it
in the air stops it** (an air hit: `hit_air`, knocked down).

| Frames (tapped) | | Root and boxes |
|---|---|---|
| 1–6 | **the crouch**: the knees bend deep, the fists drop to the hips, the wings lift off the back (wing x 0 to −30) | on the floor; crouching hurt and push boxes (8 m and 7.5 m tall). Vulnerable: a hit here is a ground hit |
| 7–14 | **the hop**: Seraph springs up and forward, the wings snapping open to spread by frame 12 | root motion **2.0 m forward and 4.0 m up** (0.25 and 0.5 m a frame). In the air from frame 7 |
| 15–26 | **the glide**: the body laid forward 60°, the legs trailing back level with the root, the arms forward, the wings spread with a slow flutter | **the fight moves the root**: 0.40 m a frame forward and 0.02 m a frame down (no root motion in the animation). **Frame 26 is the charge frame** (the `charge` mark): while B is held the move holds there, up to **24 frames**, still gliding. Push box x ± 1.4, y 0–7 from the root; the hurt boxes follow the parts and none goes below the root |
| 27–28 | **the dive**: the wings sweep back half-folded, the body pitches down, the right fist cocked by the head | the fight brings the root down to the floor evenly over frames 27–32 (whatever its height) and 0.30 m a frame forward |
| 29–32 | **active**: the diving straight, the right arm driving down and forward, the fist leading | hit box x 2.0–5.5, y 1.0–4.5 from the root |
| 33 | **touchdown** (`step`), on the right knee and the left foot | on the floor |
| 33–54 | recovery (22): Seraph rises from the knee, the wings folding by 48 | standing boxes |

- **Distance**: tapped, the root travels **8.6 m** (2.0 the hop, 4.8 the glide, 1.8 the dive) and
  the fist reaches 5.5 m past it, about 14 m from where Seraph stood; held the whole 24 frames,
  **18.2 m** (the fist about 24 m out). Held less, anything between: 0.40 m a frame held. The
  glide sinks 0.24 m tapped and 0.72 m held, so the root is between 3.3 and 3.8 m up when the dive
  starts.
- **The glide stops at the other mech**: when Seraph's push box (y 0–7 above the root) touches
  the other's push box, overlapping in height, the glide ends there and the dive starts at once
  (the animation jumps to frame 27); the dive's forward motion stops at it too. So Seraph never
  glides through or over a standing, crouching or jumping mech: it dives onto it. A push box
  lower than the root passes under: **Shadow Sneak's shadow (1 m), the Twins' Low Roll (3.0 m)**.
  A wall, the separation limit or an open edge's lip also ends the glide (the dive starts there):
  Seraph is never carried off the stage by its own Dive.
- **Over the floor**: from frame 13 (the root above 3 m) to frame 28, nothing at floor height
  touches it: **the Hero's wave** (y 0–3) passes under, **a Rift Mine** is not set off (Seraph is
  not on the ground), **Shadow Sneak's shadow** passes under (it has no hit box; the eruption
  after it is a strike like any other; Shadow's shadow stops short of a gliding Seraph, as at
  any mech, until Seraph has passed over it, since `sneak_step` does not look at height). Low
  attacks, sweeps and slides (their boxes under 2.5 m) pass under it; the Bulldozer's ram (y 0–5)
  and the Reactor Vent (y 0–9.5) reach it. A wave that arrives during frames 7–12, while the hop
  is still under 3 m, hits its legs: the hop must start at least 13 frames before the wave
  arrives. **Landing on an armed Rift Mine** (frame 33 onward) sets it off as any landing does.
- **What stops it**: every shot above the floor (a Volt Orb at y 4.8–6.6, a Hex Bolt at 4.5–7.5, a
  Mark bolt) and every strike that reaches it: a Tip Thrust, an Arc Lance, a Static Lance, an
  anti-air. A hit from frame 7 on is an air hit: Seraph is knocked down out of the sky. On frames
  1–6 a hit is an ordinary hit. It cannot be grabbed anywhere in the move.
- **Against the Parry**: the straight is parried like any strike: Seraph freezes in the air for
  20 frames (the Parry's freeze), and the Hero's riposte (x 1.5–7.5, y 4–10) takes it out of the
  air. **The Void Step** passes through it. **Tank's armour** absorbs it (Tank takes 110, no
  knockdown) and Seraph lands in front of Tank with 22 frames of recovery: punished.
- The strike: 110 damage, knockdown, chip 22, blockstun 16, about −10 on block (a jab punishes).
- What it is for: crossing the stage over the Hero's wave and Shadow's mines, and a punish from
  far (a whiffed Charge Slash, a blocked Bulldozer, a Reaction Prime). Read, it is very
  punishable: the hop and the glide are plain to see for 15 frames or more, and any shot or
  anti-air takes it.

#### Ascension (`sp_u`)

The anti-air: a rising uppercut, the wings flaring. Frames 1–7: Seraph drops into a crouch and
steps in **1.2 m** (root motion over frames 2–7, 0.2 m a frame), the right fist dropping to the
hip, the wings lifting; **invulnerable on frames 1–8** (the startup and the first active frame).
Frames 8–15, active: it springs straight up and drives the right fist up from the hip to straight
overhead, the box following the fist (**x 0.5–4.0, y 3.0–14.0** from the root), the root rising
**6.0 m** (0.75 m a frame); the wings flare to spread on frames 12–15 and beat once at the top
(down-stroke on 14), the halo lifting to x 30. Frames 16–43, recovery (28): it falls back, the
root coming down 6.0 m over frames 16–38 (accelerating), the wings folding as it falls, and
lands on 39 (`step`), the knees taking it through 43.

- **Reach**: about 5.2 m in front of where Seraph stood (the step and the fist) and 20 m up at the
  top of the rise: it takes a jump-in that lands on Seraph or just in front of it, not one that
  lands 7 m out (Eclipse Rise reaches that). Invulnerable 8 frames: between the Rising Arc's 7 and
  Eclipse Rise's 9, one frame slower to hit than the Rising Arc (startup 7).
- 120 damage, knockdown, chip 24. Very punishable on block or a miss (about −22).
- The Parry catches it; Tank's armour absorbs it (and Seraph is in the air above Tank, falling,
  for 28 frames); the Void Step passes through it.

#### Wing Ward (`sp_d`)

The folded wings swing forward round the body as a shield of light. Shots that touch it are sent
back as light and become Seraph's; **strikes are not caught** (the Hero's Parry does that): a
strike that reaches Seraph during the ward hits it as it would during any special.

| Frames | |
|---|---|
| 1–4 | **the wrap**: the arms cross in front of the face, the head bows behind them, the wings swing round the sides to the front (about x −20, y 120, z 0 on the left; the right's y and z negated) |
| 5–24 | **the ward** (the new `ward` mark, 20 frames): the wings wrapped in front from the knees to the shoulders, holding; the light flickering on the plates |
| 25–40 | recovery (16): the wings swing back and fold, the arms come down into the guard. **The move ends here (frame 40) unless a shot was reflected** (as the Parry ends at its riposte frame) |
| 41–52 | **the fling** (12 frames, `riposte` on 41), only after a reflect: the wings snap open to spread and are folded again by 52, the fists back in the guard |

- **What it catches**: a shot of the other side that touches any of Seraph's hurt boxes on a
  `ward` frame, **travelling toward Seraph's front** (its direction opposite Seraph's facing). The
  light wraps the whole body in the drawing, so the wave along the floor, which touches only the
  shins, is caught too. A shot from behind (after a side swap) hits as usual.
- **A reflect**: the shot is turned round and becomes Seraph's (below); Seraph's animation jumps to
  the fling (frame 41): **actionable 12 frames after the reflect**. A shot reflected this frame is
  not moved or tried against a mech until the next frame.
- **No room for it**: if Seraph's own shot is still out (a Mark bolt, or a shot reflected
  earlier), the ward takes the shot without sending it back: it vanishes in a burst of light, no
  damage, and Seraph still jumps to the fling. (Two opposing shots meet before they pass, so this
  is rare: a bolt fired after the other's shot had passed it.)
- **Strikes, throws and supers**: a strike (a normal, a special's hit box, an air attack, the
  Arc Lance, the Raikō Overload's beam, any super) hits a warding Seraph in the ordinary way; it is
  in a move, so it is knocked out of it. A grab misses it (a mech in its own move is not
  grabbable: strikes beat grabs), but the 16 frames of recovery are long enough to walk in and
  grab after a ward that caught nothing.
- **Meter**: a reflect itself gives nothing; the reflected shot gives Seraph a shot's meter (+120
  kinetic) when it lands, a blocked hit's (+60) when it is blocked.
- Whiffed, it is a 40-frame commitment with nothing to show: a read of the other's shot, not a
  panic button.

#### Wing Ward against each shot

A reflected shot keeps its kind, its box (size and height) and its strength, and changes these:

- **Owner**: Seraph's side. It moves from the thrower's shot slot to Seraph's (`fight.shot[s]`),
  so the thrower may fire again at once (its move permitting), and Seraph may not until it is gone.
- **Direction and speed**: reversed, **×1.25** (at most 0.45 m a frame). A shot reflected again
  (a mirror match) is turned and sped up again, up to the same cap.
- **Life**: starts again: the full life of its kind (the wave 150 frames, an orb 130, a bolt 180).
- **Damage**: its own hit (the table below), scaled in a combo like any hit; its meter is Seraph's.
- **Drawn as light** (`Shot.refl`): white-gold, whatever it was.
- **A bolt becomes a Mark**: a reflected Hex Bolt **neither curses nor stays a hex**: it becomes a
  Mark of Judgement (the Mark's hit, 45 and chip 9, and the mark) with the Hex Bolt's box. A
  reflected Mark bolt stays a Mark, now the reflector's: it marks its first thrower. The wave and
  the orbs are force, not hexes: a reflected wave or orb marks nothing.

| Shot (thrower) | Strength | Comes back at | Box | On hit | Notes |
|---|---|---|---|---|---|
| Kinetic Wave (the Hero) | 2 | 0.275 m a frame | x ± 0.8, y 0–3 | 80, chip 16, hitstun 20 | a low wave of light along the floor: the Hero blocks it, Parries it, jumps it, or fires a new wave into it (2 against 2: both go) |
| Volt Orb, tapped (Beam) | 1 | 0.30 | x ± 0.7, y 4.8–6.6 | 70, chip 14 | Beam's next tap trades with it, a charged orb beats it |
| Volt Orb, charged | 2 | 0.375 | x ± 0.9, y 4.8–6.6 | 90, chip 18 | |
| Volt Orb, full | 3 | 0.45 | x ± 1.1, y 4.8–6.6 | 120, chip 24, knockdown | the strongest thing Seraph can send: only another full orb stops it |
| Hex Bolt (Shadow) | 1 | 0.175 | x ± 0.8, y 4.5–7.5 | 45, chip 9, **marks Shadow** | no curse: the hex is lost in the light |
| Mark of Judgement (a Seraph) | 1 | 0.20, then 0.25, 0.3125 ... to 0.45 | x ± 0.8, y 5.0–7.4 | 45, chip 9, **marks its first thrower** | the mirror match's rally: each ward sends it back quicker |

The Twins, Tank and the Double-blade Hero have no shots: against them the Wing Ward catches
nothing. The Parry, the Void Step and Tank's armour treat a reflected shot as any shot of its kind
(caught, passed through, absorbed).

### Grab and throw (Y): Heaven's Arc

`grab`: startup 5, active 2 (the catch box x 1.0–3.6, y 2–10: both fists, the Hero's reach), 7
frames; a miss plays `grab_whiff` (22). Breakable as every Y grab (Y within 10 frames). On a
catch, `throw` (40 frames) on Seraph and **`thrown_vault`** (40, the Vault Throw's victim move,
over the head) on the other: Seraph grabs, beats its wings, carries the other over its head and
slams it down on the far side. **The sides swap**: Phantom Grip's swap, over instead of under.

| Frames | Seraph | The other (the fight places its root, from Seraph's root: + in front) |
|---|---|---|
| 1–8 | both fists close on the other's shoulders (the break window: 1–10), the wings lift | 3.0 m in front, lifted to 1.0 m |
| 9–16 | **two wing beats** (down-strokes on 10 and 15): Seraph rises **2.0 m** (root motion, 0.25 m a frame) and heaves the other up in front of it | from 3.0 to 2.0 m in front, lifted from 1.0 to 6.0 m above Seraph's root |
| 17–24 | **over the top**: Seraph's back arches, the arms swing the other over its head, the wings spread | from 2.0 m in front to 3.0 m behind, over the top: 9.0 m above Seraph's root on 20–21, 6.0 m on 24 |
| 25–29 | **the slam**: Seraph drops back to the floor (root motion 2.0 m down over 25–28), driving the other down behind it | from (−3.0, 6.0) to (−3.5, 0): on the floor 3.5 m behind on 29 |
| 29 (`release`, 28 from 0) | | **120 damage, knockdown**; the other bounces on about 1.3 m (−0.08 m a frame back, launch 0.30): it lands about 5 m behind Seraph |
| 30–40 | recovery: Seraph straightens and folds the wings, still facing the way it faced; it turns on returning to neutral (the Vault Throw's way) | |

- **With Seraph's back to a wall** there is no room behind it: Seraph's wing beats carry it
  forward instead. The fight moves Seraph's root forward by however much the other's spot behind
  it (3.5 m) is past the wall's limit (the stage's half-width less the other's push box), at most
  5 m, evenly over frames 9–24, so the other lands at the wall and **the sides still swap**: the
  corner escape. Phantom Grip's wall case mirrored (there the other is moved; here Seraph moves).
- **With the other's back to a wall** (Seraph cornering it), the throw takes it out of the corner
  and leaves Seraph in it: the swap is the point of the throw, not damage. Cornering, Seraph should
  chain instead.
- **With Seraph's back to an open edge**, the edge counts as a wall for the carry, but the other
  is held over the deck up to the edge itself (its root at most at the edge, not its push box
  short of it, as a wall's limit is) and Seraph moves forward as at a wall; the release then
  carries the other its last 1.3 m over the edge: **within about 5 m of an open edge, Heaven's Arc
  rings the other out**, as the Vault Throw does from there (scenario 179: 1 m from the edge it
  rings out, 6 m from it the other lands 1.6 m short). Held at the push box's lip instead, the
  1.3 m bounce would leave every mech on the deck (their push boxes are 1.4 to 2.4 m).
- Thrown mechs are not hittable, and neither is Seraph during the throw (every throw's rule).
  120 damage: the Vault Throw's; less than the Hero's 140 and Tank's 150, more than the Grip's 110.

### Super (A + B): Judgement

**The flash** (frames 1–40: the world freezes, Seraph alone moves): it plants, raises the right
fist straight overhead, the wings spread wide (to the spread pose by frame 24) and the **halo
lifts on its joint** (x 0 to 60 over frames 8–30, 0.9 m), flaring white-gold (the flare is the
effect's); the stage brightens toward white-gold. Then:

| Frames | |
|---|---|
| 41–48 | **the follow**: each frame the fight takes the other mech's root x as the column's centre (the leader's, twin A, for the split Twins), a ring of light on the floor there going with it; **on 48 it locks** (the event `Column`). From then the column does **not** track: it falls where the lock was. (The balance pass, 2026-10-14: it locked on 41, `SER_FOLLOW` 8 in `seraph.akr`) |
| 41–48 | startup (8): Seraph brings the raised fist down and forward, pointing at the target, the arm level by 48; the light gathers above the target |
| 49–58 | **active (10)**: the column slams down: a hit box **x lock ± 2.5 m, y 0–20 m** in the world, wherever Seraph stands |
| 59–92 | recovery (34): the arm comes down, the wings fold (by 80), the halo settles back on the helm (x 60 to 0 over 59–80), the stage's light fades with the column |

- **Invulnerable from frame 1 to 49** (the flash, the startup and the column's first frame).
- **Can it be walked out of?** No. The column falls 8 frames after the freeze, and it follows the
  other mech until the frame before: to leave it a mech must move more than 3.7 m (the column's
  half-width, 2.5 m, and at least 1.2 m of its own hurt box) in the one frame between the lock and
  the column, and the quickest walk (the split Twins', 0.10 m a frame) covers 0.1 m.
  Nothing jumps out either: the column reaches 20 m up.
  **Block it** on the flash (chip), or be invulnerable or gone through frames 49–58: the Void
  Step started on the first frame after the flash is gone on 47–58 and escapes; the Rising Arc
  (invulnerable 7), Eclipse Rise (9) and Ascension (8) are not invulnerable long enough; Shadow
  Sneak's shadow is hittable at the floor and is caught. A mech knocked down or getting up through
  frames 49–58 is not hittable and is missed. Anything mid-move anywhere on the stage is hit.
- **Damage**: **280**, knockdown, the super's hitstop (20), launch 0.60; scaled in a combo like any
  hit; then **×1.5 against a marked mech: 420** (182 and 273 as a chain's third hit). The bonus
  does not stack with the antimatter debt's 25 % (the owner, 2026-10-14): a marked mech in debt
  takes the larger of the two, ×1.5, so 420 at most.
- **Chip**: 70 through a block (which can finish a round), **not raised by the mark**: the mark
  rewards landing it, and blocking is the answer. Blockstun 20; −24 on block (measured), at whatever
  distance the column fell. From far, little can punish that (the Momentum Drive, the Raikō
  Overload, Antimatter Rend, a held Sneak or Dive); up close, anything.
- Not parried (no super is: the owner's rule), never absorbed by Tank's armour (no super is), not
  caught by a mirror's Wing Ward (it is not a shot). It hits one twin of the split Twins (the
  leader if both are in the column).
- One bar, as every kinetic super (no debt). What it is for: the punish for anything left unsafe
  anywhere on the stage, and the reason to land the bolt first.

### Chains

The shared chain: Jab, then Lunging Straight, then a special or the super. **The Mark of Judgement
combos from a Lunging Straight** up close (the bolt starts 3.5 m out and touches at once): the
chain's payoff is the mark. Ascension combos from a Jab close up. **Judgement combos from the
Jab or the Lunging Straight**: the column falls 8 frames after the freeze, inside their hitstun
(scaled: 182 from the chain's third hit, 273 marked). The Seraph Dive never combos (too slow). The
Wing Ward can be cancelled into (after a blocked Lunging Straight, against a mech that answers with
a shot).

### Frame advantage (measured)

`tests/run.sh 17` (mx-seraph-fight), against a standing Hero, from the stand-in timings: Jab −3 on
block / +1 on hit, Lunging Straight −6 / +1, Reaping Kick −10 / knockdown (+44), Mark of Judgement
−11 / −7 at 6 m (safe from further out), Seraph Dive −10 / knockdown (+50) from 7 m, Ascension −22
/ knockdown (+48), Judgement −24 on block with the column 8 m off (knockdown, +43, on a hit). The
Wing Ward has no contact. To measure again once the animations land.

### Balance intent

An honest answer character. Where Shadow sets traps, Seraph answers what the other does: a shot
comes back (the Ward), a wave or a mine is flown over (the Dive), a jump-in meets the Ascension,
and a whiff anywhere on the stage meets Judgement. Its weaknesses are as plain: short fists (it
must get in to poke, and the Hero's Tip Thrust and Beam's Arc Jab outreach it), slow specials that
any shot or anti-air takes, a ward that does nothing against strikes or against mechs without
shots, and a super that is a full kinetic bar (about ten landed hits). The mark is its plan: land
the slow bolt, then threaten 420 for six seconds; the other must respect the flash and block.
Health 1,000, between Shadow's 900 and Tank's 1,150; its hits are Shadow's weight, its specials a
little heavier.

- **The Hero**: the Kinetic Wave feeds the Ward (it comes back at 0.275 m a frame) and the Dive
  flies over it, so the Hero's zoning is weak here; the Hero wins up close at the tip of its sword,
  and its Parry catches the Dive, the Ascension and the bolt. Even, slightly Seraph's at range.
- **The Double-blade Hero**: rushdown against short fists. The Void Step passes the bolt and is the
  one way out of Judgement; the Antimatter Slide passes under the Jab, the Lunging Straight and the
  bolt (the Reaping Kick and the Ascension, its box from 3 m up, catch it). A marked Double-blade in
  debt takes 420 from Judgement, as any marked mech (the bonuses do not stack). Close to even.
- **Beam**: every orb is reflectable, a full orb comes back at 0.45 m a frame and knocks Beam
  down, so Beam must charge less and use the Arc Lance (a strike: not reflected, and it stops the
  Dive). Judgement punishes the Reaction Prime's 30 exposed frames from anywhere. Slightly
  Seraph's; the matchup Momentum's angel was made for.
- **Tank**: nothing to reflect; the armour eats the Jab, the Lunging Straight, the Dive and the
  Ascension, and the Atomic Clinch outranges the fists. Seraph wins from far (the bolt, which marks
  through armour, the Dive punishing a Bulldozer), Tank up close. Judgement on a marked Tank (420)
  also fills most of the reactor (3 a point). Even.
- **The Twins**: no shots, so the Ward is dead weight; the split twins' pressure and the partner's
  late copy beat slow specials, and the Low Roll goes under the bolt, the Jab and the Lunging
  Straight (the Reaping Kick answers it). The mark stays on through switching. Slightly the Twins'.
- **Shadow**: the mirror of the design. The bolts trade (1 against 1); a warded Hex Bolt marks
  Shadow; the Dive flies over the Rift Mine and the Sneak's shadow; but the Siphon takes all of
  Seraph's kinetic meter while it lasts, delaying Judgement, and Eclipse Rise (9 frames
  invulnerable, 7 m reach) takes the Dive. Even: the target is 50 %.
- **Seraph** (the mirror): the bolt rally, each Ward sending it back quicker; whoever wards last
  marks the other.

**Measured, CPU against CPU** (mx-seraph-fight; `tests/balance/run.sh 8 B`, level 2 against level
2, 10 matches a pairing on the hangar, the sides swapped every match, Seraph played from its
stand-ins): Seraph won 13 to 14 of the 60 matches against the other six base mechs (0 to 4 of 10
against each over four runs, 0 or 1 against the Twins); Shadow, measured the same way, won 22 of
50. The gap is mostly the super: in 10 matches Shadow's Total Eclipse, from zero on the antimatter
meter, came 36 to 57 times and dealt 6,300 to 12,800, where Judgement, a full kinetic bar, came 15
to 19 times and dealt 3,700 to 4,100 (7 times against Shadow, whose Siphon takes its meter); and
Shadow Sneak lands far more than the Seraph Dive (the CPUs block a Dive they see coming). The
numbers are the owner's to tune in play. On its own animations, before and after [the balance
pass](#balance-pass-2026-10-14-gamma-and-seraph)'s follow: 18 of 60 (4 of 10 against the Hero, 3
against the Double-blade Hero, 3 against Beam, 5 against Tank, 1 against the Twins, 2 against
Shadow), the same matches to the frame: the level-2 CPUs block on the flash and stand still, so
the follow never moved a column.

### The CPU (Seraph)

Seraph's own CPU replaces `cpu_as_shadow` for it (`cpu.akr`, built in mx-seraph-fight: its
section at the end, `seraph_neutral`, `seraph_chain`, `seraph_punish` and `seraph_shot`), with
lines in `cpu_think` where Shadow has them:

- **Neutral, far** (outside the other's forward attack plus 2 m): the Mark bolt when the other is
  not marked (or the mark has under 2 s left) and has no shot out; against a mech with a stronger
  shot, only while it is down or busy. Against the Hero and Beam at range, wait for their shot and
  **ward it** (down + B when the shot will touch in 6 to 14 frames: the ward's 4 frames of
  startup, then its 20, with a margin) at `lv.special` × 5 (15 % at level 0 to 60 % at level
  3; `lv.special` alone, 3 to 12 %, would leave the ward unused), else block it. From mid range
  and far, the Dive to close when nothing is coming (`lv.special` × 3).
- **A wave on its way**: the Dive over it when it will touch in 19 to 22 frames, at `lv.aa`, else
  ward or block. (Not 13 to 24: the hop carries Seraph 1.5 m toward the wave before its root
  clears 3 m on frame 12, so a wave closer than 19 frames meets the legs.) An orb or a bolt:
  ward or block (none of Seraph's moves go under).
- **The Dive held**: B held while the distance to the other is more than about 7 m (the dive's
  1.8 m and the fist's 5.5 m): the glide stops at the other anyway.
- **Chain ender**: the Mark bolt if the other is not marked; Judgement if marked and the meter is
  full (`super_wise`; on an unmarked mech now and then too); else the Ascension from a Jab up
  close, or nothing on block. Up close the jab only within its reach (else the straight).
- **Anti-air**: up + B against a jump coming within about 9 m.
- **Judgement**: on a whiff or an unsafe move anywhere on the stage (not only within 12 m, the
  general punish's range), preferring a marked mech; on any move under way at a decision in
  neutral (the column falls before it can block); on Beam's Reaction Prime; never on a mech
  knocked down or getting up through the column's frames.
- **Throws**: the general rule, and Heaven's Arc whenever its back is within 6 m of a wall (the
  corner escape) or of an open edge with the other in reach (the ring-out).
- **Against Seraph** (the other CPUs): block on Judgement's flash at any distance (the general
  "an attack starting in range" test uses the forward attack's reach, which a column ignores), and
  more so when marked; fire shots less often at a Seraph standing within ward reach of them
  (the Hero's far wave, Beam's orbs, Shadow's bolt; `shadow_neutral`'s `open_ok` and `beaten`
  treat the Mark bolt as strength 1, as the Hex Bolt).

### Reactions and the rest (Seraph)

As the shared list below, with Seraph's lengths: `idle` 60, `walk_f`, `walk_b` 44, `crouch` 8,
`jump` 40, `land` 8, `block` 4, `hit_high` and `hit_low` 20, `hit_air` 30, `knockdown` 32, `getup`
20, `ko` 90, `win` 120, `intro` 90, `grab` 7, `grab_whiff` 22, `grab_break` 20, `throw` 40, `thrown`
44, `thrown_vault` 40, `thrown_slam` 56. What differs from the other mechs is how it falls:
**Seraph lands face down**, its wings folded on its back, never flat on its back on its wings
([For the animators](#for-the-animators-seraph)).

### For the animators (Seraph)

Everything in `anims/seraph/` becomes Seraph's own; until a move is done it stays Shadow's
placeholder. Frame numbers here count from 1 as the tables do; the files count from 0.

- **The rig** (`models/seraph/seraph.rig.json`): Shadow's skeleton and offsets, the fists the
  weapon parts (keep `weapon_r` and `weapon_l` at 0: `"still"`; a fist does not open), plus
  **`wing_l`, `wing_r`** (the torso's: folded at 0; spread at x −122, y 50, z −24 on the left, the
  right's y and z negated; range x −130..10, y −10..65, z −35..10, mirrored) and **`halo`**
  (the head's: x 0..60 lifts the ring 0.9 m straight up; 60 is the rig's `halo.raised`). The wings
  are a pair of flat plates in the wing's own Y-Z plane, hanging behind the back to the calves when
  folded, 2.6 m deep behind the wing pack: anything that lays the back on the floor puts them 2 m
  into it. The wings and the halo have no hurt boxes. **The ward's pose is past the listed y
  range**: the plates point back (+Z) at 0, and only a turn about y of about 120° brings them round
  the sides to the front (−Z). The ranges are the model's notes (`make_seraph.py`'s `RANGES`, in
  the rig's `role` and `range` text), not limits the kit checks; widen the wing's to y −10..130
  there when the ward is made, and check the plates against the arms and thighs with `verify`'s
  `parts` check.
- **The guard** (new): the boxer's guard of the intro paragraph: upright, the right fist leading
  at chin height about 3 m out, the left at the jaw, the elbows in, the knees soft, the wings
  folded, the halo down. It is the rig's `poses.guard`, written by `make_seraph.py` (the model's
  generator: change it there and regenerate); every move starts and ends in it.
- **Wings and halo, in every move**: folded (0) and down (0) unless a move below says otherwise.
  The wings settle and lift a few degrees with the body (x 0 to −5) rather than hang dead: on the
  walk's plants, the idle's breath, a hit. "Spread" means the rig's spread pose; "half open" about
  x −60, y 25, z −12 on the left.
- **Marks** (from 0): `cancel` on `atk_n` 3–10 and `atk_f` 12–21; `invuln` on `sp_u` 0–7 and
  `super` 0–48; `flash` on `super` 0–39; `release` on `sp_n` 16 (the bolt) and `throw` 28 (the
  slam); `charge` on `sp_f` 25 (the glide's hold); **`ward` (new) on `sp_d` 4–23**; `riposte` on
  `sp_d` 40 (the fling); `step` on the walks' plants, `sp_f` 32 (touchdown), `sp_u` 38 (landing).
  No `hide` and no `nopush` anywhere: Seraph never vanishes.
- **Root motion**: `atk_f` 2.0 m over frames 3–11 (Shadow's); `sp_f` 2.0 m forward and 4.0 m up
  over 7–14 (the hop), **none after it** (the fight moves the root through the glide and the
  dive); `sp_u` 1.2 m forward over 2–7, 6.0 m up over 8–15, 6.0 m down over 16–38 (ease in);
  `throw` 2.0 m up over 9–16 and 2.0 m down over 25–28; none in `sp_n`, `sp_d` and `super`.
- **Boxes**: the hit boxes in the tables, following the right fist (the knuckle guard: its front
  is the point (0, 0.14, 0) in `weapon_r`'s frame, the rig's `fist.front`), the right foot and
  shin (`atk_d`), both fists (`atk_air`, `throw`'s grab). `sp_f`: crouching boxes on 1–6; on the
  glide frames the hurt boxes follow the parts with **nothing below the root** (the legs trail
  back level with it) and the push box x ± 1.4, y 0–7. `super`: a placeholder hit box `hit` 0,
  x 0–5, y 0–20, on frames 49–58: the fight moves it to the lock.

| Move | Length | Must show | Wings and halo |
|---|---|---|---|
| `idle` | 60, loop | the boxer's guard breathing: the chest rising, the fists drifting an inch, the weight shifting between the feet | the wings lift x −4 on the in-breath; the halo bobs x 0..4 |
| `walk_f`, `walk_b` | 44, loops | a short gliding boxer's step, the guard steady; `step` on 0 and 22 | settle x −3 on each plant |
| `crouch` | 8 | the knees bend, the guard kept up | folded |
| `jump` | 40 | Shadow's timing: crouch 4, launch, tuck at the top, extend for landing | half open at the top (frames 14–26), folded by 38 |
| `land` | 8 | the knees take it | folded, a settle |
| `block` | 4 | both forearms up in front of the face and chest, elbows in | the wings swing a third of the way round (y 40 on the left) |
| `hit_high`, `hit_low` | 20 | the torso snaps back, the head follows, back to the guard | the wings jolt open (x −12) and settle |
| `atk_n` | 17 | the Jab above; the fist at about 7.2 m on 4–5, its front 3.2 m out | folded |
| `atk_f` | 36 | the Lunging Straight above | swing back with the lunge (x −15), settle in the recovery |
| `atk_d` | 36 | the Reaping Kick above | flare 10° as it rises (24–32) |
| `atk_air` | 26 | the Double-fist Dive: fists clasped overhead on 1–7, driven down and forward by 8, held until landing | swept back (x −40) from 8 |
| `sp_n` | 41 | the Mark of Judgement above; the right fist's front at about x 3.5, y 6.2 on frame 17 (the bolt's start) | folded; halo x 0 to 20 on 1–16, back to 0 by 30 |
| `sp_f` | 54 (+ the hold on 26) | the Seraph Dive's table; the glide pose on 15–26. While B is held the fight holds frame 26 itself (the pose stands still, the effects stream off it), so 26 must be the best glide pose | lift x −30 by 6; spread by 12; a flutter of x ± 3 on 15–25, spread on 26; half folded on 27–28; folded by 48 |
| `sp_u` | 43 | Ascension above | lift on 1–7; spread on 12–15, one beat (down-stroke on 14); fold over 16–36; halo x 30 at the top, 0 by 30 |
| `sp_d` | 52 (40 when nothing is reflected) | Wing Ward's table; frame 40 must be the guard (the move ends there) and so must 52 | wrap to about (−20, 120, 0) by 4, held 5–24, folded by 40; on 41–44 snap to spread, folded by 52; halo down |
| `grab` | 7 | both fists reaching, the catch box above | folded |
| `grab_whiff` | 22 | the fists closing on nothing, a stumble | a flick open and closed |
| `throw` | 40 | Heaven's Arc's table; the fists stay on the other's shoulders where the fight places it | lift on 1–8; beats on 10 and 15 (x −122 up, −40 on the down-stroke); spread on 17–24; swept down on 25–29; folded by 40 |
| `grab_break` | 20 | both arms shove | open half and fold |
| `thrown`, `thrown_vault`, `thrown_slam` | 44, 40, 56 | follow the thrower's hands as every mech's; **end face down** (hit_air's last frame follows them) | folded, clear of the floor |
| `hit_air` | 30, the last frame held | thrown up and back, then **turning over** (about 150° forward, through frames 12–24) so the held last frame is face down, arms forward | half open as it tumbles, folded on the back by 24 |
| `knockdown` | 32 | lands **face down** on the forearms and knees, a bounce on 4–8, still | folded on its back, clear of the floor (no `floor_allow`) |
| `getup` | 20 | pushes up on both fists to a kneel and stands into the guard | half open on 6–14 as a counterweight, folded by 20 |
| `ko` | 90 | falls forward onto its face and stays down, the head turned to the camera | the wings droop half open across its back (x −70, y 40, z −10 on the left); the halo stays on the helm (the effect dims it) |
| `super` | 92 | Judgement's tables: the fist overhead on the flash, pointing at the target on 41–48 (the arm level), held through the column, down in the recovery | spread by 24, held to 58, folded by 80; halo x 0 to 60 over 8–30, held to 58, back to 0 over 59–80 |
| `win` | 120 | Judgement's pose for the cover: the right fist raised overhead, the left at the chest, then a slow bow of the head | spread by 30 and held; halo up (60) by 40 |
| `intro` | 90 | descends into the booth's spot from above on spread wings (the pelvis `offset` up 8 m on frame 0, down to the guard's by 30; the root stays on the floor), lands on one knee, rises into the guard | spread on 0–30, folded over 40–70; halo up, then down |

- **Lying down.** The knockdown, the KO, the get-up and the end of `hit_air` and the throws'
  victim moves put Seraph **face down** (its back up), so the folded wings stand up off its back
  instead of 2 m into the floor; `verify`'s `floor` check must pass with **no `floor_allow`** for
  the wings. `hit_air`'s last frame is also where a thrown Seraph lands (the throws' release jumps
  the victim there), so `thrown`, `thrown_vault` and `thrown_slam` end in it. The shared table's
  "flat on its back" does not apply to Seraph.
- **The cover** (`cover.akr`'s `COVER_POSE[Seraph]`, now 119 of Shadow's win): the frame of the
  new `win` where the fist is up, the wings spread and the halo raised (about 60).
- **The Lunging Straight and the Jab** keep the reach phase 1 measured; only the Jab's height
  changes (its fist's box from y 8.6–9.8 to 6.6–7.8). Keep `design` boxes in the files so
  `verify` checks them.
- **As animated** (mx-seraph-anim): every length, mark frame and root motion above is in the
  files as written; the guard is `make_seraph.py`'s `STANCE`, a boxer's (`GUARD_DROP` 1.15, the
  right fist's front at x 3.2, y 9.4), the wing's range text says y −10..130 and the rig names the
  ward's angles (`wings.ward_l`, `ward_r`). Where the files differ from the words above:
  - The Jab's arm is not straight: shoulder to knuckles is 6.3 m, so a straight arm at 7.2 m
    reaches about 6 m. To keep the reach phase 1 measured it is a short punch from the ribs, the
    elbow tucked in and the forearm and fist level; its boxes span x 1.6–3.2, y 6.6–7.8. At
    that height it meets the lead forearm Shadow and the Hero hold out in their guards (Shadow's
    reaches 5.4 m from its root at y 5.9–8.0, the Hero's 4.0 m at y 5.5–7.6), so at 6 m apart
    the jab lands on the arm, out to about 8.7 m against Shadow and 7.3 m against the Hero:
    scenarios 160 and 161's "the jab misses at 6 m" (phase 1's, made for the face-high fist)
    changes with the fight's part. The
    Ascension's fist ends over the head with the forearm upright (x 0.6–4.3, y 3.3–14.1), the
    Lunging Straight's is straight (x 2.7–6.8, y 6.9–8.2).
  - The Wing Ward's wrap is the spec's (−20, 120, 0): the wings hinge behind the shoulders and
    the plates are 2.6 m deep, so at 120 they stand at the sides, their faces forward, rather than
    closing in front; the effect's sheen covers the front. Wider (150) would bring them no nearer.
  - The Reaping Kick drops the pelvis 2.3 m, not 3: the rear foot is drawn in under the hips
    (frames 0–5) and steps back in the recovery, or the rear knee goes into the floor. Its boxes
    span x 1.4–6.2, y 0.2–2.2 (the lower shin and the front of the foot as the leg comes round).
  - The Seraph Dive's straight reaches x 2.1–5.6, y 1.4–5.0 (within `verify`'s 0.5 m of the
    table). In the dive (26–31) the legs fold up behind, about 0.5 m below the root at most
    on 31, so they stay off the floor while the fight brings the root down.
  - Knocked down, Seraph lies on its forearms and knees (the hurt boxes 4.5 m tall), not flat;
    the KO goes on to lie flat. `hit_air`'s last frame has the pelvis 2.1 m above the root.
  - `thrown_vault`: from the top of the arc (17) the victim swings on head first and comes down
    face down on 28, so on 20–26 its shoulders leave the thrower's fists; `thrown_slam` turns it
    over on the slam (28–33). The three throws' victims are Shadow's to their slam (`"base"`).
  - The cover (`COVER_POSE`) can stay 119: every frame of `win` from 40 on has the fist up, the
    wings spread and the halo at 60.

### For the effects and sound (Seraph)

Light gold and white-gold, Momentum's angel: `SRX_GOLD` 0x80E0FF (0xBBGGRR: light gold), `SRX_CORE`
0xDCF8FF (white-gold), `SRX_WHITE` 0xFFFFFF; additive sprites on fx.akr's effect slot and its
particles, as `shadow_fx.akr`'s. A new file `seraph_fx.akr`, called with a line each from
`game.akr`, `fx.akr` and `hud.akr` as Shadow's is. The budget: Seraph's effects within Shadow's
(about 76,000 cycles in `prof_fx` with fx.akr's at the worst frame; scenarios 162 and 168 re-run).

**Anchors** (part frames, from `anim_part()`): the right fist's front, (0, 0.14, 0) in `weapon_r`'s
frame (`weapon_l` for the left); the core, (0, 2.25, −1.08) in the torso's frame (the red gem on
the sternum); the halo's centre, (0, −0.45, −0.78) in the halo's frame (the rig's `halo.centre`);
each wing's tip, about (−0.7, −5.6, 2.4) in `wing_l`'s frame and (0.7, −5.6, 2.4) in `wing_r`'s
(the long flight plate's point: check it on the preview).

| Effect | When (frames from 1) | Anchor | What |
|---|---|---|---|
| Fist trails | the active frames of `atk_n`, `atk_f`, `atk_air`, `sp_f` (29–32), `sp_u` (8–15) | the fist's front, a short segment back along the forearm (the points 0.14 and −0.9 on the knuckle guard's +Y) | a short white trail edged gold, in place of fx.akr's no-trail branch for Seraph (`fx_update`) |
| The bolt's gathering | `sp_n` 1–16 | the right fist's front | gold motes drawn in to the fist, a glow growing to 1.5 m |
| The Mark bolt | while out | the shot (x, the middle of y0–y1) | a white-gold core, a gold glow 2.4 m across, a four-point glint turning slowly, gold motes falling off behind it; released with a flash at the fist |
| The mark | while `Fighter.mark` > 0 | the marked mech's core (its torso) and 1.5 m above its head | the gold sigil at the chest pulsing once a second; the ring over the head turning; motes rising; both flickering in the last 60 frames. A new mark: a gold ring bursting out from the chest; a refresh: the same, half the size |
| The HUD's mark | while marked | the marked mech's meter and health bar | MARKED, the time bar, the health bar's shine, Seraph's gold SUPER pulse ([the mark](#mark-of-judgement-sp_n-and-the-mark)) |
| The hop and the beats | `sp_f` 7, `throw` 10 and 15, `sp_u` 14 | the floor under the root | a downdraft: a ring of dust pushed out along the floor, 6 m wide |
| The glide | `sp_f` 15 to the dive | each wing's tip | white streaks off the tips and the trailing edges, a few motes a frame |
| The dive and touchdown | `sp_f` 27–33 | the fist; the floor at 33 | a white streak along the dive; a dust ring on landing |
| Ascension's flare | `sp_u` 12–16 | the wing tips, the fist | a burst of light at each wing tip on the beat (14), a vertical arc of light along the fist's path |
| The ward | `sp_d` 5–24 | in front of the body: x +1.5, y 6 from the root | a tall curved sheen of light over the wrapped wings, 11 m high, flickering, fading over 4 frames at the end |
| A reflect | the `Reflect` event | the contact point | a white flash 4 m across, a gold ring, and the shot turned to light (below) |
| A reflected shot | while `Shot.refl` | the shot | drawn as light at its own size and height: a low wave of light (the wave), a gold ball (an orb, its level's size), the Mark bolt (a bolt). Drawn before fx.akr's wave and `beam_fx_orb` branches (`sh.refl` first) |
| Heaven's Arc's slam | `throw` 29 | the other's root | a heavy dust ring and debris, as the throws' |
| Judgement's flash | `super` 1–40 | the halo's centre; the core | the halo's flare: a gold ring growing from the halo to 4 m and a white glow, pulsing; the core lit white; the stage brightened to white-gold (a positive colour offset through `layer_offset`, as Total Eclipse's dark: `seraph_fx_offset`) from frame 1 to the column's last active frame (58), fading over 59–70 |
| Judgement's lock | `super` 41–48 (following the other until the `Column` event on 48) | the floor at the lock | a gold ring opening to 5 m wide on the floor, a rain of motes falling into it from the top of the screen; the ring goes with the other mech until the lock (`srx_fixed`) |
| The column | `super` 49–58, fading over 59–70 | the lock, x ± 2.5, from the floor to the top of the view | a white-gold beam slamming down in 2 frames, a bright core 2 m wide, the edges flickering; dust thrown out at its foot; the camera's shake on the hit as a super's |
| Knocked down | `knockdown`, `ko` | the halo | the halo's glow dims (the halo part is emissive: dim it to a third while Seraph lies) |

**Sounds** (`sfx.akr`; new samples by `tools/gen_mechexpo_audio.py`; the priorities in `sfx.akr`'s
header). Until each is made, a stand-in from the existing ones (named):

| Sound | When | Priority | Stand-in |
|---|---|---|---|
| `SFX_MARK_CAST`: a bright chime over a rush of air | the bolt's release (`Shot` event: `sfx_shot(Seraph, ...)`) | 6 | `SFX_BEAM_ORB` pitched up 1.4 |
| `SFX_MARK_HIT`: a single struck bell, a long tail | the `Mark` event (a new mark; a refresh quieter) | 6 | `SFX_METER_FULL` pitched 0.8 |
| `SFX_WARD`: plates sweeping round, a soft metallic shimmer | `sp_d`'s first frame (the Swing event has no hit box: poll the move) | 4 | `SFX_VOID_IN` pitched 1.3 |
| `SFX_REFLECT`: a ringing clang and a rising shimmer | the `Reflect` event | 7 | `SFX_BREAK` pitched 1.2 |
| `SFX_WING_BEAT`: a heavy whump of air | `sp_f` 7, `sp_u` 14, `throw` 10 and 15 | 4 | `SFX_LAND` pitched 0.7 |
| `SFX_GLIDE`: wind over the plates (a loop, `sfx_hold`) | every glide frame (`sp_f` 15 to the dive), the slot of Seraph's side | 3 | `SFX_BEAM_HUM` pitched 0.6, quiet |
| `SFX_DIVE`: a descending whistle | `sp_f` 27 | 4 | `SFX_SWING_HERO` pitched 0.8 |
| Fists | the Swing event (`sfx_attack(Seraph, mv)`): the jab, the straight, the kick, the dive's straight, the Ascension | 4 | the combined Twins' fists |
| The super | `sfx_super(Seraph)`: the kinetic charge-up, with a rising choir-like pad for the halo | 9 | the kinetic charge-up alone (as now) |
| `SFX_COLUMN`: a roar falling from high to low, ending in an impact | the column's Swing (`super` 49); its lock (`Column` event) a thin rising tone | 9 | `SFX_SUPER` |
| Steps | the walks | 2 | `sfx_step_of`: lighter than the Hero's (pitch 1.1) |

The events (appended to `enum Ev`, so the others keep their numbers): `Mark` (side: Seraph's; x, y:
the marked mech; power 1 a new mark, 0 a refresh), `Reflect` (side: the warding side; x, y: the
contact; power: the shot's strength), `Column` (side: Seraph's; x: the lock). `game.akr`'s
`sound_event()` and `fx_event()` take them.

### Engine work needed (Seraph)

What the code could not do in phase 1, and where it plugs in. Items 1 to 10 and 12, and the
cover's `COVER_POSE` of item 11, are done (mx-seraph-fight); item 11's drawing and sound are the
effects' part. The rule of phase 1 holds: Shadow's code asks `seraph.akr`'s predicates, never
Seraph's name, so each special moved to Seraph's own code by taking Seraph out of one predicate
(`seraph.akr`):

| Predicate (phase 1: Shadow and Seraph) | Phase 2 | Seraph's own, in its place |
|---|---|---|
| `has_hex_bolt` | Shadow only | `has_mark`: the Mark bolt and the mark |
| `has_sneak` | Shadow only | `has_glide`: the Seraph Dive's glide and dive |
| `has_rift_mine` | Shadow only | `has_ward`: the Wing Ward and the reflect |
| `has_phantom_grip` | Shadow only | `has_over_throw`: Heaven's Arc |
| `has_eclipse` | Shadow only | `has_judgement`: the lock, the column, the marked bonus |
| `has_dive` | **Shadow and Seraph** (unchanged) | the Double-fist Dive keeps the Diving Claw's steepened fall |

(`has_shadow_kit` stays true for Seraph through `has_dive`, so `shadow_tick` still runs the dive.)

1. **State** (`fight.akr`): `Fighter.mark: s32` (frames left of the mark, as `curse`);
   `Shot.mark: bool` (a Mark bolt: it marks on a hit) and `Shot.refl: bool` (reflected: drawn as
   light); `enum Ev` gains `Mark`, `Reflect`, `Column` at its end. `start_round()` calls a
   `seraph_round()` (no marks) beside `shadow_round()`; `fight_tick()` calls `seraph_tick(live)`
   after `shadow_tick()` (the mark's count down on live frames, outside the freezes, as the
   curse's; the glide's loop for the sound is polled, not ticked).
2. **The Mark bolt** (`fighter.akr`): `fires_shot()` asks `has_mark`; `shot_fire()` calls
   `seraph_bolt_fire(i, s)` (the constants of [the bolt](#mark-of-judgement-sp_n-and-the-mark));
   `shot_hit()` returns `mark_hit()` for `s.mark`; `shot_try()` calls `seraph_marked(i, j, s)`
   beside `shadow_hexed()` after a hit and after an absorb (`fight.f[j & 1].mark = 360`, the
   `Mark` event). A cursed Seraph's +120 goes to Shadow as any kinetic gain (`meter_add`).
3. **A reflected shot changes owner** (`fighter.akr`'s `shot_try()`, before the Parry's test): a
   shot touching body j that is `seraph_warding(j)` (`has_ward`, `sp_d`, the `ward` mark on its
   frame, not yet reflected) and coming at its front calls `seraph_reflect(i, j, s)`: if
   `fight.shot[j & 1]` is free, copy the shot into it, reverse and scale `vx` (×1.25, at most
   0.45), reset `t` and `life`, set `refl`, turn a `hex` into a `mark` (clear `hex`); free the
   thrower's slot; jump Seraph to the `riposte` frame (`fx[j].riposte = true`, as the Parry does);
   the `Reflect` event. If Seraph's slot is taken, the shot is only removed. A shot reflected this
   frame is skipped by the rest of `shots_tick()` until the next frame (a flag or `t = -1`).
   `advance()` already ends any `sp_d` at its `riposte` frame when nothing was caught, so the ward's
   40 frames need no code.
4. **The `ward` mark**: `MARK_WARD: u32 = 2048` in `anim.akr`, `'ward': 2048` in
   `tools/animkit/move.py`'s `MARKS`, a row in `docs/ANIMKIT.md`'s marks table (the Animation Kit's
   owner). `parrying()` is not used: the ward must not parry strikes.
5. **A held glide with gravity** (`fighter.akr`'s `advance()`, beside the Sneak's line and before
   the charge-frame rule, which would otherwise hold it for `ORB_CHARGE_MAX`): `has_glide(f.mech)
   && seraph_advance(i)`. On the glide's frames (from the frame after the hop's root motion ends to
   the `charge` frame, found in the data once as `shadow_init` finds the Sneak's) it moves the root
   0.40 m forward and 0.02 m down a frame, holds the charge frame while B is held up to 24 frames
   (`f.charge`), and ends the glide early (jump to the dive's first frame) when Seraph's push box
   meets the other's overlapping in height, or at a wall, the separation limit or a lip. On the
   dive's frames it brings the root down by the height left at the dive's start over its 6 frames
   and 0.30 m forward a frame, stopping at the other's push box. Seraph stays out of `fx.air`
   (`grounded()` is false because its root is above the floor), so a hit is an air hit
   (`struck()`), a mine does not snare it (`snare_try()`), and `bound()` does not push it. The
   existing `move_root()` x clamp at the other mech applies only to the hop (it ignores height).
6. **Heaven's Arc** (`fighter.akr`): `catch()` gives the victim `thrown_vault` for Seraph as for
   the Double-blade Hero; `throw_tick()` calls `seraph_hold(i, j, t)` (`has_over_throw`) for the
   table's placement and the wall case (Seraph's root moved forward over frames 9–24 by the
   shortfall, at most 5 m; the lip counts as a wall); the release takes `vx = −ft × 0.08` (the
   default branch; say so explicitly beside Phantom Grip's line).
7. **A column that targets a position** (`fighter.akr`): Seraph's super records the lock
   (`judge_x[side]`, the leader's root x) on its frame 40 from 0, the first after the flash, and
   (since the balance pass) again on each frame to 47, where it locks (`SER_FOLLOW`; in
   `seraph_advance`, with the `Column` event on 47); `load_boxes()` calls
   `seraph_column_box(i)` after `mv_boxes()` to move the super's hit box to the lock in
   fight-local metres (centre `(judge_x − f.x) × facing`, ± 2.5, y 0–20). One hit index, so it hits
   once; the Parry and the armour already skip supers.
8. **The marked bonus** (`fighter.akr`'s `resolve()`, beside the Total Eclipse line): for
   `has_judgement` and `mv == super`, `h.dmg = h.dmg × 3 / 2` when `fight.f[j & 1].mark > 0`; the
   chip is left alone. `struck()` scales it for the combo and skips `meter_damage()`'s debt for
   it (`Hit.nodebt`, set by `seraph_judged()`): the bonuses do not stack, the larger applies.
9. **Seraph's tables** (`seraph.akr`): its own `seraph_hit()` (the numbers of this section:
   jab 50, straight 105, kick 85 knockdown, air 85, bolt 45 / chip 9, Dive 110 / 22, Ascension
   120 / 24, throw 120, super 280 / 70), its own stand-ins (`seraph_tm`, `seraph_root`,
   `seraph_marks`, `seraph_boxes`: this section's timings, so the fight plays before the
   animations land), and `SERAPH_MOVES` (Jab, Lunging Straight, Reaping Kick, Double-fist Dive,
   Mark of Judgement "B (mark: Judgement +50%)" (as "B (marks: Judgement +50 %)" the row is 4 px wider
   than the move list's 234), Seraph Dive "FWD + B (hold: farther)", Ascension,
   Wing Ward "DOWN + B (sends shots back)", Heaven's Arc "Y (swaps sides)", Judgement "A + B, full
   meter").
10. **The CPU** (`cpu.akr`): [The CPU (Seraph)](#the-cpu-seraph); `cpu_as_shadow()` becomes
    Shadow's alone.
11. **Drawing and sound**: `seraph_fx.akr` (new); `fx.akr`'s `fx_update` (the trails' branch) and
    the shots' drawing (`sh.refl` and `sh.mark` before `sh.hex` and `sh.lvl`); `hud.akr`'s
    `hud_draw` (a `seraph_mark_hud(f, s)` line after `shadow_siphon_hud`); `game.akr` (the draw and
    offset lines, `sound_event()` for the three events); `sfx.akr`'s `sfx_shot` (Seraph's own
    branch), `sfx_super`, `sfx_attack`; `cover.akr`'s `COVER_POSE`.
12. **Tests** (`tests/harness.akr`, the next free scenario numbers): the mark (applied by a hit and
    through armour, not by a block or a Parry, refreshed, 360 frames, gone at the round's end);
    Judgement's ×1.5 and its lock (5 m wide, not tracking, escaped by the Void Step, chip not
    raised); the ward against the wave, the three orbs, a Hex Bolt (marks, does not curse) and a
    Mark (the rally's speeds); a strike through the ward; the Dive over a wave and an armed mine,
    stopped by an orb, its held distance; Ascension's invulnerability; Heaven's Arc's swap and its
    wall and lip cases. Scenarios 160 and 161 (the phase 1 checks: five hits of the super, the
    Grip's swap) change with them; the budget (162, 168) is measured again.

### Phase 1: what is in the game now

Phase 2's fight and CPU (mx-seraph-fight) are in: Seraph plays its own moves as this section has
them, its rules in `seraph.akr` and its CPU at the end of `cpu.akr`, and the predicates of [Engine
work needed](#engine-work-needed-seraph) give Shadow's specials to Shadow alone (Seraph keeps
`has_dive`). Its animations are its own since the animators' part landed; until then `seraph.akr`
played a move from its stand-in data (this section's timings, boxes, marks and root motion) whenever
the move's animation was still a placeholder, which it told from the data (now the tests do:
`sv_placeholder` in `tests/harness.akr`, asserted by scenarios 160 and 161): a move that hides the
mech, a Wing Ward without `ward` frames, a length more than 2 frames off this section's, hit boxes
more than 0.6 m off the design (or more than one hit), the bolt timed exactly as the Hex Bolt, or a
guard (the idle, the walks, the crouch, the block) whose hurt boxes reach more than 4.5 m in front
(Shadow's stance holds its claws 6.7 m out; Seraph's guard holds its fist about 3 m out). The rest
of this list is phase 1's record, with what changed in phase 2 said:

- **Real**: the model and rig, the roster row (SERAPH, MR-02, Momentum's emblem, stats `0x2323`:
  power 2, speed 3, reach 2, armour 3; 13.5 m to the top of the halo; the blurb "PALADIN:
  WARD,\nJUDGEMENT", the owner's "THE PALADIN:\nWARDS, JUDGEMENT" being 91 px on its second line
  where the spec sheet has 76: asked), the `STATS` row (1,000 health, the walk, the kinetic
  meter), and the fists' boxes in the jab (x 1.7–3.2, y 8.6–9.8: at face height, so it passes
  over a crouching mech until re-keyed) and the lunge (x 2.6–6.8, y 6.7–8.3), measured with
  `mei_anim.py pose` and checked by scenario 160 against Shadow's.
- **Placeholders**: every animation is Shadow's on Seraph's rig (`anims/seraph/`, each `"base":
  "../shadow/MOVE.anim.json"`, the weapon joints `"still"`, the wings folded, the halo down; lying
  down the folded wings go 2.1 m into the floor, allowed by `floor_allow`); every hit's numbers
  (`seraph_hit` returns `shadow_hit`); the specials and the super are Shadow's (the six
  predicates, all true for Seraph); the CPU plays it as Shadow (`cpu_as_shadow`, with the general
  punish); the fists leave no trails; the bolt's sound is Shadow's; the training move list is
  Shadow's under fist names. (Phase 2's fight replaced the hits, the specials, the super, the CPU
  and the move list; the animations, the trails and the sounds are the other two parts': the
  trails, the effects and the sounds are in, `seraph_fx.akr` and `sfx.akr`, mx-seraph-fx.)
- **The arcade**: Shadow's final is Seraph ("MOMENTUM ROBOTICS PRESENTS ITS COMPETING PRODUCT"),
  Seraph's final is Shadow (defending its title); Seraph's grey copy is packed as every body's is.

## Gamma (Heartland Atomic Company, nuclear)

Heartland Atomic Company's echo of Beam: GAMMA, in the echo slot under Beam (unlocked by clearing
the arcade with Beam), on Beam's skeleton (the Hero's), in army surplus. Where Beam keeps the
other mech out with shots it must aim and time, Gamma **holds** it out: a slow, heavy zoner that
plants its feet behind a ray, pushes whatever walks into it back to the ray's tip, and **gets
stronger when the plan fails**: every hit that gets through fills its reactor (Tank's nuclear
meter), and its answer to a mech that has got in is its super, **Ground Zero**, a blast all round
it. It holds the middle distance with the **Atomic Ray**, a held beam that heats the gun and vents
if it is held too long; it reaches past the ray with the **Rod Shot**, a fast spike that pierces
shots and armour; it answers jumps with the **Geiger Flare**, which dazes; and it turns a hit it
cannot avoid into meter with **Lead Shielding**, a field gun's shield swung out from the left
forearm. Block still stops every attack from either side. In exchange it has the slowest walk on
legs, a jump that hardly clears anything, a jab a frame slower than Beam's, and a ray that leaves
it standing still and open to whatever goes under it, through it or round its heat. Its stance is
Beam's: upright and planted, legs wide, the projector levelled at the other mech, the shield
stowed along the left forearm.

The design is the owner's
([Decided by the owner (2026-10-14): Gamma](#decided-by-the-owner-2026-10-14-gamma-heartlands-ray-gun));
the numbers below are this section's, to tune in play; the normals' and the throw's names, the
health, the walk and this section's interpretations were proposals, which the owner approved as
proposed (2026-10-14; the open questions at the end). Phase 1 (mx-gamma-rig) put the mech in the
game with Beam's moves as placeholders ([Phase 1: what is in the game
now](#phase-1-what-is-in-the-game-now-1)); phase 2 builds this section in three parts at once, as
Seraph's: the fight and the CPU, the animations, the effects and sound. Each
part's list is at the end ([For the animators](#for-the-animators-gamma),
[For the effects and sound](#for-the-effects-and-sound-gamma),
[Engine work needed](#engine-work-needed-gamma)). The fight and the CPU are in (mx-gamma-fight:
`gamma.akr`, the end of `cpu.akr`); where play showed this section's estimates to be off, the
measured number is given beside it.

Code name `Gamma` (`enum Mech`, appended after `Seraph`); shown as GAMMA, model HA-58.
On Beam's rig: the Hero's part ids and joints, the guard of `models/beam/`, **`weapon_r` the ray
projector** (Beam's mount and muzzle, (0, 0.8, −4.4) in its frame, with the Rod Shot's bore under
the lens at (0, 0.3, −4.86)) and **`weapon_l` the lead shield** (stowed along the left forearm at
0; swung out across the fist's line by a turn of 90° about the mount's Y, the concept's
`SHIELD_OUT`). Power source: Heartland's nuclear meter, Tank's: 3 meter for every point of damage
taken, a bar per 400, carried over between rounds, the super at a full bar
([The nuclear meter](#the-nuclear-meter)).

### Movement and stats

| | Gamma |
|---|---|
| Health | 1,050: between Beam's 1,000 and Tank's 1,150 |
| Walk forward | 0.058 m a frame (3.5 m/s): the slowest on legs (Beam 0.062, Tank 0.055 on treads) |
| Walk back | 0.050 m a frame (3.0 m/s) |
| Walk cycle | 52 frames, two steps (3.0 m forward) |
| Jump | 6 frames' crouch, then 40 in the air, 5.6 m high at the top (`jump` is 46 frames): `jv` 0.56, `grav` 0.028 |
| Diagonal jump | 0.13 m a frame across (5.2 m) |
| Landing | 7 frames (10 after an air attack) |
| Push box | 1.7 m either side of the root, 11.5 m tall (7.5 crouching): Beam's |
| Hurt box | follows the parts (Beam's boxes on Gamma's parts); the shield has no hurt box of its own (Lead Shielding's protection is a rule, not a box) |

These were proposals (the owner's "slow, heavy"), approved by the owner (2026-10-14). **Health
1,050**: the nuclear meter only fills by taking damage, so the mech that lives on it needs a little
more health than Beam to live long enough to spend it; Tank's 1,150 stays the roster's most. **The
walk**: slower than Beam's both ways, and its walk back (0.050) is the slowest of any mech on legs:
Gamma does not back away from a rushing mech, it pushes it away (the Ray, Point Blank, Ground Zero).
The walk is Beam's heavy plant with more weight: the body dips under the projector, which stays
level; the jerrycans on the back rock on each plant (a light `step` mark, a heavier thud than
Beam's). The jump is short, late and heavy: 6 frames' crouch, the projector held level throughout,
the landing compressing the knees.

### Attacks (A)

| Move | Startup | Active | Recovery | Total | Damage | Hitstun / blockstun | On block / hit | Hit box |
|---|---|---|---|---|---|---|---|---|
| `atk_n` Lamp Jab | 7 | 3 | 15 | 25 | 70 | 19 / 14 | −4 / +1 | x 1.8–9.0, y 6–9 |
| `atk_f` Glare Lance | 15 | 4 | 22 | 41 | 105 | 26 / 19 | −7 / 0 | x 3.5–10.0, y 6–8.5 |
| `atk_d` Scorch Sweep | 12 | 5 | 25 | 42 | 90, knockdown | — / 16 | −14 / KD | x 1.5–8.0, y 0–2 |
| `atk_air` Down Flash | 9 | 6 | to landing | 32 | 95 | 20 / 15 | by height | x 0.5–5.5, y −3–3 (from the root, in the air) |

(Measured with `tests/run.sh 17`, mx-gamma-fight, the same from the stand-in timings and from
Gamma's own animations: as estimated from Beam's, the same recovery after the active frames giving
the same advantage; the Scorch Sweep's knockdown is +40.) Beam's four normals with
the arc taken out and the searchlight put in: each a frame slower where Beam's is quick, and a
little heavier. The names were proposals, approved by the owner (2026-10-14).

- **Lamp Jab** (`atk_n`): the chain's start and Gamma's answer up close. Beam's Arc Jab a frame
  later: the projector short-armed straight forward, lens first, and **the searchlight snaps on**
  at the lens for the active frames (a blinding white flash, no arc). Frames 1–7: the elbow draws
  back 20°, the projector tilts up a little; 8–10: the arm punches out level, the lens at about
  9 m; back to the guard by 21. The torso turns into it 10°. The hit box is the whole projector,
  fist to lens (as Beam's: the owner's 2026-10-13 rule that the jab reaches as far as it looks).
  The arm is hurtable to about 4 m out from frame 8 until it is back, the projector to its lens on
  frames 7–15. Cancel window frames 8–16.
- **Glare Lance** (`atk_f`): the footsie poke. A half step (0.8 m over frames 4–13, the right foot
  sliding forward) and the projector thrust out at full length in both hands (the left hand on the
  receiver; the shield stays stowed on the forearm), the searchlight thrown open: **the hit box is
  the glare**, a hard white cone from the lens to 10 m, not the barrel. Held on 16–19, a slow pull
  back over the last 12 frames. The arm is hurtable to 4.5 m out from frame 16 until 10 frames
  after the last active frame. Cancel window frames 16–25. Beam's Static Lance, 5 heavier.
- **Scorch Sweep** (`atk_d`): from a crouch, the lens pointed down at the floor 3 m ahead and the
  ray let out for a moment, **swept out along the floor** from 3 m to 7 m as the projector lifts:
  a low knockdown. Frames 1–12: the knees bend, the projector dips to the floor; 13–17: the sweep
  (the box follows the spot of light, x 1.5–8.0 at its widest, y 0–2), the floor scorched; then 25
  frames rising from the crouch. Punishable on block or a miss. A hit box at the floor: it clears a
  Rift Mine it touches.
- **Down Flash** (`atk_air`): in the air, the projector pointed down and forward at 45° and the
  lamp fired once, a short burst below and in front; the projector stays pointed until landing.
  Once per jump.

### Specials (B)

| Move | Startup | Active | Recovery | Total | Damage | Chip | Hitstun / blockstun | On block / hit |
|---|---|---|---|---|---|---|---|---|
| `sp_n` Atomic Ray (tapped) | 18 | the ray, 12 | 16 | 46 | 10 a tick (every 6 frames) | 2 a tick | 10 / 9 a tick | −13 / −12 at 6 m; safe once pushed to the tip |
| `sp_n` Atomic Ray (held) | 18 | 12 + held, while the heat lasts | 16 | 46 + held | | | | |
| `sp_n` vented | | | the vent, 50 | 46 + held + 50 | — | — | — | open: a free punish for anything that reaches |
| `sp_f` Rod Shot | 14 (fired on 15) | the rod | 24 | 39 | 75 | 15 | 20 / 16 | −9 / −5 to 10 m; −4 / 0 from 13 m; +1 / +5 from 16 m |
| `sp_u` Geiger Flare | 7 | 6 | 28 | 41 | 70, **dazes** | 14 | daze 32 / 14 | −20 / −2 on the ground; +15 caught 4.9 m up, +18 at 6.8 m |
| `sp_d` Lead Shielding | 5 | the brace, 24 | 18 (12 after an absorb) | 47 (59 with an absorb) | — | — | — | +13 after absorbing a Tip Thrust |

(Measured, mx-gamma-fight: `tests/run.sh 17` against a standing Hero, the rod's case also from
10, 13 and 16 m; the flare in the air and Lead Shielding by scenarios 225 to 227. A flare on a
mech dazed since it last acted lands as an ordinary hit, hitstun 20.)

**Against the defences** (the details are in each move's section):

| Gamma's move | The Parry | Wing Ward | The Void Step | Tank's armour | Lead Shielding (the mirror) |
|---|---|---|---|---|---|
| Atomic Ray | the touching tick is parried: the ray is cut (Gamma frozen 20 frames, then the shut-off); the riposte reaches Gamma only within about 9 m | held off: no damage while the ward lasts, each warded tick +10 heat to Gamma's gun; Seraph keeps its 16 frames of recovery | passes through; a Double-blade reappearing inside the ray is hit by the next tick | each tick absorbed (damage, Tank's reactor), no pushback, while the marks last | holds the whole ray while the brace lasts (each tick's damage taken and feeding the reactor), no pushback |
| Rod Shot | caught: it vanishes; the riposte if Gamma is in reach | sent back as the ward's own shot, still piercing, at 0.45 m a frame (the cap) | passes through | **pierces**: an ordinary hit, the armoured move cut | **pierces**: an ordinary hit |
| Geiger Flare | parried | not caught (a strike) | passes through | absorbs the 70; **no daze** | absorbs the 70; no daze |
| Lead Shielding | not an attack | not an attack | | | |
| Point Blank (Y) | misses: a parrying Hero is in a move | misses: a warding Seraph is in a move | misses: gone | catches: grabs break armour | catches: grabs beat the brace |
| Ground Zero | not parried (no super is) | not caught (not a shot) | a Void Step started after the flash is caught on its sink frames | never absorbs a super | never absorbs a super |

The normals are ordinary strikes: parried, absorbed, passed through, not caught by a ward.

#### Atomic Ray (`sp_n`) and the heat

A held ray, on while B is held: a beam, not a ball. It hits in **ticks**, pushes the other mech
back to its tip, and heats the gun; held too long, the gun **vents** and leaves Gamma open.

| Frames | | Boxes |
|---|---|---|
| 1–18 | **dig in**: Gamma drops into the ray stance (the concept's `ray` pose: lower and wider, leaning into the gun, the projector raised level at chest height, the left fist pulled back to the hip); the lens lights and the shroud hums | standing hurt and push boxes |
| 19–30 | **the ray**, at least 12 frames however briefly B was held. **Frame 30 is the charge frame** (the `charge` mark, Beam's): while B is held, the move holds there, the ray still on, until B is let go or the gun is too hot | the ray's hit box **x 2.5–13.0, y 6.0–8.0** from the root, every ray frame; the arm and the projector hurtable to 5.5 m out (y 5.5–8.5) from frame 19 until 8 frames after the ray ends |
| 31–46 | **the shut-off** (16): the lens dims, the projector is lowered 10° and the body rises out of the stance into the guard, steam puffing from the shroud. **The move ends here (frame 46) unless the gun vented** | standing boxes |
| 47–96 | **the vent** (50, `riposte` on 47), only on an overheat: the projector kicks up 40°, steam jets from the shroud's slots and the chest hatch, Gamma staggers back 0.8 m (root motion over 47–56) and stands hunched, the left arm up against the steam, until it straightens into the guard on 87–96 | standing hurt boxes; no block, no move |

(The balance pass, 2026-10-14, the owner's: the dig-in was 13 frames and the ray reached 16 m,
x 2.5–16.0; the move was 41 frames, 91 with the vent.)

- **The ray**: a straight beam from the lens to **13 m** at chest height (y 6.0–8.0: the projector
  level at y 7). So it hits a standing or crouching mech (8 m tall crouching), either split twin
  (7.4 m), Tank (10.2 m), and **every jumping mech** (a jump's root never gets above 8 m: there is
  no jumping over it); it passes over the Antimatter Slide (4.6 m), the Twins' Low Roll (3.0 m),
  Shadow Sneak's travelling shadow (1 m) and the Fade Sweep's recovery (4 m). A gliding Seraph
  Dive (its root 3.3–4.0 m up, the body above it) is in it and is knocked out of the air. The ray is
  Gamma's hit box, not a shot: it does not use the shot slot, is not drawn as one, and stops where
  its box stops (13 m), not at the other mech: the drawing ends it at the first mech it touches.
  Gamma is planted (no root motion) and cannot block, walk or turn while it fires.
- **Ticks**: the ray hits **once every 6 frames** it is on, counting from its first frame (ray
  frames 1, 7, 13 ...): the tapped ray's 12 frames are two ticks; a ray held from a cold gun, 17.
  A tick that hits: **10 damage**, hitstun 10, knockback 0.26 m a frame. Blocked: **chip 2**,
  blockstun 9, pushback 0.21. Since the stuns (10 and 9) outlast the 6 frames between ticks, a mech
  the ray touches stays in its hit or block reaction until it leaves the ray: it cannot block,
  jump or walk out, only be pushed. **The first tick** has a light hit's hitstop (8, or 7 on
  block) and the Hit or Block event; the later ticks have **no hitstop** (the defender shakes
  in place for 3 frames, `flash`) and no events (the ray's own effect and loop sound carry them).
  A tick in the air is an air hit: a jumping mech is knocked out of the sky (`hit_air`, knocked
  down) by the first tick, as by any hit in the air.
- **The pushback**: each tick restarts the defender's slide, so a mech held in the ray is pushed
  about **1.4 m a tick hit, 1.1 m blocked** (14 and 11 m/s): from point blank to the tip (its root
  about 14.6 m from Gamma's) in about 8 ticks (48 frames) hit, 11 (66 frames) blocked. (Measured,
  scenario 220: 1.38 and 1.07 m a tick; against the Hero, whose guard holds its sword about 4 m
  in front, the ray touches the sword until its root is about 17 m out: 9 ticks from 6 m on a
  hit, 11 blocked, the last tick's slide carrying it to about 19.5 m.) Then it is
  out of the box and free, and the ray burns on in front of it. At a wall or the separation limit
  the push passes back to Gamma (the shared rule): **a cornered mech is not pinned**; Gamma slides
  back off it, about a metre a tick, until it is out of reach. A blocked ray never rings out, nor
  does a hit one (the ticks leave the mech standing); only a tick in the air carries a mech over an
  open edge, as any air hit can.
- **Combos**: the ray is **one hit** for the combo's scaling: its ticks are all scaled by the
  combo count when its first tick landed and do not add to it (a clean ray does 10 a tick; ending
  a chain of two, 6: 65 %, rounded down). It is a special: cancelled into from the Lamp Jab and
  the Glare Lance on contact, and into nothing.
- **What cuts it**: letting go of B (after the 12 frames); any hit on Gamma (its hit reaction ends
  the move); a Parry (the touching tick is parried; when Gamma's 20 frozen frames end it goes to
  the shut-off); a stronger shot (below); and the heat.

**The heat.** The gun's heat runs from 0 (cold) to 100 (`Fighter.heat`), counted on live frames
(not in a hitstop, a super's freeze or between rounds):

| What | Heat |
|---|---|
| each frame the ray is on (frames 19–30 and each held frame) | **+1** |
| each frame it is not on, outside the vent (any move, hitstun, the air) | **−1 every second frame** (from 100 to 0 in 200 frames, 3.3 s) |
| a shot burnt up by the ray (below) | **+10** |
| a tick held off by a Wing Ward (below) | **+10** |
| the vent | falls 2 a frame, **from 100 to 0 over its 50 frames** |
| Ground Zero's first active frame (the reactor's blast takes the gun's heat with it) | **set to 0** |
| the start of a round | 0 |

- **Overheat**: the frame the heat reaches 100 while the ray is on, **the gun vents**: the ray goes
  out at once, the animation jumps to the vent (frame 47), the event `Vent`. So a ray from a cold
  gun lasts at most **100 frames** (1.7 s, 17 ticks: 99 frames of its box, the vent on the 100th);
  from a warm one, less. A ray started with
  the heat at 88 or more vents inside its 12 frames: the gauge says so before B is pressed. Being
  hit out of the ray, or letting go, never vents: the heat only cools.
- **The vent**: 50 frames in which Gamma is open (no block, no move) and the gun cools to 0.
  About −50 against a mech held at the tip: what reaches about 15 m in that time punishes it (the
  Momentum Drive, a held Shadow Sneak or Seraph Dive, the Arc Lance after a short walk in);
  against a mech nearer (a Void Step through the ray, a mech the ray never pushed), anything
  does.
- **Where it shows** (both): **on the gun**, for both players, as Tank's reactor shows its meter:
  the shroud's vent slots glow dull red from 30, orange from 60 and yellow-white from 85, with
  wisps of steam from the slots from 85; the vent is a white blast of steam. **On the HUD**, for
  the Gamma player's precision: a 2-pixel heat bar 5 pixels under Gamma's meter gauge (under the
  Siphon's and the mark's time bars, which sit 2 pixels under it), the gauge's length, filling
  from the outer end: green to 59, amber 60–84, red 85–99 and flashing, white while venting.
  `gamma_heat_hud()` ([For the effects and sound](#for-the-effects-and-sound-gamma)).

**The ray against the shots.** A shot of the other side meets the ray where their boxes overlap,
in height as well as in x (the meet rule between two shots looks only at x; the ray is a box):

| Shot (strength) | Its box | What happens |
|---|---|---|
| Kinetic Wave (2) | y 0–3 | **passes under the ray** and hits Gamma's shins (y 0–3), which ends the ray as any hit does: the Hero's answer to a held ray |
| Volt Orb, tapped (1) | y 4.8–6.6 | **burnt up**: the orb is gone, the ray goes on, **+10 heat** (the event `Burn`) |
| Volt Orb, charged (2) | y 4.8–6.6 | the orb is gone and **the ray is cut** (Gamma goes to the shut-off; no vent, no heat added) |
| Volt Orb, full (3) | y 4.8–6.6 | **the ray is cut and the orb goes on** to Gamma |
| Hex Bolt (1) | y 4.5–7.5 | burnt up, +10 heat; it touched no mech, so no curse |
| Mark of Judgement (1) | y 5.0–7.4 | burnt up, +10 heat; no mark |
| Rod Shot (a mirror's) | y 6.4–7.2 | passes through (it pierces) |
| a reflected shot | its kind's | as its kind (a reflect keeps the strength) |

So a strength-1 shot is spent against the ray but costs Gamma heat, Beam must charge to cut it
(the original's answer to its echo), and only the wave and the full orb get through to Gamma.

**The ray against the defences.**

- **The Parry** catches the tick that touches the Hero in its stance: Gamma freezes 20 frames
  (the Parry's freeze) and its ray is cut; the Hero's riposte (x 1.5–7.5) reaches Gamma only
  within about 9 m. From further out the Parry only stops the ray: the riposte's 24 frames end
  about when Gamma's freeze and shut-off (36) do. (Measured, scenario 223: frozen in the ray
  stance, Gamma's projector arm is hurtable 5.5 m out, so the riposte, which steps in about 1 m,
  reaches it from about 14 m: from 6 m it lands 11 frames after the Parry; from 17 m the Parry
  only cuts the ray, the shut-off starting 27 frames after it, the freeze's 6 and the Parry's 20.)
- **The Wing Ward** (decided here): **a held beam cannot be reflected like a ball.** A shot is a
  thing in the thrower's shot slot that the ward turns round and gives to Seraph; the ray is
  Gamma's own hit box, fixed to its gun, with nothing to turn round or give. Nor does it hit the
  ward as a strike would: it is light, as the shots the ward catches are. So **the ward holds it
  off and sends it back into the gun**: while Seraph's `ward` frames last, a tick that touches
  Seraph from in front does nothing to it (no damage, chip, stun or pushback) and **adds 10 to
  Gamma's heat** on top of the ray's own; the first such tick posts `Reflect` (power 0), for the
  flash and the clang. The ward is not cut short and has no fling (no shot became Seraph's): when
  its 20 frames end, its 16 frames of recovery are hit by the ray if Gamma still holds it. So
  warding the ray is a trade: Seraph pays 40 frames to put 30 or 40 heat into the gun (3 or 4
  ticks), and Gamma decides whether to hold through it toward a vent. The Arc Lance and the
  Raikō Overload's beam stay strikes (a discharge, not a held ray).
- **The Void Step** passes through the ray (no hurt box on its gone frames); reappearing 9 m on,
  still inside the ray, the Double-blade Hero is hit by the next tick. Started from about 10 m or
  nearer it reappears inside the ray's first 2.5 m (which the ray misses) or behind Gamma: the
  way in.
- **Tank's armour** absorbs every tick while its marks last: Tank takes each tick's 10 and its
  reactor 30, with no stun and no pushback, so an armoured Tank keeps coming through the ray. When
  the marks end, the next tick hits.
- **Lead Shielding** (the mirror): see [Lead Shielding](#lead-shielding-sp_d): it holds a whole
  ray while the brace lasts.
- **Two rays** (the mirror): hit boxes do not clash; each ray hits the other Gamma. Whoever fires
  second is in its startup when the other's first tick lands, and is hit out of it.

#### Rod Shot (`sp_f`)

Frames 1–14: Gamma plants, both hands on the projector, levels it at chest height and braces (the
body sinks 0.3 m, the left hand on the receiver); the tube under the shroud whines. **Frame 15
(the `release` mark, 14 from 0)**: the rod leaves the bore under the lens with a hard crack, the
projector kicking back 10° (a sharp recoil, not Beam's lift). 24 frames back to the guard, the
bore smoking. No root motion. The projector is hurtable to 5 m out on frames 15–25.

- **The rod**: a spike of hot metal, glowing, very fast: it starts **5.0 m** in front and flies at
  **0.60 m a frame** (36 m/s: the fastest shot; the full Volt Orb is 0.36), a box **1.2 m long
  (x ± 0.6), from y 6.4 to 7.2**, for **60 frames** (36 m, the stage), and vanishes at a wall or an
  open edge. So it hits a standing or crouching mech, either split twin and every jumping mech (a
  jumping mech is knocked down by it, as by any air hit), and passes over the Antimatter Slide,
  the Low Roll, Shadow Sneak's shadow and the Fade Sweep's recovery. It reaches a mech 16 m away
  in about 15 frames.
- **One rod at a time**: forward + B while Gamma's rod is out does nothing (the shot slot's rule;
  the Ray does not use the slot, so Gamma may fire the ray with a rod in flight).
- **Piercing**, exactly:
  - **Through shots: yes.** The rod passes through every other shot and every other shot passes
    through it: neither stops the other (too thin to clash). It passes through the Atomic Ray (a
    mirror's) too.
  - **Through armour: yes.** It is never absorbed: against Tank's armour or a braced Lead
    Shielding it lands as an ordinary hit (hitstun 20, its knockback), cutting the armoured move.
    The answer to an armoured approach from Heartland's own shelf.
  - **Through mechs: no. It hits once**: the first body it touches takes it (a hit, a block, a
    Parry) and the rod is gone. Against the split Twins it hits the first twin it reaches.
- **On hit**: 75 damage, hitstun 20, hitstop 9, knockback 0.14, no knockdown (on the ground).
  **On block**: chip 15, blockstun 16, no meter for Gamma (nuclear gains nothing from hits).
- **The Parry** catches it (it vanishes; the riposte if Gamma is in reach); **the Void Step** passes
  through it; **the Wing Ward** sends it back as Seraph's own shot, still piercing, but at **0.45 m
  a frame** (the ward's ×1.25 is capped at 0.45: a reflected rod comes back *slower*), the rod's
  hit and chip, drawn as light. A reflected rod pierces Gamma's Lead Shielding.
- What it is for: the far game, beyond the ray's 13 m; a shot that wins any projectile war by
  ignoring it; the chain's ender when the other is too far for the ray's push to matter; the
  answer to armour. Up close it is −9: a jab punishes it.

#### Geiger Flare (`sp_u`) and the daze

The anti-air: the projector thrown up at the sky ahead and the lamp fired wide open, a burst of
light upward that **dazes** what it hits. Frames 1–7: the projector swings up past the head to
point up and ahead at 60°, the body leaning back under it, the head up with it, the left arm braced
low (the concept's `flare` pose); **invulnerable on frames 1–7**, so it beats a jump-in started in
time (Beam's Thunder Pillar's). Frames 8–13, active: the burst, a cone of light the box **x 0.0–6.0,
y 6.0–18.0** from the root, held; the body shudders. Frames 14–41, recovery (28): the projector
brought back down to the guard. No root motion. 70 damage, chip 14, blockstun 14, hitstop 11, no
knockdown: **the daze** instead.

**The daze**, exactly:

- **On the ground** (standing or crouching): the hit puts the mech in `hit_high` (`hit_low`
  crouching) for **32 frames** from the end of the hitstop, the animation stretched over them as a
  hitstun's is (a slow reel; the effect draws the daze).
- **In the air**: the jump, the air attack or the special it was in is cut; it **drops**
  straight down from where it was hit (its forward speed and upward speed set to 0, gravity as
  usual) in its jump's landing pose (the last frame of `jump`, as a mech falls after a move that
  ended above the floor), **lands on its feet** without landing lag, and is dazed for 32 frames
  from touchdown. It does not ring out (it is not carried: the lip stops it). While it drops it is
  an ordinary airborne mech: a hit knocks it down (and ends the daze).
- **How it differs from hitstun** (the same reaction, different rules):
  1. **No knockback**: the dazed mech stays where it is (a hitstun slides it back).
  2. **Grabbable**: it counts as a standing mech for a grab (a mech in hitstun cannot be
     grabbed): Point Blank, Tank's grabs, any Y grab catch it.
  3. **One opening, not a loop**: the first hit or catch ends it at once and lands as an ordinary
     hit (its own hitstun or knockdown). A dazed mech hit again is not dazed again: a daze cannot
     be renewed until the mech has been actionable (`Fx.dazed` clears in `to_neutral`).
  4. **Fixed length**: 32 frames, whatever the hit; not stretched by anything.
  5. **Scaled as a combo**: the flare counted as the combo's first hit, so the next is its
     second (80 %).
  Like hitstun: the mech cannot act, block, walk or jump; presses are kept in the buffer.
- **Frame advantage**: on the ground, about −1 (a reset, not a combo: Gamma recovers as the daze
  ends). In the air, the drop adds its fall to the daze: about **+8** for a mech hit with its root
  2 m up, **+16** at 6 m, more on the flare's later active frames. (Measured, scenarios 225 and
  226: −2 on the ground; a Hero's jump caught 4.9 m up and 4.6 m out, Gamma free 15 frames
  before the daze ends; one caught at its top, 6.8 m up, 18 frames, the ray's first tick landing
  a frame after the daze ends.) So a low catch leaves time for the Lamp Jab or Point Blank; **a
  high catch leaves time to start the Atomic Ray** (startup 18) before the daze ends, which pushes
  the mech back out to the tip: the anti-air that restores the zoner's distance. Since the balance
  pass (the dig-in 18 frames, not 13) the first tick lands a frame after the daze, so it can be
  blocked: a reset, not a combo.
- **Blocked**: chip 14, blockstun 14, **no daze** (block stops every attack). About −20: very
  punishable. **Absorbed** by Tank's armour or a mirror's Lead Shielding: the 70 is taken, **no
  daze** (armour is exactly that a hit does not stagger). **Parried** as any strike. **The Void
  Step** passes through it. Not caught by a Wing Ward (a strike).
- Reach: the cone is 6 m wide and 18 m up: wider than the Thunder Pillar (x 0.5–5) and reaching a
  jump-in that lands just in front of Gamma, not one that lands 7 m out.
- The split Twins: the twin it hits is dazed; the other is not.

#### Lead Shielding (`sp_d`)

Gamma turns its left side to the other mech, drops into a crouch and **swings the field gun's
shield out** from the left forearm, bracing behind it. **The next hit is absorbed**, like Tank's
armour; its damage still feeds the reactor.

| Frames | | Boxes |
|---|---|---|
| 1–5 | **the swing**: the body turns left side forward and crouches (the concept's `shield` pose: the left forearm pointed at the other mech, thumb up; the projector drawn back level at the hip), the shield swung out about the mount's Y to stand across the arm's line, the stencilled trefoil facing the other mech; it clangs into place on 5 | crouching hurt and push boxes (8 m, 7.5 m) |
| 6–29 | **the brace** (the new `shield` mark, 24 frames): held, settling into it | crouching boxes |
| 30–47 | recovery (18): the shield swung back and stowed, Gamma rising into the guard. **The move ends here (frame 47) unless a hit was absorbed** (the Parry's and the Wing Ward's rule: `advance()` ends any `sp_d` at its `riposte` frame) | standing |
| 48–59 | **after an absorb** (12 frames, `riposte` on 48): the shield knocked back by the blow, swung back and stowed by 56, the guard by 59 | standing |

- **The window**: frames 6–29, 24 frames. A hit that lands on Gamma on a `shield` frame, on the
  ground, is absorbed.
- **How many**: **one hit.** The hit is absorbed as by Tank's armour: Gamma takes its damage **in
  full** (unscaled: an absorbed hit is not part of a combo), the reactor fills from it (3 a point),
  both mechs freeze for the hit's hitstop while Gamma flashes, and there is no hitstun, no
  knockback and no knockdown; the event `Armour` (the clank and the ring). Then the brace ends:
  the animation jumps to frame 48, and Gamma is **actionable 12 frames after the absorb** (after
  the hitstop). The attacker's hit is spent and is not contact for its chain, and it gets a blocked
  hit's meter (kinetic +60). A second hit after the absorb lands as on any move.
- **The payoff**: the reactor, and the turn. Against a Tip Thrust absorbed on its first active
  frame, the Hero has 24 frames of the thrust left and Gamma 12: **about +12**, a Lamp Jab and a
  chain. Against a jab, nothing much (the jab recovers in time): the shield is for a heavy blow.
- **Grabs beat it**: a Y grab, the Atomic Clinch and Chain Reaction catch a mech on a `shield`
  frame, as they catch one on an armour frame. On the swing (1–5) and the recovery it is a move
  like any other, and not grabbable (strikes beat grabs).
- **Supers** are never absorbed: a super's hit lands as usual and knocks Gamma out of it.
- **Shots**: absorbed as strikes are (the wave, the orbs, a reflected shot): one, then the brace
  ends. An absorbed Hex Bolt still curses and an absorbed Mark bolt still marks (the touch, as
  through Tank's armour). **The Rod Shot pierces it** (a mirror's, or one a Wing Ward reflected):
  an ordinary hit.
- **The Atomic Ray** (the mirror): lead stops the ray. A ray is one hit for the shield: its first
  tick is absorbed and the shield **stays up for that ray's later ticks until the brace's last
  frame (29)**, each tick's damage taken in full and feeding the reactor, with no stun and no
  pushback; then it jumps to frame 48 as after any absorb. A Geiger Flare is absorbed without its
  daze.
- **Not absorbed**: a mine's snare (not a hit: a mech braced on an armed Rift Mine is snared as in
  any move), and anything in the air (it is a ground move).
- Whiffed, it is 47 frames with nothing to show: a read of the other's heavy attack or shot, not
  a panic button. It can be cancelled into (below): a blocked Glare Lance into Lead Shielding takes
  the punish on the shield; a grab beats that.

### Grab and throw (Y): Point Blank

As Beam's grab (startup 5, active 2, the catch box x 1.0–3.6, y 2–10, 7 frames; a miss plays
`grab_whiff`, 22). Breakable as every Y grab (Y within 10 frames). On a catch, `throw` (46 frames)
on Gamma and `thrown` (46, Beam's) on the other: Gamma takes the other by the shoulder with its
left hand (the shield stays stowed on the forearm), jams the lens against its chest and fires the
ray point blank.

| Frames | Gamma | The other (the fight places it) |
|---|---|---|
| 1–10 | the left hand closes on the shoulder (the break window), the lens swung onto the chest | 3.4 m in front, lifted 0.1 m a frame (the Hero's and Beam's placement) |
| 11–30 | the lens held to the chest, the searchlight blazing through the other's armour, the shroud glowing | held 3.0 m up from frame 30, shaking in the light |
| 31–33 | the ray at full power, the projector bucking | |
| 33 (`release`, 32 from 0) | the blast throws it off | **120 damage, knockdown**, flying about **10 m** (`vx` ft × 0.30, the Hero's throw's; measured: 10.9 m for the Hero, 12.1 m for Beam, which falls slower) |
| 34–46 | recovery into the guard, the shroud steaming | |

The longest of the throws after Tank's: it puts a rushing mech back out at the ray's middle,
knocked down, where it gets up into the ray. 120: less than Beam's 130 (the distance is the
point). It does not heat the gun. Near an open edge behind the other, it rings out from about 10
m. Thrown mechs are not hittable, and neither is Gamma during the throw.

### Super (A + B): Ground Zero

**The flash** (frames 1–40: the world freezes, Gamma alone moves): it plants wide and low, throws
the chest hatch open (the reactor bared, the torso pitched back 16°, the head back) and raises the
projector overhead, muzzle down; the reactor's glow floods white-green and the stage tints toward
it. Then:

| Frames | |
|---|---|
| 41–44 | startup (4): the projector is driven muzzle first into the floor in front of the feet (contact on 44) |
| 45–52 | **active (8)**: the blast: a dome of light and force all round Gamma, the hit box **x −8.0 to +8.0, y 0–12** from the root (both sides at once); the concept's `ground_zero` pose held, the body shaking, the left arm flung out behind |
| 53–96 | recovery (44): the projector wrenched out of the floor, the hatch closing, steam and dust settling, Gamma straightening into the guard |

- **Radius 8 m, all round**: it hits a mech in front of Gamma or behind it (a mech that crossed
  over), standing, crouching, on the ground or in the air up to 12 m (a jump-in is hit), within 8
  m of Gamma's root (the hurt box's edge: so a mech whose root is up to about 9.6 m away). Outside
  it, nothing: the Tip Thrust's tip (10 m) is just out of it. Short range is the point: the
  zoner's answer to a mech that has got in. (Measured, scenario 229: the Hero, whose guard holds
  its sword about 4 m in front, is hit with its root 11 m away and missed at 13 m.)
- **Invulnerable from frame 1 to 45** (the flash, the startup and the first active frame): a
  reversal. After the freeze the other has 4 frames: nothing walks 8 m in 4, and a Void Step
  started then is caught on its sink frames; block on the flash, or be knocked down or getting up
  through frames 45–52.
- **Damage**: **300**, knockdown, the super's hitstop (20), launch 0.70 (the others' 0.60), the
  other blown **away from Gamma** whichever side it is on; scaled in a combo like any hit (240 as
  a chain's second hit, 195 as its third). **Chip**: 75 through a block (which can finish a round).
  Blockstun 22, pushback 0.24: **about −29 on block**, the blocker pushed about 2.5 m out: a long
  forward attack or a dashing special punishes it.
- **Ring-outs**: the launch carries the other about **5 m** (the shared knockdown speed, 0.12 m a
  frame, over a longer flight), away from Gamma: **a mech within about 5 m of an open edge behind
  it, on either side of Gamma, is rung out.** Gamma has no root motion and is never carried.
- **The heat**: the gun's heat is set to 0 on the first active frame.
- Not parried (no super is), never absorbed by armour or Lead Shielding, not caught by a Wing Ward.
  It hits one body of the split Twins (the shared rule: the leader if it touches both).
- One bar, as every nuclear super: Gamma's comes from the damage it takes, so it comes when the
  other mech has been winning, and it answers the mech that is winning up close. 300, less than
  Tank's 360 grab and the Hero's 340 dash: a defensive super, and one of the quickest to strike
  after the flash (4 frames; Antimatter Rend's 3).

### Chains

The shared chain: Lamp Jab, then Glare Lance, then a special or the super. **The Atomic Ray combos
from the Glare Lance** (and the jab): its first tick lands inside the lance's hitstun and the ray
pushes the other out to the tip: 70 + 84 + about 7 ticks of 6 (about 42) from a clean start.
**The Rod Shot combos from the Glare Lance** (the rod starts 5 m out and reaches the pushed mech in
2 or 3 frames): 49, no knockdown, Gamma about −4. The Geiger Flare combos from the Lamp Jab close
up and dazes the other (−1: a reset, not a combo). **Ground Zero combos from the Lamp Jab** and
from a Glare Lance that hits close (the lance's pushback can carry the other just past 9.6 m).
Lead Shielding can be cancelled into (a blocked Glare Lance into the brace). Scorch Sweep, Down
Flash and the specials cancel into nothing.

### Frame advantage (measured)

`tests/run.sh 17` (mx-gamma-fight), against a standing Hero, from Gamma's own animations (the same
numbers as from the stand-in timings before they landed): Lamp Jab
−4 on block / +1 on hit, Glare Lance −7 / 0, Scorch Sweep −14 / knockdown (+40), the Atomic Ray
tapped at 6 m −13 / −12 (two ticks, the first on frame 18 since the balance pass; held to the tip,
out of reach), vented about −50 (scenario 221: the Hero's Charge Slash lands 38 frames into the
vent), Rod Shot −9 / −5 to 10 m (the rod starts
5 m out, inside the Hero's guard), −4 / 0 from 13 m and +1 / +5 from 16 m, Geiger Flare −20 on
block and −2 on a ground hit, +15 caught 4.9 m up and +18 at 6.8 m (scenarios 225 and 226),
Lead Shielding +13 after absorbing a Tip Thrust (scenario 227; 47 frames whiffed), Ground Zero −30
on block with the Hero 8 m off (a knockdown, +40, on a hit). (The estimates were −14 for the sweep, −12 for the ray, even from 10 m for the rod, −1 and +8
to +19 for the flare, +12 for the shield and −29 for Ground Zero.)

### Balance intent

A slow, heavy zoner that gets stronger when the plan fails. The plan is the ray: plant at mid
range and hold the other mech at the ray's tip, the Rod Shot beyond it, the Geiger Flare above it.
When the plan fails (something goes under the ray, through it, round its heat, or the other is
simply in), every hit fills the reactor, Lead Shielding turns one more into meter and a turn, and
Ground Zero clears the space. Its weaknesses are plain: the slowest walk on legs and a poor walk
back, so a mech that gets in stays in; a jab a frame slower than Beam's; a ray that roots it to the
spot, cannot be fired while blocking, is gone under by four mechs' moves and vents if it is
greedy; a flare and a shield that are very punishable read. Health 1,050, between Beam's and
Tank's; damage a little over Beam's on the normals, less on the specials (the ray's ticks are
light, its push is the point).

- **The Hero**: the Kinetic Wave goes under the ray and hits Gamma's shins: the Hero zones the
  ray from range, and the Parry cuts it. The Rod Shot and the wave pass through each other and
  trade. Gamma outranges the Tip Thrust (13 m to 10 m) and the ray knocks a jump-in down. Slightly
  Gamma's at mid range, the Hero's from far; even.
- **The Double-blade Hero**: the Void Step through the ray and the slide under it, rushdown
  against the slowest walk. Lead Shielding takes a Cross Lunge for meter, Ground Zero answers the
  pressure (a Double-blade in debt takes 375). Slightly the Double-blade Hero's.
- **Beam**, the original: tapped orbs are burnt (+10 heat each), a charged orb cuts the ray, a full
  one cuts it and gets through; the Rod Shot passes through every orb and outruns the Arc Lance's
  reach (15 m to 36 m); the Arc Lance now outreaches the ray (15 m to 13 m). Beam's Reaction Prime
  at mid range eats the ray's ticks. Even.
- **Tank**, Heartland's own: the Rod Shot pierces the armour; the ray is absorbed by it (each tick
  fills Tank's reactor) but the armour frames are short and the ray pushes Tank back the moment
  they end. Up close the Atomic Clinch and Chain Reaction catch Lead Shielding (grabs beat it).
  Two nuclear meters: whoever is hit more gets its super sooner. Slightly Gamma's.
- **The Twins**: the Low Roll (3.0 m) goes under the ray and the rod; two bodies, and the ray, the
  rod and Ground Zero each hit one; the partner's late copy gets in. Slightly the Twins'.
- **Shadow**: the Sneak's shadow goes under the ray; the Hex Bolt is burnt (no curse, +10 heat);
  the Siphon takes a quarter of Gamma's reactor; the Rift Mine costs a slow walker little (Gamma
  stays back) and the Scorch Sweep clears it. Even.
- **Seraph**: the Wing Ward puts heat into the gun and sends the rod back slower; the Mark bolt is
  burnt; the Seraph Dive's glide flies into the ray. Even.
- **Gamma** (the mirror): rays do not clash, so whoever rays first wins the exchange; Lead
  Shielding holds a ray and the rod pierces the shield: shield the ray, rod the shield.

**Measured, CPU against CPU** (mx-gamma-fight; `tests/balance/run.sh 9 B`, level 2 against level
2, 10 matches a pairing on the hangar, the sides swapped every match, Gamma on its own
animations). Before [the balance pass](#balance-pass-2026-10-14-gamma-and-seraph) Gamma won all 60
matches against the six base mechs (10 of 10 against each): at level 2 the CPUs react to a move 13
frames in, which was the ray's startup, so its dig-in was never blocked, and a mech in it was
pushed back to its 16 m tip, where the Rod Shot (75, at 0.60 m a frame) landed or chipped. Tank,
the slowest walker, never reached Gamma. **After the pass** (the dig-in 18 frames, the ray 13 m,
the slide, roll and Sneak under it more often from mid range): **43 of 60**: 3 of 10 against the
Hero, 8 against the Double-blade Hero, 10 against Beam, 5 against Tank, 9 against the Twins, 8
against Shadow (rounds 98 to 46); Beam is still swept. The numbers are the owner's to tune in
play; the CPUs' answers to the ray are as [the CPU (Gamma)](#the-cpu-gamma) lists them.

### The CPU (Gamma)

Gamma's own CPU replaces Beam's for it (`cpu.akr`): a `gamma_neutral` like `beam_neutral`, and
lines in `cpu_think` where Beam has them. The CPU reads `Fighter.heat` (the other player sees it
on the gun). Built in mx-gamma-fight (its section at the end of `cpu.akr`: `gamma_neutral`,
`gamma_ray_hold`, `gamma_chain`, `gamma_punish`, `gamma_answer`, and for the others `under_ray`
and `vent_punish`) as this list has it, with these details: the ray is held through its first 12
frames, then while its last tick touched the other within 7 frames (so a jump knocked down, a mech
pushed out or a ward lets it go); it is started at a mech walking in or jumping in from 5.5 to 12
m (15 before the balance pass; `lv.poke` + 25 %), now and then at its own range, and as the punish
of a whiff within 13 m;
the Rod Shot also answers a wave on its way (`lv.aa`, when the wave is more than 24 frames off);
after a dazing catch the CPU acts without dice; Lead Shielding is rolled at `lv.special` × 6 / (2
+ the other's grabs seen, at most 6); Ground Zero as a reversal is rolled at `lv.punish` within
8.5 m. The Hero and Beam no longer answer a rod coming with a shot of their own (it passes
through: they block it). Measured in scenario 230 (level 2, both sides, against each base mech
and Seraph, 14 matches, on its own animations, after the balance pass): 134 rays and 297 rods, 7
flares (7 dazes), 16 shields (5 hits absorbed), 20 grabs, 19 supers, no vents; Seraph warded 3 of
its ray's ticks; Gamma won 12 of the 14 (Tank took both). (Before the pass: 194 rays, 357 rods,
2 flares, 14 shields, 10 grabs, 10 supers; 13 of 14, the Double-blade Hero taking one.)

- **The Ray**: B when the other is within 12 m and walking in, jumping in, or recovering from a
  move, and the heat is under 60; it holds B (a `ray_want`, as Beam's `charge_want`) until the
  other is pushed out of the box or the heat reaches 85 (levels 1–3); **level 0 and the novice
  hold to 100 and vent**. Not while the other's shot is coming at it, not against a mech in a move
  that goes under it (the slide, the Low Roll, the Sneak's travel: block those).
- **The Rod Shot**: from beyond 13 m with no rod out; against a mech in an armour frame at any
  range (`lv.punish`); as the answer to a shot war (it passes through).
- **The chain ender**: the Ray on a hit (the push), the Rod Shot from further than 9 m, Ground
  Zero on a hit when the meter is full (`super_wise`); nothing on block, or Lead Shielding at
  `lv.special` after a blocked Glare Lance.
- **Anti-air**: up + B against a jump coming within about 8 m (the shared line); the Ray against
  one from 8 to 12 m (a tick knocks it down). After a dazing catch: the Ray if the other is still
  in the air when Gamma recovers, else the Lamp Jab or Point Blank.
- **Lead Shielding**: in place of blocking, at `lv.special × 3`, against a forward attack or a
  special starting within the other's reach; less often against a mech that grabs (a count of its
  grabs, as `blocks_seen` counts blocks); never against a super's flash.
- **Ground Zero**: with a full meter, the other within 8 m and attacking (a reversal, at
  `lv.punish`), or on a whiff within 8 m; with the other's back within 5 m of an open edge, more
  often.
- **Throws**: the general rule, and Point Blank whenever the other's back is within 10 m of an
  open edge.
- **Against Gamma** (the other CPUs): treat the ray's startup as an attack in range out to 13 m (the
  general "an attack starting in range" test uses the forward attack's reach): block it, or go under
  it (the slide, the Low Roll, the Sneak) at `lv.special` × 3, and × 5 from beyond 6 m, where the
  ray is the threat (the balance pass; at level 2 the CPUs react 13 frames into a move, so the
  18-frame dig-in is seen in time; a jump does not clear the ray, which meets every jump); the Hero
  fires its wave while Gamma holds the ray; Beam charges an orb past 20 frames to cut it; Seraph
  wards it when the heat is over 50; everyone punishes a vent by its distance (the general whiff
  punish sees it, an `sp_n` whose hit box went away, but tries only what reaches: its jab, its
  forward attack and special, the super within 12 m; a vent at the ray's tip gets its own line, by
  distance: the Momentum Drive, the Arc Lance after a walk in, a held Sneak or Dive); no jump-ins
  within 13 m of a Gamma whose heat is under 60.

### Reactions and the rest (Gamma)

As the shared list, with Gamma's lengths (Beam's rig and Beam's timings where they are Beam's):
`idle` 60, `walk_f`, `walk_b` 52, `crouch` 8, `jump` 46, `land` 10 (the fight cuts it at 7 for a
plain landing), `block` 4, `hit_high` and `hit_low` 20, `hit_air` 30, `knockdown` 32, `getup` 20,
`ko` 90, `win` 120, `intro` 90, `grab` 7, `grab_whiff` 22, `grab_break` 20, `throw` 46, `thrown`
46, `thrown_vault` 40, `thrown_slam` 56. A dazed Gamma (a mirror's flare) plays `hit_high`
stretched over the daze, as every mech.

### For the animators (Gamma)

Everything in `anims/gamma/` becomes Gamma's own; until a move is done it stays Beam's placeholder.
Frame numbers here count from 1 as the tables do; the marks list counts from 0, as the files do.

- **The rig** is Beam's (`models/beam/beam.rig.json`'s skeleton, offsets and joint ranges, as the
  Gamma model carries them), so a Beam pose reads on Gamma. **`weapon_r` is the ray projector**,
  held as Beam holds the Arc Cannon (the grip up through the fist, the barrel along the mount's
  −Z, the forearm's line: a level forearm aims it): the receiver on the fist, the slotted shroud,
  the searchlight drum with the lens at the muzzle (0, 0.8, −4.4) and the Rod Shot's bore under it
  (0, 0.3, −4.86). It reaches a little past Beam's cannon (the drum's guard): keep it out of the
  floor, and clear of the antenna and the searchlight head when it swings overhead (the flare,
  Ground Zero).
- **`weapon_l` is the lead shield**, the field gun's plate on a bracket at the back of the left
  fist. **Stowed at 0**: it lies along the outside of the left forearm. **Out at y 90** (the
  concept's `SHIELD_OUT`, `[0, 90, 0]`): turned 90° about the mount's Y it swings out like a door
  to stand across the arm's line 0.7 m in front of the grip, its stencilled face (the trefoil)
  looking along the forearm; with the forearm pointed forward and in, it covers the chest. Keys
  about Y only, range 0..100 (the overshoot of the clang). Half out (y 45) is the block. Every
  move not listed below keeps it stowed (`"still"` at 0).
- **The key poses** are the concept's (`concepts/gamma_c/make_gamma_c.py`, `poses()`): `ray` (the
  Atomic Ray's stance: drop 1.0, the pelvis turned y −10, the torso x −10 y −14, the right upper
  arm x 40 and forearm 52, the left forearm folded 104 at the hip), `shield` (Lead Shielding's
  brace: drop 1.05, the torso turned y 26 left side forward, the left arm solved to point the
  forearm at the other mech, thumb up, `weapon_l` at SHIELD_OUT), `flare` (the Geiger Flare: drop
  0.7, the torso leaning back x 10, the right upper arm 150 to point the projector up and ahead)
  and `ground_zero` (the super's blast: drop 1.1, planted wide, the torso back 16, the head back
  24, the projector driven muzzle down at the floor ahead, the left arm flung out behind). Start
  from them.
- **The guard** is Beam's (the rig's `guard` pose): the projector level at the other mech, the left
  fist raised in front of the chest under it, the shield stowed. Every move starts and ends in it.
- **Marks** (from 0): `cancel` on `atk_n` 7–15 and `atk_f` 15–24; `invuln` on `sp_u` 0–6 and `super`
  0–44; `flash` on `super` 0–39; `release` on `sp_f` 14 (the rod) and `throw` 32 (the blast);
  `charge` on `sp_n` 29 (the ray's hold; 24 before the balance pass); **`shield` (new) on `sp_d`
  5–28**; `riposte` on `sp_n` 46 (the vent section's first frame; 41 before) and `sp_d` 47 (the
  after-absorb section); `step` on the walks' plants (0 and 26). No `armour`, `parry`, `hide` or
  `nopush` anywhere.
- **Root motion**: `atk_f` 0.8 m over frames 4–13; `sp_n` 0.8 m **back** over 46–55 (the vent's
  stagger); none in any other move (the ray, the rod, the flare, the brace and the super are all
  planted).
- **Boxes**: the hit boxes in the tables. `sp_n`: the ray's box x 2.5–13.0, y 6.0–8.0 on frames
  18–29 (`hit` 0; the fight re-arms it every 6 ray frames), and a hurt box for the arm and the
  projector out to 5.5 m (y 5.5–8.5) from 18 to 37. `sp_f`: the projector hurtable to 5 m on
  15–25. `sp_u`: the cone x 0.0–6.0, y 6.0–18.0 on 8–13. `sp_d`: crouching hurt and push boxes on
  1–29. `super`: x −8.0–8.0, y 0–12 on 45–52 (both sides of the root). Keep `design` boxes in the
  files so `verify` checks them.

| Move | Length | Must show | The projector and the shield |
|---|---|---|---|
| `idle` | 60, loop | Beam's planted guard breathing; every 20 frames the shroud ticks (a 1° shiver of the projector, the gun cooling) | the projector level; the shield stowed |
| `walk_f`, `walk_b` | 52, loops | Beam's heavy step with more weight: a long plant, the body dipping under the level projector; `step` on 0 and 26 | the projector level and steady; stowed |
| `crouch` | 8 | the knees bend, the projector kept level | stowed |
| `jump` | 46 | a 6-frame crouch, a late launch, a short tuck, a heavy landing | the projector level throughout; stowed |
| `land` | 10 | the knees take it (the fight cuts it at 7 after a plain jump) | stowed |
| `block` | 4 | upright, the left forearm raised across the chest and face, the projector drawn back to the hip | **the shield half out: y 0 to 45 by frame 4**, held |
| `hit_high`, `hit_low` | 20 | Beam's | the shield rattles: y 0, 8, 0 over 1–6 |
| `atk_n` | 25 | the Lamp Jab above; the lens at about 9 m on 8–10 | stowed |
| `atk_f` | 41 | the Glare Lance above; the projector at full length in both hands on 16–19 | stowed, the left hand on the receiver; keep the plate clear of the drum |
| `atk_d` | 42 | the Scorch Sweep: the lens pointed at the floor 3 m ahead by 12, swept out to 7 m over 13–17 as the projector lifts, rising after | stowed |
| `atk_air` | 32 | the Down Flash: the projector pointed down and forward 45° by 9, held until landing | stowed |
| `sp_n` | 96 (46 when it does not vent, + the hold on 30) | the Atomic Ray's table: dig into the `ray` pose by 18; the ray on 19–30, the body nudged back 2° (torso x) on each tick (frames 19, 25) and settling; **frame 30 is held while B is held, so it must be the best ray pose**; the shut-off 31–46 ending in the guard; the vent 47–96: the projector kicked up 40° on 47–51, the head turned away, staggering back (the root 0.8 m over 47–56), hunched with the left arm up against the steam on 56–86, into the guard by 96 (frame 46 and frame 96 must both be the guard). (Retimed in the balance pass: 91, the dig-in by 13) | stowed; the left forearm up in the vent |
| `sp_f` | 39 | the Rod Shot: levelled in both hands and braced (the body sinks 0.3 m) on 1–14; on 15 a sharp kick back of 10° (a recoil, not a lift); back to the guard by 39 | stowed, the left hand on the receiver |
| `sp_u` | 41 | the Geiger Flare: the projector swung up past the head (clear of the antenna and the lamp head) to the `flare` pose by 7, held and shuddering on 8–13, brought down over 14–41 | stowed, the left arm braced low |
| `sp_d` | 59 (47 when nothing is absorbed) | Lead Shielding's table: the `shield` pose by 5, held 6–29 with a slight settle, back to the guard over 30–47 (frame 47 must be the guard); after an absorb, 48–59: the whole body knocked back 2° and the shield knocked open, then stowed and the guard by 59 | **y 0 to 96 over 1–4 (the swing, easing out), 90 on 5 (the clang), held to 29; 90 to 0 over 30–41.** After an absorb: 100 on 48 (knocked), 0 by 56 |
| `grab` | 7 | the left hand reaching for the shoulder, the projector drawn back | stowed |
| `grab_whiff` | 22 | the hand closing on nothing, a lurch | stowed |
| `throw` | 46 | Point Blank's table: the lens on the other's chest from 6; the projector bucking on 31–33; the release on 33 | stowed (the left hand holds the shoulder) |
| `grab_break` | 20 | both arms shove | stowed |
| `thrown`, `thrown_vault`, `thrown_slam` | 46, 40, 56 | Beam's: follow the thrower's hands | stowed; the projector clear of the floor |
| `hit_air`, `knockdown`, `getup` | 30, 32, 20 | Beam's: flat on its back, the projector out to the side (not through the floor) | stowed |
| `ko` | 90 | falls back heavily, the projector dropping from the hand to lie beside it (it stays on the mount, the arm flung out), the hatch's glow dying (the effect) | stowed |
| `super` | 96 | Ground Zero's tables: on the flash, planted wide and low, the hatch thrown open, the projector raised overhead muzzle down (by 24, held); driven into the floor on 41–44; the `ground_zero` pose on 45–52, shaking; wrenched out and into the guard over 53–96 | stowed through the flash; the left arm flung out behind on 41–52 |
| `win` | 120 | the projector raised and the searchlight swept in a slow arc across the hangar's roof (1–60), then the shield swung out and rapped twice with the projector's drum (two clangs, on 80 and 92), and the guard | out (y 90) on 64–104, stowed by 116 |
| `intro` | 90 | walks out of the booth's spot lights with the projector on its shoulder, the lamp lit and swept once across the floor, then lowered into the guard | stowed |

- **The cover** (`cover.akr`'s `COVER_POSE[Gamma]`): the `win` frame with the searchlight high in
  its sweep (about 40). Set to 40 (mx-gamma-fight).
- **As animated** (mx-gamma-anim): every move is Gamma's own file on its `_body.anim.json`; every
  length, mark frame, root motion and hit box above is in the files as written (frames from 0:
  `sp_n` dig-in 0–17, ray 18–29, `charge` 29, guard on 45, vent 46–95 and the guard on 95 (the
  balance pass retimed it: dig-in 0–12, ray 13–24, `charge` 24, guard on 40, vent 41–90);
  `sp_d` swing 0–4, `shield` 5–28, the guard on 46, after an absorb 47–58), and no move needs
  `allow` or `floor_allow` beyond the rig's. Where the files differ from the words above:
  - `thrown` is 44 frames, as every mech's (Beam's is 44, not 46).
  - Scorch Sweep: the projector is 4.9 m long, so with its drum off the floor the light falls
    about 4.3 m ahead on frame 11, not 3 m (the wrist bent down like a hand holding a torch), and
    the sweep carries it to about 7.2 m on 16; the hit boxes are the table's (x 1.5–4.0 on 12 to
    x 5.0–8.0 on 16).
  - Ground Zero: a gun gripped up through the fist cannot hang muzzle down overhead, so on the
    flash the projector is raised overhead pointing up (by 23, held), and on 40–42 it is swung
    down over the top and onto the floor ahead, the lens on the floor (x about 3.3) on 43 and on
    the active frames, touching it rather than in it.
  - Lead Shielding: concept C's `shield` pose with the left elbow 8 degrees further out (the
    concept's puts the forearm in the chest) and the projector at the hip pointing about 25
    degrees down, under the shield side-on, rather than level; the right foot steps back half a
    metre into the wide stance on 0–3 and back on 34–40.
  - The Atomic Ray: the back foot drags a metre back into the `ray` stance on 0–14 and steps in
    again on 33–41; in the vent the front foot steps back with the 0.8 m stagger. The ray pose's
    lens is at about x 8.4, y 7.0. The 'projector' hurt box is a fixed rectangle, x 1.0–5.5,
    y 5.5–8.5, on 18–37; the Rod Shot's x 1.0–5.0, y 5.6–8.4 on 14–24, its kick 12 degrees.
  - The Geiger Flare's projector points about 60 degrees up (the lens at x 3.9, y 16.5), not
    concept C's straight up.
  - Win: the drum comes down on the shield's top lip from above (79 and 91), as the side-on camera
    sees it; the projector stays on the near side of the body. No marks for the clangs (frames
    79 and 91). It ends in the guard; frame 40 has the searchlight highest (about 72 degrees up),
    so the cover can stay 40.
  - Intro: the projector is carried at the shoulder pointing forward and up, not raked back over
    it (the whip antenna is there); the lamp is swept across the floor from far (66) to near (76).
  - Lying on its back (`hit_air`'s end, `knockdown`, `ko`, `thrown_slam`, `getup`'s start) the
    pelvis is 0.35 m higher than Beam's: the jerrycan rack holds the torso off the floor. In
    `ko` the projector arm sags onto the floor beyond the head instead of Beam's shaky lift. In
    `thrown_slam` the projector arm flails down and away while the left hand claws at Tank's
    wrists, so the projector and the shield stay apart.
  - The jerrycans are part of the torso's mesh: they rock with the torso's dip on the walk's plants,
    not on their own.

### For the effects and sound (Gamma)

Heartland's colours: `GMX_GLOW` 0x6EFF8C (0xBBGGRR: the concept's `#8cff6e`, the reactor's green),
`GMX_CORE` 0xE0FFF0 (white-green: the ray's core), `GMX_HALO` 0x40FF60 (Tank's reactor green),
`GMX_HEAT` the shroud's ramp 0x2030A0 (dull red), 0x2080FF (orange), 0x80E0FF (yellow-white),
steam 0xE0E0E0 at half blend; additive sprites on fx.akr's effect slot and its particles, as
`beam_fx.akr`'s and `tank_fx.akr`'s. A new file `gamma_fx.akr`, called with a line each from
`game.akr` (the drawing and `gamma_sfx` in `sound_poll`), `fx.akr` (the rod) and `hud.akr` (the
heat bar). Budget: Gamma's effects within Shadow's (about 76,000 cycles in `prof_fx` with fx.akr's
at the worst frame): the ray is a few streak sprites along its length (`bfx_streak`'s way), not
particles per metre.

**Anchors** (part frames, from `anim_part()`): the lens, (0, 0.8, −4.4) in `weapon_r`'s frame
(Beam's `BEAM_MUZZLE`); the rod's bore, (0, 0.3, −4.86) in `weapon_r`'s; the shroud's middle, (0,
0.8, −2.35) in `weapon_r`'s (the heat glow, 2.3 m long along −Z); the shield's face, (0.7, 0, 0.57)
in `weapon_l`'s frame (its centre in the concept's cameras); the chest hatch, on the sternum in the
torso's frame (read its point from the Gamma model, as `tank_fx.akr` reads Tank's window).

| Effect | When (frames from 1) | Anchor | What |
|---|---|---|---|
| The lamp | `atk_n` 8–10, `atk_f` 16–19, `atk_air` active | the lens | a white flash at the lens; for the Glare Lance a white cone from the lens over its hit box, fading at 10 m |
| The scorch | `atk_d` 13–17 | the box on the floor | a bright spot sweeping along the floor and a scorched streak behind it (12 frames) |
| The ray's warm-up | `sp_n` 1–18 | the lens; the shroud | the lens brightening, the shroud's slots lighting from the fist outward |
| **The ray** | while its hit box is out | from the lens to the box's end (13 m), or to the first mech it touches | a white-green core 0.6 m thick, a green halo 2 m thick flickering on each tick, streaks running outward along it; a glow and sparks at the contact (on the mech, or on a block at the guard); burning motes falling off |
| **The heat** | always, by `Fighter.heat` | the shroud | the slots glowing dull red from 30, orange from 60, yellow-white from 85; steam wisps from the slots from 85, a puff a frame |
| **The vent** | `sp_n` 47–96 (`Vent`) | the shroud; the hatch | a white blast of steam out of the slots on 47–56 (both ways along the barrel), then a column of steam rising and thinning; the hatch's glow flaring; the shroud fading from white through orange to dark over the vent |
| A shot burnt | `Burn` | the shot | a green-white flash 3 m across and a puff of sparks; the shot's own vanish |
| The rod | while out | the shot | a short white-hot spike with an orange glow and a long thin trail behind it (6 m), drawn before fx.akr's wave and orb branches (`sh.pierce` first); the bore's flash on firing |
| The flare | `sp_u` 8–13 | the lens; the box | a wide fan of white light up and ahead from the lens, bright for 2 frames then thinning, ticking flecks of green in it |
| **The daze** | while `Fx.dazed` (a `Daze` event starts it) | the dazed mech's head and chest | green spots swimming round its head, a faint green glow on its chest flickering, a crackle of green ticks (the Geiger count); in the air, a green streak along its drop |
| The shield | `sp_d` 5 (the clang); an absorb (`Armour`) | the shield's face | a spark at the shield's edge on 5; on an absorb, `tank_fx.akr`'s ring and glow (already drawn for every `Armour` event) and a dent-flash of white on the plate |
| The reactor | always | the chest hatch | a green glow through the hatch's slats, brighter as the meter fills, pulsing from half a bar, flaring when full (`tank_fx.akr`'s reactor rule on Gamma's hatch) |
| Point Blank | `throw` 6–33 | the lens on the other's chest | the lamp blazing white through the other's chest; the blast on 33: a white flash and a green ring |
| Ground Zero's flash | `super` 1–40 | the hatch | the hatch flaring white-green, the stage tinted toward green-white (a colour offset, as Total Eclipse's dark and Judgement's light: `gamma_fx_offset`), from 1 to the last active frame (52), fading over 53–64 |
| **The blast** | `super` 45–52, fading over 53–64 | the floor at the root | a dome of light 8 m in radius growing in 3 frames, a white flash at the impact point, a ring of dust and debris thrown out along the floor both ways, the camera's super shake |

**Sounds** (`sfx.akr`; new samples by `tools/gen_mechexpo_audio.py`; the priorities in `sfx.akr`'s
header). Until each is made, a stand-in from the existing ones (named):

| Sound | When | Priority | Stand-in |
|---|---|---|---|
| `SFX_RAY_ON`: a heavy relay clunk and a lamp's thump | the ray's first frame (`sp_n` 19) | 6 | `SFX_BEAM_LANCE` pitched 0.8 |
| `SFX_RAY`: a deep electric drone with a whine that rises with the heat (a loop, `sfx_hold`) | every ray frame, the slot of Gamma's side, pitched 0.9 + heat / 200 | 5 | `SFX_BEAM_HUM` pitched 0.7 |
| `SFX_HEAT`: a Geiger counter's clicks, quickening (a loop) | the heat over 85 and the ray on | 5 | `SFX_BEAM_PING`, repeated every 8 frames |
| `SFX_VENT`: a steam blast and a hiss falling away | the `Vent` event | 7 | `SFX_TANK_VENT` pitched 0.9 |
| `SFX_BURN`: a short sizzle | the `Burn` event | 4 | `SFX_ORB_FIZZLE` |
| `SFX_ROD`: a hard metallic crack, a rail-gun snap | the rod's release (`Shot` event: `sfx_shot(Gamma, ...)`) | 6 | `SFX_BEAM_ARC` pitched 1.3 |
| `SFX_FLARE`: a bright pop and a burst of Geiger clicks | the flare's Swing (`sp_u` 8) | 6 | `SFX_BEAM_PILLAR` pitched 1.2 |
| `SFX_DAZE`: a ringing tone with clicks (a loop) | while the other is dazed | 4 | `SFX_BEAM_GRIP` pitched 0.6, quiet |
| `SFX_SHIELD`: a steel door swung shut, a clang | `sp_d` 5 (poll the move: no hit box) | 5 | `SFX_ARMOUR` pitched 0.8 |
| The absorb | the `Armour` event | 6 | `SFX_ARMOUR` (as Tank's) |
| Point Blank | the lamp's hum on 6–30 (a loop), the blast on 33 (`sfx_throw_by(Gamma, throw)`) | 5, 8 | `SFX_BEAM_GRIP`, then `SFX_BEAM_SHOCK` pitched 0.8 |
| Normals | the Swing event (`sfx_attack(Gamma, mv)`): the lamp's snap for the jab and the lance, a sizzle for the sweep | 4 | `SFX_BEAM_ZAP` pitched 0.85 |
| The super | `sfx_super(Gamma)`: the nuclear charge-up (Tank's), with a klaxon's rising whoop | 9 | `SFX_CHARGE_NUCLEAR` (`sfx_super` gains Gamma) |
| `SFX_GROUND_ZERO`: a deep boom, a rushing shock wave, debris | the blast's Swing (`super` 45) | 9 | `SFX_TANK_SLAM` with `SFX_SUPER` |
| Steps | the walks | 2 | `sfx_step_of`: heavier than Beam's (pitch 0.9) |

The events (appended to `enum Ev` after the others, so their numbers stay): `Vent` (side: Gamma's;
x: its root), `Burn` (side: Gamma's; x, y: the shot burnt; power: its strength), `Daze` (side:
Gamma's; x, y: the dazed mech; power 0 on the ground, 1 in the air). The absorb is the existing
`Armour`; a tick held off by a Wing Ward is Seraph's `Reflect` with power 0. `game.akr`'s
`sound_event()` and `fx_event()` take them.

### Engine work needed (Gamma)

Done in mx-gamma-fight, as listed, with these differences: `fires_shot()` stays (whether a mech has
a shot at all, as the CPUs ask) beside the new `shot_move()`; `gamma_ray_advance()` also ends Lead
Shielding's held ray at the brace's last frame; a ray's later tick is told by
`gamma_ray_touch()` (its last tick touched within 6 frames), which sets `fighter.akr`'s
`tick_later` for `struck()`, `blocked()` and `absorb()` (an absorbed later tick posts no Armour and
raises no hitstop either); `Fx.dazed` is set in the daze on the ground and `Fx.daze_drop` while
the mech drops to it (not both), and `Fx.daze_spent` keeps a daze from being renewed until the
mech has been actionable; while the animations were Beam's placeholders, the stand-ins played each
of the eight moves whose animation still had Beam's length (no scan at `fight_init`; now that all
are animated, `use_standin` no longer asks, and scenario 200 checks that none is a placeholder).
Phase 1 has Gamma play Beam's moves
(the Volt Orb, the Arc Lance, the Thunder Pillar, the Reaction Prime, the Raikō Overload); the rule
should be Seraph's: Beam's code asks predicates (in a `gamma.akr`, as `seraph.akr`'s for Shadow's),
never Gamma's name, so each special moves to Gamma's own code by taking Gamma out of one
predicate. Whatever phase 1 names them, phase 2's
own are: `has_ray` (`sp_n`: the held ray and the heat), `has_rod` (`sp_f`: the Rod Shot),
`has_flare` (`sp_u`: the daze), `has_shielding` (`sp_d`: Lead Shielding), `has_point_blank`
(the throw's distance) and `has_ground_zero` (the super). **Gamma is not chemical**: the Reaction
Prime and the reaction never apply to it (`meter_power` is Nuclear, so `try_press()`'s and
`react_tick()`'s chemical tests already skip it).

1. **State** (`fight.akr`): `Fighter.heat: s32` (0..100); `Fx.ray_t: s32` (frames the ray has been
   on this move: the tick clock), `Fx.dazed: bool` and `Fx.daze_drop: s32` (a daze waiting for
   the landing); `Shot.pierce: bool` (the Rod Shot); `Hit.daze: s32` (moves.akr: frames of daze,
   0 for every other hit); `enum Ev` gains `Vent`, `Burn`, `Daze` at its end. `start_round()`
   calls a `gamma_round()` (heat 0, no daze); `fight_tick()` calls `gamma_tick(live)` after
   `shadow_tick()` (the cooling, outside the freezes).
2. **The nuclear meter for Gamma**: `meter.akr` already works by power (`meter_on_damage()`,
   `meter_can_super()`, the Siphon's quarter in `shadow_siphon()`): the `STATS` row with
   `Power.Nuclear` is all it needs. What is Tank's by name and must be by power: `hud.akr`'s
   `draw_meter()` (`fi.mech == Mech.Tank` → `meter_power(fi.mech) == Power.Nuclear`, so Gamma's
   gauge is `tank_meter_hud()`, else it falls through to `draw_antimatter()`); `sfx.akr`'s
   `sfx_super()` (Gamma → `SFX_CHARGE_NUCLEAR`); `fx.akr`'s `fx_plate()` (Gamma's paint, Heartland
   green). The reactor's glow on the mech is per model: Gamma's hatch in `gamma_fx.akr`
   (`tank_fx_draw()`'s rule, Gamma's anchor).
3. **The held ray** (`fighter.akr`'s `advance()`, beside the Sneak's line and **before the
   charge-frame rule**, which would otherwise hold it for `ORB_CHARGE_MAX`): `has_ray(f.mech) &&
   gamma_ray_advance(i)`. On the ray's frames (from its first hit-box frame to the `charge` frame,
   found once in the data as `tank_find()` finds Tank's sections): `f.heat += 1`, `x.ray_t += 1`;
   on the charge frame, hold while B is held; when the heat reaches 100, jump to the vent (the
   `sp_n` `riposte` frame), post `Vent`; a Gamma `sp_n` that did not vent ends at that frame (as a
   missed Clinch ends at its slam section, `advance()`'s Tank line). **The ticks**: every 6 ray
   frames clear the ray box's bit in `fx[i].hits`, so `strike()` lets it hit again.
4. **The ray's hits** (`resolve()`, `struck()`, `blocked()`): a tick after the first in this ray
   does not raise `fight.freeze`, posts no Hit or Block event, sets `d.flash = 3`, and does not add
   to `dx.combo` (it is scaled by the combo the first tick found: keep it in `Fx`). The pushback is
   the hit's `kb` as for any hit, so the wall's `pass_back()` already moves Gamma back off a
   cornered mech.
5. **The heat's cooling** (`gamma_tick(live)`): −1 every second live frame while the ray is not on
   and Gamma is not venting; −2 a frame through the vent; 0 on Ground Zero's first active frame.
6. **The ray against shots** (`shots_tick()`, after the meet rule): each of the other side's shots
   whose box overlaps the ray's hit box this frame (`fbox[i]`, `world_box()`, in x and y): strength
   1, `s.on = false`, heat +10, `Burn` (a vent if it reaches 100); strength 2, the shot gone and the
   ray cut; strength 3, the ray cut, the shot goes on; `pierce`, nothing. **Cutting the ray**: jump
   to the frame after the `charge` frame (the shut-off), `x.ray_t` cleared.
7. **The Parry and the ray** (`parry()`): a parried ray is cut when Gamma's `pause` ends (a flag
   read in `gamma_ray_advance()`).
8. **The Wing Ward and the ray** (once Seraph's ward exists, [Engine work needed
   (Seraph)](#engine-work-needed-seraph) item 3): in `strike()`, Gamma's ray box touching a body
   that is `seraph_warding(j)` from its front returns a new `R_WARD`: `resolve()` does nothing to
   Seraph, adds 10 to Gamma's heat, and posts `Reflect` (power 0) on the first warded tick; Seraph
   does not jump to the fling.
9. **The Rod Shot** (`fighter.akr`): the shot is `sp_f`'s for Gamma, so `try_press()`'s "one shot
   at a time" test is by the move that fires (`fires_shot()` becomes a `shot_move(m)`: `sp_n` for
   the Hero, Beam and Shadow, `sp_f` for Gamma); `shots_tick()` fires on that move's `release`;
   `shot_fire()` calls `gamma_rod_fire(i, s)` (x + 5.0, `vx` 0.60, `half` 0.6, y 6.4–7.2, `life`
   60, `str` 0, `pierce`); the meet rule skips a pair with a `pierce`; `shot_try()` skips
   `tank_armoured()` and Lead Shielding for a `pierce` shot; `shot_hit()` returns `rod_hit()` for
   it; the contact point is the middle of y0–y1 (not the wave's 1.5). Seraph's reflect keeps
   `pierce` (its ×1.25 cap at 0.45 makes the rod slower).
10. **The daze** (`fighter.akr`): `struck()` with `h.daze > 0` on a body not `dazed`: on the
    ground, the hit reaction with `stun = stun_len = h.daze`, `slide = 0`, `dazed = true`; in the
    air, `end_move()`'s fall (the last frame of `jump`, `vx = vy = 0`, `air_used`) with `daze_drop
    = h.daze`, and `advance()`'s landing (the `jump` branch) sets the dazed reaction instead of
    `land`. `grabbable()` accepts a `dazed` body in `hit_high` or `hit_low`. `to_neutral()` clears
    `dazed`; any later hit replaces the reaction (and clears it). `absorb()` ignores the daze. The
    `Daze` event.
11. **Lead Shielding** (`fighter.akr`): **`MARK_SHIELD: u32 = 4096`** in `anim.akr` (the bit after
    Seraph's planned `ward`, 2048), `'shield': 4096` in `tools/animkit/move.py`'s `MARKS`, a row in
    `docs/ANIMKIT.md`'s marks table. A one-hit armour: `resolve()` and `shot_try()` ask
    `gamma_shielded(j, mv, s)` beside `tank_armoured()` (on a `shield` frame, on the ground, not a
    super, not a `pierce` shot, not yet absorbed this move): `absorb()` (the existing function:
    damage in full, the reactor, the hitstop, `Armour`), then `fx[j].riposte = true` and the jump
    to the `riposte` frame. For a ray's tick: absorbed with no jump until the brace's last frame,
    then the jump. `grabbable()` treats `MARK_SHIELD` as `MARK_ARMOUR` (grabs beat it); `strike()`
    and `catch()` need nothing more. `advance()` already ends an `sp_d` at its `riposte` frame when
    nothing was caught.
12. **Ground Zero**: a hit box on both sides of the root (x −8.0–8.0) in the stand-ins and the
    animation, and the heat set to 0; the rest is the shared super (the `invuln` and `flash` marks,
    `struck()`'s direction away from the attacker, `twins_collide()`'s one body). Launch 0.70.
13. **Point Blank** (`throw_tick()`'s release): `vx = ft × 0.30` for `has_point_blank`, beside
    Beam's 0.24 line.
14. **Gamma's tables** (`gamma.akr`): `gamma_hit()` (the numbers of this section: jab 70, lance 105,
    sweep 90 knockdown, air 95, the ray's tick 10 / chip 2 / hitstun 10 / blockstun 9 / kb 0.26 /
    stop 8, the rod 75 / 15 / 20 / 16 / kb 0.14 / stop 9, the flare 70 / 14 / blockstun 14 / daze 32
    / stop 11, the throw 120, the super 300 / 75 / blockstun 22 / kb 0.30 / launch 0.70), its own
    stand-ins (`gamma_tm`, boxes, marks, root: this section's timings, so the fight plays before the
    animations land), the `STATS` row (1,050; 0.058 and 0.050; `pre` 6, `jv` 0.56, `grav` 0.028,
    `jvx` 0.13, `land` 7, `land_air` 10, `push` 1.7, `Power.Nuclear`), and `GAMMA_MOVES` (Lamp Jab,
    Glare Lance, Scorch Sweep, Down Flash, Atomic Ray "B (hold: heats)", Rod Shot "FWD + B
    (pierces)", Geiger Flare "UP + B (dazes)", Lead Shielding "DOWN + B (absorbs)", Point Blank
    "Y", Ground Zero "A + B, one bar", "Nuclear meter: fills as Gamma takes damage").
15. **The CPU** (`cpu.akr`): [The CPU (Gamma)](#the-cpu-gamma); `beam_neutral()` stays Beam's alone.
16. **Drawing and sound**: `gamma_fx.akr` (new: the ray, the heat, the vent, the rod, the flare,
    the daze, the shield, the hatch, Ground Zero); `fx.akr`'s shots' drawing (`sh.pierce` first)
    and `fx_update`'s no-trail branch (Gamma: no blade); `hud.akr` (nuclear by power, and a
    `gamma_heat_hud(f, s)` line after `shadow_siphon_hud`); `game.akr` (the draw and offset lines,
    `sound_event()` for the three events, `gamma_sfx(f)` in `sound_poll` for the loops); `sfx.akr`'s
    `sfx_shot`, `sfx_attack`, `sfx_throw_by`, `sfx_super`; `cover.akr`'s `COVER_POSE`.
17. **Tests** (a `tests/gamma/` of its own, as `tests/seraph/`, at the next free scenario numbers):
    the heat (+1 a ray frame, −1 every second frame off, the vent at 100: 50 frames, cold at its
    end; a vent punished); the ray's ticks (10 every 6 frames, one hitstop, unscaled after the first
    in a clean ray, 2 chip a tick, the push to the tip, a cornered mech pushing Gamma back); the ray
    against the wave (under it, hits Gamma), the three orbs (burnt +10, cut, cut and through), a Hex
    Bolt and a Mark bolt (burnt, no curse or mark), a rod (through), the Parry (cut), the Void Step
    (through), Tank's armour (absorbed, no push), the Wing Ward (no damage, +10 a tick), Lead
    Shielding (held to the brace's end); the Rod Shot (0.60 m a frame, through every shot, through
    Tank's armour and Lead Shielding, one twin, one at a time, reflected at 0.45); the daze (32 frames on the ground,
    grabbable, no slide, a hit ends it, the next hit at 80 %, no re-daze; in the air the drop and
    the daze on landing; the Ray from a high catch); Lead Shielding (one hit, full damage and the
    reactor's 3 a point, actionable 12 after, a grab and a super beat it, a shot absorbed, a rod
    not); Ground Zero (both sides, 8 m, invulnerable 1–45, 300 / chip 75, a ring-out within 5 m of
    an open edge, the heat to 0); Point Blank's 10 m; the nuclear meter on Gamma (damage, chip,
    absorbed hits; carried over). The budget scenarios are measured again with a Gamma in them.
    (Built in mx-gamma-fight as scenarios 220-230 in `tests/harness.akr`, the fight alone, as
    Seraph's 170-181 are, with 200 and 201 rewritten for Gamma's own numbers; the rod against the
    split Twins and the meter's carrying over are the shared rules' tests.)

### Phase 1: what is in the game now

Phase 2's fight and CPU (mx-gamma-fight) are in: Gamma plays its own moves as this section has
them, its rules in `gamma.akr` and its CPU at the end of `cpu.akr`, and Beam's predicates
(`has_volt_orb`, `has_shock_grip`, `has_arc_fx`) are Beam's alone. Its animations are its own
since the animators' part landed; until then a move whose animation still had Beam's length (each
of Gamma's eight own moves differs from Beam's in length; the air attack, the grab and the throw
are Beam's timings in this section too) was played from `gamma.akr`'s stand-in data (this
section's timings, boxes, marks and root motion). The frames the rules need (the charge and vent
frames, the brace's frames) are read once from the animation's marks. The rest of this list is
phase 1's record, with what changed in phase 2 said:

- **Real**: the model and rig (concept C refined, `models/gamma/`: the projector on Beam's mount,
  its muzzle Beam's (0, 0.8, −4.4) in `weapon_r`'s frame; the shield on `weapon_l`, stowed at 0,
  swung out at (0, 90, 0)), the roster row (GAMMA, HA-58, Heartland's emblem, stats `0x3253`,
  Beam's since its numbers were Beam's, `0x3254` since phase 2's fight: armour 4 for the 1,050
  health; 11.9 m to the top of the searchlight; the owner's blurb
  "THE GUNNER:\nRAYS, LEAD", 61 and 50 px of the spec sheet's 76), and the **nuclear meter**: 3
  meter a point of damage taken, nothing for landing hits, carried over between rounds, the super
  at a full bar, the HUD's reactor gauge and the reactor hatch's glow brightening with it
  (`meter.akr`, `hud.akr` and `tank_fx.akr` go by the power source, so Tank's play as before).
- **Placeholders**: every animation is Beam's on Gamma's rig (`anims/gamma/`, each `"base":
  "../beam/MOVE.anim.json"`, the shield `"still"`); every hit's numbers (`gamma_hit` returns
  `beam_hit`); health, walk and jump Beam's (`STATS`); `sp_n` the Volt Orb (`has_volt_orb`), `sp_f`
  the Arc Lance, `sp_u` the Thunder Pillar, the throw the Shock Grip (`has_shock_grip`), the
  super the Raikō Overload, Beam's discharges drawn over the boxes (`has_arc_fx`); `sp_d` plays
  the Reaction Prime's animation as a brace and starts no reaction (the meter is not chemical);
  the CPU plays it as Beam without the prime (`cpu_as_beam`); the sounds are the general ones (a
  swing for the orb, the kinetic charge-up for the super); the training move list is Beam's under
  Gamma's meter. (Phase 2's fight replaced the hits, the health, walk and jump, the specials, the
  throw, the super, the CPU and the move list; the animations, the drawing and the sounds are the
  other two parts'.)
- **The arcade**: Beam's final is Gamma ("HEARTLAND ATOMIC CO. PRESENTS ITS COMPETING PRODUCT"),
  Gamma's final is Beam (defending its title); Gamma's grey copy is packed as every body's is.

## Reactions and the rest of the list

| Move | Length | Notes |
|---|---|---|
| `idle` | 60, a loop | breathing: a slow rise and fall of the chest, the weapon steady |
| `walk_f`, `walk_b` | 48 (Hero), 40 (Double-blade), loops | two heavy steps; `step` marks on the plants |
| `crouch` | 8 to get down, then held | a loop of the last frame is fine |
| `jump` | 42 (Hero), 37 (Double-blade) | crouch, launch, tuck, extend for landing |
| `land` | 8 | the knees take the weight |
| `block` | 4 to raise, then held | weapon(s) across the body, the arm braced; blockstun is played on the held frames, shaken by the fight |
| `hit_high` | 20 | the torso snaps back from the waist, the head follows, back to stance; stretched to the hitstun |
| `hit_low` | 20 | the same from a crouch |
| `hit_air` | 30, the last frame held | thrown up and back, limbs loose, rotating back about 60° |
| `knockdown` | 32 | hits the floor flat on its back, a bounce, lies still |
| `getup` | 20 | rolls up to the stance |
| `ko` | 90 | falls back heavily, sparks, stays down |
| `win` | 120 | a show-floor pose: the Hero raises the sword overhead; the Double-blade Hero flicks its blades out to the sides |
| `intro` | 90 | walks out of the booth's spot lights into the stance |
| `grab_whiff` | 22 | the grab's miss (or the end of the grab animation when nothing was caught) |
| `thrown` | 44 (40 against the Vault Throw) | follows the thrower's hands; the fight places the root |
| `grab_break` | 20 | both arms shove; each mech slides back 3 m |

**Marks** the fight reads (F sets them per frame; anim.akr's `MARK_*`): *cancel* (the neutral
and forward attacks, from the first active frame to 6 frames after the last: without it no
chain works), *invuln* (Rising Arc, the supers), *flash* (the supers' first 40 frames: the
length of the freeze is the count of these frames), *step* (foot plants in the walks),
*release* (the wave's frame in `sp_n`, the slam in `throw`), *riposte* (the first frame of the
Parry's riposte section), *parry* (the Parry's stance frames, 4–24), *nopush* and *hide* (the
Void Step's gone frames, 7–18).

## Decided by the owner (2026-10-12)

- The Hero keeps the Kinetic Wave; the Double-blade Hero's Void Step and Antimatter Slide stay.
- The Parry does not catch the super.
- The Double-blade Hero's weaker defence is its lower health (950); retune after human play.

## Decided by the owner (2026-10-13)

- The Twins' names: twin A is **ONE**, twin B **ZERO**, the combined form **BINARY**. The roster
  and the catalogue show the pair as ONE & ZERO (BM-2X); the HUD and the round banners show
  ONE & ZERO split and BINARY combined (`fighter_short()` in `ui.akr`).
- Beam's Arc Jab hits as far as its cannon reaches (x 1.8–9.0); the cannon is hurtable to its
  muzzle on frames 6–14.

## Decided by the owner (2026-10-13): Shadow

- Shadow is Umbral Research's base mech (antimatter), slot 1, SHADOW, model UR-01; about 900
  health (the lowest), a walk between the Hero's and the Double-blade Hero's.
- Block stops every attack from either side: Shadow's tricks come from timing, grabs, space (the
  mine) and the meter (the curse), never from teleporting behind.
- Exaggerated shadowy claws (the weapon parts), a tall thin body, rigid cape plates, one violet
  eye.
- The Hex Bolt and its Siphon curse (about 6 s, refreshed, never stacked), the Rift Mine (one at
  a time, a snare of about half a second, a hit destroys it), Shadow Sneak (holding B sends the
  shadow farther), Eclipse Rise (the anti-air), Phantom Grip (the side swap), Total Eclipse (the
  stage dark, a multi-hit with afterimages). Afterimages are visual only.

## Decided by the owner (2026-10-13): the arcade ladder

Built by mx-ladder; how it works is in [README.md](README.md#the-arcade-ladder).

- **Length:** two company fights, then the final: three fights a run (`LADDER_N` in `ladder.akr`,
  so it can become three company fights later).
- **The company fights:** each against the base mech of a rival company, drawn at random per run
  (from the run's seed, so scenarios replay), never your own maker and never the final
  opponent's maker, no company twice. The Twins (Binary Mechanica) may be drawn while they are
  still locked.
- **The final:** your echo (as a base mech), or the original (as an echo: the Double-blade Hero
  meets the Hero, "defending its title"). A mech whose echo does not exist yet (Shadow, Beam,
  Tank, the Twins) meets the UAPC test unit: a copy of your own mech in the UAPC's plain grey,
  the client's own evaluation unit (it sets up the secret boss: the UAPC builds its own mechs).
  Its grey is made by the model pack's generator for every body (the Twins: both twins and the
  combined form). A real echo takes over once its roster slot gets its mech.
- **Difficulty:** chosen before a run: EASY, NORMAL, HARD (on screen with the expo's names PUBLIC
  DEMO DAY, TRADE TRIAL, FULL UAPC AUDIT). EASY must be beatable by a novice who mashes: a new
  CPU level below level 0 (the novice: slow reactions, rarely blocks, no chains, no supers,
  rarely grabs), measured against a scripted masher (scenario 116). NORMAL is near the MVP's
  ladder (levels 1 and 2); HARD ramps to level 3. The levels ramp within a run; the final is the
  hardest fight.
- **Any difficulty unlocks:** clearing the ladder on any difficulty counts for every unlock rule.
- **Clear icons:** each roster slot keeps the difficulties cleared with it, shown as bronze,
  silver and gold APPROVED seals on the select grid's card and the catalogue's spec sheet. The
  save's version is 2; a version-1 save keeps its clears and unlocks, its clears (the MVP's
  ladder at CPU levels 1-2) counted as NORMAL.
- **Losing:** unlimited continues: the same fight again ("REQUEST ANOTHER DEMONSTRATION?"), or
  the title. (Easy to change.)
- **Tone:** no wrestling announcer and no hype MC on the VS card (its layout stays). Everyone is
  plainly enjoying giant robots smashing each other, but it is all presented as dry, serious
  procurement business. The round calls in that voice in every mode (TEST 1, COMMENCE,
  CONCLUDED, TIME EXPIRED, OUT OF BOUNDS, MEETS THE REQUIREMENTS); a schedule page between
  fights (the expo's programme for the day, earlier results stamped, the next highlighted); the
  final's reveal played up, deadpan ("UMBRAL RESEARCH PRESENTS ITS COMPETING PRODUCT", "THE UAPC
  WILL NOW EVALUATE YOUR PRODUCT AGAINST ITS OWN TEST UNIT", "MOMENTUM ROBOTICS DEFENDS ITS
  TITLE").
- **The cover, the owner's notes (2026-10-13):** no mech animation: a photograph, the mech
  frozen in one strong pose; a victory fanfare when it appears (a corporate award jingle that is
  secretly a banger); headlines from pools by case, maker and mech, and a larger pool of side
  teasers, picked per run, so covers differ.
- **Endings are magazine covers:** after the final, your mech live in 3D in its win pose under a
  masthead, a headline and side teasers: one layout, text per case (a base mech wins: CONTRACT
  AWARDED; an echo beats its original: UPSET AT THE EXPO; a win over the test unit: EVALUATION
  PASSED), teasers about what is still locked ("WHO IS BINARY MECHANICA?"). Then the unlock
  screen if something unlocked, then the title. The masthead is PROCUREMENT TODAY, the owner's
  pick.

## Decided by the owner (2026-10-14): Seraph, Momentum's angel

**SERAPH** (card SERAPH), Momentum Robotics' echo of Shadow, model MR-02, in the echo slot under
Shadow (unlocked by clearing the arcade with Shadow), on Shadow's skeleton plus three joints
(`wing_l`, `wing_r`, `halo`). The model is concept A, round 4b (`concepts/angel_a/`, promoted to
`models/seraph/`). Kinetic meter (Momentum's). Phase 1 is built
([Seraph](#seraph-momentum-robotics-kinetic): the mech, its numbers and fists, Shadow's moves as
placeholders); the moves below are planned. Shadow's trickster mirrored as an honest boxer: over
the floor where Shadow goes under it, shots sent back, a mark instead of a curse.

- **Look:** white plates on a gunmetal frame; red on the gauntlets and cuffs, the armour's edges
  (the pauldron rims stay) and the solid upper wing plates; chrome flight plates with a white
  trailing edge; gold only on the halo, crest, core setting and knuckles.
- **`sp_n` Mark of Judgement:** a slow bolt of light (the Hex Bolt's slot). On hit it marks the
  other mech for about 6 s instead of cursing it; Judgement against a marked mech does more
  damage (below).
- **`sp_f` Seraph Dive:** a hop, a glide on spread wings (holding B glides farther), a diving
  straight. In the air, so it passes over the floor (a wave, a Rift Mine, Shadow Sneak's shadow)
  and anything that hits in the air stops it.
- **`sp_u` Ascension:** the anti-air: a rising uppercut, the wings flaring, invulnerable on its
  first frames.
- **`sp_d` Wing Ward:** the folded wings wrap forward as a shield for about 20 frames; a shot that
  touches it is sent back as light, now the angel's. Strikes are not caught (the Hero's Parry
  does that).
- **`atk_d`:** a sweeping low kick that knocks down (Shadow's Fade Sweep does not carry over).
- **Throw (Y), over the top:** it grabs, beats its wings, carries the other mech over its head and
  slams it down on the far side: the sides swap, as in Shadow's Phantom Grip, over instead of
  under.
- **Starting numbers** (to tune in play): about 1,000 health (the Hero's; Shadow has 900), a walk a
  little slower than Shadow's; the card's blurb "THE PALADIN:\nWARDS, JUDGEMENT".
- **Super, Judgement:** the fist raised, the wings spread, the halo lifts on its joint (0.9 m);
  a white-gold column of light slams down on the other mech, the halo's flare drawn by the
  effect. The column lands where the other mech stands as the freeze ends; against a marked mech
  it does about 50 % more; blocked, it chips like the other supers. A second mark refreshes the
  mark's time (never stacks), as the Siphon does.
- To do with the move set: the fist reaches about 3 m less than Shadow's talons (Lunging Claw's
  and Claw Jab's hit boxes, or the arm keys); Shadow's weapon-joint keys are zeroed; new
  animations for the idle, intro, win, `atk_d`, the four specials and the super.

## Decided by the owner (2026-10-14): Gamma, Heartland's ray gun

Planned, not designed in numbers yet: Heartland Atomic Company's echo of Beam, in the echo slot
under Beam (unlocked by clearing the arcade with Beam), on Beam's skeleton (the Hero's). Named
**GAMMA** (card GAMMA); model HA-58 (after Tank's HA-57). Nuclear meter (Heartland's: fills as it takes damage).

- **Look: military surplus** (concept C, `concepts/gamma_c/`, refined in `models/gamma/`; chosen
  over an atomic-age ray gun and a walking reactor plant). Phase 1 is built
  ([Gamma](#gamma-heartland-atomic-company-nuclear): the mech, the nuclear meter, Beam's moves as
  placeholders). Beam's frame refitted from army
  surplus: a searchlight head with a whip antenna, a louvred reactor hatch on the chest (the
  meter's glow), jerrycans and a toolbox racked on the back, primer-grey replacement panels on
  Heartland's faded green; Raikō's Arc Cannon becomes a searchlight converted to a ray projector
  (the muzzle at Beam's effect point); Lead Shielding is a field gun's shield stowed on the left
  forearm (`weapon_l`) and swung out in front for the brace.
- **How it plays:** a slow, heavy zoner that gets stronger when the plan fails: every hit that
  gets through fills its reactor.
- **`sp_n` the Atomic Ray** (the Volt Orb's slot): a held ray, on while B is held: a beam, not a
  ball, that pushes the other mech back. The gun heats while it runs; held too long, it vents
  and leaves the mech open.
- **`sp_f` Rod Shot** (the Arc Lance's slot): a fast spike fired from the barrel that pierces.
- **`sp_u` Geiger Flare** (the Thunder Pillar's slot): the anti-air: a burst of light upward that
  stuns briefly on hit.
- **`sp_d` Lead Shielding** (the Reaction Prime's slot): it braces behind a shield; the next hit
  is absorbed (like Tank's armour), and its damage still feeds the reactor.
- **Super, Ground Zero:** a blast all round it at short range: the zoner's answer to a mech that
  has got in.

## Balance patch (2026-10-13)

Measured with `tests/balance/matrix.sh` (CPU level 2 against level 2, every pairing, the sides
swapped every match, `table.py` prints the win rates and why), on the hangar, with Shadow fully
animated. Before: across 60 matches a pairing (seeds 1 and 2) the Hero won 83 % overall and the
Twins 20 %; the Hero beat Beam 95 % and Shadow 87 %, and the Twins beat no one more than 37 %.
After: across 150 matches a pairing (seeds 1 to 5) every mech won 47-55 % overall and every
pairing came out between 34 % and 66 %. The last two changes (the Siphon's antimatter and
nuclear shares) were measured only on the Shadow pairings. A single run of 30 matches is ±9 %
of noise, so one seed alone still puts a few pairings outside 35-65 %.

**The CPU** (`cpu.akr`; mostly blind spots that made a mech lose a matchup by playing it badly):

- Chains on a blocked hit go on half as often, and only a hit that landed is cancelled into the
  super. Before, the CPU always threw its punishable special (or its super) after a blocked hit.
  This was the biggest single change.
- It keeps off the other's Rift Mine once it is about to arm: it clears the mine with its down
  attack (the Hero with its wave), jumps it or waits, and a chain's dash or slide never ends on it.
- A shot coming is reacted to even mid-walk. The wave is blocked while it is far and jumped only
  once it is close. A shot above the floor (the orb, the bolt) is blocked or gone under: the Void
  Step, Shadow Sneak, the split Twins' Low Roll, the Hero's wave against a tap orb or a bolt,
  Beam's charged orb.
- Beam fires orbs only from outside the other's poke, walks back only while there is room behind
  it, and answers a far wave with a charged orb. Every CPU punishes with its jab out to the jab's
  own reach (Beam's Arc Jab reaches 9 m).
- Shadow ends its chain with the Hex Bolt (MOVES.md's chain) instead of the Sneak. It fires no
  bolt in neutral inside the other's poke or at a mech with a stronger shot (the Hero, Beam), and
  against those it lays a mine only while they are down.
- The Twins, cursed, stay split until the curse ends and split from combined only when that is
  safe; they roll under long pokes more often.
- Tank blocks a super it sees coming instead of meeting it with armour.

**The numbers:**

| What | Was | Now | Why |
|---|---|---|---|
| The Hero's Tip Thrust | 120 | 100 | The Tip Thrust into Charge Slash at 9-11 m decided most of the Hero's matches |
| The Hero's Charge Slash | 130, chip 26 | 95, chip 19 | The same |
| Kinetic meter, a landed hit | 150 | 125 | The Hero's super came about every eight hits and landed almost every time |
| The Double-blade Hero's Twin Cut / Cross Lunge / Charge Slash | 60 / 100 / 110 (chip 22) | 65 / 110 / 120 (chip 24) | It lost to everyone but the Twins |
| Beam's Static Lance | 110 | 100 | Beam's mid range beat the rushdown mechs |
| Beam's Arc Lance | 100, chip 20 | 85, chip 17 | The same |
| Tank's health | 1,100 | 1,150 | Supers and combos landed on it at will |
| Tank's Piston Haymaker | 140 | 150 | The same |
| Nuclear meter | 5 for every 2 damage (a bar per 480) | 3 for every point (a bar per 400) | Tank's comeback came too late |
| The split Twins: Bit Jab, Byte Kick, Low Bit, Drop Kick | 40, 60, 55, 50 | 50, 76, 68, 60 | Each twin's hit was too light to win a round |
| Pulse Spin, Dash Kick, Rising Kick, Tag Toss | 45, 80, 70, 100 | 56, 100, 88, 120 (chip 11, 20, 18) | The same |
| Fusion meter, combined | +1 a frame | +2 a frame (a bar in 10 s) | The Twins' super came about once in three rounds |
| Shadow's Claw Jab / Lunging Claw | 45 / 100 | 50 / 105 | It lost to the Hero and Beam once its mine and bolt were played sensibly |
| The Siphon on antimatter | all | half | The cursed Double-blade Hero's reactor fed Shadow's supers |
| The Siphon on nuclear | half, Tank kept none | a quarter, Tank keeps the rest | Tank's comeback meter was frozen whenever it was cursed |

Unchanged: every frame timing, box, root motion and mark; the curse's 6 s, the snare and the
health of the Double-blade Hero and Shadow (the owner's decisions).

## Balance pass (2026-10-14): Gamma and Seraph

Approved by the owner, made in mx-gamma-fight. Measured with `tests/balance/run.sh A B` (CPU
level 2 against level 2, 10 matches against each base mech, the sides swapped every match, on the
hangar); the aim was each mech winning roughly 20 to 40 of its 60 (Shadow's 50, against the five
others, as the control).

**The changes:**

| What | Was | Now |
|---|---|---|
| Gamma's Atomic Ray: the dig-in | 13 frames (the ray on 13–24 from 0, `charge` 24, `riposte` 41, 41 frames, 91 with the vent) | **18** (the ray on 18–29, `charge` 29, the shut-off 30–45, `riposte` and the vent 46–95; 46 frames, 96 with the vent): `anims/gamma/sp_n.anim.json` retimed, every key after the dig-in 5 frames later |
| Gamma's Atomic Ray: the reach | x 2.5–16.0 | **x 2.5–13.0** (`GM_RAY_X1`; the effect's length goes with the box) |
| The other CPUs against the ray | slide, roll or Sneak under it at `lv.special` × 3 | × 5 from beyond 6 m (`under_ray`); blocked otherwise, which the 18-frame dig-in now allows at level 2 (a jump does not clear the ray: it meets every jump) |
| Seraph's Judgement: the lock | on the first frame after the flash (41 from 1) | the column **follows** the other's root for 8 frames after the flash (41–48) and **locks** on 48 (`SER_FOLLOW`); the column on 49–58 as before; box, damage and the marked bonus unchanged |

**The counts** (wins of 60; against the Hero, the Double-blade Hero, Beam, Tank, the Twins, Shadow):

| Mech | Before | After |
|---|---|---|
| Gamma | **60** (10, 10, 10, 10, 10, 10) | **43** (3, 8, 10, 5, 9, 8) |
| Seraph | **18** (4, 3, 3, 5, 1, 2) | **18** (4, 3, 3, 5, 1, 2) |
| Shadow (the control, of 50) | **22** (4, 5, 3, 7, 3, —) | **22** (4, 5, 3, 7, 3, —) |

**The second steps, tried and not kept.** Gamma at 43 and Seraph at 18 after the first changes,
each was given the one further step the owner allowed, and neither helped, so neither is in:

- Gamma's push a tick (the tick's knockback, 0.26): 0.20 (about 1.0 m a tick) gave Gamma **51** of
  60, 0.34 (about 1.7 m) **49**. A lighter push holds a mech in the ray for more ticks, a heavier one
  puts it at the tip sooner, where the rod waits; 0.26 stays.
- Seraph's Judgement startup, 48 to 46 from 0 (the column on 46–55, the move 90 frames): **17** of
  60, and it cost the Double-blade Hero's Void Step its escape (started on the first frame after
  the flash, it is still sinking on 46: scenario 180). 48 stays. Judgement is not where Seraph
  loses: the level-2 CPUs block on its flash (see Seraph's measured paragraph).

What the counts still say: Gamma sweeps Beam (10 of 10), and Seraph loses to the Twins and Shadow
(1 and 2 of 10). Both are the owner's to look at in play.

## Open questions

- The Double-blade Hero's second Twin Cut: one animation played twice, or an `atk_n` variant?
  (The animator's call.)
- Beam's product name. Proposed: keep BEAM MECH on screen with the model number RC-03 (as the
  Hero is the MR-01 HERO MECH), or name it in Raikō's house style, RC-03 RAIJIN ("thunder god";
  Raikō means "lightning flash"). `ui.akr`'s `mech_name()` is the one place to change.
- Beam against the Kinetic Wave: the strength rule above (a tap orb loses, a charged orb
  trades, a full orb wins). Retune after human play.
- Tank's product name. "Tank" stays the code identifier; proposed: **HA-57 "Homestead"**
  (Heartland's farm-and-family feel; the serial plate already reads HA-57), or "Big Iron", or
  "Ironside". The menus show TANK until it is decided.
- Tank's armour absorbs every hit while its marks last (a chain cannot follow an absorbed hit,
  so in practice one). If that proves too strong, cap it at one hit a move.
- The nuclear meter's rate (a bar per 400 damage taken) and whether it carries between rounds
  (it does) want human play.
- The Twins' fusion rate (+2 a frame combined, a bar in 10 s) and whether every round should
  start split (it does) want human play; so does the partner's delay (6 frames).
- Ring-outs (mx-stages's defaults, [Stages and ring-outs](#stages-and-ring-outs)): a ring-out
  ends the round outright; the alternatives are a heavy damage penalty, or a ring-out only
  below some health. The rooftop starts 2P with its back to the drop (17 m from the edge, 1P
  17 m from the wall); swapping the starting sides each round would even it. Twin B falling
  costs the round (the other choice: twin B always pulled back by its leash). CPU against CPU
  rarely rings out (none in 20 rounds of scenario 96: the fights drift away from the edge);
  the CPU's edge play wants tuning with human play.
- Shadow's snare holds the snared mech in the pose it had (cut to `idle`, frozen) with violet
  shadow binding its legs. A dedicated `snared` reaction for every mech would read better and
  costs every mech's animator a move; proposed for later.
- The Siphon's rates (all of every source, nuclear at a quarter) and the curse's length (6 s) want
  human play; so do Shadow's health (900) and the Rift Mine's snare (30 frames).
- The arcade ladder's grades (mx-ladder): the scripted masher beats the novice, level 0 and
  level 1 alike (94-97 % of matches) and level 2 only 38 % (README.md, "The arcade ladder"). So
  EASY's final could take level 1 without getting hard, and NORMAL's final (level 2) is a big
  step from its company fights (level 1); both want the owner's own play.
- The test unit's grey is one ramp for every body; a UAPC marking on it (a roundel on the
  shoulder) would need a texture in the grey parts.
- Seraph's numbers (this file's Seraph section, 2026-10-14) want human play: the mark's ×1.5 on
  Judgement (it does not stack with the antimatter debt: the larger applies), the column's 8-frame
  follow (one frame from the lock to the column) and its 5 m width, a reflected shot's ×1.25, the
  Wing Ward's 20 frames, the Dive's 28 frames of startup and its 24-frame hold. Two of this
  section's choices are interpretations of the owner's decisions: the mark does not raise
  Judgement's chip, and a reflected Hex Bolt marks rather than curses. The throw's name, Heaven's
  Arc, and the normals' (Jab, Lunging Straight, Reaping Kick, Double-fist Dive) are proposals.
  Seraph falls face down (its wings on its back) where every other mech falls on its back.
- Gamma's numbers (this file's Gamma section, 2026-10-14) want human play: the heat (100 frames of
  ray from a cold gun, 200 frames to cool from hot, the 50-frame vent), the ray's 13 m (16 before
  the balance pass), its push (about 1.4 m a tick hit, 1.1 blocked) and its tick (10, chip 2, every
  6 frames), the Rod Shot's 0.60 m a frame and its piercing of armour, the daze's 32 frames, Lead
  Shielding's 24-frame brace and 12-frame turn, Ground Zero's 8 m and 300. The proposals below, each
  with this file's recommendation; all but the model number were decided by the owner (2026-10-14),
  approved as proposed:
  - **The normals' names**: Lamp Jab, Glare Lance, Scorch Sweep, Down Flash (Beam's four with the
    searchlight in place of the arcs: Beam's timings, a frame slower where Beam's is quick, a
    little heavier). Recommended. **Decided by the owner (2026-10-14): approved as proposed.**
  - **The throw**: Point Blank, the lens jammed against the other's chest and the ray fired: 120,
    the other thrown about 10 m (Beam's Shock Grip, 130 and 9 m), back out to the ray's middle.
    Recommended. **Decided by the owner (2026-10-14): approved as proposed.**
  - **Health and walk**: 1,050 health (between Beam's 1,000 and Tank's 1,150: the nuclear meter
    needs Gamma to live through the damage that fills it) and the slowest walk on legs, 0.058
    forward and 0.050 back (Beam 0.062 and 0.058): it pushes a mech away instead of walking away.
    Recommended; the walk back is the number most likely to need raising. **Decided by the owner
    (2026-10-14): approved as proposed.**
  - **Interpretations of the owner's decisions**: the Wing Ward holds the ray off and turns each
    warded tick into 10 heat (a held beam has nothing to reflect: neither a reflect nor a strike);
    the alternative is to treat the ray as a strike, which hits a warding Seraph like the Arc
    Lance. Lead Shielding absorbs one hit, but a whole ray while the brace lasts (lead stops the
    ray). "Piercing" is through shots and through armour, never through a mech (it hits once).
    The daze is a hit reaction with other rules (no knockback, grabbable, one opening, not
    renewed), and in the air the mech drops and is dazed on landing rather than knocked down.
    Ground Zero empties the gun's heat. The heat shows on the gun and on the HUD. **Decided by the
    owner (2026-10-14): approved as proposed.**
  - **The model number**: HA-58 (after Tank's HA-57), decided by the owner (2026-10-14): approved as proposed.
