#!/usr/bin/env python3
# Summarises mei-headless --gpu-stats CSVs: triangles, overdraw (pixels filled / screen),
# blended and textured fill, the GPU cycles per frame against the 1,000,000-cycle budget, and
# lag (frames the GPU held back, docs/DECISIONS.md "GPU budget").
# The cycles come from the console (the gpu_cycles column). For CSVs written before that column
# existed they are recomputed here from the same cost table, and lag is not known ("-").
# Usage: tools/mei_gpustats.py FILE.csv... (or a directory of them)
import csv, glob, os, sys, statistics as st
args = sys.argv[1:] or ['.']
files = []
for a in args:
    files += sorted(glob.glob(os.path.join(a, '*.csv'))) if os.path.isdir(a) else [a]
SCREEN = 320*240
BUDGET = 1000000
PX = ['px_flat','px_gouraud','px_tex','px_tex_gouraud','px_semi_flat','px_semi_gouraud','px_semi_tex','px_semi_tex_gouraud']
# the cost table (src/core/machine.h): only used for old CSVs without gpu_cycles
def model(r, tex=2, semi=2, setup=40):
    c = r['tris']*setup + r['clears']*SCREEN//2
    for k in range(8):
        cost = 1
        if k & 2: cost *= tex
        if k & 4: cost *= semi
        c += r['px'][k]*cost
    return c
rows = []
for f in files:
    R = []
    for d in csv.DictReader(open(f)):
        r = dict(cpu=int(d['cpu_cycles']), tris=int(d['tris']), empty=int(d['tris_empty']), drop=int(d['tris_dropped']),
                 clears=int(d['clears']), px=[int(d[k]) for k in PX])
        r['gpu'] = int(d['gpu_cycles']) if d.get('gpu_cycles') not in (None, '') else model(r)
        r['ticks'] = int(d['ticks']) if d.get('ticks') not in (None, '') else None
        r['lag'] = int(d['gpu_lag']) if d.get('gpu_lag') not in (None, '') else None
        R.append(r)
    A = R                              # lag counts every frame
    R = R[30:] if len(R) > 60 else R   # skip boot frames for the rest
    if not R: continue
    name = os.path.basename(f)[:-4]
    tot = [sum(r['px'])+r['clears']*SCREEN for r in R]
    semi = [sum(r['px'][4:]) for r in R]
    tex = [r['px'][2]+r['px'][3]+r['px'][6]+r['px'][7] for r in R]
    g = [r['gpu'] for r in R]
    i = max(range(len(R)), key=lambda j: g[j])
    p95 = sorted(g)[int(len(g)*0.95)]
    known = A[0]['lag'] is not None
    lagged = sum(1 for r in A if r['lag']) if known else None
    lag_ticks = sum(r['lag'] for r in A) if known else None
    rows.append((name, len(R), max(r['tris'] for r in R), max(r['empty'] for r in R)/max(1, max(r['tris'] for r in R)),
                 max(tot)/SCREEN, st.mean(tot)/SCREEN, max(semi)/SCREEN, max(tex)/SCREEN, max(g), p95, R[i]['cpu'],
                 lagged, lag_ticks))
print(f"{'run':28} {'frames':>6} {'maxtri':>6} {'empty%':>6} {'overdraw max/avg':>16} {'semi max':>8} {'tex max':>7} "
      f"{'GPU max/p95':>13} {'of budget':>9} {'cpu@worst':>9} {'lagged':>6} {'lag ticks':>9}")
for r in rows:
    lag = f"{r[11]:6} {r[12]:9}" if r[11] is not None else f"{'-':>6} {'-':>9}"
    print(f"{r[0]:28} {r[1]:6} {r[2]:6} {r[3]*100:5.0f}% {r[4]:7.2f}x/{r[5]:5.2f}x {r[6]:7.2f}x {r[7]:6.2f}x "
          f"{r[8]/1000:6.0f}k/{r[9]/1000:5.0f}k {r[8]*100/BUDGET:8.0f}% {r[10]/1000:8.0f}k {lag}")
