"""Shrine town (A + C): draws design/top.png, oblique.png and sections.png from the level's plan,
layout.py (python3 carts/garden/shrinetown/tools/draw.py). Needs NumPy, matplotlib and Pillow (the
oblique's labels use macOS's Avenir Next if present). A paper sketch, not a world recipe."""
import math, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon
from matplotlib.lines import Line2D
from matplotlib.colors import LinearSegmentedColormap, ListedColormap, LightSource
from layout import *

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'design')
GRID = 2.0
xs = np.arange(0, W + .1, GRID); zs = np.arange(0, D + .1, GRID)
HM = np.array([[height(x, z) for x in xs] for z in zs])
WM = np.array([[1.0 if is_water(x, z) else np.nan for x in xs] for z in zs])

LAYER = {  # route styles: (colour, linestyle, width)
    'axis': ('#ffffff', '-', 3.0), 'west': ('#e8761c', '-', 2.6), 'east': ('#2f7fd8', '-', 2.6),
    'canal': ('#18a8b0', '-', 2.2), 'roof': ('#d0202a', (0, (5, 2.5)), 2.4),
    'sroof': ('#8a1030', (0, (5, 2.5)), 2.4), 'tree': ('#6b3f1a', (0, (2, 1.5)), 2.4),
    'rail': ('#f0a000', '-', 1.3), 'glide': ('#7b3fb0', (0, (1, 1.6)), 2.0),
}

def trees(rnd, n, avoid_routes):
    out = []
    for _ in range(n):
        x, z = rnd.uniform(2, W - 2), rnd.uniform(120, D - 2)
        if in_rect(x, z, COURT) or in_rect(x, z, TERR) or in_rect(x, z, PARK) or in_rect(x, z, CEMETERY): continue
        if is_water(x, z) or pond_d(x, z) < 1.1 or (x < 54 and z < 206): continue
        if any(poly_dist(x, z, p) < 3.5 for p in avoid_routes): continue
        if any(math.hypot(x - cx, z - cz) < r + 2 for cx, cz, r, fl, *_ in CLEARINGS): continue
        if in_rect(x, z, (134, 336, 174, 378)) or (252 <= x and z < 130): continue
        if x < 44 and z > 206: out.append((x, z, 'bamboo')); continue
        out.append((x, z, rnd.choice(['cedar', 'cedar', 'maple', 'ginkgo'])))
    return out

ROUTES = [('axis', R_AXIS), ('west', R_WEST), ('west', R_TUNNEL), ('east', R_EAST), ('east', R_ROPEBRIDGE),
          ('east', R_WATER), ('canal', R_CANAL), ('roof', R_ROOF), ('roof', R_ROOF2), ('roof', R_ROOF3), ('sroof', R_SHRINE_ROOF),
          ('tree', R_TREE), ('tree', R_CROWN), ('tree', R_ROPE)]

# ------------------------------------------------------------------ top.png
def top():
    fig = plt.figure(figsize=(17, 13.6), dpi=100)
    ax = fig.add_axes([.035, .04, .60, .92])
    ls = LightSource(azdeg=315, altdeg=45)
    cm = LinearSegmentedColormap.from_list('t', ['#c9c6bc', '#8fb06a', '#6f9a52', '#5d8446', '#7a7c50', '#998a68', '#c8bea8'])
    rgb = ls.shade(HM, cmap=cm, vmin=-2, vmax=66, vert_exag=2.0, blend_mode='soft')
    ax.imshow(rgb, extent=(0, W, 0, D), origin='lower', interpolation='bilinear')
    # flat town and shrine surfaces
    def rect(r, c, a=1.0, z=1): ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], color=c, alpha=a, zorder=z, lw=0))
    rect((0, 0, W, ROAD[1]), '#bdbab2'); rect(ROAD, '#55565c'); rect(SANDO, '#9a968c')
    rect(PLAZA, '#cfcac0'); rect(COURT, '#d8ccb0'); rect(TERR, '#c9c0ae'); rect(PARK, '#a9c27a', .9)
    rect((244, 18, 292, 52), '#c8a878'); rect((252, 118, 320, 130), '#9a968c')
    for k in range(9):
        z0 = 130 + 12 * k; rect((CEMETERY[0], z0, CEMETERY[2], z0 + 12), '#b8b4a6' if k % 2 else '#aaa698', .95)
    ax.imshow(WM, extent=(0, W, 0, D), origin='lower', cmap=ListedColormap(['#4a8ed0']), interpolation='nearest', alpha=.95, zorder=2)
    # viaduct
    p = np.array(VIADUCT); ax.plot(p[:, 0], p[:, 1], color='#6e6a64', lw=12.5, solid_capstyle='butt', zorder=3)
    ax.plot(p[:, 0], p[:, 1], color='#a8a49a', lw=10, solid_capstyle='butt', zorder=3)
    ax.plot(p[:, 0], p[:, 1], color='#ff8a2a', lw=1.2, ls=(0, (8, 6)), zorder=3)
    cs = ax.contour(xs, zs, HM, levels=np.arange(4, 66, 4), colors='#2b2b22', linewidths=.45, alpha=.5, zorder=2)
    ax.clabel(cs, levels=np.arange(8, 66, 8), fmt='%d m', fontsize=6.5, inline=True)
    rnd = random.Random(3)
    for x, z, k in trees(rnd, 1500, [r for _, r in ROUTES[:7]]):
        col = {'cedar': '#2e5a36', 'maple': '#d86a28', 'ginkgo': '#e8b630', 'bamboo': '#9ab060'}[k]
        ax.add_patch(Circle((x, z), 2.0 if k != 'bamboo' else 1.4, color=col, alpha=.55, lw=0, zorder=3))
    for (x1, z1, x2, z2, b, t, col, lab) in boxes:
        if col == WHITE: continue
        ax.add_patch(Rectangle((x1, z1), x2 - x1, z2 - z1, facecolor=col, edgecolor='#222', lw=.35, zorder=4))
    for (a, b) in wall_segs: ax.plot([a[0], b[0]], [a[1], b[1]], color='#f4f0e4', lw=2.2, solid_capstyle='butt', zorder=4)
    for gx, gz, gr in GATES: ax.add_patch(Circle((gx, gz), 2.2, color='#2a9d5a', zorder=5))
    p = np.array(BRIDGE); ax.plot(p[:, 0], p[:, 1], color=RED, lw=3, zorder=4)
    # roof labels (heights)
    for (x1, z1, x2, z2, b, t, col, lab) in boxes:
        if lab and lab not in ('Stage hall',):
            ax.text((x1 + x2) / 2, (z1 + z2) / 2, lab, fontsize=6, ha='center', va='center', color='white' if col in (ROOF, TILE, '#2e4a30', WOOD, '#7a5a48', '#a8321e', '#3a6ab0') else '#111',
                    zorder=6, weight='bold')
    # rails
    for w in WIRES:
        p = np.array(w); ax.plot(p[:, 0], p[:, 1], color=LAYER['rail'][0], lw=1.2, zorder=6)
        ax.scatter(p[:, 0], p[:, 1], s=6, c='#333', zorder=6)
    for a, b in STRINGS: ax.plot([a[0], b[0]], [a[1], b[1]], color=LAYER['rail'][0], lw=1.6, zorder=6)
    # routes
    for k, pts in ROUTES:
        c, s, w = LAYER[k]; p = np.array(pts)
        if c == '#ffffff': ax.plot(p[:, 0], p[:, 1], color='#222', lw=w + 1.6, alpha=.8, zorder=7)
        ax.plot(p[:, 0], p[:, 1], color=c, lw=w, ls=s, zorder=7)
    for name, s, e in GLIDES:
        ax.annotate('', xy=e, xytext=s[:2], arrowprops=dict(arrowstyle='-|>', color=LAYER['glide'][0], lw=1.6, ls=(0, (1, 1.5))), zorder=8)
        ax.text(s[0] + 1.5, s[1] + 1.5, name.split()[0], fontsize=6.5, color=LAYER['glide'][0], weight='bold', zorder=8)
    for k, a, b, txt in SHORTCUTS:
        ax.annotate('', xy=b, xytext=a, arrowprops=dict(arrowstyle='-|>', color='#0b6b34', lw=2.2), zorder=8)
        ax.text(a[0] + 2, a[1] + 1, k, fontsize=9, weight='bold', color='#0b6b34', zorder=9,
                bbox=dict(boxstyle='round,pad=.12', fc='white', ec='#0b6b34'))
    # seams and exits
    ax.add_patch(Rectangle((W - 5, 96), 5, 64, color='#e0189a', alpha=.85, zorder=9))
    ax.text(W - 7, 160, 'SEAMLESS\n(downtown)', fontsize=7, color='#e0189a', ha='right', va='bottom', weight='bold', zorder=9)
    ax.add_patch(Rectangle((0, 250), 4, 134, color='#e0189a', alpha=.5, zorder=9))
    ax.text(6, 378, 'SOFT EDGE\n(bamboo level)', fontsize=7, color='#a0106a', va='top', weight='bold', zorder=9)
    for (x, z, dx, dz, t) in [(4, 111, -4, 0, 'road west'), (48, 6, 0, -6, 'canal'), (150, 6, 0, -5, 'train'),
                              (252, 376, 0, 7, 'next hill'), (308, 140, 10, 6, 'train')]:
        ax.annotate(t, xy=(x + dx, z + dz), xytext=(x, z), fontsize=6.5, ha='center', zorder=9,
                    arrowprops=dict(arrowstyle='-|>', color='#111', lw=1.4))
    # spawn sight line to the pagoda
    ax.plot([SPAWN[0], PAGODA[0]], [SPAWN[1] - 4, PAGODA[1]], color='#111', lw=.8, ls=(0, (6, 4)), alpha=.6, zorder=6)
    # stars, red coins, race switch
    for n, x, z, h, lab in STARS:
        ax.scatter([x + 5], [z + 5], marker='*', s=650, c='#ffd400', edgecolors='#5a4400', linewidths=1.2, zorder=12)
        ax.text(x + 5, z + 4.6, str(n), fontsize=9, weight='bold', ha='center', va='center', zorder=13)
    for x, z, h in RED_COINS:
        ax.scatter([x], [z], marker='o', s=40, c='#ff2020', edgecolors='#400', zorder=12)
    ax.scatter([RACE_SWITCH[0]], [RACE_SWITCH[1]], marker='s', s=60, c='#ffd400', edgecolors='#111', zorder=12)
    ax.text(RACE_SWITCH[0] + 3, RACE_SWITCH[1] - 6, 'race\nswitch', fontsize=6, zorder=12)
    for n, x, z, lab in POIS:
        ax.add_patch(Circle((x - 4, z - 4), 3.2, facecolor='white', edgecolor='#111', lw=.9, zorder=10))
        ax.text(x - 4, z - 3.9, str(n), fontsize=6.3, weight='bold', ha='center', va='center', zorder=11)
    # cell grid
    for g in range(0, W + 1, CELL): ax.axvline(g, color='#000', lw=.6, alpha=.35, zorder=9)
    for g in range(0, D + 1, CELL): ax.axhline(g, color='#000', lw=.6, alpha=.35, zorder=9)
    for i in range(W // CELL):
        for j in range(D // CELL):
            ax.text(i * CELL + 2, j * CELL + CELL - 2, f'c{i}_{j}', fontsize=6, va='top', color='#000', alpha=.55, zorder=9)
    for x, z, t in [(160, 52, 'SANDO'), (98, 94, 'BACK ALLEYS'), (22, 110, 'MACHIYA'), (160, 36, ''),
                    (276, 96, 'SCHOOL'), (168, 150, ''), (88, 270, 'WEST WOODS'), (200, 284, 'RIDGE'),
                    (154, 318, 'BASIN'), (110, 372, 'BACK MOUNTAIN'), (290, 228, 'CEMETERY'), (226, 218, 'EAST\nVALLEY'),
                    (22, 186, 'PARK'), (22, 270, 'BAMBOO'), (290, 340, 'EAST\nSHOULDER')]:
        if t: ax.text(x, z, t, fontsize=8.5, weight='bold', ha='center', va='center', alpha=.85, zorder=9,
                      bbox=dict(boxstyle='round,pad=.15', fc='white', ec='none', alpha=.6))
    ax.set_xlim(0, W); ax.set_ylim(0, D); ax.set_aspect('equal')
    ax.set_xticks(range(0, W + 1, 32)); ax.set_yticks(range(0, D + 1, 32)); ax.tick_params(labelsize=7)
    ax.set_xlabel('x east (m)'); ax.set_ylabel('z north (m)')
    ax.set_title('Shrine town (A + C): 320 x 384 m, north up, 5 x 6 cells of 64 m, contours every 4 m', fontsize=12, loc='left')
    # legend
    lx = fig.add_axes([.645, .04, .35, .92]); lx.axis('off'); lx.set_xlim(0, 1); lx.set_ylim(0, 1)
    yy = .995
    def line(t, fs=8, dy=.0145, **kw):
        nonlocal yy; lx.text(0, yy, t, fontsize=fs, va='top', **kw); yy -= dy
    line('Routes by layer', fs=10.5, dy=.02, weight='bold')
    for k, t in [('axis', 'Ground: the axis (plaza, shotengai, torii, gate, temple, north gate, pagoda)'),
                 ('west', 'Ground: west (alleys, woods trail, fox grove, torii tunnel to the stage)'),
                 ('east', 'Ground: east (school lane, overpass, cemetery, shoulder, rope bridge; pond, stream)'),
                 ('canal', 'Ground: canal lane (machiya, park, watermill, bamboo grove)'),
                 ('roof', 'Town roofs (bus stop, konbini, wires, shops, arcade, alleys)'),
                 ('sroof', 'Shrine roofs (side halls, strings, gate, corridor halls, temple)'),
                 ('tree', 'Tree layer (decks 9-24 m, crown 28 m, rope to the cedar)'),
                 ('rail', 'Rails: utility wires 8 m, lantern strings, viaduct parapet'),
                 ('glide', 'Glides (4 m out per 1 m down, from 3.4 m above take-off)')]:
        c, s, w = LAYER[k]
        lx.add_line(Line2D([0, .06], [yy - .006, yy - .006], color=c if c != '#ffffff' else '#888', lw=3, ls=s))
        lx.text(.075, yy, t, fontsize=7.6, va='top'); yy -= .016
    yy -= .006
    line('Stars', fs=10.5, dy=.019, weight='bold')
    for n, x, z, h, lab in STARS: line(f'{n}  {lab}', fs=7.8)
    line('red dots: the eight red coins (star 2); yellow square: race switch (star 5)', fs=7.2)
    yy -= .006
    line('Shortcuts (open once, stay open)', fs=10.5, dy=.019, weight='bold')
    for k, a, b, t in SHORTCUTS: line(f'{k}  {t}', fs=7.4)
    yy -= .006
    line('Glides (arrival height)', fs=10.5, dy=.019, weight='bold')
    for name, s, e in GLIDES:
        h, d = glide_end_height(s, e); line(f'{name}: {d:.0f} m, arrives {h:.1f} m', fs=7.2, dy=.0135)
    yy -= .006
    line('Places', fs=10.5, dy=.019, weight='bold')
    half = (len(POIS) + 1) // 2
    y0 = yy
    for i, (n, x, z, lab) in enumerate(POIS):
        col = 0 if i < half else .5
        lx.text(col, y0 - (i % half) * .0128, f'{n}  {lab}', fontsize=6.7, va='top')
    yy = y0 - half * .0128 - .008
    line('Edges: magenta = seamless (east, under the viaduct) and soft (north-west bamboo); arrows = conventional exits', fs=7)
    line('Moves (STYLE.md, tuning.akr): jump 2.1, double 3.4, backflip 4.8, double + grab ~5, long jump ~7,', fs=7)
    line('good wall kick +3.4 m, bounce +4.5, glide 8 m/s sinking 2 m/s; gaps <= 5 m, unaided steps <= 4.5 m', fs=7)
    fig.savefig(os.path.join(OUT, 'top.png')); plt.close(fig)

# ------------------------------------------------------------------ sections.png
def sections():
    fig, axs = plt.subplots(3, 1, figsize=(17, 11.5), dpi=100, gridspec_kw={'height_ratios': [86 / 384, 68 / 320, 34 / 320]})
    def bar(ax, a1, a2, z0, z1, col, lab=None, lz=1.0, fs=7.5):
        ax.add_patch(Rectangle((a1, z0), a2 - a1, z1 - z0, facecolor=col, edgecolor='#222', lw=.5, zorder=3))
        if lab: ax.text((a1 + a2) / 2, z1 + lz, lab, ha='center', fontsize=fs, zorder=5)
    def glide(ax, a0, h0, d, lab, col='#7b3fb0', end=None):
        a1 = a0 + d * 4 * (h0 + 3.4 - (end if end is not None else 0))
        ax.plot([a0, a0, a1], [h0, h0 + 3.4, end if end is not None else 0], color=col, lw=1.5, ls='--', zorder=6)
        ax.text(a0 + d * 8, h0 + 4.5, lab, color=col, fontsize=8, zorder=6)
    # 1. north-south along the axis, x = 156-164 (and the pagoda's line, x 178)
    ax = axs[0]
    a = np.arange(0, D, .5)
    prof = np.array([height(160, z) for z in a]); prof2 = np.array([height(178, z) for z in a])
    ax.fill_between(a, -4, np.maximum(prof, prof2), color='#c7d3b0', zorder=1)
    ax.fill_between(a, -4, prof, color='#7d9a5c', zorder=2); ax.plot(a, prof, color='#33402a', lw=.8, zorder=2)
    bar(ax, 2, 14, 0, 9, '#a8a49a', 'viaduct 9'); bar(ax, 2, 14, 9, 12.8, '#7a8a70', 'canopy 12.8', lz=.6)
    for z in range(44, 104, 10): bar(ax, z + .5, z + 9.5, 0, 6.5 if z not in (54, 94) else 9.5, TILE)
    bar(ax, 62, 94, 7, 8.5, '#a8c0cc', 'arcade roof 7-8.5', lz=.4); bar(ax, 96, 98, 0, 8.3, RED)
    bar(ax, 123.5, 124.5, .6, 13.2, RED, 'torii 13.2'); bar(ax, 126, 162, .6, SIDE_ROOF, '#e09080', 'side halls (beside) 11.6', lz=4)
    bar(ax, 161, 173, 5, GATE_ROOF, RED, f'gate {GATE_ROOF:.1f}'); bar(ax, 174, 202, 5, CORR_ROOF, '#e09080', f'corridor halls (beside) {CORR_ROOF:.0f}', lz=4)
    bar(ax, 210, 226, 8.6, TEMPLE_ROOF, WOOD, f'temple {TEMPLE_ROOF:.1f}')
    bar(ax, 257.5, 266.5, PAG_BASE, PAG_TOP, '#a03c2e', 'pagoda 50 (x 178)')
    for zz in PAG_ROOFS: ax.plot([255.7, 268.3], [zz, zz], color='#222', lw=1.4, zorder=4)
    bar(ax, 293, 299, 13, 13 + 45.8, '#2e4a30', 'sacred cedar 58.8 (x 154)')
    bar(ax, 340, 354, STAGE_Z - 1, STAGE_Z, '#aa7c50'); bar(ax, 355, 374, STAGE_Z, STAGE_Z + 18, WOOD, 'stage hall', lz=.8)
    ax.text(344, 62, 'stage 60', fontsize=8)
    glide(ax, 340, 60, -1, '', end=2.0)
    ax.text(232, 66, 'race glide (runs x 170 -> 160): 14 m east of the cedar, 5 m west of the pagoda eaves,\n3.4 m over the temple ridge, 1.5 m over the gate, between the torii posts, into the arcade', color='#7b3fb0', fontsize=8)
    glide(ax, 228, TEMPLE_ROOF, 1, 'G5 temple -> pagoda roof 1', end=PAG_ROOFS[0])
    ax.text(18, 1, 'S', fontsize=10, weight='bold', zorder=6)
    ax.set_xlim(0, D); ax.set_ylim(-4, 82); ax.set_aspect(1.0); ax.grid(alpha=.25)
    ax.set_xticks(range(0, D + 1, 32)); ax.set_xlabel('z north (m)'); ax.set_ylabel('m')
    ax.set_title('1. South-north on the axis (x = 160; pagoda at x 178 in light green behind): station, shotengai, torii, gate, temple, '
                 'pagoda, basin, stage', fontsize=10.5, loc='left')
    # 2. west-east at z = 296-300: bamboo, canal head, fox grove, rope deck, cedar, falls valley, shoulder
    ax = axs[1]
    a = np.arange(0, W, .5); z0 = 296
    prof = np.array([height(x, z0) for x in a])
    ax.fill_between(a, -4, prof, color='#7d9a5c', zorder=2); ax.plot(a, prof, color='#33402a', lw=.8, zorder=2)
    for x in range(4, 44, 5): bar(ax, x, x + .5, height(x, z0), height(x, z0) + 13, '#9ab060')
    ax.text(22, 40, 'bamboo grove (soft edge west)', ha='center', fontsize=8)
    bar(ax, 86, 94, 15, 19.4, RED, 'fox shrine 15', lz=.6)
    bar(ax, 127, 133, 23.4, 24, '#aa7c50', 'rope deck 24', lz=.8); bar(ax, 129.5, 130.5, 13.8, 23.4, '#4a3a2e')
    ax.plot([130, 150.5], [24, 21.5], color='#f0a000', lw=2.2, zorder=6); ax.text(132, 26.5, 'hang rope 24 m long, 2.5 m/s', fontsize=7.5, color='#a06000')
    bar(ax, 151, 157, 13, 58.8, '#2e4a30', 'sacred cedar', lz=.8)
    ax.add_patch(Rectangle((152, 13), 4, 9.5, facecolor='#e8d8a0', edgecolor='#222', lw=.6, zorder=4))
    ax.text(154, 14.5, 'hollow\n+ star', fontsize=6.5, ha='center', zorder=5)
    ax.add_patch(Rectangle((150.2, 20.6), 1.2, 2.2, facecolor='#111', zorder=5)); ax.text(146, 30, 'knot hole 21.5\n(lip above)', fontsize=7, ha='right')
    ax.plot([234, 234], [height(234, z0) - .3, height(234, z0) + .2], color='#4a8ed0', lw=6)
    ax.text(234, height(234, z0) + 3, 'stream', fontsize=7.5, ha='center')
    bar(ax, 245, 247.5, height(246, z0) + 1, height(246, z0) + 14, '#5a3e2c'); ax.text(246, height(246, z0) + 16, 'dead cedar (C)', fontsize=7, ha='center')
    ax.set_xlim(0, W); ax.set_ylim(-4, 64); ax.set_aspect(1.0); ax.grid(alpha=.25)
    ax.set_xticks(range(0, W + 1, 32)); ax.set_xlabel('x east (m)'); ax.set_ylabel('m')
    ax.set_title('2. West-east at z = 296: bamboo grove, canal head, fox grove, rope deck and the cedar (star 4), stream, east shoulder', fontsize=10.5, loc='left')
    # 3. west-east through the town at z = 70: machiya, sento, canal, alleys, fire tower, shotengai, building, gym, school, viaduct
    ax = axs[2]
    prof = np.array([height(x, 70) for x in a])
    ax.fill_between(a, -4, prof, color='#a8a49a', zorder=2)
    bar(ax, 4, 8, 0, 7.5, ROOF); bar(ax, 8, 30, 0, 8, '#7a5a48', 'sento 8'); bar(ax, 22, 25, 0, 18.2, '#8a8478', 'chimney 18.2', lz=.6)
    bar(ax, 30, 40, 0, 7.0, ROOF); ax.plot([44, 52], [-.4, -.4], color='#4a8ed0', lw=5); ax.text(48, 1, 'canal', fontsize=7.5, ha='center')
    for x in range(66, 136, 12):
        if 96 <= x <= 108: continue
        bar(ax, x, x + 9.5, 0, random.Random(x).choice([6, 6.5, 7, 8]), ROOF)
    bar(ax, 99, 105, 0, 15.2, '#a8321e', 'fire tower 15.2', lz=.6)
    bar(ax, 140, 154, 0, 6.5, TILE); bar(ax, 166, 180, 0, 6.5, TILE); bar(ax, 152, 168, 7, 8.5, '#a8c0cc', 'arcade 7-8.5', lz=.4)
    ax.add_patch(Rectangle((154, 2.4), 2, .3, color='#e04040', zorder=5)); ax.text(150, 3.2, 'awnings 2.6 (bounce +4.5)', fontsize=6.5, ha='right')
    bar(ax, 186, 200, 0, 18.3, '#b8b0a0', 'building 18.3', lz=.6); bar(ax, 214, 238, 0, 9, '#8a9a80', 'gym 9')
    bar(ax, 258, 288, 0, 18.9, '#d8d4c8', 'school 18.9'); bar(ax, 296, 308, 0, 9, '#a8a49a', 'viaduct 9')
    glide(ax, 25, 18.2, 1, 'G3 / red coin 7: chimney top, glides 69 m (here: over the canal)', end=7.0)
    ax.annotate('', xy=(160, 7), xytext=(160, 0), arrowprops=dict(arrowstyle='<->', lw=1))
    ax.set_xlim(0, W); ax.set_ylim(-4, 30); ax.set_aspect(1.0); ax.grid(alpha=.25)
    ax.set_xticks(range(0, W + 1, 32)); ax.set_xlabel('x east (m)'); ax.set_ylabel('m')
    ax.set_title('3. West-east through the town at z = 70: machiya, sento, canal, alleys, fire tower, shotengai and arcade, building, gym, school, viaduct',
                 fontsize=10.5, loc='left')
    fig.tight_layout(); fig.savefig(os.path.join(OUT, 'sections.png')); plt.close(fig)

# ------------------------------------------------------------------ oblique.png (as a/draw.py)
def oblique():
    from PIL import Image, ImageDraw, ImageFont
    try:
        f_lab = ImageFont.truetype('/System/Library/Fonts/Avenir Next.ttc', 15, index=5)
        f_big = ImageFont.truetype('/System/Library/Fonts/Avenir Next.ttc', 19, index=5)
    except Exception: f_lab = f_big = ImageFont.load_default()
    hexc = lambda h: tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))
    L = np.array([-.45, -.55, .70]); L /= np.linalg.norm(L)
    def shade(col, n):
        k = .45 + .6 * max(0, float(np.dot(n, L))); return tuple(int(clamp(c * k, 0, 255)) for c in col)
    S, STEP = 2.05, 4
    # view from the south-east: screen x grows with (x + (D - z)) mirrored; key = depth
    def P(x, z, h):
        u = x; v = D - z                      # v grows southwards (towards the viewer)
        return (60 + (u - v + D) * .866 * S, 200 + (u + v) * .5 * S - h * S)
    key = lambda x, z: x + (D - z)
    polys = []
    for i in range(W // STEP):
        for j in range(D // STEP):
            x0, z0 = i * STEP, j * STEP
            c = [(x0, z0), (x0 + STEP, z0), (x0 + STEP, z0 + STEP), (x0, z0 + STEP)]
            hs = [height(*p) for p in c]
            hx = (hs[1] + hs[2] - hs[0] - hs[3]) / (2 * STEP); hz = (hs[2] + hs[3] - hs[0] - hs[1]) / (2 * STEP)
            n = np.array([-hx, hz, 1.0]); n /= np.linalg.norm(n)
            cx, cz = x0 + STEP / 2, z0 + STEP / 2
            if is_water(cx, cz): col = (70, 130, 190); hs = [min(h, -.4) for h in hs]
            elif in_rect(cx, cz, ROAD): col = (84, 84, 90)
            elif cz < ROAD[1]: col = (176, 172, 164) if not in_rect(cx, cz, (244, 18, 292, 52)) else (200, 168, 120)
            elif in_rect(cx, cz, TERR) or in_rect(cx, cz, COURT): col = (206, 196, 172)
            elif in_rect(cx, cz, CEMETERY): col = (176, 172, 158)
            elif in_rect(cx, cz, PARK): col = (160, 190, 110)
            elif any(poly_dist(cx, cz, r) < 2 for r in (R_WEST, R_TUNNEL, R_EAST, R_WATER)): col = (150, 120, 84)
            elif cx < 44 and cz > 206: col = (130, 150, 80)
            else: col = (86, 116 + int(clamp(sum(hs) / 4, 0, 40)), 60)
            polys.append((key(cx, cz) - 3, [P(px, pz, h) for (px, pz), h in zip(c, hs)], shade(col, n), None))
    # viaduct as boxes along its line
    for (a, b) in zip(VIADUCT, VIADUCT[1:]):
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) // 8))
        for k in range(n):
            x = a[0] + (b[0] - a[0]) * (k + .5) / n; z = a[1] + (b[1] - a[1]) * (k + .5) / n
            boxes_v = (x - 5, z - 5, x + 5, z + 5, 7.6, 9.0, '#a8a49a', None)
            boxes.append(boxes_v)
            boxes.append((x - .9, z - .9, x + .9, z + .9, 0, 7.6, '#8a867e', None))
    for (x1, z1, x2, z2, z0, z1h, col, lab) in boxes:
        col = hexc(col)
        xa, xb, za, zb = min(x1, x2), max(x1, x2), min(z1, z2), max(z1, z2)
        k = key(xb, za) + .01
        polys.append((k, [P(xb, zb, z0), P(xb, za, z0), P(xb, za, z1h), P(xb, zb, z1h)], shade(col, (.7, .2, .7)), (30, 30, 30)))
        polys.append((k, [P(xa, za, z0), P(xb, za, z0), P(xb, za, z1h), P(xa, za, z1h)], shade(col, (.2, .3, .7)), (30, 30, 30)))
        polys.append((k + .001, [P(xa, za, z1h), P(xb, za, z1h), P(xb, zb, z1h), P(xa, zb, z1h)], shade(col, (0, 0, 1)), (30, 30, 30)))
    rnd = random.Random(11)
    for x, z, kind in trees(rnd, 1300, [R_WEST, R_TUNNEL, R_EAST, R_WATER, R_AXIS]):
        h0 = height(x, z); bx, by = P(x, z, h0); kk = key(x, z) + .5
        if kind == 'bamboo':
            tx, ty = P(x, z, h0 + 12); polys.append((kk, [(bx - 1, by), (tx, ty), (bx + 1, by)], (150, 176, 90), None)); continue
        if kind == 'cedar':
            hh = rnd.uniform(16, 26); tx, ty = P(x, z, h0 + hh); w = 2.4 * .866 * S
            polys.append((kk, [(bx - w, by), (tx, ty), (bx + w, by)], (40, 86, 52), None))
        else:
            hh, r = rnd.uniform(7, 11), rnd.uniform(3, 4.2); tx, ty = P(x, z, h0 + hh)
            col = (222, 104 + rnd.randint(-20, 20), 36) if kind == 'maple' else (238, 196, 46)
            polys.append((kk, ('blob', tx, ty + r * S * .5, r * S * 1.1, r * S * .8), col, None))
    img = Image.new('RGB', (1520, 960), (228, 232, 238)); d = ImageDraw.Draw(img)
    for _, pts, col, outline in sorted(polys, key=lambda p: p[0]):
        if isinstance(pts, tuple):
            _, cx, cy, rx, ry = pts; d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=col, outline=tuple(int(c * .7) for c in col))
        else: d.polygon(pts, fill=col, outline=outline)
    for kname, pts in [('axis', R_AXIS), ('west', R_WEST), ('west', R_TUNNEL), ('east', R_EAST), ('east', R_ROPEBRIDGE), ('canal', R_CANAL)]:
        c = hexc(LAYER[kname][0]) if LAYER[kname][0] != '#ffffff' else (255, 255, 255)
        seq = []
        for (a, b) in zip(pts, pts[1:]):
            for k in range(8):
                x = a[0] + (b[0] - a[0]) * k / 8; z = a[1] + (b[1] - a[1]) * k / 8
                seq.append(P(x, z, height(x, z) + 1.5))
        d.line(seq, fill=c, width=3)
    for pts, hh in [([(x, z) for x, z, h in DECKS], [h for x, z, h in DECKS])]:
        d.line([P(x, z, h) for (x, z), h in zip(pts, hh)], fill=(110, 64, 26), width=3)
    d.line([P(130, 282, 24), P(KNOT[0], KNOT[1], KNOT[2])], fill=(240, 160, 0), width=3)
    sx, sy = P(170, 340, 63.4); ex, ey = P(160, 92, 3)
    d.line([(sx, sy), (ex, ey)], fill=(123, 63, 176), width=2)
    for n, x, z, h, lab in STARS:
        sx, sy = P(x, z, h + 3); t = f'{n} {lab}'
        w = d.textlength(t, font=f_lab)
        off = {1: (60, -10), 2: (-60, 30), 3: (0, -10), 4: (-170, -30), 5: (0, 34)}[n]
        sx += off[0]; sy += off[1]
        d.rectangle([sx - w / 2 - 4, sy - 22, sx + w / 2 + 4, sy - 2], fill=(255, 230, 80), outline=(40, 40, 40))
        d.text((sx - w / 2, sy - 22), t, font=f_lab, fill=(20, 20, 20))
    for x, z, t in [(160, 30, 'station plaza (spawn)'), (84, 92, 'back alleys'), (20, 80, 'machiya, sento'),
                    (272, 70, 'school'), (300, 116, 'viaduct underpass: seamless edge'), (286, 200, 'cemetery'),
                    (22, 300, 'bamboo grove'), (84, 220, 'west woods'), (234, 150, 'pond')]:
        px, py = P(x, z, height(x, z) + 8); w = d.textlength(t, font=f_lab)
        d.rectangle([px - w / 2 - 3, py - 20, px + w / 2 + 3, py - 1], fill=(255, 255, 255), outline=(90, 90, 90))
        d.text((px - w / 2, py - 20), t, font=f_lab, fill=(30, 30, 30))
    d.text((30, 18), 'Shrine town (A + C) from the south-east: the town wraps the shrine; the pagoda (50 m) on the ridge and the stage (60 m) are the landmarks',
           font=f_big, fill=(20, 20, 20))
    d.text((30, 46), 'Lines: white axis, orange west, blue east, teal canal (ground); brown treetop decks, gold rope to the cedar; purple the race glide (star 5)',
           font=f_lab, fill=(40, 40, 40))
    img.save(os.path.join(OUT, 'oblique.png'))

if __name__ == '__main__':
    top(); sections(); oblique()
    for name, s, e in GLIDES:
        h, dd = glide_end_height(s, e); print(f'{name}: {dd:.1f} m, arrives {h:.1f}, ground {height(*e):.1f}')
