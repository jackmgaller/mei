"""Compile declarative recipes, audit their quantized meshes, and export Mei data."""
from collections import Counter, defaultdict
import hashlib
import math
import struct

from kitcore.jsonio import canonical
from meshlib import Mesh as NativeMesh, rgb, tex_fields, face_slot, face_colour, PALETTES4
import meshlib
from .geometry import (AssetError, Mesh, Face, add, sub, cross, dot, norm, extrude,
                       lathe, loft, explicit_mesh, transform, modify)
from .schema import validate
from . import textures as TEX, texout, faces as FACES


SIDE_AXES = {'right':(0,1),'left':(0,-1),'top':(1,1),'bottom':(1,-1),'front':(2,1),'back':(2,-1)}
# A box's open sides may also be named by their axis: -z is back, +z front, and so on.
SIDE_ALIASES = {'-x':'left','+x':'right','-y':'bottom','+y':'top','-z':'back','+z':'front'}


def open_box(mesh, sides, path):
    """A box without the faces on the named sides (each face's outward normal names its side),
    and without the vertices only they used."""
    named = [SIDE_ALIASES.get(s,s) for s in sides]
    if len(set(named)) != len(named):
        raise AssetError(path, 'Name each side once (-z is back, +z front, -x left, +x right, -y bottom, +y top).')
    gone = {SIDE_AXES[s] for s in named}
    kept = []
    for face in mesh.faces:
        a,b,c = (mesh.vertices[i] for i in face.indices)
        n = cross(sub(b,a),sub(c,a))
        k = max(range(3),key=lambda i: abs(n[i]))
        if (k,1 if n[k] > 0 else -1) not in gone: kept.append(face)
    used = sorted({i for f in kept for i in f.indices})
    new = {old:k for k,old in enumerate(used)}
    return Mesh([mesh.vertices[i] for i in used],
                [f.copy(tuple(new[i] for i in f.indices)) for f in kept])


def mirror_note(mesh, spec, label, path):
    """A note when a mirror modifier that keeps the original makes its copy coincide with it, overlap
    it across the mirror plane, or lay faces back to back on the plane; None otherwise."""
    if not spec.get('keep_original',True) or not mesh.faces: return None
    axis, offset, tol = 'xyz'.index(spec['axis']), spec.get('offset',0), 1e-6
    used = sorted({i for f in mesh.faces for i in f.indices})
    values = [mesh.vertices[i][axis] for i in used]
    lo, hi, name = min(values), max(values), label.lstrip('/') or label
    where = f'{"xyz"[axis]} from {lo:.4g} to {hi:.4g}, the mirror plane at {"xyz"[axis]} = {offset:g}'
    if lo < offset-tol and hi > offset+tol:
        key = lambda v: tuple(round(x,6) for x in v)
        points = {key(mesh.vertices[i]) for i in used}
        mirrored = {key(tuple(2*offset-x if k == axis else x for k,x in enumerate(mesh.vertices[i]))) for i in used}
        if points == mirrored:
            return {'code':'mirror_coincides','part':name,'path':path,
                    'message':f'The mirror\'s copy lies exactly over the original ({where}): every face is doubled. '
                              'Remove the mirror, or set keep_original false.'}
        return {'code':'mirror_overlaps','part':name,'path':path,
                'message':f'The part spans the mirror plane ({where}), so the copy overlaps the original. Move the part '
                          'to one side of the plane (translate a child, then mirror its group), or remove the mirror.'}
    on_plane = sum(all(abs(mesh.vertices[i][axis]-offset) <= tol for i in f.indices) for f in mesh.faces)
    if on_plane:
        return {'code':'mirror_touches','part':name,'path':path,'count':on_plane,
                'message':f'{on_plane} faces lie on the mirror plane ({where}): the copy\'s lie back to back on them, '
                          'a coplanar overlap. Open that side (a box\'s open), or overlap the halves a little.'}
    return None


def compile_recipe(recipe, base=None, budgets='error'):
    """base: the folder image paths are relative to (the recipe's own; default the current one).
    budgets: 'error' (a breach fails) or 'warn' (inspect: a breach is a warning in the report)."""
    validate(recipe)
    materials = {'default':{'color':'#c4cad4'}, **recipe.get('materials',{})}
    prototypes = recipe.get('prototypes',{})
    labels = set()
    calls = 0
    notes = []
    log = {'faces':[],'decals':[]}

    def node(spec, path, parent='', inherited='default', stack=()):
        nonlocal calls
        calls += 1
        if calls > 4096 or len(stack) > 32 or parent.count('/') > 32:
            raise AssetError(path,'Expanded recipe exceeds 4,096 nodes or 32 levels.')
        op = spec['op']
        label = parent+'/'+spec.get('id',op+'_'+path.rsplit('/',1)[-1])
        if label in labels: raise AssetError(path+'/id',f'Duplicate part path {label}. Use unique sibling IDs.')
        labels.add(label)
        material = spec.get('material',inherited)
        if material not in materials: raise AssetError(path+'/material',f'Unknown material {material!r}.')
        if op == 'box':
            x,y,z = [v/2 for v in spec['size']]
            mesh = extrude([[-x,-y],[x,-y],[x,y],[-x,y]], z*2, path)
            if 'open' in spec: mesh = open_box(mesh, spec['open'], path+'/open')
        elif op in ('sphere','cylinder','cone','lathe'):
            segments = spec.get('segments',12)
            if op == 'sphere':
                r, rings = spec['radius'],spec.get('rings',6)
                profile = [[r*math.sin(math.pi*i/rings),-r*math.cos(math.pi*i/rings)] for i in range(rings+1)]
                profile[0][0] = profile[-1][0] = 0
            elif op == 'lathe':
                profile = spec['profile']
                if any(r < 0 for r,y in profile): raise AssetError(path+'/profile','Lathe radii must be nonnegative.')
            else:
                r,h = spec['radius'],spec['height']
                profile = [[r,-h/2],[0 if op == 'cone' else r,h/2]]
            mesh = lathe(profile,segments,spec.get('caps',True),path+'/profile')
        elif op == 'extrude':
            mesh = extrude(spec['points'],spec['depth'],path+'/points')
        elif op == 'loft':
            mesh = loft(spec['sections'],spec.get('caps',True),path+'/sections')
        elif op == 'mesh':
            face_materials = spec.get('face_materials')
            if face_materials is not None:
                if len(face_materials) != len(spec['faces']):
                    raise AssetError(path+'/face_materials','Provide one material name per source polygon.')
                for i,name in enumerate(face_materials):
                    if name not in materials:
                        raise AssetError(f'{path}/face_materials/{i}',f'Unknown material {name!r}.')
            if 'uvs' in spec and len(spec['uvs']) != len(spec['vertices']):
                raise AssetError(path+'/uvs','Provide one [u, v] per vertex.')
            mesh = explicit_mesh(spec['vertices'],spec['faces'],path,face_materials,spec.get('uvs'))
        elif op == 'group':
            mesh = Mesh()
            for i,child in enumerate(spec['children']):
                mesh.append(node(child,f'{path}/children/{i}',label,material,stack))
        elif op == 'instance':
            target = spec['ref']
            if target not in prototypes: raise AssetError(path+'/ref',f'Unknown prototype {target!r}.')
            if target in stack: raise AssetError(path+'/ref','Prototype cycle: '+' → '.join((*stack,target)))
            mesh = node(prototypes[target],'/prototypes/'+target,label,material,(*stack,target))
            if 'material' in spec:
                # faces maps and decals keep their materials
                for face in mesh.faces:
                    if not face.own: face.material = material
        if op not in ('group','instance'):
            for face in mesh.faces:
                if op != 'mesh' or 'face_materials' not in spec:
                    face.material = material
                face.part = label.lstrip('/')
                face.local = tuple(mesh.vertices[i] for i in face.indices)
            if (op != 'mesh' and 'faces' in spec) or 'decals' in spec:
                FACES.apply(mesh,spec,op,label,materials,path,log)
        for i,modifier in enumerate(spec.get('modifiers',[])):
            if modifier['op'] == 'mirror':
                note = mirror_note(mesh,modifier,label,f'{path}/modifiers/{i}')
                if note: notes.append(note)
            mesh = modify(mesh,modifier,f'{path}/modifiers/{i}')
        return transform(mesh,spec.get('transform',{}),path+'/transform')

    mesh = Mesh()
    for i,spec in enumerate(recipe['nodes']):
        mesh.append(node(spec,f'/nodes/{i}'))
    # Textures: texel coordinates from each primitive's own coordinates, then faces of repeating
    # textures cut to fit the GPU's 8-bit coordinates (assetkit/textures.py).
    textures, split_faces = {}, 0
    if any('texture' in materials[f.material] for f in mesh.faces):
        textures = TEX.load(recipe,materials,base,{f.material for f in mesh.faces})
        TEX.project(mesh,textures)
        split_faces = TEX.split(mesh,textures)
    # Export precisely the geometry we audit, including fixed-point quantization.
    vertices, table, remap = [],{},{}
    used = sorted({i for face in mesh.faces for i in face.indices})
    for i in used:
        v = mesh.vertices[i]
        if any(not math.isfinite(x) or not -32768 <= x < 32768 for x in v):
            raise AssetError('/nodes',f'Vertex {i} is outside signed 16.16 coordinate range.')
        fixed = tuple(round(x*65536) for x in v)
        if any(not -(2**31) <= x < 2**31 for x in fixed):
            raise AssetError('/nodes',f'Vertex {i} overflows after fixed-point rounding.')
        if fixed not in table:
            table[fixed] = len(vertices)
            vertices.append(tuple(x/65536 for x in fixed))
        remap[i] = table[fixed]
    for face in mesh.faces:
        face.indices = tuple(remap[i] for i in face.indices)
        a,b,c = (vertices[i] for i in face.indices)
        normal = cross(sub(b,a),sub(c,a))
        if len(set(face.indices)) != 3 or dot(normal,normal) == 0:
            tex = textures.get(face.material)
            if tex and tex.repeat and split_faces:
                spec = tex.spec
                raise AssetError(f'/materials/{face.material}/texture/scale',
                                 f'Part {face.part!r} has a triangle that collapses at Mei 16.16 precision after its long faces '
                                 f'were split for the texture of material {face.material!r} ({TEX.describe(tex)}, '
                                 f'{tex.width} x {tex.height} texels, {tex.projection} projection, scale '
                                 f'{spec.get("scale",[1,1])}): a cut fell within a 16.16 step of a corner. Use a power-of-two '
                                 'scale (0.25, 0.5, 1, 2), which puts the cuts on exact coordinates, or move the corner.')
            raise AssetError('/nodes',f'Part {face.part!r} has a triangle that collapses at Mei 16.16 precision. Enlarge it or reduce detail.')
    mesh.vertices = vertices
    budget = {'vertices':2048,'triangles':2000,**recipe.get('budget',{})}
    breaches = []
    for key,count in (('vertices',len(vertices)),('triangles',len(mesh.faces))):
        if count > budget[key]:
            message = f'Asset has {count} {key}; budget is {budget[key]}. Reduce detail/repetition or explicitly raise the budget within hardware limits.'
            if budgets != 'warn': raise AssetError('/budget/'+key,message)
            breaches.append({'code':'over_budget','key':key,'count':count,'budget':budget[key],
                             'message':message+' build fails until it fits; the per-part counts are in parts.'})
    light = recipe.get('lighting',{})
    if light.get('mode','directional') == 'vertical':
        if 'direction' in light:
            raise AssetError('/lighting/direction','Vertical lighting shades by each face normal\'s Y only. Remove direction, or use mode "directional".')
    elif light.get('bake',True) and dot(light.get('direction',[-0.4,0.85,-0.35]), light.get('direction',[-0.4,0.85,-0.35])) == 0:
        raise AssetError('/lighting/direction','Baked light direction must be nonzero.')
    for name,mat in recipe.get('materials',{}).items():
        if mat.get('class') == 'emissive' and mat.get('palette') is False:
            raise AssetError(f'/materials/{name}/palette','Emissive materials are always drawn through palette entries of their own. Remove palette: false, or use class "surface".')
        if 'share' in mat and not palette_backed(mat):
            raise AssetError(f'/materials/{name}/share','share only applies to palette-backed materials. Set palette: true, or remove share.')
    mesh.palette = assign_palette(mesh,materials,recipe,bool(textures))
    if textures:
        mesh.textures = TEX.finish(mesh,textures,recipe,{**DEFAULT_LAYOUT,**recipe.get('palette_layout',{})})
        mesh.textures['split_faces'] = split_faces
    result = report(mesh,recipe,budget,materials)
    result['warnings'][:0] = breaches
    if log['faces']: result['face_maps'] = log['faces']
    if log['decals']: result['decals'] = decal_report(mesh,log['decals'])
    mesh.notes = notes
    if 'lod' in recipe:
        mesh.levels = compile_levels(recipe,mesh,base,budgets)
        result['lod'] = lod_summary(recipe,mesh,result)
        for k,(_,rep) in enumerate(mesh.levels,1):
            result['warnings'] += [{**w,'level':k,'message':f'Level {k}: '+w['message']}
                                   for w in rep['warnings'] if w['code'] == 'over_budget']
    return mesh, materials, result


def decal_report(mesh, decals):
    """The report's decals: each with its faces in the final mesh (all copies) and their bounds,
    their outward normal (the first copy's), and the triangles it added (8 a copy)."""
    out = []
    for entry in decals:
        faces = [f for f in mesh.faces if f.decal == entry['id']]
        if not faces: continue
        points = [mesh.vertices[i] for f in faces for i in f.indices]
        a,b,c = (mesh.vertices[i] for i in faces[0].indices)
        out.append({**entry,'triangles':len(faces),'added_triangles':4*len(faces),
                    'bounds':{'min':[min(p[k] for p in points) for k in range(3)],'max':[max(p[k] for p in points) for k in range(3)]},
                    'normal':[round(x,6) for x in norm(cross(sub(b,a),sub(c,a)))]})
    return out


DEFAULT_BAND = 1.0


def level_recipe(recipe, k):
    """The recipe of level k of an asset with lod: level 0 is the recipe's own nodes; level k
    takes lod.levels[k - 1]'s nodes, with everything else (materials, prototypes, lighting,
    palette layout, budget, verification) the recipe's own."""
    out = {key:value for key,value in recipe.items() if key != 'lod'}
    if k: out['nodes'] = recipe['lod']['levels'][k-1]['nodes']
    return out


def compile_levels(recipe, base, folder=None, budgets='error'):
    """Levels 1.. of a recipe with lod, each compiled as a recipe of its own: [(mesh, report)].
    Checks the switch distances."""
    lod = recipe['lod']
    levels = lod.get('levels',[])
    band = lod.get('band',DEFAULT_BAND)
    marks = [0]+[level['distance'] for level in levels]+([lod['cull']] if 'cull' in lod else [])
    for k in range(1,len(marks)):
        where = f'/lod/levels/{k-1}/distance' if k <= len(levels) else '/lod/cull'
        if marks[k] <= marks[k-1]:
            raise AssetError(where,'Switch distances increase from level to level, and cull lies beyond the last.')
        if marks[k]-marks[k-1] <= 2*band:
            raise AssetError(where,f'Switch distances lie more than twice the band ({band}) apart, so the hysteresis of '
                                   'one switch never reaches the next. Space them out or narrow lod.band.')
    out = []
    for k in range(1,len(levels)+1):
        try:
            mesh,_,rep = compile_recipe(level_recipe(recipe,k),folder,budgets)
        except AssetError as error:
            path = error.path if error.path.startswith('/budget') else f'/lod/levels/{k-1}'+error.path
            raise AssetError(path,f'Level {k}: {error}') from error
        # Every level draws through level 0's palette entries, so one palette serves them all.
        own = base.palette['by_material'] if base.palette else {}
        for name in sorted({f.material for f in mesh.faces}):
            if mesh.palette and name in mesh.palette['by_material'] and name not in own:
                raise AssetError(f'/lod/levels/{k-1}/nodes',f'Level {k} draws palette-backed material {name!r}, which '
                                 'level 0 does not use: every level shares level 0\'s palette entries.')
        mesh.palette = base.palette if mesh.palette else None
        if mesh.textures:
            # ... and level 0's textures, where level 0 put them
            own = {t.tile.key for t in base.textures['textures'].values()} if base.textures else set()
            for name,tex in mesh.textures['textures'].items():
                if tex.tile.key not in own:
                    raise AssetError(f'/lod/levels/{k-1}/nodes',f'Level {k} draws the texture of {name!r}, which level 0 '
                                     'does not use: every level shares level 0\'s textures.')
            mesh.textures['packing'] = base.textures['packing']
        out.append((mesh,rep))
    return out


def lod_summary(recipe, mesh, base):
    """Triangles, vertices and switch distances per level, for the report."""
    lod = recipe['lod']
    rows = [{'level':0,'distance':0,'triangles':base['triangles'],'vertices':base['vertices']}]
    for k,(m,rep) in enumerate(mesh.levels,1):
        rows.append({'level':k,'distance':lod['levels'][k-1]['distance'],'triangles':rep['triangles'],'vertices':rep['vertices']})
        if rep['triangles'] >= rows[-2]['triangles']:
            base['warnings'].append({'code':'lod_not_simpler','level':k,'count':rep['triangles'],
                                     'message':f'Level {k} has no fewer triangles than level {k-1}.'})
    return {'levels':rows,'cull':lod.get('cull'),'band':lod.get('band',DEFAULT_BAND)}


DEFAULT_LAYOUT = {'slot':14,'row':0,'first':0}


FONT_PALETTE = 255      # 4-bit palette 255 (colours 4080-4095) holds the fonts' colours


def palette_range_ok(first, count):
    """Whether 4-bit palettes first..first+count-1 exist (0-511, VRAM at 2 MB) and leave out
    the fonts' palette 255."""
    return 0 <= first and first+count <= PALETTES4 and not first <= FONT_PALETTE < first+count


def palette_backed(mat):
    if 'texture' in mat: return False     # a textured material draws through its texture's palette
    return mat.get('palette',mat.get('class','surface') == 'emissive')


def rgb15(color):
    r,g,b = (int(color[k:k+2],16) for k in (1,3,5))
    return (r>>3)|((g>>3)<<5)|((b>>3)<<10)


def assign_palette(mesh, materials, recipe, textured=False):
    """One 4-bit palette entry per distinct (class, colour) among the palette-backed materials
    the mesh uses, and one of its own for each material with share: false: surface entries
    first, then emissive, indices 1-15 of consecutive palettes. Index 0 is never assigned (the
    GPU never draws it)."""
    used = sorted({f.material for f in mesh.faces})
    keys, owners = [], defaultdict(list)
    for kind in ('surface','emissive'):
        for name in used:
            mat = materials[name]
            if palette_backed(mat) and mat.get('class','surface') == kind:
                key = (kind,mat['color'].lower()) if mat.get('share',True) else (kind,mat['color'].lower(),name)
                if key not in owners: keys.append(key)
                owners[key].append(name)
    if not keys:
        if 'palette_layout' in recipe and not textured:
            raise AssetError('/palette_layout','No material the mesh uses is drawn through the palette. Set palette: true (or class "emissive") on a material, or remove palette_layout.')
        return None
    layout = {**DEFAULT_LAYOUT,**recipe.get('palette_layout',{})}
    if layout['slot'] == 15:
        raise AssetError('/palette_layout/slot','Texture slot 15 holds the fonts.')
    count = (len(keys)+14)//15
    if not palette_range_ok(layout['first'],count):
        raise AssetError('/palette_layout/first',f'{len(keys)} palette entries need {count} 4-bit palettes from {layout["first"]}; '
                         f'palette 255 holds the fonts, and there are {PALETTES4} (0-{PALETTES4-1}).')
    entries, by_material = [], {}
    for i,key in enumerate(keys):
        palette, index = layout['first']+i//15, 1+i%15
        entry = {'colour':palette*16+index,'palette':palette,'index':index,'class':key[0],
                 'color':key[1],'rgb15':rgb15(key[1]),'materials':owners[key]}
        if len(key) == 3: entry['separate'] = True    # share: false; never merged with another
        entries.append(entry)
        for name in owners[key]: by_material[name] = entry
    return {'layout':layout,'palettes':list(range(layout['first'],layout['first']+count)),
            'entries':entries,'by_material':by_material}


def face_runs(mesh, keep):
    """Half-open [start, end) runs of exported face indices whose face satisfies keep."""
    runs = []
    for i,face in enumerate(mesh.faces):
        if not keep(face): continue
        if runs and runs[-1][1] == i: runs[-1][1] = i+1
        else: runs.append([i,i+1])
    return runs


def material_manifest(mesh, materials, recipe):
    """The consumer's view of materials: palette entries and their defaults, classes, tags
    and the faces each covers. Written for every build."""
    name, palette = recipe['name'], mesh.palette
    used = sorted({f.material for f in mesh.faces})
    result = {'format':'mei-asset-materials','version':1,'name':name}
    if palette:
        layout = palette['layout']
        result['swatch'] = {'file':name+'.swatch','slot':layout['slot'],'row':layout['row'],'texels':16,
                            'meaning':'4-bit texel u of the row holds palette index u; a face draws an entry by sampling (index, row) at all its corners.'}
        result['palette'] = {'file':name+'.pal','first_colour':palette['palettes'][0]*16,
                             'colours':16*len(palette['palettes']),'palettes':palette['palettes']}
        result['entries'] = [dict(e) for e in palette['entries']]
        result['classes'] = {}
        for kind in ('surface','emissive'):
            colours = [e['colour'] for e in palette['entries'] if e['class'] == kind]
            if colours:
                result['classes'][kind] = {'first_colour':colours[0],'colours':colours[-1]-colours[0]+1,'entries':colours}
    result['materials'] = {}
    for key in used:
        mat = materials[key]
        entry = palette['by_material'].get(key) if palette else None
        result['materials'][key] = {'color':mat['color'].lower(),'class':mat.get('class','surface'),
                                    'palette_colour':entry['colour'] if entry else None,'tag':mat.get('tag'),
                                    'triangles':sum(f.material == key for f in mesh.faces),
                                    'faces':face_runs(mesh,lambda f: f.material == key)}
    tags = sorted({materials[key]['tag'] for key in used if 'tag' in materials[key]})
    result['tags'] = {tag:face_runs(mesh,lambda f: materials[f.material].get('tag') == tag) for tag in tags}
    if mesh.textures:
        _,_,_,section = texture_outputs(name,mesh)
        packing = mesh.textures['packing']
        result['textures'] = {**section,'windows':[packing.placements[k].halfword() for k in window_order(mesh,packing)],
                              'list':texout.texture_entries(mesh,packing,face_runs)}
    return result


def window_order(mesh, packing):
    """The tiles in the order of the mesh's window table (first use by a face)."""
    keys = []
    for face in mesh.faces:
        tex = mesh.textures['textures'].get(face.material)
        if tex and packing.placements[tex.tile.key].window and tex.tile.key not in keys:
            keys.append(tex.tile.key)
    return keys


def palette_bytes(mesh):
    """Default colours of every palette the asset uses, 15-bit; unused indices are 0."""
    first = mesh.palette['palettes'][0]*16
    colours = [0]*16*len(mesh.palette['palettes'])
    for entry in mesh.palette['entries']: colours[entry['colour']-first] = entry['rgb15']
    return struct.pack(f'<{len(colours)}H',*colours)


# Texel u of the swatch row holds palette index u (4-bit: the low nibble is the left texel).
SWATCH = bytes(2*j|(2*j+1)<<4 for j in range(8))


def texture_outputs(name, mesh, packing=None):
    """(files, embed lines, loader lines, manifest) of a textured asset's own placement."""
    packing = packing or mesh.textures['packing']
    animations, seen = [], set()
    for material,tex in mesh.textures['textures'].items():
        if len(tex.tile.frames) > 1 and tex.tile.key not in seen:
            seen.add(tex.tile.key)
            animations.append((tex.tile.key,material,tex.ticks))
    return texout.outputs(name,'ASSET_'+name.upper(),packing,animations)


def import_source(name, mesh):
    """The generated Akari import. Assets without palette materials or textures keep the original
    two lines."""
    upper = name.upper()
    text = f'// Mei Asset Kit: {len(mesh.vertices)} vertices, {len(mesh.faces)} triangles.\nembed ASSET_{upper}: Mesh = "{name}.bin"\n'
    palette = mesh.palette
    if not palette and not mesh.textures: return text
    lines, body = [], []
    if mesh.textures:
        packing = mesh.textures['packing']
        _,embeds,body,_ = texture_outputs(name,mesh)
        pals = ', '.join(f'{b}-bit {p}' for b,p in sorted(packing.palettes))
        lines += ['',f'// Textures: slots {", ".join(map(str,packing.slots()))}; palettes {pals}. Call asset_{name}_load() before drawing.',
                  *embeds]
    if palette:
        layout, first = palette['layout'], palette['palettes'][0]*16
        lines += ['',f'// Palette-backed materials: 4-bit palettes {palette["palettes"][0]}-{palette["palettes"][-1]} '
                 f'(colours {first}-{first+16*len(palette["palettes"])-1}),',
                 f'// swatch texels u 0-15 of row {layout["row"]} in texture slot {layout["slot"]}. Call asset_{name}_load() before drawing.',
                 f'embed ASSET_{upper}_PALETTE: u16 = "{name}.pal"',
                 f'embed ASSET_{upper}_SWATCH: u8 = "{name}.swatch"',
                 f'const ASSET_{upper}_COLOUR = {first}']
        for kind in ('surface','emissive'):
            colours = [e['colour'] for e in palette['entries'] if e['class'] == kind]
            if colours:
                lines += [f'const ASSET_{upper}_{kind.upper()} = {colours[0]}',
                          f'const ASSET_{upper}_{kind.upper()}_COUNT = {colours[-1]-colours[0]+1}']
        # textures first: the swatch may share their slot
        body = body+[f'    memcpy((VRAM_TEXTURES + {layout["slot"]} * TEXTURE_SLOT_SIZE + {layout["row"]*128}) as *u8, ASSET_{upper}_SWATCH, {len(SWATCH)})',
                     f'    load_palette(ASSET_{upper}_COLOUR, ASSET_{upper}_PALETTE, len(ASSET_{upper}_PALETTE))']
    what = ('the swatch texels and the default palette colours' if not mesh.textures else
            'the textures and their palettes' if not palette else 'the textures, the swatch and their palettes')
    lines += ['',f'// Copies {what} into VRAM.',f'fn asset_{name}_load() {{',*body,'}','']
    return text+'\n'.join(lines)


def relocate(binary, colours=None, slot=None, row=None):
    """Move palette-backed faces to other palette colours and/or swatch position, for a
    consumer packing several assets into shared palettes. colours maps an old colour index
    (palette * 16 + index) to a new one; index 0 of a palette is never a valid target."""
    data = bytearray(binary)
    _,count,_,offset,_ = struct.unpack_from('<HHIII',data)
    for i in range(count):
        at = offset+i*36
        flags = data[at]
        if not flags&2: continue
        tex,palette = data[at+2],data[at+3]
        uv = struct.unpack_from('<4H',data,at+28)
        if not tex&16 or len(set(uv[:3])) != 1 or not 0 < (uv[0]&255) < 16:
            raise AssetError('/binary',f'Face {i} is textured but is not a palette swatch face.')
        colour, v = face_colour(flags,tex,palette,uv[0]&255), uv[0]>>8
        if colours and colour in colours:
            colour = colours[colour]
            if not 0 < colour < 16*PALETTES4 or colour%16 == 0 or colour//16 == FONT_PALETTE:
                raise AssetError('/binary',f'Colour {colour} is index 0 of a palette or outside palettes 0-254 and 256-511.')
        banks,tex,data[at+3] = tex_fields(face_slot(flags,tex) if slot is None else slot,True,colour//16,tex>>5)
        data[at],data[at+2] = (flags&~(meshlib.SLOT_HI|meshlib.PAL_HI))|banks,tex
        if row is not None: v = row
        struct.pack_into('<4H',data,at+28,*([colour%16|v<<8]*4))
    return bytes(data)


def report(mesh, recipe, budget, materials=None):
    parts, warnings = [],[]
    tagged = materials is not None and any('tag' in materials[f.material] for f in mesh.faces)
    by_part = defaultdict(list)
    for face in mesh.faces: by_part[face.part].append(face)
    for name,faces in sorted(by_part.items()):
        indices = sorted({i for f in faces for i in f.indices})
        verts = [mesh.vertices[i] for i in indices]
        edges, directions, duplicate = Counter(),Counter(),Counter()
        for face in faces:
            ids = face.indices
            duplicate[tuple(sorted(ids))] += 1
            for a,b in zip(ids,ids[1:]+ids[:1]):
                edges[tuple(sorted((a,b)))] += 1
                directions[a,b] += 1
        boundary = sum(n == 1 for n in edges.values())
        nonmanifold = sum(n > 2 for n in edges.values())
        winding = sum(n == 2 and (directions[a,b] == 2 or directions[b,a] == 2) for (a,b),n in edges.items())
        duplicates = sum(n-1 for n in duplicate.values())
        volume = sum(dot(mesh.vertices[f.indices[0]],cross(mesh.vertices[f.indices[1]],mesh.vertices[f.indices[2]]))/6 for f in faces)
        data = {'id':name,'vertices':len(indices),'triangles':len(faces),
                'bounds':{'min':[min(v[k] for v in verts) for k in range(3)],'max':[max(v[k] for v in verts) for k in range(3)]},
                'materials':sorted({f.material for f in faces}),
                'boundary_edges':boundary,'nonmanifold_edges':nonmanifold,
                'inconsistent_edges':winding,'duplicate_triangles':duplicates}
        if tagged: data['tags'] = sorted({materials[f.material]['tag'] for f in faces if 'tag' in materials[f.material]})
        parts.append(data)
        for code,count,message in (
            ('open_surface',boundary,'Boundary edges; intentional for open surfaces.'),
            ('nonmanifold',nonmanifold,'Edges shared by more than two triangles.'),
            ('winding',winding,'Adjacent triangles disagree on outward winding.'),
            ('duplicate_faces',duplicates,'Coincident triangles; check mirrors/arrays.'),
            ('inward',int(not boundary and not nonmanifold and volume < -1e-12),'Closed part has negative signed volume; check winding.'),
        ):
            if count: warnings.append({'code':code,'part':name,'count':count,'message':message})
    lo,hi = mesh.bounds()
    byte_count = 16+16*len(mesh.vertices)+36*len(mesh.faces)
    result = {'ok':True,'format':'mei-asset-report','version':1,'name':recipe['name'],
              'recipe_sha256':hashlib.sha256(canonical(recipe)).hexdigest(),
              'vertices':len(mesh.vertices),'triangles':len(mesh.faces),'mesh_bytes':byte_count,
              'bounds':{'min':lo,'max':hi},'budget':budget,
              'budget_used':{'vertices':len(mesh.vertices)/budget['vertices'],'triangles':len(mesh.faces)/budget['triangles']},
              'parts':parts,'warnings':warnings}
    # Only recipes using the material extensions gain keys, so legacy reports are unchanged.
    palette = mesh.palette
    if palette:
        result['palette'] = {'palettes':palette['palettes'],'entries':len(palette['entries']),
                             'emissive_entries':sum(e['class'] == 'emissive' for e in palette['entries']),
                             'textured_triangles':sum(f.material in palette['by_material'] for f in mesh.faces),
                             'swatch':{'slot':palette['layout']['slot'],'row':palette['layout']['row']}}
    if tagged:
        result['tags'] = dict(sorted(Counter(materials[f.material]['tag'] for f in mesh.faces
                                             if 'tag' in materials[f.material]).items()))
    if mesh.textures:
        packing = mesh.textures['packing']
        result['textures'] = {'textured_triangles':sum(f.material in mesh.textures['textures'] for f in mesh.faces),
                              'split_faces':mesh.textures.get('split_faces',0),
                              'windows':len(window_order(mesh,packing)),
                              **packing.summary(),
                              'list':[t.summary() for t in mesh.textures['textures'].values()]}
    return result


def shading(lighting):
    """The baked shade (0-1) of a unit normal under a recipe's lighting."""
    ambient, bake = lighting.get('ambient',0.45),lighting.get('bake',True)
    if not bake: return lambda n: 1
    if lighting.get('mode','directional') == 'vertical':
        # A function of the normal's Y alone, so any rotation about Y leaves it unchanged.
        return lambda n: ambient+(1-ambient)*(1+n[1])/2
    light = norm(lighting.get('direction',[-0.4,0.85,-0.35]))
    return lambda n: ambient+(1-ambient)*max(0,dot(n,light))


def native_bytes(mesh, materials, lighting, packing=None):
    """The native mesh. packing: where the textures are (kitcore.texpack.Packing); default the
    asset's own placement (mesh.textures['packing'])."""
    shade_of = shading(lighting)
    palette = mesh.palette
    textures = mesh.textures['textures'] if mesh.textures else {}
    if textures and packing is None: packing = mesh.textures['packing']
    normals, smooth = [],defaultdict(lambda: (0,0,0))
    for face in mesh.faces:
        a,b,c = (mesh.vertices[i] for i in face.indices)
        normal = cross(sub(b,a),sub(c,a))
        normals.append(norm(normal))
        for i in face.indices:
            key = (face.part,face.material,i)
            smooth[key] = add(smooth[key],normal)
    result = NativeMesh()
    result.verts = mesh.vertices
    for face,normal in zip(mesh.faces,normals):
        mat = materials[face.material]
        entry = palette['by_material'].get(face.material) if palette else None
        tex = textures.get(face.material)
        # A palette-backed face samples a solid swatch texel, tinted by the shade (128 = 1);
        # a textured face its texture's texels, likewise.
        color = (128,128,128) if entry or tex else tuple(int(mat['color'][k:k+2],16) for k in (1,3,5))
        colors = []
        for i in face.indices:
            n = norm(smooth[face.part,face.material,i]) if mat.get('smooth',False) else normal
            # Emissive surfaces are never shaded: their brightness is their palette entry's.
            shade = 1 if (entry or tex) and mat.get('class','surface') == 'emissive' else shade_of(n)
            colors.append(rgb(*(max(0,min(255,round(c*shade))) for c in color)))
        # Mei's front faces have cross . outward < 0. Color order follows indices.
        flags = 16 if mat.get('double_sided',False) else 0
        if tex:
            place = packing.placements[tex.tile.key]
            if place.window:
                window = result.window(u=(place.width,place.x),v=(place.height,place.y))
                uvs = list(face.texcoords)
            else:
                window = 0
                uvs = [(u+place.x,v+place.y) for u,v in face.texcoords]
            result.tri(list(reversed(face.indices)),list(reversed(colors)),list(reversed(uvs)),flags,
                       slot=place.slot,four_bit=place.bits == 4,palette=place.palette,window=window)
        elif entry:
            uv = (entry['index'],palette['layout']['row'])
            result.tri(list(reversed(face.indices)),list(reversed(colors)),[uv]*3,flags,
                       slot=palette['layout']['slot'],four_bit=True,palette=entry['palette'])
        else:
            result.tri(list(reversed(face.indices)),list(reversed(colors)),flags=flags)
    return result.pack()


def editor_project(mesh,materials,name,lighting):
    """Exchange format understood by the local Mei Modeler; no server dependency."""
    objects = []
    grouped = defaultdict(list)
    for face in mesh.faces: grouped[face.part,face.material].append(face)
    for (part,material),faces in sorted(grouped.items()):
        indices = sorted({i for f in faces for i in f.indices})
        local = {old:new for new,old in enumerate(indices)}
        objects.append({'name':part,'vertices':[list(mesh.vertices[i]) for i in indices],
                        'faces':[{'indices':[local[i] for i in f.indices],'color':materials[material]['color']} for f in faces],
                        'doubleSided':materials[material].get('double_sided',False)})
    return {'format':'mei-model','version':1,'name':name,'bakeLighting':lighting.get('bake',True),'objects':objects}


def obj_text(mesh, materials):
    lines = ['# Mei Asset Kit; Y up; outward right-handed polygon winding.']
    lines += ['v '+' '.join(f'{n:.8f}' for n in v) for v in mesh.vertices]
    last = None
    for face in mesh.faces:
        key = face.part,face.material
        if key != last:
            lines += ['g '+face.part.replace('/','_'),'usemtl '+face.material]
            last = key
        lines.append('f '+' '.join(str(i+1) for i in face.indices))
    return '\n'.join(lines)+'\n'


def import_obj(text, name):
    """Geometry-only OBJ import; the CLI explicitly reports discarded appearance data."""
    vertices,faces = [],[]
    for lineno,line in enumerate(text.splitlines(),1):
        words = line.split('#',1)[0].split()
        if not words: continue
        try:
            if words[0] == 'v':
                if len(words) != 4: raise ValueError('Only three-coordinate vertices are supported.')
                vertices.append([float(n) for n in words[1:]])
            elif words[0] == 'f':
                ids = []
                for token in words[1:]:
                    i = int(token.split('/')[0])
                    if i == 0: raise ValueError('OBJ indices are one-based; zero is invalid.')
                    at = i-1 if i > 0 else len(vertices)+i
                    if not 0 <= at < len(vertices): raise ValueError('Face references a vertex not yet defined.')
                    ids.append(at)
                faces.append(ids)
            elif words[0] not in ('o','g','s','vt','vn','mtllib','usemtl'):
                raise ValueError(f'Unsupported OBJ record {words[0]!r}.')
        except ValueError as error:
            raise AssetError(f'/obj/line/{lineno}',str(error)) from error
    recipe = {'format':'mei-asset','version':1,'name':name,
              'nodes':[{'id':name,'op':'mesh','vertices':vertices,'faces':faces}]}
    compile_recipe(recipe)
    return recipe
