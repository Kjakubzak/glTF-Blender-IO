# Copyright 2018-2021 The Khronos Group Inc.
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

import bpy
import os
import sys

try:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]  # get all args after "--"
    else:
        argv = []

    extension = '.gltf'
    if '--glb' in argv:
        extension = '.glb'

    path = os.path.splitext(bpy.data.filepath)[0] + extension
    path_parts = os.path.split(path)
    output_dir = os.path.join(path_parts[0], argv[0])
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    settings = dict(bpy.context.scene.get('glTF2ExportSettings', {}))
    if settings.get('export_allowed_empty_extensions'):
        # Test-only user extension, see gltf_test_user_extension.py
        import addon_utils
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        addon_utils.enable('gltf_test_user_extension', default_set=True)
    args = {
        # Settings from "Remember Export Settings"
        **settings,

        'export_format': ('GLB' if extension == '.glb' else 'GLTF_SEPARATE'),
        'filepath': os.path.join(output_dir, path_parts[1]),
    }
    bpy.context.preferences.addons['io_scene_gltf2'].preferences.KHR_materials_variants_ui = True
    bpy.ops.export_scene.gltf(**args)
except Exception as err:
    print(err, file=sys.stderr)
    sys.exit(1)
