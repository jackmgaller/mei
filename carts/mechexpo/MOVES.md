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

**The separation limit and the walls.** The mechs are never more than 36 m apart, and the
hangar's walls are at x = ±36. Either stops a mech walking, jumping or being knocked further;
both are corners.

**Facing.** A mech turns to face the other whenever it is on the ground and idle, walking,
crouching or blocking; during a move or in the air it keeps its facing (a jump over the other
mech lands facing the wrong way and turns on landing).

## The meters

One bar of power, shown as a gauge, spent all at once on the super (A + B).

**Kinetic (the Hero, Momentum Robotics): fills by landing hits.** +12.5 % of a bar for each hit
that lands (+10 % for the wave), +5 % for a hit the other blocks, nothing for being hit or for
missing. A bar takes about eight landed hits, about a round's worth. The meter carries over between rounds. Rewards
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
| `atk_f` Tip Thrust | 13 | 4 | 21 | 38 | 120 | 26 / 18 | −7 / +1 | x 4.0–10.4, y 6.5–8.5 |
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
| `sp_f` Charge Slash | 16 | 4 | 26 | 46 | 130, knockdown | 26 | — / 16 | −14 / KD +43 |
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
| `atk_n` Twin Cut | 5 | 3 | 11 | 19 | 60 | 17 / 12 | −2 / +3 | x 1.8–5.8, y 5.5–9 |
| `atk_f` Cross Lunge | 10 | 4 | 18 | 32 | 100 | 24 / 17 | −5 / +2 | x 2.5–7.6, y 5–9 |
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
| `sp_f` Charge Slash | 13 | 4 | 24 | 41 | 110, knockdown | 22 | — / 15 | −13 / KD +45 |
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
| `atk_n` Arc Jab | 6 | 3 | 15 | 24 | 65 | 19 / 14 | −4 / +1 | x 1.8–5.6, y 6–9 |
| `atk_f` Static Lance | 14 | 4 | 22 | 40 | 110 | 26 / 19 | −7 / 0 | x 3.5–9.4, y 6–8.5 |
| `atk_d` Ground Spark | 12 | 5 | 24 | 41 | 85, knockdown | — / 16 | −13 / KD +41 | x 1.5–7.5, y 0–2 |
| `atk_air` Down Arc | 9 | 6 | to landing | 32 | 90 | 20 / 15 | by height | x 0.5–5.5, y −3–3 (from the root, in the air) |

(The on-block and on-hit columns are measured by `tests/run.sh 17` with the stand-in timings and
boxes, against a standing Hero.)

- **Arc Jab** (`atk_n`): Beam's answer up close and the chain's start. The cannon is short-armed
  straight forward, muzzle first, a stab with a crackle at the muzzle (frames 1–5: the elbow
  draws back 20°, the cannon tilts up a little; 6–8: the arm punches out level, the muzzle at
  about 5 m; then it is pulled back to the guard by frame 20). Little body motion: the torso
  turns into it 10°. The arm is hurtable to 3 m out from frame 7 until it is back.
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
| `sp_f` Arc Lance | 20 | 6 | 24 | 50 | 100, knockdown | 20 | — / 18 | −12 / KD +40 (at 7 m) |
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
  coils charge), and the beam fires from the muzzle on frame 21: a straight bolt out to 15 m (a
  box from x 2.5 to 15, y 6 to 8), held for 6 frames, the body pushed back by the recoil, then
  24 frames of recovery with the barrel smoking. The arm and the muzzle are hurtable to 5.5 m
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

## Open questions

- The Double-blade Hero's second Twin Cut: one animation played twice, or an `atk_n` variant?
  (The animator's call.)
- Beam's product name. Proposed: keep BEAM MECH on screen with the model number RC-03 (as the
  Hero is the MR-01 HERO MECH), or name it in Raikō's house style, RC-03 RAIJIN ("thunder god";
  Raikō means "lightning flash"). `ui.akr`'s `mech_name()` is the one place to change.
- Beam against the Kinetic Wave: the strength rule above (a tap orb loses, a charged orb
  trades, a full orb wins). Retune after human play.
