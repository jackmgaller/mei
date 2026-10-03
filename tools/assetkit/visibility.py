"""Native triangle-identity verification and depth-order diagnostics.

The native probe supplies projected integer XY and 16.16 W from the real vertex
pipeline. Coverage is evaluated independently with the GPU's integer top-left
rule. Visibility is selected by reciprocal depth, not ordering-table buckets.
Colors, lighting and screenshot interpretation play no part in pass/fail.
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

from .compiler import compile_recipe, native_bytes
from .geometry import AssetError
from .geometry_audit import numpy, geometry_audit, face_ref
from .preview import source, png_bytes
from .schema import validate, VERIFICATION

ROOT=Path(__file__).resolve().parents[2]
DEFAULT_PROFILE={'yaw_steps':24,'pitches':[-.35,0,.35],'distances':[1,1.5],'far':100,'geometry':'error'}
DEPTH_EPSILON=2/65536


def identity_mesh(binary):
    """Keep geometry, flags, and ordering unchanged; replace color with RGB555 ID."""
    data=bytearray(binary)
    _,count,_,offset,_=struct.unpack_from('<HHIII',data)
    for i in range(count):
        flags=data[offset+i*36]
        if flags&~17: raise AssetError('/verification','Only opaque, untextured triangle meshes are supported.')
        n=i+1
        color=((n&31)<<3)|(((n>>5)&31)<<11)|(((n>>10)&31)<<19)
        struct.pack_into('<4I',data,offset+i*36+12,*([color]*4))
    return bytes(data)


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


def raster_surfaces(mesh, sv, materials):
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
        if area<0:
            vertices=vertices[[0,2,1]];ids=[ids[0],ids[2],ids[1]];area=-area
        low=np.maximum(vertices.min(axis=0),[0,0]);high=np.minimum(vertices.max(axis=0),[319,239])
        if np.any(low>high):continue
        yy,xx=np.mgrid[low[1]:high[1]+1,low[0]:high[0]+1]
        inside=np.ones(xx.shape,dtype=bool);weights=[]
        for j in range(3):
            a,b=vertices[(j+1)%3],vertices[(j+2)%3]
            dx,dy=b-a
            edge=dx*(yy-a[1])-dy*(xx-a[0])
            inside &= edge>=0 if dy<0 or (dy==0 and dx>0) else edge>0
            weights.append(edge)
        indices=(yy[inside]*320+xx[inside]).astype(np.int32)
        if not len(indices):continue
        bary=np.array([w[inside] for w in weights],dtype=float)/area
        z=1/np.sum(bary/depth[ids,None],axis=0)
        surfaces.append({'face':i,'pixels':indices,'depth':z,'low':low,'high':high})
    return surfaces


def compare(mesh, surfaces, actual, graph=True):
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
    coverage_bad=(covered!=(actual>=0))|((actual>=0)&~np.isfinite(actual_depth))
    differences=covered&(actual>=0)&(actual!=expected)&~coverage_bad
    delta=np.zeros(len(actual))
    comparable=differences&np.isfinite(actual_depth)
    delta[comparable]=actual_depth[comparable]-nearest[comparable]
    bad=comparable&(delta>DEPTH_EPSILON)
    ties=differences&~bad
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
    return {'tested_pixels':int(covered.sum()),'wrong_pixels':int(bad.sum()),
            'coverage_errors':int(coverage_bad.sum()),'depth_ties':int(ties.sum()),
            'visible_faces':sorted(set(expected[covered].tolist())),
            'issues':issues,'ordering_graph':graph_info},expected,actual,bad|coverage_bad


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


def verify(recipe, profile=None, directory=None, compiler=None, probe=None):
    np=numpy()
    compiler=Path(compiler or ROOT/'build/meic').resolve();probe=Path(probe or ROOT/'build/mei-asset-probe').resolve()
    for path in (compiler,probe):
        if not path.is_file():raise AssetError('/verification/native',f'Missing {path}. Run make build/meic build/mei-asset-probe.')
    mesh,materials,base=compile_recipe(recipe)
    policy={**DEFAULT_PROFILE,**recipe.get('verification',{}),**(profile or {})}
    policy.pop('required',None)
    validate(policy,VERIFICATION,'/verification')
    geometry=geometry_audit(mesh)
    original=native_bytes(mesh,materials,recipe.get('lighting',{}))
    binary=identity_mesh(original)
    root=Path(directory).resolve() if directory else None
    if root:root.mkdir(parents=True,exist_ok=True)
    views=[];visible=set();images=[]
    with tempfile.TemporaryDirectory(prefix='mei-verify-') as tmp:
        work=Path(tmp);name=recipe['name']
        (work/(name+'.bin')).write_bytes(binary)
        (work/(name+'.akr')).write_text(f'embed ASSET_{name.upper()}: Mesh = "{name}.bin"\n')
        for distance in policy['distances']:
            for pitch in policy['pitches']:
                for step in range(policy['yaw_steps']):
                    yaw=-.65+math.tau*step/policy['yaw_steps']
                    camera={'yaw':yaw,'pitch':pitch,'distance_scale':distance,'near':.1,'far':policy['far']}
                    code=source(name,base['bounds'],yaw,pitch,distance_scale=distance)
                    code='\n'.join(line for line in code.splitlines() if 'text(' not in line)
                    code=code.replace('cls(rgb(24, 28, 36))','cls(0)\n    dither(false)')
                    code=re.sub(r'camera_clip\(0\.1, [^)]*\)',f"camera_clip(0.1, {policy['far']:.7f})",code)
                    (work/'check.akr').write_text(code+'\n')
                    run([compiler,work/'check.akr','-o',work/'check.mei','--sym',work/'check.sym'])
                    symbols={line.split()[1]:int(line.split()[0],16) for line in (work/'check.sym').read_text().splitlines() if len(line.split())==2}
                    if 'G___sv' not in symbols:raise AssetError('/verification/native','Compiler did not emit the __sv diagnostic symbol.')
                    run([probe,work/'check.mei',work/'capture.bin',symbols['G___sv'],len(mesh.vertices)])
                    capture=(work/'capture.bin').read_bytes()
                    if (len(capture)!=16+16*len(mesh.vertices)+320*240*2 or capture[:4]!=b'MAV1'
                            or struct.unpack_from('<I',capture,4)[0]!=len(mesh.vertices)):
                        raise AssetError('/verification/native','Invalid native probe capture.')
                    sv=np.frombuffer(capture,dtype='<i4',count=len(mesh.vertices)*4,offset=16).reshape(-1,4)
                    actual=np.frombuffer(capture,dtype='<u2',count=320*240,offset=16+16*len(mesh.vertices))
                    if int(actual.max())>len(mesh.faces):raise AssetError('/verification/native','Probe returned an invalid triangle ID.')
                    surfaces=raster_surfaces(mesh,sv,materials)
                    row,expected,actual_ids,bad=compare(mesh,surfaces,actual)
                    visible.update(row.pop('visible_faces'))
                    row.update(index=len(views),camera=camera)
                    row['native_triangles'],row['native_cpu_cycles']=struct.unpack_from('<II',capture,8)
                    if root and (row['wrong_pixels'] or row['coverage_errors'] or row['ordering_graph']['cycle']) and len(images)<12:
                        filename=f'visibility_{len(views):04}.png'
                        (root/filename).write_bytes(diagnostic_png(expected,actual_ids,bad))
                        row['image']=filename;images.append(filename)
                    views.append(row)
    totals={key:sum(v[key] for v in views) for key in ('tested_pixels','wrong_pixels','coverage_errors','depth_ties')}
    cycles=sum(bool(v['ordering_graph']['cycle']) for v in views)
    geometry_ok=geometry['ok'] or policy['geometry']=='warn'
    ok=geometry_ok and totals['tested_pixels']>0 and not totals['wrong_pixels'] and not totals['coverage_errors'] and not cycles
    result={'ok':ok,'format':'mei-visibility-report','version':1,'name':name,'profile':policy,
            'recipe_sha256':base['recipe_sha256'],'mesh_sha256':hashlib.sha256(original).hexdigest(),
            'depth_epsilon':DEPTH_EPSILON,'geometry':geometry,'totals':{**totals,'views':len(views),'cyclic_views':cycles},
            'faces':len(mesh.faces),'observed_faces':len(visible),'unobserved_faces':len(mesh.faces)-len(visible),
            'views':views,'images':images,
            'native_tools':{'compiler_sha256':hashlib.sha256(compiler.read_bytes()).hexdigest(),
                            'probe_sha256':hashlib.sha256(probe.read_bytes()).hexdigest()},
            'scope':'Opaque static mesh; sampled fitted cameras; native projected vertices and exact integer coverage; independent reciprocal-depth selection. Depth ties within two normalized 16.16 units are allowed. Near/guard clipping and animation are not certified. Unobserved faces are not proven safe.'}
    if root:(root/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
