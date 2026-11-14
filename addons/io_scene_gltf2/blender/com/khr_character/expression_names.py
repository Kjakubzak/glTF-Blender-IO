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

# Expression-name suggestions: ARKit names for shape keys, vrm1_expressions mappings (no Blender dependency).

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


VRM1_EXPRESSIONS = (
    'happy', 'angry', 'sad', 'relaxed', 'surprised', 'aa', 'ih', 'ou', 'ee', 'oh', 'blink', 'blinkLeft',
    'blinkRight', 'lookUp', 'lookDown', 'lookLeft', 'lookRight', 'neutral',
)

# Suggested vrm1_expressions inputs in terms of ARKit-named expressions: {input: [(expression, weight)]}.
# Character left/right as in ARKit (eyeBlinkLeft closes the character's left eye).
VRM1_FROM_ARKIT = {
    'happy': [('mouthSmileLeft', 1.0), ('mouthSmileRight', 1.0), ('cheekSquintLeft', 0.5),
              ('cheekSquintRight', 0.5)],
    'angry': [('browDownLeft', 1.0), ('browDownRight', 1.0), ('noseSneerLeft', 0.5), ('noseSneerRight', 0.5)],
    'sad': [('mouthFrownLeft', 1.0), ('mouthFrownRight', 1.0), ('browInnerUp', 1.0)],
    'relaxed': [('mouthSmileLeft', 0.5), ('mouthSmileRight', 0.5)],
    'surprised': [('browInnerUp', 1.0), ('browOuterUpLeft', 1.0), ('browOuterUpRight', 1.0),
                  ('eyeWideLeft', 1.0), ('eyeWideRight', 1.0), ('jawOpen', 0.3)],
    'aa': [('jawOpen', 1.0)],
    'ih': [('mouthStretchLeft', 0.5), ('mouthStretchRight', 0.5), ('jawOpen', 0.2)],
    'ou': [('mouthPucker', 1.0), ('jawOpen', 0.2)],
    'ee': [('mouthStretchLeft', 1.0), ('mouthStretchRight', 1.0)],
    'oh': [('mouthFunnel', 1.0), ('jawOpen', 0.4)],
    'blink': [('eyeBlinkLeft', 1.0), ('eyeBlinkRight', 1.0)],
    'blinkLeft': [('eyeBlinkLeft', 1.0)],
    'blinkRight': [('eyeBlinkRight', 1.0)],
    'lookUp': [('eyeLookUpLeft', 1.0), ('eyeLookUpRight', 1.0)],
    'lookDown': [('eyeLookDownLeft', 1.0), ('eyeLookDownRight', 1.0)],
    'lookLeft': [('eyeLookOutLeft', 1.0), ('eyeLookInRight', 1.0)],
    'lookRight': [('eyeLookInLeft', 1.0), ('eyeLookOutRight', 1.0)],
}


def suggest_vrm1(expression_names):
    """{input: [(expression, weight)]} for vrm1_expressions from existing expression names.

    An expression named exactly like a VRM preset maps 1:1; otherwise the ARKit table is used with the
    expressions that exist. Inputs without any existing expression are left out.
    """
    names = set(expression_names)
    out = {}
    for preset in VRM1_EXPRESSIONS:
        if preset in names:
            out[preset] = [(preset, 1.0)]
            continue
        sources = [(e, w) for e, w in VRM1_FROM_ARKIT.get(preset, []) if e in names]
        if sources:
            out[preset] = sources
    return out
