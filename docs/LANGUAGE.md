# Akari

Akari (明かり, "light") is the Mei console's programming language. Its name shares the
kanji 明 with the console: sun and moon, "bright". It is small and statically typed, and
it compiles to the Mei CPU's machine code. Source files end in `.akr` (the older `.mls`
extension still builds). There is no garbage collector and no heap:
data is scalars, vectors, structs and fixed-size arrays in RAM, ROM and registers.

```
cart "Spinner"
embed CUBE: Mesh = "cube.bin"

var angle: fixed

fn update() {
    if btn(LEFT)  { angle -= 0.05 }
    if btn(RIGHT) { angle += 0.05 }
}

fn draw() {
    cls(rgb(20, 30, 60))
    camera(vec3(0.0, 1.0, -6.0), 0.0)
    mesh_at(CUBE, vec3(0.0, 0.0, 0.0), angle)
    text(8, 8, "HELLO", rgb(255, 255, 255))
}
```

## Contents

1. [Building and running](#building-and-running)
2. [Program structure](#program-structure)
3. [Lexical rules](#lexical-rules)
4. [Declarations](#declarations)
5. [Types](#types)
6. [Constants and conversions](#constants-and-conversions)
7. [Operators](#operators)
8. [Statements](#statements) (and [assert](#assert))
9. [Enums and match](#enums-and-match)
10. [Functions as values](#functions-as-values)
11. [Built-in functions](#built-in-functions)
12. [map, filter, reduce, each](#map-filter-reduce-each)
13. [Memory](#memory)
14. [Assembly](#assembly)
15. [Calling convention](#calling-convention)
16. [Standard library](#standard-library)
17. [Saving](#saving)
18. [Mesh format](#mesh-format)
19. [Performance notes](#performance-notes)
20. [Limitations](#limitations)

## Building and running

```
meic game.akr -o game.mei            # compile (default output: game.mei)
meic game.akr -S game.s --sym game.sym   # also write the assembly and a symbol table
mei game.mei                         # run in the desktop player
mei-headless game.mei --frames 60 --dump frame.ppm   # run without a window
```

Options: `--title TEXT` sets the cart title (otherwise the `cart` declaration, else the file
name), `--no-stdlib` compiles without the standard library, `--release` drops `assert`s.

The standard library (`stdlib/*.akr`) is compiled into every cart. `meic` looks for it in
`$MEI_STDLIB`, then in `<directory of meic>/../stdlib`. Only functions a cart can reach are
emitted. The library API `meic_compile()` (`src/lang/lang.h`) takes a file-reader callback,
so the compiler can run without a file system (for example in the browser).

Errors stop compilation and are reported as `file:line:col: error: message`, followed by the
source line and a caret.

## Program structure

A program is a set of top-level declarations in one or more files. The cart may define three
functions, all optional, with no parameters and no result:

| Function | Called |
|---|---|
| `fn init()` | once, after global initialisers and the standard library's start-up |
| `fn update()` | every frame |
| `fn draw()` | every frame, after `update()` |

The frame loop is: begin frame (reset the ordering table and packet memory) → `update()` →
`draw()` → end frame (draw the ordering table, then the interface list, remember the pads
for `btnp`) → `vsync`. Output appears on the debug console through `print*` functions.

`import "other.akr"` includes another file (path relative to the importing file). Each file is
compiled once however often it is imported; all files share one global namespace. A cart may
reuse a name the standard library defines (`A`, `sin`, ...): the cart sees its own
declaration and the library keeps using its own.

## Lexical rules

- Comments: `// to end of line` and `/* block */`.
- Statements end at a newline or `;`. A newline inside `( )` or `[ ]`, or after an operator or
  comma, does not end a statement. A `{` may start on the next line, and `else` may follow a
  line break after `}`.
- Identifiers: `[A-Za-z_][A-Za-z0-9_]*`. Names starting with `__` are used by the standard
  library.
- Integer literals: `42`, `0x2A`, `0b101010`, with `_` separators (`1_000_000`). Character
  literals `'A'`, `'\n'` are integers.
- Fixed-point literals contain a decimal point: `1.5`, `0.05`, `-3.25`. They are rounded to the
  nearest 1/65536 at compile time; there is no floating point anywhere at run time.
- String literals `"text"` are NUL-terminated byte arrays in ROM; escapes: `\n \t \r \0 \\ \"
  \' \xHH`.
- Keywords: `fn var let const struct enum if else while for in match break continue return
  import asm reg embed as true false null cart`. `=>` separates match patterns from arms and
  starts an expression-bodied function literal.

## Declarations

| Declaration | Meaning |
|---|---|
| `cart "Title"` / `cart "Title", "ID"` | the title in the cart header (at most 32 bytes) and the cart ID for memory cards (at most 16 printable ASCII characters; see [Saving](#saving)) |
| `import "file.akr"` | compile another file into the program |
| `const NAME = expr` / `const NAME: T = expr` | a compile-time constant; with an array or struct type, read-only data in ROM |
| `var name: T` / `var name: T = expr` / `var name = expr` | a global variable in RAM |
| `reg NAME: T @ address` | a memory-mapped register; `T` must be 32 bits (`u32`, `s32`, `fixed`, a pointer) |
| `embed NAME: T = "file" [, offset [, length]]` | the bytes of a file, placed in ROM; `NAME` is a `*T` |
| `struct Name { field: T, ... }` | a structure (fields separated by commas or newlines) |
| `enum Name { A, B = 5, ... }` / `enum Name: u8 { ... }` | an enumeration (see [Enums and match](#enums-and-match)) |
| `fn name(a: T, ...) -> R { ... }` | a function (`-> R` omitted: no result) |
| `asm fn name(a: T, ...) -> R { ... }` | a function written in assembly |

```
const SPEED = 3                       // untyped integer constant
const GRAVITY: fixed = 0.25
const WORLD_UP: vec3 = vec3(0.0, 1.0, 0.0)
const TITLE = "MEI"                   // [4]u8 in ROM
const WAVE: [4]fixed = [0.0, 0.5, 1.0, 0.5]

reg BORDER: u32 @ 0xFF0004            // BORDER = 0x1F is one sw

embed LEVEL: Mesh = "level.bin"       // LEVEL is a *Mesh into ROM
embed MUSIC: s8 = "music.raw", 0, 22050
```

Globals are zero at reset. A global's initialiser may be any expression, including calls;
initialisers run at start-up in declaration order (imports first). Constants must be known at
compile time and may refer to other constants (but not to variables).

Const arrays and structs may also hold **addresses that are fixed when the cart is built**: embeds,
strings, other const data, and named functions, as they are or converted to a pointer, `u32` or
`s32`. They are written into ROM as `.word label`, which makes ROM tables of assets cheap:

```
embed FERN: Mesh = "fern.bin"
embed ROCK: Mesh = "rock.bin"
const PROPS: [2]*Mesh = [FERN, ROCK]                 // PROPS[i] is one load
const ADDRS: [2]u32 = [FERN as u32, ROCK as u32]
struct Level { name: *u8, mesh: *Mesh, music: *s8 }
const LEVELS: [2]Level = [Level { name: "Shore", mesh: ROCK, music: null }, ...]
const ACTIONS: [3]fn(s32) = [walk, swim, fish]       // function values: [code, 0, 0, 0]
```

A function named only in const data is still compiled in (when the data is used). Function
literals, addresses of variables (`&g`) and single constants holding an address
(`const M: *Mesh = FERN`; use `FERN` itself) are not allowed.

Everything at the top level is visible everywhere (declaration order does not matter, except
for initialisers that read other globals).

## Types

| Type | Size | Notes |
|---|---|---|
| `s8 s16 s32` | 1, 2, 4 | signed integers |
| `u8 u16 u32` | 1, 2, 4 | unsigned integers |
| `fixed` | 4 | 16.16 fixed point, −32768 to 32767.99998 |
| `bool` | 1 | `true` / `false` |
| `vec2 vec3 vec4` | 16 | vectors of `fixed`; unused lanes are always zero |
| `ivec4` | 16 | four `s32` lanes |
| `mat4` | 64 | four `vec4` rows; `m[i]` is row `i` |
| `*T` | 4 | pointer to `T` |
| `fn(T, U) -> R` | 16 | function value: a code address and up to 3 captured words (`fn(T)` returns nothing); 4-byte aligned |
| enum | 1, 2 or 4 | an `enum` declaration; stored as its underlying integer type (default `s32`) |
| `[N]T` | N × size | fixed-size array (`[4][4]u8` is an array of arrays) |
| struct | fields, padded | fields are aligned to their size (vectors and `mat4` to 4) |

Arithmetic happens in 32 bits. The 8- and 16-bit types exist for memory layout; a value read
from one is sign- or zero-extended, a value stored into one is truncated.

Scalars live in scalar registers, vectors in vector registers; structs, arrays and matrices
always live in memory.

## Constants and conversions

**Untyped constants.** Integer literals and constants declared without a type are *untyped*:
they take whatever type the context needs, if the value fits. `var x: u8 = 200`,
`let f: fixed = 3` (3.0) and `p.yaw += 1` are all fine. An integer constant fits a 32-bit type
if it is in −2³¹..2³²−1 (so `0xFFFFFFFF` is a valid `s32` mask), and an 8/16-bit type if it fits
its bits with either signedness. Without context, integer constants become `s32` and
fixed-point constants `fixed`. Constant expressions are evaluated exactly at compile time;
division by a constant zero is an error.

**Implicit conversions** (assignment, arguments, return values):

- between integer types, in either direction (narrowing truncates);
- `null` to any pointer type; any pointer to `*u8` (a byte pointer, like `void *`);
- an array variable `[N]T` to `*T` (or `*u8`): `sum(buf, 10)` passes `&buf[0]`.

Everything else needs an explicit conversion. In particular integers and `fixed` never mix
implicitly.

**Explicit conversions**: `x as T`, or `T(x)` for scalar types (`fixed(3)`, `s32(f)`).

| From → to | Result |
|---|---|
| integer → `fixed` | the same value: shifted left 16 (`3 as fixed` is 3.0) |
| `fixed` → integer | rounded down (floor): `1.75 as s32` is 1, `-1.25 as s32` is −2 |
| integer → integer | truncated or extended |
| `bool` → integer | 0 or 1 |
| pointer ↔ pointer, pointer ↔ `u32`/`s32`, integer → pointer | the address, unchanged |
| vector → vector | lanes kept; lanes the target lacks become zero (`vec4 as vec3` clears w) |
| `vec4` ↔ `ivec4` | each lane converted like `fixed` ↔ `s32` |
| enum ↔ integer | the underlying value (no check that an integer names a variant) |
| function value → `u32`/`s32` | the code address only (captured words are dropped) |
| `u32`/`s32` → function value | a value with that code address and no captured words |

`bits(f)` gives the raw 32-bit pattern of a `fixed` as `s32` (`bits(1.0)` is 65536);
`from_bits(n)` is the reverse.

## Operators

From lowest to highest precedence:

| Precedence | Operators |
|---|---|
| 1 | `\|\|` |
| 2 | `&&` |
| 3 | `== != < <= > >=` (no chaining) |
| 4 | `\|` |
| 5 | `^` |
| 6 | `&` |
| 7 | `<< >>` |
| 8 | `+ -` |
| 9 | `* / %` |
| 10 | `x as T` |
| 11 | unary `- ! ~ & *` |
| 12 | `f(x)`, `a[i]`, `s.field` |

Note that `&`, `^` and `|` bind tighter than comparisons: `flags & MASK == 0` means
`(flags & MASK) == 0`.

**Integers.** Both operands are brought to one type: small types count as `s32`, except that
an unsigned operand next to a `u32` stays unsigned. Mixing `s32` and `u32` is an error
(convert one). `+ - *` wrap around. `/` and `%` truncate toward zero; dividing by zero gives 0;
the most negative value divided by −1 gives itself. `>>` is arithmetic for signed types and
logical for unsigned; shift counts use their low 5 bits. Multiplication and division by
constant powers of two compile to shifts.

**fixed.** `+ -` add, `*` is `fmul` and `/` is `fdiv` (64-bit intermediates; products round
down, quotients toward zero; division by zero gives 0). A `fixed` may be multiplied by an
integer (`f * 3`, `3 * f`) or divided by one (`f / n`) directly; this is an integer `mul`/`div`
and costs less than `fmul`/`fdiv`. `%` and the bitwise operators are not defined for `fixed`.

**bool.** `&&` and `||` short-circuit; `!` negates. Conditions must be `bool`: write
`if n != 0`, not `if n`.

**Pointers.** `&x` takes an address (of a variable, field, element or dereference), `*p`
dereferences, `p[i]` indexes, and `p.field` reaches a struct field (or vector lane) through a
pointer. `p + n` and `p - n` step by whole elements, `p - q` counts elements between two
pointers of the same type, and pointers compare as unsigned addresses (`p == null`).

**Vectors.**

| Expression | Instruction | Result |
|---|---|---|
| `a + b`, `a - b` | `vadd`, `vsub` | lane-wise (same vector type; also `ivec4`) |
| `a * b` | `vmul` | lane-wise fixed-point product |
| `v * f`, `f * v` | `vscale` | every lane times `f` |
| `v / f` | `fdiv` + `vscale` | `v * (1.0 / f)` |
| `-v` | `vsub` | negation |
| `dot(a, b)` | `vdot` | sum of lane products (`fixed`) |
| `cross(a, b)` | `vcross` | `vec3` cross product |
| `m * v` (`mat4 * vec4`) | 4 × `vld` + `vxfm` | rows of `m` dotted with `v` |
| `m * v` (`mat4 * vec3`) | as above | `w` of the result cleared |
| `m * n` (`mat4 * mat4`) | call to `mat4_mul` | matrix product |

`v.x .y .z .w` read or write one lane. Multi-lane swizzles such as `v.xz` or `v.zyx` build a
new vector (`vec2`/`vec3`/`vec4`) and can only be read. A vector in memory is accessed one lane
at a time with a single load or store, so `p.pos.y += 1.0` costs three instructions.

**Assignment** `=`, and compound `+= -= *= /= %= &= |= ^= <<= >>=`. The target of a compound
assignment is evaluated once (`a[next()] += 1` calls `next` once). Struct, array and matrix
assignment copies the whole value.

## Statements

```
var x: s32                 // a local variable, zero-initialised
var y = 10                 // type inferred (s32)
let z = x + y              // immutable
x = 5
x += 1

if x > 3 { ... } else if x < 0 { ... } else { ... }

while x < 100 { x *= 2 }
while true { if done() { break } }

for i in 0..n { ... }      // i = 0, 1, ..., n-1; i is immutable
for i in lo..hi { ... }    // the bound is evaluated once; nothing runs if lo >= hi

break                      // leave the innermost loop
continue                   // next iteration
return value

{ var tmp = a; a = b; b = tmp }   // a block opens a scope

asm { ... }                // inline assembly, see below
```

Locals are zero-initialised when declared without a value (also on every iteration of a loop
they are declared in). An inner block may shadow an outer name; one block may not declare a
name twice. The loop variable of `for` takes the type of its bounds (`s32` for constants; it
counts with `bltu` when the bounds are `u32`).

Only calls and assignments can be statements (`x + 1` alone is an error). A function with a
result must `return` on every path.

### assert

```
assert(hp > 0)
assert(slot < 16, "slot out of range")
assert_eq(count(), 4)              // reports both values on failure
assert_eq(speed * 2.0, 2.5, "speed doubles")
```

When the condition is false (or the values differ) the cart prints a report to the debug
console and halts with a `Break` fault:

```
assertion failed: game.akr:12: assert_eq(count(), 4)
  got 3, expected 4
```

`mei-headless` prints it and exits with status 2; the desktop player's halt screen shows the
last lines of debug output. `assert_eq` takes integers, `fixed`, `bool`, enums and pointers
(both must be comparable with `!=`); the message must be a string literal. A passing check
costs a compare and a branch. On a failure `assert_eq`'s operands are evaluated a second time
for the report, so keep side effects out of them. `meic --release` drops every `assert` (the
code is still parsed but not type-checked). `assert` and `assert_eq` are keywords.

## Enums and match

```
enum State { Title, Playing, Paused, Won }          // values 0, 1, 2, 3
enum Dir: u8 { Up = 1, Down = 2, Left = 4, Right = 8 }
enum Temp: s8 { Cold = -10, Mild, Hot = 30 }        // Mild is -9

var state = State.Title
struct Actor { state: State, facing: Dir }           // Dir takes one byte
```

Variants are written `Name.Variant`. Values start at 0 and count up by one; `= expr` gives a
variant an explicit constant value (later variants continue from it). Two variants may not
share a value. The optional `: T` picks the underlying integer type, which sets the size in
memory.

An enum is its own type: it does not mix with integers or with other enums. `==`, `!=`, `<`,
`<=`, `>`, `>=` compare two values of the same enum; there is no arithmetic. Convert explicitly
with `as`: `s as s32`, `2 as Dir` (no check that the value is a variant). Enums work in
constants, globals, struct fields and arrays, and as parameters and results.

**match** chooses one arm by value:

```
match state {
    Title => start_music()
    Playing, Paused => {           // several patterns share an arm
        tick()
    }
    Won => show_score()
}

match n {
    0 => r = 1
    1, 2, 3 => r = 2,              // a comma may end an arm
    else => r = 3                  // `_ =>` means the same
}
```

- The value is an enum or an integer. Patterns are constants of that type; in a match on an
  enum a bare variant name (`Title`) means `State.Title`.
- An arm is a single statement or a `{ }` block. Exactly one arm runs; there is no fall-through.
- A match on an enum must handle every variant or have an `else` arm; the compiler lists the
  missing variants. A match on an integer must have an `else` arm. A value may appear in only
  one pattern, and `else` must come last.
- `match` is a statement. A function can end with a `match` whose arms all `return`.
- It compiles to a chain of `beq` compares (2 cycles per pattern tested when taken, 1 when not).

## Functions as values

A function type is written `fn(T, U) -> R` (`fn(T)` for no result). Named functions and
function literals are values of function types:

```
fn twice(x: s32) -> s32 { return x * 2 }

var handler: fn(s32) -> s32 = twice              // a named function as a value
struct Button { label: *u8, on_press: fn() }     // in struct fields, arrays, globals ...

fn apply(f: fn(s32) -> s32, x: s32) -> s32 { return f(x) }   // ... and parameters

fn make_adder(n: s32) -> fn(s32) -> s32 {
    return fn(x: s32) => x + n                   // a literal that captures the parameter n
}

fn chooser(fast: bool) -> fn(s32) -> s32 {
    if fast { return fn(x: s32) => x * 8 }       // function literal, expression body
    return fn(x: s32) -> s32 {                   // function literal, block body
        var r = x
        for i in 0..3 { r += r }
        return r
    }
}
```

- **Literals.** `fn(params) -> R { body }` or `fn(params) => expr`. For `=>`, the result type is
  the expression's type unless `-> R` is given. A literal whose block body has no `-> R`
  returns nothing, unless the expected function type supplies the result type.
- **Inferred parameter types.** Where a function type is expected (an assignment to a typed
  variable, an argument, `map`/`filter`/..., a return value), parameter types may be left out:
  `map(xs, fn(x) => x * x)`, `handler = fn(x) => x + 1`.
- **Types must match exactly**: an `fn(s32) -> s32` is not an `fn(fixed) -> fixed`, and no
  conversion applies to parameters or results.
- A **call** through a value compiles to `callr` (see [Calling convention](#calling-convention)).
  Like any call it clobbers `r1`–`r8` and all vector registers. Calling `null` jumps to
  address 0, which halts the cart with a Break fault.
- A **function value is 16 bytes**, the size of a `vec4`: the code address followed by three
  captured words (zero when unused). In struct fields and arrays it takes 16 bytes with 4-byte
  alignment; in registers it lives in a vector register, and `vld`/`vst` move it whole.
- `null` (all zeros) converts to any function type. `f == g` and `f != g` compare all four
  words: two closures are equal when they run the same code with the same captured values.
  `f as u32` gives the code address alone; `n as fn(s32)` makes a value with no captures.
- Const arrays and structs may hold named functions (`const OPS: [2]fn(s32) -> s32 = [inc, dec]`,
  stored as `[code, 0, 0, 0]`); function literals and closures cannot be `const` data, so put
  those in a `var` array at start-up instead.

### Closures

A function literal may use the locals and parameters of the function around it. They are
**captured by copy** when the literal is evaluated (each time it is evaluated), so later
changes to the original do not affect the function value, and the value stays valid after the
function that made it returns:

```
var k = 10
let add_k = fn(x: s32) => x + k
k = 99
add_k(1)                                // 11: the copy was taken when the literal ran

var fs: [4]fn(s32) -> s32
for i in 0..4 { fs[i] = fn(x: s32) => x * i }   // four values, each with its own i
```

- **Read-only.** Captured variables cannot be assigned or have their address taken inside the
  literal ("'total' is a copy captured by the function literal: captures are copied when the
  literal is evaluated and are read-only"). To share a changing value, use a global, or capture
  a pointer to it.
- **At most 3 words.** Integers, `bool`, `fixed`, enums and pointers take one word each. A literal
  that captures more is an error that lists every capture:

  ```
  error: function literal captures 4 words, but a function value holds at most 3
    captured: a (s32, 1 word), b (fixed, 1 word), c (bool, 1 word), d (u8, 1 word)
    note: pass the extra values as arguments, or capture one pointer to a struct that holds them
  ```

- **Not capturable:** vectors, structs, arrays and matrices (copy the lanes or fields you need
  into locals first, and use those, or capture a pointer), and function values (4 words each:
  pass them as arguments or keep them in a global).
- **Nested literals** capture through each level: an inner literal that uses a local of the
  outermost function makes the middle literal capture it too (and count it against its 3 words).
- **Pointers** may be captured, at your own risk: the pointer is copied, not what it points
  to. When the compiler can see that a captured pointer holds the address of a local variable
  (`&local`, `&arr[i]`, or a local array passed as a pointer) it reports an error, because the
  function value could be called after that variable is gone. This is not checked when the
  literal is passed straight to `map`/`filter`/`reduce`/`each` or called on the spot (it cannot
  outlive the function then), and it is best effort: a pointer received as a parameter, or
  stored in a global, is not tracked.

## Built-in functions

These are compiled inline (no call) and work on several types:

| Function | Meaning |
|---|---|
| `vec2(x, y)`, `vec3(x, y, z)`, `vec4(x, y, z, w)`, `vec4(v3, w)`, `ivec4(a, b, c, d)` | constructors; constant arguments give a constant vector |
| `dot(a, b)`, `cross(a, b)` | `vdot`, `vcross` |
| `length(v)` | `sqrt(dot(v, v))` (calls `sqrt`) |
| `normalize(v)` | `v / length(v)` (calls `normalize4`); zero vectors stay zero |
| `abs(x)`, `min(a, b)`, `max(a, b)`, `clamp(x, lo, hi)` | integers or `fixed`, branch-free |
| `lerp(a, b, t)` | `a + (b - a) * t` for `fixed` or vectors (`t` is `fixed`) |
| `nclip(p0, p1, p2) -> s32` | twice the signed area of a screen triangle; negative when counter-clockwise on screen (front-facing). Arguments are packed positions `(x & 0xFFFF) \| (y << 16)` |
| `otz(bias, depth, scale) -> s32` | ordering-table bucket: `bias + floor(depth * scale)`, clamped to 0..1023 (`depth`, `scale` are `fixed`) |
| `clerp(from, to, t) -> u32` | blend two colours (each of the four bytes) by `t` (`fixed`, clamped to 0..1, rounded down) |
| `len(x)` | element count of an array or embedded asset (a constant) |
| `sizeof(T)` | size of a type in bytes (a constant) |
| `bits(f)`, `from_bits(n)` | reinterpret `fixed` ↔ `s32` |
| `T(x)` | conversion, same as `x as T` |

`length`, `normalize` and the dot product overflow for vectors longer than about 181.

`nclip`, `otz` and `clerp` are single instructions (see `DECISIONS.md`, "Geometry
instructions"). The fourth, `vxp3` (transform and project three vertices), works on three
vector registers at once and is used from `asm` blocks (`tests/lang/geometry.akr` has an example).

## map, filter, reduce, each

These generic built-ins work on arrays of any element type, or on a pointer plus a count.
Each compiles to an inline loop with one `call` per element (or `callr` when the function is
a value that is only known at run time). A literal written in place may capture locals
(`filter(xs, fn(x) => x > k)`): its captured words are copied once before the loop and kept in
registers, and each element is a direct `call`. The optional trailing `count` limits the loop to the
first `count` elements (it is required when the sequence is a pointer).

| Form | Meaning |
|---|---|
| `map(xs, f) -> [N]U` | a new array with `f(x)` for each element of the `[N]T` array `xs`; `f: fn(T) -> U` |
| `map_into(out, xs, f [, count])` | `out[i] = f(xs[i])`; `out` may be `xs` itself (in place) |
| `filter(xs, keep [, count]) -> s32` | keeps the elements for which `keep(x)` is true, moving them to the front of `xs` in order; returns how many remain |
| `filter_into(out, xs, keep [, count]) -> s32` | copies the kept elements to `out`; returns how many |
| `reduce(xs, init, f [, count]) -> A` | `acc = init; acc = f(acc, x)` for each element; `A` is a scalar or vector type |
| `each(xs, f [, count])` | calls `f(x)`, or `f(&x)` when `f` takes a `*T` (to modify elements in place) |

```
var parts: [96]Particle
var count = 0

fn step(p: *Particle) { p.pos = p.pos + p.vel; p.life -= 1 }

fn update() {
    each(parts, step, count)                                  // update in place
    count = filter(parts, fn(p) => p.life > 0, count)         // drop the dead ones
    let total = reduce(parts, 0, fn(a: s32, p: Particle) => a + p.life, count)
    let squares = map([1, 2, 3, 4], fn(x) => x * x)           // [4]s32
}
```

Struct elements are passed to `f` by reference and struct results are written straight into
the destination. The output of `map_into`/`filter_into` must be at least as long as the input
when both are arrays and no count is given. Over 100 `s32` elements a `map_into` whose function
is `x * 2` costs about 1,410 cycles (14 per element: load, `call`, the 3-cycle function, store
and loop) for a named function or a literal; through a function value it costs 3 cycles more
per element (1,710), plus 2 per captured word for a closure. `filter(xs, fn(x) => x > k)` over
100 elements costs about 1,670 cycles.

## Memory

| Where | What |
|---|---|
| ROM (`0x200000`) | code, `const` arrays/structs, strings, embedded files, vector constants |
| RAM from `0x000100` | global variables (small ones first, so most are one instruction away) |
| RAM below `0x200000` | the stack (grows down): locals that are not in registers, spills, call frames |

`len()` and `sizeof()` describe sizes; there is no bounds checking at run time (constant
indexes are checked at compile time). Recursion is allowed; there is no stack-overflow check,
so very deep recursion runs into the globals. ROM data is read-only: writing through a pointer
into ROM faults.

Locals whose address is never taken live in registers when possible: the compiler numbers
statements, gives each local a live range, and shares registers between locals whose ranges
do not overlap. Locals that are live across a call use `r9`–`r13`; others may also use
`r1`–`r4`. Vector locals stay in vector registers unless they are live across a call (vector
registers are not preserved). Everything else (structs, arrays, matrices, address-taken
variables, overflow) lives in the stack frame.

## Assembly

**asm functions** contain only assembly and follow the [calling convention](#calling-convention):

```
asm fn add3(a: s32, b: s32, c: s32) -> s32 {
    add r1, {a}, {b}        ; {a} is r1, {b} r2, {c} r3
    add r1, r1, {c}
}                           ; the compiler appends `ret`
```

**Inline asm blocks** sit among statements:

```
var x = 5
var y = 0
asm {
    shli {y}, {x}, 3        ; y = x * 8
    lw   r5, [r0+{counter}] ; a global: its label
    addi r5, r5, {STEP}     ; a constant: its value
    call {helper}           ; a function: its label
}
```

Inside both forms, `{name}` is replaced by:

- a parameter or local: its register (`r9`, `v2`, ...). Locals named in an `asm` block are
  always kept in registers (callee-saved ones for scalars); only scalar, pointer and vector
  locals can be named;
- a global variable, `const` array, string constant or embedded asset: its label (globals
  below `0x20000` work as absolute operands: `[r0+{name}]`);
- a constant: its value; a register declared with `reg`: its address;
- a function: its label.

Rules: an asm block may freely use `r1`–`r8`, `r15` (after saving it) and `v0`–`v7`, except
registers it names through `{...}`; it must preserve `r9`–`r13` and `sp` unless it names them.
Local labels (`.loop:`) work but must not start with `.L` (the compiler's own labels). asm
functions may use local labels freely and must `ret` (the compiler adds a final `ret`). Errors
in assembly are reported at the asm line in the `.akr` file. See `ASSEMBLY.md` for the syntax.

## Calling convention

| Registers | Use |
|---|---|
| `r1`–`r4` | the first four scalar arguments (integers, `fixed`, `bool`, pointers); `r1` holds a scalar result |
| `v0`–`v3` | the first four vector arguments; `v0` holds a vector result |
| `r5`–`r8` | temporaries, not preserved |
| `r9`–`r13` | preserved by the callee |
| `r14` (`sp`) | stack pointer, word aligned |
| `r15` (`ra`) | return address |
| `v0`–`v7` | not preserved |

Scalar and vector arguments are numbered separately, in parameter order. Further arguments go
on the stack: the caller stores them at `[sp+0]`, `[sp+4]`, ... in parameter order (4 bytes for
a scalar, 16 for a vector) before the `call`; the callee finds them at `[sp + frame size + 0]`
and so on.

Structs, arrays and matrices are passed **by reference**: the argument is a pointer to the
caller's value (it takes a scalar argument slot), and the callee may not modify it (pass a
pointer type such as `*Player` to modify a caller's struct). A function that returns a struct,
array or matrix receives a hidden pointer to the result in `r1`, ahead of the other arguments,
and copies the value there.

Frames: the callee lowers `sp` once in its prologue, saves `ra` (if it makes calls) and the
callee-saved registers it uses at the top of its frame, and restores them before `ret`.

**Function values** (16 bytes: code, c1, c2, c3) are passed and returned like vectors (in
`v0`–`v3`, result in `v0`). A call through a value puts the code address in `r5` and the
**address of the 16-byte value** in `r6`, then does `callr r5`; the arguments are as for a
direct call. Functions that capture nothing ignore `r6`, so calling a plain function through a
value costs only the `lw` of the code address and an `addi` (3 cycles more than a direct
`call`). The code address of a capturing literal is a short entry stub in front of it that
loads the captured words into `r6`–`r8` and falls into the body:

```
FL3$v:                ; the address stored in the function value
    lw r7, [r6+8]     ; second captured word (if any)
    lw r6, [r6+4]     ; first captured word
FL3:                  ; the body finds its captures in r6-r8
```

A literal that the compiler can call directly (one passed in place to `map`/`filter`/...)
skips the stub: its captured words are put straight into `r6`–`r8` and it is called with
`call FL3`. Captured words cost 2 cycles each per call through a value (the stub's loads), and
nothing extra in the body unless it makes calls (then they move to callee-saved registers).
A function value in a vector register is first stored to the stack (3 cycles more).

## Standard library

The prelude (`stdlib/prelude.akr`) imports every module below. Colours are `u32` words
`0xBBGGRR` (red in the low byte, as the GPU expects); `rgb(r, g, b)` builds one.

### Frame and system (`runtime.akr`, `io.akr`)

| | |
|---|---|
| `cpu_used() -> s32` | cycles used by the previous frame (of 500,000); a frame that ran over counts every budget it used up, so it reads above 500,000 |
| `frames_dropped() -> s32` | how many budgets the previous frame ran over by: 0 when it was on time, n when the picture before it stayed up n more times |
| `cycle_count() -> s32` | a cycle clock that keeps counting across frames and overruns (`FRAME × 500,000 − CYCLES`); differences between readings are exact for spans under 71 seconds |
| `tris_drawn() -> s32` | 3D triangles drawn in the previous frame |
| `frame() -> u32` | frames since reset |
| `vsync()` | end the frame now (low level: skips the ordering table and pad bookkeeping) |
| registers | `GPU_DRAW GPU_CLEAR GPU_CTRL GPU_STATUS GPU_BACK PAD1 PAD2 STICK1_X STICK1_Y STICK2_X STICK2_Y FRAME CYCLES RAND DEBUG` |
| constants | `AUDIO_BASE VRAM_PALETTE VRAM_TEXTURES TEXTURE_SLOT_SIZE SCREEN_W SCREEN_H` |

### Input (`input.akr`)

Buttons are bit masks: `UP DOWN LEFT RIGHT A B X Y L R START SELECT`.

| | |
|---|---|
| `btn(b: u32) -> bool` | any of the buttons in `b` is held (controller 1) |
| `btnp(b: u32) -> bool` | pressed this frame: held now, not held on the previous frame |
| `btn2`, `btnp2` | the same for controller 2 |
| `stick() -> vec2`, `stick2() -> vec2` | analog stick, −1.0..1.0 on each axis (y up), dead zone applied |

### Maths (`math.akr`)

| | |
|---|---|
| `sin(a)`, `cos(a)`, `tan(a)` | radians; 1,024-entry table with interpolation |
| `atan2(y, x)` | radians, −π..π, error under 0.005 |
| `sqrt(x)` | exact to the last bit; 0 for x ≤ 0 |
| `rand() -> u32`, `seed(s)`, `rnd(n) -> s32` (0..n−1), `rndf() -> fixed` (0..1) | the hardware generator |
| `PI`, `TAU`, `HALF_PI` | constants |
| `mat4_identity()`, `mat4_translate(v)`, `mat4_scale(v)`, `mat4_rotate_x/y/z(a)`, `mat4_mul(a, b)` | matrices (rows are `vec4`) |

`mat4_rotate_y(a)` turns +Z toward +X (the same sense as camera yaw), `mat4_rotate_x(a)` turns +Z
toward +Y, `mat4_rotate_z(a)` turns +X toward +Y.

### Graphics (`gfx.akr`, `text.akr`)

**Coordinates.** World space has +X right, +Y up and +Z forward. The camera looks along +Z at
yaw 0; positive yaw turns right (toward +X), positive pitch looks up.

| | |
|---|---|
| `cls(colour)` | clear the back buffer now |
| `rgb(r, g, b) -> u32`, `rgb15(colour) -> u32` | build a colour; convert to the 15-bit framebuffer format |
| `dither(on: bool)` | ordered dither (on by default) |
| `camera(pos: vec3, yaw)` | set the view (no pitch) |
| `camera_look(pos: vec3, yaw, pitch)` | set the view with pitch |
| `camera_fov(fov)` | vertical field of view in radians (default 1.047, 60°); the 4:3 aspect is built in |
| `camera_clip(near, far)` | near plane (default 0.1; geometry closer than it is clipped away) and the depth that maps to the farthest ordering-table bucket (default 100) |
| `camera_matrix(m: mat4)` | use your own view-projection matrix (row 3 must produce view depth in w) |
| `mesh(m: *Mesh)` | draw a mesh whose vertices are in world space |
| `mesh_at(m: *Mesh, pos: vec3, yaw)` | draw a mesh placed at `pos`, turned by `yaw` |
| `mesh_xf(m: *Mesh, model: mat4)` | draw a mesh with a model matrix |
| `fog(colour, near, far)`, `fog_off()` | blend vertex colours toward `colour` between view depths `near` and `far` |
| `depth_bias(buckets)` | shift the ordering-table bucket of following `mesh*()` polygons (negative: drawn later, in front); reset each frame |
| `depth_key(w, squash)`, `depth_key_off()` | sort the faces of following `mesh*()` calls around view depth `w`: their own order kept, `squash` times closer to `w` (a sort key per mesh; see below); reset each frame |
| `depth_bucket_of(w) -> s32` | the ordering-table bucket of view depth `w` (for `FACE_KEYED` faces) |
| `cull_rect(x0, y0, x1, y1)` | the screen rectangle outside which faces that must be clipped are dropped (default the screen; see the guard band below) |
| `subdivide(levels)` | split big textured faces near the camera, up to `levels` times (0 = off, the default; at most 3); see below |
| `subdivide_tuning(percent, distance)` | how much deeper the far end of an edge may be than its near end before `subdivide()` splits it (default 25 %; smaller is straighter and costs more), and the view depth beyond which nothing is split (default 8.0) |
| `text(x, y, s: *u8, colour)` | 8×8 font, ASCII 32–126; `\n` starts a new line |
| `text_int(x, y, n, colour) -> s32` | draw a number; returns the x after it |
| `int_to_str(buf: *u8, n) -> *u8` | format a number (buf needs 12 bytes) |
| `sprite(slot, palette, four_bit: bool, u, v, w, h, x, y)` | draw a w×h texel rectangle of a texture at (x, y), untinted |
| `rect(x, y, w, h, colour)` | a filled rectangle |
| `load_texture(slot, src: *u8, bytes)` | copy texture data (in the GPU's layout, spec p. 11) into a slot |
| `load_palette(index, src: *u16, count)` | copy 15-bit colours into palette memory from colour `index` |

`mesh*()` transform vertices with the vector unit, clip faces that cross the near plane (and
drop those wholly behind it), cull back faces (front faces are counter-clockwise on screen), fog vertex colours,
build packets into a per-frame packet arena (160 KB) and insert them into the 1,024-bucket
ordering table by average view depth. At the end of the frame the table is drawn farthest
bucket first, then the **interface list** (text, sprites, rectangles) in call order on top.
When the arena is full, further polygons are dropped.

**Near plane.** A face with some corners closer than the near plane (`camera_clip`) and some
beyond it, such as a wall or pillar the camera stands beside or the floor under it, is clipped
to the plane in clip space, so the part in front of the camera is drawn (`stdlib/clip.akr`,
with the guard-band clipping below). Faces sharing an edge across the plane clip it at the
same point, so no cracks open. A face wholly behind the plane is dropped, and so is a crossing
face that lies wholly beyond one side of the view or faces away. The camera itself should
still keep a little more than the near distance away from walls it looks at: geometry nearer
than the near plane is cut away, so a wall closer than that shows what is behind it.

**Guard band.** `vproj` clamps screen coordinates to −1024..1023 (spec p. 9), so a vertex that
projects further out, typically a corner of a big floor or wall polygon right beside or below
the camera, would be moved, bending the polygon's edges and texture as the camera turns and
sometimes flipping its winding so that it is culled. `mesh*()` therefore clip any face with a
vertex outside the guard band (screen x and y in −1000..999) against the edges of that band
in clip space before culling it, with texture coordinates and colours interpolated along the
3D edges (`stdlib/clip.akr`). The visible part is drawn where it belongs; faces sharing a
clipped edge clip it identically, so no cracks open. Faces wholly off one side of the screen
are dropped. Only geometry is corrected: the pieces are still mapped affinely.

A cart that keeps the packets of a `mesh()` pass and shifts them on screen later (a panned view
drawn from a cache) calls `cull_rect()` with the screen widened by the most it will shift them
while it builds that pass: a face to be clipped is dropped only when it lies wholly beyond that
rectangle, so the part that is panned into view later is there. Faces that need no clipping are
never dropped for lying off the screen.

**Sort keys.** Each face is sorted by its own average view depth, which is right for a scene of
small faces around a moving camera. When the painter's order is known instead, such as a grid
seen from a fixed angle where things should be drawn by where they stand on the floor (height
reads as nearness from above, so a tall wall's middle sorts in front of what stands against it),
two keys are available. `depth_key(w, squash)` sorts a whole `mesh*()` call around view depth `w`
(for example the middle of an object's footprint on the floor): its faces keep their order among
themselves, `squash` times closer to `w`, so an object no longer interleaves with its neighbours.
A face with the `FACE_KEYED` flag (32) goes into the bucket its `col[3]` holds
(`depth_bucket_of(w)`, plus `depth_bias`), whatever its depth: a key per face, for example the
middle of a wall's base. Keyed faces must not be Gouraud (`col[3]` is not a colour then); faces
in one bucket draw in the reverse of the order they were made (the last one made first), and
the pieces clipping or `subdivide()` makes of a keyed face keep its key.

**Subdivision.** Textures are mapped affinely, so a big polygon that spans a wide range of
depth warps, and it swims as the camera moves (the PlayStation's look; whole-pixel vertex
snapping adds a wobble of its own). PlayStation games tamed it near the camera by splitting
polygons, and `subdivide(levels)` does the same for the following `mesh*()` calls (it stays
set until changed, like `fog`). A textured face is considered when its nearest vertex is
nearer than the subdivision distance and its depth spreads by more than the tolerance, or
when it crosses the near plane; faces that are back-facing or entirely off screen are
skipped. Each edge of such a face is split when its far end is deeper than its near end by
more than the tolerance (the affine error grows with that ratio); edges crossing the near
plane are split once, and pieces that still cross it are clipped like any face. A quad whose
opposite edges both split is cut in two along them (so texture lines parallel to its edges,
such as bricks and tiles, stay straight); any other quad continues as its two triangles, which
split into four or are bisected one edge at a time, up to `levels` halvings per edge.
Midpoints are made in object space and transformed exactly, with averaged texture
coordinates and colours. The decision for an edge depends only on its two ends and on how
often it has been halved, so the faces sharing an edge always split it alike and no cracks
open between them, whatever their own pattern. The pieces are culled, fogged, sorted and
drawn like any face, and count against the 2,000-triangle limit. Untextured faces are never
split. Splitting is not free (see Performance notes): a cart can enable it only for the
meshes that need it, raise the tolerance, or adjust it from frame to frame from `cpu_used()`
(Sun & Moon Orbs does)
(keep the settings the same for all the meshes of a frame that share edges, or they may
disagree about a shared edge).

The fonts occupy texture slot 15 (the 8×8 font rows 0–47, `font_small()` rows 48–66) and 4-bit
palette 255 (colours 4080–4095); carts should not use them.

For hand-built packets: `packet_alloc(words) -> *u32` (null when full), `ot_insert(p, type,
depth)` (depth 0 nearest .. 1023), `ui_insert(p, type)`. Word 0 of a packet is filled in by the
insert; write the rest as described in the spec (p. 14–16). The packet types are named
`PKT_TRI`, `PKT_TRI_GOURAUD`, `PKT_TRI_TEX`, `PKT_TRI_TEX_GOURAUD`, `PKT_QUAD_FLAT`,
`PKT_QUAD_GOURAUD`, `PKT_QUAD_TEX`, `PKT_QUAD_TEX_GOURAUD` (0x20–0x27), or built from `PKT_POLY`
(0x20) and the flag bits `PKT_GOURAUD`, `PKT_TEXTURED`, `PKT_QUAD`, `PKT_SEMI`; a semi-transparent
packet's blend mode goes in bits 24–25 of its first colour (`mode << BLEND_SHIFT`), and
`TEX_4BIT` is the 4-bit flag of the first texture coordinate.

### Projection, the ordering table and packet memory (`render.akr`)

What `mesh()` does with the camera, the ordering table and the packet arena, available to carts
that place 2D things in the 3D world, draw parts of the world early, or keep packets across
frames.

| | |
|---|---|
| `project_point(p: vec3) -> ivec4` | where `mesh()` would put a vertex at `p` (`vxfm` and `vproj`, the same rounding): lanes `x`, `y` in pixels, `z` the ordering-table bucket of its view depth (without `depth_bias`; −1 when `p` is nearer than the near plane or behind the camera, and then `x`, `y` mean nothing), `w` the view depth as raw bits (`from_bits(r.w)`) |
| `view_depth(p: vec3) -> fixed` | the view depth of `p` |
| `depth_bucket_of(w) -> s32` | the bucket of view depth `w` (see Sort keys) |
| `buckets_per_unit() -> fixed` | buckets per unit of view depth, `1024 / (far − near)` |
| `camera_focal(f)` | the projection's scale: `f = 1 / tan(fov / 2)` (`camera_fov` sets it from an angle); a point at view depth `d` is `120 × f / d` pixels per unit tall. Applies from the next `camera()`/`camera_look()` |
| `camera_pan(px, py)` | shift the view by whole pixels (right, down) without moving the camera (an off-axis view); every vertex moves by exactly `(px, py)`. After `camera()`/`camera_look()`, which reset it |
| `ot_clear()` | empty the frame's ordering table |
| `ot_save(buf: *u32)`, `ot_restore(buf)` | copy the frame's table (1,024 words) out and back |
| `ot_swap(buf)` | exchange the frame's table with `buf` (about 4,900 cycles) |
| `ot_detach(dst, home)` | move the frame's table to `dst` as a list of its own, linked to end at `home`'s entries (usually `dst`), and empty the frame's table |
| `ot_draw(table) -> s32` | draw a detached table now; returns the triangles drawn |
| `ot_flush() -> s32` | draw the frame's table now and empty it (what is sorted later draws over it) |
| `ui_flush()` | draw the interface list queued so far now (3D drawn later lands on top) |
| `arena_init(a: *PacketArena, buf: *u32, words)`, `arena_swap(a)` | a packet arena of the cart's own; `arena_swap` exchanges it with the current one |
| `arena_used() -> s32`, `arena_left() -> s32` | words of the frame's arena used this frame; words left in the current arena |

The ordering table is 1,024 empty packets, entry `b` linking to entry `b − 1`; a packet sorted
into bucket `b` links on to what the bucket held, so the last packet of each bucket's chain links
to the entry below. A copy of the table (`ot_save`, `ot_swap`) therefore still links into the
frame's table, and is only drawn correctly once it is put back (`ot_restore`, `ot_swap` again);
`ot_detach` rewrites those last links (about 26,000 cycles for the buckets plus 15 a packet) to
make a list that can be drawn from wherever it lives with `ot_draw`. The frame's table is set up
at the start of each frame, after `init()`: call `ot_clear()` before using it in `init()`.

The packets themselves live in the frame's arena, which is emptied at the start of every frame.
To keep geometry across frames (a static scene built once, or a few steps per frame, then drawn
again and again), make its packets in an arena of the cart's own and keep its table:

```
var cache: [40960]u32
var cache_ot: [1024]u32
var cache_arena: PacketArena

fn build_scene() {                 // once, or whenever the scene changes
    arena_init(&cache_arena, &cache[0], 40960)
    ot_swap(&cache_ot[0])          // sort into an empty table of our own...
    ot_clear()
    arena_swap(&cache_arena)       // ...with packets that outlive the frame
    mesh(TOWN)
    arena_swap(&cache_arena)       // cache_arena.ptr: where its packets end
    ot_swap(&cache_ot[0])          // the frame's table back; cache_ot holds the scene
}

fn draw() {
    ot_restore(&cache_ot[0])       // the scene, then this frame's moving parts on top of it
    mesh_at(CART, cart_pos, cart_yaw)
}
```

Building over several frames works the same way: swap the arena and table in at the start of
each step and out at the end (a task, below, can hold the loop). The packets of `ot_restore`d
tables are linked into by the frame's own inserts, so a table restored every frame must be
restored from the saved copy each time (it is: `ot_restore` copies).

### 2D drawing (`draw.akr`)

More shapes for the interface list, drawn like `rect()`, `sprite()` and `text()`: after the 3D
world, in call order. Positions are whole pixels; a rectangle `(x, y, w, h)` covers `x .. x+w−1`
and `y .. y+h−1`. Colours are `0xBBGGRR`. A `mode` is a blend mode:

| `mode` | Result |
|---|---|
| `BLEND_NONE` (−1) | opaque |
| `BLEND_HALF` (0) | half the background + half the shape (glass, water) |
| `BLEND_ADD` (1) | background + shape (glows) |
| `BLEND_SUB` (2) | background − shape (shadows, darkening a panel's backdrop) |
| `BLEND_QUARTER` (3) | background + a quarter of the shape (faint glows) |

| | |
|---|---|
| `rect_blend(x, y, w, h, colour, mode)` | a filled rectangle |
| `rect_grad(x, y, w, h, top, bottom, mode)` | a vertical gradient |
| `rect_hgrad(x, y, w, h, left, right, mode)` | a horizontal gradient |
| `rect_grad4(x, y, w, h, tl, tr, bl, br, mode)` | a colour per corner |
| `rect_outline(x, y, w, h, colour, mode)` | a one-pixel frame just inside the rectangle |
| `line(x0, y0, x1, y1, colour)` | a one-pixel line; the end point is not drawn (like a rectangle's far edges), so joined lines don't overlap |
| `line_ex(x0, y0, x1, y1, width, c0, c1, mode)` | a line `width` pixels thick (thickened down for flat lines, right for steep ones), shaded from `c0` to `c1` |
| `tri_fill(x0, y0, x1, y1, x2, y2, colour, mode)` | a filled triangle (either winding) |
| `tri_grad(x0, y0, x1, y1, x2, y2, c0, c1, c2, mode)` | a Gouraud-shaded triangle |
| `quad_fill(x0, y0, x1, y1, x2, y2, x3, y3, colour, mode)` | a quad in strip order (0-1-2, 1-2-3: top-left, top-right, bottom-left, bottom-right) |
| `tex_page(slot, palette, four_bit) -> u32` | the texture page of the sprite functions: slot, palette and depth |
| `sprite_ex(page, u, v, tw, th, x, y, w, h, tint, mode)` | the texels `(u, v, tw, th)` stretched over `(x, y, w, h)`; a negative `tw` or `th` mirrors that axis |
| `sprite_rot(page, u, v, tw, th, cx, cy, w, h, angle, tint, mode)` | the same `w × h`, centred on `(cx, cy)` and turned clockwise by `angle` radians |
| `sprite_quad(page, u, v, tw, th, xs: *s32, ys: *s32, tint, mode)` | on four free corners (`xs[k]`, `ys[k]`: top-left, top-right, bottom-left, bottom-right of the texels) |
| `col_tint(colour) -> u32` | the tint that shows a white texel in `colour` (half of it, rounded up: `col_tint(0xFFFFFF)` is `0x808080`) |

A sprite's `tint` multiplies its texels by `tint / 128` per channel: `0x808080` draws the texture
as it is, `0xFFFFFF` twice as bright (clamped), `col_tint(c)` in colour `c` when the texels are
white. Texture coordinates are 8 bits, so `u + tw` and `v + th` are clamped to 255. Mirroring is
exact at 1:1; scaled up, the GPU's rounding leaves the first texel of a mirrored axis one pixel
wide, so large mirrored sprites are better mirrored in the texture.

```
let ui = tex_page(3, 40, true)                          // slot 3, 4-bit, palette 40
rect_grad(0, 200, 320, 40, rgb(36, 44, 96), rgb(14, 16, 40), BLEND_HALF)   // a glassy panel
rect_blend(8, 206, 80, 1, rgb(150, 170, 230), BLEND_NONE)                // its top edge
sprite_ex(ui, 0, 0, 16, 16, 8, 210, 32, 32, 0x808080, BLEND_NONE)       // an icon at 2x
sprite_ex(ui, 64, 192, 16, 16, cx - r, cy - r, 2 * r, 2 * r, rgb(255, 220, 110), BLEND_ADD)  // a glow
line_ex(10, 20, 90, 60, 2, rgb(60, 70, 110), rgb(200, 200, 120), BLEND_ADD)
```

Each call builds one packet (two triangles for the rectangles, quads, lines and sprites; one for
the triangles) and makes no other calls; when the packet arena is full it draws nothing.

### Proportional text (`font.akr`)

Besides the 8×8 `text()`, the library draws proportional fonts. The built-in one,
`font_small()`, is a pixel font with 7-pixel capitals, 2-pixel descenders and a 10-pixel line
(ASCII 32–126). It lives in texture slot 15 below the 8×8 font (rows 48–66, palette 255, both
reserved) and is copied there the first time it is used.

| | |
|---|---|
| `font_text(x, y, s, colour) -> s32` | draws `s` with the top-left of its first glyph at `(x, y)`; `\n` starts a new line. Returns the x after the last character |
| `font_text_align(x, y, s, colour, align) -> s32` | each line `ALIGN_LEFT` (from x), `ALIGN_CENTRE` (centred on x) or `ALIGN_RIGHT` (ending at x) |
| `text_width(s) -> s32` | the width of `s`: the sum of its characters' advances (the longest line) |
| `font_line() -> s32` | the line advance |
| `font_shadow(colour)`, `font_shadow_off()` | draw a 1-pixel drop shadow under the following text |
| `font_use(f: *Font)` | the font of the following calls (`null`: `font_small()`) |
| `font_load(f: *Font)` | copy a font's atlas and palette to VRAM, when its blob holds them |
| `font_small() -> *Font` | the built-in font |

The colour works as for `text()` (the tint `col_tint(colour)`; white shows the font's ink as it
is). Characters the font lacks are skipped. A glyph costs about 45 cycles (the 8×8 `text()`:
about 105), `text_width` about 30 cycles a character.

**Fonts of your own** come from `tools/meifont.py`, which bakes a TrueType font (antialiased,
optionally with a drop shadow baked in) or a pixel font into a blob: the glyph metrics and,
unless `--no-texels`, the atlas rows and palette, for a given texture slot, first row and
palette. Embed it and load it once:

```
// python3 tools/meifont.py --ttf Georgia.ttf --size 15 --shadow --slot 3 --palette 40 -o title.fnt
embed TITLE: Font = "title.fnt"

fn init() { font_load(TITLE) }

fn draw() {
    font_use(TITLE)
    font_text_align(160, 30, "Lantern Lake", rgb(255, 220, 140), ALIGN_CENTRE)
    font_use(null)                                   // back to font_small()
}
```

The blob is a `Font` header (`height`, `line`, `first`, `count`, `slot`, `palette`, `row`, `rows`,
`colours: [16]u16`) followed by a word per glyph (`u | v << 8 | w << 16 | advance << 24`) and
`rows × 128` bytes of 4-bit texels; `tools/meifont.py` describes it, and its `--akr NAME` option
writes it as an Akari `const` array instead (as `stdlib/font_small.akr` is made). A font atlas can
also share a texture with other art: bake it with `--no-texels` at the rows the cart loads it to.

### Colours and animation phases (`colour.akr`)

| | |
|---|---|
| `col_mix(a, b, t) -> u32` | blend two colours, `t` 0 (a) .. 1.0 (b), clamped; each channel rounds down (one `clerp`) |
| `col_scale(c, t) -> u32` | each channel times `t` (0..1.0) |
| `col_add(a, b) -> u32` | channel sums, clamped at 255 |
| `rgb_of15(c) -> u32` | the 24-bit colour of a 15-bit palette or framebuffer colour (`rgb15` is the reverse) |
| `palette_lerp(index, a: *u16, b: *u16, count, t)` | write `count` palette colours from colour `index` on, each `a[i]` blended toward `b[i]` by `t` (15-bit colours, e.g. two keyframe palettes in ROM); about 38 cycles a colour |
| `palette_rotate(index, count, step)` | rotate `count` palette colours in place: colour `index + i` gets what `index + (i + step) mod count` held (colour cycling); about 14 cycles a colour |
| `frame_phase(t, period) -> fixed` | how far through a cycle of `period` frames the count `t` is: 0 up to 1.0 |
| `frame_wave(t, period) -> fixed` | `sin(TAU * frame_phase(t, period))`, −1.0..1.0 |
| `frame_angle(t, speed) -> fixed` | `t × speed` (radians per frame) reduced to 0..TAU, exactly |

`fixed(frame_count) * speed` stops working after 32,768 frames (about nine minutes): the count
overflows `fixed` and every animation driven by it jumps. The `frame_*` functions take the count
itself, `frame() as s32` or a cart's own tick counter (one that stops while paused, say), and are
exact for any count, so `sin(frame_angle(tick, 0.05))` keeps turning smoothly for as long as the
cart runs. `frame_angle` costs about 150 cycles (five remainders), `frame_phase` about 70.

### Strings (`str.akr`)

Strings are NUL-terminated bytes. The `str_append*` functions add to the string already in a
buffer of `cap` bytes (the NUL included), never write past it (the text is cut short instead),
and return the buffer, so calls nest or chain:

| | |
|---|---|
| `strlen(s) -> s32`, `streq(a, b) -> bool` | length; same bytes |
| `str_copy(dst, cap, s) -> *u8` | replace the buffer's string with `s` |
| `str_append(dst, cap, s) -> *u8`, `str_append_char(dst, cap, c) -> *u8` | |
| `str_append_int(dst, cap, n, width, zero_pad) -> *u8` | `n` right-aligned in at least `width` characters, padded with `'0'` after the sign (`-007`) or with spaces (`  -7`) |
| `str_append_fixed(dst, cap, f, decimals) -> *u8` | `f` rounded to 0–4 decimals, halves away from zero (`3.14`, `2.0`) |
| `str_append_time(dst, cap, n) -> *u8` | `n / 60`, a colon and `n % 60` in two digits: seconds as m:ss (`125` → `2:05`), minutes as h:mm (`605` → `10:05`) |

```
var buf: [32]u8
let b = &buf[0]
str_copy(b, 32, "Day ")
str_append_int(b, 32, day, 0, false)
font_text_align(312, 8, str_append_time(str_copy(b, 32, ""), 32, minutes), CREAM, ALIGN_RIGHT)
```

### Tasks (`task.akr`)

Work too big for one frame (rebuilding a cached scene, path finding, generating a level) can
run as a **task**: a function with a stack of its own that runs for a while each frame and keeps
its place between frames, locals, loops and calls in progress included, instead of a
hand-written state machine.

| | |
|---|---|
| `task_start(t: *Task, stack: *u8, size, body: fn())` | prepare `t` to run `body` on `size` bytes at `stack`; it does not run yet. Starting it again abandons what it was doing |
| `task_resume(t) -> bool` | run `t` until it yields (true) or its function returns (false); false at once unless it is ready |
| `task_yield()` | inside a task: suspend it and return from the `task_resume` that ran it. Outside a task it does nothing |
| `task_time() -> s32` | cycles since the running task was last resumed (0 outside one) |
| `task_done(t) -> bool`, `task_current() -> *Task` | its function has returned; the task running now (or null) |

`t.state` is `TASK_IDLE`, `TASK_READY` (started or suspended), `TASK_RUNNING` or `TASK_DONE`.

```
var builder: Task
var builder_stack: [4096]u8

fn rebuild() {                                   // written as if it had the CPU to itself
    for g in 0..floors {
        for i in 0..n_objects(g) {
            bake_object(g, i)
            if task_time() > 60000 { task_yield() }    // the rest next frame
        }
    }
}

fn update() {
    if dirty {
        task_start(&builder, &builder_stack[0], 4096, rebuild)
        dirty = false
    }
    task_resume(&builder)                        // false (and does nothing) once it is done
}
```

`body` may be a closure (a function literal with captures); a task may resume other tasks, and
`task_yield()` always suspends the innermost one. A switch is an ordinary call as far as the
code around it is concerned: it saves and restores only what the calling convention preserves
(`r9`–`r13`, `sp`, `ra`), so a resume and the yield back cost about 125 cycles together. The
stack must hold the deepest calls the task makes, with their locals (`mesh()` with clipping, fog
and `subdivide(3)` uses about 320 bytes; 1–2 KB is comfortable for most work). A guard word at
the bottom of the stack is checked whenever the task yields or returns: a task that ran over it
halts the cart with "task stack overflow" (by then it may have overwritten the memory below its
stack, so leave room).

### Sound (`audio.akr`)

Sixteen channels (0–15) of mono samples at 22,050 Hz, in 8-bit, 16-bit or 4-bit ADPCM, and a
global reverb. `len` and `loop_start` count samples; volumes are 0–255; `pitch` 1.0 plays at
22,050 Hz (ADPCM channels go up to 16.0). The hardware is described in `DECISIONS.md`
("Audio upgrade").

| | |
|---|---|
| `play(ch, sample: *s8, len: u32, pitch, vol_l, vol_r, looping: bool)` | 8-bit samples |
| `play16(ch, sample: *s16, ...)` | 16-bit samples |
| `play_adpcm(ch, data: *u8, ...)` | Mei ADPCM blocks (16 bytes per 28 samples) |
| `play_sample(ch, data: *u8, len, loop_start, pitch, vol_l, vol_r, flags: u32)` | any format, with a loop start and the reverb send: `flags` combines `SND_16BIT` or `SND_ADPCM` (neither: 8-bit) with `SND_LOOP` and `SND_REVERB` |
| `adpcm_samples(bytes) -> u32` | samples in an ADPCM asset of that many bytes (`bytes / 16 * 28`) |
| `stop(ch)`, `sound_playing(ch) -> bool`, `sound_pos(ch) -> u32` | |
| `sound_vol(ch, vol_l, vol_r)`, `sound_pitch(ch, pitch)` | change a playing channel |
| `sound_loop(ch, on: bool)` | turn looping on or off without restarting (off: it plays to its end) |
| `sound_active() -> u32`, `sound_free(lo, hi) -> s32` | bit n set while channel n plays; the lowest idle channel in `lo..hi` (inclusive), or −1 |
| `reverb(preset, vol_l, vol_r)` | `REVERB_OFF`, `REVERB_ROOM`, `REVERB_STUDIO`, `REVERB_HALL`, `REVERB_SPACE` or `REVERB_ECHO`, and the wet volume per side. A new preset starts from silence |
| `reverb_send(ch, on: bool)` | send a playing channel to the reverb, or stop sending, without restarting it |
| `reverb_decay(n)` | 0: the preset's own decay; 1–255: its feedback × n / 256 (shorter tails) |
| registers, constants | `REVERB_CTRL REVERB_VOL REVERB_DECAY AUDIO_ACTIVE`, `AUDIO_HI_BASE` (channels 8–15) |

`play`, `play16` and `play_adpcm` start a channel dry (no reverb send) and loop from sample 0;
use `play_sample` or `reverb_send` for the rest. Every `play*` restarts the channel.

```
embed MUSIC: u8 = "music.adp"     // tools/mei_adpcm.py encode music.wav -o music.adp --loop 88200

fn init() {
    reverb(REVERB_HALL, 96, 96)
    play_sample(0, MUSIC, 1_234_567, 88200, 1.0, 180, 180, SND_ADPCM | SND_LOOP | SND_REVERB)
}
```

**Voices (`voice.akr`).** A `Voices` record hands out a range of channels to sound effects, so
a cart need not assign channels by hand:

| | |
|---|---|
| `voices_init(v: *Voices, first, last, gap)` | channels `first..last` (inclusive); a sound started again within `gap` frames of its last start plays once |
| `voice_alloc(v, id, pri, limit) -> s32` | the channel for sound `id` (any number the cart gives it) with priority `pri` (higher matters more) and at most `limit` instances (0: any number); −1 when it should not play. Start it on that channel at once |
| `voice_play(v, id, pri, limit, data, samples, pitch, vol_l, vol_r, flags) -> s32` | `voice_alloc`, then `play_sample` on the channel (from sample 0) |
| `voice_count(v, id) -> s32`, `voice_stop(v, id)` | instances of `id` playing; stop them (`id` −1: everything on `v`'s channels) |

A sound takes a free channel; at its instance limit it restarts its own oldest instance instead;
with no channel free it replaces the least important sound playing (the oldest among equals),
but never one more important than itself. Keep the allocator's channels for it alone (music
and ambience on others): a channel it did not start counts as a sound of priority 0.

```
const SND_STEP = 0
const SND_COIN = 1
var sfx: Voices

fn init() { voices_init(&sfx, 8, 15, 3) }
fn footstep() { voice_play(&sfx, SND_STEP, 1, 2, STEP, len(STEP), 0.9 + rndf() / 5, 70, 70, 0) }
fn coin() { voice_play(&sfx, SND_COIN, 3, 1, COIN, len(COIN), 1.0, 160, 160, SND_REVERB) }
```

`tools/mei_adpcm.py` converts WAV files (`encode in.wav -o out.adp [--loop N]`, which prints
the sample count), decodes them back for checking, and is importable (`encode`, `decode`).
Loop points are best on multiples of 28 samples (one block), which the encoder makes seamless.

### Debug output and memory (`debug.akr`, `mem.akr`)

| | |
|---|---|
| `print(s)`, `println(s)`, `print_debug(s)` (= `println`) | strings |
| `print_char(c)`, `print_int(n)`, `print_uint(n)`, `print_hex(n)` | numbers |
| `print_fixed(f)` | up to four decimals: `1.5`, `-0.25`, `3.1416` |
| `print_vec(v: vec4)` | `(x, y, z, w)` |
| `memcpy(dst: *u8, src: *u8, n: u32)` | front to back; 16 bytes per `vld`/`vst` (about 0.95 cycles a byte) once both are word aligned, also when they start misaligned by the same amount; byte by byte otherwise (about 10 a byte) |
| `memset(dst: *u8, v: u8, n: u32)` | a word at a time when `dst` is aligned (about 1.8 cycles a byte), else bytes (about 6) |
| `mem_fill(dst: *u8, v: u8, n: u32)` | the same as `memset`, fast: bytes up to a word boundary, then 64 bytes per step (about 0.3 cycles a byte). `memset` keeps its old speed, so carts that budget work by the cycle counter run as before |

### Memory cards (`card.akr`)

`card_save`, `card_load`, `card_busy` and the rest: see [Saving](#saving).

## Saving

Saves go to a memory card through the card controller (`docs/MEMCARD.md`). Each cart has
16 save numbers (0–15), each holding up to 32,000 bytes plus a title and an animated 16×16
icon that the OS shows. Give the cart an ID, which the card files its saves under (without
one the controller uses a hash of the title, so renaming the cart would lose its saves):

```
cart "Lantern Lake", "LANTERN-LAKE"
```

**Title and icon.** A save's title and icon come from a `SaveMeta` record (452 bytes). Make
one from 1–3 PNG frames (16×16, at most 15 colours plus transparent) with the icon tool, embed
it, and copy it to RAM if you want to change the title:

```
python3 tools/mei_icon.py icon.png icon2.png -o save_icon.bin --title "Lantern Lake"
```

```
embed ICON: SaveMeta = "save_icon.bin"    // in ROM; card_save can use it directly
var meta: SaveMeta

meta = *ICON
card_set_title(&meta, "Day 3 - North Shore")
```

`tools/mei_icon.py` is also a Python module: `make_meta(frames, title, palette=None,
quantize=False)` takes PIL images or numpy arrays (RGBA, RGB, or palette indices with a
palette) and returns the 452 bytes. `SaveMeta` has the fields `title: [32]u8`,
`frames: s32`, `palette: [16]u16` (15-bit colours, colour 0 transparent) and
`pixels: [384]u8` (three frames of 128 bytes, 4 bits per pixel, low nibble = left pixel).

**Functions** (save numbers 0–15; slots 1 and 2):

| | |
|---|---|
| `card_save(num, data: *u8, len, meta: *SaveMeta) -> s32` | start writing a save; returns an error code (`CARD_OK` = 0). Any pointer converts to `*u8`: `card_save(0, &progress, sizeof(Progress), &meta)` |
| `card_load(num, data: *u8, max_len) -> s32` | read a save; returns the bytes read, or a negative error (`-CARD_NOT_FOUND`) |
| `card_load_meta(num, meta: *SaveMeta) -> s32` | read a save's title and icon |
| `card_delete(num) -> s32` | delete a save |
| `card_exists(num) -> bool`, `card_size(num) -> s32` | does it exist; its data length (or a negative error) |
| `card_saves() -> u32` | bit *n* set when save *n* exists: one command for all 16 |
| `card_free_blocks() -> s32` | free 512-byte blocks (255 on an empty card); `card_blocks_for(len)` is what a save of `len` bytes needs (1 + ⌈len / 512⌉) |
| `card_busy() -> bool`, `card_error() -> s32` | the controller is still working; the last command's error |
| `card_wait()` | wait until the controller is idle (stalls the frame loop) |
| `card_slot(n)`, `card_present(n) -> bool` | use the card in slot `n` (1, the default, or 2); is a card inserted |
| `card_set_title(meta: *SaveMeta, s: *u8)` | set a record's title |

Errors: `CARD_OK` 0, `CARD_NO_CARD` 1, `CARD_NOT_FOUND` 2, `CARD_FULL` 3,
`CARD_BAD_ADDRESS` 4 (bad buffer, or more than `CARD_MAX_DATA` = 32,000 bytes),
`CARD_NOT_ALLOWED` 5, `CARD_BAD_COMMAND` 6, `CARD_BUSY` 7. A failed write leaves the old save
in place: replacing a save is atomic.

**Busy time.** A command happens at once (a load has filled the buffer when `card_load`
returns), but the controller then stays busy, like a real card: 2 frames, plus 1 frame per
block read, plus 3 per block written, so saving 1 KB takes about 11 frames and a full 32,000-byte
save about 3 seconds. Even `card_exists` keeps it busy for 2 frames. Every card function first
waits for the previous command to finish, ending frames with `vsync` while it waits: `update()`
and `draw()` do not run, so the game stops and the picture freezes. That is fine in `init()`
or on a title screen, but in play, start the command and keep the frame loop going:

```
var saving = false

fn update() {
    if saving {
        if !card_busy() { saving = false }   // written: safe to change progress again
    } else if btnp(START) && !card_busy() {
        let err = card_save(0, &progress, sizeof(Progress), &meta)
        if err == CARD_OK { saving = true }
        else if err == CARD_FULL { show_message("Card full") }
        else if err == CARD_NO_CARD { show_message("No memory card") }
    }
    ...   // the game keeps running; don't change `progress` or `meta` while saving
}

fn draw() {
    ...
    if saving { text(240, 224, "Saving...", rgb(255, 255, 255)) }
}
```

Loading at start-up is simplest with the blocking calls:

```
fn init() {
    if card_load(0, &progress, sizeof(Progress)) != sizeof(Progress) { new_game() }
}
```

Check what you load: a save written by an older version of the cart may be shorter, so keep
a version number at the start of the saved struct. Only the data the cart passes is stored;
pointers in it are meaningless after a reload.

The headless runner takes `--card1 FILE` and `--card2 FILE` (a missing file is a blank card;
changes are written back at exit), and the tests use `// cards: 1`.

## Mesh format

A mesh is a little-endian binary blob, usually embedded with `embed NAME: Mesh = "file"`.
`tools/meshlib.py` writes it.

```
header (16 bytes)
  +0   u16  vertex count (at most 2,048)
  +2   u16  face count
  +4   u32  byte offset of the vertices (from the start of the mesh; normally 16)
  +8   u32  byte offset of the faces
  +12  u32  reserved (0)
vertex (16 bytes): x, y, z, w as 16.16 fixed point, with w = 1.0
face (36 bytes)
  +0   u8   flags: bit 0 Gouraud, bit 1 textured, bit 2 quad, bit 3 semi-transparent, bit 4 double-sided,
            bit 5 keyed (sorted into the bucket held in col[3]; see Sort keys)
  +1   u8   blend mode 0-3 (used when semi-transparent)
  +2   u8   texture: bits 0-3 slot, bit 4 set for a 4-bit texture
  +3   u8   palette (0-255 for 4-bit textures, 0-15 for 8-bit)
  +4   u16  vertex index ×4 (triangles ignore the fourth)
  +12  u32  colour ×4, 0xBBGGRR (flat faces use the first; for textured faces 0x808080 leaves the texture unchanged)
  +28  u16  texture coordinate ×4: u | v << 8
```

Vertices are 16 bytes so `vld`/`vxfm` work on them directly. Flag bits 0–3 equal the GPU packet
type bits. A triangle is front-facing when its vertices are counter-clockwise as seen by the
viewer. Quads are in strip order: triangles 0-1-2 and 1-2-3, with 0-1-2 counter-clockwise; for a
face seen from the front that is bottom-left, bottom-right, top-left, top-right. When fog is on,
every face is drawn Gouraud-shaded (fog is per vertex); textured faces fade toward half the fog
colour because their colour is a tint.

## Performance notes

Measured with the `CYCLES` register (500,000 cycles per frame):

| Operation | Cycles |
|---|---|
| frame overhead (ordering-table reset, submit) | about 1,500 |
| vertex transform in `mesh()` | 26 per vertex (40 with fog), including the guard-band mark |
| guard-band test, in a mesh with a vertex outside the band | about 9 more per face |
| a face clipped to the guard band | about 3,000, including drawing its pieces |
| the sort-key check per visible face | 2 (a `FACE_KEYED` face about 8 more, instead of `otz`) |
| face in `mesh()`, wholly behind the near plane | about 40 (every corner is checked: one in front makes it a crossing face) |
| face crossing the near plane | about 100 when its corners show it lies beyond one side of the view; about 1,000 when that only shows once it is clipped to the plane (or it faces away); about 4,000 when it is clipped and drawn, including its pieces |
| face in `mesh()`, back-facing | about 48 |
| visible flat quad / Gouraud textured quad | about 130 / 163 (triangles a little less) |
| fog | about 8–11 more per visible face vertex |
| `text()` | about 105 per character |
| `font_text()` | about 45 per glyph plus about 300 a call (`ALIGN_CENTRE`/`ALIGN_RIGHT`: about 30 more per character, to measure the line) |
| `rect()` / `rect_blend()` / `rect_grad()` | about 140 / 90 / 110 |
| `line()`, `tri_fill()` / `sprite()` / `sprite_ex()` / `sprite_rot()` | about 100 / 210 / 180 / 460 |
| `palette_lerp` / `palette_rotate` | about 38 / 14 per colour |
| `project_point` | about 120 |
| `ot_save`/`ot_restore` / `ot_swap` / `ot_detach` | about 3,900 / 4,900 / 26,000 plus 15 per packet |
| `task_resume` and the `task_yield` back | about 125 |
| `memcpy`, word aligned / `mem_fill` / `memset` | about 0.95 / 0.3 / 1.8 (aligned) or 6 per byte |
| `sin`, `cos` | about 50 |
| `sqrt` | about 300 |
| `mat4 * mat4` | about 300 |
| function call overhead | 4 (`call` + `ret`) plus argument moves and saved registers |
| call through a function value in memory | 3 more than a direct call, plus 2 per captured word |
| `map`/`filter`/`reduce`/`each` | about 11 cycles per element plus the function's own cost |
| `mesh()` with `subdivide()` on: each face not split | about 35 more |
| a face split by `subdivide()` | about 1,000 per piece drawn (a quad cut in two: about 2,000 more than drawing it whole) |

The demo cart (a fogged 16×16 ground and a textured cube, about 370 triangles, plus a HUD)
uses about 78,000 cycles per frame with `subdivide(2)` at a 10 % tolerance.

`mesh()` uses the geometry instructions (`DECISIONS.md`): `vxp3` transforms and projects three
vertices at a time, `nclip` is the back-face test, `otz` the ordering-table bucket and `clerp`
the fog blend. Before them, a vertex cost 46 cycles (58 with fog), a visible Gouraud textured
quad 187 (364 with fog) and a frame's ordering-table reset 3,600.

Guidelines: integer `*` by a constant power of two and `fixed * int` are cheaper than `fmul`;
`fdiv`/`div` cost 20 cycles; accessing a global costs one load or store; locals are in
registers unless their address is taken; vector maths stays in vector registers within a
function but vectors are spilled around calls; `-S` shows exactly what was generated.

## Limitations

- No generics (except the built-ins above), unions, slices, methods or operator overloading.
- Closures capture at most 3 one-word values, by copy, read-only (no vectors, structs, arrays or
  function values). `match` is a statement, not an expression. Const data may hold named
  functions and the addresses of embeds, strings and const data, but not function literals or
  addresses of variables.
- No local `const` declarations (declare constants at the top level).
- Multi-lane swizzles cannot be assigned; vectors cannot be compared with `==`.
- `for` loops count up by one; there is no `..=` or step.
- No run-time bounds or stack-overflow checks. The locals of one function may use at most
  120 KB of stack (make large arrays global).
- One error is reported per compilation.
- Struct, array and matrix parameters are read-only (passed by reference).
- `mesh()` draws at most 2,048 vertices per mesh. Faces crossing the near plane are clipped in
  clip space (see Near plane), which costs far more than drawing a face whole: keep the camera
  clear of walls where it can.

## Testing the compiler

`tests/run_lang_tests.sh` (run by `make test`) compiles every `tests/lang/*.akr`, runs it with
`mei-headless` and compares the debug output with the file's `// expect:` lines (`// frames: N`,
`// pad1: HEX`, `// error: TEXT`, `// exit: N` (e.g. 2 for a failed `assert`) and
`// flags: ARGS` (extra `meic` arguments) adjust a test). `tools/fuzz_lang.py [count] [seed]` compiles
random programs and checks their output against a Python model of the CPU's arithmetic.
