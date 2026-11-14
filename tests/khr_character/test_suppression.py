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

import khr_test_utils as u
from test_expression import add_expression

EXT = 'KHR_character_expression'
SUP = 'KHR_character_expression_suppression'


def suppress(expression, target, type_='blend', amount=1.0, threshold=0.0, use_threshold=False, custom=''):
    s = expression.suppressions.add()
    s.target, s.type, s.amount, s.threshold, s.use_threshold, s.custom_type = (
        target, type_, amount, threshold, use_threshold, custom)


class Suppression(unittest.TestCase):
    def setUp(self):
        u.clear_scene()
        u.shape_key_mesh('Face', ['eyeBlinkLeft', 'eyeLookUpLeft', 'mouthSmileLeft', 'jawOpen'])
        self.e = {k: add_expression(k, (k, 1.0)) for k in ('eyeBlinkLeft', 'eyeLookUpLeft', 'mouthSmileLeft',
                                                           'jawOpen')}

    def test_types_and_threshold(self):
        suppress(self.e['eyeBlinkLeft'], 'eyeLookUpLeft', 'blend', 0.8, threshold=0.4, use_threshold=True)
        suppress(self.e['eyeBlinkLeft'], 'mouthSmileLeft', 'block', 0.5, threshold=0.25)
        suppress(self.e['jawOpen'], 'mouthSmileLeft', 'CUSTOM', 0.3, custom='ACME_expression_curve')
        g = u.Glb(u.export('suppression', export_khr_character=True))
        entries = g.json['extensions'][EXT]['expressions']
        self.assertEqual(entries[0]['extensions'][SUP], {'suppressions': [
            {'target': 1, 'type': 'blend', 'amount': 0.8},
            {'target': 2, 'type': 'block', 'amount': 0.5, 'threshold': 0.25}]})
        self.assertEqual(entries[3]['extensions'][SUP], {'suppressions': [
            {'target': 2, 'type': 'ACME_expression_curve', 'amount': 0.3}]})
        self.assertNotIn(SUP, entries[1]['extensions'])
        self.assertIn(SUP, g.json['extensionsUsed'])
        self.assertNotIn(SUP, g.json.get('extensionsRequired', []))

    def test_unknown_target_and_bad_custom_type(self):
        suppress(self.e['jawOpen'], 'nope')
        with self.assertRaises(RuntimeError):
            u.export('suppression_target', export_khr_character=True)
        self.e['jawOpen'].suppressions.clear()
        suppress(self.e['jawOpen'], 'eyeBlinkLeft', 'CUSTOM', custom='acme-curve')
        with self.assertRaises(RuntimeError):
            u.export('suppression_custom', export_khr_character=True)


if __name__ == '__main__':
    unittest.main()
