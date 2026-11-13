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

# Capture Expression (I4 authoring): evaluates the armature and its shape keys at a neutral and a peak
# state (two frames of an action, or two values of a control property) and keys the difference as a
# two-key LINEAR action (neutral at frame 0, peak at frame = scene fps, so the expression lasts 1 s).
# Bone poses are read from the evaluated pose (constraints and drivers included) and converted to
# local channels. An optional look direction rotates the eye bones about a head-frame axis on top of
# the peak (S41): up = head - neck (limb_dir of the neck), left = left eye - right eye, both in
# armature space and independent of the bone axes.
# Shape-key changes are keyed in a second slot of the same action, so the exporter merges them into the
# armature's animation of that action.

import math

import bpy

LOOK = {'LEFT': ('up', 1.0), 'RIGHT': ('up', -1.0), 'UP': ('left', -1.0), 'DOWN': ('left', 1.0)}


def head_frame(ob, mapping):
    """(up, left, forward) unit vectors in armature space from the vrm1_humanoid mapping."""
    from mathutils import Vector
    pose = ob.pose.bones
    head = pose[mapping['head']]
    if 'neck' in mapping:
        up = head.head - pose[mapping['neck']].head
    elif head.parent is not None:
        up = head.head - head.parent.head
    else:
        up = Vector((0.0, 0.0, 1.0))
    up.normalize()
    if 'leftEye' in mapping and 'rightEye' in mapping:
        left = pose[mapping['leftEye']].head - pose[mapping['rightEye']].head
    else:
        left = Vector((1.0, 0.0, 0.0))
    left = (left - up * left.dot(up)).normalized()
    return up, left, left.cross(up)


def set_control(ob, path, value):
    """Set ob's property at path: 'prop', 'a.b', '["key"]' or 'pose.bones["c"]["key"]' (never eval)."""
    if path.endswith('"]') and '["' in path:
        owner_path, key = path[:-2].rsplit('["', 1)
        owner = ob.path_resolve(owner_path) if owner_path else ob
        owner[key] = value
    else:
        owner_path, _dot, attr = path.rpartition('.')
        owner = ob.path_resolve(owner_path) if owner_path else ob
        setattr(owner, attr, value)
    ob.update_tag()  # ID-property writes do not tag the depsgraph; drivers reading them must re-run


def shape_key_objects(ob):
    out = []
    for m in bpy.context.scene.objects:
        if m.type != 'MESH' or m.data.shape_keys is None:
            continue
        if m.parent == ob or any(md.type == 'ARMATURE' and md.object == ob for md in m.modifiers):
            out.append(m)
    return out


def evaluate(ob, meshes):
    """{bone: local matrix} and {(mesh, key): value} of the evaluated state."""
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ob_eval = ob.evaluated_get(dg)
    pose = {}
    for pb in ob_eval.pose.bones:
        pose[pb.name] = ob_eval.convert_space(pose_bone=pb, matrix=pb.matrix, from_space='POSE', to_space='LOCAL')
    keys = {}
    for m in meshes:
        key_eval = m.data.shape_keys.evaluated_get(dg)
        for k in key_eval.key_blocks[1:]:
            keys[(m.name, k.name)] = k.value
    return pose, keys, ob_eval


def look_rotation(ob_eval, ob, mapping, pose, direction, angle_deg):
    """Rotate the eye bones of pose (local matrices) by angle_deg about the head-frame axis."""
    from mathutils import Matrix
    up, left, _forward = head_frame(ob, mapping)
    axis_name, sign = LOOK[direction]
    rot = Matrix.Rotation(math.radians(angle_deg) * sign, 4, up if axis_name == 'up' else left)
    for role in ('leftEye', 'rightEye'):
        if role not in mapping:
            continue
        pb = ob_eval.pose.bones[mapping[role]]
        arm = ob_eval.convert_space(pose_bone=pb, matrix=pose[pb.name], from_space='LOCAL', to_space='POSE')
        head = arm.to_translation()
        arm = Matrix.Translation(head) @ rot @ Matrix.Translation(-head) @ arm
        pose[pb.name] = ob_eval.convert_space(pose_bone=pb, matrix=arm, from_space='POSE', to_space='LOCAL')


def _changed(a, b, eps=1e-6):
    return any(abs(x - y) > eps for ra, rb in zip(a, b) for x, y in zip(ra, rb))


def _key_pose(ob, pb, matrix, frame):
    pb.matrix_basis = matrix
    pb.keyframe_insert('location', frame=frame)
    if pb.rotation_mode == 'QUATERNION':
        pb.keyframe_insert('rotation_quaternion', frame=frame)
    elif pb.rotation_mode == 'AXIS_ANGLE':
        pb.keyframe_insert('rotation_axis_angle', frame=frame)
    else:
        pb.keyframe_insert('rotation_euler', frame=frame)
    pb.keyframe_insert('scale', frame=frame)


def capture_expression(ob, name, mapping, source='ACTION', action=None, neutral_frame=0, peak_frame=24,
                       control_path='', neutral_value=0.0, peak_value=1.0, look='NONE', look_angle=12.0):
    """Create a two-key action for expression name and an ACTION entry in Scene.khr_character.expressions.

    Returns (action, warnings).
    """
    from mathutils import Matrix
    scene = bpy.context.scene
    meshes = shape_key_objects(ob)
    ad = ob.animation_data_create()
    saved_action, saved_frame = ad.action, scene.frame_current
    saved_control = ob.path_resolve(control_path) if source == 'CONTROL' and control_path else None
    warnings = []

    def state(frame=None, value=None):
        if source == 'ACTION':
            ad.action = action
            scene.frame_set(frame)
        else:
            set_control(ob, control_path, value)
            scene.frame_set(scene.frame_current)
        return evaluate(ob, meshes)

    neutral_pose, neutral_keys, _ = state(neutral_frame, neutral_value)
    peak_pose, peak_keys, ob_eval = state(peak_frame, peak_value)
    if look != 'NONE':
        look_rotation(ob_eval, ob, mapping, peak_pose, look, look_angle)
    for bone, m in neutral_pose.items():
        if _changed(m, Matrix.Identity(4), 1e-4):
            warnings.append('bone {} is not at rest at the neutral state'.format(bone))
            break

    # restore the scene before keying
    if source == 'ACTION':
        ad.action = saved_action
    elif saved_control is not None:
        set_control(ob, control_path, saved_control)
    scene.frame_set(saved_frame)

    out = bpy.data.actions.new(name)
    out.use_fake_user = True
    previous = ad.action
    ad.action = out
    end = int(round(scene.render.fps / scene.render.fps_base))
    moved = [b for b in neutral_pose if _changed(neutral_pose[b], peak_pose[b])]
    for b in moved:
        pb = ob.pose.bones[b]
        _key_pose(ob, pb, neutral_pose[b], 0)
        _key_pose(ob, pb, peak_pose[b], end)
    for pb in ob.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    ad.action = previous
    for m in meshes:
        changed = [k for k in m.data.shape_keys.key_blocks[1:]
                   if abs(neutral_keys[(m.name, k.name)] - peak_keys[(m.name, k.name)]) > 1e-6]
        if not changed:
            continue
        kad = m.data.shape_keys.animation_data_create()
        saved_key_action = kad.action
        kad.action = out
        for k in changed:
            rest = k.value
            for frame, values in ((0, neutral_keys), (end, peak_keys)):
                k.value = values[(m.name, k.name)]
                k.keyframe_insert('value', frame=frame)
            k.value = rest
        slot = kad.action_slot
        kad.action = saved_key_action
        # ACTIONS-mode export only picks up shape-key actions that are active or in an NLA track; a muted
        # track with one unmuted strip exports the slot without changing the scene's evaluation
        track = kad.nla_tracks.new()
        track.name = 'khr_expression:' + name
        strip = track.strips.new(name, 0, out)
        if slot is not None:
            strip.action_slot = slot
        track.mute = True
    _make_linear(out)
    if not moved and not any(True for _ in _fcurves(out)):
        warnings.append('neutral and peak states are identical')
    entry = scene.khr_character.expressions.add()
    entry.name = name
    entry.source = 'ACTION'
    entry.action = out
    bpy.context.view_layer.update()
    return out, warnings


def _fcurves(action):
    if hasattr(action, 'layers'):
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    yield from bag.fcurves
    else:
        yield from action.fcurves


def _make_linear(action):
    for fc in _fcurves(action):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
