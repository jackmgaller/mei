"""Compile declarative recipes, audit their quantized meshes, and export Mei data."""
from collections import Counter, defaultdict
import hashlib
import json
import math
import struct

from kitcore.jsonio import canonical  # noqa: F401 (re-exported)
from meshlib import Mesh as NativeMesh, rgb
from .geometry import (AssetError, Mesh, add, sub, cross, dot, norm, extrude,
                       lathe, loft, explicit_mesh, transform, modify)
from .schema import validate


def compile_recipe(recipe):
    validate(recipe)
    materials = {'default':{'color':'#c4cad4'}, **recipe.get('materials',{})}
    prototypes = recipe.get('prototypes',{})
    labels = set()
    calls = 0

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
            mesh = explicit_mesh(spec['vertices'],spec['faces'],path,face_materials)
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
                for face in mesh.faces: face.material = material
        if op not in ('group','instance'):
            for face in mesh.faces:
                if op != 'mesh' or 'face_materials' not in spec:
                    face.material = material
                face.part = label.lstrip('/')
        for i,modifier in enumerate(spec.get('modifiers',[])):
            mesh = modify(mesh,modifier,f'{path}/modifiers/{i}')
        return transform(mesh,spec.get('transform',{}),path+'/transform')

    mesh = Mesh()
    for i,spec in enumerate(recipe['nodes']):
        mesh.append(node(spec,f'/nodes/{i}'))
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
            raise AssetError('/nodes',f'Part {face.part!r} has a triangle that collapses at Mei 16.16 precision. Enlarge it or reduce detail.')
    mesh.vertices = vertices
    budget = {'vertices':2048,'triangles':2000,**recipe.get('budget',{})}
    for key,count in (('vertices',len(vertices)),('triangles',len(mesh.faces))):
        if count > budget[key]:
            raise AssetError('/budget/'+key,f'Asset has {count} {key}; budget is {budget[key]}. Reduce detail/repetition or explicitly raise the budget within hardware limits.')
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
    mesh.palette = assign_palette(mesh,materials,recipe)
    return mesh, materials, report(mesh,recipe,budget,materials)


DEFAULT_LAYOUT = {'slot':14,'row':0,'first':0}


def palette_backed(mat):
    return mat.get('palette',mat.get('class','surface') == 'emissive')


def rgb15(color):
    r,g,b = (int(color[k:k+2],16) for k in (1,3,5))
    return (r>>3)|((g>>3)<<5)|((b>>3)<<10)


def assign_palette(mesh, materials, recipe):
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
        if 'palette_layout' in recipe:
            raise AssetError('/palette_layout','No material the mesh uses is drawn through the palette. Set palette: true (or class "emissive") on a material, or remove palette_layout.')
        return None
    layout = {**DEFAULT_LAYOUT,**recipe.get('palette_layout',{})}
    count = (len(keys)+14)//15
    if layout['first']+count > 255:
        raise AssetError('/palette_layout/first',f'{len(keys)} palette entries need {count} 4-bit palettes from {layout["first"]}; palette 255 holds the fonts.')
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
    return result


def palette_bytes(mesh):
    """Default colours of every palette the asset uses, 15-bit; unused indices are 0."""
    first = mesh.palette['palettes'][0]*16
    colours = [0]*16*len(mesh.palette['palettes'])
    for entry in mesh.palette['entries']: colours[entry['colour']-first] = entry['rgb15']
    return struct.pack(f'<{len(colours)}H',*colours)


# Texel u of the swatch row holds palette index u (4-bit: the low nibble is the left texel).
SWATCH = bytes(2*j|(2*j+1)<<4 for j in range(8))


def import_source(name, mesh):
    """The generated Akari import. Assets without palette materials keep the original two lines."""
    upper = name.upper()
    text = f'// Mei Asset Kit: {len(mesh.vertices)} vertices, {len(mesh.faces)} triangles.\nembed ASSET_{upper}: Mesh = "{name}.bin"\n'
    palette = mesh.palette
    if not palette: return text
    layout, first = palette['layout'], palette['palettes'][0]*16
    lines = ['',f'// Palette-backed materials: 4-bit palettes {palette["palettes"][0]}-{palette["palettes"][-1]} '
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
    lines += ['','// Copies the swatch texels and the default palette colours into VRAM.',
              f'fn asset_{name}_load() {{',
              f'    memcpy((VRAM_TEXTURES + {layout["slot"]} * TEXTURE_SLOT_SIZE + {layout["row"]*128}) as *u8, ASSET_{upper}_SWATCH, {len(SWATCH)})',
              f'    load_palette(ASSET_{upper}_COLOUR, ASSET_{upper}_PALETTE, len(ASSET_{upper}_PALETTE))',
              '}','']
    return text+'\n'.join(lines)


def relocate(binary, colours=None, slot=None, row=None):
    """Move palette-backed faces to other palette colours and/or swatch position, for a
    consumer packing several assets into shared palettes. colours maps an old colour index
    (palette * 16 + index) to a new one; index 0 of a palette is never a valid target."""
    data = bytearray(binary)
    _,count,_,offset,_ = struct.unpack_from('<HHIII',data)
    for i in range(count):
        at = offset+i*36
        if not data[at]&2: continue
        tex,palette = data[at+2],data[at+3]
        uv = struct.unpack_from('<4H',data,at+28)
        if not tex&16 or len(set(uv[:3])) != 1 or not 0 < (uv[0]&255) < 16:
            raise AssetError('/binary',f'Face {i} is textured but is not a palette swatch face.')
        colour, v = palette*16+(uv[0]&255), uv[0]>>8
        if colours and colour in colours:
            colour = colours[colour]
            if not 0 < colour < 4080 or colour%16 == 0:
                raise AssetError('/binary',f'Colour {colour} is index 0 of a palette or outside palettes 0-254.')
        if slot is not None: tex = (tex&~15)|slot
        if row is not None: v = row
        data[at+2],data[at+3] = tex,colour//16
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


def native_bytes(mesh, materials, lighting):
    shade_of = shading(lighting)
    palette = mesh.palette
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
        # A palette-backed face samples a solid swatch texel, tinted by the shade (128 = 1).
        color = (128,128,128) if entry else tuple(int(mat['color'][k:k+2],16) for k in (1,3,5))
        colors = []
        for i in face.indices:
            n = norm(smooth[face.part,face.material,i]) if mat.get('smooth',False) else normal
            # Emissive surfaces are never shaded: their brightness is their palette entry's.
            shade = 1 if entry and entry['class'] == 'emissive' else shade_of(n)
            colors.append(rgb(*(max(0,min(255,round(c*shade))) for c in color)))
        # Mei's front faces have cross . outward < 0. Color order follows indices.
        flags = 16 if mat.get('double_sided',False) else 0
        if entry:
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
