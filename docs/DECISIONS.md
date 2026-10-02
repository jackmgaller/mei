# Implementation decisions

The spec (`spec-v0.1.txt`) is authoritative. This file records how this implementation
settles the open questions and the details the spec leaves ambiguous. Everything here
is deterministic.

## Open questions from the spec

| Question | Decision |
|---|---|
| Random numbers | xorshift32 (`x ^= x<<13; x ^= x>>17; x ^= x<<5`). Reset seed `0x4D454921`. Reading `RAND` advances the state and returns it. Writing sets the seed; writing 0 sets it to the reset seed (xorshift would stick at 0). |
| Audio mixing | Each channel produces a signed 16-bit sample (8-bit samples are shifted left 8). Left = sample × left volume ÷ 256 (arithmetic shift), same for right. The channels (eight, now sixteen, plus the reverb: see [Audio upgrade](#audio-upgrade-adpcm-16-channels-reverb)) are summed in 32 bits and hard-clipped to −32768..32767. No interpolation: nearest sample. |
| Save data | Two memory card slots, 128 KB each in 512-byte blocks, accessed through a card controller at `0xFF0380` that isolates each cart's saves by cart ID. Saves carry a title and a 16×16 animated icon. See `MEMCARD.md`. |
| Cart file format | A cart is a raw ROM image (≤ 2 MB) mapped at `0x200000`; execution starts at its first word. Optional header: word 0 is any instruction (normally `jmp start`), bytes 4–7 are `"MEI1"`, bytes 8–39 are the title, NUL-padded, bytes 40–55 the cart ID for memory cards (NUL-padded; all zero: none). Code starts at byte 56. Extension `.mei`. |
| Language syntax | See `LANGUAGE.md`. |
| Compressed audio | A PS1-SPU-style 4-bit ADPCM (3.5 : 1 against 16-bit), selected per channel; see [Audio upgrade](#audio-upgrade-adpcm-16-channels-reverb). |
| Standard library location | Compiled into each cart (counts against its 2 MB). |
| Culling/clipping helpers | Four geometry instructions in the reserved opcodes 19–1B and 1F: a back-face test, an ordering-table depth, a colour blend and a three-vertex transform (see [Geometry instructions](#geometry-instructions)). The CPU has 63 instructions. Clipping stays in software. |
| Fill rate | Unlimited, as drafted. The plane chip ([PLANES.md](PLANES.md)) takes screen-sized skies, floors and water off the GPU, and its measurements are the basis for a GPU budget (see its "Timing and costs"). |
| Controller count | Two. Each also has a **Select** button (bit 11 of `PAD1`/`PAD2`), added to the spec's eleven. |

## Details filled in

**Frames and ticks.** The core runs in 60 Hz ticks. Each tick gives the CPU a fresh
500,000-cycle budget. An instruction runs if any budget remains, so the counter can go
slightly negative; the deficit is not carried over. `vsync` ends the tick: the buffers
swap, the triangle count resets and input is latched. If the budget runs out first, the
front buffer is unchanged (the previous picture repeats) and the CPU resumes next tick.
`FRAME` counts ticks since reset. `CYCLES` reads the budget left before the reading `lw`
is charged.

**Audio per tick.** 22,050 / 60 = 367.5, so ticks alternate 367 and 368 stereo samples.

**Audio channels.** Writing `CTRL` with bit 0 set restarts playback at sample 0; writing it
with bit 0 clear stops the channel. Reading `CTRL` returns bit 0 = currently playing,
bits 1–2 as written. `POS` advances by `PITCH` (16.16) per output sample. When it reaches
`LEN`: if looping, it wraps to `LOOP + (pos − LEN)`; otherwise the channel stops.
Sample data must be in RAM or ROM; a read outside them stops the channel (audio never
faults the CPU). 16-bit samples are little-endian. The reserved offset `+1C` faults like
any unlisted offset.

**Input.** Radial dead zone of 0.2, rescaled so the edge of the dead zone reads 0 and full
deflection reads 1.0 (65,536); clamped to unit length. Stick y is +1 for up.

**Faults.** The error screen is rendered by the core. GPU list errors report the address
of the `sw` that wrote `GPU_DRAW`. A packet address outside RAM/ROM raises *Unmapped
address*; a non-word-aligned packet raises *Misaligned access*; more than 65,536
packets raises *Bad packet list* (an extra fault type). Instruction fetch is allowed from
RAM, ROM and VRAM; the PC must be word-aligned. `brk` and `vsync` ignore their low 26 bits;
`jr`/`callr` ignore fields a, c and the immediate. `vget`/`vset` with a lane above 3 are
illegal instructions.

**vproj.** All rounding is floor on the final value:
`x = 160 + floor(160·x / w)`, `y = 120 + floor(−120·y / w)`, then each is clamped to
−1024..1023. `z = (z << 16) / w` truncated like `fdiv`. When `w = 0` all three quotients
are 0 (x = 160, y = 120, z = 0). `w` is copied through.

**Fixed-point rounding.** `fmul`, `vmul`, `vscale`, `vdot`, `vcross`, `vxfm` use 64-bit
products and an arithmetic shift right by 16 (rounds toward −∞). `fdiv` truncates toward
zero.

**Rasterization.** Pixel centres are at integer coordinates. Integer edge functions with
a top-left fill rule; both windings are drawn; zero-area triangles are skipped. Colours
and texture coordinates are interpolated affinely (barycentric in screen space) with
integer arithmetic. A 15-bit palette colour is expanded to 8 bits per channel as
`(c << 3) | (c >> 2)` before tinting. Tint: `min(255, texel × colour / 128)`. Then dither
(if `GPU_CTRL` bit 0) or not, then reduce to 5 bits, then blend if semi-transparent.
Written pixels always have bit 15 clear, except while the plane compositor is on (`PLN_CTRL` bit 0), when bit 15 is the polygon priority bit, `0x8000` is a hole, and a blend over a hole (or, upper, over a lower pixel) blends with the composite of the layers behind its layer ([PLANES.md](PLANES.md)).

**Triangle limit.** Counted per triangle: a quad whose first half is the 2,000th
triangle draws that half and drops the second.

**GPU_CLEAR** writes the low 15 bits to every pixel of the back buffer (all 16 while the plane compositor is on, so `0x8000` clears to holes: [PLANES.md](PLANES.md)).

**CPU and bus edge cases.**
- Fault checks run alignment first, then region. For I/O, width is checked before offset (so `lb` on any I/O address is *Bad I/O width*).
- Jumps, calls and taken branches check their target before transferring: an unmapped, misaligned or I/O target faults *at the jump* with `addr` = target, and `call`/`callr` do not write r15. Running sequentially off the end of a region faults at fetch (pc = addr = the bad pc). `callr r15` reads its target before writing r15.
- `addr` is 0 for Break, Illegal instruction and No cart. A faulting instruction is charged no cycles.
- `vmov`, `vxfm`, `vproj` ignore the c field (bits 13–0 must still be zero).
- `vld`/`vst` are four 32-bit accesses; `vld` leaves the register unchanged if any word faults, `vst` may have written earlier words.
- `GPU_CTRL` stores and reads back all 32 bits.
- Stick input: each axis is rounded to 16.16 and clamped to ±1.0 (NaN → 0); the dead zone (13107), length (integer square root) and rescale are integer math. A full diagonal reads 46341 per axis.
- A zero-length cart is rejected. After a fault all audio channels stop; the faulting tick counts in `FRAME`, later ticks don't advance it.
- `mei_reset` clears the latched input registers but keeps the platform's pending input.

**GPU edge cases.**
- Every submitted triangle counts against the 2,000 budget, including zero-area and fully off-screen ones; a second `GPU_DRAW` in a frame keeps counting.
- Packet checks: region first (*Unmapped address*), then alignment (*Misaligned access*). Every packet word is checked, so a polygon running off the end of ROM faults at that word. The 65,536 cap counts every packet, including empty and unknown ones. Packets drawn before a fault stay drawn.
- `GPU_DRAW` is not masked: exactly `0xFFFFFF` is an empty list; anything else outside RAM/ROM faults.
- 8-bit textures may start on an odd slot; texel addresses wrap within the 512 KB texture area (slot 15 + 1 = slot 0). For 8-bit textures only palette bits 24–27 are used.
- Interpolated colour and u,v are `floor(weighted sum / area)`; no wrapping.
- Semi-transparent textured polygons blend every non-zero texel (no per-texel transparency bit). Untextured black draws normally.
- `gpu_vsync` leaves `GPU_CTRL` alone.

**Audio edge cases.**
- Channel registers store and read back the full 32-bit value; `VOL` uses bits 0–15. Unaligned offsets are unmapped.
- A sample is read, then `POS` advances, so the first output after a start is sample 0. If one step overshoots `LEN` by more than the loop length, `POS` wraps modulo `LEN − LOOP`. With the loop bit set but `LOOP ≥ LEN`, or with `LEN = 0`, the channel stops. 16-bit samples need not be aligned; a sample straddling the end of RAM/ROM stops the channel.

**Extensions beyond the spec.** Four system registers support the system ROM
(`docs/SYSTEM.md`): `SYS_LAUNCH` (`0xFF0310`), `SYS_CONFIG` (`0xFF0314`, a persisted settings
word) and a real-time clock, `SYS_TIME` (`0xFF0318`) and `SYS_DATE` (`0xFF031C`). The clock is
latched at `vsync` like input, so determinism holds as long as a replay records it.

**Broadcast decoder.** A one-way data broadcast (time and weather pages from a looping
carousel, Teletext-style) is received by a decoder chip at `0xFF0600`–`0xFF0647`, which extends
the I/O region to `0xFF06FF`. It is driven by the frame loop (16 bytes per tick) and is idle
until a cart turns it on. See `BROADCAST.md`.

**I/O map.** `0xFF0000`–`0xFF03FF` as in the spec (with the extensions above and the memory
card at `0xFF0380`), `0xFF0400`–`0xFF05FF` the audio upgrade (below), `0xFF0600`–`0xFF06FF`
the broadcast decoder (`docs/BROADCAST.md`) and `0xFF0700`–`0xFF07FF` the plane chip
([PLANES.md](PLANES.md)). `0xFF0800` and up are unmapped.

## Geometry instructions

Like the PlayStation's GTE (RTPT, NCLIP, AVSZ, DPCS), the CPU has four instructions for the
per-vertex and per-face work of drawing meshes. They use opcodes the spec reserved; `3F`
still faults, so the all-ones word stops the cart, and `00` is still `brk`. The CPU now has
63 instructions.

| Op | Mnemonic | Format | Operation | Cycles |
|---|---|---|---|---|
| 19 | `nclip a, b, c` | R | a = (x1 − x0)(y2 − y0) − (x2 − x0)(y1 − y0), for the packed screen positions P0 = a, P1 = b, P2 = c | 6 |
| 1A | `otz a, b, c` | R | a = clamp(a + ⌊b × c ÷ 2³²⌋, 0, 1023) | 5 |
| 1B | `clerp a, b, c` | R | each byte of a moves toward the same byte of b by the fraction c | 4 |
| 1F | `vxp3 va, vb` | R | va, va+1, va+2 = `vxfm` then `vproj` of vb, vb+1, vb+2, with lane z = packed screen position | 23 |

A **packed screen position** is the vertex word of a GPU packet: x in bits 0–15 and y in bits
16–31, both signed, i.e. `(x & 0xFFFF) | (y << 16)`.

**nclip** reads its destination: a holds P0 on entry and the result on exit. The value is twice
the signed area of the screen triangle, computed exactly in 64 bits and saturated to
−2³¹..2³¹−1, so its sign is always right (saturation needs coordinates beyond ±16,383;
`vproj` never makes them). Negative means counter-clockwise on screen (y grows down), which is
how the standard library's front faces wind; zero means a degenerate triangle. Within
`vproj`'s range it equals the scalar sequence it replaces bit for bit.

**otz** turns a depth into an ordering-table index. a holds a bias on entry (the standard
library's `depth_bias`) and the index on exit; b is a depth and c a scale, both 16.16, so
⌊b × c ÷ 2³²⌋ is the integer part of their product (64-bit product, rounded down). The sum is
taken in 64 bits and clamped to 0..1023, the standard library's 1,024 buckets. For a triangle,
b = w0 + w1 + w2 − 3 × near and c = 1024 ÷ (far − near) ÷ 3 give the bucket of its average
depth (÷ 4 for a quad). It equals `fmul`, `sari 16`, `add`, clamp whenever that `fmul` does
not overflow.

**clerp** blends packed colours (or any four unsigned bytes). c is a signed 16.16 fraction t,
clamped to 0..1.0. Each byte of a (bits 0–7, 8–15, 16–23, 24–31) becomes
a + ⌊(b − a) × t ÷ 65536⌋, rounded down, with b's byte in the same place: t = 0 gives a, t ≥ 1.0
gives b, and the bytes never carry into each other. With t = 0.5 it is the floor average of
each byte. The standard library's fog blend (amount 0..256) is `clerp` with t = amount × 256,
bit for bit, for colours whose top byte is zero.

**vxp3** transforms and projects three vertices at once. va and vb each name three
consecutive registers, so both must be `v0`–`v5`; a field of 6–15 is an illegal instruction.
c is ignored (as for `vmov`, `vxfm` and `vproj`) and bits 13–0 must be zero. For k = 0, 1, 2 it
computes the `vxfm` of vb+k with the matrix in `v4`–`v7`, then `vproj` of that: lanes x, y and
w are bit for bit what `vxfm` followed by `vproj` give (floor rounding, the −1024..1023 clamp,
x = 160 and y = 120 when w = 0). Lane z holds the packed screen position instead of z ÷ w,
which `vproj` still provides. All inputs, matrix rows included, are read before any register
is written, so the source and destination may overlap each other and `v4`–`v7`: `vxp3 v0, v0`
works in place, and `vxp3 v5, v0` overwrites two matrix rows only after using them.

All four have a fixed cost and fault only as illegal instructions (bad fields or non-zero
bits 13–0). With r0 as the scalar destination the result is discarded, and P0 or the bias
reads as 0.

**Why these four.** They were chosen by profiling `mesh()` in Lantern Lake and Sun & Moon
Orbs. A microbenchmark of the standard library's sequences, before and after (cycles):

| Step | Today | With the instruction |
|---|---|---|
| vertex transform, projection and packing (`vxp3`) | 39 per vertex | 17 |
| the same with fog | 52 per vertex | 31 |
| back-face test (`nclip`) | 32 per face | 14 |
| ordering-table bucket (`otz`) | 19 per visible face | 13 |
| fog blend of a vertex colour (`clerp`) | 33 per face vertex (mixed amounts) | 11 |

A lane-wise vector lerp was considered instead of `clerp`: `vsub`, `vscale`, `vadd` already
do it in 6 cycles, so it would save at most 2, while fog works on packed colours, where
`clerp` saves about 22.

## Audio upgrade: ADPCM, 16 channels, reverb

Mei gains the PS1 sound chip's tools: a 4-bit ADPCM sample format, sixteen channels and a
global hardware reverb. The output stays 22,050 Hz stereo and everything is integer and
deterministic. The upgrade is additive: a cart that never sets the new `CTRL` bits or touches
the new registers sounds bit-identical (checked by comparing `--wav` output of the old and new
builds for the system ROM with both boot themes and every cart).

### Register map

| Address | Name | Access | Purpose |
|---|---|---|---|
| `0xFF0100 + n×0x20` | channels 0–7 | | unchanged (spec p. 12) |
| `0xFF0400 + (n−8)×0x20` | channels 8–15 | | the same seven registers (`ADDR LEN LOOP PITCH VOL CTRL POS`); `+1C` reserved |
| `0xFF0500` | `REV_CTRL` | Read/write | bits 0–3: reverb preset, 0 off, 1 room, 2 studio, 3 hall, 4 space, 5 echo; 6–15 act as off. All 32 bits read back |
| `0xFF0504` | `REV_VOL` | Read/write | bits 0–7: wet left volume, bits 8–15: wet right (÷ 256, like `VOL`) |
| `0xFF0508` | `REV_DECAY` | Read/write | bits 0–7: 0 = the preset's own decay; n = 1–255 scales every feedback gain by n ÷ 256 |
| `0xFF050C` | `AUD_ACTIVE` | Read | bit n = channel n is playing |

The I/O region is now `0xFF0000`–`0xFF05FF`. Every other offset in it faults as before:
`+1C` of each channel and `0xFF0510`–`0xFF05FF` are *Unmapped address*, writing `AUD_ACTIVE`
or a `POS` is *Read-only*, and byte or halfword access anywhere in the region is *Bad I/O
width*. `0xFF0600` and up were unmapped until the [broadcast decoder](BROADCAST.md#registers-0xff0600) took `0xFF0600`–`0xFF06FF`. (Before the upgrade `0xFF0400`–`0xFF05FF` faulted
*Unmapped address*; no working cart could depend on that.)

**Channel `CTRL`**, for all sixteen channels:

| Bit | Meaning |
|---|---|
| 0 | write 1: start from sample 0 (write 0: stop); read: playing |
| 1 | loop |
| 2 | 16-bit PCM (otherwise 8-bit) |
| 3 | ADPCM (takes precedence over bit 2) |
| 4 | send to the reverb |
| 7 | update (write only): the write changes bits 1 and 4 only, and neither starts nor stops the channel; the other bits of the value are ignored |

Reading `CTRL` gives bit 0 = playing and bits 1–4 as last written. A start writes all bits
(so a play without bit 4 is dry); bit 7 lets a cart change the loop flag or the reverb send of
a playing channel, for example clearing the loop so a sound plays out to its end.

### ADPCM format

A PS1-SPU-style 4-bit ADPCM. Data is a sequence of **16-byte blocks of 28 samples**:

| Byte | Contents |
|---|---|
| 0 | header: bits 0–3 shift (0–12), bits 4–7 filter (0–4) |
| 1 | reserved: ignored by the console, written as 0 |
| 2–15 | 28 signed 4-bit nibbles: sample j of the block is in byte 2 + j ÷ 2, the low nibble for even j |

Decoding one sample with history `h1` (previous sample) and `h2` (the one before):

```
t = nibble as a signed 4-bit value (-8..7)
s = t × 2^(12 - shift) + floor((h1 × K0[filter] + h2 × K1[filter] + 32) / 64)
s = clamp(s, -32768, 32767);  h2 = h1;  h1 = s
```

| Filter | K0 | K1 | as a predictor |
|---|---|---|---|
| 0 | 0 | 0 | none |
| 1 | 60 | 0 | 0.9375 h1 |
| 2 | 115 | −52 | 1.796875 h1 − 0.8125 h2 |
| 3 | 98 | −55 | 1.53125 h1 − 0.859375 h2 |
| 4 | 122 | −60 | 1.90625 h1 − 0.9375 h2 |

These are the PS1 SPU's coefficients. Reserved values behave as on the PS1 where it is
known: shifts 13–15 act as 9; filters 5–15 predict nothing (as filter 0). The predictor
product is exact (64-bit) and `floor` is an arithmetic shift.

Size: 4.57 bits per sample, 12,600 bytes per second at 22,050 Hz: **3.5 : 1 against 16-bit,
1.75 : 1 against 8-bit**. `tools/mei_adpcm.py` encodes (best filter and shift per block,
closed loop, optional noise shaping), decodes and reports quality. Measured SNR on 4-second
test signals, against 8-bit PCM at the same byte budget (12,600 Hz, played by nearest sample
as the console does) and at full rate:

| Signal | ADPCM | 8-bit, same bytes (12.6 kHz) | 8-bit, 22 kHz (1.75 × the bytes) |
|---|---|---|---|
| music-like | 39.0 dB | 19.3 dB | 36.9 dB |
| speech-like | 32.4 dB | 10.7 dB | 36.3 dB |
| white noise | 19.7 dB | −0.1 dB | 39.1 dB |
| sine sweep 50 Hz–10 kHz | 32.2 dB | 3.5 dB | 48.9 dB |

ADPCM's error follows the signal (segmental SNR on music is 51 dB against 35 dB for full-rate
8-bit); it is weakest on noise-like sounds, where nothing can be predicted.

### ADPCM channels

- `ADDR` is the byte address of block 0, any alignment. Sample n is nibble n mod 28 of the
  block at `ADDR + 16 × (n div 28)`. `LEN` and `LOOP` count samples, as for PCM; `LEN` need
  not be a multiple of 28 (the rest of the last block never plays).
- Besides `POS`, an ADPCM channel keeps `DEC`, the next sample to decode, and the history
  `h1`, `h2`. A start (a `CTRL` write with bit 0 set) sets `POS`, `DEC`, `h1`, `h2` to 0.
- Each output sample, as for PCM, reads sample `idx = POS` (integer part) and then advances
  `POS`. If `idx ≥ LEN` the channel stops. Otherwise every sample from `DEC` to `idx` is decoded
  in order, each one updating the history, and the output is `h1`, the sample at `idx`.
  So with a pitch below 1.0 a sample repeats without decoding, and **with a pitch above 1.0 the
  skipped samples are still decoded** for the history.
- **Pitch**: an ADPCM channel advances by `min(PITCH, 16.0)` per output sample (`0x100000`),
  which bounds the decoding work at 16 samples per output. `PITCH` reads back as written.
  PCM channels are not capped.
- **Loops**: `POS` wraps exactly as for PCM (to `LOOP + (POS − LEN) mod (LEN − LOOP)`), then
  `DEC` is set to `LOOP` and **the history carries on**, as on the PS1: the first sample after
  the wrap is predicted from the last samples before it. Only `LOOP` to the new `POS` is
  decoded, even when one step skips several whole loops. `LOOP` need not be a multiple of 28;
  decoding resumes at nibble `LOOP mod 28` of its block, with that block's header. A loop is
  clean when its first block decodes well both from the intro and from the loop's end. The
  encoder (`--loop`) takes care of that for block-aligned loop points: it encodes the first
  loop block to minimise the error from both histories and finds the loop end's history by
  iterating, so every pass after the first decodes identically (for a loop point inside a
  block it uses filter 0, which needs no history). With looping off, or `LOOP ≥ LEN`, the
  channel stops at the end.
- **Out of range**: when a header or nibble byte that a decode needs lies outside RAM/ROM the
  channel stops silently from that sample on, as for PCM. A block may straddle the end of RAM
  into ROM.
- A `CTRL` update write (bit 7) does not touch `POS`, `DEC` or the history.

### Sixteen channels

Channels 8–15 behave exactly like 0–7. The mixer sums all sixteen (the order does not matter:
integer sums). After a fault all sixteen stop and the reverb is silent. The system ROM
convention (theme 0–5, shell 6–7) is unchanged; 8–15 are free.

### Reverb

A global stereo reverb, its state inside the core (about 96 KB of delay memory, not in cart
RAM). It is fed by the channels with `CTRL` bit 4 set.

**Input.** Send left/right = the sum of the sending channels' contributions after their
volume (the same `floor(s × vol ÷ 256)` values the dry mix uses). The reverb takes the mono
mean `floor((L + R) ÷ 2)`, clamped to ±2²⁰, scales it by 64 (6 bits of internal precision so
quiet tails keep their shape), and removes DC with `y = x − x₁ + trunc(y₁ × 32604 ÷ 32768)`
(about 17 Hz).

**Presets 1–4** are an 8-line feedback delay network:

1. a predelay line;
2. four Schroeder allpass diffusers in series, each `v = x + trunc(g·d)`, `out = d − trunc(g·v)`,
   `v` written into a delay of length M (d = the value M samples ago), g = 0.7;
3. eight delay lines. Each sample, line i outputs its oldest value `o`, then
   `lp = trunc((o·a + lp·(32768 − a)) ÷ 32768)` (damping) and `u = trunc(lp · gain ÷ 32768)`;
   the eight `u` go through an 8 × 8 Hadamard matrix (butterflies; its 1/√8 is folded into
   `gain`), and line i is written with `u'ᵢ ± x` (+ for lines 0–3, − for 4–7), clamped to ±2³⁰;
4. output L = o₀ − o₁ + o₂ − o₃ + o₄ − o₅ + o₆ − o₇ and R = o₀ + o₁ − o₂ − o₃ + o₄ + o₅ − o₆ − o₇
   (two orthogonal Hadamard rows, so the two sides are decorrelated), times the preset's output
   gain ÷ 2^(15+6) (floor), clamped to ±2²⁰.

`a` and `gain` follow Jot's absorbent-filter design for a decay time (RT60) and a
high-frequency ratio, with the Hadamard's 1/√8 folded into `gain`.
`tools/gen_reverb_tables.py` computes them (as integers, so the console never uses floating
point) and writes the table in `audio.c`.

**Preset 5, echo**, is a ping-pong delay: two 5,512-sample lines (250 ms), the left one fed
`x + trunc(lp_R × 0.6)` and the right one `trunc(lp_L × 0.6)`, with the same damping filter
(a = 0.6); the outputs are the two lines, times the output gain. Each repeat is 4.4 dB quieter
and darker than the last, alternating sides.

| Preset | Predelay | Lines (samples) | Decay, 500 Hz–1 kHz | at 8 kHz | Echo density reached |
|---|---|---|---|---|---|
| 1 room | 4 ms | 419–887 | 0.63 s | 0.29 s | 65 ms |
| 2 studio | 8 ms | 557–1,201 | 1.2 s | 0.71 s | 90 ms |
| 3 hall | 20 ms | 1,153–2,903 | 2.4 s | 0.81 s | 190 ms |
| 4 space | 45 ms | 1,559–3,571 | 6.3 s | 3.0 s | 340 ms |
| 5 echo | — | 2 × 5,512 | repeats every 250 ms | | |

Measured on impulse responses: tail spectra are as smooth as a noise burst with the same
decay (no ringing modes between 100 Hz and 4 kHz), the left/right correlation of the tail is
below 0.1, and each preset's output gain is set so white noise sent at full volume returns at
−3 dB with `REV_VOL` at 255.

**State rules.** Writing `REV_CTRL` with a different preset (bits 0–3) clears all reverb
memory; writing the same preset does not. The reverb runs whenever a preset is selected,
even with nothing sent or `REV_VOL` at 0, so tails keep decaying. Every feedback product
truncates toward zero, so with no input the whole state decays to exactly zero. Reset clears
it; a fault silences it.

**Cost.** Measured on an Apple M1 Pro (native `-O2`) and in WebAssembly under Node
(`-O3`), per 60 Hz tick:

| Load | Native | WebAssembly |
|---|---|---|
| 8 PCM channels (the old maximum) | 0.010 ms | 0.022 ms |
| 16 ADPCM channels, pitch about 1.0 | 0.038 ms | 0.091 ms |
| the same with a reverb preset 1–4 | 0.054 ms | 0.107 ms |
| reverb alone (preset 1–4 / echo) | 0.017 / 0.003 ms | 0.022 / 0.005 ms |
| worst case: 16 ADPCM channels at pitch 16.0 + hall | 0.25 ms | 0.58 ms |

The two builds produce identical output (same hashes).

### Mixing and headroom

For each output sample:

```
dry_L  = Σ floor(s_k × volL_k / 256)          over the playing channels k = 0..15
send_L = the same sum over channels with CTRL bit 4
wet_L  = reverb(send_L, send_R)               (clamped to ±2^20)
out_L  = clamp(dry_L + floor(wet_L × REV_VOL_L / 256), -32768, 32767)
```

and likewise for the right. All sums are 32-bit (at most 16 × 32,767 + 2²⁰ in magnitude, so
nothing wraps), and the final step is a hard clip, as before. Sending a channel to the reverb
does not change its dry contribution; there is no separate send level (use the channel
volume, `REV_VOL` and the dry/wet balance).

There is no automatic headroom: one channel at volume 255 with a full-scale sample already
reaches full scale, so two such channels can clip. To be safe, keep the sum of
`peak × volume ÷ 256` over the channels that can sound together within 32,767. The reverb adds
level too: at `REV_VOL` 255 its output is about 3 dB below the RMS of what is sent (for noise),
and its peaks are well below the dry peaks because the energy is spread in time, so a wet
volume of 64–160 with about 3–6 dB of headroom in the dry mix is a good start.

## Sort keys and the cull rectangle

The ordering table sorts each face by its own average depth. That is right for a single convex
mesh, but in a scene built from many small pieces on a grid (a building game seen from above)
it puts a tall cupboard's top in front of the chair beside it, and a long wall run in front of
the furniture standing at one end. A depth buffer would fix this, but the console has none, by
design. Instead a cart can say what a face should sort as:

- `depth_key(w, n)` sorts the faces of following `mesh*()` calls `n` times closer to depth `w`
  (n at least 1): their own depths still order them among themselves (so an object still draws
  correctly), but the whole object sorts as one unit by where it stands. `depth_key_off()`
  goes back to normal sorting (as does the start of each frame).
- A face with flag bit 5 (`FACE_KEYED`) takes its bucket from its fourth colour word
  (`col[3]`, unused by a flat face) instead of from its depth (still plus `depth_bias`). This lets a cart that bakes its
  own faces give each piece of a wall or rail the bucket of its base.

Both cost nothing for faces that do not use them beyond the flag test (2 cycles per visible
face). They are kept to the bucket computation: transforming, clipping and culling are
unchanged.

`cull_rect(x0, y0, x1, y1)` sets the rectangle that faces needing clipping are dropped against
(the screen by default; it stays until changed). A cart that records packets once and shifts
them on screen for several frames while the view pans widens it while recording, so the parts
that pan into view are there. Faces that need no clipping were never dropped for lying off the
screen, so nothing else changes.
