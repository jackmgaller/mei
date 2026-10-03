<p align="center"><img src="docs/logo.png" alt="Mei" width="480"></p>

Mei is a 3D fantasy console in the spirit of the PlayStation era: a 30 MHz RISC CPU, a vector
unit, a 3D polygon processor (the Prism Engine) that only fills triangles, so affine-warped
textures, wobbly vertices and dithered colour come from the hardware rules rather than filters,
and a scrolling plane processor (the Horizon Engine) for skies, floors and backdrops. It has its
own language, Akari, a tiny OS with boot animations and memory cards, and runs on the desktop
(SDL3) or in a browser tab (WebAssembly).

```bash
make && ./build/mei
```

More in [docs/OVERVIEW.md](docs/OVERVIEW.md).

For VS Code syntax highlighting of Akari (`.akr`) files, see
[the Akari extension](tools/vscode-akari/README.md) for installation instructions.

For agent-driven 3D modeling, [Mei Asset Kit](docs/ASSETKIT.md) builds JSON recipes into native
meshes with extrusion, lathes, lofts, reusable parts, and six-view previews rendered by Mei.
Its `verify` command checks triangle identities against depth-correct visibility and can block
exports on intersections, ordering errors or cycles, without relying on visual inspection.
