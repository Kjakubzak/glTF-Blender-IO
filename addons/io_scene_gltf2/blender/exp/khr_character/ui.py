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


def humanoid_mapping(ob):
    for s in ob.khr_skeleton_mapping.sets:
        if s.set_id == 'vrm1_humanoid':
            return {e.role: e.bone for e in s.entries if e.bone in ob.pose.bones}
    return {}


class KHR_OT_make_t_pose(bpy.types.Operator):
    """Create a one-frame t_pose reference-pose action from the rest pose (limbs only: torso, head, shoulders
    and feet keep the rest pose; limb_dir convention in the rig's own frame). Replaces this armature's
    previous t_pose action"""
    bl_idname = 'khr_character.make_t_pose'
    bl_label = 'Make T-Pose'
    bl_options = {'REGISTER', 'UNDO'}

    action_name: bpy.props.StringProperty(name='Action', default='t_pose')
    include_thumb: bpy.props.BoolProperty(name='Thumb', default=True)

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        from .tpose import make_t_pose
        ob = context.active_object
        mapping = humanoid_mapping(ob)
        missing = [r for r in ('leftUpperArm', 'rightUpperArm', 'leftLowerArm', 'rightLowerArm') if r not in mapping]
        if missing:
            self.report({'ERROR'}, 'vrm1_humanoid mapping lacks ' + ', '.join(missing))
            return {'CANCELLED'}
        mode = ob.mode
        if mode != 'POSE':
            bpy.ops.object.mode_set(mode='POSE')
        report = []
        action = make_t_pose(ob, mapping, self.action_name, include_thumb=self.include_thumb, report=report)
        for line in report:
            self.report({'WARNING'}, line)
        if mode != 'POSE':
            bpy.ops.object.mode_set(mode=mode)
        self.report({'INFO'}, 'Created reference pose action ' + action.name)
        return {'FINISHED'}


class KHR_OT_capture_reference_pose(bpy.types.Operator):
    """Key the current (or rest) pose of the armature as a one-frame reference-pose action"""
    bl_idname = 'khr_character.capture_reference_pose'
    bl_label = 'Capture Reference Pose'
    bl_options = {'REGISTER', 'UNDO'}

    pose_type: bpy.props.EnumProperty(name='Pose Type', items=(
        ('t_pose', 'T-Pose', ''), ('a_pose', 'A-Pose', ''), ('i_pose', 'I-Pose', '')), default='a_pose')
    from_rest: bpy.props.BoolProperty(name='From Rest Pose', default=True)
    action_name: bpy.props.StringProperty(name='Action', default='')

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        from .tpose import key_reference_pose
        ob = context.active_object
        report = []
        action = key_reference_pose(ob, self.action_name or self.pose_type, self.pose_type, self.from_rest,
                                    report=report)
        for line in report:
            self.report({'WARNING'}, line)
        self.report({'INFO'}, 'Created reference pose action ' + action.name)
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
        row = layout.row(align=True)
        row.operator(KHR_OT_make_t_pose.bl_idname)
        row.operator(KHR_OT_capture_reference_pose.bl_idname)
        for mapping_set in ob.khr_skeleton_mapping.sets:
            box = layout.box()
            box.prop(mapping_set, 'set_id')
            for e in mapping_set.entries:
                row = box.row(align=True)
                row.prop(e, 'role', text='')
                row.prop_search(e, 'bone', ob.data, 'bones', text='')


classes = (
    KHR_OT_auto_map_skeleton,
    KHR_OT_make_t_pose,
    KHR_OT_capture_reference_pose,
    KHR_PT_skeleton_mapping,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
