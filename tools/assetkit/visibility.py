"""Native triangle-identity verification and depth-order diagnostics.

The native probe supplies projected integer XY and 16.16 W from the real vertex
pipeline. Coverage is evaluated independently with the GPU's integer top-left
rule. Visibility is selected by reciprocal depth, not ordering-table buckets.
Colors, lighting and screenshot interpretation play no part in pass/fail.

With the policy's `depth` (the asset is drawn with the depth buffer, docs/RENDERING.md) the cart
draws as such a game does and depth order is a regression check of the depth test: faces count
as a tie unless their depths differ by more than the depth key's precision (kitcore/depth.py),
surface intersections and ordering cycles are not failures, coplanar overlaps still are.
"""
from collections import Counter, defaultdict
import hashlib
import json
import math
import re
from pathlib import Path
import struct
import subprocess
import tempfile

from kitcore import depth as DEPTH
from .compiler import compile_recipe, native_bytes
from .geometry import AssetError
from .geometry_audit import numpy, geometry_audit, face_ref, CODES, close_faces
from .preview import source, camera_numbers, png_bytes
from .views import cameras, cutout_texels, select_views
from .schema import validate, VERIFICATION

ROOT=Path(__file__).resolve().parents[2]
DEFAULT_PROFILE={'yaw_steps':24,'pitches':[-.35,0,.35],'distances':[1,1.5],'far':100,'geometry':'error','edge_margin':1.0}
DEPTH_EPSILON=2/65536
DEPTH_VIEWS=16                   # the views judged in depth mode (views.py)
ALLOWED_LINES=12                 # the report's `allowed` lines; geometry.allowed has every part pair


def allowed_codes(policy):
    """The geometry codes the policy does not fail: all with geometry 'warn'; surface crossings
    and T-junctions in depth mode; none otherwise."""
    if policy.get('geometry')=='warn': return CODES
    if policy.get('depth'): return ('surface_intersection','t_junction')
    return ()


def verdict(ok, failures, geometry, depth, policy):
    """One line saying what decided the result."""
    mode='depth mode' if depth else 'ordering-table mode'
    if policy.get('geometry')=='warn': mode+=', geometry warn'
    allowed=sum(row['count'] for row in geometry['allowed'])
    tail=f"; {allowed} findings allowed in {mode} ({', '.join(geometry['allowed_codes'])})" if allowed else ''
    if ok: return f'PASS ({mode}){tail}'
    return f"FAIL ({mode}): {len(failures)} problem{'s' if len(failures)!=1 else ''}, see failures{tail}"


def identity_mesh(binary, cutouts=(), solid=False):
    """Keep geometry, flags, and ordering unchanged; replace color with RGB555 ID.

    A palette swatch face (4-bit, the same nonzero texel index at every corner) covers
    exactly the pixels of the untextured face: the GPU interpolates equal texture
    coordinates to that texel everywhere, only index 0 skips pixels, and mesh() sorts and
    clips textured faces like untextured ones. Such faces are checked untextured; so is every
    other textured face when solid (a texture without holes never samples index 0).

    cutouts: faces whose texture has holes (texel 0). They stay textured, through palette 0,
    whose colour 1 the verification cart makes white over a mask of the textures (every texel
    that is not 0 becomes 1), and their tint carries the ID: a white texel tinted t shows
    255 t >> 7 per channel, so t = ceil(1024 k / 255) shows 5-bit value k."""
    data=bytearray(binary)
    _,count,_,offset,_=struct.unpack_from('<HHIII',data)
    for i in range(count):
        at=offset+i*36
        flags=data[at]
        n=i+1
        color=((n&31)<<3)|(((n>>5)&31)<<11)|(((n>>10)&31)<<19)
        if flags&2 and i in cutouts:
            if flags&~19: raise AssetError('/verification','Only opaque triangle meshes are supported.')
            data[at+3]=0
            color=sum(-(-1024*((n>>(5*c))&31)//255)<<(8*c) for c in range(3))
            struct.pack_into('<4I',data,at+12,*([color]*4))
            continue
        if flags&2:
            uv=struct.unpack_from('<3H',data,at+28)
            if not solid and (not data[at+2]&16 or len(set(uv))!=1 or not 0<(uv[0]&255)<16):
                raise AssetError('/verification','Textured faces are supported only as palette swatch faces.')
            flags&=~2;data[at]=flags;data[at+2]=data[at+3]=0
            struct.pack_into('<4H',data,at+28,0,0,0,0)
        if flags&~17: raise AssetError('/verification','Only opaque, untextured triangle meshes are supported.')
        struct.pack_into('<4I',data,offset+i*36+12,*([color]*4))
    return bytes(data)


def reciprocal(w):
    """The GPU's vertex reciprocal (RENDERING.md, "The depth test"): 2^40 / w (16.16), 2^28 below 1/16."""
    return (1<<40)//w if w>=4096 else 1<<28


def texel_coverage(np, v, uv, w, xx, yy, inside, area, texture):
    """Which covered pixels of a textured triangle with depth sample a texel other than 0, as the
    GPU samples (RENDERING.md, "Perspective-correct texturing"): exact planes of q-weighted u and
    v, divided at each span's first pixel, every 16th and its last, stepped between with
    truncation; affine when the scaled reciprocals are equal; then the texture window and the
    texel. v, uv, w: the three corners as drawn (after the winding swap); texture: (slot, 4-bit,
    window halfword, the texture area with every texel not 0 made 1)."""
    slot,four,window,vram=texture
    x,y=xx[inside],yy[inside]
    def weights(px,py):
        return [(int(v[(i+2)%3][0])-int(v[(i+1)%3][0]))*(py-int(v[(i+1)%3][1]))-(int(v[(i+2)%3][1])-int(v[(i+1)%3][1]))*(px-int(v[(i+1)%3][0])) for i in range(3)]
    r=[reciprocal(int(k)) for k in w]
    shift=0
    while max(r)>>shift>=65536: shift+=1
    q=[max(1,k>>shift) for k in r]
    e=np.stack(weights(x,y),axis=1).astype(np.int64)
    if len(set(q))>1:
        x0=np.full(240,320,dtype=np.int64);x1=np.zeros(240,dtype=np.int64)
        np.minimum.at(x0,y,x);np.maximum.at(x1,y,x)
        x0,x1=x0[y],x1[y]
        a=x0+(x-x0)//16*16;b=np.minimum(a+16,x1)
        qv=[int(k) for k in q]
        def corrected(px):
            wts=[c.astype(object) for c in weights(px,y)]
            Q=sum(wt*qk for wt,qk in zip(wts,qv))
            out=[]
            for axis in (0,1):
                U=sum(wt*(qk*int(t[axis])) for wt,qk,t in zip(wts,qv,uv))
                out.append(np.array(U*65536//Q,dtype=np.int64))
            return out
        sa,sb=corrected(a),corrected(b)
        span=np.maximum(b-a,1)
        def step(fa,fb):
            d=fb-fa
            return np.where(x==x1,fb,fa+(x-a)*(np.sign(d)*(np.abs(d)//span)))
        u,t=(step(sa[k],sb[k])>>16 for k in (0,1))
    else:
        u=(e@np.array([int(c[0]) for c in uv],dtype=np.int64))//area
        t=(e@np.array([int(c[1]) for c in uv],dtype=np.int64))//area
    def windowed(c,k):
        size=k&7
        return c&255 if not size else ((k>>3&31)*8+c%min(4<<size,256))&255
    u,t=windowed(u,window&255),windowed(t,window>>8)
    if four:
        texel=(vram[slot*32768+t*128+(u>>1)]>>((u&1)*4))&15
    else:
        texel=vram[(slot*32768+t*256+u)&0x7FFFF]
    keep=inside.copy()
    keep[inside]=texel!=0
    return keep


def cycle_witness(edges):
    """Return an actual directed cycle, not the acyclic descendants of a cycle."""
    nodes=set(edges)|{v for targets in edges.values() for v in targets}
    state={};parent={}
    for root in sorted(nodes):
        if state.get(root): continue
        state[root]=1;stack=[(root,iter(sorted(edges.get(root,()))))]
        while stack:
            a,neighbors=stack[-1]
            b=next(neighbors,None)
            if b is None: state[a]=2;stack.pop();continue
            if not state.get(b):
                parent[b]=a;state[b]=1;stack.append((b,iter(sorted(edges.get(b,())))))
            elif state[b]==1:
                path=[a]
                while path[-1]!=b:path.append(parent[path[-1]])
                return list(reversed(path))+[b]
    return []


def raster_surfaces(mesh, sv, materials, margin=0.0, textured=None):
    """Each front face's covered pixels (the GPU's integer top-left rule) and depths there, and,
    with a margin, each covered pixel's distance inside the face's outline ('inside', pixels) and
    the pixels within margin outside it with the face's plane depth extended there ('ring',
    'ring_depth'). textured: {face: (corner texture coordinates as drawn, texture)} for faces
    with cutouts, whose pixels on texel 0 are not covered (texel_coverage)."""
    np=numpy()
    packed=sv[:,2].astype(np.uint32)
    x=(packed&65535).astype(np.int32);x=np.where(x>=32768,x-65536,x)
    y=(packed>>16).astype(np.int32);y=np.where(y>=32768,y-65536,y)
    positions=np.column_stack((x,y)).astype(np.int64)
    depth=sv[:,3].astype(float)/65536
    if np.any(sv[:,0]!=1) or np.any(depth<.1):
        raise AssetError('/verification/camera','Near-plane/guard-band clipping is unsupported by this checker. Move the camera farther away; this view cannot pass.')
    surfaces=[]
    for i,face in enumerate(mesh.faces):
        # Export reverses source winding for Mei.
        ids=list(reversed(face.indices))
        vertices=positions[ids]
        a,b,c=vertices
        area=int((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))
        if not area or (area>=0 and not materials[face.material].get('double_sided',False)):continue
        swap=area<0
        if area<0:
            vertices=vertices[[0,2,1]];ids=[ids[0],ids[2],ids[1]];area=-area
        grow=int(math.ceil(margin))
        low=np.maximum(vertices.min(axis=0)-grow,[0,0]);high=np.minimum(vertices.max(axis=0)+grow,[319,239])
        if np.any(low>high):continue
        yy,xx=np.mgrid[low[1]:high[1]+1,low[0]:high[0]+1]
        inside=np.ones(xx.shape,dtype=bool);weights=[];dist=np.full(xx.shape,np.inf)
        for j in range(3):
            a,b=vertices[(j+1)%3],vertices[(j+2)%3]
            dx,dy=b-a
            edge=dx*(yy-a[1])-dy*(xx-a[0])
            inside &= edge>=0 if dy<0 or (dy==0 and dx>0) else edge>0
            weights.append(edge)
            ln=math.hypot(dx,dy)
            if ln:dist=np.minimum(dist,edge/ln)
        outline=inside
        if textured and i in textured and inside.any():
            uv,texture=textured[i]
            uv=[uv[0],uv[2],uv[1]] if swap else uv
            inside=texel_coverage(np,vertices,uv,sv[ids,3],xx,yy,inside,area,texture)
        indices=(yy[inside]*320+xx[inside]).astype(np.int32)
        if not len(indices):continue
        bary=np.array([w[inside] for w in weights],dtype=float)/area
        z=1/np.sum(bary/depth[ids,None],axis=0)
        s={'face':i,'pixels':indices,'depth':z,'low':np.maximum(vertices.min(axis=0),[0,0]),'high':np.minimum(vertices.max(axis=0),[319,239])}
        if margin>0:
            s['inside']=dist[inside]
            ring=(~outline)&(dist>-margin)
            s['ring']=(yy[ring]*320+xx[ring]).astype(np.int32)
            with np.errstate(divide='ignore',invalid='ignore'):
                rz=1/np.sum((np.array([w[ring] for w in weights],dtype=float)/area)/depth[ids,None],axis=0)
            # past the plane's horizon the extended depth means nothing: count it as nearest
            s['ring_depth']=np.where(np.isfinite(rz)&(rz>0),rz,0.0)
        surfaces.append(s)
    return surfaces


def compare(mesh, surfaces, actual, graph=True, margin=0.0, key=0.0):
    """The view's verdict. With a margin (the World Checker's edge_margin), a pixel's depth order
    is judged only where the nearest face covers it at least `margin` pixels inside its outline
    and is nearer, by more than DEPTH_EPSILON, than every other face that comes within `margin`
    of the pixel; other differing pixels are `undecided_pixels`. Coverage is always exact. key
    (depth mode: kitcore.depth.KEY_TOLERANCE): two depths are a tie unless the farther exceeds
    the nearer by more than this fraction of it, besides DEPTH_EPSILON."""
    np=numpy()
    nearest=np.full(320*240,np.inf);expected=np.full(320*240,-1,dtype=np.int32)
    actual_depth=np.full(320*240,np.inf)
    actual=actual.reshape(-1).astype(np.int32)-1
    for s in surfaces:
        pixels,z=s['pixels'],s['depth']
        wins=z<nearest[pixels]
        nearest[pixels[wins]]=z[wins];expected[pixels[wins]]=s['face']
        matched=actual[pixels]==s['face']
        actual_depth[pixels[matched]]=z[matched]
    covered=expected>=0
    decided=np.ones(320*240,dtype=bool)
    if margin>0:
        deep=np.zeros(320*240,dtype=bool)
        for s in surfaces:
            own=expected[s['pixels']]==s['face']
            deep[s['pixels'][own]]=s['inside'][own]>=margin
        # the nearest depth of any other face within the margin of each pixel
        rival=np.full(320*240,np.inf)
        for s in surfaces:
            for pix,z in ((s['pixels'],s['depth']),(s['ring'],s['ring_depth'])):
                other=expected[pix]!=s['face']
                np.minimum.at(rival,pix[other],z[other])
        decided=deep&(rival>nearest*(1+key)+DEPTH_EPSILON) if key else deep&(rival>nearest+DEPTH_EPSILON)
    coverage_bad=(covered!=(actual>=0))|((actual>=0)&~np.isfinite(actual_depth))
    differences=covered&(actual>=0)&(actual!=expected)&~coverage_bad
    delta=np.zeros(len(actual))
    comparable=differences&np.isfinite(actual_depth)
    delta[comparable]=actual_depth[comparable]-nearest[comparable]
    wrong=comparable&(delta>nearest*key+DEPTH_EPSILON) if key else comparable&(delta>DEPTH_EPSILON)
    bad=wrong&decided
    undecided=wrong&~decided
    ties=differences&~wrong
    pairs=Counter(zip(actual[bad].tolist(),expected[bad].tolist()))
    issues=[]
    for (front,behind),pixels in pairs.most_common(32):
        mask=bad&(actual==front)&(expected==behind)
        first=int(np.flatnonzero(mask)[0])
        issues.append({'code':'wrong_order','drawn':face_ref(mesh,front),'expected':face_ref(mesh,behind),
                       'pixels':pixels,'sample_pixel':[first%320,first//320],
                       'max_depth_error':float(max(delta[mask])),
                       'repair':'Remove buried/overlapping faces or split these faces to reduce ordering ambiguity; rerun the same camera.'})
    graph_info={'edges':0,'cycle':[],'crossing_pairs':[]}
    if graph:
        edges=defaultdict(set);crossings=[]
        lows=np.array([s['low'] for s in surfaces]);highs=np.array([s['high'] for s in surfaces])
        for i,a in enumerate(surfaces):
            candidates=np.flatnonzero(np.all(highs[i]>=lows,axis=1)&np.all(highs>=lows[i],axis=1))
            for j in candidates[candidates>i]:
                b=surfaces[int(j)]
                _,ia,ib=np.intersect1d(a['pixels'],b['pixels'],assume_unique=True,return_indices=True)
                if not len(ia):continue
                dz=a['depth'][ia]-b['depth'][ib]
                a_far=bool(np.any(dz>DEPTH_EPSILON));b_far=bool(np.any(dz<-DEPTH_EPSILON))
                if a_far:edges[a['face']].add(b['face'])
                if b_far:edges[b['face']].add(a['face'])
                if a_far and b_far and len(crossings)<16:
                    crossings.append({'a':face_ref(mesh,a['face']),'b':face_ref(mesh,b['face']),
                                      'repair':'Depth order reverses across the overlap. Split/trim the intersecting projected surfaces; reordering alone cannot solve it.'})
        cycle=cycle_witness(edges)
        graph_info={'edges':sum(len(v) for v in edges.values()),
                    'cycle':[face_ref(mesh,i) for i in cycle],'crossing_pairs':crossings}
    return {'tested_pixels':int((covered&decided).sum()),'undecided_pixels':int((covered&~decided).sum()),
            'undecided_wrong_pixels':int(undecided.sum()),'wrong_pixels':int(bad.sum()),
            'coverage_errors':int(coverage_bad.sum()),'depth_ties':int(ties.sum()),
            'visible_faces':sorted(set(expected[covered].tolist())),
            'issues':issues,'ordering_graph':graph_info},expected,actual,bad|coverage_bad


DEPTH_SCOPE=('Opaque static mesh drawn with the depth buffer; fitted cameras of the sweep chosen to show every face it '
             'sees (depth_views); native projected vertices and '
             'exact integer coverage; independent reciprocal-depth selection. Depth ties within two steps of the depth '
             'key (2/4096 of the depth) are allowed; surface intersections and ordering cycles are reported, not failed. '
             'Near/guard clipping and animation are not certified. Unobserved faces are not proven safe.')


def diagnostic_png(expected,actual,bad):
    np=numpy()
    def paint(ids):
        ids=ids.reshape(240,320)
        colors=np.stack(((ids*73+83)%192+48,(ids*131+17)%192+48,(ids*197+41)%192+48),axis=2).astype(np.uint8)
        colors[ids<0]=[24,28,36]
        return colors
    a,e=paint(actual),paint(expected)
    highlight=a.copy();highlight[bad.reshape(240,320)]=[255,32,64]
    return png_bytes(960,240,np.concatenate((a,e,highlight),axis=1).tobytes())


def run(command):
    try:
        result=subprocess.run([str(a) for a in command],capture_output=True,text=True,timeout=45)
    except (OSError,subprocess.TimeoutExpired) as error:raise AssetError('/verification/native',str(error)) from error
    if result.returncode:raise AssetError('/verification/native',(result.stderr+'\n'+result.stdout).strip()[-4000:])


def cutout_setup(np, mesh, original):
    """For an asset with cutouts: the faces that have them, {face: (corner texture coordinates as
    drawn, texture)} for the reference, and the files and Akari lines with which the
    verification cart loads the texture area with every texel that is not 0 made 1, and colour
    1 white."""
    textures=mesh.textures['textures'] if mesh.textures else {}
    holed={name for name,tex in textures.items() if tex.cutout}
    faces={i for i,f in enumerate(mesh.faces) if f.material in holed}
    if not faces: return set(),{},None
    packing=mesh.textures['packing']
    vram=np.zeros(16*32768,dtype=np.uint8);files={};lines=[]
    for slot in packing.slots():
        first,data=packing.slot_image(slot)
        raw=np.frombuffer(data,dtype=np.uint8)
        if packing.slot_bits[slot]==4:
            mask=((raw&15)!=0).astype(np.uint8)|(((raw>>4)!=0).astype(np.uint8)<<4)
            at=first*128
        else:
            mask=(raw!=0).astype(np.uint8);at=first*256
        vram[slot*32768+at:slot*32768+at+len(mask)]=mask
        files[f'mask{slot}.tex']=mask.tobytes()
        lines.append(f'embed MASK{slot}: u8 = "mask{slot}.tex"')
        lines.append(f'fn mask{slot}_load() {{ memcpy((VRAM_TEXTURES + {slot} * TEXTURE_SLOT_SIZE + {at}) as *u8, MASK{slot}, {len(mask)}) }}')
    files['white.pal']=struct.pack('<2H',0,0x7FFF)
    _,_,_,offset,windows=struct.unpack_from('<HHIII',original)
    textured={}
    for i in faces:
        at=offset+i*36
        tex=original[at+2]
        k=tex>>5
        window=struct.unpack_from('<H',original,windows+2*(k-1))[0] if k and windows else 0
        uv=[(c&255,c>>8) for c in struct.unpack_from('<3H',original,at+28)]
        textured[i]=(uv,(tex&15,bool(tex&16),window,vram))
    lines.append('embed WHITE: u16 = "white.pal"')
    lines+=['fn asset_NAME_load() {',*(f'    mask{slot}_load()' for slot in packing.slots()),'    load_palette(0, WHITE, 2)','}']
    return faces,textured,(files,lines)


def verify(recipe, profile=None, directory=None, compiler=None, probe=None, folder=None):
    np=numpy()
    compiler=Path(compiler or ROOT/'build/meic').resolve();probe=Path(probe or ROOT/'build/mei-asset-probe').resolve()
    for path in (compiler,probe):
        if not path.is_file():
            raise AssetError('/verification/native',f'Missing {path.name} in {path.parent}. Build it with make (make B=DIR '
                             'for a build directory of your own), or point the kit at your build directory with '
                             '--build-dir DIR (or B, MEIC and PROBE in the environment).')
    mesh,materials,base=compile_recipe(recipe,folder)
    policy={**DEFAULT_PROFILE,**recipe.get('verification',{}),**(profile or {})}
    policy.pop('required',None)
    validate(policy,VERIFICATION,'/verification')
    depth,perspective=policy.get('depth',False),policy.get('perspective',False)
    if depth:policy.setdefault('depth_views',DEPTH_VIEWS)
    geometry=geometry_audit(mesh,t_junctions=depth,allowed=allowed_codes(policy))
    original=native_bytes(mesh,materials,recipe.get('lighting',{}))
    # Textured faces are judged as solid faces, but those of textures with holes (cutouts), whose
    # coverage the reference takes from the real texels.
    cutouts,textured,cart=cutout_setup(np,mesh,original)
    binary=identity_mesh(original,cutouts,solid=True)
    root=Path(directory).resolve() if directory else None
    if root:root.mkdir(parents=True,exist_ok=True)
    views=[];visible=set();images=[]
    with tempfile.TemporaryDirectory(prefix='mei-verify-') as tmp:
        work=Path(tmp);name=recipe['name']
        (work/(name+'.bin')).write_bytes(binary)
        akr=f'embed ASSET_{name.upper()}: Mesh = "{name}.bin"\n'
        if cart:
            for filename,data in cart[0].items():(work/filename).write_bytes(data)
            akr+='\n'.join(cart[1]).replace('asset_NAME_load',f'asset_{name}_load')+'\n'
        (work/(name+'.akr')).write_text(akr)
        world=policy.get('scale','fit')=='world'
        sweep=cameras(policy)
        # One cart draws every view: the probe writes the view's index into asset_view, and the
        # cart takes the camera from its table, the literals a cart for that camera alone has.
        code=source(name,base['bounds'],world=world,load=bool(cart))
        code='\n'.join(line for line in code.splitlines() if 'text(' not in line)
        code=code.replace('cls(rgb(24, 28, 36))','cls(0)\n    dither(false)'+
                          ('\n'+DEPTH.cart_lines(depth,perspective).rstrip() if depth or perspective else ''))
        if depth or perspective:code=code.replace(f'import "{name}.akr"\n',f'import "{name}.akr"\n'+DEPTH.cart_import(depth,perspective))
        code=re.sub(r'camera_clip\(0\.1, [^)]*\)',f"camera_clip(0.1, {policy['far']:.7f})",code)
        table=[n for camera in sweep for n in camera_numbers(base['bounds'],*camera,world=world)]
        code=re.sub(r'    camera_look\(.*\)\n','    let k = asset_view * 5\n    camera_look(vec3(ASSET_VIEWS[k], ASSET_VIEWS[k + 1], '
                    'ASSET_VIEWS[k + 2]), ASSET_VIEWS[k + 3], ASSET_VIEWS[k + 4])\n',code)
        code=code.replace('\nfn draw() {',f'\nconst ASSET_VIEWS: [{len(table)}]fixed = [{", ".join(table)}]\n'
                          'var asset_view: s32\n\nfn draw() {')
        (work/'check.akr').write_text(code+'\n')
        run([compiler,work/'check.akr','-o',work/'check.mei','--sym',work/'check.sym'])
        symbols={line.split()[1]:int(line.split()[0],16) for line in (work/'check.sym').read_text().splitlines() if len(line.split())==2}
        if 'G___sv' not in symbols or 'G_asset_view' not in symbols:
            raise AssetError('/verification/native','Compiler did not emit the __sv and asset_view diagnostic symbols.')
        run([probe,work/'check.mei',work/'capture.bin',symbols['G___sv'],len(mesh.vertices),symbols['G_asset_view'],len(sweep)])
        captures=(work/'capture.bin').read_bytes()
        size=16+16*len(mesh.vertices)+320*240*2
        if len(captures)!=size*len(sweep):raise AssetError('/verification/native','Invalid native probe capture.')
        drawn=[]
        for k in range(len(sweep)):
            capture=captures[k*size:(k+1)*size]
            if capture[:4]!=b'MAV1' or struct.unpack_from('<I',capture,4)[0]!=len(mesh.vertices):
                raise AssetError('/verification/native','Invalid native probe capture.')
            actual=np.frombuffer(capture,dtype='<u2',count=320*240,offset=16+16*len(mesh.vertices))
            if int(actual.max())>len(mesh.faces):raise AssetError('/verification/native','Probe returned an invalid triangle ID.')
            drawn.append(actual)
        selection=None
        if depth and policy['depth_views']<len(sweep):
            # every camera of the sweep is drawn (cheap); the reference judges those that show every face
            counts=np.stack([np.bincount(a,minlength=len(mesh.faces)+1)[1:] for a in drawn])
            texels=None
            if cutouts:
                svs=[np.frombuffer(captures,dtype='<i4',count=len(mesh.vertices)*4,offset=k*size+16).reshape(-1,4) for k in range(len(sweep))]
                texels=cutout_texels(np,mesh,svs,drawn,textured)
            selection=select_views(np,counts,mesh,materials,base['bounds'],sweep,policy['depth_views'],cutouts,world,texels)
            chosen=selection.pop('views')
        else:
            chosen=list(range(len(sweep)))
        for k in chosen:
            yaw,pitch,distance=sweep[k]
            camera={'yaw':yaw,'pitch':pitch,'distance_scale':distance,'near':.1,'far':policy['far']}
            capture=captures[k*size:(k+1)*size]
            sv=np.frombuffer(capture,dtype='<i4',count=len(mesh.vertices)*4,offset=16).reshape(-1,4)
            actual=drawn[k]
            surfaces=raster_surfaces(mesh,sv,materials,policy['edge_margin'],textured)
            row,expected,actual_ids,bad=compare(mesh,surfaces,actual,graph=not depth,margin=policy['edge_margin'],
                                                key=DEPTH.KEY_TOLERANCE if depth else 0.0)
            visible.update(row.pop('visible_faces'))
            row.update(index=len(views),camera=camera)
            if selection is not None:row['sweep_index']=k
            row['native_triangles'],row['native_cpu_cycles']=struct.unpack_from('<II',capture,8)
            if root and (row['wrong_pixels'] or row['coverage_errors'] or row['ordering_graph']['cycle']) and len(images)<12:
                filename=f'visibility_{len(views):04}.png'
                (root/filename).write_bytes(diagnostic_png(expected,actual_ids,bad))
                row['image']=filename;images.append(filename)
            views.append(row)
    totals={key:sum(v[key] for v in views) for key in ('tested_pixels','undecided_pixels','undecided_wrong_pixels','wrong_pixels','coverage_errors','depth_ties')}
    cycles=sum(bool(v['ordering_graph']['cycle']) for v in views)
    # geometry['ok'] is the policy's verdict: in depth mode crossing surfaces and T-junctions are
    # allowed (the depth test draws crossings right; duplicates and coplanar overlaps z-fight),
    # and with geometry 'warn' every code is
    geometry_ok=geometry['ok']
    # coverage is judged at every covered pixel: an asset all of whose pixels lie within the edge
    # margin (a thin pole) passes on coverage alone, and its tested_pixels say so
    covered=totals['tested_pixels']+totals['undecided_pixels']
    ok=geometry_ok and covered>0 and not totals['wrong_pixels'] and not totals['coverage_errors'] and not cycles
    failures=['geometry: '+line for line in geometry['summary']]
    if not covered:failures.append('views: no covered pixels in any view (the asset is not drawn)')
    if totals['wrong_pixels']:
        failures.append(f"views: {totals['wrong_pixels']} wrong-depth pixels in "
                        f"{sum(1 for v in views if v['wrong_pixels'])} views (see views[].issues)")
    if totals['coverage_errors']:
        failures.append(f"views: {totals['coverage_errors']} coverage errors in "
                        f"{sum(1 for v in views if v['coverage_errors'])} views")
    if cycles:failures.append(f'views: ordering cycles in {cycles} views (see views[].ordering_graph)')
    allowed=[f"{row['code']}: {row['count']} {'within '+row['parts'][0] if row['parts'][0]==row['parts'][1] else 'between '+' and '.join(row['parts'])}"
             for row in geometry['allowed']]
    if len(allowed)>ALLOWED_LINES:
        allowed=allowed[:ALLOWED_LINES]+[f'... and {len(allowed)-ALLOWED_LINES} more part pairs (geometry.allowed)']
    # faces facing the same way closer than 3 cm: allowed (no view of the sweep fails them), but they
    # tie in the depth key from a game's distances
    close=close_faces(mesh)
    geometry['close_faces']=close
    result={'ok':ok,'verdict':verdict(ok,failures,geometry,depth,policy),'failures':failures,
            'allowed':allowed,'warnings':close['summary'],
            'format':'mei-visibility-report','version':1,'name':name,'profile':policy,
            'recipe_sha256':base['recipe_sha256'],'mesh_sha256':hashlib.sha256(original).hexdigest(),
            'depth_epsilon':DEPTH_EPSILON,'geometry':geometry,'totals':{**totals,'views':len(views),'cyclic_views':cycles},
            'faces':len(mesh.faces),'observed_faces':len(visible),'unobserved_faces':len(mesh.faces)-len(visible),
            'views':views,'images':images,
            **({'depth_mode':{'depth':depth,'perspective':perspective,'key_steps':DEPTH.KEY_STEPS,
                              'key_tolerance':DEPTH.KEY_TOLERANCE,
                              'not_failures':['surface_intersection','t_junction','ordering cycles'],
                              **({'view_selection':selection} if selection is not None else {})}}
               if depth or perspective else {}),
            'native_tools':{'compiler_sha256':hashlib.sha256(compiler.read_bytes()).hexdigest(),
                            'probe_sha256':hashlib.sha256(probe.read_bytes()).hexdigest()},
            'scope':DEPTH_SCOPE if depth else 'Opaque static mesh; sampled fitted cameras; native projected vertices and exact integer coverage; independent reciprocal-depth selection. Depth ties within two normalized 16.16 units are allowed. Near/guard clipping and animation are not certified. Unobserved faces are not proven safe.'}
    if 'lod' in recipe:
        # Each level of detail is checked as an asset of its own, with the same policy.
        from .compiler import level_recipe
        result['lod']=[]
        for k in range(1,len(recipe['lod'].get('levels',[]))+1):
            level=verify(level_recipe(recipe,k),profile,root/f'lod{k}' if root else None,compiler,probe,folder)
            result['lod'].append({'level':k,'ok':level['ok'],'faces':level['faces'],'totals':level['totals'],
                                  'geometry_ok':level['geometry']['ok'],'failures':level['failures'],
                                  'mesh_sha256':level['mesh_sha256']})
            result['ok']=result['ok'] and level['ok']
            result['failures']+=[f'lod {k} {line}' for line in level['failures']]
        result['verdict']=verdict(result['ok'],result['failures'],geometry,depth,policy)
    if root:(root/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
