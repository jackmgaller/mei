"""The Animation Kit (tools/mei_anim.py, tools/animkit/): the move format, sampling, plants and
reaches, the authoring fields (retime, relative, aim, travel, floor, ...), the checks, pose and
fmt, the export's layout, and the runtime (carts/mechexpo/anim.akr) against the kit's numbers. Standard library only; the runtime test needs meic and mei-headless (MEIC and
RUN, else $B, else build/) and is skipped without them.

    python3 -m unittest discover -s tests -p test_animkit.py -v
"""
import json
import math
import os
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))

from animkit.rig import AnimError, load_rig, rot_xyz, apply, PARTS, SKELETON  # noqa: E402
from animkit.move import Move, ease, MARKS                                  # noqa: E402
from animkit.verify import verify                                           # noqa: E402
from animkit import export as EX                                            # noqa: E402

CART = ROOT/'carts'/'mechexpo'
HERO_RIG = CART/'models'/'hero'/'hero.rig.json'
DB_RIG = CART/'models'/'doubleblade'/'doubleblade.rig.json'
SERAPH_RIG = CART/'models'/'seraph'/'seraph.rig.json'
ATK_F = CART/'anims'/'hero'/'atk_f.anim.json'
BODY = CART/'anims'/'hero'/'_body.anim.json'


def tool(variable, name):
    if os.environ.get(variable):
        return Path(os.environ[variable])
    return ROOT/os.environ.get('B', 'build')/name


class Files:
    """Moves written into a temporary folder for a test."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def move(self, name='m', **fields):
        data = {'format': 'mei-anim', 'version': 1, 'rig': str(HERO_RIG), 'length': 20,
                'keys': [{'at': 0, 'from': 'guard'}]}
        if 'base' in fields and 'length' not in fields:
            del data['length']          # from the base
        data.update(fields)
        path = self.dir/f'{name}.anim.json'
        path.write_text(json.dumps(data))
        return path


class RigTests(unittest.TestCase):
    def test_rotation_matches_the_asset_kit(self):
        from assetkit.geometry import rotate
        rnd = random.Random(1)
        for _ in range(50):
            angles = [rnd.uniform(-180, 180) for _ in range(3)]
            p = [rnd.uniform(-2, 2) for _ in range(3)]
            want = rotate(p, angles)
            got = apply(rot_xyz(angles), p)
            for a, b in zip(want, got):
                self.assertAlmostEqual(a, b, places=9)

    def test_guard_stands_on_the_floor(self):
        for path in (HERO_RIG, DB_RIG):
            rig = load_rig(path)
            g = rig.poses['guard']
            mats = rig.pose_matrices(g['rotate'], g['offset'])
            low = min(apply(mats[j], v)[1] for j, px in rig.proxies().items() for v in px['points'])
            self.assertLess(abs(low), 0.03, path)

    def test_every_part_has_a_joint(self):
        for path in (HERO_RIG, DB_RIG, SERAPH_RIG):
            rig = load_rig(path)
            for pid in SKELETON:
                self.assertIn(pid, rig.joints, f'{path}: {pid}')
        # the joints appended after the shared skeleton are Seraph's alone
        self.assertEqual(PARTS[len(SKELETON):], ['wing_l', 'wing_r', 'halo'])
        for pid in PARTS[len(SKELETON):]:
            self.assertIn(pid, load_rig(SERAPH_RIG).joints)
            self.assertNotIn(pid, load_rig(HERO_RIG).joints)

    def test_part_count(self):
        self.assertEqual(EX.part_count(load_rig(HERO_RIG)), len(SKELETON))
        self.assertEqual(EX.part_count(load_rig(SERAPH_RIG)), len(PARTS))


class FormatTests(Files, unittest.TestCase):
    def error(self, **fields):
        with self.assertRaises(AnimError) as ctx:
            Move(self.move(**fields))
        return ctx.exception

    def test_errors_name_the_path(self):
        self.assertEqual(self.error(colour=1).path, '/colour')
        e = self.error(keys=[{'at': 0}, {'at': 5, 'pose': {'torso': [0, 0, 0]}}, {'at': 3, 'pose': {}}])
        self.assertEqual(e.path, '/keys/2/at')
        self.assertEqual(self.error(keys=[{'at': 2}]).path, '/keys/0/at')
        self.assertEqual(self.error(keys=[{'at': 0, 'pose': {'tail': [0, 0, 0]}}]).path, '/keys/0/pose/tail')
        self.assertEqual(self.error(keys=[{'at': 0, 'ease': 'bounce'}]).path, '/keys/0/ease')
        self.assertEqual(self.error(marks={'sparkle': [1]}).path, '/marks/sparkle')
        self.assertEqual(self.error(marks={'cancel': [[5, 30]]}).path, '/marks/cancel/0')
        self.assertEqual(self.error(boxes={'b': {'kind': 'hit', 'part': 'tail'}}).path, '/boxes/b/part')
        self.assertEqual(self.error(plant={'torso': [[0, 3]]}).path, '/plant/torso')

    def test_every_mark_is_a_bit(self):
        self.assertEqual(sorted(MARKS.values()), [1 << k for k in range(len(MARKS))])
        akr = (CART/'anim.akr').read_text()
        for name, bit in MARKS.items():
            const = {'invuln': 'INVULN', 'armour': 'ARMOUR'}.get(name, name.upper())
            self.assertIn(f'const MARK_{const}: u32 = {bit}', akr)

    def test_parts_match_the_runtime(self):
        akr = '\n'.join(line.split('//')[0] for line in (CART/'anim.akr').read_text().splitlines())
        block = akr[akr.index('enum Part {'):]
        block = block[:block.index('}')]
        names = [n.strip() for n in block[len('enum Part {'):].replace('\n', ' ').split(',') if n.strip()]
        self.assertEqual(names, PARTS)
        block = akr[akr.index('enum Mv {'):]
        block = block[:block.index('}')]
        names = [n.strip() for n in block[len('enum Mv {'):].replace('\n', ' ').split(',') if n.strip()]
        self.assertEqual(names, EX.MOVES)


class SamplingTests(Files, unittest.TestCase):
    def test_eases(self):
        self.assertEqual(ease('linear', 0.25), 0.25)
        self.assertEqual(ease('hold', 0.9), 0.0)
        self.assertEqual(ease('ease', 0.5), 0.5)
        self.assertLess(ease('in', 0.5), 0.5)
        self.assertGreater(ease('out', 0.5), 0.5)

    def test_keys_carry_and_interpolate(self):
        m = Move(self.move(keys=[{'at': 0, 'pose': {'torso': [0, 0, 0]}, 'ease': 'linear'},
                                 {'at': 10, 'pose': {'torso': [20, 0, 0]}},
                                 {'at': 12, 'boxes': {}}]))
        rot, off = m.pose_at(5)
        self.assertAlmostEqual(rot['torso'][0], 10.0)
        # an untouched joint keeps the guard's angle; a box-only key is not a pose key
        self.assertEqual(rot['thigh_r'], load_rig(HERO_RIG).poses['guard']['rotate']['thigh_r'])
        self.assertEqual([k[0] for k in m.pose_keys], [0, 10])
        self.assertEqual(m.pose_at(15)[0]['torso'], [20.0, 0, 0])

    def test_a_loop_returns_to_its_first_key(self):
        m = Move(self.move(loop=True, keys=[{'at': 0, 'pose': {'head': [0, 0, 0]}, 'ease': 'linear'},
                                            {'at': 10, 'pose': {'head': [10, 0, 0]}, 'ease': 'linear'}]))
        self.assertAlmostEqual(m.pose_at(15)[0]['head'][0], 5.0)
        self.assertAlmostEqual(m.pose_at(25)[0]['head'][0], m.pose_at(5)[0]['head'][0])

    def test_motion_adds_up_exactly(self):
        m = Move(self.move(motion=[{'from': 2, 'to': 9, 'by': [1.3, 0.25], 'ease': 'out'},
                                   {'from': 12, 'to': 13, 'by': [-9.0, 0]}]))
        raw = m.motion_raw()
        self.assertEqual(sum(d[0] for d in raw), round(1.3*65536)+round(-9.0*65536))
        self.assertEqual(sum(d[1] for d in raw), round(0.25*65536))
        self.assertEqual(raw[12][0], -9*65536)
        self.assertEqual(raw[0], (0, 0))

    def test_boxes_follow_their_parts(self):
        m = Move(self.move(boxes={'r': {'kind': 'push', 'rect': [-1, 0, 1, 10]},
                                  'blade': {'kind': 'hit', 'part': 'weapon_r', 'min': [-0.1, 1, -0.3],
                                            'max': [0.1, 7, 0.3], 'split': 3}}))
        mats = m.matrices(0)
        boxes = {b[0]: b for b in m.boxes_at(0, mats)}
        self.assertEqual(boxes['r'][4:], (-1.0, 0.0, 1.0, 10.0))
        self.assertEqual(sorted(n for n in boxes if n.startswith('blade')), ['blade.0', 'blade.1', 'blade.2'])
        tip = apply(mats['weapon_r'], (0, 7, 0))
        self.assertTrue(any(b[4] - 0.01 <= -tip[2] <= b[6] + 0.01 and b[5] - 0.01 <= tip[1] <= b[7] + 0.01
                            for n, b in boxes.items() if n.startswith('blade')))

    def test_a_plant_holds_the_foot_through_root_motion(self):
        m = Move(ATK_F)
        start = m.matrices(13)['foot_l']
        t0 = m.root_travel(13)
        for f in range(13, m.length):
            foot = m.matrices(f)['foot_l']
            t = m.root_travel(f)
            self.assertAlmostEqual(foot[1][3], start[1][3], places=3)
            # in the world: the root's travel forward is -Z in the root's frame
            self.assertAlmostEqual(-foot[2][3]+t[0], -start[2][3]+t0[0], places=3)
            self.assertAlmostEqual(foot[1][1], 1.0, places=6)      # level

    def test_a_base_is_merged(self):
        derived = self.move('d', base=str(ATK_F), rig=str(DB_RIG),
                            keys=[{'at': 4, 'pose': {'head': [30, 0, 0]}}, {'at': 27, 'remove': True}],
                            boxes={'pelvis': None})
        m = Move(derived)
        base = Move(ATK_F)
        self.assertEqual(m.rig.name, 'doubleblade')
        self.assertEqual(m.length, base.length)
        self.assertEqual([k[0] for k in m.pose_keys], [k[0] for k in base.pose_keys if k[0] != 27])
        self.assertEqual(m.pose_keys[1][2]['head'], [30.0, 0.0, 0.0])
        self.assertEqual(m.pose_keys[1][2]['torso'], base.pose_keys[1][2]['torso'])
        self.assertNotIn('pelvis', m.boxes0)
        self.assertIn('head', m.boxes0)


class VerifyTests(Files, unittest.TestCase):
    def test_the_proof_move_passes(self):
        r = verify(ATK_F)
        self.assertTrue(r['ok'], r['failures'])

    def test_timing(self):
        hit = {'kind': 'hit', 'part': 'weapon_r'}
        r = verify(self.move(base=str(BODY), length=20, phases={'startup': 5, 'active': 3, 'recovery': 12},
                             keys=[{'at': 0, 'from': 'guard'}, {'at': 5, 'boxes': {'h': hit}}, {'at': 7, 'boxes': {'h': None}}]))
        self.assertEqual([f['check'] for f in r['failures']], ['timing'])
        self.assertIn('no hit box on active frame 7', r['failures'][0]['message'])
        r = verify(self.move(base=str(BODY), length=20, phases={'startup': 5, 'active': 3, 'recovery': 10},
                             keys=[{'at': 0, 'from': 'guard'}, {'at': 5, 'boxes': {'h': hit}}, {'at': 8, 'boxes': {'h': None}}]))
        self.assertIn('add up', r['failures'][0]['message'])

    def test_no_hurt_box(self):
        r = verify(self.move())
        self.assertIn('boxes', [f['check'] for f in r['failures']])
        r = verify(self.move(marks={'nopush': [[0, 19]]}))
        self.assertNotIn('boxes', [f['check'] for f in r['failures']])

    def test_boxes_below_the_root(self):
        low = {'low': {'kind': 'hurt', 'rect': [0, -3, 1, 1]}}
        r = verify(self.move(base=str(BODY), length=20, boxes=low))
        self.assertTrue(any('Box low' in f['message'] for f in r['failures']))
        r = verify(self.move(base=str(BODY), length=20, air=True, boxes=low))
        self.assertFalse(any('Box low' in f['message'] for f in r['failures']), r['failures'])
        r = verify(self.move(base=str(BODY), length=20, air=True, boxes={'low': {'kind': 'hurt', 'rect': [0, -5, 1, 1]}}))
        self.assertTrue(any('Box low' in f['message'] for f in r['failures']))

    def test_sinking_and_passing_through(self):
        r = verify(self.move(base=str(BODY), keys=[{'at': 0, 'from': 'guard', 'offset': [0, -2.5]}]))
        self.assertIn('floor', [f['check'] for f in r['failures']])
        # the sword arm swung back through the body
        r = verify(self.move(base=str(BODY), keys=[{'at': 0, 'from': 'guard', 'ease': 'linear'},
                                                   {'at': 10, 'pose': {'upper_arm_r': [-10, 0, 60], 'forearm_r': [0, 0, 0],
                                                                       'hand_r': [0, 0, 0]}}]))
        parts = [tuple(f['parts']) for f in r['failures'] if f['check'] == 'parts']
        self.assertTrue(any('torso' in p or 'pelvis' in p for p in parts), r['failures'])

    def test_a_plant_out_of_reach(self):
        r = verify(self.move(base=str(BODY), motion=[{'from': 0, 'to': 10, 'by': [6, 0]}],
                             plant={'foot_l': [[0, 19]]}))
        self.assertTrue(any('cannot be held' in f['message'] for f in r['failures']))


def blade(mats, part='weapon_r'):
    """[elevation, yaw] of a part's +Y, as "aim" gives them."""
    m = mats[part]
    return (math.degrees(math.asin(m[1][1])), math.degrees(math.atan2(m[0][1], -m[2][1])))


class AuthoringTests(Files, unittest.TestCase):
    """The fields that save the animator work: retime, relative, the guard's foot, aim, travel,
    ending a reach, its own ease, floor, and the allow lists."""

    def test_retime_moves_keys_motion_plants_and_marks(self):
        base = self.move('b', length=40, keys=[{'at': 0, 'from': 'guard', 'ease': 'linear'},
                                                {'at': 10, 'pose': {'head': [10, 0, 0]}},
                                                {'at': 11, 'boxes': {}, 'note': 'merges into 10'},
                                                {'at': 20, 'pose': {'head': [20, 0, 0]}},
                                                {'at': 39, 'from': 'guard'}],
                         motion=[{'from': 10, 'to': 20, 'by': [2, 0]}], plant={'foot_l': [[0, 10], [20, 39]]},
                         marks={'step': [10, [20, 22]]})
        m = Move(self.move('d', base=str(base), retime=[[0, 0], [10, 6], [20, 14]],
                           keys=[{'at': 14, 'pose': {'torso': [5, 0, 0]}}]))
        self.assertEqual(m.length, 34)                      # 39 -> 33 (shifted one for one after 20)
        self.assertEqual([k[0] for k in m.pose_keys], [0, 6, 14, 33])
        self.assertEqual(m.pose_keys[1][2]['head'], [10.0, 0.0, 0.0])
        self.assertEqual(m.pose_keys[2][2]['torso'], [5.0, 0.0, 0.0])
        self.assertEqual(m.pose_keys[2][2]['head'], [20.0, 0.0, 0.0])
        self.assertEqual(m.motion, [(6, 14, [2, 0], 'linear')])
        self.assertEqual(m.plants['foot_l'][2], [(0, 6), (14, 33)])
        self.assertEqual([f for f in range(m.length) if m.marks[f]], [6, 14, 15, 16])
        # the frame map: linear between pairs, halves up
        from animkit.move import retime_map
        f = retime_map([[0, 0], [3, 2], [6, 5]])
        self.assertEqual([f(x) for x in range(8)], [0, 1, 1, 2, 3, 4, 5, 6])
        e = None
        try:
            Move(self.move('e', base=str(base), retime=[[10, 0], [5, 3]]))
        except AnimError as error:
            e = error
        self.assertEqual(e.path, '/retime/1')

    def test_relative_keys_add_to_the_guard(self):
        guard = load_rig(DB_RIG).poses['guard']
        hero = self.move('h', keys=[{'at': 0, 'from': 'guard', 'relative': True,
                                     'pose': {'torso': [-10, 4, 0]}, 'offset': [0.2, -0.5]}])
        m = Move(self.move('d', base=str(hero), rig=str(DB_RIG)))
        self.assertEqual(m.pose_keys[0][2]['torso'], [a+b for a, b in zip(guard['rotate']['torso'], [-10, 4, 0])])
        self.assertEqual(m.pose_keys[0][3], [0.2, guard['offset'][1]-0.5])
        self.assertEqual(m.pose_keys[0][2]['head'], guard['rotate']['head'])

    def test_the_guard_foot(self):
        for rig, want in ((HERO_RIG, -2.51), (DB_RIG, -2.94)):
            m = Move(self.move(rig=str(rig), keys=[{'at': 0, 'from': 'guard', 'reach': {'foot_l': 'guard'}}]))
            self.assertEqual(m.reach['foot_l'][0][2], [want, 0.0])

    def test_aim_points_the_blade(self):
        for torso in ([0, 0, 0], [-12, -40, 8]):
            for aim in ([0, 0], [35, -25], [-70, 60], [10, 150]):
                m = Move(self.move(length=2, keys=[{'at': 0, 'from': 'guard', 'aim': {'weapon_r': aim},
                                                    'pose': {'torso': torso, 'upper_arm_r': [70, 10, -20]}}]))
                e, y = blade(m.matrices(0))
                self.assertLess(abs(e-aim[0]), 0.05, (torso, aim))
                self.assertLess(abs((y-aim[1]+180) % 360-180), 0.05, (torso, aim))
        # the wrist turns as little as it can: an aim where the blade already points keeps the guard's wrist
        g = Move(self.move(length=2))
        m = Move(self.move(length=2, keys=[{'at': 0, 'from': 'guard', 'aim': {'weapon_r': list(blade(g.matrices(0)))}}]))
        for a, b in zip(m.pose_keys[0][2]['hand_r'], load_rig(HERO_RIG).poses['guard']['rotate']['hand_r']):
            self.assertAlmostEqual(a, b, places=1)

    def test_travel_holds_plants_in_the_world(self):
        walk = dict(base=str(BODY), length=20, plant={'foot_r': [[0, 19]], 'foot_l': [[0, 19]]},
                    keys=[{'at': 0, 'from': 'guard', 'reach': {'foot_r': 'guard', 'foot_l': 'guard'}}])
        m = Move(self.move(travel=0.1, **walk))
        self.assertEqual(m.motion_raw()[5], (0, 0))          # the fight moves the root, not the export
        for f in (0, 10, 19):
            self.assertAlmostEqual(-m.matrices(f)['foot_r'][2][3]+0.1*f, -m.matrices(0)['foot_r'][2][3], places=3)
        r = verify(self.move(travel=0.1, **walk))
        self.assertFalse(any(w['check'] == 'slides' for w in r['warnings']), r['warnings'])
        # the same foot held relative to the root slides once the fight moves the root
        r = verify(self.move(travel=0.1, base=str(BODY), length=20))
        self.assertTrue(any(w['check'] == 'slides' for w in r['warnings']))

    def test_a_reach_track_can_end(self):
        m = Move(self.move(base=str(BODY), keys=[{'at': 0, 'from': 'guard', 'reach': {'foot_l': [-2.0, 0.0]}},
                                                 {'at': 4, 'reach': {'foot_l': [-1.0, 1.0]}},
                                                 {'at': 8, 'reach': {'foot_l': None}},
                                                 {'at': 12, 'reach': {'foot_l': [-2.0, 0.0]}},
                                                 {'at': 14, 'reach': {'foot_l': [-2.5, 0.0]}}]))
        track = m.reach['foot_l']
        rest = m.rest_joint('foot_l')
        self.assertEqual(m._reach_at('foot_l', track, 6), (rest[1]+1.0, rest[2]+1.0))     # held until the null
        self.assertIsNone(m._reach_at('foot_l', track, 8))
        self.assertIsNone(m._reach_at('foot_l', track, 11))
        self.assertIsNotNone(m._reach_at('foot_l', track, 13))
        free = Move(self.move('f', base=str(BODY)))
        self.assertEqual(m.matrices(10)['shin_l'], free.matrices(10)['shin_l'])

    def test_reach_ease(self):
        keys = [{'at': 0, 'from': 'guard', 'ease': 'in', 'reach': {'foot_l': [-2.0, 0.0]}},
                {'at': 10, 'reach': {'foot_l': [-1.0, 0.0]}}]
        m = Move(self.move(base=str(BODY), keys=keys))
        self.assertAlmostEqual(m._reach_at('foot_l', m.reach['foot_l'], 5)[1], m.rest_joint('foot_l')[2]+2.0-0.25)
        keys[0]['reach_ease'] = 'linear'
        m = Move(self.move(base=str(BODY), keys=keys))
        self.assertAlmostEqual(m._reach_at('foot_l', m.reach['foot_l'], 5)[1], m.rest_joint('foot_l')[2]+1.5)
        self.assertEqual(m.pose_keys[0][1], 'in')

    def test_a_reach_over_keyed_knees_warns(self):
        knee = {'thigh_l': [40, 0, 5], 'shin_l': [-80, 0, 0]}
        m = Move(self.move(base=str(BODY), keys=[{'at': 0, 'from': 'guard', 'reach': {'foot_l': [-2.5, 0.0]}},
                                                 {'at': 5, 'pose': knee}, {'at': 10, 'pose': {'head': [0, 0, 0]}},
                                                 {'at': 19, 'reach': {'foot_l': [-2.5, 0.0]}}]))
        self.assertTrue(any(w['check'] == 'legs' and 'frame 5' in w['message'] for w in m.warnings), m.warnings)
        # ended before the key's frames: the keyed knee shows, no warning
        m = Move(self.move(base=str(BODY), keys=[{'at': 0, 'from': 'guard', 'reach': {'foot_l': [-2.5, 0.0]}},
                                                 {'at': 1, 'reach': {'foot_l': None}},
                                                 {'at': 5, 'pose': knee}, {'at': 10, 'pose': {'head': [0, 0, 0]}}]))
        self.assertFalse(any(w['check'] == 'legs' for w in m.warnings), m.warnings)

    def test_floor_sets_the_pelvis(self):
        m = Move(self.move(base=str(BODY), keys=[{'at': 0, 'from': 'guard'},
                                                 {'at': 10, 'offset': [0.2, 0.0], 'floor': True,
                                                  'pose': {'thigh_l': [60, 0, 5], 'shin_l': [-100, 0, 0]}},
                                                 {'at': 15, 'pose': {'head': [5, 0, 0]}}]))
        self.assertLess(abs(m.lowest(10)[0]), 0.001)
        self.assertEqual(m.pose_keys[1][3][0], 0.2)
        self.assertEqual(m.pose_keys[2][3], m.pose_keys[1][3])          # the key after carries it
        r = verify(self.move('s', base=str(BODY), keys=[{'at': 0, 'from': 'guard', 'offset': [0, -2.0]}]))
        sunk = sorted((f for f in r['failures'] if f['check'] == 'floor'), key=lambda f: -f['depth'])
        self.assertTrue(sunk and 'offset up of' in sunk[0]['message'])
        g = load_rig(HERO_RIG).poses['guard']['offset'][1]
        self.assertAlmostEqual(sunk[0]['offset_up'], g, delta=0.05)

    def test_still_holds_joints_at_zero(self):
        keys = [{'at': 0, 'from': 'guard', 'pose': {'weapon_r': [20, 0, 0]}},
                {'at': 10, 'pose': {'weapon_r': [-30, 5, 0], 'head': [10, 0, 0]}}]
        free = Move(self.move('a', base=str(BODY), keys=keys))
        held = Move(self.move('b', base=str(BODY), keys=keys, still=['weapon_r']))
        for f in (0, 5, 10):
            self.assertNotEqual(free.pose_at(f)[0].get('weapon_r'), [0.0, 0.0, 0.0])
            self.assertEqual(held.pose_at(f)[0]['weapon_r'], [0.0, 0.0, 0.0])
            self.assertEqual(held.pose_at(f)[0]['head'], free.pose_at(f)[0]['head'])
        # it carries into a derived move, and names parts only
        d = Move(self.move('c', base=str(self.dir/'b.anim.json')))
        self.assertEqual(d.still, ['weapon_r'])
        with self.assertRaises(AnimError) as ctx:
            Move(self.move('e', base=str(BODY), still=['tail']))
        self.assertEqual(ctx.exception.path, '/still/0')

    def test_floor_allow(self):
        sunk = [{'at': 0, 'from': 'guard', 'offset': [0, -2.0]}]
        r = verify(self.move('s', base=str(BODY), keys=sunk))
        deepest = max((f for f in r['failures'] if f['check'] == 'floor'), key=lambda f: f['depth'])
        parts = {f['part']: f['depth'] for f in r['failures'] if f['check'] == 'floor'}
        # every sunk part allowed to its depth: warnings, not failures
        r = verify(self.move('t', base=str(BODY), keys=sunk, floor_allow={p: d+0.01 for p, d in parts.items()}))
        self.assertNotIn('floor', [f['check'] for f in r['failures']])
        self.assertIn('floor', [w['check'] for w in r['warnings']])
        # not deep enough: still a failure
        r = verify(self.move('u', base=str(BODY), keys=sunk, floor_allow={deepest['part']: deepest['depth']/2}))
        self.assertIn(deepest['part'], [f.get('part') for f in r['failures'] if f['check'] == 'floor'])
        with self.assertRaises(AnimError) as ctx:
            Move(self.move('v', base=str(BODY), floor_allow={'head': -1}))
        self.assertEqual(ctx.exception.path, '/floor_allow/head')

    def test_allow_comes_from_the_rig_and_merges(self):
        rig = load_rig(HERO_RIG)
        self.assertIn(frozenset(('forearm_r', 'weapon_r')), rig.allow)
        base = self.move('b', allow=[['head', 'upper_arm_r']])
        m = Move(self.move('d', base=str(base), allow=[['torso', 'forearm_l']]))
        for pair in (('head', 'upper_arm_r'), ('torso', 'forearm_l'), ('forearm_r', 'weapon_r')):
            self.assertIn(frozenset(pair), m.allow)


class ToolTests(Files, unittest.TestCase):
    def test_pose_reports_the_blade(self):
        from animkit import pose
        m = Move(ATK_F)
        r = pose.report(m, [13])['frames'][0]
        tip = r['weapons']['weapon_r']['tip']
        hits = [b['rect'] for b in r['boxes'] if b['kind'] == 'hit']
        self.assertTrue(any(x0 - 0.5 <= tip[0] <= x1 + 0.5 and y0 - 0.5 <= tip[1] <= y1 + 0.5
                            for x0, y0, x1, y1 in hits), (tip, hits))
        self.assertEqual(r['weapons']['weapon_r']['aim'], [round(v, 1) for v in blade(m.matrices(13))])
        self.assertEqual(r['hurt_top'], max(b['rect'][3] for b in r['boxes'] if b['kind'] == 'hurt'))
        self.assertLess(min(r['lowest'].values()), 0.05)
        self.assertEqual(pose.frames_arg('3,10-12', 38, []), [3, 10, 11, 12])

    def test_fmt_keeps_the_values(self):
        from animkit.fmt import fmt, format_move
        for path in sorted((CART/'anims').glob('*/*.anim.json'))+sorted((CART/'tests'/'anim').glob('**/*.anim.json')):
            data = json.loads(path.read_text())
            text = format_move(data)
            self.assertEqual(json.loads(text), data, path)
            self.assertEqual(format_move(json.loads(text)), text, path)
        self.assertEqual(fmt(sorted((CART/'anims').glob('*/*.anim.json')), check=True), [],
                         'the cart\'s moves are not in the compact style: python3 tools/mei_anim.py fmt')


class ExportTests(Files, unittest.TestCase):
    def test_layout(self):
        out = self.dir/'out'
        anims = self.dir/'anims'
        for mech in EX.MECHS:
            if not (CART/'anims'/mech/'_body.anim.json').is_file():
                continue                    # a mech with no rig yet: the first mech's stand-in
            (anims/mech).mkdir(parents=True)
            (anims/mech/'_body.anim.json').write_text((CART/'anims'/mech/'_body.anim.json').read_text().replace(
                '../../models/', str(CART/'models')+'/').replace('../hero/', str(CART/'anims'/'hero')+'/'))
        (anims/'hero'/'atk_f.anim.json').write_text(ATK_F.read_text().replace('"base": "_body.anim.json"',
                                                                             f'"base": "{anims/"hero"/"_body.anim.json"}"'))
        # a second real move: two moves made one after another must not share data
        (anims/'hero'/'atk_n.anim.json').write_text(json.dumps(
            {'format': 'mei-anim', 'version': 1, 'base': str(anims/'hero'/'_body.anim.json'), 'length': 7,
             'keys': [{'at': 0, 'from': 'guard'}]}))
        report = EX.export(anims, CART, out)
        akr = (out/'anim_data.akr').read_text()
        blob = (out/'anims'/'anim_data.bin').read_bytes()
        rows = [l for l in akr.splitlines() if l.strip().startswith('AnimMove {')]
        self.assertEqual(len(rows), len(EX.MECHS)*len(EX.MOVES))
        heads = {}
        for row, r in zip(rows, report['moves']):
            vals = dict(kv.split(': ') for kv in row[row.index('{')+1:row.index('}')].strip().split(', '))
            heads[(r['mech'], r['move'])] = {k: int(v) for k, v in vals.items()}
        a, n = heads[('hero', 'atk_f')], heads[('hero', 'atk_n')]
        self.assertEqual((a['len'], n['len']), (38, 7))
        self.assertNotEqual(a['frames'], n['frames'])
        self.assertEqual(a['flags'] & EX.FLAG_STANDIN, 0)
        self.assertTrue(heads[('hero', 'idle')]['flags'] & EX.FLAG_LOOP)
        self.assertTrue(heads[('hero', 'super')]['flags'] & EX.FLAG_STANDIN)
        self.assertEqual(a['box_first']-a['frames'], 38*len(SKELETON)*EX.XF_BYTES)
        # a mech with the appended joints holds them all in each frame (AK_NPART says how many)
        s = heads[('seraph', 'idle')]
        self.assertEqual(s['box_first']-s['frames'], s['len']*len(PARTS)*EX.XF_BYTES)
        npart = [l for l in akr.splitlines() if l.startswith('const AK_NPART')][0]
        counts = [int(v) for v in npart[npart.index('[', npart.index('=')) + 1:npart.rindex(']')].split(',')]
        self.assertEqual(counts, [len(PARTS) if m == 'seraph' else len(SKELETON) for m in EX.MECHS])
        # the first frame's pelvis matrix, as anim.akr reads it
        r = struct.unpack_from('<10h3i', blob, a['frames'])
        m = Move(ATK_F).matrices(0)['pelvis']
        self.assertAlmostEqual(r[0]/4096, m[0][0], places=3)
        self.assertAlmostEqual(r[11]/65536, m[1][3], places=4)
        # boxes: frame 13's count and a hit box among them
        first = struct.unpack_from('<39H', blob, a['box_first'])
        kinds = [blob[a['boxes']+20*i] for i in range(first[13], first[14])]
        self.assertIn(0, kinds)
        self.assertEqual(sum(struct.unpack_from('<2i', blob, a['root']+8*f)[0] for f in range(38)), round(1.2*65536))


@unittest.skipUnless(tool('MEIC', 'meic').is_file() and tool('RUN', 'mei-headless').is_file(),
                     'needs meic and mei-headless (make B=DIR DIR/meic DIR/mei-headless)')
class RuntimeTests(unittest.TestCase):
    """The check scene of carts/mechexpo/tests/anim/ prints what anim.akr computes; it must be
    what the kit computed."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        env = dict(os.environ, MEIC=str(tool('MEIC', 'meic')), RUN=str(tool('RUN', 'mei-headless')),
                   DATA=str(Path(cls.tmp.name)/'data'))
        out = Path(cls.tmp.name)/'check'
        cls.result = subprocess.run([str(CART/'tests'/'anim'/'run.sh'), '5', '3', str(out)], env=env,
                                    capture_output=True, text=True, timeout=300)
        cls.lines = cls.result.stdout.splitlines()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_cart_checks_pass(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout[-2000:]+self.result.stderr[-2000:])
        self.assertIn('OK check', self.lines)

    def test_matrices(self):
        move = Move(ATK_F)
        seen = 0
        for line in self.lines:
            if not line.startswith('part '):
                continue
            w = line.split()
            f, p = int(w[1]), int(w[2])
            got = [float(v) for v in w[3:]]
            m = move.matrices(f)[PARTS[p]] if PARTS[p] in move.rig.joints else None
            if m is None:
                continue
            want = [m[i][j] for i in range(3) for j in range(4)]
            for a, b in zip(got, want):
                self.assertLess(abs(a-b), 0.002, f'frame {f} {PARTS[p]}')
            seen += 1
        self.assertEqual(seen, 3*len([p for p in PARTS if p in move.rig.joints]))

    def test_boxes_and_marks(self):
        move = Move(ATK_F)
        want = {f: sorted((b[1], b[3], b[4], b[5], b[6], b[7]) for b in move.boxes_at(f)) for f in range(move.length)}
        got = {}
        kinds = {0: 'hit', 1: 'hurt', 2: 'push'}
        for line in self.lines:
            w = line.split()
            if w and w[0] == 'box':
                got.setdefault(int(w[1]), []).append((kinds[int(w[2])], PARTS[int(w[3])], *(float(v) for v in w[4:])))
            if w and w[0] == 'marks':
                self.assertEqual(int(w[2]), move.marks[int(w[1])])
        for f in range(move.length):
            g = sorted(got.get(f, []))
            self.assertEqual(len(g), len(want[f]), f'frame {f}')
            for a, b in zip(g, want[f]):
                self.assertEqual(a[:2], b[:2])
                for x, y in zip(a[2:], b[2:]):
                    self.assertLess(abs(x-y), 0.0001)


if __name__ == '__main__':
    unittest.main()
