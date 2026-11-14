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


# I2: Make T-pose (limb_dir convention), reference-pose capture and KHR_character_reference_pose export.

import unittest

import bpy

import khr_test_utils as u
import rigs

UP = {'leftUpperArm': 'leftLowerArm', 'leftLowerArm': 'leftHand', 'rightUpperArm': 'rightLowerArm',
      'rightLowerArm': 'rightHand', 'leftIndexProximal': 'leftIndexIntermediate',
      'rightIndexProximal': 'rightIndexIntermediate', 'leftLittleIntermediate': 'leftLittleDistal',
      'leftUpperLeg': 'leftLowerLeg', 'rightLowerLeg': 'rightFoot'}


def a_pose_rig(name='mixamo', tail_mode='perpendicular'):
    bones, expected = rigs.RIGS[name]()
    bones = rigs.a_pose(bones, expected)
    ob = rigs.build_armature(bones, tail_mode=tail_mode)
    bpy.context.view_layer.objects.active = ob
    assert bpy.ops.khr_character.auto_map_skeleton('EXEC_DEFAULT') == {'FINISHED'}
    return ob, expected


def transformed_rig(transform, name='mixamo'):
    """A-pose rig whose rest heads are mapped by transform((x, y, z)) in armature space."""
    bones, expected = rigs.RIGS[name]()
    bones = [(n, p, transform(h)) for n, p, h in rigs.a_pose(bones, expected)]
    ob = rigs.build_armature(bones)
    bpy.context.view_layer.objects.active = ob
    assert bpy.ops.khr_character.auto_map_skeleton('EXEC_DEFAULT') == {'FINISHED'}
    return ob, expected


class MakeTPose(unittest.TestCase):
    def setUp(self):
        u.clear_scene()

    def check_t_pose(self, g, expected, tolerance=2.0):
        pose = g.animation('t_pose')
        pos = u.world_positions(g, pose)
        for a, b in UP.items():
            d = pos[expected[b]] - pos[expected[a]]
            if 'Leg' in a or 'Foot' in b:
                want = (0, -1, 0)
            else:
                want = (1, 0, 0) if a.startswith('left') else (-1, 0, 0)
            tol = 3.0 if ('Index' in a or 'Little' in a) else tolerance
            self.assertLess(u.angle_deg(d, want), tol, (a, b))
        thumb = pos[expected['leftThumbDistal']] - pos[expected['leftThumbProximal']]
        self.assertLess(u.angle_deg(thumb, (1, 0, 1)), 3.0)  # 45 degrees between +X and front (+Z)

    def test_a_pose_rig_with_perpendicular_bone_axes(self):
        ob, expected = a_pose_rig()
        self.assertEqual(bpy.ops.khr_character.make_t_pose('EXEC_DEFAULT'), {'FINISHED'})
        self.assertEqual(bpy.ops.khr_character.capture_reference_pose('EXEC_DEFAULT', pose_type='a_pose',
                                                                      from_rest=True), {'FINISHED'})
        g = u.Glb(u.export('refpose', export_khr_character=True, export_animation_mode='ACTIONS'))
        names = [a['name'] for a in g.json['animations']]
        self.assertEqual(names[-2:], ['t_pose', 'a_pose'])
        for name, label in (('t_pose', 't_pose'), ('a_pose', 'a_pose')):
            a = g.animation(name)
            self.assertEqual(a['extensions']['KHR_character_reference_pose'], {'poseType': label})
            for ch in a['channels']:
                self.assertIn(ch['target']['path'], ('translation', 'rotation', 'scale'))
                s = a['samplers'][ch['sampler']]
                self.assertEqual(g.json['accessors'][s['input']]['count'], 1)
                self.assertIn(s.get('interpolation', 'LINEAR'), ('LINEAR', 'STEP'))
                if ch['target']['path'] == 'rotation':
                    q = g.accessor(s['output'])[0]
                    self.assertAlmostEqual(float((q * q).sum()), 1.0, places=5)
            targeted = {ch['target']['node'] for ch in a['channels']}
            self.assertTrue(all(g.node_index(b) in targeted for b in expected.values()))
        self.assertIn('KHR_character_reference_pose', g.json['extensionsUsed'])
        self.check_t_pose(g, expected)
        a_pos = u.world_positions(g, g.animation('a_pose'))
        rest = u.world_positions(g)
        for b in expected.values():
            self.assertLess(float(abs(a_pos[b] - rest[b]).max()), 1e-5)
        # the scene itself is left in rest pose
        self.assertTrue(all(pb.matrix_basis.is_identity for pb in ob.pose.bones))

    def check_frame_t_pose(self, g, expected):
        """T-pose in the character frame of the exported rest pose (not glTF axes)."""
        import numpy as np
        rest = u.world_positions(g)
        up = rest[expected['head']] - rest[expected['hips']]
        lr = rest[expected['leftUpperLeg']] - rest[expected['rightUpperLeg']]
        up = up / np.linalg.norm(up)
        left = lr - up * np.dot(lr, up)
        left = left / np.linalg.norm(left)
        forward = np.cross(left, up)
        pos = u.world_positions(g, g.animation('t_pose'))
        for side, sx in (('left', 1.0), ('right', -1.0)):
            for a, b, tol in (('UpperArm', 'LowerArm', 2.0), ('LowerArm', 'Hand', 2.0),
                              ('IndexProximal', 'IndexIntermediate', 3.0)):
                d = pos[expected[side + b]] - pos[expected[side + a]]
                self.assertLess(u.angle_deg(d, sx * left), tol, (side, a))
            d = pos[expected[side + 'LowerLeg']] - pos[expected[side + 'UpperLeg']]
            self.assertLess(u.angle_deg(d, -up), 2.0, (side, 'leg'))
            d = pos[expected[side + 'ThumbDistal']] - pos[expected[side + 'ThumbProximal']]
            self.assertLess(u.angle_deg(d, sx * left + forward), 3.0, (side, 'thumb'))
        return up, left, forward

    def test_rig_facing_plus_y(self):
        ob, expected = transformed_rig(lambda h: (-h[0], -h[1], h[2]))
        bpy.ops.khr_character.make_t_pose('EXEC_DEFAULT')
        g = u.Glb(u.export('refpose_plus_y', export_khr_character=True, export_animation_mode='ACTIONS'))
        up, left, forward = self.check_frame_t_pose(g, expected)
        self.assertLess(u.angle_deg(left, (-1, 0, 0)), 1.0)  # glTF: character-left is -X for this rig
        self.assertLess(u.angle_deg(up, (0, 1, 0)), 1.0)

    def test_y_up_rig_rotated_on_x(self):
        import math
        ob, expected = transformed_rig(lambda h: (h[0], h[2], -h[1]))  # Y-up, front +Z bones (FBX import)
        ob.rotation_euler = (math.pi / 2, 0.0, 0.0)
        bpy.context.view_layer.update()
        bpy.ops.khr_character.make_t_pose('EXEC_DEFAULT')
        g = u.Glb(u.export('refpose_y_up', export_khr_character=True, export_animation_mode='ACTIONS'))
        up, left, forward = self.check_frame_t_pose(g, expected)
        self.assertLess(u.angle_deg(up, (0, 1, 0)), 1.0)
        self.assertLess(u.angle_deg(forward, (0, 0, 1)), 1.0)

    def test_posture_lean_snaps_to_armature_axes(self):
        import math
        t = math.radians(2.0)  # 2 degree forward lean of the whole rest pose (head towards -Y)
        ob, expected = transformed_rig(lambda h: (h[0], h[1] * math.cos(t) - (h[2] - 1.0) * math.sin(t),
                                                  1.0 + h[1] * math.sin(t) + (h[2] - 1.0) * math.cos(t)))
        bpy.ops.khr_character.make_t_pose('EXEC_DEFAULT')
        g = u.Glb(u.export('refpose_lean', export_khr_character=True, export_animation_mode='ACTIONS'))
        pos = u.world_positions(g, g.animation('t_pose'))
        for side, sx in (('left', 1.0), ('right', -1.0)):
            d = pos[expected[side + 'LowerLeg']] - pos[expected[side + 'UpperLeg']]
            self.assertLess(u.angle_deg(d, (0, -1, 0)), 0.01, side)
            d = pos[expected[side + 'LowerArm']] - pos[expected[side + 'UpperArm']]
            self.assertLess(u.angle_deg(d, (sx, 0, 0)), 0.01, side)
            d = pos[expected[side + 'ThumbDistal']] - pos[expected[side + 'ThumbProximal']]
            self.assertLess(u.angle_deg(d, (sx, 0, 1)), 0.01, side)

    def test_body_turned_in_armature_keeps_its_left_axis(self):
        import math
        t = math.radians(25.0)  # the whole body turned 25 degrees about the armature's up axis
        ob, expected = transformed_rig(lambda h: (h[0] * math.cos(t) - h[1] * math.sin(t),
                                                  h[0] * math.sin(t) + h[1] * math.cos(t), h[2]))
        self.assertEqual(bpy.ops.khr_character.make_t_pose('EXEC_DEFAULT'), {'FINISHED'})
        g = u.Glb(u.export('refpose_turned', export_khr_character=True, export_animation_mode='ACTIONS'))
        up, left, forward = self.check_frame_t_pose(g, expected)
        self.assertLess(u.angle_deg(up, (0, 1, 0)), 0.01)
        self.assertAlmostEqual(u.angle_deg(left, (1, 0, 0)), 25.0, places=2)

    def test_rerun_replaces_and_duplicates_abort(self):
        ob, expected = a_pose_rig()
        bpy.ops.khr_character.make_t_pose('EXEC_DEFAULT')
        bpy.ops.khr_character.make_t_pose('EXEC_DEFAULT')
        self.assertEqual([a.name for a in bpy.data.actions], ['t_pose'])
        self.assertTrue(bpy.data.actions['t_pose'].khr_reference_pose.is_reference)
        g = u.Glb(u.export('refpose_rerun', export_khr_character=True, export_animation_mode='ACTIONS'))
        self.assertEqual([a['name'] for a in g.json['animations']], ['t_pose'])
        copy = bpy.data.actions['t_pose'].copy()
        copy.use_fake_user = True
        with self.assertRaises(RuntimeError):
            u.export('refpose_duplicate', export_khr_character=True, export_animation_mode='ACTIONS')

    def test_rerun_keeps_superseded_action_still_in_use(self):
        ob, expected = a_pose_rig()
        bpy.ops.khr_character.make_t_pose('EXEC_DEFAULT')
        track = ob.animation_data.nla_tracks.new()
        track.strips.new('t_pose', 1, bpy.data.actions['t_pose'])
        bpy.ops.khr_character.make_t_pose('EXEC_DEFAULT')
        old = bpy.data.actions['t_pose.superseded']
        self.assertFalse(old.khr_reference_pose.is_reference)
        self.assertEqual(track.strips[0].action, old)
        self.assertEqual([a.name for a in bpy.data.actions if a.khr_reference_pose.is_reference], ['t_pose'])

    def test_rerun_leaves_other_rigs_with_same_bone_names(self):
        a, expected = a_pose_rig()
        bpy.ops.khr_character.make_t_pose('EXEC_DEFAULT')
        b, _ = a_pose_rig()
        self.assertEqual(set(a.pose.bones.keys()), set(b.pose.bones.keys()))
        bpy.ops.khr_character.make_t_pose('EXEC_DEFAULT')
        bpy.ops.khr_character.make_t_pose('EXEC_DEFAULT')
        mine = {act.khr_reference_pose.armature.name: act for act in bpy.data.actions
                if act.khr_reference_pose.is_reference}
        self.assertEqual(sorted(mine), [a.name, b.name])
        self.assertEqual(mine[a.name].name, 't_pose')
        self.assertTrue(mine[a.name].use_fake_user)
        self.assertEqual(len(bpy.data.actions), 2)
        b.khr_skeleton_mapping.sets.clear()  # a file maps one skeleton; the second rig is a prop
        for ob in (a, b):  # with several armatures the exporter takes only assigned or NLA actions
            ob.animation_data.nla_tracks.new().strips.new('pose', 1, mine[ob.name])
        g = u.Glb(u.export('refpose_two_rigs', export_khr_character=True, export_animation_mode='ACTIONS'))
        poses = [anim for anim in g.json['animations'] if 'KHR_character_reference_pose' in anim.get('extensions', {})]
        self.assertEqual(len(poses), 2)
        targets = [{ch['target']['node'] for ch in anim['channels']} for anim in poses]
        self.assertFalse(targets[0] & targets[1])

    def test_nla_tracks_mode(self):
        ob, expected = a_pose_rig()
        bpy.ops.khr_character.make_t_pose('EXEC_DEFAULT')
        track = ob.animation_data.nla_tracks.new()
        track.name = 'Reference'
        track.strips.new('t_pose', 1, bpy.data.actions['t_pose'])
        g = u.Glb(u.export('refpose_nla', export_khr_character=True, export_animation_mode='NLA_TRACKS'))
        a = g.animation('Reference')
        self.assertEqual(a['extensions']['KHR_character_reference_pose'], {'poseType': 't_pose'})
        for ch in a['channels']:
            self.assertEqual(g.json['accessors'][a['samplers'][ch['sampler']]['input']]['count'], 1)

    def test_distal_with_two_children(self):
        bones, expected = rigs.mixamo()
        bones = rigs.a_pose(bones, expected)
        heads = {n: h for n, _p, h in bones}
        for side in ('Left', 'Right'):
            distal = 'mixamorig:{}HandIndex3'.format(side)
            h = heads[distal]
            bones.append(('{}_nail'.format(distal), distal, (h[0], h[1] - 0.01, h[2] + 0.005)))
        ob = rigs.build_armature(bones, tail_mode='perpendicular')
        bpy.context.view_layer.objects.active = ob
        bpy.ops.khr_character.auto_map_skeleton('EXEC_DEFAULT')
        bpy.ops.khr_character.make_t_pose('EXEC_DEFAULT')
        g = u.Glb(u.export('refpose_two_children', export_khr_character=True, export_animation_mode='ACTIONS'))
        pos = u.world_positions(g, g.animation('t_pose'))
        for side, sx in (('Left', 1), ('Right', -1)):
            d = pos['mixamorig:{}HandIndex4'.format(side)] - pos['mixamorig:{}HandIndex3'.format(side)]
            self.assertLess(u.angle_deg(d, (sx, 0, 0)), 3.0, side)

    def test_leaning_spine_warns(self):
        from io_scene_gltf2.blender.exp.khr_character.tpose import character_frame
        bones, expected = rigs.mixamo()
        bones = [(n, p, (h[0] + (0.15 if n == 'mixamorig:Head' else 0.0), h[1], h[2])) for n, p, h in bones]
        ob = rigs.build_armature(bones)
        bpy.context.view_layer.objects.active = ob
        report = []
        character_frame(ob, expected, report)
        self.assertTrue(any('neck -> head leans' in r for r in report), report)
        report = []
        character_frame(rigs.build_armature(rigs.mixamo()[0], name='Upright'), expected, report)
        self.assertEqual(report, [])

    def test_distal_uses_unmapped_tip_child(self):
        # every tail is perpendicular to its limb; the 4th finger/thumb segments are unmapped tip bones
        ob, expected = a_pose_rig()
        tips = {b.parent.name: b.name for b in ob.data.bones if b.parent and not b.children
                and b.parent.name in expected.values()}
        bpy.ops.khr_character.make_t_pose('EXEC_DEFAULT')
        g = u.Glb(u.export('refpose_tips', export_khr_character=True, export_animation_mode='ACTIONS'))
        pos = u.world_positions(g, g.animation('t_pose'))
        checked = 0
        for side in ('left', 'right'):
            hand = pos[expected[side + 'MiddleProximal']] - pos[expected[side + 'Hand']]
            for finger in ('Index', 'Middle', 'Ring', 'Little'):
                distal = expected[side + finger + 'Distal']
                self.assertIn(distal, tips)
                self.assertLess(u.angle_deg(pos[tips[distal]] - pos[distal], hand), 3.0, (side, finger))
                checked += 1
            thumb = expected[side + 'ThumbDistal']
            want = pos[thumb] - pos[expected[side + 'ThumbProximal']]
            self.assertLess(u.angle_deg(pos[tips[thumb]] - pos[thumb], want), 3.0, (side, 'thumb'))
        self.assertEqual(checked, 8)

    def test_rigs_with_limb_axes(self):
        for name in ('rigify', 'maya_jnt', 'cartoon3finger'):
            with self.subTest(rig=name):
                u.clear_scene()
                ob, expected = a_pose_rig(name, tail_mode='child')
                bpy.ops.khr_character.make_t_pose('EXEC_DEFAULT')
                g = u.Glb(u.export('refpose_' + name, export_khr_character=True, export_animation_mode='ACTIONS'))
                pos = u.world_positions(g, g.animation('t_pose'))
                for side, want in (('left', (1, 0, 0)), ('right', (-1, 0, 0))):
                    d = pos[expected[side + 'LowerArm']] - pos[expected[side + 'UpperArm']]
                    self.assertLess(u.angle_deg(d, want), 2.0)

    def test_flag_without_package_is_plain_animation(self):
        ob, expected = a_pose_rig()
        bpy.ops.khr_character.make_t_pose('EXEC_DEFAULT')
        g = u.Glb(u.export('refpose_off', export_animation_mode='ACTIONS'))
        self.assertNotIn('extensions', g.animation('t_pose'))


if __name__ == '__main__':
    unittest.main()
