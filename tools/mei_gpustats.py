#!/usr/bin/env python3
# Summarises mei-headless --gpu-stats CSVs: triangles, overdraw (pixels filled / screen),
# blended and textured fill, and a candidate GPU time model (cycles per frame).
# Usage: tools/mei_gpustats.py FILE.csv... (or a directory of them)
import csv, glob, os, sys, statistics as st
args = sys.argv[1:] or ['.']
files = []
for a in args:
    files += sorted(glob.glob(os.path.join(a, '*.csv'))) if os.path.isdir(a) else [a]
SCREEN=320*240
# candidate GPU cost models: cycles per pixel by kind (index = gouraud|tex<<1|semi<<2) + per-triangle setup
def model(r, tex=2, semi=2, setup=40):
    c = r['tris']*setup + r['clears']*SCREEN*0.5
    for k in range(8):
        cost = 1.0
        if k & 2: cost = tex
        if k & 4: cost *= semi
        c += r['px'][k]*cost
    return c
rows=[]
for f in files:
    R=[]
    for d in csv.DictReader(open(f)):
        px=[int(d[k]) for k in ['px_flat','px_gouraud','px_tex','px_tex_gouraud','px_semi_flat','px_semi_gouraud','px_semi_tex','px_semi_tex_gouraud']]
        R.append(dict(cpu=int(d['cpu_cycles']),tris=int(d['tris']),empty=int(d['tris_empty']),drop=int(d['tris_dropped']),clears=int(d['clears']),px=px))
    R=R[30:] if len(R)>60 else R   # skip boot frames
    if not R: continue
    name=os.path.basename(f)[:-4]
    tot=[sum(r['px'])+r['clears']*SCREEN for r in R]
    semi=[sum(r['px'][4:]) for r in R]
    tex=[r['px'][2]+r['px'][3]+r['px'][6]+r['px'][7] for r in R]
    g=[model(r) for r in R]
    i=max(range(len(R)),key=lambda j:g[j])
    p95=sorted(g)[int(len(g)*0.95)]
    rows.append((name,len(R),max(r['tris'] for r in R),max(r['empty'] for r in R)/max(1,max(r['tris'] for r in R)),
                 max(tot)/SCREEN, st.mean(tot)/SCREEN, max(semi)/SCREEN, max(tex)/SCREEN, max(g), p95, R[i]['cpu']))
print(f"{'run':28} {'frames':>6} {'maxtri':>6} {'empty%':>6} {'overdraw max/avg':>16} {'semi max':>8} {'tex max':>7} {'GPU model max/p95':>18} {'cpu@worst':>9}")
for r in rows:
    print(f"{r[0]:28} {r[1]:6} {r[2]:6} {r[3]*100:5.0f}% {r[4]:7.2f}x/{r[5]:5.2f}x {r[6]:7.2f}x {r[7]:6.2f}x {r[8]/1000:8.0f}k/{r[9]/1000:6.0f}k {r[10]/1000:8.0f}k")
