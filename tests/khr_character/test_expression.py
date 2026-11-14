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

EXT = 'KHR_character_expression'
MORPH = 'KHR_character_expression_morphtarget'


def add_expression(name, *weights):
    e = bpy.context.scene.khr_character.expressions.add()
    e.name = name
    e.source = 'SHAPE_KEYS'
    for key, weight, *ob in weights:
        w = e.shape_key_weights.add()
        w.key_name = key
        w.weight = weight
        if ob:
            w.object = ob[0]
    return e


class MorphExpressions(unittest.TestCase):
    def setUp(self):
        u.clear_scene()
        self.face = u.shape_key_mesh('Face', ['jawOpen', 'smile', 'blink'])
        self.teeth = u.shape_key_mesh('Teeth', ['jawOpen'], location=(0, 0, -0.2))

    def weights(self, g, animation, node_name):
        for ch in animation['channels']:
            if ch['target']['node'] == g.node_index(node_name):
                self.assertEqual(ch['target']['path'], 'weights')
                s = animation['samplers'][ch['sampler']]
                self.assertEqual(s.get('interpolation', 'LINEAR'), 'LINEAR')
                times = g.accessor(s['input'])[:, 0].tolist()
                self.assertEqual(times, [0.0, 1.0])
                self.assertEqual(g.json['accessors'][s['input']]['min'], [0.0])
                self.assertEqual(g.json['accessors'][s['input']]['max'], [1.0])
                values = g.accessor(s['output'])[:, 0]
                n = len(values) // 2
                return [round(float(v), 6) for v in values[:n]], [round(float(v), 6) for v in values[n:]]
        return None

    def test_multimesh_by_name(self):
        add_expression('jawOpen', ('jawOpen', 1.0))
        add_expression('smileHalf', ('smile', 0.5))
        g = u.Glb(u.export('expr_multimesh', export_khr_character=True))
        entries = g.json['extensions'][EXT]['expressions']
        self.assertEqual([e['name'] for e in entries], ['jawOpen', 'smileHalf'])
        for name in (EXT, MORPH, 'KHR_character'):
            self.assertIn(name, g.json['extensionsUsed'])
            self.assertNotIn(name, g.json.get('extensionsRequired', []))
        jaw = g.json['animations'][entries[0]['animation']]
        smile = g.json['animations'][entries[1]['animation']]
        self.assertEqual(jaw['name'], 'jawOpen')
        self.assertEqual(entries[0]['extensions'][MORPH], {'channels': [0, 1]})
        self.assertEqual(entries[1]['extensions'][MORPH], {'channels': [0]})
        self.assertEqual(self.weights(g, jaw, 'Face'), ([0, 0, 0], [1, 0, 0]))
        self.assertEqual(self.weights(g, jaw, 'Teeth'), ([0], [1]))
        self.assertEqual(self.weights(g, smile, 'Face'), ([0, 0, 0], [0, 0.5, 0]))
        self.assertIsNone(self.weights(g, smile, 'Teeth'))

    def test_exported_key_order_and_initial_value(self):
        self.face.data.shape_keys.key_blocks['smile'].mute = True
        self.face.data.shape_keys.key_blocks['blink'].value = 0.25
        add_expression('blink', ('blink', 0.5))
        g = u.Glb(u.export('expr_order', export_khr_character=True))
        anim = g.animation('blink')
        self.assertEqual(self.weights(g, anim, 'Face'), ([0, 0.25], [0, 0.75]))

    def test_weights_outside_unit_range_are_not_clamped(self):
        add_expression('jawPress', ('jawOpen', -0.054), ('smile', 1.25))
        g = u.Glb(u.export('expr_unclamped', export_khr_character=True))
        self.assertEqual(self.weights(g, g.animation('jawPress'), 'Face'), ([0, 0, 0], [-0.054, 1.25, 0]))

    def test_object_filter(self):
        add_expression('jawFaceOnly', ('jawOpen', 1.0, self.face))
        g = u.Glb(u.export('expr_filter', export_khr_character=True))
        anim = g.animation('jawFaceOnly')
        self.assertEqual(len(anim['channels']), 1)
        self.assertIsNone(self.weights(g, anim, 'Teeth'))

    def test_order_clips_expressions_reference_poses(self):
        ad = self.face.data.shape_keys.animation_data_create()
        clip = bpy.data.actions.new('talk')
        ad.action = clip
        k = self.face.data.shape_keys.key_blocks['jawOpen']
        for frame, v in ((1, 0.0), (10, 1.0)):
            k.value = v
            k.keyframe_insert('value', frame=frame)
        k.value = 0.0
        add_expression('jawOpen', ('jawOpen', 1.0))
        g = u.Glb(u.export('expr_order_anims', export_khr_character=True))
        names = [a['name'] for a in g.json['animations']]
        self.assertEqual(names[-1], 'jawOpen')
        self.assertLess(names.index('jawOpen'), len(names))
        self.assertEqual(len(names), 2)

    def test_unknown_key_strict_and_lenient(self):
        add_expression('jawOpen', ('jawOpen', 1.0))
        add_expression('bad', ('no_such_key', 1.0))
        with self.assertRaises(RuntimeError):
            u.export('expr_unknown', export_khr_character=True)
        g = u.Glb(u.export('expr_unknown_lenient', export_khr_character=True, export_khr_strict=False))
        self.assertEqual([e['name'] for e in g.json['extensions'][EXT]['expressions']], ['jawOpen'])

    def test_duplicate_name_aborts(self):
        add_expression('jawOpen', ('jawOpen', 1.0))
        add_expression('jawOpen', ('smile', 1.0))
        with self.assertRaises(RuntimeError):
            u.export('expr_duplicate', export_khr_character=True)

    def test_package_off(self):
        add_expression('jawOpen', ('jawOpen', 1.0))
        g = u.Glb(u.export('expr_off'))
        self.assertNotIn('extensions', g.json)
        self.assertNotIn('animations', g.json)

    def test_suggest_arkit(self):
        u.shape_key_mesh('Brows', ['face.browInnerUp', 'mouth_smile_left', 'custom'])
        add_expression('jawOpen', ('jawOpen', 0.3))
        self.assertEqual(bpy.ops.khr_character.suggest_arkit_expressions('EXEC_DEFAULT'), {'FINISHED'})
        exprs = {e.name: [(w.key_name, round(w.weight, 6)) for w in e.shape_key_weights]
                 for e in bpy.context.scene.khr_character.expressions}
        self.assertEqual(exprs, {'jawOpen': [('jawOpen', 0.3)], 'browInnerUp': [('face.browInnerUp', 1.0)],
                                 'mouthSmileLeft': [('mouth_smile_left', 1.0)]})


class Names(unittest.TestCase):
    def test_suggest(self):
        from io_scene_gltf2.blender.com.khr_character.expression_names import ARKIT_52, suggest_arkit
        self.assertEqual(len(ARKIT_52), 52)
        self.assertEqual(len(set(ARKIT_52)), 52)
        self.assertEqual(suggest_arkit(['JawOpen', 'x:eyeBlinkLeft', 'tongue_out', 'foo']),
                         [('eyeBlinkLeft', 'x:eyeBlinkLeft'), ('jawOpen', 'JawOpen'), ('tongueOut', 'tongue_out')])


if __name__ == '__main__':
    unittest.main()
