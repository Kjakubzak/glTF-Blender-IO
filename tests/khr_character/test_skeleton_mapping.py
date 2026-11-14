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

# I1: vrm1_humanoid auto-mapping and KHR_character_skeleton_mapping export.

import unittest

import bpy

import khr_test_utils as u
import rigs
from io_scene_gltf2.blender.com.khr_character import automap


def add_set(ob, mapping, set_id='vrm1_humanoid'):
    s = ob.khr_skeleton_mapping.sets.add()
    s.set_id = set_id
    for role, bone in mapping.items():
        e = s.entries.add()
        e.role, e.bone = role, bone
    return s


class AutoMap(unittest.TestCase):
    def test_conventions(self):
        for name, make in rigs.RIGS.items():
            with self.subTest(rig=name):
                bones, expected = make()
                mapping, problems = automap.auto_map(bones)
                self.assertEqual(problems, [])
                self.assertEqual(mapping, expected)

    def test_shoulder_named_upper_arm_without_clavicle(self):
        bones, expected = rigs.clavicle_chain()
        bones = [(n, 'chest' if p and p.startswith('clavicle') else p, h) for n, p, h in bones
                 if not n.startswith('clavicle')]
        mapping, problems = automap.auto_map(bones)
        self.assertEqual(problems, [])
        self.assertEqual(mapping['leftUpperArm'], 'shoulder_l')
        self.assertNotIn('leftShoulder', mapping)

    def test_all_or_nothing(self):
        bones, _ = rigs.mixamo()
        bones = [b for b in bones if 'LeftFoot' not in b[0] and 'LeftToe' not in b[0]]
        mapping, problems = automap.auto_map(bones)
        self.assertEqual(mapping, {})
        self.assertIn('missing required role leftFoot', problems)

    def test_validate_order_and_uniqueness(self):
        bones, expected = rigs.maya_jnt()
        bad = dict(expected, leftHand=expected['leftUpperArm'])
        problems = automap.validate(bad, bones=bones)
        self.assertTrue(any('used by' in p for p in problems))
        swapped = dict(expected, spine=expected['head'], head=expected['spine'])
        self.assertTrue(any('is not below' in p for p in automap.validate(swapped, bones=bones)))


class Export(unittest.TestCase):
    def setUp(self):
        u.clear_scene()

    def test_operator_and_export(self):
        bones, expected = rigs.rigify()
        ob = rigs.build_armature(bones)
        bpy.context.view_layer.objects.active = ob
        self.assertEqual(bpy.ops.khr_character.auto_map_skeleton('EXEC_DEFAULT'), {'FINISHED'})
        g = u.Glb(u.export('skelmap', export_khr_character=True))
        roles = g.json['extensions']['KHR_character_skeleton_mapping']['skeletalRigMappings']['vrm1_humanoid']
        self.assertEqual({r: g.json['nodes'][a['node']]['name'] for r, a in roles.items()}, expected)
        self.assertIn('KHR_character_skeleton_mapping', g.json['extensionsUsed'])
        self.assertNotIn('extensionsRequired', g.json)

    def test_unexported_bone_is_an_error(self):
        bones, expected = rigs.cartoon3finger()
        ob = rigs.build_armature(bones)
        add_set(ob, dict(expected, jaw='no_such_bone'))
        with self.assertRaises(RuntimeError):
            u.export('skelmap_bad', export_khr_character=True)
        g = u.Glb(u.export('skelmap_lenient', export_khr_character=True, export_khr_strict=False))
        roles = g.json['extensions']['KHR_character_skeleton_mapping']['skeletalRigMappings']['vrm1_humanoid']
        self.assertNotIn('jaw', roles)

    def test_custom_set_and_partial_mapping(self):
        bones, _ = rigs.cartoon3finger()
        ob = rigs.build_armature(bones)
        add_set(ob, {'pelvis_role': 'pelvis'}, set_id='ACME_custom')
        add_set(ob, {'hips': 'pelvis', 'head': 'head'})
        g = u.Glb(u.export('skelmap_sets', export_khr_character=True))
        sets = g.json['extensions']['KHR_character_skeleton_mapping']['skeletalRigMappings']
        self.assertEqual(sorted(sets), ['ACME_custom', 'vrm1_humanoid'])
        self.assertEqual(g.json['nodes'][sets['ACME_custom']['pelvis_role']['node']]['name'], 'pelvis')

    def test_no_mapping_no_extension(self):
        bones, _ = rigs.mixamo()
        rigs.build_armature(bones)
        g = u.Glb(u.export('skelmap_none', export_khr_character=True))
        self.assertNotIn('KHR_character_skeleton_mapping', g.json['extensions'])


if __name__ == '__main__':
    unittest.main()
