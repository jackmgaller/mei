#!/usr/bin/env python3
"""Deterministic, shared INPUTS for Mei and the independent reference renderer.

Writes the nine-view stress scene's cart source, meshes, textures, palette and scene.json
to BUILD/reference_renderer/carts/scene/ (common.py); oracle.py compiles and checks it.
"""
import json
import math
import struct
import common
from meshlib import Mesh, rgb, DOUBLE, SEMI

OUT = common.cart_dir('scene')
UV = [(0, 255), (255, 255), (0, 0), (255, 0)]
MATERIALS = [(4, True, 0), (7, True, 7), (2, False, 2),
             (13, False, 3), (15, False, 3), (None, False, 0)]


def material(m, corners, number, colours=None, semi=False, blend=0, window=0):
    slot, four, palette = MATERIALS[number % len(MATERIALS)]
    colours = colours or [rgb(96, 108, 128), rgb(128, 96, 112),
                          rgb(168, 156, 140), rgb(140, 168, 156)]
    m.face(corners, colours[:len(corners)], UV[:len(corners)] if slot is not None else None,
           flags=SEMI if semi else 0, slot=slot or 0, four_bit=four,
           palette=palette, blend=blend, window=window)


def cube(number):
    m = Mesh()
    for normal, up in [((0, 0, -1), (0, 1, 0)), ((0, 0, 1), (0, 1, 0)),
                       ((-1, 0, 0), (0, 1, 0)), ((1, 0, 0), (0, 1, 0)),
                       ((0, 1, 0), (0, 0, 1)), ((0, -1, 0), (0, 0, -1))]:
        a, b = up, tuple(-x for x in normal)
        right = (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
        ids = [m.vertex(*(0.65*(normal[k]+right[k]*x+up[k]*y) for k in range(3)))
               for x, y in [(-1, -1), (1, -1), (-1, 1), (1, 1)]]
        material(m, ids, number)
    return m


def sphere():
    m = Mesh()
    # Triangles with independent corners keep poles/UV seams explicit.
    for j in range(6):
        for i in range(12):
            points = []
            for u, v in [(i, j), (i+1, j), (i, j+1), (i+1, j+1)]:
                a, b = u*math.tau/12, v*math.pi/6
                points.append((0.8*math.sin(b)*math.cos(a), 0.8*math.cos(b), 0.8*math.sin(b)*math.sin(a)))
            ids = [m.vertex(*p) for p in points]
            # Double-sided deliberately exercises both GPU windings.
            m.quad(ids, [rgb(230, 70, 45), rgb(70, 210, 130), rgb(60, 110, 240), rgb(240, 205, 90)], flags=DOUBLE)
    return m


def generate():
    OUT.mkdir(exist_ok=True)
    assets = {f'cube{i}': cube(i) for i in range(6)}
    floor = Mesh()
    for j in range(10):
        for i in range(10):
            ids = [floor.vertex((i-5+x)*1.6, -1, (j+y)*1.6-2) for x,y in [(0,0),(1,0),(0,1),(1,1)]]
            material(floor, ids, (i+j)%5, [rgb(128,128,128)]*4)
    assets['floor'] = floor
    assets['sphere'] = sphere()
    glass = Mesh()
    for i in range(4):
        ids = [glass.vertex(-5+i*2.6+x*1.7, -0.8+y*2.8, 0.7+y*0.2) for x,y in [(0,0),(1,0),(0,1),(1,1)]]
        material(glass, ids, i, semi=True, blend=i)
        glass.faces[-1] = bytes([glass.faces[-1][0] | DOUBLE]) + glass.faces[-1][1:]
    assets['glass'] = glass
    # Slanted textured triangles cross the near and guard planes in the diagnostic views.
    # The second clipping triangle has a texture window: clipped pieces must keep it.
    clip = Mesh()
    for i in range(4):
        ids = [clip.vertex(*p) for p in [(-1.4+i, -0.7, -3.8),(-0.7+i, 1.2, -2.2),(0.1+i,-0.6,0.8)]]
        material(clip, ids, i, window=clip.window(u=(32, 64), v=(16, 128)) if i == 1 else 0)
        clip.faces[-1] = bytes([clip.faces[-1][0] | DOUBLE]) + clip.faces[-1][1:]
    assets['clip'] = clip
    # Texture windows (DECISIONS.md, "Texture windows"): a row of five panels over the boxes,
    # both texture depths, one axis or both, and an origin plus size past 256 (wraps to 0).
    tiles = Mesh()
    windows = [tiles.window(u=(16, 32), v=(16, 64)), tiles.window(u=(32, 240), v=(64, 0)),
               tiles.window(u=(8, 128)), tiles.window(v=(128, 192)),
               tiles.window(u=(256, 0), v=(8, 248))]
    for i, window in enumerate(windows):
        ids = [tiles.vertex(-4.6+i*1.9+x*1.6, 2.4+y*1.1, 1.5+y*0.3) for x,y in [(0,0),(1,0),(0,1),(1,1)]]
        material(tiles, ids, [0, 2, 1, 4, 3][i], window=window)
    assets['tiles'] = tiles
    for name, mesh in assets.items():
        (OUT / f'{name}.bin').write_bytes(mesh.pack())
    def c15(r,g,b):
        return (r>>3) | ((g>>3)<<5) | ((b>>3)<<10)
    palette = []
    for i in range(4096):
        level = 45 + (i*23 % 160)
        palette.append(c15(level, min(255,level+14), min(255,level+24)))
    for i in range(1,16):
        palette[i] = c15(90+i*9, 40+i*5, 30+i*3)
        palette[7*16+i] = c15(35+i*4, 80+i*9, 65+i*6)
    for i in range(256):
        light = 75 + (i*13 % 135)
        palette[2*256+i] = c15(light-25, light, min(255,light+25))
        palette[3*256+i] = c15(min(255,light+28), light, max(0,light-38))
    (OUT/'palette.bin').write_bytes(struct.pack('<4096H', *palette))
    textures = []
    for slot, four in [(4,True),(7,True),(2,False),(13,False),(15,False)]:
        data = bytearray(32768 if four else 65536)
        for y in range(256):
            for x in range(256):
                if slot == 4:
                    idx = 1 if y%16==15 or (x+(8 if y//16%2 else 0))%32==31 else 2+(x//8+y//8)%13
                elif slot == 7:
                    idx = 0 if (x//16+y//16)%4==0 else 1+(x//16+y//16)%15
                else:
                    idx = (x//8 + y//8*17 + slot*9)%256
                if four:
                    data[y*128+x//2] |= idx << (4*(x%2))
                else:
                    data[y*256+x] = idx
        path = f'tex{slot}.bin'
        (OUT/path).write_bytes(data)
        textures.append({'slot':slot,'file':path})
    instances = [{'mesh':'floor','position':[0,0,0]}]
    for j in range(5):
        for i in range(6):
            instances.append({'mesh':f'cube{(i+j)%6}','position':[(i-2.5)*1.8,-0.35+(j%2)*0.4,j*2.5+1]})
    for i in range(5):
        instances.append({'mesh':'sphere','position':[(i-2)*2.3,1.8,5.5+i%2*2]})
    instances += [{'mesh':'glass','position':[0,0,0]}, {'mesh':'clip','position':[0,0,0]},
                  {'mesh':'tiles','position':[0,0,0]}]
    views = [
        ('overview', [[1.125,0,0,0],[0,1.44,0.42,-3],[0,-0.28,0.96,11],[0,-0.28,0.96,11]]),
        ('fractional', [[1.125,0,0,-0.173],[0,1.44,0.42,-2.983],[0,-0.28,0.96,11.013],[0,-0.28,0.96,11.013]]),
        ('side', [[0.9,0,-0.675,-2.25],[0.252,1.44,0.336,-2.58],[0.576,-0.28,0.768,11.96],[0.576,-0.28,0.768,11.96]]),
        ('near', [[1.125,0,0,0],[0,1.5,0,-0.5],[0,0,1,3],[0,0,1,3]]),
        ('guard', [[3,0,0,0],[0,3,0,0],[0,0,1,2.3],[0,0,1,2.3]]),
    ]
    cases = [{'name': name, 'matrix':matrix,'dither':True,'fog':False} for name,matrix in views]
    cases += [{'name':'no_dither','matrix':views[0][1],'dither':False,'fog':False},
              {'name':'fog','matrix':views[0][1],'dither':True,'fog':True},
              {'name':'near_fog','matrix':views[3][1],'dither':True,'fog':True},
              {'name':'model_transform','matrix':views[0][1],'dither':True,'fog':False,'models':True}]
    manifest = {'textures':textures,'instances':instances,'cases':cases,'background':[24,32,48], 'near':0.5,'far':32}
    (OUT/'scene.json').write_text(json.dumps(manifest,indent=2)+'\n')
    lines = ['// Generated by tests/reference_renderer/gen_scene.py. A/B select a deterministic view.',
             'cart "Reference Renderer"']
    for name in assets:
        lines.append(f'embed {name.upper()}: Mesh = "{name}.bin"')
    lines.append('embed PALETTE: u16 = "palette.bin"')
    for tex in textures:
        lines.append(f'embed TEX{tex["slot"]}: u8 = "{tex["file"]}"')
    lines += ['var selected: s32', 'fn init() {', '    camera_clip(0.5, 32.0)', '    load_palette(0, PALETTE, len(PALETTE))']
    # Slot 15's second half wraps to slot 0, matching the documented texture addressing.
    for tex in textures:
        slot=tex['slot']
        if slot == 15:
            lines += ['    load_texture(15, TEX15, 32768)', '    load_texture(0, TEX15 + 32768, 32768)']
        else:
            lines.append(f'    load_texture({slot}, TEX{slot}, len(TEX{slot}))')
    lines += ['}', 'fn update() {', f'    if btnp(A) {{ selected = (selected + 1) % {len(cases)} }}', f'    if btnp(B) {{ selected = (selected + {len(cases)-1}) % {len(cases)} }}', '}', 'fn draw() {', '    cls(rgb(24, 32, 48))', '    var view: mat4']
    for i,case in enumerate(cases):
        lines.append(f'    if selected == {i} {{ // {case["name"]}')
        for row,values in enumerate(case['matrix']):
            lines.append(f'        view[{row}] = vec4({", ".join(str(float(x)) for x in values)})')
        lines.append(f'        dither({str(case["dither"]).lower()})')
        lines.append('        fog(rgb(65, 80, 110), 6.0, 24.0)' if case['fog'] else '        fog_off()')
        lines.append('    }')
    lines += ['    camera_matrix(view)']
    for obj in instances:
        if obj['mesh'].startswith('cube'):
            x,y,z=obj['position']
            lines += ['    if selected == 8 {', '        var model: mat4',
                      f'        model[0] = vec4(0.9, 0.0, 0.45, {float(x)})',
                      f'        model[1] = vec4(0.0, 1.25, 0.0, {float(y)})',
                      f'        model[2] = vec4(-0.675, 0.0, 0.6, {float(z)})',
                      '        model[3] = vec4(0.0, 0.0, 0.0, 1.0)',
                      f'        mesh_xf({obj["mesh"].upper()}, model)', '    } else {']
        lines.append(f'    mesh_at({obj["mesh"].upper()}, vec3({", ".join(str(float(x)) for x in obj["position"])}), 0.0)')
        if obj['mesh'].startswith('cube'):
            lines.append('    }')
    lines += ['}']
    (OUT/'scene.akr').write_text('\n'.join(lines)+'\n')
    print(f'Generated {len(instances)} mesh instances, {len(cases)} cases in {OUT}')

if __name__ == '__main__':
    generate()
