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

# Expression-name suggestions for shape keys (no Blender dependency).

ARKIT_52 = (
    'eyeBlinkLeft', 'eyeLookDownLeft', 'eyeLookInLeft', 'eyeLookOutLeft', 'eyeLookUpLeft', 'eyeSquintLeft',
    'eyeWideLeft', 'eyeBlinkRight', 'eyeLookDownRight', 'eyeLookInRight', 'eyeLookOutRight', 'eyeLookUpRight',
    'eyeSquintRight', 'eyeWideRight', 'jawForward', 'jawLeft', 'jawRight', 'jawOpen', 'mouthClose',
    'mouthFunnel', 'mouthPucker', 'mouthLeft', 'mouthRight', 'mouthSmileLeft', 'mouthSmileRight',
    'mouthFrownLeft', 'mouthFrownRight', 'mouthDimpleLeft', 'mouthDimpleRight', 'mouthStretchLeft',
    'mouthStretchRight', 'mouthRollLower', 'mouthRollUpper', 'mouthShrugLower', 'mouthShrugUpper',
    'mouthPressLeft', 'mouthPressRight', 'mouthLowerDownLeft', 'mouthLowerDownRight', 'mouthUpperUpLeft',
    'mouthUpperUpRight', 'browDownLeft', 'browDownRight', 'browInnerUp', 'browOuterUpLeft', 'browOuterUpRight',
    'cheekPuff', 'cheekSquintLeft', 'cheekSquintRight', 'noseSneerLeft', 'noseSneerRight', 'tongueOut',
)


def _norm(name):
    return ''.join(c for c in name.lower() if c.isalnum())


def suggest_arkit(key_names):
    """[(expression name, shape key name)] for the ARKit blend-shape names found among key_names.

    Matching ignores case and non-alphanumeric characters and accepts a prefix ending in '.', ':' or
    '_' (e.g. 'face.jawOpen'); the first matching key wins. Result in ARKIT_52 order.
    """
    by_norm = {}
    for k in key_names:
        for candidate in (k, k.rsplit('.', 1)[-1], k.rsplit(':', 1)[-1], k.rsplit('_', 1)[-1]):
            by_norm.setdefault(_norm(candidate), k)
    return [(name, by_norm[_norm(name)]) for name in ARKIT_52 if _norm(name) in by_norm]
