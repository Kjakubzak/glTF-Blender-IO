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

EXT = 'KHR_character_expression_mapping'


def add_set(set_id, inputs):
    s = bpy.context.scene.khr_character.mapping_sets.add()
    s.set_id = set_id
    for name, sources in inputs.items():
        e = s.entries.add()
        e.name = name
        for expression, weight in sources:
            src = e.sources.add()
            src.expression = expression
            src.weight = weight
    return s


class Mapping(unittest.TestCase):
    def setUp(self):
        u.clear_scene()
        u.shape_key_mesh('Face', ['jawOpen', 'mouthSmileLeft', 'mouthSmileRight', 'eyeBlinkLeft'])
        for key in ('jawOpen', 'mouthSmileLeft', 'mouthSmileRight', 'eyeBlinkLeft'):
            add_expression(key, (key, 1.0))

    def test_sets_resolve_to_indices(self):
        add_set('vrm1_expressions', {'aa': [('jawOpen', 1.0)],
                                     'happy': [('mouthSmileLeft', 1.0), ('mouthSmileRight', 0.75)]})
        add_set('ACME_custom_v1', {'open': [('jawOpen', 0.5)]})
        g = u.Glb(u.export('mapping', export_khr_character=True))
        self.assertIn(EXT, g.json['extensionsUsed'])
        self.assertNotIn(EXT, g.json.get('extensionsRequired', []))
        self.assertEqual(g.json['extensions'][EXT], {'expressionSetMappings': {
            'vrm1_expressions': {'aa': [{'source': 0, 'weight': 1.0}],
                                 'happy': [{'source': 1, 'weight': 1.0}, {'source': 2, 'weight': 0.75}]},
            'ACME_custom_v1': {'open': [{'source': 0, 'weight': 0.5}]}}})

    def test_unknown_expression_strict_and_lenient(self):
        add_set('vrm1_expressions', {'aa': [('jawOpen', 1.0)], 'oh': [('mouthFunnel', 1.0)]})
        with self.assertRaises(RuntimeError):
            u.export('mapping_bad', export_khr_character=True)
        g = u.Glb(u.export('mapping_lenient', export_khr_character=True, export_khr_strict=False))
        self.assertEqual(list(g.json['extensions'][EXT]['expressionSetMappings']['vrm1_expressions']), ['aa'])

    def test_duplicate_input_aborts(self):
        s = add_set('vrm1_expressions', {'aa': [('jawOpen', 1.0)]})
        e = s.entries.add()
        e.name = 'aa'
        e.sources.add().expression = 'jawOpen'
        with self.assertRaises(RuntimeError):
            u.export('mapping_dup', export_khr_character=True)

    def test_suggest_vrm1(self):
        self.assertEqual(bpy.ops.khr_character.suggest_vrm1_mapping('EXEC_DEFAULT'), {'FINISHED'})
        s = bpy.context.scene.khr_character.mapping_sets[0]
        self.assertEqual(s.set_id, 'vrm1_expressions')
        got = {e.name: [(x.expression, round(x.weight, 3)) for x in e.sources] for e in s.entries}
        self.assertEqual(got, {'happy': [('mouthSmileLeft', 1.0), ('mouthSmileRight', 1.0)],
                               'relaxed': [('mouthSmileLeft', 0.5), ('mouthSmileRight', 0.5)],
                               'aa': [('jawOpen', 1.0)], 'ih': [('jawOpen', 0.2)], 'ou': [('jawOpen', 0.2)],
                               'oh': [('jawOpen', 0.4)], 'surprised': [('jawOpen', 0.3)],
                               'blink': [('eyeBlinkLeft', 1.0)], 'blinkLeft': [('eyeBlinkLeft', 1.0)]})
        g = u.Glb(u.export('mapping_suggested', export_khr_character=True))
        self.assertIn('happy', g.json['extensions'][EXT]['expressionSetMappings']['vrm1_expressions'])


if __name__ == '__main__':
    unittest.main()
