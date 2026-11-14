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

# I7: hint extensions. KHR_node_camera_hint on exported camera objects (the camera moves from
# node.camera into the hint's advisory camera unless keep_core_camera is set), KHR_node_lookat_target
# (may be {}), KHR_node_visibility_hint on objects and KHR_mesh_primitive_visibility_hint on the
# primitives of materials with a hint. Hints are never listed in extensionsRequired.
# S40: every exported hint camera with a source aspect must match the render aspect of the scene it is
# exported in (1e-3), and all exported hint cameras must share one source aspect. Checked while the nodes
# are gathered (so selection, visibility, collection filters and every exported scene are respected);
# strict mode aborts in gather_gltf_extensions_hook, before anything is written.

import re

import bpy

from ...com import khr_character as khr
from ....io.com.gltf2_io_extensions import Extension

STANDARD_CAMERA_ROLES = ('default_view', 'detail', 'first_person', 'framing_view', 'full_body', 'orbit_view',
                         'portrait', 'third_person')
VENDOR_VALUE = re.compile(r'^[A-Z0-9]+_[A-Za-z0-9_]+$')
ASPECT_TOLERANCE = 1e-3


def render_aspect(scene):
    r = scene.render
    return (r.resolution_x * r.pixel_aspect_x) / (r.resolution_y * r.pixel_aspect_y)


def _roles(text):
    out = []
    for role in (s.strip() for s in text.split(',')):
        if role and role not in out:
            out.append(role)
    return out


def pre_export(ctx):
    ctx.pending_targets = []
    ctx.hint_aspects = []


def _check_aspect(ctx, ob):
    """S40 for one exported hint camera, against the scene being gathered (the exporter makes each exported
    scene current in turn); only cameras that are actually exported get here."""
    aspect = ob.khr_hints.camera.source_aspect
    if aspect <= 0.0:
        return
    scene = bpy.context.scene
    render = render_aspect(scene)
    ctx.hint_aspects.append((ob.name, aspect))
    if abs(aspect - render) > ASPECT_TOLERANCE:
        ctx.error('hint-aspect', 'hint camera {} has source aspect {:.4g} but scene {} renders at {:.4g} ({}x{}); '
                  'set the scene resolution to the hint aspect'.format(
                      ob.name, aspect, scene.name, render, scene.render.resolution_x, scene.render.resolution_y))


def _set(node, name, data):
    if node.extensions is None:
        node.extensions = {}
    node.extensions[name] = Extension(name, data, False)
    return data


def node(ctx, node, ob):
    hints = ob.khr_hints
    if hints.camera.enabled:
        if ob.type != 'CAMERA':
            ctx.warning('{}: camera hint on a {} object is ignored'.format(ob.name, ob.type.lower()))
        else:
            _check_aspect(ctx, ob)
            role = hints.camera.role.strip()
            if not role:
                ctx.error('camera-hint', '{}: empty role'.format(ob.name))
            elif role not in STANDARD_CAMERA_ROLES and not VENDOR_VALUE.match(role):
                ctx.warning('{}: camera role "{}" is neither standard nor vendor-qualified'.format(ob.name, role))
            data = {'role': role}
            if node.camera is not None:
                data['camera'] = node.camera
                if not hints.camera.keep_core_camera:
                    node.camera = None
            if hints.camera.label:
                data['label'] = hints.camera.label
            _set(node, khr.CAMERA_HINT, data)
            if hints.camera.target is not None:
                target = hints.camera.target
                bone = hints.camera.target_bone if target.type == 'ARMATURE' else ''
                ctx.pending_targets.append((ob.name, data, target.name, bone))
    if hints.lookat.enabled:
        _set(node, khr.LOOKAT_TARGET, {'hint': hints.lookat.hint} if hints.lookat.hint else {})
    if hints.visibility.enabled:
        roles = _roles(hints.visibility.roles)
        if not roles:
            ctx.error('visibility-hint', '{}: no visibility role'.format(ob.name))
        else:
            data = {'roles': roles}
            if hints.visibility.label:
                data['label'] = hints.visibility.label
            _set(node, khr.NODE_VISIBILITY_HINT, data)


def mesh(ctx, mesh, blender_mesh, ob, materials):
    by_name = {m.name: m for m in bpy.data.materials if m.khr_primitive_hint.enabled}
    if not by_name:
        return
    for primitive in mesh.primitives:
        material = by_name.get(getattr(primitive.material, 'name', None))
        if material is None:
            continue
        hint = material.khr_primitive_hint
        roles = _roles(hint.roles)
        if not roles:
            ctx.error('visibility-hint', 'material {}: no visibility role'.format(material.name))
            continue
        data = {'roles': roles}
        if hint.label:
            data['label'] = hint.label
        _set(primitive, khr.PRIMITIVE_VISIBILITY_HINT, data)


def gltf(ctx, scenes, animations):
    aspects = getattr(ctx, 'hint_aspects', [])
    values = sorted(set(round(a, 6) for _n, a in aspects))
    if values and values[-1] - values[0] > ASPECT_TOLERANCE:
        ctx.error('hint-aspect', 'exported hint cameras have mixed source aspects: {}'.format(
            ', '.join('{} {:.4g}'.format(n, a) for n, a in sorted(set(aspects)))))
    for camera_name, data, target, bone in getattr(ctx, 'pending_targets', []):
        if bone:
            node = ctx.bone_nodes.get((target, bone))
            if node is None:
                ctx.error('camera-hint', '{}: target bone {}/{} is not exported'.format(camera_name, target, bone))
            else:
                data['targetNode'] = node
        elif target == camera_name:
            ctx.error('camera-hint', '{}: targetNode must be a different node'.format(camera_name))
        elif target in ctx.object_nodes:
            data['targetNode'] = ctx.object_nodes[target]
        else:
            ctx.error('camera-hint', '{}: target {} is not exported'.format(camera_name, target))


def validate(ctx, gltf_root):
    for ob in bpy.context.scene.objects:
        hint = ob.khr_hints.camera
        if ob.type == 'CAMERA' and hint.enabled and ob.name not in ctx.object_nodes:
            ctx.warning('camera hint on {} not exported (export_cameras is off or the camera is filtered '
                        'out)'.format(ob.name))
        if ob.type == 'CAMERA' and hint.enabled and hint.keep_core_camera and ob.name in ctx.object_nodes:
            ctx.warning('{}: hint camera kept on node.camera (keep_core_camera)'.format(ob.name))
