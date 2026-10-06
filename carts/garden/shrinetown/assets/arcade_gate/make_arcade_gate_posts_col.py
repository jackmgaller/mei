#!/usr/bin/env python3
"""Writes arcade_gate_posts_col.asset.json beside this script from arcade_gate_col.asset.json: the
arcade gate's collision without its name board and crest, its two pillars only.

    python3 carts/garden/shrinetown/assets/arcade_gate/make_arcade_gate_posts_col.py

The shotengai's north gate uses it. Glide G8, the race line from the stage into the arcade (spec
4.4, scenario 417), comes in under the north gate with its feet at about 4.3; the board's
underside is at 5.11, so with the full collision the glider struck the board and fell short of
the arcade (the spec's gate had a beam at 7.0). The pillars, at the street's edges, stay solid.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
col = json.loads((HERE / 'arcade_gate_col.asset.json').read_text())
col['name'] = 'arcade_gate_posts_col'
col['nodes'] = [n for n in col['nodes'] if n['id'] == 'pillars']
(HERE / 'arcade_gate_posts_col.asset.json').write_text(json.dumps(col, indent=1) + '\n')
print('wrote arcade_gate_posts_col')
