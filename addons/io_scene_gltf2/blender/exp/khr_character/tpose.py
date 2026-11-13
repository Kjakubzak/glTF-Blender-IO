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

# Make T-pose (limb_dir convention) for an armature with a vrm1_humanoid mapping.

import bpy


ARM_CHAINS = {
    'UpperArm': 'LowerArm', 'LowerArm': 'Hand', 'Hand': 'MiddleProximal',
    'ThumbMetacarpal': 'ThumbProximal', 'ThumbProximal': 'ThumbDistal', 'ThumbDistal': None,
}
for _f in ('Index', 'Middle', 'Ring', 'Little'):
    ARM_CHAINS.update({_f + 'Proximal': _f + 'Intermediate', _f + 'Intermediate': _f + 'Distal', _f + 'Distal': None})
LEG_CHAINS = {'UpperLeg': 'LowerLeg', 'LowerLeg': 'Foot'}
ARM_ORDER = ['UpperArm', 'LowerArm', 'Hand', 'ThumbMetacarpal', 'ThumbProximal', 'ThumbDistal'] + [
    f + s for f in ('Index', 'Middle', 'Ring', 'Little') for s in ('Proximal', 'Intermediate', 'Distal')]


def make_t_pose(ob, mapping, action_name, include_thumb=True):
    """Pose ob into a T-pose from its rest pose and key it as a one-frame reference-pose action.

    Limb direction of a role = head of its mapped child role - its own head (limb_dir); a leaf uses its
    bone direction. Arms and fingers are aligned with +X (left) / -X (right), the thumb 45 degrees
    between that axis and the character's front (-Y), legs with -Z. Assumes the armature object
    faces -Y with +Z up. Returns the new action.
    """
    from mathutils import Matrix, Vector

    bpy.context.view_layer.objects.active = ob
    for pb in ob.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()

    def limb_dir(role):
        pb = ob.pose.bones[mapping[role]]
        side = 'left' if role.startswith('left') else 'right'
        base = role[len(side):]
        child = ARM_CHAINS.get(base) if base in ARM_CHAINS else LEG_CHAINS.get(base)
        if child and side + child in mapping:
            d = ob.pose.bones[mapping[side + child]].head - pb.head
        elif base == 'Hand' and side + 'IndexProximal' in mapping:
            d = ob.pose.bones[mapping[side + 'IndexProximal']].head - pb.head
        else:
            d = pb.tail - pb.head
        return d

    def align(role, target):
        if role not in mapping:
            return
        pb = ob.pose.bones[mapping[role]]
        d = limb_dir(role)
        if d.length < 1e-9:
            return
        rot = d.normalized().rotation_difference(target.normalized()).to_matrix().to_4x4()
        head = pb.head.copy()
        pb.matrix = Matrix.Translation(head) @ rot @ Matrix.Translation(-head) @ pb.matrix
        bpy.context.view_layer.update()

    for side, sx in (('left', 1.0), ('right', -1.0)):
        for base in ARM_ORDER:
            if base.startswith('Thumb'):
                if not include_thumb:
                    continue
                target = Vector((sx, -1.0, 0.0))
            else:
                target = Vector((sx, 0.0, 0.0))
            align(side + base, target)
        for base in ('UpperLeg', 'LowerLeg'):
            align(side + base, Vector((0.0, 0.0, -1.0)))

    return key_reference_pose(ob, action_name, 't_pose', from_rest=False)


def key_reference_pose(ob, action_name, pose_type, from_rest=True):
    """Key every pose bone of ob at scene.frame_start into a new one-frame action flagged as a
    reference pose of pose_type, then leave the armature in rest pose with its previous action."""
    from mathutils import Matrix

    if from_rest:
        for pb in ob.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
    action = bpy.data.actions.new(action_name)
    action.use_fake_user = True
    ad = ob.animation_data_create()
    previous = ad.action
    ad.action = action
    frame = bpy.context.scene.frame_start
    rotation = {'QUATERNION': 'rotation_quaternion', 'AXIS_ANGLE': 'rotation_axis_angle'}
    for pb in ob.pose.bones:
        for path in ('location', rotation.get(pb.rotation_mode, 'rotation_euler'), 'scale'):
            pb.keyframe_insert(path, frame=frame)
    action.khr_reference_pose.is_reference = True
    if pose_type in ('t_pose', 'a_pose', 'i_pose'):
        action.khr_reference_pose.pose_type = pose_type
    else:
        action.khr_reference_pose.pose_type = 'CUSTOM'
        action.khr_reference_pose.custom_pose_type = pose_type
    ad.action = previous
    for pb in ob.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    return action
