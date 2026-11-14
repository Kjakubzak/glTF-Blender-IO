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

# KHR_character_expression with _morphtarget (I3) and _joint (I4).
# Each SHAPE_KEYS expression becomes a new two-key animation (t = 0 and t = 1 s). For every exported
# mesh node whose shape keys include a listed key name, it holds one complete weights channel in
# get_sk_exported order: the authored initial weights (node/mesh weights as exported, never the live
# shape-key values after the animation pass) at t = 0 and those weights plus the listed
# weights at t = 1. Expression animations are placed after the other animations and before the
# reference poses.

import math
import struct

import bpy

from ...com import khr_character as khr
from ...com.data_path import get_sk_exported
from ....io.com import constants
from ....io.com import gltf2_io
from ....io.com.gltf2_io_extensions import Extension
from ....io.exp.binary_data import BinaryData
from ..accessors import gather_accessor

DURATION = 1.0


def _scalar_accessor(values, ctx, bounds=False):
    data = BinaryData(struct.pack('<{}f'.format(len(values)), *values))
    lo, hi = ((min(values),), (max(values),)) if bounds else (None, None)
    # gather_accessor takes max before min
    return gather_accessor(data, constants.ComponentType.Float, len(values), hi, lo,
                           constants.DataType.Scalar, False, ctx.settings)


def pre_export(ctx):
    # Shape-key values before the core exporter samples animations: afterwards they hold whatever the last
    # exported track or action left behind.
    ctx.initial_key_values = {}
    for ob in bpy.context.scene.objects:
        if ob.type == 'MESH' and ob.data.shape_keys is not None:
            for k in ob.data.shape_keys.key_blocks:
                ctx.initial_key_values[(ob.name, k.name)] = float(k.value)


def _initial_weights(ob, node, keys, ctx):
    """Authored initial morph weights of a node: node.weights, else mesh.weights (both gathered before the
    animation pass), else the shape-key values captured in pre_export."""
    for weights in (node.weights, node.mesh.weights):
        if weights is not None and len(weights) == len(keys):
            return [float(v) for v in weights]
    values = getattr(ctx, 'initial_key_values', {})
    return [values.get((ob.name, k.name), 0.0) for k in keys]


def _mesh_objects(ctx):
    """(object, node, exported shape keys) for every exported mesh node with morph targets."""
    out = []
    for name in sorted(ctx.object_nodes):
        ob = bpy.data.objects.get(name)
        node = ctx.object_nodes[name]
        if ob is None or ob.type != 'MESH' or node.mesh is None or ob.data.shape_keys is None:
            continue
        keys = get_sk_exported(ob.data.shape_keys.key_blocks)
        targets = len(node.mesh.primitives[0].targets or []) if node.mesh.primitives else 0
        if not keys or targets != len(keys):
            continue
        out.append((ob, node, keys))
    return out


def _morph_channels(expression, meshes, ctx):
    """(channels, samplers) of one SHAPE_KEYS expression; reports unknown keys."""
    channels, samplers, matched = [], [], set()
    for ob, node, keys in meshes:
        names = [k.name for k in keys]
        base = _initial_weights(ob, node, keys, ctx)
        peak = list(base)
        touched = False
        for w in expression.shape_key_weights:
            if w.object is not None and w.object != ob:
                continue
            if w.key_name in names:
                i = names.index(w.key_name)
                peak[i] = base[i] + w.weight
                touched = True
                matched.add(w.key_name)
                if base[i] != 0.0:
                    ctx.warning('expression "{}": shape key "{}" on {} has initial weight {:g} (not 0)'.format(
                        expression.name, w.key_name, ob.name, base[i]))
        if not touched:
            continue
        sampler = gltf2_io.AnimationSampler(
            extensions=None, extras=None, interpolation='LINEAR',
            input=_scalar_accessor([0.0, DURATION], ctx, bounds=True),
            output=_scalar_accessor(base + peak, ctx))
        samplers.append(sampler)
        target = gltf2_io.AnimationChannelTarget(extensions=None, extras=None, node=node, path='weights')
        channels.append(gltf2_io.AnimationChannel(extensions=None, extras=None, sampler=len(samplers) - 1,
                                                  target=target))
    for w in expression.shape_key_weights:
        if w.key_name not in matched:
            ctx.error('expression', '"{}": shape key "{}" is not on any exported mesh with morph targets'.format(
                expression.name, w.key_name))
    return channels, samplers


def gltf(ctx, scenes, animations):
    data = ctx.scene_data
    ctx.expressions = []
    if not len(data.expressions):
        return
    meshes = _mesh_objects(ctx)
    clips = list(animations)
    consumed = []
    for expression in data.expressions:
        if expression.source == 'SHAPE_KEYS':
            channels, samplers = _morph_channels(expression, meshes, ctx)
            if not channels:
                continue
            animation = gltf2_io.Animation(channels=channels, extensions=None, extras=None,
                                           name=expression.name, samplers=samplers)
            joint, morph = [], list(range(len(channels)))
        else:
            result = _action_expression(expression, clips, ctx)
            if result is None:
                continue
            animation, source, joint, morph = result
            consumed.append(source)
        animations.append(animation)
        ctx.expressions.append({'name': expression.name, 'animation': animation, 'morph': morph, 'joint': joint})
    animations[:] = [a for a in animations if not any(a is c for c in consumed)]


# I4: ACTION expressions. The action is exported by the core exporter as an ordinary animation; the
# expression builds a new animation from it: channels outside the allow-lists are discarded (the
# discarded motion is reported), morph components outside the shape-key allow-list are held at their
# initial value, channels that are constant at their node's initial value are dropped (one is kept if
# all are), times are shifted to start at 0, and the channels are classified as joint (node TRS) or
# morph (weights). The source animation is removed from the clip list.

EPS = 1e-5  # float32 round trips through the exporter's matrices differ by ~1e-7
TRS_WIDTH = {'translation': 3, 'rotation': 4, 'scale': 3}


def _floats(accessor):
    data = accessor.buffer_view.data
    return list(struct.unpack('<{}f'.format(len(data) // 4), data))


def _width(target):
    if target.path == 'weights':
        return len(target.node.mesh.primitives[0].targets)
    return TRS_WIDTH[target.path]


def _initial(target):
    node = target.node
    if target.path == 'translation':
        return list(node.translation or (0.0, 0.0, 0.0))
    if target.path == 'rotation':
        return list(node.rotation or (0.0, 0.0, 0.0, 1.0))
    if target.path == 'scale':
        return list(node.scale or (1.0, 1.0, 1.0))
    n = _width(target)
    return list(node.weights or node.mesh.weights or [0.0] * n)


def _keys(sampler, width):
    """Key values (tangents skipped) as lists of width floats."""
    raw = _floats(sampler.output)
    cubic = sampler.interpolation == 'CUBICSPLINE'
    stride, offset = (3 * width, width) if cubic else (width, 0)
    return [raw[i * stride + offset:i * stride + offset + width] for i in range(sampler.input.count)]


def _distance(path, a, b):
    if path == 'rotation':
        dot = min(1.0, abs(sum(x * y for x, y in zip(a, b))))
        return math.degrees(2.0 * math.acos(dot))
    return max(abs(x - y) for x, y in zip(a, b))


def _same(path, a, b):
    if path == 'rotation' and sum(x * y for x, y in zip(a, b)) < 0.0:
        b = [-y for y in b]
    return all(abs(x - y) <= EPS for x, y in zip(a, b))


def _split(text):
    return {s.strip() for s in text.split(',') if s.strip()}


def _action_expression(expression, animations, ctx):
    """New animation and channel classification for one ACTION expression, or None."""
    if expression.action is None:
        ctx.error('expression', '"{}": no action'.format(expression.name))
        return None
    track = expression.track_name or expression.action.name
    source = next((a for a in animations if a.name == track), None)
    if source is None:
        ctx.error('expression', '"{}": action "{}" was not exported as an animation (export_animation_mode '
                  'ACTIONS exports each action)'.format(expression.name, track))
        return None
    bone_of = {id(node): bone for (_arm, bone), node in ctx.bone_nodes.items()}
    allow_joints, allow_morphs = _split(expression.allow_joints), _split(expression.allow_morphs)
    kept, discarded = [], []
    for channel in source.channels:
        target = channel.target
        sampler = source.samplers[channel.sampler]
        if target.node is None or (target.path not in TRS_WIDTH and target.path != 'weights'):
            discarded.append('{} (unsupported target)'.format(target.path))
            continue
        name = bone_of.get(id(target.node), target.node.name)
        width = _width(target)
        keys = _keys(sampler, width)
        initial = _initial(target)
        if target.path in TRS_WIDTH:
            if allow_joints and name not in allow_joints:
                if not all(_same(target.path, k, initial) for k in keys):
                    moved = max(_distance(target.path, k, initial) for k in keys)
                    discarded.append('{}.{} ({:.4g}{})'.format(name, target.path, moved,
                                                               ' deg' if target.path == 'rotation' else ''))
                continue
        else:
            ob = next((bpy.data.objects.get(n) for n, nd in ctx.object_nodes.items() if nd is target.node), None)
            key_names = [k.name for k in get_sk_exported(ob.data.shape_keys.key_blocks)] if ob else []
            if allow_morphs and len(key_names) == width:
                held = [i for i, n in enumerate(key_names) if n not in allow_morphs]
                if held:
                    moved = max(abs(k[i] - initial[i]) for k in keys for i in held)
                    if moved > EPS:
                        discarded.append('{} weights {} ({:.4g})'.format(
                            target.node.name, ','.join(key_names[i] for i in held), moved))
                    for k in keys:
                        for i in held:
                            k[i] = initial[i]
                    if sampler.interpolation == 'CUBICSPLINE':
                        ctx.warning('expression "{}": CUBICSPLINE weights resampled as LINEAR'.format(
                            expression.name))
                    sampler = None  # rebuilt below from keys
        constant = all(_same(target.path, k, initial) for k in keys)
        kept.append((channel, sampler, keys, constant))
    if discarded:
        ctx.warning('expression "{}": discarded motion outside the allow-lists: {}'.format(
            expression.name, '; '.join(discarded)))
    if not kept:
        ctx.error('expression', '"{}": no joint or morph channel in "{}"'.format(expression.name, track))
        return None
    moving = [k for k in kept if not k[3]] or kept[:1]
    t0 = min(_floats((s or source.samplers[c.sampler]).input)[0] for c, s, _k, _const in moving)
    channels, samplers, joint, morph = [], [], [], []
    for channel, sampler, keys, _constant in moving:
        original = source.samplers[channel.sampler]
        times = [t - t0 for t in _floats(original.input)]
        if sampler is not None and t0 <= EPS:
            new = sampler
        else:
            interpolation = 'LINEAR' if sampler is None else original.interpolation
            if sampler is None:
                output = _float_accessor([v for k in keys for v in k], channel.target, ctx)
            else:
                output = original.output
            new = gltf2_io.AnimationSampler(extensions=None, extras=None, interpolation=interpolation,
                                            input=_scalar_accessor(times, ctx, bounds=True), output=output)
        samplers.append(new)
        (joint if channel.target.path in TRS_WIDTH else morph).append(len(channels))
        channels.append(gltf2_io.AnimationChannel(extensions=None, extras=None, sampler=len(samplers) - 1,
                                                  target=channel.target))
    animation = gltf2_io.Animation(channels=channels, extensions=None, extras=None, name=expression.name,
                                   samplers=samplers)
    return animation, source, joint, morph


def _float_accessor(values, target, ctx):
    data = BinaryData(struct.pack('<{}f'.format(len(values)), *values))
    if target.path == 'weights':
        return gather_accessor(data, constants.ComponentType.Float, len(values), None, None,
                               constants.DataType.Scalar, False, ctx.settings)
    width = TRS_WIDTH[target.path]
    return gather_accessor(data, constants.ComponentType.Float, len(values) // width, None, None,
                           constants.DataType.Vec4 if width == 4 else constants.DataType.Vec3, False, ctx.settings)


def root(ctx, gltf_root):
    entries = []
    for e in getattr(ctx, 'expressions', []):
        extensions = {}
        if e['morph']:
            extensions[khr.EXPRESSION_MORPHTARGET] = {'channels': e['morph']}
            ctx.declare(khr.EXPRESSION_MORPHTARGET)
        if e['joint']:
            extensions[khr.EXPRESSION_JOINT] = {'channels': e['joint']}
            ctx.declare(khr.EXPRESSION_JOINT)
        entries.append({'name': e['name'], 'animation': e['animation'], 'extensions': extensions})
    if entries:
        gltf_root.extensions[khr.EXPRESSION] = Extension(khr.EXPRESSION, {'expressions': entries}, False)


def validate(ctx, gltf_root):
    seen = set()
    for expression in ctx.scene_data.expressions:
        if not expression.name:
            ctx.error('expression', 'an expression has no name')
        elif expression.name in seen:
            ctx.error('expression', 'duplicate expression name "{}"'.format(expression.name))
        seen.add(expression.name)
    # runs after traversal: samplers and accessors are referenced by index
    for e in getattr(ctx, 'expressions', []):
        animation = e['animation']
        for kind, indices, paths in (('joint', e['joint'], TRS_WIDTH), ('morph', e['morph'], ('weights',))):
            for i in indices:
                if animation.channels[i].target.path not in paths:
                    ctx.error('expression', '"{}": channel {} listed as {} targets {}'.format(
                        e['name'], i, kind, animation.channels[i].target.path))
        if set(e['joint']) & set(e['morph']):
            ctx.error('expression', '"{}": a channel is listed twice'.format(e['name']))
        for channel in animation.channels:
            sampler = animation.samplers[channel.sampler]
            accessor = gltf_root.accessors[sampler.input] if isinstance(sampler.input, int) else sampler.input
            if accessor.count < 2:
                ctx.error('expression', '"{}": a sampler has {} key (needs 2 or more)'.format(
                    e['name'], accessor.count))
