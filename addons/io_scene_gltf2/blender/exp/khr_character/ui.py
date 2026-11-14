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
    """Create a one-frame t_pose reference-pose action from the rest pose (limb_dir convention)"""
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
        action = make_t_pose(ob, mapping, self.action_name, include_thumb=self.include_thumb)
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
        action = key_reference_pose(ob, self.action_name or self.pose_type, self.pose_type, self.from_rest)
        self.report({'INFO'}, 'Created reference pose action ' + action.name)
        return {'FINISHED'}


class KHR_OT_capture_expression(bpy.types.Operator):
    """Key the change between a neutral and a peak state of the active armature (and its shape keys) as a
    two-key expression action, and add it as an ACTION expression"""
    bl_idname = 'khr_character.capture_expression'
    bl_label = 'Capture Expression'
    bl_options = {'REGISTER', 'UNDO'}

    name: bpy.props.StringProperty(name='Name', default='expression')
    source: bpy.props.EnumProperty(name='Source', items=(
        ('ACTION', 'Action Frames', 'Neutral and peak frames of an action'),
        ('CONTROL', 'Control', 'Neutral and peak values of a property of the armature object')), default='ACTION')
    action_name: bpy.props.StringProperty(name='Action')
    neutral_frame: bpy.props.IntProperty(name='Neutral Frame', default=0)
    peak_frame: bpy.props.IntProperty(name='Peak Frame', default=24)
    control_path: bpy.props.StringProperty(name='Control', description='e.g. pose.bones["face"]["smile"]')
    neutral_value: bpy.props.FloatProperty(name='Neutral Value', default=0.0)
    peak_value: bpy.props.FloatProperty(name='Peak Value', default=1.0)
    look: bpy.props.EnumProperty(name='Look', items=(
        ('NONE', 'None', ''), ('LEFT', 'Left', ''), ('RIGHT', 'Right', ''), ('UP', 'Up', ''), ('DOWN', 'Down', '')),
        default='NONE', description='Also rotate the mapped eyes about a head-frame axis (character directions)')
    look_angle: bpy.props.FloatProperty(name='Look Angle', default=12.0, min=0.0, max=90.0)

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'ARMATURE'

    def execute(self, context):
        from .capture import capture_expression
        ob = context.active_object
        mapping = humanoid_mapping(ob)
        if self.look != 'NONE' and 'head' not in mapping:
            self.report({'ERROR'}, 'Look needs a vrm1_humanoid mapping with head (and eyes)')
            return {'CANCELLED'}
        action = bpy.data.actions.get(self.action_name) if self.action_name else None
        if self.source == 'ACTION' and self.action_name and action is None:
            self.report({'ERROR'}, 'No action ' + self.action_name)
            return {'CANCELLED'}
        out, warnings = capture_expression(
            ob, self.name, mapping, source=self.source, action=action, neutral_frame=self.neutral_frame,
            peak_frame=self.peak_frame, control_path=self.control_path, neutral_value=self.neutral_value,
            peak_value=self.peak_value, look=self.look, look_angle=self.look_angle)
        for w in warnings:
            self.report({'WARNING'}, w)
        self.report({'INFO'}, 'Captured expression action ' + out.name)
        return {'FINISHED'}


class KHR_OT_suggest_vrm1_mapping(bpy.types.Operator):
    """Create (or replace) the vrm1_expressions mapping set from the scene's expression names"""
    bl_idname = 'khr_character.suggest_vrm1_mapping'
    bl_label = 'Suggest vrm1_expressions Mapping'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from ...com.khr_character.expression_names import suggest_vrm1
        sc = context.scene.khr_character
        suggestion = suggest_vrm1([e.name for e in sc.expressions])
        if not suggestion:
            self.report({'WARNING'}, 'No expression matches a vrm1_expressions input')
            return {'CANCELLED'}
        target = next((s for s in sc.mapping_sets if s.set_id == 'vrm1_expressions'), None)
        if target is None:
            target = sc.mapping_sets.add()
            target.set_id = 'vrm1_expressions'
        target.entries.clear()
        for name, sources in suggestion.items():
            entry = target.entries.add()
            entry.name = name
            for expression, weight in sources:
                src = entry.sources.add()
                src.expression = expression
                src.weight = weight
        self.report({'INFO'}, 'Mapped {} vrm1_expressions inputs'.format(len(suggestion)))
        return {'FINISHED'}


class KHR_PT_expression_mapping(bpy.types.Panel):
    bl_label = 'KHR_character Expression Mapping'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        sc = context.scene.khr_character
        layout.operator(KHR_OT_suggest_vrm1_mapping.bl_idname)
        for s in sc.mapping_sets:
            box = layout.box()
            box.prop(s, 'set_id')
            for entry in s.entries:
                row = box.row()
                row.label(text=entry.name)
                row.label(text=', '.join('{} x{:.2f}'.format(x.expression, x.weight) for x in entry.sources))


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


class KHR_UL_expressions(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, 'name', text='', emboss=False)
        layout.label(text=item.source.replace('_', ' ').title())


class KHR_OT_expression_add(bpy.types.Operator):
    """Add a shape-key expression"""
    bl_idname = 'khr_character.expression_add'
    bl_label = 'Add Expression'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        sc = context.scene.khr_character
        e = sc.expressions.add()
        e.name = 'expression.{:03d}'.format(len(sc.expressions))
        sc.active_expression = len(sc.expressions) - 1
        return {'FINISHED'}


class KHR_OT_expression_remove(bpy.types.Operator):
    """Remove the active expression"""
    bl_idname = 'khr_character.expression_remove'
    bl_label = 'Remove Expression'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return len(context.scene.khr_character.expressions) > 0

    def execute(self, context):
        sc = context.scene.khr_character
        sc.expressions.remove(sc.active_expression)
        sc.active_expression = max(0, min(sc.active_expression, len(sc.expressions) - 1))
        return {'FINISHED'}


class KHR_OT_expression_key_add(bpy.types.Operator):
    """Add a shape key to the active expression"""
    bl_idname = 'khr_character.expression_key_add'
    bl_label = 'Add Shape Key'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return len(context.scene.khr_character.expressions) > 0

    def execute(self, context):
        sc = context.scene.khr_character
        sc.expressions[sc.active_expression].shape_key_weights.add()
        return {'FINISHED'}


class KHR_OT_expression_key_remove(bpy.types.Operator):
    """Remove a shape key from the active expression"""
    bl_idname = 'khr_character.expression_key_remove'
    bl_label = 'Remove Shape Key'
    bl_options = {'REGISTER', 'UNDO'}

    index: bpy.props.IntProperty()

    def execute(self, context):
        sc = context.scene.khr_character
        weights = sc.expressions[sc.active_expression].shape_key_weights
        if 0 <= self.index < len(weights):
            weights.remove(self.index)
        return {'FINISHED'}


def scene_shape_key_names(scene):
    names = []
    for ob in scene.objects:
        if ob.type == 'MESH' and ob.data.shape_keys is not None:
            for k in ob.data.shape_keys.key_blocks[1:]:
                if k.name not in names:
                    names.append(k.name)
    return names


class KHR_OT_suggest_arkit_expressions(bpy.types.Operator):
    """Add one expression per ARKit blend-shape name found among the scene's shape keys (existing names are kept)"""
    bl_idname = 'khr_character.suggest_arkit_expressions'
    bl_label = 'Suggest ARKit Expressions'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from ...com.khr_character.expression_names import suggest_arkit
        sc = context.scene.khr_character
        existing = {e.name for e in sc.expressions}
        added = 0
        for name, key in suggest_arkit(scene_shape_key_names(context.scene)):
            if name in existing:
                continue
            e = sc.expressions.add()
            e.name = name
            e.source = 'SHAPE_KEYS'
            w = e.shape_key_weights.add()
            w.key_name = key
            w.weight = 1.0
            added += 1
        self.report({'INFO'}, 'Added {} expressions'.format(added))
        return {'FINISHED'}


class KHR_PT_expressions(bpy.types.Panel):
    bl_label = 'KHR_character Expressions'
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = 'scene'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        layout = self.layout
        sc = context.scene.khr_character
        row = layout.row()
        row.template_list('KHR_UL_expressions', '', sc, 'expressions', sc, 'active_expression', rows=4)
        col = row.column(align=True)
        col.operator(KHR_OT_expression_add.bl_idname, icon='ADD', text='')
        col.operator(KHR_OT_expression_remove.bl_idname, icon='REMOVE', text='')
        row = layout.row(align=True)
        row.operator(KHR_OT_suggest_arkit_expressions.bl_idname)
        row.operator(KHR_OT_capture_expression.bl_idname)
        if not len(sc.expressions):
            return
        e = sc.expressions[min(sc.active_expression, len(sc.expressions) - 1)]
        layout.prop(e, 'name')
        layout.prop(e, 'source')
        if e.source == 'SHAPE_KEYS':
            for i, w in enumerate(e.shape_key_weights):
                row = layout.row(align=True)
                row.prop(w, 'key_name', text='')
                row.prop(w, 'weight', text='')
                row.prop(w, 'object', text='')
                row.operator(KHR_OT_expression_key_remove.bl_idname, icon='X', text='').index = i
            layout.operator(KHR_OT_expression_key_add.bl_idname, icon='ADD')
        else:
            layout.prop(e, 'action')
            layout.prop(e, 'track_name')
            layout.prop(e, 'allow_joints')
            layout.prop(e, 'allow_morphs')


classes = (
    KHR_OT_auto_map_skeleton,
    KHR_OT_make_t_pose,
    KHR_OT_capture_reference_pose,
    KHR_OT_capture_expression,
    KHR_UL_expressions,
    KHR_OT_expression_add,
    KHR_OT_expression_remove,
    KHR_OT_expression_key_add,
    KHR_OT_expression_key_remove,
    KHR_OT_suggest_arkit_expressions,
    KHR_PT_expressions,
    KHR_OT_suggest_vrm1_mapping,
    KHR_PT_expression_mapping,
    KHR_PT_skeleton_mapping,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
