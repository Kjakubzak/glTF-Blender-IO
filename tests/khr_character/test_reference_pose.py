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
