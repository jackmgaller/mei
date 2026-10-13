"""`mei_anim.py export`: every move of every mech baked frame by frame into the runtime's data,
anim_data.akr and anims/anim_data.bin (docs/ANIMKIT.md, "The exported data").

Per move, per frame: each part's matrix relative to the root (rotation as 4.12 fixed point,
translation 16.16), the boxes (anim.akr's Box records), the marks and the root motion. A move
with no file gets a stand-in: the mech's _body.anim.json (else its rig's guard pose), so every
move of the list can be drawn and has boxes from the start. A mech in the list whose rig is not
there yet (a mech added to anim.akr's Mech before its model) gets the first mech's stand-in and
meshes, so the runtime's tables have a row for every Mech.
"""
from pathlib import Path
import struct

from .move import Move, KINDS
from .rig import AnimError, PARTS, load_rig

# anim.akr's enums, in order
MECHS = ['hero', 'doubleblade', 'beam', 'tank', 'twins', 'twin_a', 'twin_b']
MOVES = ['idle', 'walk_f', 'walk_b', 'crouch', 'jump', 'land', 'block', 'hit_high', 'hit_low', 'hit_air',
         'knockdown', 'getup', 'ko', 'win', 'intro', 'atk_n', 'atk_f', 'atk_d', 'atk_air', 'sp_n', 'sp_f', 'sp_u',
         'sp_d', 'grab', 'grab_whiff', 'throw', 'thrown', 'grab_break', 'super', 'thrown_vault',
         'thrown_slam', 'combine', 'split']
BODY = '_body.anim.json'
LOOPING = {'idle', 'walk_f', 'walk_b', 'crouch', 'block'}   # stand-ins for these loop
XF_BYTES = 32           # anim.akr's PartXf: [10]fixed16 (9 used), [3]fixed
BOX_BYTES = 20          # anim.akr's Box: kind, hit, part, pad, x0, y0, x1, y1
FLAG_LOOP, FLAG_AIR, FLAG_STANDIN = 1, 2, 4
ROT_ONE = 4096          # fixed16 is 4.12


def s16(v):
    n = round(v*ROT_ONE)
    if not -32768 <= n <= 32767:
        raise AnimError('/export', f'A rotation entry {v} does not fit 4.12 fixed point.')
    return n


def fixed(v):
    n = round(v*65536)
    if not -2**31 <= n < 2**31:
        raise AnimError('/export', f'{v} does not fit 16.16 fixed point.')
    return n


def frame_bytes(mats):
    out = bytearray()
    for pid in PARTS:
        m = mats.get(pid)
        if m is None:           # a joint the rig lacks entirely: the pelvis's frame
            m = mats['pelvis']
        r = [m[i][j] for i in range(3) for j in range(3)]
        out += struct.pack('<10h3i', *(s16(v) for v in r), 0, *(fixed(m[i][3]) for i in range(3)))
    return bytes(out)


def bake(move):
    """The move's sections: (frames, box_first, boxes, marks, root) bytes, and a summary."""
    frames, first, boxes, root = bytearray(), [], bytearray(), bytearray()
    count = 0
    for f in range(move.length):
        mats = move.matrices(f)
        frames += frame_bytes(mats)
        first.append(count)
        for name, kind, hit, part, x0, y0, x1, y1 in move.boxes_at(f, mats):
            boxes += struct.pack('<4B4i', KINDS[kind], hit, PARTS.index(part), 0, *(fixed(v) for v in (x0, y0, x1, y1)))
            count += 1
    first.append(count)
    if count > 65535:
        raise AnimError('/export', f'{move.name}: {count} boxes is too many for one move (65,535).')
    marks = struct.pack(f'<{move.length}I', *move.marks)
    for dx, dy in move.motion_raw():
        root += struct.pack('<2i', dx, dy)
    return bytes(frames), struct.pack(f'<{len(first)}H', *first), bytes(boxes), marks, bytes(root)


def find_moves(anims, mechs=MECHS):
    """{(mech, move): path} for the files present, and warnings for files that are not moves."""
    found, warnings = {}, []
    for mech in mechs:
        folder = Path(anims)/mech
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob('*.anim.json')):
            name = path.name[:-len('.anim.json')]
            if name.startswith('_'):
                continue
            if name not in MOVES:
                warnings.append(f'{path}: {name} is not in the move list (anim.akr\'s Mv); not exported')
                continue
            found[(mech, name)] = path
    return found, warnings


def rig_path(cart, mech):
    return Path(cart)/'models'/mech/f'{mech}.rig.json'


def standin(anims, cart, mech, move):
    """The move used where a mech has no file for one: its _body.anim.json, else a generated
    guard pose."""
    body = Path(anims)/mech/BODY
    if body.is_file():
        return Move(body, rig_path(cart, mech), move)
    raise AnimError('/export', f'{mech} has no {move}.anim.json and no {BODY} to stand in for it ({body}).')


def export(anims, cart, out, meshes=True, pack='assets.akr', override=None):
    """Bakes every move into out/anim_data.akr and out/anims/anim_data.bin. anims: the folder of
    MECH/MOVE.anim.json; cart: the cart folder (its models/MECH/MECH.rig.json); override:
    {(mech, move): path} used in place of (or as well as) the files found. Returns the report."""
    found, warnings = find_moves(anims)
    found.update(override or {})
    blob = bytearray()
    headers, report = [], []

    def put(data):
        while len(blob) % 4:
            blob.append(0)
        at = len(blob)
        blob.extend(data)
        return at

    body_cache, baked = {}, {}
    rigged = [m for m in MECHS if rig_path(cart, m).is_file()]
    for mech in MECHS:
        if mech not in rigged:
            warnings.append(f'{mech}: no rig yet ({rig_path(cart, mech)}); its moves and meshes are '
                            f'{MECHS[0]}\'s stand-in')
        for mv in MOVES:
            path = found.get((mech, mv)) if mech in rigged else None
            flags = 0
            if path:
                move = Move(path, None, mv)
            else:
                stand = mech if mech in rigged else MECHS[0]
                if stand not in body_cache:
                    body_cache[stand] = standin(anims, cart, stand, mv)
                move = body_cache[stand]
                flags |= FLAG_STANDIN
                if mv in LOOPING:
                    flags |= FLAG_LOOP
            for w in move.warnings:
                warnings.append(f'{mech}/{mv} {w["path"]}: {w["message"]}')
            if move.loop:
                flags |= FLAG_LOOP
            if move.air:
                flags |= FLAG_AIR
            # a stand-in is baked once per mech and shared by the moves it stands in for
            # (keyed by the object, which the table keeps alive: an id() alone can be reused)
            if id(move) not in baked:
                sections = bake(move)
                baked[id(move)] = (move, [put(s) for s in sections], sum(len(s) for s in sections))
            _, offs, size = baked[id(move)]
            headers.append((move.length, flags, *offs))
            report.append({'mech': mech, 'move': mv, 'file': str(path) if path else None, 'length': move.length,
                           'stand_in': not path, 'bytes': size if path else 0})
    out = Path(out)
    (out/'anims').mkdir(parents=True, exist_ok=True)
    bin_path = out/'anims'/'anim_data.bin'
    bin_path.write_bytes(bytes(blob))
    rigs = [load_rig(rig_path(cart, mech if mech in rigged else MECHS[0])) for mech in MECHS]
    lines = ['// Generated by tools/mei_anim.py export - do not edit.',
             '// Every move of both mechs baked frame by frame (docs/ANIMKIT.md, "The exported data"), for',
             '// anim.akr: the moves in Mech then Mv order, their sections in anims/anim_data.bin.']
    if meshes:
        lines.append(f'import "{pack}"')
    lines += ['', 'embed AK_BLOB: u8 = "anims/anim_data.bin"', '',
              f'const AK_MOVES: [{len(headers)}]AnimMove = [']
    for (length, flags, fr, fi, bx, mk, rt), r in zip(headers, report):
        lines.append(f'    AnimMove {{ len: {length}, flags: {flags}, frames: {fr}, box_first: {fi}, boxes: {bx}, '
                     f'marks: {mk}, root: {rt} }},   // {r["mech"]} {r["move"]}' + (' (stand-in)' if r['stand_in'] else ''))
    lines += [']', '']
    names = []
    for rig in rigs:
        for pid in PARTS:
            asset = rig.joints.get(pid, {}).get('asset') if meshes else None
            names.append(asset or 'null')
    lines += [f'// each mech\'s part meshes in anim.akr\'s Part order (null: no mesh)',
              f'const AK_MESH: [{len(names)}]*Mesh = [']
    for k in range(0, len(names), len(PARTS)):
        lines.append('    ' + ', '.join(names[k:k+len(PARTS)]) + ',')
    lines += [']', '']
    (out/'anim_data.akr').write_text('\n'.join(lines))
    return {'ok': True, 'output': str(out), 'files': [str(out/'anim_data.akr'), str(bin_path)],
            'bytes': len(blob), 'moves': report, 'warnings': warnings}
