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

# I2: KHR_character_reference_pose. Actions flagged with khr_reference_pose are exported as ordinary
# animations; in gather_gltf_hook each matching animation is sliced to its first key with NEW
# one-key accessors (shared cached accessors are never modified), keeps only node TRS channels, and
# is tagged and moved to the end of the animation list.

import struct

import bpy

from ...com import khr_character as khr
from ....io.com import constants
from ....io.com import gltf2_io
from ....io.com.gltf2_io_extensions import Extension
from ....io.exp.binary_data import BinaryData
from ..accessors import gather_accessor

TRS = ('translation', 'rotation', 'scale')
POSE_ORDER = {'t_pose': 0, 'a_pose': 1, 'i_pose': 2}


def flagged_actions():
    out = {}
    for action in bpy.data.actions:
        rp = action.khr_reference_pose
        if rp.is_reference:
            out[action.name] = rp.custom_pose_type if rp.pose_type == 'CUSTOM' else rp.pose_type
    return out


def pose_label(animation):
    ext = (animation.extensions or {}).get(khr.REFERENCE_POSE)
    if ext is None:
        return None
    # after the exporter's traversal the Extension object has been replaced by its dict
    return (ext.extension if isinstance(ext, Extension) else ext)['poseType']


def _first_key(sampler, ctx):
    width = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4}[sampler.output.type]
    t0 = struct.unpack('<f', sampler.input.buffer_view.data[:4])[0]
    data = sampler.output.buffer_view.data
    offset = 4 * width if sampler.interpolation == 'CUBICSPLINE' else 0  # skip the in-tangent
    value = data[offset:offset + 4 * width]
    interpolation = 'STEP' if sampler.interpolation == 'STEP' else 'LINEAR'
    return gltf2_io.AnimationSampler(
        extensions=None, extras=None, interpolation=interpolation,
        input=gather_accessor(BinaryData(sampler.input.buffer_view.data[:4]), constants.ComponentType.Float, 1,
                              (t0,), (t0,), constants.DataType.Scalar, False, ctx.settings),
        output=gather_accessor(BinaryData(value), constants.ComponentType.Float, 1, None, None,
                               sampler.output.type, False, ctx.settings))


def slice_to_reference_pose(animation, label, ctx):
    channels, samplers = [], []
    for channel in animation.channels:
        target = channel.target
        if target.node is None or target.path not in TRS or (target.extensions or {}):
            continue
        samplers.append(_first_key(animation.samplers[channel.sampler], ctx))
        channels.append(gltf2_io.AnimationChannel(extensions=channel.extensions, extras=channel.extras,
                                                  sampler=len(samplers) - 1, target=target))
    animation.channels = channels
    animation.samplers = samplers
    if animation.extensions is None:
        animation.extensions = {}
    animation.extensions[khr.REFERENCE_POSE] = Extension(khr.REFERENCE_POSE, {'poseType': label}, False)


def gltf(ctx, scenes, animations):
    flagged = flagged_actions()
    if not flagged:
        return
    found = set()
    for animation in animations:
        if animation.name in flagged:
            slice_to_reference_pose(animation, flagged[animation.name], ctx)
            found.add(animation.name)
            if not animation.channels:
                ctx.error('reference-pose', '{}: no node translation, rotation or scale channel'.format(
                    animation.name))
    for name in sorted(set(flagged) - found):
        ctx.warning('reference pose action "{}" was not exported as an animation'.format(name))
    ordered = sorted(animations, key=lambda a: (pose_label(a) is not None,
                                                POSE_ORDER.get(pose_label(a), 3) if pose_label(a) else 0))
    animations[:] = ordered


def validate(ctx, gltf_root):
    # runs after traversal: samplers and accessors are referenced by index
    def resolve(ref, table):
        return table[ref] if isinstance(ref, int) else ref

    for animation in ctx.animations:
        label = pose_label(animation)
        if label is None:
            continue
        if not label:
            ctx.error('reference-pose', '{}: empty poseType'.format(animation.name))
        for channel in animation.channels:
            sampler = animation.samplers[channel.sampler]
            count = resolve(sampler.input, gltf_root.accessors).count
            if count != 1:
                ctx.error('reference-pose', '{}: sampler input count {} (must be 1)'.format(animation.name, count))
            if sampler.interpolation not in ('LINEAR', 'STEP', None):
                ctx.error('reference-pose', '{}: interpolation {}'.format(animation.name, sampler.interpolation))
