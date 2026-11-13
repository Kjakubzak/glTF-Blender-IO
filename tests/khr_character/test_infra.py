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

# KHR_character package infrastructure: option switch, generator provenance, strict mode, extras.

import re
import subprocess
import os
import unittest

import bpy

import khr_test_utils as u
from io_scene_gltf2.blender.com import extras
from io_scene_gltf2.blender.com import khr_character as khr
from io_scene_gltf2.blender.exp import khr_character as khr_exp
from io_scene_gltf2.blender.exp.khr_character import features

GENERATOR_OFF = re.compile(r'^Khronos glTF Blender I/O v[0-9.]+$')
GENERATOR_ON = re.compile(r'^Khronos glTF Blender I/O v[0-9.]+\+khr_character\.[0-9a-f]{12}\.bl[0-9.]+$')


class FailingRule:
    @staticmethod
    def validate(ctx, gltf):
        ctx.error('test-rule', 'deliberate failure')


class Infra(unittest.TestCase):
    def setUp(self):
        u.clear_scene()
        bpy.ops.mesh.primitive_cube_add()

    def test_black_list_covers_package_properties(self):
        for name in khr.PROPERTY_NAMES:
            self.assertIn(name, extras.BLACK_LIST)

    def test_option_off_is_deterministic_and_plain(self):
        a = u.Glb(u.export('off_a'))
        b = u.Glb(u.export('off_b'))
        self.assertEqual(a.bytes, b.bytes)
        self.assertRegex(a.json['asset']['generator'], GENERATOR_OFF)
        self.assertNotIn('extensionsUsed', a.json)

    def test_option_on_generator_suffix(self):
        g = u.Glb(u.export('on', export_khr_character=True))
        self.assertRegex(g.json['asset']['generator'], GENERATOR_ON)
        version = '.'.join(str(v) for v in bpy.app.version)
        self.assertTrue(g.json['asset']['generator'].endswith('.bl' + version))

    def test_option_on_is_deterministic(self):
        a = u.export('on_a', export_khr_character=True)
        b = u.export('on_b', export_khr_character=True)
        self.assertEqual(u.Glb(a).bytes, u.Glb(b).bytes)

    def test_fork_revision_matches_git(self):
        here = os.path.dirname(khr_exp.__file__)
        r = subprocess.run(['git', '-C', here, 'rev-parse', 'HEAD'], capture_output=True, text=True)
        if r.returncode != 0:
            self.skipTest('add-on is not in a git checkout')
        self.assertEqual(khr_exp.fork_revision(), r.stdout.strip()[:12])

    def test_strict_rule_failure_aborts_export(self):
        features.FEATURES.append(FailingRule)
        try:
            with self.assertRaises(RuntimeError):
                u.export('strict', export_khr_character=True, export_khr_strict=True)
            self.assertFalse(os.path.exists(os.path.join(u.TMP, 'strict.glb')))
        finally:
            features.FEATURES.remove(FailingRule)

    def test_non_strict_rule_failure_only_logs(self):
        features.FEATURES.append(FailingRule)
        try:
            g = u.Glb(u.export('lenient', export_khr_character=True, export_khr_strict=False))
            self.assertRegex(g.json['asset']['generator'], GENERATOR_ON)
        finally:
            features.FEATURES.remove(FailingRule)

    def test_package_properties_never_exported_as_extras(self):
        ob = bpy.context.active_object
        ob.khr_hints.lookat.hint = 'test'
        ob['user_property'] = 1
        g = u.Glb(u.export('extras', export_extras=True))
        node = g.json['nodes'][g.node_index(ob.name)]
        self.assertEqual(node.get('extras'), {'user_property': 1})


if __name__ == '__main__':
    unittest.main()
