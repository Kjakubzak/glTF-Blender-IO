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

# I3: KHR_character_expression + KHR_character_expression_morphtarget (declarative shape-key expressions).
# Each SHAPE_KEYS expression becomes a new two-key animation (t = 0 and t = 1 s). For every exported
# mesh node whose shape keys include a listed key name, it holds one complete weights channel in
# get_sk_exported order: the authored initial weights at t = 0 and those weights plus the listed
# weights at t = 1. Expression animations are placed after the other animations and before the
# reference poses.

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
        base = [float(k.value) for k in keys]
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
                if keys[i].value != 0.0:
                    ctx.warning('expression "{}": shape key "{}" on {} has value {:g} (not 0) at rest'.format(
                        expression.name, w.key_name, ob.name, keys[i].value))
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
    for expression in data.expressions:
        if expression.source != 'SHAPE_KEYS':
            continue
        channels, samplers = _morph_channels(expression, meshes, ctx)
        if not channels:
            continue
        animation = gltf2_io.Animation(channels=channels, extensions=None, extras=None, name=expression.name,
                                       samplers=samplers)
        animations.append(animation)
        ctx.expressions.append({'name': expression.name, 'animation': animation,
                                'morph': list(range(len(channels))), 'joint': []})


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
