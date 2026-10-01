# Mei assembly reference

The assembler is `build/meiasm` (library: `src/asm/asm.h`, `mei_assemble`). The
instruction set itself is in `spec-v0.1.txt` pages 4–9; this file covers the syntax.

```
meiasm in.s [-o out.mei] [--sym out.sym] [--list]   # default output: in.s.mei
meiasm --disasm cart.mei                            # disassemble a ROM from 0x200000
```

`--sym` writes one `ADDRESS NAME` line per symbol (hex, sorted by value). `--list`
prints a listing (address, bytes, source line) to stdout.

## Lines

One statement per line. Comments start with `;` or `//`.

```
label:  addi r1, r0, 5      ; label, instruction, comment
other:                      ; a label alone
        NAME = 42           ; constant
```

- **Labels** are `name:` and may share a line with a statement. Names are
  `[A-Za-z_.][A-Za-z0-9_.$]*` and case-sensitive.
- **Local labels** start with `.` (`.loop:`) and belong to the most recent global
  label: inside `draw:`, `.loop` means `draw.loop`, which is also the name in the
  symbol table and can be used from anywhere.
- **Mnemonics, directives and register names** are case-insensitive.
- Registers: `r0`–`r15`, `sp` (= `r14`), `ra` (= `r15`), `v0`–`v7`. Register names
  cannot be used as symbol names.

## Operands

| Shape | Example |
|---|---|
| registers | `add r1, r2, r3`, `vadd v0, v1, v2`, `vscale v0, v1, r3`, `vdot r1, v0, v1` |
| immediate | `addi r1, r2, -4`, `andi r1, r1, 0xFF`, `shli r1, r1, 3`, `vget r1, v2, 3` |
| memory | `lw r1, [r2+8]`, `sw r1, [r2-4]`, `lb r1, [r2]`, `lw r1, [0x100]` (base `r0`) |
| branch | `beq r1, r2, label` (any expression giving an absolute address) |
| jump | `jmp label`, `call func`, `jr r5`, `callr r5` |

Range checks:

| Operand | Range |
|---|---|
| `addi`, `slti`, memory offsets | −131072..131071 (sign-extended 18 bits) |
| `andi`, `ori`, `xori` | 0..262143 (zero-extended; `andi r1, r1, -4` is an error) |
| `shli`, `shri`, `sari` | 0..31 |
| `lui` | 0..0x3FFFFF (−0x200000.. also accepted, encoded as 22 bits) |
| `vget`/`vset` lane | 0..3 |
| branch target | word-aligned, within ±131072 words of `pc + 4` |
| `jmp`/`call` target | word-aligned, below 0x10000000 |
| `[expr]` absolute | must fit sign-extended 18 bits (so I/O needs a base register) |

`brk` and `vsync` take an optional 26-bit code (`brk 7`) that the CPU ignores.

## Expressions

C precedence, evaluated in 64 bits; the user of the value range-checks it.

| | |
|---|---|
| literals | `42`, `0x2A`, `0b101010`, `'A'`, `'\n'` (C escapes, `\xHH`, octal), `_` allowed as a digit separator in hex/binary |
| fixed point | `1.5`, `-0.25`, `3.14159` → 16.16 integer, rounded to nearest (`1.5` = 98304) |
| `.` | current location (address of the word being assembled) |
| unary | `-` `~` `+` |
| binary (high → low) | `* / %`, `+ -`, `<< >>` (arithmetic), `&`, `^`, `\|` |
| functions | `hi(x)` = `(x & 0xFFFFFFFF) >> 10` (for `lui`), `lo(x)` = `x & 0x3FF` (for `ori`) |

Fixed-point literals are just integers, so `2 * 1.5` is 3.0, but `1.5 * 1.5` is not
2.25 (no rescaling; use `fmul` at run time or `.fixed` for tables).

Symbols may be used before they are defined, except where the value decides a size or
location (`.org`, `.align`, `.space`, `.incbin` arguments).

## Pseudo-instructions

| Pseudo | Expands to |
|---|---|
| `nop` | `add r0, r0, r0` |
| `mov a, b` | `add a, b, r0` |
| `ret` | `jr r15` |
| `li a, x` | `addi a, r0, x` if `x` is known on the first pass and fits signed 18 bits, else `lui a, hi(x)` + `ori a, a, lo(x)` |
| `la a, x` | always `lui a, hi(x)` + `ori a, a, lo(x)` (use for addresses) |
| `b label` | `jmp label` |
| `bgt a, b, L` / `ble` / `bgtu` / `bleu` | `blt b, a, L` / `bge b, a, L` / `bltu b, a, L` / `bgeu b, a, L` |
| `beqz a, L` / `bnez a, L` | `beq a, r0, L` / `bne a, r0, L` |
| `neg a, b` | `sub a, r0, b` |
| `not a, b` | `sub a, r0, b` + `addi a, a, -1` (2 words) |
| `push a` | `addi sp, sp, -4` + `sw a, [sp]` |
| `pop a` | `lw a, [sp]` + `addi sp, sp, 4` |

`li` accepts −2³¹..2³²−1 and uses the low 32 bits, so `li r1, 0xFFFFFFFF` is one
`addi r1, r0, -1`. A `li` whose value is only known later (a forward label or
constant) is always two words.

## Directives

| Directive | Meaning |
|---|---|
| `.section rom` / `.section ram` | switch location counter. ROM starts at 0x200000, RAM at 0x000100 |
| `.org addr` | set the location. In ROM only forward (the gap is zero-filled) |
| `.align n` | align to `n` bytes (power of two); ROM padding is zero |
| `.byte x, ...` | 8-bit values (−128..255); string items allowed: `.byte "ab", 0` |
| `.half x, ...` | 16-bit little-endian values |
| `.word x, ...` | 32-bit little-endian values (labels allowed) |
| `.fixed x, ...` | 16.16 words; items are real-number expressions of literals with `+ - * /` and parentheses (`.fixed 1, 0.5, 1/3`), no symbols |
| `.ascii "s", ...` | string bytes (C escapes) |
| `.asciz "s", ...` | string bytes plus a NUL each |
| `.space n [, fill]` / `.zero n` | `n` bytes of `fill` (default 0) |
| `.equ NAME, x` / `NAME = x` | define a constant (no redefinition) |
| `.include "file"` | assemble another source file inline (path relative to the including file) |
| `.incbin "file" [, offset [, length]]` | insert raw bytes from a file |
| `.cart "Title" [, entry] [, "ID"]` | cart header (see below); must be the first thing in ROM |

`.half`, `.word` and `.fixed` do not align automatically; instructions must be
word-aligned (use `.align 4` after byte data).

The **ram** section holds no initialised data: only labels, `.org`, `.align`,
`.space`/`.zero` without a fill, and constants. It is for reserving variables:

```
        .section ram
score:  .space 4
buffer: .space 1024
        .section rom
        lw   r1, [score]          ; small RAM addresses fit in an absolute operand
```

`ram_used` in the result (end of the RAM section) is the first free RAM address.
The stack starts at 0x200000 and grows down.

**Cart header.** `.cart "Title", entry, "ID"` emits `jmp entry`, the bytes `MEI1`, the
title NUL-padded to 32 bytes, and the cart ID NUL-padded to 16 bytes (56 bytes in all, see
`DECISIONS.md`). Without `entry` (`.cart "Title"`, `.cart "Title", "ID"` or
`.cart "Title", , "ID"`) the jump goes to 0x200038, the first byte after the header. The
cart ID (up to 16 printable ASCII characters, e.g. `"LANTERN-LAKE"`) is what the memory
card controller files the cart's saves under (`MEMCARD.md`); without one the header holds
zeros there and the controller uses a hash of the title.

## Output

The ROM image runs from 0x200000 to the highest byte written (at most 2 MB). The
symbol table holds every label and constant, sorted by value. Errors stop assembly
with one message in `file:line: message` form, e.g.
`game.s:12: immediate 200000 out of range (-131072..131071)`.

## Disassembly

`mei_disasm` output is valid input: branches and jumps show absolute hex targets,
`add a, b, r0` shows as `mov`, `jr r15` as `ret`. Reserved opcodes, R-format words
with non-zero low bits, vector fields above 7, lanes above 3, shift amounts above 31,
and `jr`/`callr` words with ignored fields set come out as `.word 0x...`, so every word
re-assembles to itself at the same address.

## Example

```
; Clear the screen to blue every frame and print "HI" once.
        .cart "Example", start

IO_HI     = 0x3FC0              ; lui value for the I/O base 0xFF0000
GPU_CLEAR = 0x004
DEBUG     = 0x30C

        .section ram
frames: .space 4                ; a RAM variable at 0x100
        .section rom

start:  lui   r1, IO_HI
        li    r2, 'H'
        sw    r2, [r1+DEBUG]
        li    r2, 'I'
        sw    r2, [r1+DEBUG]
        li    r2, '\n'
        sw    r2, [r1+DEBUG]
        li    r3, 31 << 10      ; pure blue

.frame: sw    r3, [r1+GPU_CLEAR]
        lw    r4, [frames]
        addi  r4, r4, 1
        sw    r4, [frames]
        vsync
        b     .frame
```

A fuller sample is `carts/asm/hello.s`.
