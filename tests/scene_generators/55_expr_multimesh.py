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

# Generates tests/scenes/55_expr_multimesh.blend from generated data only (needs this add-on enabled):
#   blender -b --factory-startup --addons io_scene_gltf2 \
#       --python tests/scene_generators/55_expr_multimesh.py -- OUT.blend
# Three quad meshes share shape-key names (Face: jawOpen, mouthSmileLeft, eyeBlinkLeft; Teeth: jawOpen;
# Tongue: jawOpen, tongueOut). "Suggest ARKit Expressions" creates one expression per name, and
# "smileHalf" sets mouthSmileLeft to 0.5. The saved export settings enable the KHR_character package.

import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "khr_character"))
import khr_test_utils as u  # noqa: E402

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)
u.shape_key_mesh('Face', ['jawOpen', 'mouthSmileLeft', 'eyeBlinkLeft'])
u.shape_key_mesh('Teeth', ['jawOpen'], location=(0, 0, -0.2))
u.shape_key_mesh('Tongue', ['jawOpen', 'tongueOut'], location=(0, 0, -0.4))
assert bpy.ops.khr_character.suggest_arkit_expressions('EXEC_DEFAULT') == {'FINISHED'}
e = bpy.context.scene.khr_character.expressions.add()
e.name = 'smileHalf'
w = e.shape_key_weights.add()
w.key_name = 'mouthSmileLeft'
w.weight = 0.5

bpy.context.scene["glTF2ExportSettings"] = {"export_khr_character": True}
# Write only the scene and its dependencies: no window manager or file browser state.
bpy.data.libraries.write(out, {bpy.context.scene}, path_remap="NONE", fake_user=False, compress=False)
