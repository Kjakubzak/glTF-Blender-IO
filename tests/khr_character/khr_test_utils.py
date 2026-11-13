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

# Helpers for the KHR_character unit tests: scene reset, GLB export and reading. Generated data only.

import json
import os
import struct
import tempfile

import bpy

import numpy as np

COMPONENT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
WIDTH = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}
TMP = tempfile.mkdtemp(prefix='khr_character_tests_')


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    for coll in (bpy.data.meshes, bpy.data.armatures, bpy.data.cameras, bpy.data.lights, bpy.data.actions,
                 bpy.data.materials):
        for d in list(coll):
            coll.remove(d)
    sc = bpy.context.scene.khr_character
    sc.expressions.clear()
    sc.mapping_sets.clear()
    sc.armature = None


def export(name, **kwargs):
    path = os.path.join(TMP, name + '.glb')
    if os.path.exists(path):
        os.remove(path)
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', **kwargs)
    return path


class Glb:
    def __init__(self, path):
        with open(path, 'rb') as f:
            data = f.read()
        self.bytes = data
        off = 12
        self.json, self.bin = None, b''
        while off + 8 <= len(data):
            n, t = struct.unpack_from('<II', data, off)
            chunk = data[off + 8:off + 8 + n]
            if t == 0x4E4F534A:
                self.json = json.loads(chunk)
            elif t == 0x004E4942:
                self.bin = chunk
            off += 8 + n

    def accessor(self, index):
        a = self.json['accessors'][index]
        v = self.json['bufferViews'][a['bufferView']]
        dt = np.dtype(COMPONENT[a['componentType']])
        width = WIDTH[a['type']]
        start = v.get('byteOffset', 0) + a.get('byteOffset', 0)
        stride = v.get('byteStride', dt.itemsize * width)
        out = np.empty((a['count'], width), dtype=dt)
        for i in range(a['count']):
            out[i] = np.frombuffer(self.bin, dtype=dt, count=width, offset=start + i * stride)
        return out

    def node_index(self, name):
        for i, n in enumerate(self.json.get('nodes', [])):
            if n.get('name') == name:
                return i
        raise KeyError(name)

    def animation(self, name):
        for a in self.json.get('animations', []):
            if a.get('name') == name:
                return a
        raise KeyError(name)


def quat_matrix(q):
    x, y, z, w = q
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def pose_values(g, animation):
    """{(node, path): first output value} of an animation."""
    out = {}
    for ch in animation['channels']:
        s = animation['samplers'][ch['sampler']]
        out[(ch['target']['node'], ch['target']['path'])] = g.accessor(s['output'])[0]
    return out


def world_positions(g, animation=None):
    """Global translation of every node, with an animation's first key applied (reference pose)."""
    pose = pose_values(g, animation) if animation else {}
    nodes = g.json['nodes']
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get('children', []):
            parent[c] = i
    local = []
    for i, n in enumerate(nodes):
        if 'matrix' in n:
            local.append(np.array(n['matrix'], dtype=float).reshape(4, 4).T)
            continue
        t = pose.get((i, 'translation'), n.get('translation', [0, 0, 0]))
        r = pose.get((i, 'rotation'), n.get('rotation', [0, 0, 0, 1]))
        s = pose.get((i, 'scale'), n.get('scale', [1, 1, 1]))
        m = np.eye(4)
        m[:3, :3] = quat_matrix(r) @ np.diag(s)
        m[:3, 3] = t
        local.append(m)
    world = {}

    def get(i):
        if i not in world:
            world[i] = (get(parent[i]) if i in parent else np.eye(4)) @ local[i]
        return world[i]
    return {nodes[i].get('name'): get(i)[:3, 3] for i in range(len(nodes))}


def angle_deg(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    c = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    return float(np.degrees(np.arccos(max(-1.0, min(1.0, c)))))


def shape_key_mesh(name, keys, location=(0.0, 0.0, 0.0)):
    """A one-quad mesh object with a Basis and one shape key per name (each moves one vertex)."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-0.1, 0, -0.1), (0.1, 0, -0.1), (0.1, 0, 0.1), (-0.1, 0, 0.1)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new(name, me)
    ob.location = location
    bpy.context.scene.collection.objects.link(ob)
    ob.shape_key_add(name='Basis')
    for i, key in enumerate(keys):
        k = ob.shape_key_add(name=key)
        k.data[i % 4].co.y += 0.01 * (i + 1)
        k.value = 0.0
    return ob
