# The shrine slice's assets

The shrine slice was a vertical slice of the platformer: a shrine in a forest climbing a back
mountain, 192 × 288 m, built as the garden cart's world `shrine` on 2026-10-04. The shrine town
grew from it ([../shrinetown/README.md](../shrinetown/README.md); its shrine zone,
`shrinetown/place/shrine.py`), and on 2026-10-11 the world was removed: the garden runs on the
shrine town alone ([../README.md](../README.md)). Its recipe, cells, sketches and screenshots are
in git history before that date.

What stays here is what the shrine town's recipe reads:

- `assets/`: the Asset Kit recipes the shrine town lists in its `asset_dirs` (the temple, gate,
  pagoda, halls and walls, the forest's shrines, torii, stage and platforms, plants, street props,
  coins), with their collision companions (`*_col`).
- `assets/art/`: their textures and the generators that draw them (`draw_*.py`, `make_*.py`),
  and the terrain textures the shrine town's ground uses (`terrain_*.png`).
- [STYLE.md](STYLE.md): how these assets look and are built.
