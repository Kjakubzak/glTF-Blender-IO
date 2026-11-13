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

# User extension loaded by export_gltf.py only for test scenes that store
# export_allowed_empty_extensions in their saved export settings.
# For every allowed name it adds an empty root extension, plus one empty
# extension that is not allowed and must be stripped by the exporter.

bl_info = {
    "name": "glTF test user extension",
    "blender": (4, 2, 0),
    "category": "Import-Export",
}

NOT_ALLOWED = 'EXT_test_not_allowed'


class glTF2ExportUserExtension:
    def __init__(self):
        from io_scene_gltf2.io.com.gltf2_io_extensions import Extension
        self.Extension = Extension

    def gather_gltf_extensions_hook(self, gltf2_object, export_settings):
        names = export_settings.get('gltf_allowed_empty_extensions', [])
        if not names:
            return
        for name in names:
            gltf2_object.extensions[name] = self.Extension(name, {}, False)
        gltf2_object.extensions[NOT_ALLOWED] = self.Extension(NOT_ALLOWED, {}, False)


def register():
    pass


def unregister():
    pass
