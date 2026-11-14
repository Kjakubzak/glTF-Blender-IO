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

# I1: KHR_character_skeleton_mapping from the armatures' khr_skeleton_mapping sets.
# Bones resolve to their exported joint nodes; a role is associated with at most one node per set; roles
# outside a known vocabulary are errors; mapped bones survive "deform bones only" (tree_filter).

import bpy

from ...com import khr_character as khr
from ...com.khr_character import automap
from ....io.com.gltf2_io_extensions import Extension


KNOWN_VOCABULARIES = {'vrm1_humanoid': lambda: automap.vocabulary()['parent']}


def tree_filter(ctx, vtree):
    """S4: with "deform bones only", keep every bone mapped in a skeleton mapping set (non-deform spine, neck,
    eye or jaw bones would otherwise be filtered out and their roles lost)."""
    if not ctx.settings.get('gltf_def_bones'):
        return
    mapped = set()
    for ob in bpy.data.objects:
        if ob.type == 'ARMATURE':
            for mapping_set in ob.khr_skeleton_mapping.sets:
                mapped.update((ob.data.name, e.bone) for e in mapping_set.entries if e.bone)
    if not mapped:
        return
    for node in vtree.nodes.values():
        bone = getattr(node, 'blender_bone', None)
        if bone is not None and (bone.id_data.name, bone.name) in mapped and not node.keep_tag:
            node.keep_tag = True
            ctx.kept_bones = getattr(ctx, 'kept_bones', 0) + 1


def root(ctx, gltf):
    sets = {}
    owners = {}
    for ob in bpy.data.objects:
        if ob.type != 'ARMATURE' or not len(ob.khr_skeleton_mapping.sets):
            continue
        exported = any(key[0] == ob.name for key in ctx.bone_nodes)
        if not exported:
            continue
        for mapping_set in ob.khr_skeleton_mapping.sets:
            if not mapping_set.set_id:
                ctx.error('mapping', '{}: mapping set without identifier'.format(ob.name))
                continue
            roles = sets.setdefault(mapping_set.set_id, {})
            for entry in mapping_set.entries:
                if not entry.role:
                    ctx.error('mapping', '{}/{}: entry without role'.format(ob.name, mapping_set.set_id))
                    continue
                vocabulary = KNOWN_VOCABULARIES.get(mapping_set.set_id)
                if vocabulary is not None and entry.role not in vocabulary():
                    # an exporter MUST write only roles that the set's vocabulary defines
                    ctx.error('mapping', '{}/{}: role {} is not in the vocabulary (dropped)'.format(
                        ob.name, mapping_set.set_id, entry.role))
                    continue
                node = ctx.bone_nodes.get((ob.name, entry.bone))
                if node is None:
                    ctx.error('mapping', '{}/{}: role {} uses bone "{}", which is not exported'.format(
                        ob.name, mapping_set.set_id, entry.role, entry.bone))
                    continue
                key = (mapping_set.set_id, entry.role)
                if key in owners:
                    ctx.error('mapping', '{}: role {} is mapped twice ({} and {})'.format(
                        mapping_set.set_id, entry.role, owners[key], ob.name))
                    continue
                owners[key] = ob.name
                roles[entry.role] = {'node': node}
            if mapping_set.set_id == 'vrm1_humanoid':
                problems = automap.validate({e.role: e.bone for e in mapping_set.entries}, bones=[
                    (b.name, b.parent.name if b.parent else None, tuple(b.head_local)) for b in ob.data.bones])
                for p in problems:
                    if not p.startswith('unknown role'):  # already an error above
                        ctx.warning('{}/vrm1_humanoid: {}'.format(ob.name, p))
    sets = {k: v for k, v in sets.items() if v}
    if sets:
        gltf.extensions[khr.SKELETON_MAPPING] = Extension(khr.SKELETON_MAPPING, {'skeletalRigMappings': sets}, False)
