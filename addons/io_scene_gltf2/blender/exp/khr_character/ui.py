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

# Export-dialog panel (drawn through exporter_extension_layout_draw), authoring panels and operators of
# the KHR_character package.

import bpy


def draw_export_panel(context, layout):
    operator = context.space_data.active_operator
    if operator is None or not hasattr(operator, 'export_khr_character'):
        return
    header, body = layout.panel('GLTF_export_khr_character', default_closed=True)
    header.use_property_split = False
    header.prop(operator, 'export_khr_character', text='')
    header.label(text='KHR_character')
    if body:
        body.active = operator.export_khr_character
        body.prop(operator, 'export_khr_strict')


def armature_bones(ob):
    return [(b.name, b.parent.name if b.parent else None, tuple(b.head_local)) for b in ob.data.bones]


class KHR_OT_auto_map_skeleton(bpy.types.Operator):
    """Map vrm1_humanoid roles to the bones of the active armature (all or nothing)"""
    bl_idname = 'khr_character.auto_map_skeleton'
    bl_label = 'Auto-Map Humanoid Roles'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'ARMATURE'

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        from ...com.khr_character import automap
        ob = context.active_object
        mapping, problems = automap.auto_map(armature_bones(ob))
        if problems:
            self.report({'ERROR'}, 'No mapping assigned: ' + '; '.join(problems[:5]))
            return {'CANCELLED'}
        sets = ob.khr_skeleton_mapping.sets
        target = next((s for s in sets if s.set_id == 'vrm1_humanoid'), None) or sets.add()
        target.set_id = 'vrm1_humanoid'
        target.entries.clear()
        order = list(automap.vocabulary()['parent'])
        for role in sorted(mapping, key=order.index):
            e = target.entries.add()
            e.role = role
            e.bone = mapping[role]
        self.report({'INFO'}, 'Mapped {} vrm1_humanoid roles'.format(len(mapping)))
        return {'FINISHED'}


class KHR_PT_skeleton_mapping(bpy.types.Panel):
    bl_label = 'KHR_character Skeleton Mapping'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'data'
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return context.object is not None and context.object.type == 'ARMATURE'

    def draw(self, context):
        ob = context.object
        layout = self.layout
        layout.operator(KHR_OT_auto_map_skeleton.bl_idname)
        for mapping_set in ob.khr_skeleton_mapping.sets:
            box = layout.box()
            box.prop(mapping_set, 'set_id')
            for e in mapping_set.entries:
                row = box.row(align=True)
                row.prop(e, 'role', text='')
                row.prop_search(e, 'bone', ob.data, 'bones', text='')


classes = (
    KHR_OT_auto_map_skeleton,
    KHR_PT_skeleton_mapping,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
