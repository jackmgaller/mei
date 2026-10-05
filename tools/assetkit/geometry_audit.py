"""Pairwise triangle checks on quantized model geometry, independent of rendering."""
from collections import Counter
import math

from .geometry import AssetError


def numpy():
    try:
        import numpy as np
    except ImportError as error:
        raise AssetError('/verification','Visibility verification requires NumPy; ordinary modeling/building does not.') from error
    return np


def face_ref(mesh, i):
    f=mesh.faces[i]
    return {'face':i,'part':f.part,'material':f.material}


def clip_polygon(subject, clip, eps):
    """Convex 2D intersection; area, not edge/point contact, constitutes overlap."""
    def cross(a,b): return a[0]*b[1]-a[1]*b[0]
    orientation=cross(clip[1]-clip[0],clip[2]-clip[0])
    sign=1 if orientation>0 else -1
    result=list(subject)
    for a,b in zip(clip,list(clip[1:])+[clip[0]]):
        previous=result;result=[]
        for p,q in zip(previous,previous[1:]+previous[:1]):
            dp,dq=sign*cross(b-a,p-a),sign*cross(b-a,q-a)
            if (dp>=-eps)!=(dq>=-eps):
                result.append(p+(q-p)*(dp/(dp-dq)))
            if dq>=-eps: result.append(q)
    return result


CODES=('duplicate_face','coplanar_overlap','surface_intersection','t_junction')
EXAMPLES=3          # example findings kept per part pair of an allowed code


def geometry_audit(mesh, t_junctions=False, allowed=(), crossings=True):
    """Pairwise findings on the quantized mesh. allowed: the codes the caller's policy does not
    fail (depth mode: surface_intersection and t_junction; geometry 'warn': all). Failing
    findings are reported in full, ordered by part pair; allowed ones as counts per part pair
    with a few examples. crossings=False skips the surface-crossing test (inspect's flush
    check, which needs only duplicates and coplanar overlaps)."""
    np=numpy()
    triangles=np.array([[mesh.vertices[i] for i in f.indices] for f in mesh.faces],dtype=float)
    normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    normals/=np.linalg.norm(normals,axis=1)[:,None]
    lo,hi=triangles.min(axis=1),triangles.max(axis=1)
    eps=1/65536/4
    found=[];seen={}

    def issue(code,i,j,message):
        found.append({'code':code,'a':face_ref(mesh,i),'b':face_ref(mesh,j),'message':message})

    def cuts(tri,dist):
        result=[]
        for k,(a,b) in enumerate(zip(tri,np.roll(tri,-1,axis=0))):
            da,db=dist[k],dist[(k+1)%3]
            if abs(da)<=eps: result.append(a)
            if da*db<0: result.append(a+(b-a)*da/(da-db))
        return result

    for i,tri in enumerate(triangles):
        key=tuple(sorted(mesh.faces[i].indices))
        if key in seen: issue('duplicate_face',seen[key],i,'Remove one coincident triangle; material differences do not resolve the overlap.')
        else: seen[key]=i
        candidates=np.flatnonzero(np.all(hi[i]+eps>=lo,axis=1)&np.all(hi+eps>=lo[i],axis=1))
        for j in candidates[candidates>i]:
            j=int(j)
            if tuple(sorted(mesh.faces[j].indices))==key: continue
            other=triangles[j]
            da=(other-tri[0])@normals[i]
            db=(tri-other[0])@normals[j]
            if np.all(da>eps) or np.all(da<-eps) or np.all(db>eps) or np.all(db<-eps): continue
            parallel=np.linalg.norm(np.cross(normals[i],normals[j]))<1e-8
            if parallel and max(np.max(np.abs(da)),np.max(np.abs(db)))<=eps:
                dims=[k for k in range(3) if k!=np.argmax(np.abs(normals[i]))]
                overlap=clip_polygon(tri[:,dims],other[:,dims],eps*eps)
                if len(overlap)>2:
                    area=abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(overlap,overlap[1:]+overlap[:1])))/2
                    if area>eps*eps:
                        facing='back to back' if normals[i]@normals[j]<0 else 'facing the same way'
                        issue('coplanar_overlap',i,j,f'Coplanar faces overlap in area ({facing}), as where two parts sit '
                              'flush: sink one 1-2 cm into the other or open the hidden face; on one surface, tile '
                              'materials or remove the covered faces.')
                continue
            if not crossings: continue
            # Pure boundary contact is permitted. Actual crossings straddle both planes.
            if not (min(da)<-eps and max(da)>eps and min(db)<-eps and max(db)>eps): continue
            a,b=cuts(tri,db),cuts(other,da)
            if len(a)<2 or len(b)<2: continue
            axis=np.cross(normals[i],normals[j]);axis/=np.linalg.norm(axis)
            aa,bb=np.array(a)@axis,np.array(b)@axis
            if min(max(aa),max(bb))-max(min(aa),min(bb))>eps:
                issue('surface_intersection',i,j,'Surfaces cross. Split/trim them at the intersection and remove buried faces, or join the components.')
    scope=('Triangle duplicates, positive-area coplanar overlaps and proper surface crossings after 16.16 quantization; '
           'boundary contact is allowed. Containment is not certified.' if crossings else
           'Triangle duplicates and positive-area coplanar overlaps after 16.16 quantization; surface crossings are not tested.')
    if t_junctions:
        for v,(i,j) in t_junction_pairs(np,mesh):
            issue('t_junction',i,j,f'Vertex {v} of the first face lies inside an edge of the second, which does not share it: '
                                   'the two can leave a crack of background pixels between them. Split that edge at the vertex.')
        scope+=' T-junctions: a vertex within 2^-16 units of the inside of another face\'s edge.'
    return summarise(found,allowed,scope)


def pair_of(finding):
    return tuple(sorted((finding['a']['part'],finding['b']['part'])))


def by_code(counter):
    return {code:counter[code] for code in CODES if counter.get(code)}


def summarise(found, allowed, scope):
    """The audit's report. ok: no failing finding. counts: every code found. failing: the codes
    that fail, counted. findings: every failing finding, in full, ordered by part pair. allowed:
    the allowed codes' findings as counts per part pair, each with up to EXAMPLES examples.
    summary: one line per part pair and failing code."""
    allowed=set(allowed)
    failing=[f for f in found if f['code'] not in allowed]
    failing.sort(key=lambda f:(pair_of(f),CODES.index(f['code']),f['a']['face'],f['b']['face']))
    groups={}
    for f in found:
        if f['code'] in allowed:
            groups.setdefault((f['code'],pair_of(f)),[]).append(f)
    rows=[{'code':code,'parts':list(pair),'count':len(group),'examples':group[:EXAMPLES]}
          for (code,pair),group in sorted(groups.items(),key=lambda kv:(-len(kv[1]),kv[0]))]
    return {'ok':not failing,
            'counts':by_code(Counter(f['code'] for f in found)),
            'failing':by_code(Counter(f['code'] for f in failing)),
            'allowed_codes':[code for code in CODES if code in allowed],
            'summary':failure_summary(failing),
            'findings':failing,
            'allowed':rows,
            'scope':scope}


def failure_summary(failing, faces=4):
    """One line per part pair and code, the largest first:
    'coplanar_overlap: 12 between roof and wall (faces 3/40, 5/41, 6/44, 9/45, ...)'."""
    groups={}
    for f in failing:
        groups.setdefault((pair_of(f),f['code']),[]).append(f)
    lines=[]
    for (pair,code),group in sorted(groups.items(),key=lambda kv:(-len(kv[1]),kv[0])):
        where=f'within {pair[0]}' if pair[0]==pair[1] else f'between {pair[0]} and {pair[1]}'
        sample=', '.join(f"{g['a']['face']}/{g['b']['face']}" for g in group[:faces])+(', ...' if len(group)>faces else '')
        lines.append(f'{code}: {len(group)} {where} (faces {sample})')
    return lines


def t_junction_pairs(np, mesh):
    """[(vertex, (a face using it, a face with an edge it lies inside of))]: the vertex is within
    T_JUNCTION (2^-16 units, one step of the 16.16 coordinates) of the edge's line, strictly
    between its ends (projected), and is not a corner of that face."""
    V=np.array(mesh.vertices,dtype=float)
    edges={}
    for i,f in enumerate(mesh.faces):
        for k in range(3):
            edges.setdefault(tuple(sorted((f.indices[k],f.indices[(k+1)%3]))),i)
    uses={}
    for i,f in enumerate(mesh.faces):
        for v in f.indices: uses.setdefault(v,i)
    keys=sorted(edges)
    out=[]
    for start in range(0,len(keys),256):
        batch=np.array(keys[start:start+256])
        a,b=V[batch[:,0]],V[batch[:,1]]
        d=b-a
        length2=np.einsum('ex,ex->e',d,d)
        rel=V[None,:,:]-a[:,None,:]
        t=np.einsum('evx,ex->ev',rel,d)/np.where(length2>0,length2,1)[:,None]
        off=rel-t[:,:,None]*d[:,None,:]
        near=np.einsum('evx,evx->ev',off,off)<=T_JUNCTION**2
        inside=(t>0)&(t<1)&near&(length2[:,None]>0)
        for e,v in zip(*np.nonzero(inside)):
            owner=edges[tuple(batch[e])]
            if v in uses and v not in mesh.faces[owner].indices:
                out.append((int(v),(uses[v],owner)))
    return sorted(out,key=lambda x:(x[1],x[0]))


T_JUNCTION=1/65536

# Faces facing the same way closer than this (units) z-fight from a game's distances even with the
# depth buffer: a key step is 1/4,096 of the depth, and a face seen at a grazing angle needs about
# ten (RENDERING.md, "Precision": 2.7 cm at 8 units for a floor at 11 degrees). So a gap g fights
# from about g / 0.0034 units at such an angle and g / 0.00029 face on.
CLOSE_GAP=0.03
CLOSE_COS=math.cos(math.radians(5))     # "parallel": normals within 5 degrees
CLOSE_AREA=1e-4                          # overlap in projection above 1 cm^2
GRAZING_PER_UNIT=0.0034                  # gap that fights, per unit of distance, at about 11 degrees
FACING_PER_UNIT=0.00029                  # and face on


def fights_from(gap):
    """(grazing, face on): the distances (units) from which faces gap apart tie in the depth key."""
    return gap/GRAZING_PER_UNIT,gap/FACING_PER_UNIT


def close_faces(mesh, threshold=CLOSE_GAP):
    """Pairs of faces that face the same way (normals within 5 degrees), overlap in projection by
    more than 1 cm^2 and lie less than threshold apart, but not in one plane (that is a coplanar
    overlap): a sign panel 1 cm in front of its board. The depth buffer allows them, and they tie
    in its key from far enough away (fights_from). A warning, never a failure. Returns
    {'threshold', 'count', 'summary', 'pairs'}: per part pair the faces, the gap and which part is
    in front."""
    np=numpy()
    triangles=np.array([[mesh.vertices[i] for i in f.indices] for f in mesh.faces],dtype=float)
    if not len(triangles):
        return {'threshold':threshold,'count':0,'summary':[],'pairs':[]}
    normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    normals/=np.linalg.norm(normals,axis=1)[:,None]
    lo,hi=triangles.min(axis=1)-threshold,triangles.max(axis=1)+threshold
    tiny=1/65536
    groups={}
    for i,tri in enumerate(triangles):
        near=np.flatnonzero(np.all(hi[i]>=lo,axis=1)&np.all(hi>=lo[i],axis=1)&(normals@normals[i]>CLOSE_COS))
        for j in near[near>i]:
            j=int(j)
            other=triangles[j]
            d=(other-tri[0])@normals[i]
            back=(tri-other[0])@normals[j]
            if not (np.all(d>tiny) or np.all(d<-tiny)) or not (np.all(back>tiny) or np.all(back<-tiny)): continue
            if max(np.max(np.abs(d)),np.max(np.abs(back)))>=threshold: continue
            dims=[k for k in range(3) if k!=np.argmax(np.abs(normals[i]))]
            overlap=clip_polygon(tri[:,dims],other[:,dims],1e-12)
            if len(overlap)<3: continue
            area=abs(sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(overlap,overlap[1:]+overlap[:1])))/2
            # the overlap in the plane, measured across the dropped axis
            area/=max(abs(normals[i][np.argmax(np.abs(normals[i]))]),1e-9)
            if area<=CLOSE_AREA: continue
            front,behind=(j,i) if d.mean()>0 else (i,j)
            gap=float(np.mean(np.abs(d)))
            key=(mesh.faces[front].part,mesh.faces[behind].part)
            groups.setdefault(key,[]).append((front,behind,gap))
    pairs,summary=[],[]
    for (front,behind),found in sorted(groups.items(),key=lambda kv:(-len(kv[1]),kv[0])):
        gaps=[g for _,_,g in found]
        grazing,facing=fights_from(min(gaps))
        where=(f'within {front}: faces' if front==behind else
               f'between {front} and {behind}: {front}\'s faces')
        sample=', '.join(f'{a}/{b}' for a,b,_ in found[:4])+(', ...' if len(found)>4 else '')
        apart=f'{min(gaps)*1000:.1f}'+(f'-{max(gaps)*1000:.1f}' if max(gaps)-min(gaps)>=0.00005 else '')
        far=lambda d: f'{d:.1f}' if d<10 else f'{d:.0f}'
        summary.append(f'close_faces: {len(found)} {where} {apart} mm in front of {behind+chr(39)+"s" if front!=behind else "others"}, '
                       f'facing the same way (faces {sample}): they z-fight from about {far(grazing)} units '
                       f'at a grazing view, {far(facing)} face on')
        pairs.append({'front':front,'behind':behind,'count':len(found),'gap_min':round(min(gaps),5),
                      'gap_max':round(max(gaps),5),'fights_from':{'grazing':round(grazing,1),'face_on':round(facing,1)},
                      'faces':[[a,b] for a,b,_ in found[:8]]})
    hint=(f'Faces closer than {threshold*100:.0f} cm that face the same way tie in the depth buffer from a distance. '
          f'Stand the front part at least {threshold*100:.0f} cm proud of the one behind (move it along their normal), '
          'or remove the covered face behind it.') if pairs else None
    return {'threshold':threshold,'count':sum(p['count'] for p in pairs),'summary':summary,'pairs':pairs,
            **({'hint':hint} if hint else {})}
