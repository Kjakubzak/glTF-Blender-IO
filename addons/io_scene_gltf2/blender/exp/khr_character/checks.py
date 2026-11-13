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

# Cross-feature validation rules (strict mode turns them into export errors).

from ...com import khr_character as khr


def validate(ctx, gltf):
    used = gltf.extensions_used or []
    required = gltf.extensions_required or []
    for name in ctx.declared:
        if name not in used:
            ctx.error('declaration', '{} is not listed in extensionsUsed'.format(name))
    for name in khr.HINT_EXTENSIONS:
        if name in required:
            ctx.error('hint-required', '{} must not be listed in extensionsRequired'.format(name))
