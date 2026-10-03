#!/usr/bin/env python3
"""Persistent multi-frame planes: animated textures/palettes, motion and vsync latching.

Uses the independently authored scalar compositor from planes_check.py.
Unlike static replay, one Mei instance persists and both physical framebuffers
alternate throughout the whole sequence. Inputs change before each presentation.
"""
import argparse
import json
import struct
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import common
import planes_check as spec


def initial_vram():
    vram=bytearray(1<<20)
    for n in range(3):
        for y in range(32):
            for x in range(32):
                entry=(x+y*9)%128 | ((x//4+y//4)%2)<<13 | ((x%3==0)<<14) | ((y%3==0)<<15)
                struct.pack_into('<H',vram,0x50000+n*2048+2*(y*32+x),entry)
    return vram


def frame_inputs(vram,frame):
    yy,xx=np.mgrid[0:256,0:256]
    four=np.where((xx+yy+frame)%23==0,0,1+(xx//8+yy//8+frame//2)%15).astype(np.uint8)
    vram[0x60000:0x68000]=(four[:,::2]|(four[:,1::2]<<4)).tobytes()
    eight=np.where((xx-frame+2*yy)%31==0,0,1+(xx//4+yy//4*13+frame*3)%255).astype(np.uint8)
    vram[0x70000:0x80000]=eight.tobytes()
    indices=np.arange(4096,dtype=np.int64)
    colors=((indices+frame)%32)|(((indices*3+frame*2)%32)<<5)|(((indices*7-frame)%32)<<10)
    vram[0x4c000:0x4e000]=colors.astype('<u2').tobytes()
    regs=[0]*64
    regs[:7]=[3|4,7,0x32542110,0,0,0,0x8000]
    # Two different atlas depths; BG2 is independently transformed each line.
    for n in range(3):
        b=8+8*n
        regs[b:b+3]=[0 if n!=1 else 32|(2<<8),0x60000 if n!=1 else 0x70000,0x50000+n*2048]
        regs[b+3]=((frame*3+n*17)&65535)|(((frame*2-n*11)&65535)<<16)
    regs[3]=(4 if frame%2 else 0) | ((4+(frame%4))<<8)
    # Line table 0 animates a dithered backdrop; table 1 moves/zooms the affine plane.
    regs[40:44]=[0x52000,0x8014,0x52400,0x8378]
    regs[44:46]=[0x53400,0x8030]
    for y in range(240):
        sky=(35+frame*2)%256 | (((65+y//3+frame)%256)<<8) | (((120+y//2-frame)%256)<<16)
        struct.pack_into('<I',vram,0x52000+4*y,sky)
        du=32768+(y+frame)*73
        dv=((frame%16)-8)*701
        struct.pack_into('<4I',vram,0x52400+16*y,
                         (-30*65536+frame*17011-y*215)&0xffffffff,
                         (frame*19001+y*65536)&0xffffffff,du,dv&0xffffffff)
        left=(frame*5+y//4)%80
        right=(frame*3+y//7)%70
        struct.pack_into('<I',vram,0x53400+4*y,left|(right<<16))
    # Moving translucent overlays draw against this frame's updated plane inputs.
    draws=[(15+frame*7%190,40+frame*3%80,72,58,frame%4,frame%2,0x704060),
           (200-frame*5%170,140-frame*2%80,49,47,(frame+1)%4,1,0x304070)]
    return regs,draws


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--frames',type=int,default=24)
    ap.add_argument('--out',type=Path,default=common.OUT/'plane_motion')
    args=ap.parse_args()
    if not 1<=args.frames<=4096: ap.error('--frames must be in 1..4096')
    args.out.mkdir(parents=True,exist_ok=True)
    probe=common.probe('plane_motion_probe')
    initial=initial_vram()
    fixture=args.out/'sequence.bin'
    inputs=[]
    with fixture.open('wb') as stream:
        stream.write(struct.pack('<I',args.frames)+initial)
        for frame in range(args.frames):
            vram=initial.copy()
            regs,draws=frame_inputs(vram,frame)
            inputs.append((vram,regs,draws))
            packets=spec.packet_data(draws)
            stream.write(struct.pack('<64I',*regs)+vram[0x4c000:0x4e000]+vram[0x60000:0x68000]+
                         vram[0x70000:0x80000]+vram[0x52000:0x53800]+struct.pack('<I',len(packets))+packets)
    raw=args.out/'sequence.rgb555'
    subprocess.run([str(probe.resolve()),str(fixture.resolve()),str(raw.resolve())],check=True)
    actual=np.frombuffer(raw.read_bytes(),dtype='<u2').reshape(args.frames,3,240,320)
    reports=[];animation=[]
    previous=np.zeros((240,320),dtype='<u2')
    previous_actual=None
    contact=Image.new('RGB',(960,4*270),(15,19,28));pen=ImageDraw.Draw(contact)
    samples=set(np.linspace(0,args.frames-1,4,dtype=int).tolist())
    sample_row=0
    for frame,(vram,regs,draws) in enumerate(inputs):
        front=np.full(76800,0x8000,dtype='<u2')
        _,expected=spec.expected(vram,regs,front,draws)
        expected=expected.reshape(240,320)
        mismatch=actual[frame,1]!=expected
        temporal_errors=0 if previous_actual is None else int(np.count_nonzero(
            actual[frame,1].astype(np.int32)-previous_actual.astype(np.int32) !=
            expected.astype(np.int32)-previous.astype(np.int32)))
        result={'frame':frame,'different_pixels':int(mismatch.sum()),
                'early_latch_pixels':int(np.count_nonzero(actual[frame,0]!=previous)),
                'auto_erase_pixels':int(np.count_nonzero(actual[frame,2]!=0x8000)),
                'temporal_delta_errors':temporal_errors,
                'changed_pixels':0 if previous_actual is None else int(np.count_nonzero(expected!=previous))}
        reports.append(result)
        reference=Image.fromarray(spec.rgb(expected.reshape(-1)))
        mei=Image.fromarray(spec.rgb(actual[frame,1].reshape(-1)))
        heat=np.zeros((240,320,3),dtype=np.uint8);heat[mismatch]=[255,40,90]
        diff=Image.fromarray(heat)
        picture=Image.new('RGB',(960,270),(15,19,28));draw=ImageDraw.Draw(picture)
        for i,(name,img) in enumerate([('Independent reference',reference),('Mei',mei),('Difference',diff)]):
            draw.text((i*320+6,8),f'Frame {frame}: {name}',fill='white');picture.paste(img,(i*320,30))
        animation.append(picture)
        if frame in samples:
            contact.paste(picture,(0,sample_row*270));sample_row+=1
            reference.save(args.out/f'frame_{frame:03d}_reference.png')
            mei.save(args.out/f'frame_{frame:03d}_mei.png')
        if any(result[k] for k in ('different_pixels','early_latch_pixels','auto_erase_pixels','temporal_delta_errors')):
            picture.save(args.out/f'frame_{frame:03d}_failure.png')
        previous=expected.copy();previous_actual=actual[frame,1].copy()
        if frame%6==5: print(f'Plane motion: {frame+1}/{args.frames} frames compared',flush=True)
    contact.save(args.out/'contact.png')
    animation[0].save(args.out/'comparison.webp',save_all=True,append_images=animation[1:],duration=70,loop=0,lossless=True)
    summary={'frames':args.frames,'pixel_comparisons':args.frames*76800*3,
             'reports':reports,'source':'persistent Mei instance, scalar specification compositor'}
    (args.out/'report.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:sum(r[k] for r in reports) for k in ('different_pixels','early_latch_pixels','auto_erase_pixels','temporal_delta_errors')}))
    return int(any(any(r[k] for k in ('different_pixels','early_latch_pixels','auto_erase_pixels','temporal_delta_errors')) for r in reports))

if __name__=='__main__': raise SystemExit(main())
