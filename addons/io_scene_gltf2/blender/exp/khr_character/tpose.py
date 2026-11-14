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

# Make T-pose (limb_dir convention, character frame from the rig) for an armature with a vrm1_humanoid mapping.

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


SPINE_CHAIN = ('hips', 'spine', 'chest', 'upperChest', 'neck', 'head')
LEAN_LIMIT_DEG = 20.0


def character_frame(ob, mapping, report=None):
    """(up, left, forward) unit vectors in armature space, from the rig itself: up = head - hips, left =
    leftUpperLeg - rightUpperLeg (else the upper arms, else the shoulders) made orthogonal to up, forward =
    left x up. Missing roles fall back to the object's world frame (+Z up, +X left). Problems (a mapped left
    side that the feet place on the character's right, a leaning rest spine or neck) go to report."""
    import math
    from mathutils import Vector
    report = report if report is not None else []
    to_arm = ob.matrix_world.to_3x3().inverted()
    head = {r: ob.pose.bones[b].head.copy() for r, b in mapping.items() if b in ob.pose.bones}
    world_up = (to_arm @ Vector((0.0, 0.0, 1.0))).normalized()
    up = head['head'] - head['hips'] if 'head' in head and 'hips' in head else world_up.copy()
    if up.length < 1e-9:
        up = world_up.copy()
    up.normalize()
    for a, b in (('leftUpperLeg', 'rightUpperLeg'), ('leftUpperArm', 'rightUpperArm'),
                 ('leftShoulder', 'rightShoulder')):
        if a in head and b in head and (head[a] - head[b]).length > 1e-9:
            lr = head[a] - head[b]
            break
    else:
        lr = to_arm @ Vector((1.0, 0.0, 0.0))
    left = (lr - up * lr.dot(up)).normalized()
    forward = left.cross(up)
    toes = [head[s + 'Toes'] - head[s + 'Foot'] for s in ('left', 'right') if s + 'Toes' in head and s + 'Foot' in head]
    if toes and sum(toes, Vector()).dot(forward) < 0.0:
        report.append('the mapped left side is on the character\'s right (the toes point backwards in the '
                      'frame derived from the mapping); check the left/right roles')
    if math.degrees(up.angle(world_up)) > LEAN_LIMIT_DEG:
        report.append('the rig is not upright in world space (hips to head {:.0f} degrees from world up); the '
                      'T-pose uses the rig\'s own up'.format(math.degrees(up.angle(world_up))))
    chain = [r for r in SPINE_CHAIN if r in head]
    for a, b in zip(chain, chain[1:]):
        d = head[b] - head[a]
        if d.length > 1e-9 and math.degrees(d.angle(up)) > LEAN_LIMIT_DEG:
            report.append('rest {} -> {} leans {:.0f} degrees from the character\'s up; the T-pose keeps the torso, '
                          'head, shoulders and feet at rest'.format(a, b, math.degrees(d.angle(up))))
    return up, left, forward


def make_t_pose(ob, mapping, action_name, include_thumb=True, report=None):
    """Pose the limbs of ob into a T-pose from its rest pose and key it as a one-frame reference-pose action.

    Limbs only: torso, head, shoulders and feet keep the rest pose. Limb direction of a role (limb_dir) =
    head of its mapped child role - its own head; a role without a mapped child uses the head of its only
    child bone (e.g. an unmapped fingertip), or with several children the child whose head lies most nearly
    along the parent-to-bone direction, and a bone without children its bone direction. Targets are in the
    character frame derived from the rig (character_frame): arms and fingers along left / -left, thumbs 45
    degrees between that axis and forward, upper and lower legs along -up. Warnings go to report. Returns
    the new action (an earlier t_pose action of this armature is superseded, see key_reference_pose).
    """
    from mathutils import Matrix

    bpy.context.view_layer.objects.active = ob
    for pb in ob.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    up, left, forward = character_frame(ob, mapping, report)

    def limb_dir(role):
        pb = ob.pose.bones[mapping[role]]
        side = 'left' if role.startswith('left') else 'right'
        base = role[len(side):]
        child = ARM_CHAINS.get(base) if base in ARM_CHAINS else LEG_CHAINS.get(base)
        if child and side + child in mapping:
            return ob.pose.bones[mapping[side + child]].head - pb.head
        if base == 'Hand' and side + 'IndexProximal' in mapping:
            return ob.pose.bones[mapping[side + 'IndexProximal']].head - pb.head
        if len(pb.children) == 1:
            # unmapped tip bone (e.g. a fingertip): its head, since the bone axis need not follow the limb
            return pb.children[0].head - pb.head
        if pb.children and pb.parent is not None and (pb.head - pb.parent.head).length > 1e-9:
            along = (pb.head - pb.parent.head).normalized()
            kids = [c for c in pb.children if (c.head - pb.head).length > 1e-9]
            if kids:
                best = max(kids, key=lambda c: (c.head - pb.head).normalized().dot(along))
                return best.head - pb.head
        return pb.tail - pb.head

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
                target = left * sx + forward
            else:
                target = left * sx
            align(side + base, target)
        for base in ('UpperLeg', 'LowerLeg'):
            align(side + base, -up)

    return key_reference_pose(ob, action_name, 't_pose', from_rest=False, report=report)


def _action_bones(action):
    """Pose-bone names animated by an action (layered or legacy)."""
    import re
    curves = []
    if hasattr(action, 'layers'):
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    curves.extend(bag.fcurves)
    else:
        curves = list(action.fcurves)
    return {m.group(1) for fc in curves for m in [re.match(r'pose\.bones\["(.+?)"\]', fc.data_path)] if m}


def pose_label(action):
    rp = action.khr_reference_pose
    return rp.custom_pose_type if rp.pose_type == 'CUSTOM' else rp.pose_type


def key_reference_pose(ob, action_name, pose_type, from_rest=True, report=None):
    """Key every pose bone of ob at scene.frame_start into a new one-frame action flagged as a
    reference pose of pose_type, then leave the armature in rest pose with its previous action.

    A flagged action of the same pose type that animates this armature's bones is superseded: unflagged,
    renamed with '.superseded' and its fake user cleared, so a re-run replaces it."""
    from mathutils import Matrix

    bones = set(ob.pose.bones.keys())
    for old in list(bpy.data.actions):
        if old.khr_reference_pose.is_reference and pose_label(old) == pose_type and _action_bones(old) & bones:
            old.khr_reference_pose.is_reference = False
            old.use_fake_user = False
            old.name = old.name + '.superseded'
            if report is not None:
                report.append('superseded reference pose action ' + old.name)
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
