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

# Authoring data for the KHR_character family. Registered with the add-on; only read when the
# exporter option "KHR_character" is enabled.

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty,
                       PointerProperty, StringProperty)


def _is_armature(_self, obj):
    return obj.type == 'ARMATURE'


class KHR_CharacterShapeKeyWeight(bpy.types.PropertyGroup):
    key_name: StringProperty(name='Shape Key', description='Shape key name, matched on every exported mesh')
    weight: FloatProperty(name='Weight', default=1.0, min=0.0, max=1.0)
    object: PointerProperty(name='Object', type=bpy.types.Object,
                            description='Restrict to this mesh object (empty: every mesh with the shape key)')


class KHR_CharacterSuppression(bpy.types.PropertyGroup):
    target: StringProperty(name='Target', description='Name of the suppressed expression')
    type: EnumProperty(name='Type', items=(('blend', 'Blend', ''), ('block', 'Block', ''),
                                           ('CUSTOM', 'Custom', 'Vendor-qualified custom type')), default='blend')
    custom_type: StringProperty(name='Custom Type')
    amount: FloatProperty(name='Amount', default=1.0, min=0.0, max=1.0)
    threshold: FloatProperty(name='Threshold', default=0.0, min=0.0, max=1.0)
    use_threshold: BoolProperty(name='Write Threshold', default=False)


class KHR_CharacterExpression(bpy.types.PropertyGroup):
    name: StringProperty(name='Name')
    source: EnumProperty(name='Source', items=(
        ('SHAPE_KEYS', 'Shape Keys', 'Morph-only expression built from shape-key weights'),
        ('ACTION', 'Action', 'Expression animation exported from an action (joints and/or shape keys)')),
        default='SHAPE_KEYS')
    shape_key_weights: CollectionProperty(type=KHR_CharacterShapeKeyWeight)
    action: PointerProperty(name='Action', type=bpy.types.Action)
    track_name: StringProperty(name='Animation Name',
                               description='Exported animation name, when it differs from the action name')
    allow_joints: StringProperty(name='Allowed Joints', description='Comma-separated bone names (empty: all)')
    allow_morphs: StringProperty(name='Allowed Shape Keys', description='Comma-separated shape keys (empty: all)')
    suppressions: CollectionProperty(type=KHR_CharacterSuppression)


class KHR_CharacterMappingSource(bpy.types.PropertyGroup):
    expression: StringProperty(name='Expression')
    weight: FloatProperty(name='Weight', default=1.0, min=0.0, max=1.0)


class KHR_CharacterMappingEntry(bpy.types.PropertyGroup):
    name: StringProperty(name='Input', description='Expression identifier of the mapping set vocabulary')
    sources: CollectionProperty(type=KHR_CharacterMappingSource)


class KHR_CharacterMappingSet(bpy.types.PropertyGroup):
    set_id: StringProperty(name='Mapping Set', default='vrm1_expressions')
    entries: CollectionProperty(type=KHR_CharacterMappingEntry)


class KHR_CharacterScene(bpy.types.PropertyGroup):
    armature: PointerProperty(name='Armature', type=bpy.types.Object, poll=_is_armature)
    expressions: CollectionProperty(type=KHR_CharacterExpression)
    active_expression: IntProperty(default=0)
    mapping_sets: CollectionProperty(type=KHR_CharacterMappingSet)
    active_mapping_set: IntProperty(default=0)


class KHR_CharacterRoleBone(bpy.types.PropertyGroup):
    role: StringProperty(name='Role')
    bone: StringProperty(name='Bone')


class KHR_CharacterSkeletonSet(bpy.types.PropertyGroup):
    set_id: StringProperty(name='Mapping Set', default='vrm1_humanoid')
    entries: CollectionProperty(type=KHR_CharacterRoleBone)


class KHR_CharacterSkeletonMapping(bpy.types.PropertyGroup):
    sets: CollectionProperty(type=KHR_CharacterSkeletonSet)
    active_set: IntProperty(default=0)


class KHR_CharacterReferencePose(bpy.types.PropertyGroup):
    is_reference: BoolProperty(name='Reference Pose', default=False,
                               description='Export this action as a KHR_character_reference_pose animation')
    pose_type: EnumProperty(name='Pose Type', items=(('t_pose', 'T-Pose', ''), ('a_pose', 'A-Pose', ''),
                                                     ('i_pose', 'I-Pose', ''), ('CUSTOM', 'Custom', '')),
                            default='t_pose')
    custom_pose_type: StringProperty(name='Custom Pose Type', description='Vendor-qualified label')


class KHR_CharacterCameraHint(bpy.types.PropertyGroup):
    enabled: BoolProperty(name='Camera Hint', default=False)
    role: StringProperty(name='Role', default='default_view')
    target: PointerProperty(name='Target', type=bpy.types.Object)
    label: StringProperty(name='Label')
    keep_core_camera: BoolProperty(name='Keep Core Camera', default=False,
                                   description='Also keep the camera on the node (node.camera)')
    source_aspect: FloatProperty(name='Source Aspect', default=0.0, min=0.0,
                                 description='Width/height of the camera this hint was made from (0: render aspect)')


class KHR_CharacterLookatTarget(bpy.types.PropertyGroup):
    enabled: BoolProperty(name='Look-at Target', default=False)
    hint: StringProperty(name='Hint')


class KHR_CharacterVisibilityHint(bpy.types.PropertyGroup):
    enabled: BoolProperty(name='Visibility Hint', default=False)
    roles: StringProperty(name='Roles', description='Comma-separated roles', default='third_person')
    label: StringProperty(name='Label')


class KHR_CharacterObjectHints(bpy.types.PropertyGroup):
    camera: PointerProperty(type=KHR_CharacterCameraHint)
    lookat: PointerProperty(type=KHR_CharacterLookatTarget)
    visibility: PointerProperty(type=KHR_CharacterVisibilityHint)


class KHR_CharacterPrimitiveHint(bpy.types.PropertyGroup):
    enabled: BoolProperty(name='Primitive Visibility Hint', default=False)
    roles: StringProperty(name='Roles', description='Comma-separated roles', default='third_person')
    label: StringProperty(name='Label')


classes = (
    KHR_CharacterShapeKeyWeight,
    KHR_CharacterSuppression,
    KHR_CharacterExpression,
    KHR_CharacterMappingSource,
    KHR_CharacterMappingEntry,
    KHR_CharacterMappingSet,
    KHR_CharacterScene,
    KHR_CharacterRoleBone,
    KHR_CharacterSkeletonSet,
    KHR_CharacterSkeletonMapping,
    KHR_CharacterReferencePose,
    KHR_CharacterCameraHint,
    KHR_CharacterLookatTarget,
    KHR_CharacterVisibilityHint,
    KHR_CharacterObjectHints,
    KHR_CharacterPrimitiveHint,
)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.khr_character = PointerProperty(type=KHR_CharacterScene)
    bpy.types.Object.khr_skeleton_mapping = PointerProperty(type=KHR_CharacterSkeletonMapping)
    bpy.types.Action.khr_reference_pose = PointerProperty(type=KHR_CharacterReferencePose)
    bpy.types.Object.khr_hints = PointerProperty(type=KHR_CharacterObjectHints)
    bpy.types.Material.khr_primitive_hint = PointerProperty(type=KHR_CharacterPrimitiveHint)


def unregister():
    del bpy.types.Material.khr_primitive_hint
    del bpy.types.Object.khr_hints
    del bpy.types.Action.khr_reference_pose
    del bpy.types.Object.khr_skeleton_mapping
    del bpy.types.Scene.khr_character
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
