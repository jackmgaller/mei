#!/usr/bin/env python3
"""Compare native Mei turntable frames to an independent depth-buffered reference.

Optional diagnostic tool (requires NumPy). It tests visibility, not pixel-exact
emulator conformance: antialiasing/raster boundaries are excluded and color error
has a 24-channel-value tolerance for dither and projection rounding.
"""
import argparse
import json
import math
from pathlib import Path
import struct
import subprocess
import sys

import numpy as np

from assetkit.compiler import compile_recipe
from assetkit.preview import source, png_bytes
from mei_assets import ROOT, build, load


def reference(binary, mesh, bounds, yaw, pitch, target):
    """Float camera + reciprocal-depth rasterizer; no emulator packets or OT order."""
    nv,nf,vo,fo,_ = struct.unpack_from('<HHIII',binary)
    vertices = np.array([struct.unpack_from('<4i',binary,vo+i*16)[:3] for i in range(nv)],dtype=float)/65536
    lo,hi = np.array(bounds['min']),np.array(bounds['max'])
    scale = min(8192,2/max(hi-lo))
    radius = np.linalg.norm((hi-lo)*scale/2)
    distance = max(1,radius*2.6)
    p = (vertices-(lo+hi)/2)*scale
    right = np.array([math.cos(yaw),0,-math.sin(yaw)])
    up = np.array([-math.sin(yaw)*math.sin(pitch),math.cos(pitch),-math.cos(yaw)*math.sin(pitch)])
    forward = np.array([math.sin(yaw)*math.cos(pitch),math.sin(pitch),math.cos(yaw)*math.cos(pitch)])
    depth = p@forward+distance
    screen = np.floor(np.column_stack((160+160*1.299*(p@right)/depth,120-120*1.732*(p@up)/depth)))
    colors = np.zeros((240,320,3),dtype=np.uint8)
    colors[:] = [24,24,33]
    zbuffer = np.full((240,320),np.inf)
    mask = np.zeros((240,320),dtype=bool)
    for i in range(nf):
        flags,_,_,_,*tail = struct.unpack_from('<BBBB4H4I4H',binary,fo+i*36)
        ids = tail[:3]
        a,b,c = screen[ids]
        area = (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        if area == 0 or (area >= 0 and not flags&16): continue
        left,top = np.maximum(np.min([a,b,c],axis=0).astype(int),[0,0])
        rightmost,bottom = np.minimum(np.max([a,b,c],axis=0).astype(int),[319,239])
        if left>rightmost or top>bottom: continue
        yy,xx = np.mgrid[top:bottom+1,left:rightmost+1]
        weights = []
        for v,w in ((b,c),(c,a),(a,b)):
            weights.append(((w[0]-v[0])*(yy-v[1])-(w[1]-v[1])*(xx-v[0]))/area)
        weights = np.array(weights)
        inside = np.all(weights>=-1e-9,axis=0)
        reciprocal = np.sum(weights/depth[ids,None,None],axis=0)
        z = np.divide(1,reciprocal,out=np.full_like(reciprocal,np.inf),where=reciprocal>0)
        oldz = zbuffer[top:bottom+1,left:rightmost+1]
        visible = inside & (z<oldz)
        cols = np.array([[(word>>shift)&255 for shift in (0,8,16)] for word in tail[4:7]])
        if not flags&1: cols[:]=cols[0]
        shade = np.moveaxis(np.tensordot(cols.T,weights,axes=1),0,-1)
        quantized = np.clip(shade,0,255).astype(np.uint8)>>3
        quantized = (quantized<<3)|(quantized>>2)
        colors[top:bottom+1,left:rightmost+1][visible] = quantized[visible]
        mask[top:bottom+1,left:rightmost+1][visible] = mesh.faces[i].material == target
        oldz[visible] = z[visible]
    # Compare only stable material interiors, away from silhouettes and shade seams.
    stable = mask.copy()
    for dy,dx in ((0,1),(0,-1),(1,0),(-1,0),(0,2),(0,-2),(2,0),(-2,0)):
        stable &= np.roll(mask,(dy,dx),(0,1))
        stable &= np.max(np.abs(colors.astype(int)-np.roll(colors,(dy,dx),(0,1)).astype(int)),axis=2)<=8
    return colors,stable


def audit(recipe, directory, material, views=48, pitch=-.28, compiler=None, runner=None):
    directory = Path(directory).resolve()
    report = build(recipe,directory)
    mesh,materials,_ = compile_recipe(recipe)
    if material not in materials: raise ValueError(f'Unknown target material {material!r}.')
    binary = (directory/(recipe['name']+'.bin')).read_bytes()
    compiler = compiler or ROOT/'build/meic'
    runner = runner or ROOT/'build/mei-headless'
    rows=[]
    for i in range(views):
        yaw = -.65+math.tau*i/views
        stem = directory/f'angle_{i:03}'
        code = source(recipe['name'],report['bounds'],yaw,pitch)
        code = '\n'.join(line for line in code.splitlines() if 'text(' not in line)+'\n'
        stem.with_suffix('.akr').write_text(code)
        subprocess.run([str(compiler),str(stem.with_suffix('.akr')),'-o',str(stem.with_suffix('.mei'))],check=True,capture_output=True)
        subprocess.run([str(runner),str(stem.with_suffix('.mei')),'--frames','4','--dump',str(stem.with_suffix('.ppm'))],check=True,capture_output=True)
        raw = stem.with_suffix('.ppm').read_bytes().split(b'\n',3)[3]
        actual = np.frombuffer(raw,dtype=np.uint8).reshape(240,320,3)
        expected,stable = reference(binary,mesh,report['bounds'],yaw,pitch,material)
        error = np.max(np.abs(actual.astype(int)-expected.astype(int)),axis=2)
        bad = stable & (error>24)
        highlight = actual.copy()
        highlight[bad] = [255,40,100]
        contact = np.concatenate((actual,expected,highlight),axis=1)
        stem.with_suffix('.png').write_bytes(png_bytes(960,240,contact.tobytes()))
        rows.append({'view':i,'yaw':yaw,'tested_pixels':int(stable.sum()),'wrong_pixels':int(bad.sum()),
                     'image':str(stem.with_suffix('.png'))})
    result={'material':material,'views':views,'pitch':pitch,'tested_pixels':sum(r['tested_pixels'] for r in rows),
            'wrong_pixels':sum(r['wrong_pixels'] for r in rows),'worst_views':sorted(rows,key=lambda r:r['wrong_pixels'],reverse=True)[:8],
            'frames':rows,'scope':'Stable material interiors only; independent depth visibility, not pixel-exact GPU conformance.'}
    result['ok'] = result['tested_pixels']>0 and result['wrong_pixels']==0
    (directory/'oracle.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recipe')
    parser.add_argument('-o','--output',required=True)
    parser.add_argument('--material',required=True)
    parser.add_argument('--views',type=int,default=48)
    parser.add_argument('--pitch',type=float,default=-.28)
    parser.add_argument('--compiler',type=Path,default=ROOT/'build/meic')
    parser.add_argument('--runner',type=Path,default=ROOT/'build/mei-headless')
    args=parser.parse_args()
    if not 4<=args.views<=360: parser.error('--views must be between 4 and 360')
    if not math.isfinite(args.pitch) or abs(args.pitch)>math.pi/2: parser.error('--pitch must be finite and between -pi/2 and pi/2')
    result=audit(load(args.recipe),args.output,args.material,args.views,args.pitch,args.compiler.resolve(),args.runner.resolve())
    print(json.dumps({k:v for k,v in result.items() if k!='frames'},indent=2))
    return 0 if result['ok'] else 1


if __name__=='__main__': sys.exit(main())
