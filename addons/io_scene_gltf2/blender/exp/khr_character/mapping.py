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

# I5: KHR_character_expression_mapping. Scene.khr_character.mapping_sets become the root
# expressionSetMappings {set_id: {input: [{source, weight}]}}; each source is resolved by expression name
# to its index in the exported KHR_character_expression entries.

from ...com import khr_character as khr
from ....io.com.gltf2_io_extensions import Extension


def root(ctx, gltf_root):
    sets = ctx.scene_data.mapping_sets
    if not len(sets):
        return
    index = {e['name']: i for i, e in enumerate(getattr(ctx, 'expressions', []))}
    out = {}
    for s in sets:
        if not s.set_id:
            ctx.error('mapping', 'a mapping set has no identifier')
            continue
        if s.set_id in out:
            ctx.error('mapping', 'mapping set "{}" is defined twice'.format(s.set_id))
            continue
        inputs = {}
        for entry in s.entries:
            if not entry.name:
                ctx.error('mapping', '{}: an input has no name'.format(s.set_id))
                continue
            if entry.name in inputs:
                ctx.error('mapping', '{}: input "{}" is defined twice'.format(s.set_id, entry.name))
                continue
            contributions = []
            for source in entry.sources:
                if source.expression not in index:
                    ctx.error('mapping', '{}/{}: expression "{}" is not exported'.format(
                        s.set_id, entry.name, source.expression))
                    continue
                contributions.append({'source': index[source.expression], 'weight': round(source.weight, 6)})
            if contributions:
                inputs[entry.name] = contributions
            else:
                ctx.error('mapping', '{}/{}: no contribution'.format(s.set_id, entry.name))
        if inputs:
            out[s.set_id] = inputs
    if out:
        if not index:
            ctx.error('mapping', 'expression mappings need exported expressions')
            return
        gltf_root.extensions[khr.EXPRESSION_MAPPING] = Extension(khr.EXPRESSION_MAPPING,
                                                                 {'expressionSetMappings': out}, False)
