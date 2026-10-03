# Roadmap

What's planned for later, what's still undecided, and what we've decided against. Items move
out of this file when they land, and the decision goes into DECISIONS.md or the relevant spec.

## Language: other candidates (not yet approved)

From the agents' retrospective, roughly in order of value:

- **Multiple return values:** `fn divmod(a, b) -> (s32, s32)`, `let (q, r) = divmod(7, 2)`.
- **Iterating arrays directly:** `for x in arr`, `for i, x in arr`, `step` and reverse ranges,
  and labelled `break outer` for nested grid scans.
- **Compile-time tables (`const fn`):** simple lookup tables built by the compiler instead of a
  Python generator.
- **Saturating arithmetic** (`+|`, `-|`) for colours, volumes and meters.
- **`static` locals:** variables that keep their value between calls.

## Machine (pending go-ahead)

All PS1-authentic unless noted.

- **GPU draw-offset register**, like the PS1's, so cached screen-space geometry can be panned
  without rewriting it.
- **A GPU dropped-triangle counter register.** Dropped triangles past the 4,000 cap only set a
  status bit today.
- **Sprite packets** with their own cost, so an interface rectangle isn't two triangles. This is
  how the real PS1 GPU worked.
- **Per-mesh sort mode** (average, nearest or farthest depth) and per-face bias. The existing
  depth keys cover part of this.
- **A clamp flag on `vxp3`**, like the GTE's FLAG register, to make clipping cheaper.
- **Smaller ones:**
  - a hardware ordering-table clear;
  - per-channel volume ramps, to stop zipper noise;
  - making the null page fault;
  - instant memory-card status queries.
- **Maybe:** count-leading-zeros and funnel-shift instructions for bitmask work. Borderline for
  the era, since the R3000 had neither.

## Tooling (pending go-ahead)

- **Self-checking scenarios:** carts' scenario files check `// expect:` lines, and
  `make test-carts` runs them all.
- **`mei-headless`:**
  - `--arg name=value`, so one build serves a parameter sweep;
  - `--rev HEAD` for before/after runs;
  - `--no-raster`, to run the simulation without drawing pixels;
  - `--compare A.mei B.mei`, a frame diff with masked regions;
  - dumps named by game tick instead of frame number;
  - `--profile` for cycles per function, and faults reported as function and line;
  - direct PNG dumps, and analog stick values in scripted input.
- **`meic -D NAME=value`** for build-time constants.
- **Assembly checks:** warn when code falls through into an assembly label.

## Networking (maybe later)

- **Messaging** between consoles.

## Open questions

- **A name for the assembly language.**
- **Plane chip ports:** Sun & Moon Orbs and the boot themes fit the 1M GPU budget as they are;
  porting them to planes would only buy headroom.

## Decided against

- **Typed (data-carrying) enums.**
- **Headlines or news on MeiNet.** Time is the only canonical feed, for carts only; scores
  weren't wanted either.
- **A depth buffer.** By spec; draw order stays the ordering table's job.
- **Generics, `defer` and language-level generators:** slices, the no-heap design and the task
  library cover them.
- **Tsumiki**, the stdlib 3D toolkit, and its Playroom sample cart: removed in October 2026
  in favour of a different approach.
- **Check-In!**: the cart and its asset generators were removed in October 2026.
