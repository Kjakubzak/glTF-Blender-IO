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

# Automatic vrm1_humanoid role mapping for an armature, without Blender dependencies.
# Input: bones as (name, parent_name or None, head) in armature space (Blender: +Z up, character
# front -Y, character left +X). Steps: name tokens (common conventions), topology for the spine
# chain, neck and head, side from tokens or head x, finger segments by depth; then validation
# (required roles, unique bones, ancestry order). The result is all-or-nothing.

import json
import os
import re

_VOCAB = None

SIDE_TOKENS = {'l': 'left', 'left': 'left', 'lf': 'left', 'lft': 'left',
               'r': 'right', 'right': 'right', 'rt': 'right', 'rgt': 'right'}
SKIP_TOKENS = {'twist', 'roll', 'bend', 'helper', 'end', 'tip', 'nub', 'ik', 'fk', 'ctrl', 'ctl', 'pole', 'mch',
               'target', 'tgt', 'null', 'top', 'headtop', 'corrective', 'pv'}
PREFIXES = ('mixamorig', 'def-', 'def_', 'org-', 'bip001', 'bip01', 'j_bip_', 'cc_base_')
SUFFIXES = ('_jnt', '_joint', '_bn', '_def', '_skin')
FINGERS = {'thumb': 'Thumb', 'index': 'Index', 'middle': 'Middle', 'ring': 'Ring', 'pinky': 'Little',
           'little': 'Little'}


def vocabulary():
    global _VOCAB
    if _VOCAB is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vocab', 'vrm1_humanoid.json')
        with open(path, encoding='utf-8') as f:
            _VOCAB = json.load(f)
    return _VOCAB


def tokens(name):
    n = re.split(r'[:|]', name)[-1]
    low = n.lower()
    for p in PREFIXES:
        if low.startswith(p):
            n = n[len(p):]
            low = low[len(p):]
    for s in SUFFIXES:
        if low.endswith(s):
            n = n[:-len(s)]
            low = low[:-len(s)]
    n = re.sub(r'([a-z])([A-Z])', r'\1 \2', n)
    n = re.sub(r'([A-Za-z])([0-9])', r'\1 \2', n)
    n = re.sub(r'([0-9])([A-Za-z])', r'\1 \2', n)
    return [t for t in re.split(r'[\s._\-]+', n.lower()) if t]


def classify(name):
    """(base, side, segment) from a bone name; base None when unknown or a helper bone."""
    toks = tokens(name)
    if any(t in SKIP_TOKENS for t in toks):
        return None, None, None
    side = None
    rest = []
    for t in toks:
        if t in SIDE_TOKENS and side is None:
            side = SIDE_TOKENS[t]
        else:
            rest.append(t)
    digits = [int(t) for t in rest if t.isdigit()]
    words = [t for t in rest if not t.isdigit()]
    w = set(words)
    joined = ''.join(words)
    seg = digits[-1] if digits else None
    for key, finger in FINGERS.items():
        if key in w or joined.startswith('hand' + key) or joined.startswith(key):
            return 'finger:' + finger, side, seg
    if w & {'clavicle', 'shoulder', 'collar'}:
        return 'Shoulder', side, seg
    if 'forearm' in w or ('fore' in w and 'arm' in w) or ('lower' in w and 'arm' in w) or 'lowerarm' in w \
            or 'elbow' in w:
        return 'LowerArm', side, seg
    if 'upperarm' in w or ('upper' in w and 'arm' in w) or 'humerus' in w or (w == {'arm'}):
        return 'UpperArm', side, seg
    if w & {'hand', 'wrist'}:
        return 'Hand', side, seg
    if w & {'thigh', 'upleg', 'femur', 'upperleg'} or ('up' in w and 'leg' in w) or ('upper' in w and 'leg' in w):
        return 'UpperLeg', side, seg
    if w & {'calf', 'shin', 'knee', 'lowerleg'} or ('lower' in w and 'leg' in w) or (w == {'leg'}):
        return 'LowerLeg', side, seg
    if w & {'foot', 'ankle'}:
        return 'Foot', side, seg
    if w & {'toe', 'toes', 'toebase', 'ball'}:
        return 'Toes', side, seg
    if w & {'eye'}:
        return 'Eye', side, seg
    if 'hip' in w and side is not None:
        return 'UpperLeg', side, seg
    if w & {'hips', 'hip', 'pelvis'}:
        return 'hips', None, seg
    if 'neck' in w:
        return 'neck', None, seg
    if 'head' in w:
        return 'head', None, seg
    if 'jaw' in w:
        return 'jaw', None, seg
    if w & {'upperchest'} or ('upper' in w and 'chest' in w):
        return 'upperChest', None, seg
    if w & {'chest', 'ribcage', 'thorax'}:
        return 'chest', None, seg
    if w & {'spine', 'torso', 'abdomen', 'waist'}:
        return 'spine', None, seg
    return None, side, seg


class Tree:
    def __init__(self, bones):
        self.parent = {n: p for n, p, _h in bones}
        self.head = {n: tuple(h) for n, _p, h in bones}
        self.order = [n for n, _p, _h in bones]
        self.children = {n: [] for n in self.order}
        for n, p, _h in bones:
            if p in self.children:
                self.children[p].append(n)

    def ancestors(self, n):
        out = []
        p = self.parent.get(n)
        while p is not None:
            out.append(p)
            p = self.parent.get(p)
        return out

    def depth(self, n):
        return len(self.ancestors(n))

    def lca(self, names):
        names = [n for n in names if n]
        if not names:
            return None
        common = [names[0]] + self.ancestors(names[0])
        for n in names[1:]:
            chain = set([n] + self.ancestors(n))
            common = [c for c in common if c in chain]
        return common[0] if common else None

    def path(self, top, bottom):
        """Bones from just below top down to bottom (inclusive), or None if top is not an ancestor."""
        chain = [bottom]
        for a in self.ancestors(bottom):
            if a == top:
                return list(reversed(chain))
            chain.append(a)
        return None


def auto_map(bones):
    """Return (mapping {role: bone}, problems [str]). mapping is empty when any problem is found."""
    tree = Tree(bones)
    cand = {}
    for n in tree.order:
        base, side, seg = classify(n)
        if base is None:
            continue
        if base[0].isupper() or base.startswith('finger:'):
            if side is None:
                x = tree.head[n][0]
                side = 'left' if x > 1e-6 else 'right' if x < -1e-6 else None
            if side is None:
                continue
        cand.setdefault((base, side), []).append((n, seg))
    m = {}

    def pick(base, side):
        c = cand.get((base, side))
        if c:
            return min(c, key=lambda e: (tree.depth(e[0]), tree.order.index(e[0])))[0]
        return None

    for s in ('left', 'right'):
        for base in ('Shoulder', 'UpperArm', 'LowerArm', 'Hand', 'UpperLeg', 'LowerLeg', 'Foot', 'Toes', 'Eye'):
            b = pick(base, s)
            if b:
                m[s + base] = b
    legs = [m.get('leftUpperLeg'), m.get('rightUpperLeg')]
    hips = pick('hips', None)
    if hips is None or not all(l and hips in tree.ancestors(l) for l in legs):
        hips = tree.lca(legs)
    if hips:
        m['hips'] = hips
    arm_roots = [m.get(s + 'Shoulder') or m.get(s + 'UpperArm') for s in ('left', 'right')]
    arm_root = tree.lca(arm_roots)
    if arm_root and arm_root in arm_roots:
        arm_root = tree.parent.get(arm_root)
    if hips and arm_root:
        chain = tree.path(hips, arm_root) or []
        if len(chain) == 1:
            m['spine'] = chain[0]
        elif len(chain) == 2:
            m['spine'], m['chest'] = chain
        elif len(chain) >= 3:
            m['spine'], m['chest'], m['upperChest'] = chain[0], chain[-2], chain[-1]
        neck_named, head_named = pick('neck', None), pick('head', None)

        def usable(b):
            return not any(t in SKIP_TOKENS for t in tokens(b))

        up = [c for c in tree.children.get(arm_root, []) if c not in arm_roots and usable(c)
              and (classify(c)[0] or 'x') in ('x', 'neck', 'head', 'spine', 'chest', 'upperChest')]
        chain_up = []
        n = up[0] if len(up) == 1 else None
        while n is not None:
            chain_up.append(n)
            kids = [k for k in tree.children.get(n, []) if usable(k)]
            n = kids[0] if len(kids) == 1 else None
        if head_named and arm_root in tree.ancestors(head_named):
            m['head'] = head_named
            if neck_named and neck_named in tree.ancestors(head_named):
                m['neck'] = neck_named
            else:
                path = tree.path(arm_root, head_named) or []
                if len(path) >= 2:
                    m['neck'] = path[0]
        elif chain_up:
            m['head'] = chain_up[-1]
            if len(chain_up) >= 2:
                m['neck'] = chain_up[0]
    jaw = pick('jaw', None)
    if jaw and m.get('head') in tree.ancestors(jaw):
        m['jaw'] = jaw
    for s in ('left', 'right'):
        if m.get(s + 'Eye'):
            m[s + 'Eye'] = m.pop(s + 'Eye')
        for finger in set(FINGERS.values()):
            segs = sorted(cand.get(('finger:' + finger, s), []), key=lambda e: tree.depth(e[0]))
            names = [n for n, _seg in segs]
            if finger == 'Thumb':
                roles = ['ThumbMetacarpal', 'ThumbProximal', 'ThumbDistal']
                if len(names) == 2:
                    roles = ['ThumbProximal', 'ThumbDistal']
            else:
                roles = [finger + 'Proximal', finger + 'Intermediate', finger + 'Distal']
                if len(names) == 4:
                    # a leaf fourth segment is an end bone; otherwise the first one is a metacarpal
                    names = names[:3] if not tree.children.get(names[3]) else names[1:]
                if len(names) == 2:
                    roles = [finger + 'Proximal', finger + 'Distal']
            for r, n in zip(roles, names[:3]):
                m[s + r] = n
    problems = validate(m, tree)
    return ({} if problems else m), problems


def validate(mapping, tree=None, bones=None):
    """Problems of a role -> bone mapping: required roles, unknown roles, unique bones, ancestry order."""
    if tree is None:
        tree = Tree(bones)
    v = vocabulary()
    problems = []
    for r in v['required']:
        if r not in mapping:
            problems.append('missing required role ' + r)
    for r in mapping:
        if r not in v['parent']:
            problems.append('unknown role ' + r)
    seen = {}
    for r, b in mapping.items():
        if b not in tree.parent:
            problems.append('{}: bone {} not found'.format(r, b))
        if b in seen:
            problems.append('bone {} used by {} and {}'.format(b, seen[b], r))
        seen[b] = r
    for r, b in mapping.items():
        p = v['parent'].get(r)
        while p is not None and p not in mapping:
            p = v['parent'].get(p)
        if p is not None and b in tree.parent and mapping[p] not in tree.ancestors(b):
            problems.append('{} ({}) is not below {} ({})'.format(r, b, p, mapping[p]))
    return problems
