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

# Generates tests/scenes/57_mapping.blend from generated data only (needs this add-on enabled):
#   blender -b --factory-startup --addons io_scene_gltf2 --python tests/scene_generators/57_mapping.py -- OUT.blend
# One quad mesh with ARKit-named shape keys; "Suggest ARKit Expressions" creates the expressions and
# "Suggest vrm1_expressions Mapping" the mapping set. The saved export settings enable the package.

import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "khr_character"))
import khr_test_utils as u  # noqa: E402

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)
u.shape_key_mesh('Face', ['jawOpen', 'mouthSmileLeft', 'mouthSmileRight', 'eyeBlinkLeft', 'eyeBlinkRight',
                          'mouthPucker', 'mouthFunnel', 'browInnerUp'])
assert bpy.ops.khr_character.suggest_arkit_expressions('EXEC_DEFAULT') == {'FINISHED'}
assert bpy.ops.khr_character.suggest_vrm1_mapping('EXEC_DEFAULT') == {'FINISHED'}

bpy.context.scene["glTF2ExportSettings"] = {"export_khr_character": True}
# Write only the scene and its dependencies: no window manager or file browser state.
bpy.data.libraries.write(out, {bpy.context.scene}, path_remap="NONE", fake_user=False, compress=False)
