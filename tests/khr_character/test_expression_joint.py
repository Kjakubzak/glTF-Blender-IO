# Copyright 2018-2021 The glTF-Blender-IO authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest

import bpy
import numpy as np

import khr_test_utils as u
import rigs

EXT = 'KHR_character_expression'
JOINT = 'KHR_character_expression_joint'
MORPH = 'KHR_character_expression_morphtarget'
P = 'mixamorig:'


def armature():
    bones, expected = rigs.mixamo()
    ob = rigs.build_armature(bones)
    bpy.context.view_layer.objects.active = ob
    return ob, expected


def key_rotation(ob, action, frames):
    """frames: {frame: {bone: (w, x, y, z)}}; every bone is keyed on every frame."""
    ad = ob.animation_data_create()
    ad.action = action
    bones = sorted({b for pose in frames.values() for b in pose})
    for frame, pose in frames.items():
        for b in bones:
            pb = ob.pose.bones[b]
            pb.rotation_quaternion = pose.get(b, (1, 0, 0, 0))
            pb.keyframe_insert('rotation_quaternion', frame=frame)
    for pb in ob.pose.bones:
        pb.rotation_quaternion = (1, 0, 0, 0)
    ad.action = None


def add_action_expression(name, action, **kwargs):
    e = bpy.context.scene.khr_character.expressions.add()
    e.name = name
    e.source = 'ACTION'
    e.action = action
    for k, v in kwargs.items():
        setattr(e, k, v)
    return e


class JointExpressions(unittest.TestCase):
    def setUp(self):
        u.clear_scene()

    def test_prune_classify_and_consume(self):
        ob, _ = armature()
        nod = bpy.data.actions.new('nod')
        nod.use_fake_user = True
        key_rotation(ob, nod, {0: {P + 'Spine': (1, 0, 0, 0), P + 'Head': (1, 0, 0, 0)},
                               24: {P + 'Head': (0.9659, 0.2588, 0, 0)}})
        clip = bpy.data.actions.new('clip')
        clip.use_fake_user = True
        key_rotation(ob, clip, {1: {P + 'Neck': (1, 0, 0, 0)}, 10: {P + 'Neck': (0.9659, 0, 0, 0.2588)}})
        add_action_expression('nod', nod)
        g = u.Glb(u.export('expr_joint', export_khr_character=True, export_animation_mode='ACTIONS'))
        names = [a['name'] for a in g.json['animations']]
        self.assertEqual(names, ['clip', 'nod'])
        entry = g.json['extensions'][EXT]['expressions'][0]
        anim = g.json['animations'][entry['animation']]
        self.assertEqual(entry['extensions'], {JOINT: {'channels': [0]}})
        self.assertEqual(len(anim['channels']), 1)
        ch = anim['channels'][0]
        self.assertEqual((ch['target']['node'], ch['target']['path']), (g.node_index(P + 'Head'), 'rotation'))
        s = anim['samplers'][ch['sampler']]
        times = g.accessor(s['input'])[:, 0]
        self.assertAlmostEqual(float(times[0]), 0.0, places=6)
        self.assertAlmostEqual(float(times[-1]), 1.0, places=5)
        self.assertGreaterEqual(len(times), 2)
        q = g.accessor(s['output'])
        self.assertLess(u.angle_deg(q[-1][:3], (1, 0, 0)), 1.0)
        self.assertIn(JOINT, g.json['extensionsUsed'])
        self.assertNotIn(MORPH, g.json['extensionsUsed'])

    def test_allow_list_discards(self):
        ob, _ = armature()
        act = bpy.data.actions.new('look')
        act.use_fake_user = True
        key_rotation(ob, act, {0: {}, 24: {P + 'Head': (0.9659, 0.2588, 0, 0), P + 'Neck': (0.9659, 0, 0, 0.2588)}})
        add_action_expression('look', act, allow_joints=P + 'Neck')
        g = u.Glb(u.export('expr_allow', export_khr_character=True, export_animation_mode='ACTIONS'))
        anim = g.animation('look')
        self.assertEqual([c['target']['node'] for c in anim['channels']], [g.node_index(P + 'Neck')])

    def test_all_constant_keeps_one(self):
        ob, _ = armature()
        act = bpy.data.actions.new('still')
        act.use_fake_user = True
        key_rotation(ob, act, {0: {P + 'Head': (1, 0, 0, 0)}, 24: {P + 'Head': (1, 0, 0, 0)}})
        add_action_expression('still', act)
        g = u.Glb(u.export('expr_still', export_khr_character=True, export_animation_mode='ACTIONS'))
        self.assertEqual(len(g.animation('still')['channels']), 1)

    def test_missing_action_aborts(self):
        ob, _ = armature()
        act = bpy.data.actions.new('orphan')
        act.use_fake_user = True
        add_action_expression('orphan', act)
        with self.assertRaises(RuntimeError):
            u.export('expr_orphan', export_khr_character=True, export_animation_mode='ACTIONS')


def face_rig():
    """Armature with a 'smile' control property driving the head and a shape key (0.2 at neutral)."""
    ob, expected = armature()
    face = u.shape_key_mesh('Face', ['mouthSmileLeft', 'jawOpen'], location=(0, -0.1, 1.7))
    face.parent = ob
    ob['smile'] = 0.0
    head = ob.pose.bones[P + 'Head']
    head.rotation_mode = 'XYZ'
    fc = head.driver_add('rotation_euler', 0)
    fc.driver.type = 'SCRIPTED'
    v = fc.driver.variables.new()
    v.name = 's'
    v.targets[0].id = ob
    v.targets[0].data_path = '["smile"]'
    fc.driver.expression = 's * 0.3'
    key = face.data.shape_keys.key_blocks['mouthSmileLeft']
    fc = key.driver_add('value')
    fc.driver.type = 'SCRIPTED'
    v = fc.driver.variables.new()
    v.name = 's'
    v.targets[0].id = ob
    v.targets[0].data_path = '["smile"]'
    fc.driver.expression = '0.2 + 0.8 * s'
    bpy.context.view_layer.update()
    return ob, face, expected


def eye_rig():
    """Head with two eye joints whose bone axes do not follow the gaze, plus eye-tip children in front."""
    bones = [('hips', None, (0, 0, 1.0)), ('spine', 'hips', (0, 0, 1.2)), ('neck', 'spine', (0, 0, 1.5)),
             ('head', 'neck', (0, 0, 1.6)), ('eye.L', 'head', (0.03, -0.08, 1.7)),
             ('eye.R', 'head', (-0.03, -0.08, 1.7)), ('eyeTip.L', 'eye.L', (0.03, -0.1, 1.7)),
             ('eyeTip.R', 'eye.R', (-0.03, -0.1, 1.7))]
    ob = rigs.build_armature(bones, tail_mode='perpendicular')
    bpy.context.view_layer.objects.active = ob
    s = ob.khr_skeleton_mapping.sets.add()
    s.set_id = 'vrm1_humanoid'
    for role, bone in (('hips', 'hips'), ('spine', 'spine'), ('neck', 'neck'), ('head', 'head'),
                       ('leftEye', 'eye.L'), ('rightEye', 'eye.R')):
        e = s.entries.add()
        e.role, e.bone = role, bone
    return ob


class Capture(unittest.TestCase):
    def setUp(self):
        u.clear_scene()

    def test_capture_from_control_mixed(self):
        ob, face, _ = face_rig()
        self.assertEqual(bpy.ops.khr_character.capture_expression(
            'EXEC_DEFAULT', name='smile', source='CONTROL', control_path='["smile"]'), {'FINISHED'})
        self.assertEqual(ob['smile'], 0.0)
        # the drivers stay: the export mutes them only while the expression's action is sampled
        g = u.Glb(u.export('expr_capture', export_khr_character=True, export_animation_mode='ACTIONS'))
        entry = g.json['extensions'][EXT]['expressions'][0]
        anim = g.json['animations'][entry['animation']]
        self.assertEqual(entry['name'], 'smile')
        joint = entry['extensions'][JOINT]['channels']
        morph = entry['extensions'][MORPH]['channels']
        self.assertEqual(sorted(joint + morph), list(range(len(anim['channels']))))
        self.assertEqual([anim['channels'][i]['target']['path'] for i in morph], ['weights'])
        self.assertTrue(all(anim['channels'][i]['target']['path'] in ('translation', 'rotation', 'scale')
                            for i in joint))
        head_rot = [anim['channels'][i] for i in joint if anim['channels'][i]['target']['node'] ==
                    g.node_index(P + 'Head') and anim['channels'][i]['target']['path'] == 'rotation']
        self.assertEqual(len(head_rot), 1)
        s = anim['samplers'][anim['channels'][morph[0]]['sampler']]
        w = g.accessor(s['output'])[:, 0]
        n = 2
        self.assertAlmostEqual(float(w[0]), 0.2, places=4)                # t = 0 equals the neutral
        self.assertAlmostEqual(float(w[-n]), 1.0, places=4)               # peak
        self.assertAlmostEqual(float(w[1]), 0.0, places=6)                # jawOpen untouched
        times = g.accessor(s['input'])[:, 0]
        self.assertAlmostEqual(float(times[0]), 0.0, places=6)
        self.assertAlmostEqual(float(times[-1]), 1.0, places=5)
        drivers = list(ob.animation_data.drivers) + list(face.data.shape_keys.animation_data.drivers)
        self.assertEqual(len(drivers), 2)
        self.assertFalse(any(d.mute for d in drivers))

    def test_constraints_disabled_while_sampled(self):
        ob, _ = armature()
        con = ob.pose.bones[P + 'Head'].constraints.new('LIMIT_ROTATION')
        con.use_limit_x, con.min_x, con.max_x = True, 0.0, 0.0
        act = bpy.data.actions.new('tilt')
        act.use_fake_user = True
        key_rotation(ob, act, {0: {P + 'Head': (1, 0, 0, 0)}, 24: {P + 'Head': (0.9659, 0.2588, 0, 0)}})
        add_action_expression('tilt', act)
        g = u.Glb(u.export('expr_constraint', export_khr_character=True, export_animation_mode='ACTIONS'))
        anim = g.animation('tilt')
        self.assertEqual([(c['target']['node'], c['target']['path']) for c in anim['channels']],
                         [(g.node_index(P + 'Head'), 'rotation')])
        q = g.accessor(anim['samplers'][anim['channels'][0]['sampler']]['output'])
        self.assertGreater(2 * np.degrees(np.arccos(min(1.0, abs(float(np.dot(q[0], q[-1])))))), 25.0)
        self.assertTrue(con.enabled)

    def test_look_left_in_head_frame(self):
        eye_rig()
        self.assertEqual(bpy.ops.khr_character.capture_expression(
            'EXEC_DEFAULT', name='lookLeft', source='ACTION', look='LEFT', look_angle=12.0), {'FINISHED'})
        g = u.Glb(u.export('expr_look', export_khr_character=True, export_animation_mode='ACTIONS'))
        anim = g.animation('lookLeft')
        rest = u.world_positions(g)
        peak = u.world_positions(g, anim, key=-1)
        for side in ('L', 'R'):
            d = peak['eyeTip.' + side] - rest['eyeTip.' + side]
            self.assertGreater(float(d[0]), 0.0035)        # toward character-left (+X)
            self.assertLess(abs(float(d[1])), 0.002)       # stays level
            self.assertLess(float(np.linalg.norm(peak['eye.' + side] - rest['eye.' + side])), 1e-6)


if __name__ == '__main__':
    unittest.main()
