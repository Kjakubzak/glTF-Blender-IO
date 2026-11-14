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

import math
import unittest

import bpy

import khr_test_utils as u

CAM = 'KHR_node_camera_hint'
LOOK = 'KHR_node_lookat_target'
VIS = 'KHR_node_visibility_hint'
PRIM = 'KHR_mesh_primitive_visibility_hint'


def hint_scene(resolution=(1024, 1024), source_aspect=1.0):
    """Body (two materials, Hair with a primitive hint), Helmet (visibility hint), EyeTarget (look-at {}),
    a perspective full_body and an orthographic portrait hint camera."""
    u.clear_scene()
    scene = bpy.context.scene
    scene.render.resolution_x, scene.render.resolution_y = resolution
    scene.render.pixel_aspect_x = scene.render.pixel_aspect_y = 1.0
    body = u.shape_key_mesh('Body', [])
    skin, hair = bpy.data.materials.new('Skin'), bpy.data.materials.new('Hair')
    body.data.materials.append(skin)
    body.data.materials.append(hair)
    hair.khr_primitive_hint.enabled = True
    hair.khr_primitive_hint.roles = 'third_person'
    hair.khr_primitive_hint.label = 'Hair'
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True)
    for i, f in enumerate(bm.faces):
        f.material_index = i % 2
    bm.to_mesh(body.data)
    bm.free()
    helmet = u.shape_key_mesh('Helmet', [], location=(0, 0, 0.3))
    helmet.khr_hints.visibility.enabled = True
    helmet.khr_hints.visibility.roles = 'third_person, first_person, third_person'
    target = bpy.data.objects.new('EyeTarget', None)
    scene.collection.objects.link(target)
    target.location = (0, -0.1, 0.2)
    target.khr_hints.lookat.enabled = True
    cams = {}
    for name, kind in (('full_body', 'PERSP'), ('portrait', 'ORTHO')):
        data = bpy.data.cameras.new(name)
        data.type = kind
        data.sensor_fit = 'VERTICAL' if kind == 'PERSP' else 'AUTO'
        data.ortho_scale = 0.6
        ob = bpy.data.objects.new(name, data)
        scene.collection.objects.link(ob)
        ob.location = (0, -2, 0.1)
        ob.rotation_euler = (math.pi / 2, 0, 0)
        h = ob.khr_hints.camera
        h.enabled, h.role, h.source_aspect = True, name, source_aspect
        cams[name] = ob
    cams['portrait'].khr_hints.camera.target = target
    cams['portrait'].khr_hints.camera.label = 'Close-up'
    return cams


def ext(node, name):
    return node.get('extensions', {}).get(name)


class Hints(unittest.TestCase):
    def test_hints(self):
        hint_scene()
        g = u.Glb(u.export('hints', export_khr_character=True, export_cameras=True))
        j = g.json
        nodes = {n['name']: n for n in j['nodes']}
        for name in (CAM, LOOK, VIS, PRIM):
            self.assertIn(name, j['extensionsUsed'])
            self.assertNotIn(name, j.get('extensionsRequired', []))
        full, portrait = nodes['full_body'], nodes['portrait']
        self.assertNotIn('camera', full)
        self.assertNotIn('camera', portrait)
        self.assertEqual(set(ext(full, CAM)), {'role', 'camera'})
        self.assertEqual(ext(full, CAM)['role'], 'full_body')
        self.assertEqual(ext(portrait, CAM)['targetNode'], g.node_index('EyeTarget'))
        self.assertEqual(ext(portrait, CAM)['label'], 'Close-up')
        persp = j['cameras'][ext(full, CAM)['camera']]
        ortho = j['cameras'][ext(portrait, CAM)['camera']]
        self.assertAlmostEqual(persp['perspective']['aspectRatio'], 1.0, places=5)
        self.assertAlmostEqual(ortho['orthographic']['xmag'], ortho['orthographic']['ymag'], places=6)
        self.assertEqual(ext(nodes['EyeTarget'], LOOK), {})
        self.assertEqual(ext(nodes['Helmet'], VIS), {'roles': ['third_person', 'first_person']})
        prims = j['meshes'][nodes['Body']['mesh']]['primitives']
        hinted = [p for p in prims if PRIM in p.get('extensions', {})]
        self.assertEqual(len(hinted), 1)
        self.assertEqual(j['materials'][hinted[0]['material']]['name'], 'Hair')
        self.assertEqual(hinted[0]['extensions'][PRIM], {'roles': ['third_person'], 'label': 'Hair'})

    def test_bone_target(self):
        import rigs
        cams = hint_scene()
        ob = rigs.build_armature(rigs.clavicle_chain()[0], name='Rig')
        hint = cams['portrait'].khr_hints.camera
        hint.target, hint.target_bone = ob, 'head'
        g = u.Glb(u.export('hints_bone', export_khr_character=True, export_cameras=True))
        node = g.json['nodes'][g.node_index('portrait')]
        self.assertEqual(node['extensions'][CAM]['targetNode'], g.node_index('head'))
        hint.target_bone = 'no_such_bone'
        with self.assertRaises(RuntimeError):
            u.export('hints_bone_missing', export_khr_character=True, export_cameras=True)

    def test_aspect_rule_covers_every_exported_scene(self):
        hint_scene()
        other = bpy.data.scenes.new('Other')
        other.render.resolution_x, other.render.resolution_y = 1920, 1080
        data = bpy.data.cameras.new('wide')
        cam = bpy.data.objects.new('wide', data)
        other.collection.objects.link(cam)
        cam.khr_hints.camera.enabled, cam.khr_hints.camera.role = True, 'full_body'
        cam.khr_hints.camera.source_aspect = 1.0
        try:
            with self.assertRaises(RuntimeError):
                u.export('hints_two_scenes', export_khr_character=True, export_cameras=True)
            g = u.Glb(u.export('hints_active_scene', export_khr_character=True, export_cameras=True,
                               use_active_scene=True))
            self.assertNotIn('wide', [n.get('name') for n in g.json['nodes']])
        finally:
            bpy.data.objects.remove(cam)
            bpy.data.scenes.remove(other)

    def test_aspect_rule_ignores_unexported_cameras(self):
        hint_scene(resolution=(1920, 1080), source_aspect=1.0)
        for ob in bpy.context.scene.objects:
            ob.select_set(ob.name == 'Body')
        g = u.Glb(u.export('hints_selection', export_khr_character=True, export_cameras=True, use_selection=True))
        self.assertEqual([n.get('name') for n in g.json['nodes']], ['Body'])

    def test_full_collection_hierarchy(self):
        cams = hint_scene()
        coll = bpy.data.collections.new('Cameras')
        bpy.context.scene.collection.children.link(coll)
        for ob in cams.values():
            for c in list(ob.users_collection):
                c.objects.unlink(ob)
            coll.objects.link(ob)
        g = u.Glb(u.export('hints_collections', export_khr_character=True, export_cameras=True,
                           export_hierarchy_full_collections=True))
        node = g.json['nodes'][g.node_index('portrait')]
        self.assertEqual(node['extensions'][CAM]['role'], 'portrait')
        bpy.data.collections.remove(coll)

    def test_keep_core_camera(self):
        cams = hint_scene()
        cams['full_body'].khr_hints.camera.keep_core_camera = True
        g = u.Glb(u.export('hints_keep', export_khr_character=True, export_cameras=True))
        node = g.json['nodes'][g.node_index('full_body')]
        self.assertEqual(node['camera'], node['extensions'][CAM]['camera'])

    def test_aspect_rule(self):
        hint_scene(resolution=(1920, 1080), source_aspect=1.0)
        with self.assertRaises(RuntimeError):
            u.export('hints_aspect', export_khr_character=True, export_cameras=True)
        g = u.Glb(u.export('hints_aspect_lenient', export_khr_character=True, export_cameras=True,
                           export_khr_strict=False))
        ortho = [c for c in g.json['cameras'] if c['type'] == 'orthographic'][0]['orthographic']
        self.assertNotAlmostEqual(ortho['xmag'], ortho['ymag'], places=3)

    def test_unset_source_aspect_skips_check(self):
        hint_scene(resolution=(1920, 1080), source_aspect=0.0)
        g = u.Glb(u.export('hints_unset', export_khr_character=True, export_cameras=True))
        self.assertIn(CAM, g.json['extensionsUsed'])

    def test_mixed_aspects_abort(self):
        cams = hint_scene()
        cams['portrait'].khr_hints.camera.source_aspect = 1.5
        with self.assertRaises(RuntimeError):
            u.export('hints_mixed', export_khr_character=True, export_cameras=True)

    def test_package_off(self):
        hint_scene()
        g = u.Glb(u.export('hints_off', export_cameras=True))
        self.assertNotIn('extensionsUsed', g.json)
        self.assertIn('camera', g.json['nodes'][g.node_index('full_body')])

    def test_default_camera_hints_operator(self):
        u.clear_scene()
        u.shape_key_mesh('Body', [])
        bpy.context.scene.render.resolution_x = 1920
        self.assertEqual(bpy.ops.khr_character.add_default_camera_hints('EXEC_DEFAULT'), {'FINISHED'})
        self.assertEqual((bpy.context.scene.render.resolution_x, bpy.context.scene.render.resolution_y),
                         (1024, 1024))
        g = u.Glb(u.export('hints_default', export_khr_character=True, export_cameras=True))
        roles = sorted(n['extensions'][CAM]['role'] for n in g.json['nodes'] if CAM in n.get('extensions', {}))
        self.assertEqual(roles, ['full_body', 'portrait'])


if __name__ == '__main__':
    unittest.main()
