"""UE 5.5.4 editor process. Only publishes new packages in a unique Stage01 folder."""

import hashlib
import json
import os
import re
import traceback
from pathlib import Path

import unreal as ue

ROOT = "/Game/TakamatsuRoute/Stage01"
COLLIDING = {"Asphalt", "WidthEstimate", "TurningApron", "Paving", "Buildings", "Land", "Shelters"}


def import_textures(art, hashes, folder):
    """Import only this plan's shared textures into the freshly reserved map folder."""
    textures = {}
    for name, expected in hashes.items():
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", name):
            raise ValueError("Invalid artwork name")
        path = art / (name + ".png")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Map artwork changed after preparation: {name}")
        task = ue.AssetImportTask()
        task.set_editor_properties(
            {
                "filename": str(path),
                "destination_path": folder,
                "destination_name": "T_" + name,
                "automated": True,
                "replace_existing": False,
                "save": False,
                "factory": ue.TextureFactory(),
            }
        )
        ue.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        items = [v for v in task.get_objects() if isinstance(v, ue.Texture2D)]
        if len(items) != 1:
            raise RuntimeError(f"Failed texture import: {path}")
        texture = items[0]
        normal = name.endswith("_N")
        texture.set_editor_properties(
            {
                "compression_settings": ue.TextureCompressionSettings.TC_NORMALMAP
                if normal
                else ue.TextureCompressionSettings.TC_DEFAULT,
                "srgb": not normal,
            }
        )
        textures[name] = texture
    return textures


def street_material(tools, folder, name, spec, textures):
    edit = ue.MaterialEditingLibrary
    prop = ue.MaterialProperty
    material = tools.create_asset("M_" + name, folder, ue.Material, ue.MaterialFactoryNew())
    if spec.get("masked"):
        material.set_editor_properties(
            {"blend_mode": ue.BlendMode.BLEND_MASKED, "two_sided": True, "opacity_mask_clip_value": 0.39}
        )

    def node(cls, x, y):
        return edit.create_material_expression(material, cls, x, y)

    def connect(expr, pin, output):
        if not edit.connect_material_property(expr, pin, output):
            raise RuntimeError(f"Could not connect {name} to {output}")

    def wire(a, pin, b, slot):
        if not edit.connect_material_expressions(a, pin, b, slot):
            raise RuntimeError(f"Could not wire {name} input {slot}")

    def scalar(value, x, y):
        expr = node(ue.MaterialExpressionConstant, x, y)
        expr.set_editor_property("r", value)
        return expr

    def rgb(value, y):
        expr = node(ue.MaterialExpressionConstant3Vector, -450, y)
        expr.set_editor_property("constant", ue.LinearColor(*value, 1))
        return expr

    tile = spec.get("tile")
    image = spec.get("image")
    if tile or image:
        coord = node(ue.MaterialExpressionTextureCoordinate, -800, 0)
        scale = 1 / spec.get("metres", 1)
        coord.set_editor_properties({"u_tiling": scale, "v_tiling": scale})

        def sample(key, normal, y):
            expr = node(ue.MaterialExpressionTextureSample, -550, y)
            expr.set_editor_property("texture", textures[key])
            expr.set_editor_property(
                "sampler_type",
                ue.MaterialSamplerType.SAMPLERTYPE_NORMAL
                if normal
                else ue.MaterialSamplerType.SAMPLERTYPE_COLOR,
            )
            wire(coord, "", expr, "Coordinates")
            return expr

        base = sample(tile + "_BC" if tile else image, False, 0)
        base_pin = "RGB"
        if tile:
            connect(base, "A", prop.MP_ROUGHNESS)
            connect(sample(tile + "_N", True, 280), "RGB", prop.MP_NORMAL)
        if spec.get("masked"):
            connect(base, "A", prop.MP_OPACITY_MASK)
        if "tint" in spec:
            multiply = node(ue.MaterialExpressionMultiply, -190, 0)
            wire(base, "RGB", multiply, "A")
            wire(rgb(spec["tint"], -160), "", multiply, "B")
            base, base_pin = multiply, ""
    else:
        base, base_pin = rgb(spec["color"], 0), ""
    connect(base, base_pin, prop.MP_BASE_COLOR)
    if not tile:
        connect(scalar(spec["roughness"], -420, 310), "", prop.MP_ROUGHNESS)
    if spec.get("metal"):
        connect(scalar(spec["metal"], -410, 440), "", prop.MP_METALLIC)
    if spec.get("emission"):
        glow = node(ue.MaterialExpressionMultiply, -180, 540)
        wire(base, base_pin, glow, "A")
        wire(scalar(spec["emission"], -430, 555), "", glow, "B")
        connect(glow, "", prop.MP_EMISSIVE_COLOR)
    edit.recompile_material(material)
    return material


def import_stage(plan, bus_folder, revision):
    if not re.fullmatch(r"/Game/Kotoden1086/Build_\d{3}", bus_folder) or not re.fullmatch(
        r"Build_[0-9a-f]{32}", revision
    ):
        raise ValueError("Invalid stage or bus package folder")
    assets = ue.EditorAssetLibrary
    bus = assets.load_blueprint_class(bus_folder + "/BP_Kotoden1086")
    mode = assets.load_blueprint_class(bus_folder + "/BP_KotodenDriveMode")
    if not bus or not mode or ue.get_default_object(mode).get_editor_property("default_pawn_class") != bus:
        raise ValueError(
            "Selected drive mode does not reference the selected 1086 Pawn; see survey instructions"
        )
    if plan["schema"] != 1 or not plan["meshes"].get("Asphalt"):
        raise ValueError("Stage plan missing road triangles")
    folder = ROOT + "/" + revision
    content = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_content_dir()))
    if (
        (content / folder.removeprefix("/Game/")).exists()
        or assets.does_directory_exist(folder)
        or not assets.make_directory(folder)
    ):
        raise RuntimeError("Stage folder exists or cannot be reserved: " + folder)
    levels = ue.get_editor_subsystem(ue.LevelEditorSubsystem)
    level = folder + "/L_TakamatsuStation47"
    if not levels.new_level(level):
        raise RuntimeError("Cannot create " + level)
    world = ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world()
    actors = ue.get_editor_subsystem(ue.EditorActorSubsystem)
    origin = ue.Vector(0, 0, 0)

    def spawn(cls, loc=origin, yaw=0, pitch=0):
        obj = actors.spawn_actor_from_class(cls, loc, ue.Rotator(roll=0, pitch=pitch, yaw=yaw))
        if not obj:
            raise RuntimeError(f"Cannot spawn {cls}")
        return obj

    world.get_world_settings().set_editor_property("default_game_mode", mode)
    tools = ue.AssetToolsHelpers.get_asset_tools()
    art = Path(__file__).resolve().parents[1] / "Maps" / "TakamatsuStage1" / "Art"
    textures = import_textures(art, plan["artwork"], folder)
    for name, data in plan["meshes"].items():
        material = street_material(tools, folder, name, plan["materials"][name], textures)
        collides = name in COLLIDING
        mesh = ue.TakamatsuStreetMeshLibrary.create_textured_street_mesh(
            folder + "/SM_" + name,
            [ue.Vector(*p) for p in data["vertices"]],
            data["triangles"],
            [ue.Vector2D(*p) for p in data.get("uv", [])],
            material,
            collides,
        )
        if not mesh:
            raise RuntimeError("Static mesh creation failed: " + name)
        actor = spawn(ue.StaticMeshActor)
        actor.set_actor_label("Stage01_" + name)
        component = actor.static_mesh_component
        component.set_static_mesh(mesh)
        component.set_collision_profile_name("BlockAll" if collides else "NoCollision")
    x, y, z, yaw = plan["spawn"]
    spawn(ue.PlayerStart, ue.Vector(x, y, z), yaw).set_actor_label("1086 departure")
    daylight = plan["daylight"]
    light = spawn(
        ue.DirectionalLight,
        ue.Vector(0, 0, 600),
        (daylight["sun_azimuth"] + 180) % 360,
        -daylight["sun_elevation"],
    )
    sun = light.get_component_by_class(ue.DirectionalLightComponent)
    sun.set_mobility(ue.ComponentMobility.MOVABLE)
    sun.set_editor_properties(
        {
            "atmosphere_sun_light": True,
            "use_temperature": True,
            "shadow_bias": 0.45,
            "contact_shadow_length": 0.035,
        }
    )
    sun.set_temperature(daylight["temperature_k"])
    sun.set_light_source_angle(daylight["source_angle"])
    extended = bool(
        ue.SystemLibrary.get_console_variable_int_value(
            "r.DefaultFeature.AutoExposure.ExtendDefaultLuminanceRange"
        )
    )
    sun.set_intensity(daylight["sun_lux"] if extended else 8.0)
    spawn(ue.SkyAtmosphere)
    sky = spawn(ue.SkyLight, ue.Vector(0, 0, 700))
    sky.light_component.set_mobility(ue.ComponentMobility.MOVABLE)
    sky.light_component.set_editor_property("real_time_capture", True)
    sky.light_component.set_intensity(1.0)
    fog = spawn(ue.ExponentialHeightFog, ue.Vector(0, 0, -250)).get_component_by_class(
        ue.ExponentialHeightFogComponent
    )
    fog.set_fog_density(0.012)
    fog.set_start_distance(5500)
    fog.set_fog_height_falloff(0.22)
    volume = spawn(ue.PostProcessVolume)
    volume.set_actor_label("Takamatsu afternoon - driver exposure")
    volume.set_editor_property("unbound", True)
    settings = volume.get_editor_property("settings")
    # Retain the project's renderer/scalability. Keep adaptation bounded for a dark cab and bright plaza.
    for prop, value in {
        "auto_exposure_min_brightness": 10.0 if extended else 0.32,
        "auto_exposure_max_brightness": 15.5 if extended else 2.8,
        "auto_exposure_bias": 0.0,
        "bloom_intensity": 0.18,
        "vignette_intensity": 0.10,
        "motion_blur_amount": 0.04,
        "ambient_occlusion_intensity": 0.62,
        "screen_space_reflection_intensity": 55.0,
        "screen_space_reflection_max_roughness": 0.55,
    }.items():
        settings.set_editor_property("override_" + prop, True)
        settings.set_editor_property(prop, value)
    volume.set_editor_property("settings", settings)
    # The Japanese bay/route lettering is printed onto the physical sign mesh.
    # Place source credits on the back of its cabinet, clear of the driver's sightline.
    credit = spawn(ue.TextRenderActor, ue.Vector(*plan["sign"]), plan["board_yaw"])
    credit.set_actor_label(plan["attribution"])
    credit_text = credit.get_component_by_class(ue.TextRenderComponent)
    credit_text.set_horizontal_alignment(ue.HorizTextAligment.EHTA_CENTER)
    credit_text.set_text("© OpenStreetMap contributors | Kotoden GTFS")
    credit_text.set_world_size(2)
    if not assets.save_directory(folder, False, True) or not levels.save_current_level():
        raise RuntimeError("Could not save generated level and street mesh packages")
    if not levels.load_level(level):
        raise RuntimeError("Saved stage failed to reopen")
    world = ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world()
    if world.get_world_settings().get_editor_property("default_game_mode") != mode:
        raise RuntimeError("1086 drive mode assignment did not survive reload")
    starts = [actor for actor in actors.get_all_level_actors() if isinstance(actor, ue.PlayerStart)]
    if len(starts) != 1 or not ue.TakamatsuStreetMeshLibrary.check_departure_ground(
        starts[0], assets.load_asset(folder + "/SM_Asphalt")
    ):
        raise RuntimeError("Saved street collision check failed at the 1086 wheel positions")
    return level, [texture.get_name() for texture in textures.values()]


if __name__ == "__main__":
    run = Path(os.environ["KOTODEN_STAGE_RUN"])
    try:
        plan = json.loads((run.parent.parent / "plan.json").read_text(encoding="utf-8"))
        level, texture_names = import_stage(plan, os.environ["KOTODEN_STAGE_BUS"], "Build_" + run.name)
        report = {"status": "ok", "level": level, "layers": list(plan["meshes"]), "textures": texture_names}
    except Exception:
        report = {"status": "failed", "error": traceback.format_exc()}
        ue.log_error(report["error"])
    (run / "result.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
