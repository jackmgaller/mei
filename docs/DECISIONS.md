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
| Cart file format | A cart is a raw ROM image (≤ 64 MB) mapped at `0x08000000` (see [Cart ROM](#cart-rom-up-to-64-mb-in-a-128-mb-window)); execution starts at its first word. Optional header: word 0 is any instruction (normally `jmp start`), bytes 4–7 are `"MEI1"`, bytes 8–39 are the title, NUL-padded, bytes 40–55 the cart ID for memory cards (NUL-padded; all zero: none). Code starts at byte 56. Extension `.mei`. |
| Language syntax | See `LANGUAGE.md`. |
| Compressed audio | A PS1-SPU-style 4-bit ADPCM (3.5 : 1 against 16-bit), selected per channel; see [Audio upgrade](#audio-upgrade-adpcm-16-channels-reverb). |
| Standard library location | Compiled into each cart (counts against its ROM size). |
| Culling/clipping helpers | Four geometry instructions in the reserved opcodes 19–1B and 1F: a back-face test, an ordering-table depth, a colour blend and a three-vertex transform (see [Geometry instructions](#geometry-instructions)). The CPU has 63 instructions. Clipping stays in software. |
| Fill rate | Budgeted: the GPU, named the **Prism Engine** (the 3D polygon processor), has 2,000,000 cycles a tick (a 120 MHz GPU since [2026-10-03](#a-depth-buffer-perspective-texturing-and-a-2000000-cycle-gpu); 1,000,000 at 60 MHz before), charged by a cost table (40 a triangle, 1 a pixel, ×2 textured, ×2 semi-transparent, 38,400 a clear; the depth buffer and perspective add terms of their own, [RENDERING.md](RENDERING.md#cost)). A frame over budget is shown late, never cut short; the triangle limit is raised to 4,000 as a backstop. See [GPU budget](#gpu-budget). The plane chip, the **Horizon Engine** (the scrolling plane processor, [PLANES.md](PLANES.md)), costs the GPU nothing. |
| Controller count | Two. Each also has a **Select** button (bit 11 of `PAD1`/`PAD2`), added to the spec's eleven. |

## Details filled in

**Frames and ticks.** The core runs in 60 Hz ticks. Each tick gives the CPU a fresh
1,000,000-cycle budget (500,000 before [the CPU went to 60 MHz](#the-cpu-at-60-mhz)). An
instruction runs if any budget remains, so the counter can go slightly negative; the deficit is not carried over. `vsync` ends the tick: the buffers
swap, the triangle count resets and input is latched. If the budget runs out first, the
front buffer is unchanged (the previous picture repeats) and the CPU resumes next tick.
A frame whose GPU work is over the GPU's budget is also shown late: the CPU waits at its
`vsync` until the GPU has finished ([GPU budget](#gpu-budget)).
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
integer arithmetic (textured packets with depth, `0x30`–`0x3F`, are perspective-correct instead:
[RENDERING.md](RENDERING.md)). A 15-bit palette colour is expanded to 8 bits per channel as
`(c << 3) | (c >> 2)` before tinting. Tint: `min(255, texel × colour / 128)`. Then dither
(if `GPU_CTRL` bit 0) or not, then reduce to 5 bits, then blend if semi-transparent.
Written pixels always have bit 15 clear, except while the plane compositor is on (`PLN_CTRL` bit 0), when bit 15 is the polygon priority bit, `0x8000` is a hole, and a blend over a hole (or, upper, over a lower pixel) blends with the composite of the layers behind its layer ([PLANES.md](PLANES.md)).

**Triangle limit.** 4,000 triangles a frame (the spec's 2,000, raised as a backstop when the
GPU got a cycle budget: see [GPU budget](#gpu-budget)). Counted per triangle: a quad whose
first half is the 4,000th triangle draws that half and drops the second.

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
- Every submitted triangle counts against the 4,000 limit (and costs its 40 setup cycles), including zero-area and fully off-screen ones; a second `GPU_DRAW` in a frame keeps counting.
- Packet checks: region first (*Unmapped address*), then alignment (*Misaligned access*). Every packet word is checked, so a polygon running off the end of RAM or of the ROM window faults at that word. The 65,536 cap counts every packet, including empty and unknown ones. Packets drawn before a fault stay drawn.
- `GPU_DRAW` is not masked: exactly `0xFFFFFF` is an empty list; anything else outside RAM/ROM faults.
- 8-bit textures may start on an odd slot; texel addresses wrap within the 512 KB texture area (slot 15 + 1 = slot 0). For 8-bit textures only palette bits 24–27 are used.
- Interpolated colour and u,v are `floor(weighted sum / area)`; they never leave 0–255 (no wrapping). A textured polygon may then map u,v through its texture window before the texel is read ([Texture windows](#texture-windows)).
- Semi-transparent textured polygons blend every non-zero texel (no per-texel transparency bit). Untextured black draws normally.
- `gpu_vsync` leaves `GPU_CTRL` alone.

**Audio edge cases.**
- Channel registers store and read back the full 32-bit value; `VOL` uses bits 0–15. Unaligned offsets are unmapped.
- A sample is read, then `POS` advances, so the first output after a start is sample 0. If one step overshoots `LEN` by more than the loop length, `POS` wraps modulo `LEN − LOOP`. With the loop bit set but `LOOP ≥ LEN`, or with `LEN = 0`, the channel stops. 16-bit samples need not be aligned; a sample straddling the end of RAM or of the ROM window stops the channel.

**Extensions beyond the spec.** Four system registers support the system ROM
(`docs/SYSTEM.md`): `SYS_LAUNCH` (`0xFF0310`), `SYS_CONFIG` (`0xFF0314`, a persisted settings
word) and a real-time clock, `SYS_TIME` (`0xFF0318`) and `SYS_DATE` (`0xFF031C`). The clock is
latched at `vsync` like input, so determinism holds as long as a replay records it.
Three read-only GPU registers, `GPU_LOAD`, `GPU_TICKS` and `GPU_LAG` (`0xFF0014`–`0xFF001C`),
report the GPU budget ([GPU budget](#gpu-budget)), and two more, `GPU_DEPTH` (`0xFF0020`) and
`GPU_ZCLEAR` (`0xFF0024`), control the depth buffer ([RENDERING.md](RENDERING.md)).

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

## GPU budget

The GPU is the **Prism Engine** (Prism for short), Mei's 3D polygon processor. The spec leaves
its fill rate open and caps it at 2,000 triangles a frame. Mei gives Prism a cycle budget like
the CPU's instead: it was a 60 MHz chip (beside a 30 MHz CPU when this was decided; the CPU has
been 60 MHz too since [2026-10-03](#the-cpu-at-60-mhz)), so it had 1,000,000 GPU cycles per tick.
Since [the depth buffer](#a-depth-buffer-perspective-texturing-and-a-2000000-cycle-gpu) (also
2026-10-03) it is a 120 MHz chip with **2,000,000 GPU cycles per tick**
(`MEI_GPU_CYCLES_PER_FRAME` in `src/core/mei.h`, `GPU_BUDGET` in `stdlib/runtime.akr`). A frame that needs more is shown late, as on the PlayStation, where a heavy scene
slows the game down rather than losing polygons. The triangle limit stays as a backstop (the
packet list needs a bound anyway), raised to **4,000**. The plane chip, the **Horizon Engine**
(Horizon, the scrolling plane processor; [PLANES.md](PLANES.md)), is a separate chip and costs
the GPU nothing; it is what lets the heavy carts fit (its "Timing and costs" and open question 1
have the measurements behind these numbers).

### Cost table

This is the official table. The constants are `GPU_CYCLES_*` in `src/core/machine.h`, applied
in one place (`gpu_pixel_cycles` and the two charges in `src/core/gpu.c`).

| Work | GPU cycles |
|---|---|
| a triangle's setup: every triangle counted against the limit, including zero-area, off-screen and empty ones (a quad is two) | 40 |
| a pixel filled, flat or Gouraud | 1 |
| a pixel filled, textured | 2 |
| a pixel filled, semi-transparent | 2 |
| a pixel filled, textured and semi-transparent | 4 |
| `GPU_CLEAR` (76,800 pixels at half a cycle) | 38,400 |
| packets with depth: a pixel failing the depth test (1), the vertex reciprocals (24 a triangle), a perspective divide (2), `GPU_ZCLEAR` (38,400) | [RENDERING.md](RENDERING.md#cost) |
| triangles over the limit, packets that are not polygons, walking the list, `GPU_CTRL` | 0 |
| the plane chip: planes, backdrop, colour math, colour offset, auto-erase | 0 |

A pixel counts when it is inside the triangle, whether or not it is written: a textured
pixel whose texel is 0 costs the same as any other. Gouraud shading and dither cost nothing
extra. The cost is integer and exact; a frame's total is the sum over everything drawn
between two presents.

### Lag

The GPU draws in parallel with the CPU, so a frame takes as long as the slower of the two, in
whole ticks:

- The GPU adds up the cycles of the frame being drawn: everything drawn since the last
  present (or reset).
- When the CPU executes `vsync`, the frame is presented at the first tick end at which its
  GPU cycles are at most **2,000,000 × n**, where n is the number of ticks since the last
  present, counting the current one. On time and under budget (n = 1) that is the tick of the
  `vsync`, as before.
- Until then the CPU waits at `vsync` and runs nothing. The buffers do not swap, the plane chip
  does not compose, and the pads, sticks, clock and card controller do not latch: it is
  exactly as if the frame had taken longer. Audio, the broadcast decoder and `FRAME` go on
  every tick. `mei_run_frame` returns 0 for those ticks (the previous picture repeats).
- At the present everything a `vsync` does happens, and the CPU resumes in the next tick.

So a frame at 1–2× the budget is shown one tick late, and at 2–3× two ticks late; exactly
the budget is on time. It composes with a CPU overrun: a frame whose CPU work spanned two
ticks has 4,000,000 GPU cycles, and the ticks are not counted twice. In all, a frame takes
max(its CPU ticks, ⌈GPU cycles ÷ 2,000,000⌉) ticks. Everything is integer, so a replay with
the same input lags identically.

The model does not let the GPU run on into the next frame (on the PlayStation it draws the
last frame's list while the CPU builds the next), because here the GPU draws when the packets
are submitted. The lag a cart sees is the same as in a pipelined machine whose frame takes
max(CPU, GPU).

### Registers

| Address | Name | Access | Purpose |
|---|---|---|---|
| `0xFF0014` | `GPU_LOAD` | Read | GPU cycles of the last presented frame (saturates at `0xFFFFFFFF`) |
| `0xFF0018` | `GPU_TICKS` | Read | ticks the last presented frame took, from the present before it (or reset) to its own: 1 on time, more when the CPU or the GPU ran over |
| `0xFF001C` | `GPU_LAG` | Read | ticks since reset in which a finished frame waited for the GPU |

All three read 0 after reset until the first present, and writing any of them is
*Read-only*; `0xFF0020` and `0xFF0024` are `GPU_DEPTH` and `GPU_ZCLEAR`
([RENDERING.md](RENDERING.md#registers)), and `0xFF0028`–`0xFF00FF` stay unmapped. A cart sees them change only at `vsync`
(the CPU does not run while `GPU_LAG` counts). `GPU_TICKS − 1` is how late the last frame was
for any reason; the difference of two `GPU_LAG` readings is the part the GPU caused. `GPU_LAG`
is a running count rather than cleared on reading, so reads have no side effects and a cart
that looks only now and then loses nothing.

The standard library reads them with `gpu_used()`, `frame_ticks()` and `gpu_lag()`, and has
`GPU_BUDGET` (`LANGUAGE.md`). `cpu_used()` and `frames_dropped()` are unchanged, so they still
count from one `vsync` to the next: the frame after one that the GPU held back includes the
wait in them.

`mei-headless --gpu-stats` writes `gpu_cycles`, `ticks` and `gpu_lag` for every presented
frame, and `tools/mei_gpustats.py` summarises them. The halt screen and the desktop player show
no CPU load, so they show no GPU load either.

### Every cart fits

Measured with `mei-headless --gpu-stats` (the console's own count) over 1,500–1,800 ticks a
run, idle and with held and pressed buttons, plus the Lantern Lake and Check-In! test
scenarios: 38 runs and 63,440 frames, **none of them held back by the GPU**. Each run's frames
and audio are bit-identical to the build before the budget. (These are shares of the 1,000,000
of then; the budget is twice that since
[2026-10-03](#a-depth-buffer-perspective-texturing-and-a-2000000-cycle-gpu).)

| Cart | Highest GPU cycles in a frame | Of the budget |
|---|---|---|
| Lantern Lake: the map menu over the lake | 865,915 | 87 % |
| Lantern Lake: day, dusk, night, fights, festival ending (scenarios 1–30) | 537,524 (festival ending) | 54 % |
| System ROM: Eclipse boot | 748,421 | 75 % |
| System ROM: shell, then a launched cart | 690,225 | 69 % |
| System ROM: Duet boot | 528,096 | 53 % |
| Check-In! (scenarios 12, 209, 215, 224 and the cart) | 588,743 | 59 % |
| Sun & Moon Orbs | 573,270 | 57 % |
| Fair Skies | 336,993 | 34 % |
| Demo, Sound Lab, Pad Test, Features, Hello | 150,538 or less | 15 % or less |

The Lantern Lake map menu (blended and textured panels over the whole lake scene) is the
closest to the budget.

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
the furniture standing at one end. A depth buffer would fix this, but the console had none, by
design (it has an opt-in one since
[2026-10-03](#a-depth-buffer-perspective-texturing-and-a-2000000-cycle-gpu); what follows is for
the ordering table). Instead a cart can say what a face should sort as:

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

## Akari data and code ergonomics

The compiler supports the five additions approved in the data and code ergonomics round:

- Slices use an eight-byte pointer/length descriptor over caller-owned storage. `[]T` allows
  element writes; `[]const T` provides read-only access, including ROM arrays. Debug builds
  check indexing and subranges. `map(slice, f, out)` uses a caller-provided destination, checks
  its capacity even in release builds, and returns a slice; no heap or variable-size stack
  allocation is introduced.
- Dot calls use UFCS: `value.function(args)` passes `value` as the first argument of the free
  function. Pointer receivers remain explicit. Real fields take precedence; a type's module
  supplies public associated functions when no local or visible free function shadows them.
- Structs can contain byte-aligned `bits` groups, with one-bit boolean flags and explicitly
  sized unsigned fields. Reads and writes preserve adjacent bits; members have no individual
  address.
- `fixed16` stores signed 4.12 values in two bytes while using canonical 16.16 register values
  and the scalar calling convention. Arithmetic promotes to `fixed`; narrowing drops the
  low four fractional bits and wraps to signed sixteen-bit storage.
- Named file imports expose public symbols through their alias and use module-specific
  assembly labels. Plain imports retain their existing global behavior.

See `LANGUAGE.md` for syntax, conversions, lifetime restrictions and examples.

### Packed struct flags and integer fields

Inline `bits { flag, count: u8: 3 }` groups store bool flags and explicitly sized unsigned
integer fields in declaration order, low bit first, with byte alignment and no gaps between
members. Integer fields may span bytes; byte loads/stores avoid imposing alignment or touching
memory beyond the group. Writes truncate to the declared width and preserve neighboring bits,
including when a right-hand-side function changes other flags. Member addresses are rejected;
whole groups remain ordinary aggregates for copies and enclosing struct parameters/returns.
Context-typed `bits { flag: true }` literals use the existing struct default and zero rules.
Each inline declaration has its own identity, avoiding accidental copies between unrelated
flag layouts. Signed fields are omitted to keep extension and overflow rules explicit.

## Cart ROM: up to 64 MB in a 128 MB window

The spec gives the cart 2 MB at `0x200000`–`0x3FFFFF` and says every address fits in 24 bits.
Mei departs from that so carts can hold large streamed worlds: as on the N64, the ROM stays
memory-mapped and is read in place, while RAM stays 2 MB and VRAM 1 MB. The ROM moves to a
reserved **128 MB window at `0x08000000`–`0x0FFFFFFF`**, and a cart may be up to **64 MB**
(`0x08000000`–`0x0BFFFFFF`). RAM, VRAM and I/O keep their addresses; `0x200000`–`0x3FFFFF` is now
unmapped. The window and the limit are separate constants (`MEI_ROM_WINDOW` and `MEI_ROM_MAX` in
`src/core/mei.h`, with `MEI_ROM_BASE`), so the limit can rise to the whole window later without
moving anything.

| Address | Region | Size | Access |
|---|---|---|---|
| `0x000000`–`0x1FFFFF` | RAM | 2 MB | read/write |
| `0x400000`–`0x4FFFFF` | VRAM | 1 MB (2 MB, to `0x5FFFFF`, since 2026-10-05: [below](#vram-at-2-mb)) | read/write |
| `0xFF0000`–`0xFF07FF` | I/O | 2 KB | see the I/O map in [Details filled in](#details-filled-in) |
| `0x08000000`–`0x0FFFFFFF` | cart ROM window | 128 MB (carts up to 64 MB) | read only |

- **Reach.** `jmp`/`call` targets are 26 bits × 4, so a plain jump or call reaches the whole window
  (anything below `0x10000000`); `la` and `lui` + `ori` build any 32-bit address. The instruction
  encoding is unchanged.
- **Past the image.** A cart is still a raw image, and the core keeps only its bytes (a small cart
  costs a small cart's memory). The rest of the window reads as zeros, as the unused part of the
  spec's 2 MB region did: loads there return 0, an instruction fetch there finds the all-zeros
  word, `brk`, and stops the cart with *Break*. Writes anywhere in the window fault *Read-only
  write*. The GPU, the audio channels and the memory card controller read the same zeros.
  Outside the window is *Unmapped address* as before.
- **Reset.** `pc` starts at `0x08000000`; `r14` (the stack) still starts at `0x200000`, the top of
  RAM.
- **Packet links.** A packet's next address keeps its 24 bits (and `0xFFFFFF` still ends the
  list), so a link reaches RAM only. `GPU_DRAW` takes a full 32-bit address, so a list may start
  with a packet in ROM; the packets it links to are in RAM.
- **No longer adjacent.** RAM used to run straight into ROM and ROM into VRAM. Now an access,
  sample or packet running off the end of RAM reaches unmapped memory.
- **Tools.** The assembler and compiler stop with *ROM is full (64 MB)*; `mei_load_cart`, the
  platforms and the system ROM's catalogue reject or skip a larger file.
- **Data limits follow the region.** In Akari, ROM data (const arrays and structs, strings,
  embeds) is limited only by the cart ROM, so one table or asset may be up to 64 MB; global
  variables stay within RAM (2 MB less the stack). The compiler hands embeds and const data of
  64 KB or more to the assembler in memory (`.incbin` of a blob, `ASSEMBLY.md`) rather than as
  `.word` text, so a large asset costs compile time and memory in proportion to its size.
- **System ROM.** It is still loaded as a 2 MB image, so its catalogue moves with the ROM base to
  `0x081F0000` (see `SYSTEM.md`).

## Texture windows

The spec's texture coordinates are 8 bits per vertex, interpolated without wrapping, inside a
256×256 slot: a small pattern can repeat across a big surface only if it is repeated in VRAM.
For the open-world city (large surfaces, small repeating patterns, 1 MB of VRAM) the project
owner approved (2026-10-03) a small departure that the original PlayStation also had: a
**per-polygon texture window**, an optional power-of-two rectangle inside the slot that u and v
wrap within. It saves VRAM (many small repeating tiles in one slot instead of one slot per
pre-repeated tile); it does not let a face repeat a tile more often than its 8-bit coordinates
allow.

- **Encoding.** Bits 16–31 of the **second vertex's texture coordinate word**, which the spec
  says should be zero and which no cart, scenario or test sets (each draws the same frames
  with the window decoded): bits 16–18 the u size (0: no window; k: 4 << k texels, so 1–6 give
  8–256 and 7 is 256 too), 19–23 the u origin ÷ 8, 24–26 the v size and 27–31 the v origin ÷ 8.
  All zeros is no window. No packet grows, and there is no new register or global state: the
  window travels with the polygon.
- **Sampling.** After interpolation, u becomes `(origin_u + (u mod size_u)) & 255` (likewise
  v), then the texel is addressed as before: 4-bit and 8-bit textures, an 8-bit texture's second
  slot and the slot 15 → 0 wrap are unchanged, and index 0 stays transparent. An axis with size
  0 is untouched; an origin plus size past 256 wraps to 0. The window is decoded once per
  packet, so both triangles of a quad share it.
- **Cost.** None on the GPU (no new cost-table term). Packets without a window draw exactly as
  before.
- **Meshes.** No format or version change: the face's texture byte bits 5–7 pick a window 1–7
  from a table of halfwords (the packet's bits 16–31) at the byte offset in the mesh header's
  `+12`, formerly reserved (0 in every mesh). `mesh()` sends a mesh with a table through
  windowed copies of the face loops' textured packet writers (a second half of their jump
  tables), so a mesh without one costs the same cycles as before; clipped and subdivided
  pieces keep their face's window. See `LANGUAGE.md`, "Texture windows" and "Mesh format".
- **Limits.** u and v are still 8 bits per vertex, so a single face repeats a tile at most
  255 texels' worth (31 × 8, 15 × 16, 7 × 32, 3 × 64, 1 × 128 whole repeats): windows help tiles
  of 64 texels or less. A face whose coordinate ends exactly at 256 is one texel short, as
  before.

## The kits and the first open-world game

On 2026-10-03 the project owner decided how levels are to be built for Mei and what the first
open-world game is. Most of those decisions are about tools and a game, not about how the
machine departs from the spec, so they are recorded where they apply:

- the World Kit's (the two tools and their boundary, the world format, terrain, streaming, the
  runtime reader, verification) in [WORLDKIT.md](WORLDKIT.md), with the World Checker in
  [WORLDCHECKER.md](WORLDCHECKER.md) and the pack format in [WORLDPACK.md](WORLDPACK.md);
- the Asset Kit's (palettes for day and night, shading, examples, textures) in
  [ASSETKIT.md](ASSETKIT.md);
- the platformer's (setting, pace, moves, the movement garden, build order) in
  [PLATFORMER.md](PLATFORMER.md), as design intent.

Three tools check the work, each under its own name:

| Name | What it checks | Where |
|---|---|---|
| **Asset Checker** | One asset's faces draw in the right order from every side (`mei_assets.py verify`) | [ASSETKIT.md](ASSETKIT.md#automated-visibility-gate) |
| **World Checker** | A level from where a player can stand: budgets, drawing order, collision holes (`tools/worldkit/verify.py`, run by `mei_world.py build`) | [WORLDCHECKER.md](WORLDCHECKER.md) |
| **Reference Renderer** | Mei itself: an independent renderer its output is compared against (`make rendercheck`, `make rendercheck-motion`) | [tests/reference_renderer/README.md](../tests/reference_renderer/README.md) |

### The machine

- **Cart ROM** as in [the section above](#cart-rom-up-to-64-mb-in-a-128-mb-window): 64 MB now,
  128 MB reserved. Bank switching, a disc device and a depth buffer were considered and left out
  (the depth buffer was adopted later the same day:
  [below](#a-depth-buffer-perspective-texturing-and-a-2000000-cycle-gpu)).
- **VRAM stays 1 MB** and the ordering table stays a cart convention. Both are to be revisited
  only if a second region or a real district shows they cannot work. (The shrine town did:
  VRAM is 2 MB since 2026-10-05, [below](#vram-at-2-mb).)

## The CPU at 60 MHz

On 2026-10-03 the project owner doubled the CPU's clock: **30 MHz → 60 MHz, 500,000 →
1,000,000 cycles a tick** (`MEI_CYCLES_PER_FRAME` in `src/core/mei.h`, `CPU_BUDGET` in
`stdlib/runtime.akr`). Only the CPU changes: the Prism Engine keeps its 1,000,000 GPU cycles a
tick (doubled later that day: [below](#a-depth-buffer-perspective-texturing-and-a-2000000-cycle-gpu)), the cost table and the 4,000-triangle backstop, and RAM (2 MB) and VRAM (1 MB) stay as
they are. Every instruction costs the cycles it did. This supersedes the CPU figure in the
published v0.1 spec (`spec-v0.1.pdf`, `spec-v0.1.txt`), which is left as published.

**Why.** The flagship platformer's first detailed city block drew at up to about 556,000 CPU
cycles a frame, over the old budget, and the game is to run at 60 frames a second with more
detail than that: a "PS1.5", like the extra CPU of the N64 and Saturn generation. The GPU
budget was already twice the CPU's (a 60 MHz chip; [GPU budget](#gpu-budget)), so the two units
now have the same clock.

**Condition: the hosts still run it at full speed.** Measured before the change on an Apple
M1 Pro, with two builds of the same core differing only in the constant. The worst case is a
cart that uses its whole CPU budget every tick (a busy loop of loads, stores, multiplies and
branches that never reaches `vsync`), and the same with the GPU near its budget as well
(434,000 or 934,000 CPU cycles a frame, then six blended Gouraud full-screen rectangles,
960,000 GPU cycles). Host milliseconds per tick, against the 16.7 ms a tick lasts, best of
three runs of 600–1,200 ticks:

| Cart | Native `mei-headless`, 500k | 1M | WebAssembly in Chromium 152, 500k | 1M |
|---|---|---|---|---|
| Busy loop, integer and memory | 4.05 | 7.38 | 1.99 | 4.06 |
| Busy loop, vector unit (`mat4_mul`, `dot`) | 2.76 | 5.27 | 1.90 | 3.80 |
| Busy loop and 960,000 GPU cycles | 3.93 | 7.36 | 3.25 | 5.04 |
| Movement Garden tour (scenario 27) | 1.69 | 1.65 | 1.24 | 1.23 |
| Movement Garden camera sweep (scenario 30) | 2.32 | 2.32 | 1.68 | 1.65 |

The native figures are the Makefile's build (`-O2 -g`). The browser figures are the core
compiled with Emscripten 6.0.10 at the web build's `-O3` and timed in the Claude desktop app's
Chromium (Node's V8 gives the same within 5%); they leave out `sdl_main.c`'s presenting and
audio, which the CPU's clock does not change. At 1,000,000 cycles the worst case takes 44% of a
tick natively and 30% in the browser, so both hold 60 ticks a second with more than twice the
time to spare.

**What changed with it.**

- `cpu_used()`, `cycle_count()` and the task clock in `stdlib/task.akr` count in `CPU_BUDGET`.
  `cycle_count()`'s s32 now wraps every 35 seconds instead of 71, and `cpu_used()` counts at
  most 2,000 overrun budgets instead of 4,000 so that it cannot overflow.
- The readouts drawn against the budget use `CPU_BUDGET`: the shell's System page (which now
  reads 60 MHz and 1,000,000 cycles), Movement Garden's timing bar, and the CPU percentage in
  the debug lines of Lantern Lake and Sun & Moon Orbs.
- The World Checker's `draw_cpu_cycles` threshold is 600,000, still 60% of the CPU.
- Thresholds that are a cart's own tuning rather than a share of the budget stay as they were,
  so the cart behaves the same: Sun & Moon Orbs' subdivision governor (`SUB_CPU_HIGH`,
  `SUB_CPU_LOW`).

**Existing carts.** Frames are unchanged except where a frame used to run over the CPU budget
and where a readout draws the budget. Compared frame by frame over every scenario of `make
test-carts` and 600 ticks of each built cart and the system ROM: each Lantern Lake scenario had
one frame over 500,000 cycles and now has none, so it presents one more frame and the rest of
the run is a frame ahead; Movement Garden's scenarios 36–38 (which time `mesh_at` on purpose)
present 94 frames of 100 instead of 88; and Movement Garden's timing bar is half as long. Mei
Weather, World Viewer, Sun & Moon Orbs, Features and the system ROM are unchanged.

## A depth buffer, perspective texturing and a 2,000,000-cycle GPU

On 2026-10-03 the project owner set Mei's target as "the 1997 slot", just past the N64, and
decided three changes to the Prism Engine after two prototypes measured them (branches
`worktree-agent-a3f0efcad6721f943`, commit `cc8f47a`, and `worktree-agent-a0ed2dee138e8ac58`,
commit `56ffd84`):

1. **A depth buffer, opt-in.** Cost model "early depth": a pixel that fails the depth test costs
   only the test, and opaque faces are meant to be submitted nearest first. Semi-transparent
   faces test but do not write, and still go back to front.
2. **The GPU budget doubled:** 1,000,000 → **2,000,000 cycles a tick**, the Prism Engine at
   120 MHz. The CPU is unchanged (1,000,000).
3. **Perspective-correct texturing**, one divide every **16 pixels** with affine steps between;
   textures stay unfiltered (nearest texel). Opt-in per polygon.

The interface (registers, packets, the key, the test, the perspective rule, the cost table) is
[RENDERING.md](RENDERING.md); this section records why. It supersedes the v0.1 spec's "Depth:
None" and its affine-only texturing, and the GPU figure in [GPU budget](#gpu-budget); the spec
is left as published.

**One packet bit, one word per vertex.** Both prototypes had independently chosen the same
encoding: types `0x30`–`0x3F` are the `0x2X` layouts followed by each vertex's view depth *w*
(16.16, what `vxp3` leaves in lane w). The adopted chip takes one reciprocal per vertex,
2⁴⁰ ÷ *w*, and uses it for both: interpolated exactly for the depth key, and scaled to 16 bits
for the perspective planes. So one set of face loops serves both features, and the setup that
computes the reciprocals is charged once a triangle (24 cycles) whichever of the two uses it.
Packets without the bit are untouched, so every existing cart draws as before.

**Why a depth buffer.** The ordering table sorts each face by its average depth, and the kits
spend a great deal working around what that gets wrong (object keys and biases, a ground pass
drawn first, authoring rules about splitting tops and keeping clear of thin geometry, and the
Asset and World Checkers' ordering checks). The depth prototype ran the World Checker over the
Movement Garden's 600 views both ways:

| | Ordering table | Depth buffer |
|---|---|---|
| wrong-order pixels, near / far | 51,382 / 4,810 | 73 / 81 |
| views with wrong order | 263 | 53 |
| entity over a nearer face / something over an entity | 17,464 / 2 | 3 / 0 |
| GPU cycles a view, peak / median (+1 a tested pixel) | 625,372 / 243,828 | 941,678 / 366,395 |

What is left with the depth buffer is a pixel or few at edges: vertex positions are whole
pixels, so a face's plane is off by up to half a pixel's worth of depth.

**Why 16 bits, a float of 1/w, on the GPU.** 1/*w* is linear in screen space, so interpolating
it is exact and cheap; *w* itself would need a divide per pixel. Stored linearly in 16 bits,
1/*w* would step 2.5 units at a distance of 128; as a float with a 12-bit mantissa it steps
1/4,096 of the distance at any distance, which is what a facing wall needs (the precision table
in RENDERING.md). The 150 KB buffer is the GPU's own memory: VRAM stays 1 MB for framebuffers,
palettes and textures, and the CPU never needs to read it.

**Why early depth, and what a passing pixel costs.** At +1 cycle for every tested pixel (the
prototype's model: a 16-bit read-modify-write on its own bus) the garden's GPU peak rose
51–64 % and one frame of the kick alley went 1.9 % over the old budget, because the table still
drew back to front, so the test rarely failed and saved nothing. Under early depth the test
sits in front of the pixel pipeline on the depth memory's own bus: a pixel that fails costs 1
cycle (its test) and is never textured or blended; a pixel that passes costs what it always
did, the test overlapping its texel fetch and write. (The prototype's estimate of about 600,000
for the kick-alley frame with near-first order assumed exactly this.) Hidden pixels then cost
less than visible ones, so opaque faces submitted nearest first are cheapest. `GPU_ZCLEAR`
costs what `GPU_CLEAR` does, 38,400.

**Why perspective, and why every 16 pixels.** Affine texturing warps large faces, and
`subdivide()` only reduces it at a high CPU cost. The perspective prototype measured a corridor
of large textured quads (`tests/perspective/measure.py` on its branch), 24 cycles a triangle
for the reciprocals and 2 a divide:

| Corridor view | `mesh()` CPU | GPU cycles | GPU vs affine | Pixels off the exact picture | Mean error (texels) |
|---|---|---|---|---|---|
| affine | 12,334 | 161,970 | — | 99.5 % | ≥ 5 |
| affine + `subdivide(2)` | 50,858 | 163,238 | +0.8 % | 99.5 % | ≥ 5 |
| a divide every pixel (exact) | 12,622 | 284,964 | +75.9 % | 0 | 0 |
| every 8 pixels | 12,622 | 181,128 | +11.8 % | 10.4 % | 0.17 |
| **every 16 pixels** | 12,622 | 173,760 | **+7.3 %** | 20.7 % | 0.41 |
| every 32 pixels | 12,622 | 170,160 | +5.1 % | 33.4 % | 0.82 |

A divide every 16 pixels removes the warp for about 7 % more GPU work (6–7 % on the other two
views), and leaves a one-texel drift between divide points at grazing angles: the look of a
1997 span renderer with nearest sampling, which the owner chose over N64-style filtering.
Every 8 pixels costs twice the divides for half the error; every 32 visibly wobbles on far
walls. The prototype's selector of the spacing (`GPU_CTRL` bits 8–10) is not adopted.

**Why 2,000,000 cycles.** The new mode costs more per frame than the ordering table (a
`GPU_ZCLEAR` a frame, the reciprocals, the divides, and, where faces are not perfectly sorted,
overdraw that still costs), the heaviest carts already reached 87 % of the old budget (Lantern
Lake's map menu), and the garden's World Checker views peaked at 941,678 with the prototype's
costs. A 120 MHz polygon chip beside the 60 MHz CPU fits the 1997 slot. The 4,000-triangle
backstop is unchanged: at 40 cycles a triangle it still binds only far past any frame that fits.

**Calls made while adopting it** (by the agent that built it; recorded so they can be revisited):

- A pixel that passes costs its old price, with nothing added for the test (above).
- The reciprocal is ⌊2⁴⁰ ÷ *w*⌋ for *w* ≥ 1/16 and 2²⁸ otherwise, including *w* ≤ 0, as in
  the depth prototype. For perspective the three are shifted right together until the largest
  fits 16 bits (the perspective prototype normalised to the nearest vertex instead); the
  difference is below a texel's rounding.
- A triangle whose three scaled reciprocals are equal is affine: it draws exactly as without
  depth and makes no divides. So a billboard or a sprite drawn with one *w* looks as it would
  without depth.
- At every divide point, the span's last pixel included, the pixel uses the divided value; the
  prototype stepped onto its last pixel.
- `GPU_DEPTH` keeps bit 0 only (bits 1–31 reserved, read 0); `GPU_ZCLEAR` reads 0.
- The decal offset is added to the key that is written as well as to the one tested, so a decal
  drawn before its wall still wins (as in the depth prototype).
- An untextured packet with depth while the test is off costs exactly its plain price (it needs
  no reciprocals); a triangle that needs them pays the 24 cycles even when empty or off screen,
  like the 40 of setup.
- The World Checker's `gpu_cycles` threshold follows the budget: 1,600,000 (80 %).

**What changed with it.** `MEI_GPU_CYCLES_PER_FRAME` and `GPU_BUDGET` are 2,000,000;
`tools/mei_gpustats.py` reports against it and lists the depth and perspective work (the new
`--gpu-stats` columns `px_ztest`, `px_zfail`, `zclears`, `tris_recip`, `px_persp`,
`persp_divs`); `stdlib/io.akr` names `GPU_DEPTH` and `GPU_ZCLEAR`. Packet type `0x30` was the
unit tests' example of an unknown type; `0x40` is now.

**Existing carts.** Every cart ROM and `system.mei` builds byte-identical to the build before,
except Movement Garden's: its timing readout draws the GPU bar against `GPU_BUDGET` (the ROM is
identical with the old constant). Compared frame by frame, old build against new: every cart
and the system ROM for 1,800–2,400 ticks with scripted input, every Lantern Lake and Movement
Garden scenario of `make test-carts` (121 runs). No frame of any run was over 1,000,000 GPU
cycles before (the highest: 894,990, Lantern Lake scenario 9), so no frame presents earlier
and every frame is identical, except in Movement Garden's timing readout, whose GPU bar is half
as long (and its cycle counts move by the pixels the bar no longer draws).

**Host time.** The new spans are compiled for every combination of the depth test,
perspective and the old flags; the old types take the old spans, whose speed is unchanged. The
unit tests' benchmark (2,000 textured Gouraud triangles of about 35 × 36 pixels, far more fill
than a frame within the budget): natively (M1 Pro, `-O2`) 4.5 ms a frame plain, 5.5 ms
depth-tested, 7.0 ms depth-tested and perspective; in WebAssembly (Emscripten `-O3`, Node)
7.8, 10.6 and 9.5 ms.

## VRAM at 2 MB

On 2026-10-05 the project owner doubled VRAM: **1 MB → 2 MB, `0x400000`–`0x5FFFFF`**
(`MEI_VRAM_BASE`, `MEI_VRAM_SIZE` in `src/core/mei.h`; the layout in `src/core/machine.h`). The
target stays the 1997 slot: the N64 had 4 MB of RAM shared by everything, the PlayStation 1 MB of
VRAM beside 2 MB of RAM. This supersedes the VRAM size and layout in the published v0.1 spec
(`spec-v0.1.pdf`, `spec-v0.1.txt`, p. 10–11), which is left as published, like the CPU and GPU
figures before it.

**Why.** The shrine town, the movement garden's second large level, is limited by texture
memory. A World Kit region could use slots 13–0, 448 KB; the town's region was full to 32 bytes
of its allowance and the level's assets need 595 KB before its ground
(`carts/garden/shrinetown/TEXTURES.md`). Palettes ran out as well: regions get disjoint 4-bit
palettes so that every region's colours are loaded at once, and the town and shrine regions
already took palettes 0–232 of the 255 (an 8-bit texture takes 16 more).

**The memory map.** The first megabyte is unchanged, so every address a cart, the system ROM or
the standard library uses stays where it was. Nothing was above VRAM before `MEI_IO_BASE`
(`0xFF0000`), so the second megabyte needs no other region to move:

| Address | Contents | Size |
|---|---|---|
| `0x400000`–`0x44AFFF` | framebuffers A and B | 300 KB |
| `0x44B000`–`0x44BFFF` | spare | 4 KB |
| `0x44C000`–`0x44DFFF` | palette bank 0: colours 0–4095 | 8 KB |
| `0x44E000`–`0x47FFFF` | Horizon Engine line tables and pages 10–15 (convention) | 200 KB |
| `0x480000`–`0x4FFFFF` | texture slots 0–15 (pages 16–31) | 512 KB |
| `0x500000`–`0x57FFFF` | **texture slots 16–31** (pages 32–47) | 512 KB |
| `0x580000`–`0x581FFF` | **palette bank 1: colours 4096–8191** | 8 KB |
| `0x582000`–`0x5FFFFF` | **free**: the rest of page 48, pages 49–63 | 504 KB |
| `0x600000`–`0xFEFFFF` | unmapped, as before | |

Slot *n* is at `0x480000 + n × 0x8000` for every *n* 0–31, so slots 16–31 continue the old
formula. Palette bank 1 could not follow bank 0 directly: `0x44E000` is the line tables' place
in the standard library (`planes.akr`, which Lantern Lake and the World Kit's backdrops use), so
it sits after the slots.

**The packet encoding.** Bits 21 and 22 of a packet's first texture coordinate, which the spec
left unused and which nothing set (the face loops mask them out; RENDERING.md, "Texture slots and
palette banks"):

- **bit 21, the slot's bank**: slots 16–31 (bits 16–19 the slot within the bank);
- **bit 22, the palette bank**: colours 4096–8191, so 4-bit palettes 256–511 and 8-bit palettes
  16–31 (bits 24–31 the palette within the bank);
- bit 23 stays reserved (ignored): a third bank, if VRAM ever grows again.

An 8-bit texture's second slot wraps within its bank: slot 15 into slot 0 as before, slot 31
into slot 16. The packet does not grow and neither field costs a GPU cycle. A packet with the
two bits clear draws exactly as before.

**More palette entries came with it** because the bank bit is free to add and the palettes were
as short as the slots: 8,192 colours, 512 4-bit palettes. The plane chip still reads bank 0 only
(its palette fields are unchanged); its page and map registers gain bit 20 (`BGn_TILES` bits
15–20, `BGn_MAP` 11–20, `LCn_ADDR` 2–20), so atlases, maps and line tables may be anywhere in
the 2 MB, and its addresses wrap at the end of the 2 MB instead of the 1 MB.

**Meshes.** A face has no spare bit in its texture and palette bytes (bits 5–7 of the texture
byte are the texture window), and the blend byte's bits 2–7 are taken at run time by
`poly_upper()` and the decal offset. Bits 6 and 7 of the **flags** byte were unused: bit 6
(`FACE_SLOT_HI`) puts the face's texture in slots 16–31, bit 7 (`FACE_PAL_HI`) its palette in
bank 1 (LANGUAGE.md, "Mesh format"). Every mesh made before has them clear and draws as it did.
`mesh()`'s packet writers copy them into bits 21–22: three instructions per drawn textured face,
in every face loop (plain, plane chip and depth; `tools/gen_faces_asm.py`). A variant of the
writers only for meshes that use the bits, as texture windows have, would have kept old meshes at
their old cost but doubled the jump tables again and left the World Kit's fast loop for flat
textured faces (`__draw_faces_safe`) without them. Measured, the three cycles are about 1 % of a
busy frame (below).

**The kits.** The World Kit's default region slots are `"13-0,16-31"`, 30 slots: **983,040 bytes
a region** where 458,752 was (`textures.budget` still caps it). 13–0 come first, so a set that
fit before packs exactly as before. Regions' palettes are still disjoint, now from 0–254 and
256–511; a region's range never includes 255 (the fonts'), so one that does not fit below it
starts at 256, and no palette run crosses colour 4096. `palette.first8`'s default is 31, the top
of bank 1 (it was 14, in the middle of bank 0's 4-bit palettes), and 8-bit palettes never take
15 (the fonts' colours). The Asset Kit's slots and palettes are 0–31 and 0–511 the same way
(`palette_layout`, `pack --slots`, `--palette`, `--palette8`); a single asset's default packing
fills slots 14–0 first, then 16–31. `kitcore/texpack.py` does both kits' packing. The World
Checker, the Asset Checker's renderer and the Reference Renderer read the new bits. The World
Checker has no texture thresholds; its CPU thresholds are unchanged.

**The standard library.** `load_texture()` takes slots 0–31; `load_palette()` and
`palette_lerp()` take colours 0–8191 (a run that crosses 4096 continues in bank 1);
`palette_ptr(i)` gives a colour's address; `tex_page()` and `sprite()` take slots 0–31 and
palettes 0–511 (0–31 for 8-bit); `tex_atlas()` slots 0–31. `io.akr` names `VRAM_PALETTE_HI`,
`PALETTE_BANK_COLOURS`, `TEXTURE_SLOTS`, `VRAM_FREE` and `VRAM_END`, `draw.akr` `TEX_SLOT_HI` and
`TEX_PAL_HI`, `gfx.akr` `FACE_SLOT_HI` and `FACE_PAL_HI`. The World Kit reader
(`wp_region_enter()`, `wp_texture_load()`, `wp_variant_load()`, `wp_variant_blend()`, the
animated tiles) needed no change of its own: it loads through those functions, and the pack
format already had a byte for the slot and 16 bits for the first colour (WORLDPACK.md; the
encoder now accepts slots 16–31 and colours to 8,191, with no version change). The shell's System
page reads "2 MB, 32 texture slots".

**Existing carts.** Compiled with the old standard library, every cart ROM and `system.mei`
builds byte-identical to the build before, and the three garden worlds' packs are byte-identical:
the compiler, the assembler, the carts and the kits' output for existing recipes are unchanged.
With the new standard library the ROMs grow by the face loops' three instructions a writer and
the bank handling in `load_palette()`, `palette_lerp()`, `tex_page()`, `sprite()`,
`load_texture()` and `tex_atlas()` (bytes):

| ROM | Before | After | Face loops | The rest of the library |
|---|---|---|---|---|
| `system.mei` | 890,329 | 890,441, and the System page's text | 0 | +112 |
| `features.mei` | 26,806 | 26,806 (identical) | 0 | 0 |
| `lantern.mei` | 1,330,337 | 1,330,953 | +504 | +112 |
| `orbs.mei` | 861,166 | 861,886 | +504 | +216 |
| `weather.mei` | 857,163 | 857,339 | 0 | +176 |
| `garden.mei` | 19,540,915 | 19,541,907 | +864 | +128 |

Compared frame by frame, old build against new: every cart and the system ROM for 1,800 ticks
with the same scripted input (the GPU statistics of every presented frame, the last frame's
pixels, the tick each frame was presented at). Every frame is presented at the same tick, and no
frame changes except where a cart acts on its own CPU use:

| Cart | Frames | CPU cycles a frame added, mean / most | Peak CPU |
|---|---|---|---|
| system ROM | identical | 0 / 34 | 118,665 → 118,699 |
| Features | identical | 0 / 0 | 72,881 |
| Lantern Lake | identical | 833 / 945 | 488,779 → 489,687 |
| Mei Weather | identical | 73 / 124 | 162,957 → 163,030 |
| Movement Garden | the timing bar 6 pixels longer, nothing else | 2,767 / 4,215 | 487,953 → 491,913 |
| Sun & Moon Orbs | differ from tick 89 | 639 on average | 366,479 → 367,752 |

Sun & Moon Orbs' subdivision governor subdivides less above 280,000 cycles a frame
(`SUB_CPU_HIGH`, its own tuning): at tick 88 the new build crosses it (280,258 against 279,097)
and the governor steps down a tick earlier, so the orbs are cut into a few triangles fewer from
then on. The World Checker's peaks over the garden's three worlds (600 views each; the GPU
figures and hard failures are identical):

| World | CPU peak before | After | Over a threshold, before / after |
|---|---|---|---|
| garden | 451,836 | 456,849 (+1.1 %) | 0 / 0 |
| shrine | 590,756 | 596,123 (+0.9 %) | 0 / 0 |
| shrinetown | 617,020 | 619,861 (+0.5 %) | 2 / 3 (`draw_cpu_cycles`, 600,000) |

**Host cost.** The core's `Mei` struct grows by the second megabyte (it holds RAM, VRAM and the
depth buffer by value); the web build grows its memory as it needs (`ALLOW_MEMORY_GROWTH`) and
builds unchanged. The GPU's per-pixel work is unchanged (it resolves the banks once a packet,
into the base pointers it already had): the unit tests' benchmarks (`test_gpu`, `test_planes`)
are within their run-to-run spread of the build before (2,000 textured Gouraud triangles of about
35 × 36 pixels: 5.4–5.9 ms against 5.5–5.9 ms a frame natively, M1 Pro, `-O2`, three runs each,
measured while a world built).

**Calls made while adopting it** (by the agent that built it; recorded so they can be revisited):

- The second megabyte is laid out as slots 16–31, palette bank 1, then free space, rather than
  as more slots (bit 23 could address 48): the free 504 KB serve the plane chip and carts, and
  the regions' budget doubles already.
- The palette banks are a bit, not a contiguous 13-bit colour index: bank 1 is not next to bank
  0 in memory, and `load_palette()` and `palette_lerp()` hide that for runs. `palette_rotate()`
  works within one bank.
- Planes stay on palette bank 0.
- The face loops pay three cycles a textured face rather than a second set of writers.
- `palette.first8` moved to 31. No built world has an 8-bit texture, so no pack changed; the
  night market example's sign moved from 8-bit palette 14 to 31.
- The spec text (`spec-v0.1.txt`) is a transcription of the published PDF and is left as it is,
  as for the CPU and GPU changes; DECISIONS.md, RENDERING.md and PLANES.md give the current map.
