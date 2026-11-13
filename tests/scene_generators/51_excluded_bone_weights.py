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

# Generates tests/scenes/51_excluded_bone_weights.blend from generated data only:
#   blender -b --factory-startup --python tests/scene_generators/51_excluded_bone_weights.py -- OUT.blend [--redistribute]
# Armature: non-deforming root > b0 > b1 > (non-deforming helper, deforming twist).
# Bottom ring: b0 = 1. Top ring: every other vertex b1 0.5 / helper 0.3 / twist 0.2,
# the others helper = 1 only. The saved export settings use Export Deforming Bones Only,
# and with --redistribute also Redistribute Excluded Weights.

import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]
redistribute = "--redistribute" in argv

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)

arm = bpy.data.armatures.new("Armature")
rig = bpy.data.objects.new("Armature", arm)
bpy.context.scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
for name, head, tail, parent, deform in (
        ("root", (0, 0, 0), (0, 0.3, 0), None, False),
        ("b0", (0, 0, 0), (0, 0, 1), "root", True),
        ("b1", (0, 0, 1), (0, 0, 2), "b0", True),
        ("helper", (0.3, 0, 1.5), (0.3, 0, 2), "b1", False),
        ("twist", (0, 0, 1), (0, 0, 1.5), "b1", True)):
    bone = arm.edit_bones.new(name)
    bone.head = head
    bone.tail = tail
    bone.parent = arm.edit_bones[parent] if parent else None
    bone.use_deform = deform
bpy.ops.object.mode_set(mode="OBJECT")

bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.2, depth=2.0, location=(0, 0, 1))
mesh = bpy.context.active_object
mesh.name = "Body"
bpy.ops.object.transform_apply(location=True)
mesh.parent = rig
mesh.modifiers.new("Armature", "ARMATURE").object = rig
groups = {name: mesh.vertex_groups.new(name=name) for name in ("b0", "b1", "helper", "twist")}
top = [v for v in mesh.data.vertices if v.co.z > 1.0]
for v in mesh.data.vertices:
    if v.co.z <= 1.0:
        groups["b0"].add([v.index], 1.0, "REPLACE")
for i, v in enumerate(top):
    if i % 2 == 0:
        groups["b1"].add([v.index], 0.5, "REPLACE")
        groups["helper"].add([v.index], 0.3, "REPLACE")
        groups["twist"].add([v.index], 0.2, "REPLACE")
    else:
        groups["helper"].add([v.index], 1.0, "REPLACE")

settings = {"export_def_bones": True}
if redistribute:
    settings["export_redistribute_excluded_weights"] = True
bpy.context.scene["glTF2ExportSettings"] = settings
# Write only the scene and its dependencies: no window manager or file browser state.
bpy.data.libraries.write(out, {bpy.context.scene}, path_remap="NONE", fake_user=False, compress=False)
