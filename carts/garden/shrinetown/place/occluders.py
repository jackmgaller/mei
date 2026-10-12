"""The shrine town's occlusion zones (WORLDKIT.md, "Occlusion"; DESIGN.md 12.9, "Workstream 7").

Called by the placement hook (place/__init__.py) from make_world.py's `world` stage, after the
zones: it adds the recipe's `occlusion` section. Each occluder is a box inside solid geometry of a
real asset (the coordinates are the asset's faces, read from the placed meshes, less a margin);
each zone is a box the game's camera can be in. The World Kit works out what each zone hides; the
World Checker's occlusion check casts rays from every zone to what it hides, and finds no leak.

What is here, and why so little (DESIGN.md 12.9 has the measurements):

- The viaduct's deck between x 120 and 200 (the station spans and the tapers) is solid between
  its underside (8.55 at most) and its top (9.0), except the stair span's opening for the
  platform stair (x 160.65-167.9, z 6.6-9.4): four slabs around it. From under the tapers the
  slabs hide the two train cars standing on the deck (256 faces each at level 0); from the
  plaza west of the station's door, the west car.
- The concourse's end walls (x 136 and 184, y 0-8.6, z 1.5-14.7) hide what is behind them from
  under the tapers.
- The station's facade above its door (z 15, y 4.6-8.6) is solid; with the slabs it hides the
  west car from the plaza near the door. The platform (40 m) and the concourse (48 m) are larger
  than any single occluder's shadow from a useful zone: the kit joins no shadows.

Tried and left out (measured with the World Checker at r01's and r02's cameras and 60 of r01's
heaviest ground views):

- A box in every building of the town rows (67) and a zone every 8 m over the town at camera
  heights up to 5: 3,284 placements hidden over 640 zones (after the leak check had pruned 259
  zone and occluder pairs), but almost none of them in view from where they are hidden (the
  views look along the streets, and what stands behind a row is beside the view, not in it), so
  the views changed by -3,300 to +2,100 cycles, +500 on average: the zones' box tests (up to 64
  a cell) cost more than the culls saved. The shotengai's rows hide 27 placements from a 4 x 8 m
  piece of the street, which a view along the street hardly sees.
- The viaduct's parapet over the cemetery (r02's 709,866 view): the parapet panels are 1.2 m
  tall above the deck; from an eye on the deck the cemetery is below the deck's edge, hidden by
  the deck and the parapet together, never by one of them. Deck and parapet make a U round the
  eye, which no convex occluder outside the zone can stand for.
- The woods decks: the trees are cut-out cards (textures with holes) and cannot occlude; the
  ground under the decks is open.
"""

OCCLUDERS = {
    # the deck slab (y 8.6-8.95), round the stair span's opening at x 160.65-167.9, z 6.6-9.4
    'deck_w': {'box': [[120.2, 8.6, 2.0], [160.6, 8.95, 14.0]]},
    'deck_e': {'box': [[167.95, 8.6, 2.0], [199.8, 8.95, 14.0]]},
    'deck_s': {'box': [[120.2, 8.6, 2.0], [199.8, 8.95, 6.55]]},
    'deck_n': {'box': [[120.2, 8.6, 9.45], [199.8, 8.95, 14.0]]},
    # the station's facade above its door, and the concourse's end walls
    'facade': {'box': [[136.1, 4.7, 14.8], [183.9, 8.5, 14.99]]},
    'concourse_w': {'box': [[136.05, 0.1, 1.6], [136.3, 8.5, 14.6]]},
    'concourse_e': {'box': [[183.7, 0.1, 1.6], [183.95, 8.5, 14.6]]},
}

ZONES = {
    # under the viaduct's tapers, west and east of the concourse: on foot and the follow camera
    'under_taper_w': {'box': [[120, -0.5, 2], [136, 5, 14]]},
    'under_taper_e': {'box': [[184, -0.5, 2], [200, 5, 14]]},
    # the plaza in front of the station, west of its door, at eye height
    'station_front_w': {'box': [[136, -0.5, 16], [160, 2, 28]]},
}


def world(ns):
    ns['world']['occlusion'] = {'occluders': OCCLUDERS, 'zones': ZONES}
