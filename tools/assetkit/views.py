"""The Asset Checker's cameras, and in depth mode the few views of them it judges.

cameras(policy) is the policy's sweep: yaw_steps yaws (around the circle from -0.65 radians, or
evenly over yaw_range_degrees) at each pitch at each distance, in that order.

Without depth every view of the sweep is judged: ordering-table mistakes depend on the exact
camera, so only a dense sweep finds them. With the depth buffer the depth test orders each pixel,
and what the views are still for is coverage: that every face, and every texel of a cutout face,
is drawn where the reference expects it. A face's coverage can only be judged where it is seen, so
select_views() chooses `depth_views` views of the sweep that see every face the sweep sees, each
also from a view that shows it well (docs/ASSETKIT.md, "Depth mode"). Drawing a view is cheap (the
probe runs every camera of the sweep, about 3 ms each); judging one is not (the reference
rasteriser in Python), so the choice is made from what the console drew:

1. counts[view, face]: the pixels the console drew of each face in each view of the sweep (its
   triangle-ID buffer).
2. A view *shows a face well* when it draws at least WELL of the face's largest count over the
   sweep (a cutout face, whose texels are checked one by one: WELL_CUTOUT).
3. Greedy cover, one view at a time, deterministic: take the view that draws the most faces no
   chosen view draws yet; on a tie, the one that shows well the most faces no chosen view shows
   well; then the most faces shown well only once; then the most pixels; then the earliest in the
   sweep. So the first views see every face the sweep sees, the next show each well and then well
   twice, and the rest add pixels.
4. A face the console draws in no view of the sweep could be one it fails to draw. If there are
   any, the views are first given, for each such face that an estimate made without the console
   says is visible (at least SUSPECT pixels in some view), the view the estimate shows it best in,
   so that the reference judges it there (beyond depth_views if need be). The estimate projects
   points spread over the faces (SPACING apart) with the cart's camera into a 160 x 120 depth
   buffer: a face's estimate is its projected area times the fraction of its points that are
   nearest in their cell.

The judged views are reported in sweep order, with their sweep_index; the report's
view_selection gives the cover's numbers.
"""
import math

SPACING = 0.012          # points this fraction of the drawn bounding radius apart
MAX_POINTS = 150000      # farther apart when there would be more
GRID = (160, 120)        # the estimate's depth buffer: half the screen's resolution
WELL = 0.5               # a camera shows a face well from this fraction of its best count
WELL_CUTOUT = 0.9        # for a face with cutouts
SUSPECT = 4              # estimated pixels from which a face the console never draws is judged
FOCAL = 1.7320508        # camera_fov(60 degrees), the cart's default


def cameras(policy):
    """[(yaw, pitch, distance_scale)] of the policy's sweep, in the order the views are drawn."""
    steps = policy['yaw_steps']
    if 'yaw_range_degrees' in policy:
        a,b = (math.radians(d) for d in policy['yaw_range_degrees'])
        yaws = [a+(b-a)*step/(steps-1) for step in range(steps)]
    else:
        yaws = [-.65+math.tau*step/steps for step in range(steps)]
    return [(yaw,pitch,distance) for distance in policy['distances'] for pitch in policy['pitches'] for yaw in yaws]


def samples(np, triangles, spacing):
    """Points spread evenly over the triangles, about `spacing` apart: (points, face of each
    point). From the corner opposite a face's longest edge, its two edges are cut into n and m
    parts (n, m = ceil(length / spacing)) and the points are the centres of the n x m grid's cells
    inside the face; a face too small for any has its centroid. Long thin faces get points along
    their length."""
    longest = np.argmax(np.stack([np.linalg.norm(triangles[:,(k+2)%3]-triangles[:,(k+1)%3],axis=1) for k in range(3)],axis=1),axis=1)
    a = triangles[np.arange(len(triangles)),longest]
    u = triangles[np.arange(len(triangles)),(longest+1)%3]-a
    w = triangles[np.arange(len(triangles)),(longest+2)%3]-a
    n = np.maximum(1,np.ceil(np.linalg.norm(u,axis=1)/spacing)).astype(np.int64)
    m = np.maximum(1,np.ceil(np.linalg.norm(w,axis=1)/spacing)).astype(np.int64)
    # every (i, j) cell centre of every face, kept where it lies inside (s + t < 1)
    total = n*m
    face = np.repeat(np.arange(len(triangles)),total)
    k = np.arange(total.sum())-np.repeat(np.cumsum(total)-total,total)
    s = (k//m[face]+.5)/n[face]
    t = (k%m[face]+.5)/m[face]
    inside = s+t < 1
    alone = np.setdiff1d(np.arange(len(triangles)),face[inside])
    s = np.concatenate((s[inside],np.full(len(alone),1/3)))
    t = np.concatenate((t[inside],np.full(len(alone),1/3)))
    face = np.concatenate((face[inside],alone))
    return a[face]+s[:,None]*u[face]+t[:,None]*w[face], face


def visible_counts(np, mesh, materials, bounds, sweep, world=False):
    """counts[camera, face]: the estimate of each face's visible pixels from each camera: its
    projected area in pixels times the fraction of its points that are nearest in their cell of
    the GRID depth buffer (on screen and not hidden)."""
    from .preview import fitting
    triangles = np.array([[mesh.vertices[i] for i in f.indices] for f in mesh.faces],dtype=float)
    center, scale, radius = fitting(bounds,world)
    center = np.array(center)
    normals = np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0])
    both = np.array([materials[f.material].get('double_sided',False) for f in mesh.faces])
    spacing = SPACING*radius/scale
    lengths = np.linalg.norm(triangles-np.roll(triangles,1,axis=1),axis=2)
    many = float(np.sum(np.ceil(np.median(lengths,axis=1)/spacing)*np.ceil(lengths.min(axis=1)/spacing)))
    if many > MAX_POINTS: spacing *= math.sqrt(many/MAX_POINTS)
    points, face = samples(np, triangles, spacing)
    w, h = GRID
    nf = len(mesh.faces)
    counts = np.zeros((len(sweep),nf))
    for v,(yaw,pitch,distance_scale) in enumerate(sweep):
        sy, cy, sp, cp = math.sin(yaw), math.cos(yaw), math.sin(pitch), math.cos(pitch)
        distance = max(1, radius*2.6)*distance_scale
        eye = center+np.array((-sy*cp,-sp,-cy*cp))*distance/scale
        axes = np.array(((cy,0,-sy),(-sy*sp,cp,-cy*sp),(sy*cp,sp,cy*cp)))      # right, up, forward
        front = both | (np.einsum('fx,fx->f',normals,eye-triangles[:,0]) > 0)
        # projected area, in the screen's pixels, of the faces wholly beyond the near plane
        c = (triangles-eye)@axes.T
        ahead = np.all(c[:,:,2] > .1/scale,axis=1)
        q = 120*FOCAL*c[:,:,:2]/np.where(ahead[:,None],c[:,:,2],1.0)[:,:,None]
        area = np.abs((q[:,1,0]-q[:,0,0])*(q[:,2,1]-q[:,0,1])-(q[:,1,1]-q[:,0,1])*(q[:,2,0]-q[:,0,0]))/2
        area = np.where(front & ahead,area,0.0)
        keep = (front & ahead)[face]
        f = face[keep]
        c = (points[keep]-eye)@axes.T
        x = (w/2+(h/2)*FOCAL*c[:,0]/c[:,2]).astype(np.int64)
        y = (h/2-(h/2)*FOCAL*c[:,1]/c[:,2]).astype(np.int64)
        ok = (x >= 0) & (x < w) & (y >= 0) & (y < h)
        cell, z, g = (y*w+x)[ok], c[ok,2], f[ok]
        nearest = np.full(w*h,np.inf)
        np.minimum.at(nearest,cell,z)
        winners = np.flatnonzero(z == nearest[cell])
        _, first = np.unique(cell[winners],return_index=True)       # one a cell on a tie
        shown = np.bincount(g[winners[first]],minlength=nf)
        total = np.bincount(f,minlength=nf)
        counts[v] = area*shown/np.maximum(total,1)
    return counts


def cutout_texels(np, mesh, svs, drawn, textured):
    """For each view, the texels of cutout faces the console drew pixels of: an array of keys
    slot << 16 | v << 8 | u (after the texture window). svs: each view's __sv; drawn: each view's
    triangle-ID buffer; textured: {face: (corner texture coordinates as drawn, texture)} (the
    reference's). The texture coordinates are interpolated linearly in screen space from the
    console's projected corners, which differs from the GPU's perspective-correct ones by a texel
    here and there: enough to choose views by, not to judge them."""
    faces = np.array(sorted(textured))
    corners = np.array([list(reversed(mesh.faces[f].indices)) for f in faces])
    uv = np.array([textured[f][0] for f in faces],dtype=np.int64)
    window = np.array([textured[f][1][2] for f in faces],dtype=np.int64)
    slot = np.array([textured[f][1][0] for f in faces],dtype=np.int64)
    out = []
    for sv,ids in zip(svs,drawn):
        ids = ids.astype(np.int64)-1
        pix = np.flatnonzero(np.isin(ids,faces))
        k = np.searchsorted(faces,ids[pix])
        packed = sv[:,2].astype(np.int64)
        xy = np.stack(((packed&65535)^32768,(packed>>16&65535)^32768),axis=1)-32768
        p = xy[corners[k]].astype(float)                   # (pixels, 3 corners, x y)
        x, y = (pix%320).astype(float), (pix//320).astype(float)
        d = (p[:,1,0]-p[:,0,0])*(p[:,2,1]-p[:,0,1])-(p[:,1,1]-p[:,0,1])*(p[:,2,0]-p[:,0,0])
        d = np.where(d == 0,1.0,d)
        w1 = ((x-p[:,0,0])*(p[:,2,1]-p[:,0,1])-(y-p[:,0,1])*(p[:,2,0]-p[:,0,0]))/d
        w2 = ((p[:,1,0]-p[:,0,0])*(y-p[:,0,1])-(p[:,1,1]-p[:,0,1])*(x-p[:,0,0]))/d
        w = np.stack((1-w1-w2,w1,w2),axis=1)
        c = np.floor(np.einsum('nk,nka->na',w,uv[k])).astype(np.int64)
        def windowed(c, kk):
            size = kk&7
            return np.where(size == 0,c&255,((kk>>3&31)*8+c%np.minimum(4<<size,256))&255)
        u, v = windowed(c[:,0],window[k]&255), windowed(c[:,1],window[k]>>8)
        out.append(np.unique(slot[k]<<16|v<<8|u))
    return out


def select_views(np, counts, mesh, materials, bounds, sweep, count, cutouts=(), world=False, texels=None):
    """{'views': the chosen views' indices in the sweep, in order, and the cover's numbers}.
    counts[view, face]: the pixels of each face the console drew in each view of the sweep;
    texels: each view's cutout texels (cutout_texels()), to be drawn like the faces."""
    nf, nv = len(mesh.faces), len(sweep)
    best = counts.max(axis=0)
    need = np.full(nf,WELL)
    need[list(cutouts)] = WELL_CUTOUT
    sees = counts > 0
    well = (counts >= need*best) & sees
    seen = best > 0
    keys = np.unique(np.concatenate(texels)) if texels else np.zeros(0,dtype=np.int64)
    items = sees
    if len(keys):
        # the items to draw: the faces, then the cutout texels
        has = np.zeros((nv,len(keys)),dtype=bool)
        for k,t in enumerate(texels): has[k,np.searchsorted(keys,t)] = True
        items = np.concatenate((sees,has),axis=1)
    chosen, suspects = [], []
    if not seen.all():
        estimate = visible_counts(np, mesh, materials, bounds, sweep, world)
        suspects = [f for f in np.flatnonzero(~seen).tolist() if estimate[:,f].max() >= SUSPECT]
        for f in suspects:
            k = int(np.argmax(estimate[:,f]))
            if k not in chosen: chosen.append(k)
    met = items[chosen].any(axis=0) if chosen else np.zeros(items.shape[1],dtype=bool)
    shown = well[chosen].sum(axis=0) if chosen else np.zeros(nf,dtype=np.int64)
    pixels = counts.sum(axis=1)
    free = np.ones(nv,dtype=bool)
    free[chosen] = False
    drawable = items.any(axis=0)
    # until every face (and cutout texel) the sweep draws is drawn, and then up to count views
    while free.any() and (len(chosen) < count or (drawable & ~met).any()):
        new = (items & ~met).sum(axis=1)
        first = (well & (shown == 0)).sum(axis=1)
        second = (well & (shown == 1)).sum(axis=1)
        # the largest (new, first, second, pixels), the earliest view on a tie
        order = np.lexsort((np.arange(nv),-pixels,-second,-first,-new))
        pick = int(next(k for k in order if free[k]))
        chosen.append(pick)
        free[pick] = False
        shown += well[pick]
        met |= items[pick]
    return {'views':sorted(chosen),'candidates':nv,'faces':nf,'faces_drawn_by_sweep':int(seen.sum()),
            'faces_drawn_by_views':int(met[:nf].sum()),'faces_shown_well':int((shown > 0).sum()),
            'faces_shown_well_twice':int((shown > 1).sum()),'cutout_faces':len(cutouts),
            **({'cutout_texels_drawn_by_sweep':len(keys),'cutout_texels_drawn_by_views':int(met[nf:].sum())}
               if len(keys) else {}),
            'suspect_faces':suspects}
