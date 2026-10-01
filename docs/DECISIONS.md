# Implementation decisions

The spec (`spec-v0.1.txt`) is authoritative. This file records how this implementation
settles the open questions and the details the spec leaves ambiguous. Everything here
is deterministic.

## Open questions from the spec

| Question | Decision |
|---|---|
| Random numbers | xorshift32 (`x ^= x<<13; x ^= x>>17; x ^= x<<5`). Reset seed `0x4D454921`. Reading `RAND` advances the state and returns it. Writing sets the seed; writing 0 sets it to the reset seed (xorshift would stick at 0). |
| Audio mixing | Each channel produces a signed 16-bit sample (8-bit samples are shifted left 8). Left = sample × left volume ÷ 256 (arithmetic shift), same for right. The eight channels are summed in 32 bits and hard-clipped to −32768..32767. No interpolation: nearest sample. |
| Save data | Two memory card slots, 128 KB each in 512-byte blocks, accessed through a card controller at `0xFF0380` that isolates each cart's saves by cart ID. Saves carry a title and a 16×16 animated icon. See `MEMCARD.md`. |
| Cart file format | A cart is a raw ROM image (≤ 2 MB) mapped at `0x200000`; execution starts at its first word. Optional header: word 0 is any instruction (normally `jmp start`), bytes 4–7 are `"MEI1"`, bytes 8–39 are the title, NUL-padded, bytes 40–55 the cart ID for memory cards (NUL-padded; all zero: none). Code starts at byte 56. Extension `.mei`. |
| Language syntax | See `LANGUAGE.md`. |
| Compressed audio | Not implemented. |
| Standard library location | Compiled into each cart (counts against its 2 MB). |
| Culling/clipping helpers | No extra instruction; the 59-instruction set is unchanged. Culling is done in the standard library with scalar code. |
| Fill rate | Unlimited, as drafted. |
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
Written pixels always have bit 15 clear.

**Triangle limit.** Counted per triangle: a quad whose first half is the 2,000th
triangle draws that half and drops the second.

**GPU_CLEAR** writes the low 15 bits to every pixel of the back buffer.

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
