"""UE 5.5.4 editor process. Only publishes new packages in a unique Stage01 folder."""

import json
import os
import re
import traceback
from pathlib import Path

import unreal as ue

ROOT = "/Game/TakamatsuRoute/Stage01"
COLORS = {
    "Land": (0.21, 0.24, 0.17),
    "Asphalt": (0.075, 0.077, 0.075),
    "TurningApron": (0.17, 0.19, 0.18),  # Provisional turn safety, not real surveyed asphalt
    "Paving": (0.38, 0.34, 0.30),
    "Kerb": (0.56, 0.55, 0.51),
    "Paint": (0.9, 0.89, 0.77),
    "Buildings": (0.48, 0.47, 0.42),
    "Posts": (0.27, 0.28, 0.26),
    "SignalHousing": (0.075, 0.08, 0.07),
    "StopSign": (0.08, 0.40, 0.60),
    "Shelters": (0.23, 0.35, 0.39),
    "SignalLens": (0.08, 0.42, 0.25),
}
COLLIDING = {"Asphalt", "TurningApron", "Paving", "Buildings", "Land", "Shelters"}


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
    for name, data in plan["meshes"].items():
        rgb = COLORS[name]
        material = tools.create_asset("M_" + name, folder, ue.Material, ue.MaterialFactoryNew())
        edit = ue.MaterialEditingLibrary
        color = edit.create_material_expression(material, ue.MaterialExpressionConstant3Vector, 0, 0)
        color.set_editor_property("constant", ue.LinearColor(*rgb, 1))
        if not edit.connect_material_property(color, "", ue.MaterialProperty.MP_BASE_COLOR):
            raise RuntimeError("Material connection failed: " + name)
        edit.recompile_material(material)
        collides = name in COLLIDING
        mesh = ue.TakamatsuStreetMeshLibrary.create_street_mesh(
            folder + "/SM_" + name,
            [ue.Vector(*p) for p in data["vertices"]],
            data["triangles"],
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
    light = spawn(ue.DirectionalLight, ue.Vector(0, 0, 600), 135, -48)
    light.get_component_by_class(ue.DirectionalLightComponent).set_mobility(ue.ComponentMobility.MOVABLE)
    light.get_component_by_class(ue.DirectionalLightComponent).set_editor_property(
        "atmosphere_sun_light", True
    )
    spawn(ue.SkyAtmosphere)
    sky = spawn(ue.SkyLight, ue.Vector(0, 0, 600))
    sky.light_component.set_mobility(ue.ComponentMobility.MOVABLE)
    sky.light_component.set_editor_property("real_time_capture", True)
    sign = spawn(ue.TextRenderActor, ue.Vector(*plan["sign"]), yaw - 90)
    label = sign.get_component_by_class(ue.TextRenderComponent)
    bay = plan["survey"]["platform_evidence"]
    label.set_text("47  |  " + ("Takamatsu Sta." if "unverified" in bay else "5  Takamatsu Sta."))
    label.set_world_size(15)
    # Carry provenance in the level as well as the local source receipt.
    credit = spawn(ue.TextRenderActor, ue.Vector(x, y, z + 165), yaw + 180)
    credit.set_actor_label(plan["attribution"])
    credit_text = credit.get_component_by_class(ue.TextRenderComponent)
    credit_text.set_text("© OpenStreetMap contributors | Kotoden GTFS")
    credit_text.set_world_size(8)
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
    return level


if __name__ == "__main__":
    run = Path(os.environ["KOTODEN_STAGE_RUN"])
    try:
        plan = json.loads((run.parent.parent / "plan.json").read_text(encoding="utf-8"))
        level = import_stage(plan, os.environ["KOTODEN_STAGE_BUS"], "Build_" + run.name)
        report = {"status": "ok", "level": level, "layers": list(plan["meshes"])}
    except Exception:
        report = {"status": "failed", "error": traceback.format_exc()}
        ue.log_error(report["error"])
    (run / "result.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
