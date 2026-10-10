# Licences

Mei is under three licences, by folder.

| What | Licence |
|---|---|
| Everything not listed below: the emulator (`src/`), the standard library (`stdlib/`), the system ROM (`system/`), the tools (`tools/`), the tests (`tests/`), the browser page (`web/`) and the documentation (`docs/`) | MIT, in [LICENSE](LICENSE) |
| The carts' art and audio (`carts/*/art/`, `carts/*/audio/`), the movement garden's world folders (`carts/garden/*/`, except `tests/`), and the examples (`examples/`) | [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/) (CC BY 4.0), credited to jackmgaller |
| The fonts in `tools/fonts/` | SIL Open Font License 1.1; each family's licence is beside it (`OFL-*.txt`) |

**Carts you make are yours.** A compiled cart contains code from `stdlib/`. As an exception to
the MIT licence's notice condition, a cart compiled with `meic` may be distributed on any terms
without including the copyright notice; the condition still applies to copies of the source.
Textures rendered from the fonts in `tools/fonts/` are not bound by the OFL.

**Not licensed:** `carts/eyewitness/` and `tools/gen_eyewitness_*.py`, which contain material
from the *Eyewitness* title sequence (BBC / Dorling Kindersley). They are not part of any
release.
