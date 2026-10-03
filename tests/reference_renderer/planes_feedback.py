#!/usr/bin/env python3
"""Investigate case-33 feedback with pixel-live VRAM in packet traversal order.

This diagnostic is separate from the static-resource specification suite: pixel
traversal is an implementation detail when draw resources alias the destination.
It replays the aliased form of planes_check.py's case 33 (BG2's atlas, set line by
line, may overlap the framebuffer being drawn), then compares Mei with both the
static oracle, which must disagree, and a pixel-live one, which must agree.
"""
import json
import struct
import subprocess
import numpy as np
import common
import planes_check as spec

def main():
    root=common.OUT/'planes_feedback'
    root.mkdir(parents=True,exist_ok=True)
    probe=common.probe('planes_probe')
    v,regs,front,draws=spec.fixture(33,aliased=True)
    packets=spec.packet_data(draws)
    replay=root/'case_033.bin'
    replay.write_bytes(struct.pack('<64I',*regs)+v+struct.pack('<I',len(packets))+packets)
    raw=root/'case_033.rgb555'
    subprocess.run([str(probe),str(replay),str(raw)],check=True)
    actual=np.frombuffer(raw.read_bytes(),dtype='<u2').reshape(2,-1)
    static=np.count_nonzero(actual!=np.stack(spec.expected(bytearray(v),regs,front,draws)),axis=1)
    vram=bytearray(v)
    front=front.copy()
    for x0,y0,width,height,mode,upper,color in draws:
        a=spec.pack([(color >> (8*k)&255)//8 for k in range(3)])
        # Strip triangles are (TL,TR,BL), then (TR,BL,BR); shared diagonal
        # belongs to the second triangle under the integer top-left rule.
        for triangle in range(2):
            for y in range(y0,y0+height):
                lr=spec.line(regs,vram,y)
                for x in range(x0,x0+width):
                    second=(x-x0)*height+(y-y0)*width >= width*height
                    if int(second)!=triangle: continue
                    f=int(front[y*spec.W+x])
                    b=spec.stack(vram,lr,x,y,f,4 if upper else 3) if f==0x8000 or (upper and not f&0x8000) else f&0x7fff
                    out=spec.blend(b,a,mode)|(upper<<15)
                    if out==0x8000: out=0x8400
                    front[y*spec.W+x]=out
                    off=2*(y*spec.W+x)
                    vram[off:off+2]=struct.pack('<H',out)
    display=np.empty(spec.W*spec.H,dtype='<u2')
    for y in range(spec.H):
        lr=spec.line(regs,vram,y)
        for x in range(spec.W): display[y*spec.W+x]=spec.stack(vram,lr,x,y,int(front[y*spec.W+x]))
    expected=np.stack([front,display])
    counts=np.count_nonzero(actual!=expected,axis=1)
    report={'case':33,'oracle':'pixel-live VRAM in triangle/row/column traversal order',
            'static_framebuffer_different_pixels':int(static[0]),
            'static_display_different_pixels':int(static[1]),
            'framebuffer_different_pixels':int(counts[0]),'display_different_pixels':int(counts[1])}
    (root/'live_report.json').write_text(json.dumps(report,indent=2)+'\n')
    (root/'live_expected.rgb555').write_bytes(expected.astype('<u2').tobytes())
    print(json.dumps(report))
    # The fixture must still alias (the static oracle disagrees) and the live oracle must agree.
    return int(counts.sum()!=0 or static.sum()==0)

if __name__=='__main__': raise SystemExit(main())
