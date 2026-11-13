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

# Generates tests/scenes/50_empty_extension_hook.blend from generated data only:
#   blender -b --factory-startup --python tests/scene_generators/50_empty_extension_hook.py -- OUT.blend
# The scene stores export_allowed_empty_extensions in its saved export settings,
# which makes export_gltf.py load gltf_test_user_extension.py.

import sys

import bpy

out = sys.argv[sys.argv.index("--") + 1]

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)
bpy.ops.mesh.primitive_cube_add(size=1.0)
bpy.context.active_object.name = "Cube"
bpy.context.scene["glTF2ExportSettings"] = {"export_allowed_empty_extensions": "KHR_character"}
# Write only the scene and its dependencies: no window manager or file browser state.
bpy.data.libraries.write(out, {bpy.context.scene}, path_remap="NONE", fake_user=False, compress=False)
