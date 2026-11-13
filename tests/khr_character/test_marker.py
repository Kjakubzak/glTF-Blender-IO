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

# I0: KHR_character marker.

import unittest

import bpy

import khr_test_utils as u


class Marker(unittest.TestCase):
    def setUp(self):
        u.clear_scene()
        bpy.ops.mesh.primitive_cube_add()

    def test_marker_written_used_not_required(self):
        g = u.Glb(u.export('marker', export_khr_character=True))
        self.assertEqual(g.json['extensions']['KHR_character'], {})
        self.assertIn('KHR_character', g.json['extensionsUsed'])
        self.assertNotIn('KHR_character', g.json.get('extensionsRequired', []))

    def test_no_marker_when_option_off(self):
        g = u.Glb(u.export('no_marker'))
        self.assertNotIn('extensions', g.json)


if __name__ == '__main__':
    unittest.main()
