"""Pairwise triangle checks on quantized model geometry, independent of rendering."""
from collections import Counter

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


def geometry_audit(mesh, limit=200):
    np=numpy()
    triangles=np.array([[mesh.vertices[i] for i in f.indices] for f in mesh.faces],dtype=float)
    normals=np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    normals/=np.linalg.norm(normals,axis=1)[:,None]
    lo,hi=triangles.min(axis=1),triangles.max(axis=1)
    eps=1/65536/4
    findings=[];counts=Counter();seen={}

    def issue(code,i,j,message):
        counts[code]+=1
        if len(findings)<limit:
            findings.append({'code':code,'a':face_ref(mesh,i),'b':face_ref(mesh,j),'message':message})

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
                        issue('coplanar_overlap',i,j,'Coplanar faces overlap in area. Tile materials on one surface or remove the covered faces.')
                continue
            # Pure boundary contact is permitted. Actual crossings straddle both planes.
            if not (min(da)<-eps and max(da)>eps and min(db)<-eps and max(db)>eps): continue
            a,b=cuts(tri,db),cuts(other,da)
            if len(a)<2 or len(b)<2: continue
            axis=np.cross(normals[i],normals[j]);axis/=np.linalg.norm(axis)
            aa,bb=np.array(a)@axis,np.array(b)@axis
            if min(max(aa),max(bb))-max(min(aa),min(bb))>eps:
                issue('surface_intersection',i,j,'Surfaces cross. Split/trim them at the intersection and remove buried faces, or join the components.')
    return {'ok':not counts,'counts':dict(counts),'findings':findings,
            'truncated':sum(counts.values())>len(findings),
            'scope':'Triangle duplicates, positive-area coplanar overlaps and proper surface crossings after 16.16 quantization; boundary contact is allowed. Containment is not certified.'}
