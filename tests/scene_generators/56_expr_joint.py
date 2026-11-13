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

# Generates the I4 expression scenes from generated data only (needs this add-on enabled):
#   blender -b --factory-startup --addons io_scene_gltf2 \
#       --python tests/scene_generators/56_expr_joint.py -- OUT.blend VARIANT
# VARIANT joint: a mixamo-style skeleton with a "nod" action (head rotation; spine keyed but constant) used
#   as an ACTION expression, plus a clip action.
# VARIANT from_control: "Capture Expression" from a control property that drives the head and a shape key
#   (0.2 at neutral); the drivers are removed after the capture, as on export copies.
# VARIANT headframe: "Capture Expression" with look LEFT on eye joints whose bone axes do not follow
#   the gaze.
# The saved export settings enable the KHR_character package and export each action.

import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
out, variant = argv[0], argv[1]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "khr_character"))
import test_expression_joint as t  # noqa: E402

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)
if variant == 'joint':
    ob, _ = t.armature()
    nod = bpy.data.actions.new('nod')
    nod.use_fake_user = True
    t.key_rotation(ob, nod, {0: {t.P + 'Spine': (1, 0, 0, 0), t.P + 'Head': (1, 0, 0, 0)},
                             24: {t.P + 'Head': (0.9659, 0.2588, 0, 0)}})
    clip = bpy.data.actions.new('clip')
    clip.use_fake_user = True
    t.key_rotation(ob, clip, {1: {t.P + 'Neck': (1, 0, 0, 0)}, 10: {t.P + 'Neck': (0.9659, 0, 0, 0.2588)}})
    t.add_action_expression('nod', nod)
elif variant == 'from_control':
    ob, face, _ = t.face_rig()
    assert bpy.ops.khr_character.capture_expression(
        'EXEC_DEFAULT', name='smile', source='CONTROL', control_path='["smile"]') == {'FINISHED'}
    ob.pose.bones[t.P + 'Head'].driver_remove('rotation_euler', 0)
    face.data.shape_keys.key_blocks['mouthSmileLeft'].driver_remove('value')
else:
    t.eye_rig()
    assert bpy.ops.khr_character.capture_expression(
        'EXEC_DEFAULT', name='lookLeft', source='ACTION', look='LEFT', look_angle=12.0) == {'FINISHED'}

bpy.context.scene["glTF2ExportSettings"] = {"export_khr_character": True, "export_animation_mode": "ACTIONS"}
# Write only the scene, its dependencies and the actions: no window manager or file browser state.
bpy.data.libraries.write(out, {bpy.context.scene, *bpy.data.actions}, path_remap="NONE", fake_user=True,
                         compress=False)
