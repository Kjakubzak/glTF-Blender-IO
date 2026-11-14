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

# I0: the top-level KHR_character marker, an empty object kept through gltf_allowed_empty_extensions.

from ...com import khr_character as khr
from ....io.com.gltf2_io_extensions import Extension


def root(ctx, gltf):
    gltf.extensions[khr.KHR_CHARACTER] = Extension(khr.KHR_CHARACTER, {}, False)


def validate(ctx, gltf):
    if khr.KHR_CHARACTER in (gltf.extensions_required or []):
        ctx.error('marker', 'KHR_character is not written to extensionsRequired by this exporter')
