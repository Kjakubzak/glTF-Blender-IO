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

# Export side of the KHR_character family, as a glTF export user extension. The exporter adds an
# instance to export_settings['gltf_user_extensions'] when the "KHR_character" option is enabled.
# Each feature module implements some of the stage functions called below; they share one
# ExportContext per export.

import os

import bpy

from ...com import khr_character as khr
from . import features


class ValidationError(RuntimeError):
    pass


class ExportContext:
    def __init__(self, export_settings):
        self.settings = export_settings
        self.strict = export_settings.get('gltf_khr_strict', True)
        self.errors = []
        self.warnings = []
        self.object_nodes = {}   # object name -> gltf2_io.Node
        self.bone_nodes = {}     # (armature object name, bone name) -> gltf2_io.Node
        self.declared = []       # extension names to list in extensionsUsed
        self.animations = []
        self.gltf = None

    @property
    def scene_data(self):
        return bpy.context.scene.khr_character

    def error(self, rule, message):
        self.errors.append('{}: {}'.format(rule, message))

    def warning(self, message):
        self.warnings.append(message)

    def declare(self, name):
        if name not in self.declared:
            self.declared.append(name)


def fork_revision(start=None):
    """Commit of the git checkout holding this add-on, read from .git without running git.

    Returns 12 hex digits, or None when the add-on is not inside a git checkout.
    """
    d = start or os.path.dirname(os.path.abspath(__file__))
    while True:
        dot_git = os.path.join(d, '.git')
        if os.path.exists(dot_git):
            break
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    try:
        git_dir = dot_git
        if os.path.isfile(dot_git):  # worktree: "gitdir: <path>"
            with open(dot_git, encoding='utf-8') as f:
                git_dir = os.path.join(d, f.read().split(':', 1)[1].strip())
        common = git_dir
        if os.path.isfile(os.path.join(git_dir, 'commondir')):
            with open(os.path.join(git_dir, 'commondir'), encoding='utf-8') as f:
                common = os.path.join(git_dir, f.read().strip())
        with open(os.path.join(git_dir, 'HEAD'), encoding='utf-8') as f:
            head = f.read().strip()
        if head.startswith('ref:'):
            ref = head.split(':', 1)[1].strip()
            for base in (git_dir, common):
                path = os.path.join(base, ref)
                if os.path.isfile(path):
                    with open(path, encoding='utf-8') as f:
                        return f.read().strip()[:12]
            with open(os.path.join(common, 'packed-refs'), encoding='utf-8') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) == 2 and parts[1] == ref:
                        return parts[0][:12]
            return None
        return head[:12]
    except (OSError, IndexError):
        return None


class KhrCharacterExportExtension:
    """User extension instance created per export; is_critical follows export_khr_strict."""

    def __init__(self):
        self.is_critical = True
        self.ctx = None

    def _run(self, stage, *args):
        for feature in features.FEATURES:
            fn = getattr(feature, stage, None)
            if fn is not None:
                fn(self.ctx, *args)

    def pre_export_hook(self, export_settings):
        # export_khr_strict decides whether a raised error aborts the export (see user_extensions.py)
        self.is_critical = export_settings.get('gltf_khr_strict', True)
        self.ctx = ExportContext(export_settings)
        try:
            export_settings['gltf_allowed_empty_extensions'].extend(khr.EMPTY_ALLOWED)
        except Exception as e:
            export_settings['log'].warning('KHR_character: could not register empty extensions: {}'.format(e))
        self._run('pre_export')
        self._raise_if_errors('pre-export')

    def gather_asset_hook(self, asset, export_settings):
        revision = fork_revision() or '000000000000'
        asset.generator = '{}+khr_character.{}.bl{}'.format(
            asset.generator, revision, '.'.join(str(v) for v in bpy.app.version))

    def gather_node_hook(self, node, blender_object, export_settings):
        self.ctx.object_nodes[blender_object.name] = node
        self._run('node', node, blender_object)

    def gather_joint_hook(self, node, blender_bone, export_settings):
        if node.name == blender_bone.name:  # not a '_leaf' node
            self.ctx.bone_nodes[(blender_bone.id_data.name, blender_bone.name)] = node
        self._run('joint', node, blender_bone)

    def gather_tree_filter_tag_hook(self, vtree, export_settings):
        self._run('tree_filter', vtree)

    def gather_mesh_hook(self, mesh, blender_mesh, blender_object, vertex_groups, modifiers, materials,
                         export_settings):
        self._run('mesh', mesh, blender_mesh, blender_object, materials)

    def gather_gltf_hook(self, active_scene_idx, scenes, animations, export_settings):
        self.ctx.animations = animations
        self._run('gltf', scenes, animations)

    def gather_gltf_extensions_hook(self, gltf, export_settings):
        self.ctx.gltf = gltf
        self._run('root', gltf)
        for name in self.ctx.declared:
            if name not in gltf.extensions_used:
                gltf.extensions_used.append(name)
        self._run('validate', gltf)
        for message in self.ctx.warnings:
            export_settings['log'].warning('KHR_character: ' + message)
        self._raise_if_errors('validation')

    def _raise_if_errors(self, stage):
        if not self.ctx.errors:
            return
        errors, self.ctx.errors = self.ctx.errors, []
        text = 'KHR_character {} failed: {}'.format(stage, '; '.join(errors))
        if self.is_critical:
            raise ValidationError(text)
        self.ctx.settings['log'].warning(text)
