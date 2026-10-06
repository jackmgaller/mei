#!/usr/bin/env python3
"""Scalar specification compositor and adversarial full-frame GPU replay.

No import from oracle.py or Mei's tests: expectations use docs/PLANES.md.
"""
import argparse
import json
import random
import struct
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import common

W, H, MASK = 320, 240, 0x1fffff     # VRAM offsets: 2 MB (DECISIONS.md, "VRAM at 2 MB")
DM = ((-4,0,-3,1),(2,-2,3,-1),(-3,1,-4,0),(3,-1,2,-2))
ORDER = (2,1,0,3,4)
RESERVED = {0x1c,0x38,0x3c,0x58,0x5c,0x6c}

def read(v, a, n):
    return int.from_bytes(v[a & MASK:(a & MASK)+n], 'little')

def signed(v, n):
    return v-(1 << n) if v & (1 << (n-1)) else v

def lanes(c):
    return [(c >> n) & 31 for n in (0,5,10)]

def pack(c):
    return sum(max(0,min(31,t)) << (5*i) for i,t in enumerate(c))

def blend(b,a,mode):
    b,a=lanes(b),lanes(a)
    return pack([(x+y)//2 if mode==0 else x+y if mode==1 else x-y if mode==2 else x+y//4
                 for x,y in zip(b,a)])

def line(r,v,y):
    w=r.copy()
    for ch in range(8):
        a,c=r[40+2*ch:42+2*ch]
        if not c & 0x8000: continue
        n=((c >> 8)&3)+1
        for k in range(n):
            target=(c & 0xfc)+4*k
            if 4 <= target <= 0x8c and target not in RESERVED:
                w[target//4]=read(v,(a & 0x1ffffc)+4*(y*n+k),4)
    return w

def sample(v,r,n,x,y):
    b=8+8*n
    mode,atlas,mp=r[b:b+3]
    left,right=r[b+4]&511,(r[b+4] >> 16)&511
    top,bottom=r[b+5]&255,(r[b+5] >> 8)&255
    if not (left <= x < W-right and top <= y < H-bottom): return None
    ts=16 if mode & 16 else 8
    mw,mh=[32 << min(2,(mode >> s)&3) for s in (0,2)]
    if n==2:
        u0,v0,dux,dvx,duy,dvy=[signed(t,32) for t in r[30:36]]
        u=(u0+y*duy+x*dux)//65536
        t=(v0+y*dvy+x*dvx)//65536
        outside=(mode >> 16)&3
        is_out=not (0 <= u < mw*ts and 0 <= t < mh*ts)
        if is_out and outside in (1,3): return None
        entry=0 if is_out and outside==2 else read(v,(mp & 0x1ff800)+2*((t//ts % mh)*mw+u//ts % mw),2)
    else:
        scroll=r[b+3]
        u,t=x+(scroll&65535),y+(scroll >> 16)
        entry=read(v,(mp & 0x1ff800)+2*((t//ts % mh)*mw+u//ts % mw),2)
    tx,ty=u%ts,t%ts
    if entry & 0x4000: tx=ts-1-tx
    if entry & 0x8000: ty=ts-1-ty
    tile=entry & 1023
    cols=256//ts
    u,t=(tile%cols)*ts+tx,((tile//cols)%cols)*ts+ty
    eight=bool(mode&32)
    raw=v[((atlas & 0x1f8000)+t*(256 if eight else 128)+(u if eight else u//2)) & MASK]
    idx=raw if eight else (raw >> (4*(u%2))) & 15
    if not idx: return None
    page=(((mode >> 8)&255)+((entry >> 10)&7)) % (16 if eight else 256)
    color=read(v,0x4c000+2*(page*(256 if eight else 16)+idx),2) & 0x7fff
    return color, bool(entry & 0x2000)

def stack(v,r,x,y,f,below=None):
    bd=pack([max(0,min(255,((r[5] >> (8*k))&255)+(DM[y%4][x%4] if r[0]&4 else 0)))//8 for k in range(3)])
    priority=r[2]
    candidates=[]
    # Draw-time visibility does not suppress stored lower polygon data (rev-2 contract).
    if f != 0x8000 and (below is not None or not r[1]&8):
        n=4 if f&0x8000 else 3
        candidates.append((((priority >> (24 if n==3 else 28))&15),ORDER[n],n,f&0x7fff))
    for n in range(3):
        if not (r[1] >> n)&1: continue
        c=sample(v,r,n,x,y)
        if c is not None:
            col,high=c
            candidates.append((((priority >> (8*n+4*high))&15),ORDER[n],n,col))
    if below is not None:
        cut=((priority >> (24 if below==3 else 28))&15,ORDER[below])
        candidates=[c for c in candidates if c[:2]<cut]
    candidates.sort(reverse=True)
    layer=5
    out=bd
    if candidates:
        _,_,layer,out=candidates[0]
        math=(r[3] >> (4*layer)) & 15
        if math & 4: out=blend(candidates[1][3] if len(candidates)>1 else bd,out,math&3)
    if below is None and (r[3] >> (24+layer)) & 1:
        out=pack([c+signed((r[4] >> (8*k))&255,8) for k,c in enumerate(lanes(out))])
    return out

def fixture(case, aliased=False):
    # aliased: channel 7 writes random words over BG2's atlas register line by line, as the
    # first version of this fixture did, so the atlas may overlap the pixels being drawn
    # (planes_feedback.py; a static-input oracle cannot predict that).
    rng=random.Random(0x504c414e+case)
    v=bytearray(rng.randbytes(1 << 21))
    front=np.array([(0x8000 if (x//19+y//13)%3==0 else ((x*29+y*41)&32767)|((x//31%2)<<15))
                    for y in range(H) for x in range(W)],dtype='<u2')
    v[:W*H*2]=front.tobytes()
    r=[0]*64
    r[:6]=[1|((case%2)<<2),7|(8 if case%9==8 else 0),rng.getrandbits(32),
           rng.getrandbits(32)&0x3f0fffff,rng.getrandbits(24),rng.getrandbits(24)]
    if case%4==0: r[2]=0 # force all five priority ties
    for n in range(3):
        b=8+8*n
        mode=((case+n)%4)|(((case//4+n)%4)<<2)|(((case+n)//2%2)<<4)|(((case+n)%2)<<5)|(((253+case+n)%256)<<8)
        if n==2: mode|=(case%4)<<16
        r[b:b+3]=[mode,[0x60000,0x78000,0x70000 if case%2 else 0x1f8000][n], [0x50000,0x58000,0x5c000 if case%2 else 0x1ff800][n]]   # the last page and map: wrap
        r[b+3]=rng.getrandbits(32)
        if case%3:
            left=[0,1,319,320,511][(case+n)%5]
            right=[0,1,319,320,511][(case//2+n)%5]
            r[b+4]=left|(right<<16)
            r[b+5]=[0,1,239,240,255][(case+n)%5]|([0,1,239,240,255][(case//2+n)%5]<<8)
    r[30:36]=[rng.choice([-1,0,65536,-65536,0x7fffffff,-0x80000000,rng.randrange(-4*65536,4*65536)])&0xffffffff for _ in range(6)]
    # Three ordinary data channels, two conflicting channels, reserved/cross-boundary channels.
    targets=[0x14,0x2c,0x78,0x30,0x30,0x88,0x00,0x58]
    for ch,target in enumerate(targets):
        n=4 if ch in (2,5,6,7) else 1
        a=(0x1fffc0 if ch==6 else 0x4e000+ch*0x1000)
        r[40+2*ch:42+2*ch]=[a|3,0x8000|((n-1)<<8)|target|3]
        for y in range(H):
            for k in range(n):
                val=rng.getrandbits(32)
                if ch==0: val=(y*2311)&0xffffff
                if ch in (3,4): val=(y%59)|((y%73)<<16)
                if ch==6: val=[r[0],r[1],r[2],r[3]][k]
                if ch==7 and k==3 and not aliased: val=0x70000 if case%2 else 0x1f8000
                off=(a+4*(y*n+k))&MASK
                v[off:off+4]=struct.pack('<I',val)
    # Avoid wrap-table overwrites of front being interpreted as initial fixture discrepancy.
    front=np.frombuffer(v[:W*H*2],dtype='<u2').copy()
    draws=[]
    if case%2:
        for i in range(8): draws.append((i*40,10,40,210,i%4,i//4,rng.getrandbits(24)))
    return v,r,front,draws

def packet_data(draws):
    chunks=[]
    for i,(x,y,w,h,mode,upper,color) in enumerate(draws):
        # Flat blended strip quad: type 0x2c, five payload words.
        nxt=0x1000+(i+1)*24 if i+1<len(draws) else 0xffffff
        header=nxt|(0x2c << 24)
        pos=lambda a,b: (a&65535)|((b&65535)<<16)
        chunks.append(struct.pack('<6I',header,color|(mode<<24)|(upper<<26),
                                  pos(x,y),pos(x+w,y),pos(x,y+h),pos(x+w,y+h)))
    return b''.join(chunks)

def expected(v,r,front,draws):
    front=front.copy()
    for x0,y0,width,height,mode,upper,color in draws:
        a=pack([(color >> (8*k)&255)//8 for k in range(3)])
        for y in range(y0,y0+height):
            lr=line(r,v,y)
            for x in range(x0,x0+width):
                f=int(front[y*W+x])
                b=stack(v,lr,x,y,f,4 if upper else 3) if f==0x8000 or (upper and not f&0x8000) else f&0x7fff
                out=blend(b,a,mode)|(upper<<15)
                if out==0x8000: out=0x8400
                front[y*W+x]=out
        # Update VRAM because vsync reads the completed polygon buffer.
        v[:W*H*2]=front.tobytes()
    out=np.empty(W*H,dtype='<u2')
    for y in range(H):
        lr=line(r,v,y)
        for x in range(W): out[y*W+x]=stack(v,lr,x,y,int(front[y*W+x]))
    return front,out

def rgb(pixels):
    p=pixels.reshape(H,W)
    channels=[(p >> k)&31 for k in (0,5,10)]
    return np.stack([(c << 3)|(c >> 2) for c in channels],axis=2).astype(np.uint8)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--cases',type=int,default=32)
    ap.add_argument('--output',type=Path,default=common.OUT/'planes')
    ap.add_argument('--probe',type=Path,help='Use an already built replay probe (e.g. a mutation build).')
    args=ap.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    probe=args.probe or common.probe('planes_probe')
    reports=[]
    sheet=Image.new('RGB',(W*3,H*4+32*4),(12,14,20))
    pen=ImageDraw.Draw(sheet)
    for case in range(args.cases):
        v,r,front,draws=fixture(case)
        packets=packet_data(draws)
        replay=args.output/f'case_{case:03}.bin'
        replay.write_bytes(struct.pack('<64I',*r)+v+struct.pack('<I',len(packets))+packets)
        raw=args.output/f'case_{case:03}.rgb555'
        subprocess.run([str(probe),str(replay),str(raw)],check=True)
        actual=np.frombuffer(raw.read_bytes(),dtype='<u2').reshape(2,-1)
        reference=np.stack(expected(v,r,front,draws))
        counts=np.count_nonzero(actual!=reference,axis=1)
        report={'case':case,'draws':len(draws),'framebuffer_different_pixels':int(counts[0]),'display_different_pixels':int(counts[1])}
        reports.append(report)
        print(json.dumps(report),flush=True)
        if case<4 or counts.sum():
            for name,p in [('reference',reference[1]),('mei',actual[1])]:
                Image.fromarray(rgb(p)).save(args.output/f'case_{case:03}_{name}.png')
            diff=np.zeros((H,W,3),dtype=np.uint8)
            diff[(actual[1]!=reference[1]).reshape(H,W)]=(255,32,160)
            Image.fromarray(diff).save(args.output/f'case_{case:03}_diff.png')
            if case<4:
                y=case*(H+32)
                for i,(name,p) in enumerate([('Scalar specification',rgb(reference[1])),('Mei',rgb(actual[1])),('Pixel difference',diff)]):
                    pen.text((i*W+8,y+8),f'Case {case}: {name}',fill='white')
                    sheet.paste(Image.fromarray(p),(i*W,y+32))
    sheet.save(args.output/'comparison.png')
    summary={'cases':args.cases,'pixel_comparisons':args.cases*W*H*2,'reports':reports}
    (args.output/'report.json').write_text(json.dumps(summary,indent=2)+'\n')
    return int(any(r['framebuffer_different_pixels'] or r['display_different_pixels'] for r in reports))

if __name__=='__main__': raise SystemExit(main())
