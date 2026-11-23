"""Render the Blender source model. Staging is temporary and is never saved.

blender -b Art/Bus1086/Bus1086.blend -P Art/Bus1086/render_preview.py
Add "-- --view cockpit" to render just one view.
"""
import argparse
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy
import _cycles
from mathutils import Vector


def parse_options():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--view", choices=("all", "exterior", "cockpit", "cabin"), default="all")
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent / "preview")
    parser.add_argument("--oidn", type=Path, help="Optional standalone oidnDenoise binary for Blender builds without a bundled denoiser")
    parser.add_argument("--draft", action="store_true", help="Quick camera and material inspection")
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return parser.parse_args(args)


def point_at(obj, target):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


class Studio:
    def __init__(self, scene):
        self.scene = scene
        self.units = 1.0 / scene.unit_settings.scale_length
        self.world = bpy.data.worlds.new("Preview daylight")
        self.world.use_nodes = True
        self.scene.world = self.world
        self.lights = []

        bpy.ops.mesh.primitive_plane_add(size=300.0 * self.units, location=self.position((0, 0, -0.016)))
        self.floor = bpy.context.object
        self.floor.name = "Studio floor"
        self.floor_material = bpy.data.materials.new("Studio floor matte")
        self.floor_material.use_nodes = True
        self.floor.data.materials.append(self.floor_material)

        # A curved studio sweep keeps the end of the ground plane out of the hero shot.
        forward = Vector((-0.70, -0.714, 0.0)).normalized()
        sideways = Vector((-forward.y, forward.x, 0))
        profile = []
        for step in range(17):
            angle = math.pi * step / 32
            profile.append((11.0 + 3.0 * math.sin(angle), -0.017 + 3.0 * (1 - math.cos(angle))))
        profile.append((14.0, 15))
        verts = [self.position(forward * distance + sideways * width + Vector((0, 0, z)))
                 for distance, z in profile for width in (-34, 34)]
        faces = [(i * 2, i * 2 + 1, i * 2 + 3, i * 2 + 2) for i in range(len(profile) - 1)]
        mesh = bpy.data.meshes.new("Studio sweep")
        mesh.from_pydata(verts, [], faces)
        self.sweep = bpy.data.objects.new("Studio sweep", mesh)
        self.scene.collection.objects.link(self.sweep)
        mesh.materials.append(self.floor_material)
        for poly in mesh.polygons:
            poly.use_smooth = True

        bpy.ops.object.camera_add()
        self.camera = bpy.context.object
        self.camera.name = "Preview camera"
        self.camera.data.clip_start = 0.02 * self.units
        self.camera.data.clip_end = 350 * self.units
        scene.camera = self.camera

    def position(self, xyz):
        return Vector(xyz) * self.units

    def light(self, name, xyz, focus, size, watts, color):
        lamp = bpy.data.lights.new(name, "AREA")
        lamp.shape = "DISK"
        lamp.size = size * self.units
        lamp.energy = watts * self.units ** 2
        lamp.color = color
        obj = bpy.data.objects.new(name, lamp)
        self.scene.collection.objects.link(obj)
        obj.location = self.position(xyz)
        point_at(obj, self.position(focus))
        self.lights.append(obj)

    def lighting(self, interior):
        for obj in self.lights:
            bpy.data.objects.remove(obj, do_unlink=True)
        self.lights.clear()
        self.sweep.hide_render = interior
        sky = self.world.node_tree.nodes.get("Background")
        sky.inputs["Color"].default_value = (0.56, 0.69, 0.82, 1.0)
        sky.inputs["Strength"].default_value = 0.8 if interior else 0.48
        floor_shader = self.floor_material.node_tree.nodes.get("Principled BSDF")
        floor_shader.inputs["Base Color"].default_value = (0.27, 0.32, 0.37, 1)
        floor_shader.inputs["Roughness"].default_value = 0.78

        # Large soft sources keep the painted shell, glass and rounded panel edges distinct.
        self.light("Daylight", (6, 4, 9), (1, 0, 1.4), 7.5, 2800, (1, 0.91, 0.79))
        self.light("Side fill", (-4, 5, 5), (-1, 0, 1.5), 6.0, 1400, (0.76, 0.89, 1))
        self.light("Roof rim", (-3, -5, 7), (-1, 0, 2), 5.0, 2300, (1, 0.95, 0.89))
        if interior:
            self.light("Cabin ceiling bounce", (1.45, 0.0, 2.61), (3.7, -0.48, 1.3),
                       1.1, 88, (1, 0.94, 0.84))
            self.light("Saloon ceiling bounce", (-2.5, 0.0, 2.58), (0.1, 0.0, 1.1),
                       1.3, 95, (0.93, 0.96, 1))

    def frame(self, view):
        frames = {
            # Origin is between axles, +X front, +Y boarding side; distances are metres.
            "exterior": ((13.45, 13.75, 4.55), (0.0, 0, 1.31), 63),
            "cockpit": ((3.02, -0.78, 1.82), (3.87, -0.43, 1.37), 17),
            "cabin": ((-3.10, 0.03, 2.13), (3.45, -0.1, 1.54), 16),
        }
        eye, target, lens = frames[view]
        self.camera.location = self.position(eye)
        self.camera.data.lens = lens
        self.camera.data.sensor_width = 36
        point_at(self.camera, self.position(target))
        self.lighting(interior=view != "exterior")


def render_jpeg(scene, output, denoiser):
    if not denoiser:
        scene.render.filepath = str(output.resolve())
        bpy.ops.render.render(write_still=True)
        return

    # Some Linux builds package Cycles without Open Image Denoise. Its standalone
    # utility accepts linear float RGB; apply the Blender view transform afterwards.
    import numpy as np
    with tempfile.TemporaryDirectory() as staging:
        staging = Path(staging)
        scene.render.image_settings.file_format = "OPEN_EXR"
        scene.render.filepath = str(staging / "beauty.exr")
        bpy.ops.render.render(write_still=True)
        image = bpy.data.images.load(scene.render.filepath)
        width, height = image.size
        pixels = np.empty(width * height * 4, dtype=np.float32)
        image.pixels.foreach_get(pixels)
        rgba = pixels.reshape(height, width, 4)
        raw, filtered = staging / "beauty.pfm", staging / "filtered.pfm"
        with raw.open("wb") as stream:
            stream.write(f"PF\n{width} {height}\n-1.0\n".encode("ascii"))
            rgba[:, :, :3].astype("<f4").tofile(stream)
        subprocess.run([str(denoiser.resolve()), "--device", "cpu", "--hdr", str(raw),
                        "--threads", "4", "-o", str(filtered)], check=True)
        with filtered.open("rb") as stream:
            assert stream.readline().strip() == b"PF"
            assert tuple(map(int, stream.readline().split())) == (width, height)
            endian = "<f4" if float(stream.readline()) < 0 else ">f4"
            rgba[:, :, :3] = np.fromfile(stream, dtype=endian).reshape(height, width, 3)
        image.pixels.foreach_set(pixels)
        image.update()
        scene.render.image_settings.file_format = "JPEG"
        image.save_render(str(output.resolve()), scene=scene)
        bpy.data.images.remove(image)


def main():
    opts = parse_options()
    opts.out_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.use_denoising = bool(getattr(_cycles, "with_openimagedenoise", False))
    scene.cycles.samples = 4 if opts.draft else (28 if scene.cycles.use_denoising or opts.oidn else 56)
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.max_bounces = 8
    scene.cycles.transparent_max_bounces = 12
    scene.cycles.seed = 1086
    scene.render.film_transparent = False
    scene.render.resolution_x = 1536
    scene.render.resolution_y = 960
    scene.render.resolution_percentage = 35 if opts.draft else 100
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.quality = 90
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -0.55
    studio = Studio(scene)
    views = ["exterior", "cockpit", "cabin"] if opts.view == "all" else [opts.view]
    for view in views:
        studio.frame(view)
        output = opts.out_dir / f"{view}.jpg"
        render_jpeg(scene, output, opts.oidn if not scene.cycles.use_denoising else None)
        print(f"Rendered {output}")


if __name__ == "__main__":
    main()
