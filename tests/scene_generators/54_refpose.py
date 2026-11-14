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

# Generates tests/scenes/54_refpose.blend from generated data only (needs this add-on enabled):
#   blender -b --factory-startup --addons io_scene_gltf2 --python tests/scene_generators/54_refpose.py -- OUT.blend
# A synthetic mixamo-style skeleton built in A-pose with bone axes perpendicular to the limbs, mapped by
# the auto-mapper; Make T-Pose and Capture Reference Pose (a_pose, from rest) create the reference-pose
# actions, and a two-key clip action is added. The saved export settings enable the KHR_character
# package and export each action as an animation.

import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "khr_character"))
import rigs  # noqa: E402

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob)
bones, expected = rigs.mixamo()
arm = rigs.build_armature(rigs.a_pose(bones, expected), tail_mode='perpendicular')
bpy.context.view_layer.objects.active = arm
assert bpy.ops.khr_character.auto_map_skeleton('EXEC_DEFAULT') == {'FINISHED'}
assert bpy.ops.khr_character.make_t_pose('EXEC_DEFAULT') == {'FINISHED'}
assert bpy.ops.khr_character.capture_reference_pose('EXEC_DEFAULT', pose_type='a_pose', from_rest=True) == {'FINISHED'}

clip = bpy.data.actions.new('clip')
clip.use_fake_user = True
arm.animation_data_create().action = clip
head = arm.pose.bones[expected['head']]
for frame, w, z in ((1, 1.0, 0.0), (10, 0.9689, 0.2474)):
    head.rotation_quaternion = (w, 0.0, 0.0, z)
    head.keyframe_insert('rotation_quaternion', frame=frame)
head.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
arm.animation_data.action = None

bpy.context.scene["glTF2ExportSettings"] = {"export_khr_character": True, "export_animation_mode": "ACTIONS"}
# Write only the scene, its dependencies and the actions: no window manager or file browser state.
bpy.data.libraries.write(out, {bpy.context.scene, *bpy.data.actions}, path_remap="NONE", fake_user=True,
                         compress=False)
