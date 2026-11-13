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

# Synthetic humanoid skeletons in four naming conventions, as (name, parent, head) in armature
# space (+Z up, front -Y, character left +X), plus the expected vrm1_humanoid mapping of each.
# Pure Python; scene generators and unit tests build armatures from them.

FINGER_X = (0.76, 0.80, 0.83)


def _limbs(fmt, chest, hips, fingers, finger_segments, shoulder=True):
    """Arms and legs for both sides; fmt maps (part, side, index) to a bone name."""
    bones = []
    for side, sx in (('L', 1), ('R', -1)):
        parent = chest
        if shoulder:
            bones.append((fmt('shoulder', side, 0), chest, (sx * 0.05, 0, 1.45)))
            parent = fmt('shoulder', side, 0)
        bones.append((fmt('upper_arm', side, 0), parent, (sx * 0.18, 0, 1.45)))
        bones.append((fmt('forearm', side, 0), fmt('upper_arm', side, 0), (sx * 0.45, 0, 1.45)))
        bones.append((fmt('hand', side, 0), fmt('forearm', side, 0), (sx * 0.70, 0, 1.45)))
        for fi, finger in enumerate(fingers):
            prev = fmt('hand', side, 0)
            for k in range(finger_segments):
                name = fmt(finger, side, k + 1)
                y = -0.03 + 0.02 * fi
                bones.append((name, prev, (sx * (FINGER_X[min(k, 2)] + 0.03 * (k // 3)), y, 1.45)))
                prev = name
        bones.append((fmt('thigh', side, 0), hips, (sx * 0.1, 0, 0.95)))
        bones.append((fmt('shin', side, 0), fmt('thigh', side, 0), (sx * 0.1, 0, 0.5)))
        bones.append((fmt('foot', side, 0), fmt('shin', side, 0), (sx * 0.1, 0, 0.08)))
        bones.append((fmt('toe', side, 0), fmt('foot', side, 0), (sx * 0.1, -0.12, 0.02)))
    return bones


def rigify():
    def fmt(part, side, i):
        names = {'shoulder': 'shoulder', 'upper_arm': 'upper_arm', 'forearm': 'forearm', 'hand': 'hand',
                 'thigh': 'thigh', 'shin': 'shin', 'foot': 'foot', 'toe': 'toe', 'thumb': 'thumb',
                 'index': 'f_index', 'middle': 'f_middle', 'ring': 'f_ring', 'pinky': 'f_pinky'}
        if i:
            return 'DEF-{}.{:02d}.{}'.format(names[part], i, side)
        return 'DEF-{}.{}'.format(names[part], side)
    spine = [('DEF-spine', None, (0, 0, 1.0)), ('DEF-spine.001', 'DEF-spine', (0, 0, 1.1)),
             ('DEF-spine.002', 'DEF-spine.001', (0, 0, 1.25)), ('DEF-spine.003', 'DEF-spine.002', (0, 0, 1.4)),
             ('DEF-spine.004', 'DEF-spine.003', (0, 0, 1.55)), ('DEF-spine.005', 'DEF-spine.004', (0, 0, 1.6)),
             ('DEF-spine.006', 'DEF-spine.005', (0, 0, 1.7))]
    bones = spine + _limbs(fmt, 'DEF-spine.003', 'DEF-spine', ('thumb', 'index', 'middle', 'ring', 'pinky'), 3)
    # Rigify DEF arms and legs are split in two segments; the second ones are not humanoid roles.
    out = []
    for name, parent, head in bones:
        out.append((name, parent, head))
    extra = []
    for side, sx in (('L', 1), ('R', -1)):
        for part, x in (('upper_arm', 0.3), ('forearm', 0.58)):
            seg = 'DEF-{}.{}.001'.format(part, side)
            base = 'DEF-{}.{}'.format(part, side)
            extra.append((seg, base, (sx * x, 0, 1.45)))
    out += extra
    nxt = {'DEF-forearm.L': 'DEF-upper_arm.L.001', 'DEF-forearm.R': 'DEF-upper_arm.R.001',
           'DEF-hand.L': 'DEF-forearm.L.001', 'DEF-hand.R': 'DEF-forearm.R.001'}
    out = [(n, nxt.get(n, p), h) for n, p, h in out]
    expected = {'hips': 'DEF-spine', 'spine': 'DEF-spine.001', 'chest': 'DEF-spine.002',
                'upperChest': 'DEF-spine.003', 'neck': 'DEF-spine.004', 'head': 'DEF-spine.006'}
    for side, s in (('L', 'left'), ('R', 'right')):
        expected.update({s + 'Shoulder': 'DEF-shoulder.' + side, s + 'UpperArm': 'DEF-upper_arm.' + side,
                         s + 'LowerArm': 'DEF-forearm.' + side, s + 'Hand': 'DEF-hand.' + side,
                         s + 'UpperLeg': 'DEF-thigh.' + side, s + 'LowerLeg': 'DEF-shin.' + side,
                         s + 'Foot': 'DEF-foot.' + side, s + 'Toes': 'DEF-toe.' + side,
                         s + 'ThumbMetacarpal': 'DEF-thumb.01.' + side, s + 'ThumbProximal': 'DEF-thumb.02.' + side,
                         s + 'ThumbDistal': 'DEF-thumb.03.' + side})
        for f, n in (('Index', 'f_index'), ('Middle', 'f_middle'), ('Ring', 'f_ring'), ('Little', 'f_pinky')):
            expected.update({s + f + 'Proximal': 'DEF-{}.01.{}'.format(n, side),
                             s + f + 'Intermediate': 'DEF-{}.02.{}'.format(n, side),
                             s + f + 'Distal': 'DEF-{}.03.{}'.format(n, side)})
    return out, expected


def mixamo():
    p = 'mixamorig:'

    def fmt(part, side, i):
        s = 'Left' if side == 'L' else 'Right'
        names = {'shoulder': 'Shoulder', 'upper_arm': 'Arm', 'forearm': 'ForeArm', 'hand': 'Hand', 'thigh': 'UpLeg',
                 'shin': 'Leg', 'foot': 'Foot', 'toe': 'ToeBase', 'thumb': 'HandThumb', 'index': 'HandIndex',
                 'middle': 'HandMiddle', 'ring': 'HandRing', 'pinky': 'HandPinky'}
        return p + s + names[part] + (str(i) if i else '')
    spine = [(p + 'Hips', None, (0, 0, 1.0)), (p + 'Spine', p + 'Hips', (0, 0, 1.1)),
             (p + 'Spine1', p + 'Spine', (0, 0, 1.25)), (p + 'Spine2', p + 'Spine1', (0, 0, 1.4)),
             (p + 'Neck', p + 'Spine2', (0, 0, 1.55)), (p + 'Head', p + 'Neck', (0, 0, 1.65)),
             (p + 'HeadTop_End', p + 'Head', (0, 0, 1.85))]
    bones = spine + _limbs(fmt, p + 'Spine2', p + 'Hips', ('thumb', 'index', 'middle', 'ring', 'pinky'), 4)
    for side, sx in (('Left', 1), ('Right', -1)):
        bones.append((p + side + 'Toe_End', p + side + 'ToeBase', (sx * 0.1, -0.2, 0.02)))
    expected = {'hips': p + 'Hips', 'spine': p + 'Spine', 'chest': p + 'Spine1', 'upperChest': p + 'Spine2',
                'neck': p + 'Neck', 'head': p + 'Head'}
    for side, s in (('Left', 'left'), ('Right', 'right')):
        expected.update({s + 'Shoulder': p + side + 'Shoulder', s + 'UpperArm': p + side + 'Arm',
                         s + 'LowerArm': p + side + 'ForeArm', s + 'Hand': p + side + 'Hand',
                         s + 'UpperLeg': p + side + 'UpLeg', s + 'LowerLeg': p + side + 'Leg',
                         s + 'Foot': p + side + 'Foot', s + 'Toes': p + side + 'ToeBase',
                         s + 'ThumbMetacarpal': p + side + 'HandThumb1', s + 'ThumbProximal': p + side + 'HandThumb2',
                         s + 'ThumbDistal': p + side + 'HandThumb3'})
        for f, n in (('Index', 'Index'), ('Middle', 'Middle'), ('Ring', 'Ring'), ('Little', 'Pinky')):
            expected.update({s + f + 'Proximal': p + side + 'Hand' + n + '1',
                             s + f + 'Intermediate': p + side + 'Hand' + n + '2',
                             s + f + 'Distal': p + side + 'Hand' + n + '3'})
    return bones, expected


def maya_jnt():
    def fmt(part, side, i):
        names = {'shoulder': 'Clavicle', 'upper_arm': 'UpperArm', 'forearm': 'Elbow', 'hand': 'Wrist',
                 'thigh': 'Thigh', 'shin': 'Knee', 'foot': 'Ankle', 'toe': 'Ball', 'thumb': 'Thumb',
                 'index': 'Index', 'middle': 'Middle', 'ring': 'Ring', 'pinky': 'Pinky'}
        return '{}_{}{}_jnt'.format(side, names[part], i if i else '')
    spine = [('Hips_jnt', None, (0, 0, 1.0)), ('Spine1_jnt', 'Hips_jnt', (0, 0, 1.1)),
             ('Spine2_jnt', 'Spine1_jnt', (0, 0, 1.25)), ('Chest_jnt', 'Spine2_jnt', (0, 0, 1.4)),
             ('Neck_jnt', 'Chest_jnt', (0, 0, 1.55)), ('Head_jnt', 'Neck_jnt', (0, 0, 1.65))]
    bones = spine + _limbs(fmt, 'Chest_jnt', 'Hips_jnt', ('thumb', 'index', 'middle', 'ring', 'pinky'), 3)
    expected = {'hips': 'Hips_jnt', 'spine': 'Spine1_jnt', 'chest': 'Spine2_jnt', 'upperChest': 'Chest_jnt',
                'neck': 'Neck_jnt', 'head': 'Head_jnt'}
    for side, s in (('L', 'left'), ('R', 'right')):
        expected.update({s + 'Shoulder': side + '_Clavicle_jnt', s + 'UpperArm': side + '_UpperArm_jnt',
                         s + 'LowerArm': side + '_Elbow_jnt', s + 'Hand': side + '_Wrist_jnt',
                         s + 'UpperLeg': side + '_Thigh_jnt', s + 'LowerLeg': side + '_Knee_jnt',
                         s + 'Foot': side + '_Ankle_jnt', s + 'Toes': side + '_Ball_jnt',
                         s + 'ThumbMetacarpal': side + '_Thumb1_jnt', s + 'ThumbProximal': side + '_Thumb2_jnt',
                         s + 'ThumbDistal': side + '_Thumb3_jnt'})
        for f, n in (('Index', 'Index'), ('Middle', 'Middle'), ('Ring', 'Ring'), ('Little', 'Pinky')):
            expected.update({s + f + 'Proximal': '{}_{}1_jnt'.format(side, n),
                             s + f + 'Intermediate': '{}_{}2_jnt'.format(side, n),
                             s + f + 'Distal': '{}_{}3_jnt'.format(side, n)})
    return bones, expected


def cartoon3finger():
    def fmt(part, side, i):
        names = {'upper_arm': 'arm_upper', 'forearm': 'arm_lower', 'hand': 'hand', 'thigh': 'leg_upper',
                 'shin': 'leg_lower', 'foot': 'foot', 'toe': 'toe', 'thumb': 'thumb', 'index': 'index',
                 'middle': 'middle'}
        return '{}{}.{}'.format(names[part], '_{:02d}'.format(i) if i else '', side.lower())
    spine = [('pelvis', None, (0, 0, 1.0)), ('spine', 'pelvis', (0, 0, 1.15)), ('chest', 'spine', (0, 0, 1.35)),
             ('neck', 'chest', (0, 0, 1.55)), ('head', 'neck', (0, 0, 1.65))]
    bones = spine + _limbs(fmt, 'chest', 'pelvis', ('thumb', 'index', 'middle'), 2, shoulder=False)
    expected = {'hips': 'pelvis', 'spine': 'spine', 'chest': 'chest', 'neck': 'neck', 'head': 'head'}
    for side, s in (('l', 'left'), ('r', 'right')):
        expected.update({s + 'UpperArm': 'arm_upper.' + side, s + 'LowerArm': 'arm_lower.' + side,
                         s + 'Hand': 'hand.' + side, s + 'UpperLeg': 'leg_upper.' + side,
                         s + 'LowerLeg': 'leg_lower.' + side, s + 'Foot': 'foot.' + side, s + 'Toes': 'toe.' + side,
                         s + 'ThumbProximal': 'thumb_01.' + side, s + 'ThumbDistal': 'thumb_02.' + side,
                         s + 'IndexProximal': 'index_01.' + side, s + 'IndexDistal': 'index_02.' + side,
                         s + 'MiddleProximal': 'middle_01.' + side, s + 'MiddleDistal': 'middle_02.' + side})
    return bones, expected


RIGS = {'rigify': rigify, 'mixamo': mixamo, 'maya_jnt': maya_jnt, 'cartoon3finger': cartoon3finger}


def build_armature(bones, name='Armature'):
    """Create an armature object from (name, parent, head) rows; each tail points at its first child."""
    import bpy
    arm = bpy.data.armatures.new(name)
    ob = bpy.data.objects.new(name, arm)
    bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode='EDIT')
    heads = {n: h for n, _p, h in bones}
    first_child = {}
    for n, p, _h in bones:
        if p is not None and p not in first_child:
            first_child[p] = n
    for n, p, h in bones:
        b = arm.edit_bones.new(n)
        b.head = h
        c = first_child.get(n)
        t = heads[c] if c else (h[0], h[1], h[2] + 0.05)
        if sum((a - b_) ** 2 for a, b_ in zip(t, h)) < 1e-8:
            t = (h[0], h[1], h[2] + 0.05)
        b.tail = t
    for n, p, _h in bones:
        if p is not None:
            arm.edit_bones[n].parent = arm.edit_bones[p]
    bpy.ops.object.mode_set(mode='OBJECT')
    return ob
