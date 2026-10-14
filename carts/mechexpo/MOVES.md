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
stairwell's housing (a wall) at x = −26 and an open edge at x = +26. The rules at an open edge
(`fighter.akr`, the ring-out block at its end):

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

## Decided by the owner (2026-10-14): Momentum's angel

Planned, not built: Momentum Robotics' echo of Shadow, model MR-02, on Shadow's skeleton plus three
joints (`wing_l`, `wing_r`, `halo`). The model is concept A, round 4b
(`concepts/angel_a/`, on its own branch for now). Kinetic meter (Momentum's). Shadow's trickster
mirrored as an honest boxer: over the floor where Shadow goes under it, shots sent back, a mark
instead of a curse.

- **Look:** white plates on a gunmetal frame; red on the gauntlets and cuffs, the armour's edges
  (the pauldron rims stay) and the solid upper wing plates; chrome flight plates with a white
  trailing edge; gold only on the halo, crest, core setting and knuckles.
- **`sp_n` Mark of Judgement:** a slow bolt of light (the Hex Bolt's slot). On hit it marks the
  other mech for about 6 s instead of cursing it; Judgement against a marked mech does more
  damage.
- **`sp_f` Seraph Dive:** a hop, a glide on spread wings (holding B glides farther), a diving
  straight. In the air, so it passes over the floor (a wave, a Rift Mine, Shadow Sneak's shadow)
  and anything that hits in the air stops it.
- **`sp_u` Ascension:** the anti-air: a rising uppercut, the wings flaring, invulnerable on its
  first frames.
- **`sp_d` Wing Ward:** the folded wings wrap forward as a shield for about 20 frames; a shot that
  touches it is sent back as light, now the angel's. Strikes are not caught (the Hero's Parry
  does that).
- **Super, Judgement:** the fist raised, the wings spread, the halo lifts on its joint (0.9 m);
  a white-gold column of light slams down on the other mech, the halo's flare drawn by the
  effect.
- To do with the move set: the fist reaches about 3 m less than Shadow's talons (Lunging Claw's
  and Claw Jab's hit boxes, or the arm keys); Shadow's weapon-joint keys are zeroed; new
  animations for the idle, intro, win, `atk_d`, the four specials and the super.

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
