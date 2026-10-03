#!/usr/bin/env python3
"""Independent specification renderer; no emulator pixels/packets used as truth.

Uses exact integer barycentric evaluation at every pixel (NumPy), rather than
Mei's incremental scanline rasterizer. Reads raw Mesh input and independently
performs model/view transforms, clipping, culling, OT sorting, fog, shading.
See README.md for scope and the contract used by this oracle. Run on its own, it
checks the nine views of the stress scene that gen_scene.py writes.
"""
import argparse
import csv
import json
import struct
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
import common

CART = common.cart_dir('scene')
S = 65536
DM = np.array([[-4,0,-3,1],[2,-2,3,-1],[-3,1,-4,0],[3,-1,2,-2]], dtype=np.int64)
PLANES = [[-S,0,0,344064],[S,0,0,475136],
          [0,S,0,480597],[0,-S,0,611669],[0,0,0,S]]


def fixed(x):
    return round(x*S)


def trunc(n, d):
    if not d:
        return 0
    return (abs(n)//abs(d)) * (-1 if (n<0)!=(d<0) else 1)


def dot(a,b):
    return sum(x*y for x,y in zip(a,b))//S


def transform(matrix, v):
    return [dot(row,v) for row in matrix]


def project(c):
    x,y,_,w = c
    return [max(-1024,min(1023,160+(160*x//w if w else 0))),
            max(-1024,min(1023,120+(-120*y//w if w else 0)))]


def read_mesh(path):
    data = path.read_bytes()
    nv,nf,vo,fo,wo = struct.unpack_from('<HHIII',data)
    vertices = [list(struct.unpack_from('<4i',data,vo+i*16)) for i in range(nv)]
    faces = []
    for i in range(nf):
        flags,blend,tex,pal,*tail = struct.unpack_from('<BBBB4H4I4H',data,fo+i*36)
        n = 4 if flags&4 else 3
        cols = [[(c>>k)&255 for k in (0,8,16)] for c in tail[4:8]]
        uv = [[t&255,t>>8] for t in tail[8:12]]
        # Texture byte bits 5-7: window 1-7 from the halfword table at header +12.
        window = struct.unpack_from('<H',data,wo+2*((tex>>5)-1))[0] if tex>>5 else 0
        faces.append({'flags':flags,'blend':blend,'slot':tex&15,'four':bool(tex&16),
                      'pal':pal,'window':window,'idx':tail[:n],'cols':cols[:n],'uv':uv[:n]})
    return vertices,faces


def clip_polygon(vertices, plane, near):
    distances = [dot(v['c'],PLANES[plane])-(near if plane==4 else 0) for v in vertices]
    if all(d>=0 for d in distances):
        return vertices
    output = []
    for i,b in enumerate(vertices):
        j = (i-1)%len(vertices)
        a,da,db = vertices[j],distances[j],distances[i]
        if (da>=0)!=(db>=0):
            inside,outside,di,do = (a,b,da,db) if da>=0 else (b,a,db,da)
            t = trunc(di*S,di-do)
            v = {key:[x+(y-x)*t//S for x,y in zip(inside[key],outside[key])]
                 for key in ('c','col','uv')}
            if plane==4:
                v['c'][3]=near
            output.append(v)
        if db>=0:
            output.append(b)
    return output


def clip_front(corners):
    # Fixed-point determinant test defined by the clipping API.
    rows = []
    for v in corners[:3]:
        c = v['c']
        scale = max(abs(c[k]) for k in (0,1,3))
        rows.append([trunc(c[k]*S,scale) for k in (0,1,3)])
    a,b,c=rows
    cross = [(b[1]*c[2]-b[2]*c[1])//S,(b[2]*c[0]-b[0]*c[2])//S,(b[0]*c[1]-b[1]*c[0])//S]
    return dot(a,cross)>0


def offview(corners):
    return any(all(sign*v['c'][axis] > v['c'][3] for v in corners)
               for axis in (0,1) for sign in (-1,1))


def packets_for(scene, case):
    view = [[fixed(x) for x in row] for row in case['matrix']]
    near,far = fixed(scene['near']),fixed(scene['far'])
    scale = trunc(1024*S*S,far-near)
    packets=[]
    counters={'faces':0,'culled':0,'clipped_faces':0,'packets':0,'triangles':0}

    def emit(face,corners,clipped=False):
        n=len(corners)
        pos=[project(v['c']) for v in corners]
        a,b,c=pos[:3]
        area=(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        if not face['flags']&16 and area>=0:
            counters['culled']+=1
            return
        depth=sum(v['c'][3]-near for v in corners)
        bucket=max(0,min(1023,depth*(scale//n)//(S*S)))
        flags=(face['flags']&~4)|(4 if n==4 else 0)
        if case['fog']:
            flags |= 1
        cols=[]
        for v in corners:
            col=[(x+S//2)//S for x in v['col']] if clipped else [x//S for x in v['col']]
            if case['fog']:
                amount=max(0,min(256,((v['c'][3]-6*S)*trunc(256*S,18)//S)//S))
                target=[65,80,110]
                if flags&2:
                    target=[x//2 for x in target]
                col=[a+(b-a)*amount//256 for a,b in zip(col,target)]
            cols.append(col)
        uv=[[(x+S//2)//S for x in v['uv']] if clipped else [x//S for x in v['uv']] for v in corners]
        packets.append({**face,'flags':flags,'pos':pos,'cols':cols,'uv':uv,'bucket':bucket,'sequence':len(packets)})

    for instance in scene['instances']:
        verts,faces=read_mesh(CART/(instance['mesh']+'.bin'))
        model=[[S,0,0,fixed(instance['position'][0])],[0,S,0,fixed(instance['position'][1])],
               [0,0,S,fixed(instance['position'][2])],[0,0,0,S]]
        if case.get('models') and instance['mesh'].startswith('cube'):
            model[0][:3] = [fixed(0.9),0,fixed(0.45)]
            model[1][:3] = [0,fixed(1.25),0]
            model[2][:3] = [fixed(-0.675),0,fixed(0.6)]
        # mat4_mul scales four rows separately, then adds: each product is floored.
        # vxfm below differs: its dot products accumulate before the final floor.
        matrix=[[sum(view[i][k]*model[k][j]//S for k in range(4)) for j in range(4)] for i in range(4)]
        transformed=[transform(matrix,v) for v in verts]
        for face in faces:
            counters['faces']+=1
            cs=[{'c':transformed[idx], 'col':[x*S for x in face['cols'][i if face['flags']&1 else 0]],
                 'uv':[x*S for x in face['uv'][i]]} for i,idx in enumerate(face['idx'])]
            pos=[project(v['c']) for v in cs]
            if all(v['c'][3]<near for v in cs):
                counters['culled']+=1
                continue
            needs_clip=any(v['c'][3]<near for v in cs) or any(not(-1000<=p[0]<=999 and -1000<=p[1]<=999) for p in pos)
            if not needs_clip:
                emit(face,cs)
                continue
            if offview(cs):
                counters['culled']+=1
                continue
            counters['clipped_faces']+=1
            if not face['flags']&16 and not clip_front(cs):
                counters['culled']+=1
                continue
            # Traverse polygon boundary, then fan-pair into triangle strips.
            polygon=[cs[i] for i in ([0,1,3,2] if len(cs)==4 else [0,1,2])]
            crosses_near=any(v['c'][3]<near for v in cs)
            planes=[4,0,1,2,3] if crosses_near else [p for p in range(4) if any(
                (pos[i][0]>999 if p==0 else pos[i][0]<-1000 if p==1 else pos[i][1]>999 if p==2 else pos[i][1]<-1000)
                for i in range(len(cs)))]
            for plane in planes:
                polygon=clip_polygon(polygon,plane,near)
                if len(polygon)<3 or (plane==4 and offview(polygon)):
                    polygon=[]
                    break
            i=1
            while i+1<len(polygon):
                indices=[i,i+1,0,i+2] if i+2<len(polygon) else [0,i,i+1]
                emit(face,[polygon[k] for k in indices],True)
                i+=2 if len(indices)==4 else 1
    packets.sort(key=lambda p:(p['bucket'],p['sequence']), reverse=True)
    counters['packets']=len(packets)
    counters['triangles']=sum(2 if p['flags']&4 else 1 for p in packets)
    return packets,counters


def load_vram(scene):
    texture=np.zeros(524288,dtype=np.uint8)
    for tex in scene['textures']:
        data=np.frombuffer((CART/tex['file']).read_bytes(),dtype=np.uint8)
        addresses=(np.arange(len(data))+tex['slot']*32768)%524288
        texture[addresses]=data
    palette=np.frombuffer((CART/'palette.bin').read_bytes(),dtype='<u2').astype(np.int64)
    return texture,palette


def colour15(col):
    return sum((x>>3)<<(k*5) for k,x in enumerate(col))


def windowed(t,window):
    # A texture window axis (DECISIONS.md, "Texture windows"): bits 0-2 the size, 4 << k
    # texels (7 is 256 too; 0 is no window), bits 3-7 the origin / 8; origin + size wraps.
    k=window&7
    if not k:
        return t
    return ((window>>3&31)*8+t%min(4<<k,256))&255


def render(scene,case,packets,texture,palette):
    fb=np.full((240,320),colour15(scene['background']),dtype=np.int64)
    for p in packets:
        for indices in ([0,1,2],[1,2,3]) if p['flags']&4 else ([0,1,2],):
            vertices=np.array([p['pos'][i] for i in indices],dtype=np.int64)
            attrs=np.array([p['cols'][i]+p['uv'][i] for i in indices],dtype=np.int64)
            a,b,c=vertices
            area=int((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))
            if area==0:
                continue
            if area<0:
                vertices[[1,2]]=vertices[[2,1]]
                attrs[[1,2]]=attrs[[2,1]]
                area=-area
            low=np.maximum(vertices.min(axis=0),[0,0])
            high=np.minimum(vertices.max(axis=0),[319,239])
            if np.any(low>high):
                continue
            yy,xx=np.mgrid[low[1]:high[1]+1,low[0]:high[0]+1]
            weights=[]
            inside=np.ones(xx.shape,dtype=bool)
            for i in range(3):
                a,b=vertices[(i+1)%3],vertices[(i+2)%3]
                dx,dy=b-a
                edge=dx*(yy-a[1])-dy*(xx-a[0])
                weights.append(edge)
                inside &= (edge>=0 if dy<0 or (dy==0 and dx>0) else edge>0)
            y,x=yy[inside],xx[inside]
            if not len(x):
                continue
            bary=np.array([w[inside] for w in weights]).T
            interpolated=(bary@attrs)//area
            colours=interpolated[:,:3] if p['flags']&1 else np.tile(p['cols'][0],(len(x),1))
            if p['flags']&2:
                u,v=interpolated[:,3],interpolated[:,4]
                u,v=windowed(u,p.get('window',0)),windowed(v,p.get('window',0)>>8)
                if p['four']:
                    idx=(texture[p['slot']*32768+v*128+u//2]>>(u%2*4))&15
                    base=p['pal']*16
                else:
                    idx=texture[(p['slot']*32768+v*256+u)%524288]
                    base=(p['pal']&15)*256
                keep=idx!=0
                y,x,colours,idx=y[keep],x[keep],colours[keep],idx[keep]
                texel=palette[base+idx.astype(np.int64)]
                channels=(texel[:,None]>>np.array([0,5,10]))&31
                channels=(channels<<3)|(channels>>2)
                colours=np.minimum(255,(channels*colours)//128)
            if case['dither']:
                colours=np.clip(colours+DM[y%4,x%4,None],0,255)
            colours=colours>>3
            if p['flags']&8:
                bg=(fb[y,x,None]>>np.array([0,5,10]))&31
                mode=p['blend']
                colours=(bg+colours)//2 if mode==0 else np.minimum(31,bg+colours) if mode==1 else np.maximum(0,bg-colours) if mode==2 else np.minimum(31,bg+(colours//4))
            fb[y,x]=colours@np.array([1,32,1024])
    return fb.astype('<u2')


def rgb_image(fb):
    channels=(fb.astype(np.int64)[:,:,None]>>np.array([0,5,10]))&31
    return Image.fromarray(((channels<<3)|(channels>>2)).astype(np.uint8))


def write_probe(path,scene,case,packets,texture,palette):
    records=[]
    for p in packets:
        words=[]
        for i,pos in enumerate(p['pos']):
            if i==0 or p['flags']&1:
                words.append(sum(c<<(k*8) for k,c in enumerate(p['cols'][i])) | (p['blend']<<24))
            words.append((pos[0]&65535)|((pos[1]&65535)<<16))
            if p['flags']&2:
                uv=p['uv'][i][0]|(p['uv'][i][1]<<8)
                if i==0:
                    uv |= p['slot']<<16 | int(p['four'])<<20 | p['pal']<<24
                if i==1:
                    uv |= p.get('window',0)<<16
                words.append(uv)
        records.append([((p['flags']&15)|0x20)<<24,*words])
    address=0x1000
    for i,words in enumerate(records):
        address+=len(words)*4
        words[0]|=address if i<len(records)-1 else 0xFFFFFF
    payload=b''.join(struct.pack('<'+'I'*len(words),*words) for words in records)
    path.write_bytes(struct.pack('<III',colour15(scene['background']),int(case['dither']),len(payload))+
                     palette.astype('<u2').tobytes()+texture.tobytes()+payload)


def compare(expected,actual):
    mask=np.any(expected!=actual,axis=2)
    ys,xs=np.where(mask)
    return {'different_pixels':int(mask.sum()),'total_pixels':76800,
            'max_channel_error':int(np.abs(expected.astype(int)-actual.astype(int)).max()),
            'bbox':[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())] if len(xs) else None}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=common.OUT/'scene')
    parser.add_argument('--case',action='append',help='Case name (repeatable); default all')
    args=parser.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    if not (CART/'scene.json').exists():
        parser.error(f'no scene in {CART}: run gen_scene.py first')
    rom=common.compile_cart('scene')
    probe=common.probe('gpu_probe')
    scene=json.loads((CART/'scene.json').read_text())
    texture,palette=load_vram(scene)
    results=[]
    for number,case in enumerate(scene['cases']):
        name=case['name']
        if args.case and name not in args.case:
            continue
        packets,counts=packets_for(scene,case)
        expected=render(scene,case,packets,texture,palette)
        oracle=rgb_image(expected)
        oracle.save(args.out/f'{name}_oracle.png')
        fixture=args.out/f'{name}.packets'
        write_probe(fixture,scene,case,packets,texture,palette)
        raw=args.out/f'{name}_gpu.rgb555'
        subprocess.run([str(probe.resolve()),str(fixture),str(raw)],check=True)
        gpu=rgb_image(np.frombuffer(raw.read_bytes(),dtype='<u2').reshape(240,320))
        gpu.save(args.out/f'{name}_gpu.png')
        events=[]
        for i in range(number):
            events.extend([f'{20+i*20}:10',f'{25+i*20}:0'])
        ppm=args.out/f'{name}_mei.ppm'
        stats=args.out/f'{name}_stats.csv'
        subprocess.run([str(common.HEADLESS),str(rom),'--frames',str(40+number*20),
                        '--input',','.join(events) or '0:0','--dump',str(ppm),'--gpu-stats',str(stats),'--quiet'],check=True)
        mei=Image.open(ppm).convert('RGB')
        mei.save(args.out/f'{name}_mei.png')
        reference=np.array(oracle)
        end_to_end=compare(reference,np.array(mei))
        gpu_diff=compare(reference,np.array(gpu))
        delta=np.max(np.abs(reference.astype(int)-np.array(mei).astype(int)),axis=2)
        heat=np.zeros_like(reference)
        heat[delta>0]=[255,40,90]
        diff=Image.fromarray(heat)
        diff.save(args.out/f'{name}_diff.png')
        sheet=Image.new('RGB',(960,270),(15,19,28))
        draw=ImageDraw.Draw(sheet)
        for i,(label,picture) in enumerate([('Independent oracle',oracle),('Mei',mei),('Difference (pink)',diff)]):
            draw.text((i*320+8,8),label,fill='white')
            sheet.paste(picture,(i*320,30))
        sheet.resize((1920,540),Image.Resampling.NEAREST).save(args.out/f'{name}_comparison.png')
        rows=list(csv.DictReader(stats.open()))
        if not rows:
            raise RuntimeError(f'{name}: Mei never presented a frame')
        last=rows[-1]
        if int(last['tris_dropped']):
            raise RuntimeError(f'{name}: scene exceeded the GPU triangle limit')
        result={'mei_stats':{key:int(last[key]) for key in ('tris','tris_empty','tris_dropped','gpu_cycles','cpu_cycles','ticks')},'case':name,'geometry':counts,'end_to_end':end_to_end,'gpu_only':gpu_diff}
        results.append(result)
        print(json.dumps(result),flush=True)
    if not results:
        parser.error('no matching cases')
    report={'contract':'docs/DECISIONS.md and public mesh/clip API','cases':results}
    (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return 1 if any(r['end_to_end']['different_pixels'] or r['gpu_only']['different_pixels'] for r in results) else 0

if __name__=='__main__':
    raise SystemExit(main())
