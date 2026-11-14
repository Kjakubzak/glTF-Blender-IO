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

# Generates tests/scenes/59_hints.blend from generated data only (needs this add-on enabled):
#   blender -b --factory-startup --addons io_scene_gltf2 --python tests/scene_generators/59_hints.py -- OUT.blend
# The hint scene of tests/khr_character/test_hints.py at 1024x1024: a perspective full_body and an
# orthographic portrait hint camera (source aspect 1, portrait targets EyeTarget), a look-at target, a
# node visibility hint and a primitive visibility hint. The saved export settings enable the package and
# camera export.

import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "khr_character"))
import test_hints  # noqa: E402

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)
test_hints.hint_scene()

bpy.context.scene["glTF2ExportSettings"] = {"export_khr_character": True, "export_cameras": True}
# Write only the scene and its dependencies: no window manager or file browser state.
bpy.data.libraries.write(out, {bpy.context.scene}, path_remap="NONE", fake_user=False, compress=False)
