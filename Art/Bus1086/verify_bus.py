"""Read-only checks: blender -b --python-exit-code 1 -P verify_bus.py -- <asset directory>."""
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector

WHEELS = {"wheel_FL": (2.2, .94, .39), "wheel_FR": (2.2, -.94, .39),
          "wheel_RL": (-2.2, .94, .39), "wheel_RR": (-2.2, -.94, .39)}
RIG = set(WHEELS) | {
    "root", "door_front_A", "door_front_B", "door_mid_A", "door_mid_B",
    "wiper_L", "wiper_R", "steering", "needle_speed", "needle_rpm", "selector",
    "pedal_brake", "pedal_throttle", "switch_front", "switch_mid", "switch_park",
    "switch_left", "switch_right", "switch_lights",
}
LAMP_SLOTS = {"HeadlampLens", "TailLens", "SignalLeft", "SignalRight"}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def points(meshes, graph):
    """Measure the evaluated, world-space geometry, including actual armature deformation."""
    result = {}
    triangle_count = 0
    for obj in meshes:
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        try:
            result[obj.name] = [evaluated.matrix_world @ v.co for v in mesh.vertices]
            mesh.calc_loop_triangles()
            triangle_count += len(mesh.loop_triangles)
        finally:
            evaluated.to_mesh_clear()
    return result, triangle_count


def check_uv(obj):
    mesh = obj.data
    require(len(mesh.uv_layers) > 0, f"{obj.name} has no FBX UV0")
    texcoords = mesh.uv_layers[0].data
    require(len(texcoords) == len(mesh.loops), f"{obj.name}: incomplete UV0")
    require(all(math.isfinite(v) for t in texcoords for v in t.uv), f"{obj.name}: nonfinite UV")
    mesh.calc_loop_triangles()
    for tri in mesh.loop_triangles:
        # Tiny or degenerate geometric triangles may occur at a bevel's ends.
        if tri.area <= 1e-12:
            continue
        a, b, c = (texcoords[i].uv for i in tri.loops)
        require(abs((b-a).cross(c-a)) > 1e-14,
                f"{obj.name}, triangle {tri.index}: nonzero geometric area but collapsed UV0")


def validate(manifest, fbx):
    label = "FBX round trip" if fbx else "Blender source"
    scene = bpy.context.scene
    require(abs(scene.unit_settings.scale_length-1.0) < 1e-6, f"{label}: expected metre scene")
    arms = [o for o in scene.objects if o.type == "ARMATURE"]
    require(len(arms) == 1, f"{label}: expected one armature, got {len(arms)}")
    arm = arms[0]
    require(set(manifest["bones"]) == RIG == set(arm.data.bones.keys()), f"{label}: unexpected rig")
    for bone in arm.data.bones:
        head = arm.matrix_world @ bone.head_local
        require((head-Vector(manifest["bones"][bone.name])).length < .0005,
                f"{label}: {bone.name} pivot differs from manifest")
        posed_head = arm.matrix_world @ arm.pose.bones[bone.name].head
        require((head-posed_head).length < .0005,
                f"{label}: {bone.name} default pose {tuple(posed_head)} differs from its bind pivot {tuple(head)}")
        if bone.name in WHEELS:
            require((head-Vector(WHEELS[bone.name])).length < .0005,
                    f"{label}: {bone.name} does not match Chaos wheel coordinates")
        expected_parent = None if bone.name == "root" else arm.data.bones["root"]
        require(bone.parent == expected_parent, f"{label}: wrong parent for {bone.name}")

    meshes = [o for o in scene.objects if o.type == "MESH"]
    mesh_bones = {}
    used_materials = set()
    for obj in meshes:
        require(any(m.type == "ARMATURE" and m.object == arm for m in obj.modifiers),
                f"{label}: missing armature binding on {obj.name}")
        names = set()
        for v in obj.data.vertices:
            weights = [g for g in v.groups if g.weight > .00001]
            require(len(weights) == 1 and abs(weights[0].weight-1) < 1e-5,
                    f"{label}: vertex {v.index} on {obj.name} is not rigidly weighted")
            names.add(obj.vertex_groups[weights[0].group].name)
        require(len(names) == 1, f"{label}: expected one rigid assembly per mesh on {obj.name}")
        mesh_bones[obj.name] = names.pop()
        slots = obj.data.materials
        used_materials.update(slots[i].name for i in {p.material_index for p in obj.data.polygons})
        if fbx:
            check_uv(obj)
    require(set(mesh_bones.values()) == RIG, f"{label}: missing skinned components")
    require(set(manifest["materials"]) == used_materials and LAMP_SLOTS <= used_materials,
            f"{label}: material assignments differ from manifest ({used_materials ^ set(manifest['materials'])})")
    glass = bpy.data.materials["ExtGlass"].node_tree.nodes.get("Principled BSDF")
    require(glass and 0 < glass.inputs["Alpha"].default_value < .5, f"{label}: windshield transparency")

    graph = bpy.context.evaluated_depsgraph_get()
    rest, triangles = points(meshes, graph)
    all_pts = [v for verts in rest.values() for v in verts]
    size = [max(p[i] for p in all_pts) - min(p[i] for p in all_pts) for i in range(3)]
    require(8.8 <= size[0] <= 9.2 and 2.30 <= size[1] <= 3.1 and 2.9 <= size[2] <= 3.2,
            f"{label}: unexpected outside dimensions including mirrors {size}")
    for wheel, center in WHEELS.items():
        wheel_pts = [v for name, verts in rest.items() if mesh_bones[name] == wheel for v in verts]
        require(wheel_pts, f"{wheel}: no visible geometry")
        for axis in (0, 2):
            lo = min(p[axis] for p in wheel_pts)
            hi = max(p[axis] for p in wheel_pts)
            require(abs((lo+hi)*.5 - center[axis]) < .001 and abs((hi-lo)*.5 - .39) < .001,
                    f"{label}: {wheel} tyre does not fit its .39 m Chaos radius")
        side = 1 if center[1] > 0 else -1
        for dx, dz in ((0, 0), (0, .19), (.23, .06)):
            origin = Vector((center[0]+dx, side*2.1, center[2]+dz))
            hit, _, _, _, obj, _ = scene.ray_cast(graph, origin, Vector((0,-side,0)), distance=1.7)
            require(hit and mesh_bones.get(obj.name) == wheel,
                    f"{label}: exterior view of {wheel} occluded by {obj.name if hit else 'empty space'}")

    door = arm.pose.bones["door_front_A"]
    door.rotation_mode = "XYZ"
    door.rotation_euler.z = math.radians(50)
    bpy.context.view_layer.update()
    moved, _ = points(meshes, bpy.context.evaluated_depsgraph_get())
    door_travel = 0.0
    for name, before in rest.items():
        after = moved[name]
        require(len(after) == len(before), f"{label}: pose changed topology on {name}")
        travel = max((b-a).length for a, b in zip(before, after))
        if mesh_bones[name] == door.name:
            door_travel = max(door_travel, travel)
        else:
            require(travel < 1e-5, f"{label}: opening the front door moved {name} by {travel} m")
    require(door_travel > .20, f"{label}: door mesh failed to swing about its hinge")
    print(f"PASS {label}: {len(meshes)} meshes, {triangles:,} triangles, {len(RIG)} weighted bones, "
          f"{len(used_materials)} used materials, length/width/height "
          f"{size[0]:.3f}/{size[1]:.3f}/{size[2]:.3f} m, test hinge travel {door_travel:.3f} m")


def main():
    args = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    directory = Path(args[0]).resolve() if args else Path(__file__).resolve().parent
    manifest = json.loads((directory/"Bus1086.json").read_text())
    bpy.ops.wm.open_mainfile(filepath=str(directory/"Bus1086.blend"))
    validate(manifest, fbx=False)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    fbx_path = directory/"Bus1086.fbx"
    # Blender 4.x bundles this reader with its FBX importer. FBX unit factors
    # are centimetres per scene unit; a metre-based file would report 100.
    from io_scene_fbx.parse_fbx import parse
    tree, _ = parse(fbx_path)
    settings = next(n for n in tree.elems if n.id == b"GlobalSettings")
    properties = next(n for n in settings.elems if n.id == b"Properties70")
    unit = next(n.props[-1] for n in properties.elems if n.props[0] == b"UnitScaleFactor")
    require(math.isclose(unit, 1.0), f"FBX is not in centimetres (UnitScaleFactor={unit})")
    del tree, settings, properties
    bpy.ops.import_scene.fbx(filepath=str(fbx_path))
    validate(manifest, fbx=True)


if __name__ == "__main__":
    main()
