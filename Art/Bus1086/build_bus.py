"""Blender 4.x: blender -b -t 2 -P build_bus.py -- <output directory>."""
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


class Builder:
    def __init__(self):
        self.bones = {"root": (0.0, 0.0, 0.0)}
        self.materials = {}
        self.parts = []
        self.section("Exterior")
        for axle, x in (("F", 2.2), ("R", -2.2)):
            for side, y in (("L", .94), ("R", -.94)):
                self.bone(f"wheel_{axle}{side}", (x, y, .39))
        for name, x in (("front_A", 3.91), ("front_B", 3.05), ("mid_A", -.11), ("mid_B", -1.25)):
            self.bone("door_" + name, (x, 1.138, 1.25))
        self.bone("wiper_L", (4.34, .49, 1.24))
        self.bone("wiper_R", (4.34, -.49, 1.24))
        self.bone("steering", (3.62, -.66, 1.31))
        self.bone("needle_speed", (3.872, -.515, 1.527))
        self.bone("needle_rpm", (3.872, -.805, 1.527))
        self.bone("selector", (3.70, -.245, 1.30))

    def section(self, name):
        self.collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(self.collection)

    def bone(self, name, pivot):
        self.bones[name] = tuple(pivot)

    def material(self, name, rgb, metallic=0.0, roughness=.45, alpha=1.0, emission=0.0):
        if name in self.materials:
            return bpy.data.materials[name]
        rgb = tuple(rgb[:3])
        self.materials[name] = dict(rgb=rgb, metallic=metallic, roughness=roughness,
                                    alpha=alpha, emission=emission)
        material = bpy.data.materials.new(name)
        material.diffuse_color = (*rgb, alpha)
        material.use_nodes = True
        inputs = material.node_tree.nodes.get("Principled BSDF").inputs
        for key, value in (("Base Color", (*rgb, 1.0)), ("Metallic", metallic),
                           ("Roughness", roughness), ("Alpha", alpha),
                           ("Emission Color", (*rgb, 1.0)), ("Emission Strength", emission)):
            inputs[key].default_value = value
        return material

    def mesh(self, name, verts, faces, mat, bone="root", bevel=0.0):
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        obj = bpy.data.objects.new(name, mesh)
        self.collection.objects.link(obj)
        mesh.materials.append(bpy.data.materials[mat] if isinstance(mat, str) else mat)
        if bevel:
            rounding = obj.modifiers.new("Edge radius", "BEVEL")
            rounding.width = bevel
            rounding.segments = 3
            rounding.harden_normals = True
            obj.modifiers.new("Panel normals", "WEIGHTED_NORMAL")
        self.parts.append((obj, bone))
        return obj

    def box(self, name, center, size, mat, bevel=0.0, bone="root", rot=(0, 0, 0)):
        x, y, z = (v * .5 for v in size)
        corners = [(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),
                   (-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
        faces = [(3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
        obj = self.mesh(name, corners, faces, mat, bone, bevel)
        obj.location = center
        obj.rotation_euler = rot
        return obj

    def tube(self, name, points, radius, mat, bone="root", sides=12):
        points = [Vector(p) for p in points]
        closed = len(points) > 2 and (points[0] - points[-1]).length < 1e-7
        if closed:
            points.pop()
        verts, faces = [], []
        normal = None
        for i, p in enumerate(points):
            prev = points[(i-1) % len(points)] if closed or i else p
            nxt = points[(i+1) % len(points)] if closed or i+1 < len(points) else p
            axis = ((p-prev).normalized() + (nxt-p).normalized()).normalized()
            if normal is None or abs(axis.dot(normal)) > .999:
                normal = axis.orthogonal().normalized()
            normal = (normal - axis * axis.dot(normal)).normalized()
            tangent = axis.cross(normal)
            for j in range(sides):
                a = math.tau * j / sides
                verts.append(p + radius * (math.cos(a)*normal + math.sin(a)*tangent))
        for i in range(len(points) if closed else len(points)-1):
            a, b = i*sides, ((i+1) % len(points))*sides
            for j in range(sides):
                k = (j+1) % sides
                faces.append((a+j,a+k,b+k,b+j))
        if not closed:
            faces.extend([tuple(reversed(range(sides))), tuple(range(len(verts)-sides,len(verts)))])
        obj = self.mesh(name, verts, faces, mat, bone)
        for face in obj.data.polygons:
            face.use_smooth = len(face.vertices) == 4
        return obj

    def cyl(self, name, a, b, radius, mat, bone="root", sides=24):
        return self.tube(name, [a, b], radius, mat, bone, sides)

    def make_skeleton(self, units_per_metre):
        data = bpy.data.armatures.new("1086 skeleton")
        arm = bpy.data.objects.new("Armature", data)
        bpy.context.scene.collection.objects.link(arm)
        bpy.context.view_layer.objects.active = arm
        arm.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        for name, p in self.bones.items():
            bone = data.edit_bones.new(name)
            bone.head = Vector(p) * units_per_metre
            bone.tail = (Vector(p) + Vector((0, .12, 0))) * units_per_metre
            if name != "root":
                bone.parent = data.edit_bones["root"]
        bpy.ops.object.mode_set(mode="OBJECT")
        arm.display_type = "WIRE"
        return arm

    def bind(self):
        arm = self.make_skeleton(1.0)
        for obj, name in self.parts:
            if name not in self.bones:
                raise ValueError(f"Unknown bone {name} on {obj.name}")
            group = obj.vertex_groups.new(name=name)
            group.add(list(range(len(obj.data.vertices))), 1., "REPLACE")
            obj.parent = arm
            mod = obj.modifiers.new("Rigid part", "ARMATURE")
            mod.object = arm
        return arm


def add_planar_uvs(mesh):
    # Materials use solid colours. Give each face a nondegenerate tangent space
    # for UE's skeletal-mesh build, with 1 UV unit per metre of panel.
    mesh.update()
    coords = [v.co.copy() for v in mesh.vertices]
    uv = [0.0] * (2 * len(mesh.loops))
    for face in mesh.polygons:
        normal = face.normal
        axis = max(range(3), key=lambda i: abs(normal[i]))
        u, v = (axis + 1) % 3, (axis + 2) % 3
        for idx, vert in zip(face.loop_indices, face.vertices):
            uv[2 * idx] = coords[vert][u] * .01
            uv[2 * idx + 1] = coords[vert][v] * .01
    mesh.uv_layers.new(name="PanelUV").data.foreach_set("uv", uv)


def export_fbx(h, arm, path):
    # Evaluate bevels in metres before baking them to cm, then group by rigid part.
    graph = bpy.context.evaluated_depsgraph_get()
    groups = {}
    mats = list(bpy.data.materials)
    mat_index = {mat.name: i for i, mat in enumerate(mats)}
    for obj, bone in h.parts:
        verts, faces, indices, smooth = groups.setdefault(bone, ([], [], [], []))
        evaluated = obj.evaluated_get(graph)
        data = evaluated.to_mesh()
        offset = len(verts)
        transform = evaluated.matrix_world
        verts.extend((transform @ v.co) * 100.0 for v in data.vertices)
        for f in data.polygons:
            faces.append(tuple(offset + v for v in f.vertices))
            indices.append(mat_index[data.materials[f.material_index].name])
            smooth.append(f.use_smooth)
        evaluated.to_mesh_clear()
    for obj, _ in h.parts:
        bpy.data.objects.remove(obj, do_unlink=True)
    # Rebuild in cm so bind transforms and default pose both use the FBX units.
    bpy.data.objects.remove(arm, do_unlink=True)
    arm = h.make_skeleton(100.0)
    for bone, (verts, faces, indices, smooth) in groups.items():
        data = bpy.data.meshes.new(bone + "_skin")
        data.from_pydata(verts, [], faces)
        add_planar_uvs(data)
        used = sorted(set(indices))
        local_index = {v: k for k, v in enumerate(used)}
        for i in used:
            data.materials.append(mats[i])
        data.polygons.foreach_set("material_index", [local_index[i] for i in indices])
        data.polygons.foreach_set("use_smooth", smooth)
        obj = bpy.data.objects.new(bone + "_skin", data)
        bpy.context.scene.collection.objects.link(obj)
        obj.parent = arm
        obj.vertex_groups.new(name=bone).add(list(range(len(verts))), 1.0, "REPLACE")
        obj.modifiers.new("Skeleton", "ARMATURE").object = arm
    bpy.context.scene.unit_settings.scale_length = .01
    bpy.context.view_layer.update()
    bpy.ops.export_scene.fbx(filepath=str(path), object_types={"ARMATURE","MESH"},
                             axis_forward="Y", axis_up="Z", add_leaf_bones=False,
                             apply_unit_scale=True, use_mesh_modifiers=False,
                             use_triangles=True, bake_anim=False, mesh_smooth_type="FACE")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:])
    out = args.output.resolve()
    out.mkdir(exist_ok=True, parents=True)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import exterior
    import interior
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    h = Builder()
    exterior.build(h)
    h.section("Passenger saloon and driving position")
    interior.build(h)
    arm = h.bind()
    bpy.ops.object.select_all(action="DESELECT")
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            space = area.spaces.active
            space.overlay.show_overlays = False
            space.shading.type = 'MATERIAL'
            space.region_3d.view_rotation = Vector((-1.1, -1.6, -.55)).to_track_quat('-Z', 'Y')
            space.region_3d.view_location = (0,0,1.4)
            space.region_3d.view_distance = 12.0
    scene["vehicle"] = "Kotoden Takamatsu 210 a 1086 / Hino Rainbow / 2KG-KR290J5"
    (out/"Bus1086.json").write_text(json.dumps(dict(materials=h.materials, bones=h.bones), indent=2)+"\n")
    bpy.ops.wm.save_as_mainfile(filepath=str(out/"Bus1086.blend"), compress=True)
    export_fbx(h, arm, out/"Bus1086.fbx")
    print(f"Generated {len(h.parts)} parts, {len(h.bones)} bones, {len(h.materials)} materials")


if __name__ == "__main__":
    main()
