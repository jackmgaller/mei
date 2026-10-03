#!/usr/bin/env python3
"""Adversarial GPU scene comparisons across all 16 packet kinds.

Exact pixel oracle is in oracle.py. Includes full signed-16-bit positions,
large-area slow paths, thin triangles, reverse windings, every blend mode, both
texture depths, arbitrary slots/palettes, texture windows (every size code on
each axis, any origin), clipping and both dither settings.
"""
import argparse
import json
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image
import common
import oracle


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenes',type=int,default=64)
    parser.add_argument('--seed',type=int,default=20261002)
    parser.add_argument('--composed-only',action='store_true',help='Skip isolated packet checks')
    parser.add_argument('--out',type=Path,default=common.OUT/'fuzz')
    args=parser.parse_args()
    if args.scenes<1:
        parser.error('--scenes must be positive')
    args.out.mkdir(parents=True,exist_ok=True)
    probe=common.probe('gpu_probe')
    rng=np.random.default_rng(args.seed)
    # Windows come from a second generator so that the other inputs stay as they were.
    windows=np.random.default_rng(args.seed+1)
    texture=rng.integers(0,256,524288,dtype=np.uint8)
    palette=rng.integers(0,32768,4096,dtype=np.int64)
    failures=[]
    tally={'scenes':args.scenes,'seed':args.seed,'packets':0,'triangles':0,
           'large_area_triangles':0,'degenerate_triangles':0,'negative_windings':0,
           'kinds':{},'windowed_packets':0,'isolated_packets':0,
           'pixel_comparisons':args.scenes*76800}
    for run in range(args.scenes):
        packets=[]
        for kind in range(16):
            flags=kind
            n=4 if flags&4 else 3
            category=(run+kind)%7
            if category==0:
                pos=rng.integers(-32768,32768,(n,2)).tolist()
            elif category==1:
                pos=[[-32768,-32768],[32767,32767],[32766,32767],[32767,32766]][:n]
            elif category==2:
                pos=rng.integers([-400,-300],[720,540],(n,2)).tolist()
            elif category==3:
                pos=rng.integers([0,0],[320,240],(n,2)).tolist()
            elif category==4:
                x,y=rng.integers([0,0],[300,220]).tolist()
                pos=[[x,y],[x+1,y+1],[x+2,y+2],[x+3,y+3]][:n]
            elif category==5:
                x,y=rng.integers([-60,-60],[320,240]).tolist()
                pos=[[x,y],[x+65,y],[x,y+65],[x+65,y+65]][:n]
            else:
                pos=[[-32768,0],[32767,1],[0,240],[320,239]][:n]
            for ids in ([0,1,2],[1,2,3]) if n==4 else ([0,1,2],):
                a,b,c=[pos[i] for i in ids]
                area=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
                tally['triangles']+=1
                tally['large_area_triangles']+=int(abs(area)>=1<<26)
                tally['degenerate_triangles']+=int(area==0)
                tally['negative_windings']+=int(area<0)
            # Half the textured packets of each scene have a texture window: a random size code
            # (0-7, 0 no window) and origin on each axis.
            window=0
            if flags&2 and (run+kind//2)%2:
                window=int(windows.integers(0,8))|int(windows.integers(0,32))<<3
                window|=(int(windows.integers(0,8))|int(windows.integers(0,32))<<3)<<8
                tally['windowed_packets']+=int(bool(window&0x707))
            packets.append({'flags':flags,'blend':(run+kind)%4,'slot':(run+kind)%16,
                            'four':bool((run+kind)%2),'pal':int(rng.integers(0,256)),
                            'pos':pos,'cols':rng.integers(0,256,(n,3)).tolist(),
                            'uv':rng.integers(0,256,(n,2)).tolist(),'window':window})
            tally['kinds'][str(kind)]=tally['kinds'].get(str(kind),0)+1
            tally['packets']+=1
        scene={'background':rng.integers(0,256,3).tolist()}
        case={'dither':bool(run%2)}
        expected=oracle.render(scene,case,packets,texture,palette)
        fixture=args.out/'current.packets'
        raw=args.out/'current.rgb555'
        oracle.write_probe(fixture,scene,case,packets,texture,palette)
        subprocess.run([str(probe.resolve()),str(fixture),str(raw)],check=True)
        actual=np.frombuffer(raw.read_bytes(),dtype='<u2').reshape(240,320)
        mismatch=expected!=actual
        count=int(mismatch.sum())
        if count or run==0:
            prefix=f'case_{run:04d}'
            oracle.rgb_image(expected).save(args.out/f'{prefix}_oracle.png')
            oracle.rgb_image(actual).save(args.out/f'{prefix}_mei.png')
            diff=np.zeros((240,320,3),dtype=np.uint8);diff[mismatch]=[255,40,90]
            Image.fromarray(diff).save(args.out/f'{prefix}_diff.png')
            (args.out/f'{prefix}.packets').write_bytes(fixture.read_bytes())
            (args.out/f'{prefix}.json').write_text(json.dumps({'scene':scene,'case':case,'packets':packets},indent=2)+'\n')
        if count:
            failures.append({'scene':run,'different_pixels':count,'first_mismatch_yx':np.argwhere(mismatch)[0].tolist()})
        if not args.composed_only:
            # Prevent later opaque packets from hiding defects in earlier kinds.
            for kind,p in enumerate(packets):
                expected_one=oracle.render(scene,case,[p],texture,palette)
                oracle.write_probe(fixture,scene,case,[p],texture,palette)
                subprocess.run([str(probe.resolve()),str(fixture),str(raw)],check=True)
                actual_one=np.frombuffer(raw.read_bytes(),dtype='<u2').reshape(240,320)
                mask=expected_one!=actual_one
                tally['isolated_packets']+=1
                tally['pixel_comparisons']+=76800
                if np.any(mask):
                    prefix=f'case_{run:04d}_kind_{kind}'
                    failures.append({'scene':run,'kind':kind,'different_pixels':int(mask.sum()),
                                     'first_mismatch_yx':np.argwhere(mask)[0].tolist()})
                    oracle.rgb_image(expected_one).save(args.out/f'{prefix}_oracle.png')
                    oracle.rgb_image(actual_one).save(args.out/f'{prefix}_mei.png')
                    (args.out/f'{prefix}.packets').write_bytes(fixture.read_bytes())
        if run%16==15:
            print(f'Compared {run+1}/{args.scenes} scenes; {len(failures)} mismatches',flush=True)
    tally['failures']=failures
    (args.out/'report.json').write_text(json.dumps(tally,indent=2)+'\n')
    print(json.dumps(tally),flush=True)
    return bool(failures)

if __name__=='__main__':
    raise SystemExit(main())
