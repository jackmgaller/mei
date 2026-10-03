"""Compile declarative recipes, audit their quantized meshes, and export Mei data."""
from collections import Counter, defaultdict
import hashlib
import json
import math

from meshlib import Mesh as NativeMesh, rgb
from .geometry import (AssetError, Mesh, add, sub, cross, dot, norm, extrude,
                       lathe, loft, explicit_mesh, transform, modify)
from .schema import validate


def canonical(recipe):
    return json.dumps(recipe, sort_keys=True, separators=(',',':'), allow_nan=False).encode()


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
    if light.get('bake',True) and dot(light.get('direction',[-0.4,0.85,-0.35]), light.get('direction',[-0.4,0.85,-0.35])) == 0:
        raise AssetError('/lighting/direction','Baked light direction must be nonzero.')
    return mesh, materials, report(mesh,recipe,budget)


def report(mesh, recipe, budget):
    parts, warnings = [],[]
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
    return {'ok':True,'format':'mei-asset-report','version':1,'name':recipe['name'],
            'recipe_sha256':hashlib.sha256(canonical(recipe)).hexdigest(),
            'vertices':len(mesh.vertices),'triangles':len(mesh.faces),'mesh_bytes':byte_count,
            'bounds':{'min':lo,'max':hi},'budget':budget,
            'budget_used':{'vertices':len(mesh.vertices)/budget['vertices'],'triangles':len(mesh.faces)/budget['triangles']},
            'parts':parts,'warnings':warnings}


def native_bytes(mesh, materials, lighting):
    light = norm(lighting.get('direction',[-0.4,0.85,-0.35]))
    ambient, bake = lighting.get('ambient',0.45),lighting.get('bake',True)
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
        color = tuple(int(mat['color'][k:k+2],16) for k in (1,3,5))
        colors = []
        for i in face.indices:
            n = norm(smooth[face.part,face.material,i]) if mat.get('smooth',False) else normal
            shade = ambient+(1-ambient)*max(0,dot(n,light)) if bake else 1
            colors.append(rgb(*(max(0,min(255,round(c*shade))) for c in color)))
        # Mei's front faces have cross . outward < 0. Color order follows indices.
        result.tri(list(reversed(face.indices)),list(reversed(colors)),flags=16 if mat.get('double_sided',False) else 0)
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
