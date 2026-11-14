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

# KHR_character family support shared by export and import (draft extensions,
# KhronosGroup glTF pull request 2512 at 7ab5368a).

KHR_CHARACTER = 'KHR_character'
SKELETON_MAPPING = 'KHR_character_skeleton_mapping'
REFERENCE_POSE = 'KHR_character_reference_pose'
EXPRESSION = 'KHR_character_expression'
EXPRESSION_MORPHTARGET = 'KHR_character_expression_morphtarget'
EXPRESSION_JOINT = 'KHR_character_expression_joint'
EXPRESSION_MAPPING = 'KHR_character_expression_mapping'
EXPRESSION_SUPPRESSION = 'KHR_character_expression_suppression'
CAMERA_HINT = 'KHR_node_camera_hint'
LOOKAT_TARGET = 'KHR_node_lookat_target'
NODE_VISIBILITY_HINT = 'KHR_node_visibility_hint'
PRIMITIVE_VISIBILITY_HINT = 'KHR_mesh_primitive_visibility_hint'

# Extensions that must never be listed in extensionsRequired
HINT_EXTENSIONS = (CAMERA_HINT, NODE_VISIBILITY_HINT, PRIMITIVE_VISIBILITY_HINT)

# Extensions whose empty object ({}) is meaningful
EMPTY_ALLOWED = (KHR_CHARACTER, LOOKAT_TARGET)

# Blender properties registered by this package. They are authoring data and must never be
# exported as extras (see blender/com/extras.py BLACK_LIST).
PROPERTY_NAMES = (
    'khr_character',
    'khr_skeleton_mapping',
    'khr_reference_pose',
    'khr_hints',
    'khr_primitive_hint',
)
