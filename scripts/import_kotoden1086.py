"""Run with Tools > Execute Python Script in the UE 5.5.4 editor."""

import json
from pathlib import Path

import unreal as ue


BASE_FOLDER = "/Game/Kotoden1086"
ASSETS = ue.EditorAssetLibrary
MATERIALS = ue.MaterialEditingLibrary


def new_folder():
    for build in range(1, 1000):
        path = f"{BASE_FOLDER}/Build_{build:03d}"
        if not ASSETS.does_directory_exist(path):
            if ASSETS.make_directory(path):
                return path
            raise RuntimeError(f"Cannot create {path}")
    raise RuntimeError("No unused 1086 build folder available")


def make_asset(folder, name, cls, factory):
    obj = ue.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, cls, factory)
    if not obj:
        raise RuntimeError(f"Cannot create {folder}/{name}")
    return obj


def import_bus_mesh(folder, source, world):
    options = ue.FbxImportUI()
    options.set_editor_properties({
        "automated_import_should_detect_type": False,
        "mesh_type_to_import": ue.FBXImportType.FBXIT_SKELETAL_MESH,
        "original_import_type": ue.FBXImportType.FBXIT_SKELETAL_MESH,
        "import_as_skeletal": True, "import_mesh": True, "import_animations": False,
        "create_physics_asset": False, "import_materials": False, "import_textures": False,
    })
    # Exported FBX numbers already use +X nose, +Z up and centimetres.
    # The legacy importer performs the right-to-left-handed Y conversion.
    options.skeletal_mesh_import_data.set_editor_properties({
        "convert_scene": False, "force_front_x_axis": False, "convert_scene_unit": True,
        "import_uniform_scale": 1.0,
        "normal_import_method": ue.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS,
    })
    task = ue.AssetImportTask()
    task.set_editor_properties({
        "filename": str(source), "destination_path": folder,
        "destination_name": "SK_Kotoden1086", "automated": True, "save": False,
        "replace_existing": False, "factory": ue.FbxFactory(), "options": options,
    })
    # FbxImportUI is a legacy importer option; temporarily select that importer for FBX.
    switch = "Interchange.FeatureFlags.Import.FBX"
    old_value = ue.SystemLibrary.get_console_variable_int_value(switch)
    try:
        ue.SystemLibrary.execute_console_command(world, f"{switch} 0")
        if ue.SystemLibrary.get_console_variable_int_value(switch) != 0:
            raise RuntimeError("Could not select the legacy FBX importer")
        ue.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    finally:
        ue.SystemLibrary.execute_console_command(world, f"{switch} {old_value}")
    meshes = [obj for obj in task.get_objects() if isinstance(obj, ue.SkeletalMesh)]
    if len(meshes) != 1:
        raise RuntimeError(f"Expected one skinned bus, imported {len(meshes)}; see FBX log")
    return meshes[0]


def master_material(folder, translucent):
    material = make_asset(folder, "M_Glass" if translucent else "M_Paint",
                          ue.Material, ue.MaterialFactoryNew())
    if translucent:
        material.set_editor_properties({
            "blend_mode": ue.BlendMode.BLEND_TRANSLUCENT, "two_sided": True,
            "translucency_lighting_mode": ue.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING,
        })
    MATERIALS.set_material_usage(material, ue.MaterialUsage.MATUSAGE_SKELETAL_MESH)
    prop = ue.MaterialProperty

    def parameter(name, scalar, y, output=None):
        cls = ue.MaterialExpressionScalarParameter if scalar else ue.MaterialExpressionVectorParameter
        node = MATERIALS.create_material_expression(material, cls, -650, y)
        node.set_editor_property("parameter_name", name)
        if output is not None and not MATERIALS.connect_material_property(node, "", output):
            raise RuntimeError(f"Material connection failed: {name}")
        return node

    color = parameter("BaseColor", False, 0, prop.MP_BASE_COLOR)
    parameter("Metallic", True, 160, prop.MP_METALLIC)
    parameter("Roughness", True, 300, prop.MP_ROUGHNESS)
    glow = parameter("Glow", True, 450)
    multiply = MATERIALS.create_material_expression(material, ue.MaterialExpressionMultiply, -290, 455)
    if not (MATERIALS.connect_material_expressions(color, "", multiply, "A")
            and MATERIALS.connect_material_expressions(glow, "", multiply, "B")
            and MATERIALS.connect_material_property(multiply, "", prop.MP_EMISSIVE_COLOR)):
        raise RuntimeError("Material emission connection failed")
    if translucent:
        parameter("Opacity", True, 600, prop.MP_OPACITY)
    MATERIALS.recompile_material(material)
    return material


def assign_surface_materials(folder, mesh, palette):
    masters = {kind: master_material(folder, kind) for kind in (False, True)}
    instances = {}
    slots = list(mesh.get_editor_property("materials"))
    if not slots:
        raise RuntimeError("Imported bus has no material slots")
    for slot in slots:
        name = str(slot.get_editor_property("imported_material_slot_name"))
        if name not in palette:
            name = str(slot.get_editor_property("material_slot_name"))
        if name not in palette:
            raise RuntimeError(f"FBX material '{name}' is missing from Bus1086.json")
        if name not in instances:
            entry = palette[name]
            glass = entry["alpha"] < 1.0
            instance = make_asset(folder, f"MI_{name}", ue.MaterialInstanceConstant,
                                  ue.MaterialInstanceConstantFactoryNew())
            MATERIALS.set_material_instance_parent(instance, masters[glass])
            MATERIALS.set_material_instance_vector_parameter_value(
                instance, "BaseColor", ue.LinearColor(*entry["rgb"], 1.0))
            scalars = {"Metallic": entry["metallic"], "Roughness": entry["roughness"], "Glow": entry["emission"]}
            if glass:
                scalars["Opacity"] = entry["alpha"]
            for key, value in scalars.items():
                MATERIALS.set_material_instance_scalar_parameter_value(instance, key, value)
            MATERIALS.update_material_instance(instance)
            instances[name] = instance
        slot.set_editor_property("material_interface", instances[name])
    mesh.set_editor_property("materials", slots)


def make_blueprint(folder, name, native_name):
    parent = ue.load_class(None, f"/Script/KotodenBusSimulator.{native_name}")
    if not parent:
        raise RuntimeError(f"Build the Development Editor target first; missing class {native_name}")
    factory = ue.BlueprintFactory()
    factory.set_editor_property("parent_class", parent)
    return make_asset(folder, name, ue.Blueprint, factory)


def save_and_reload_blueprint(bp):
    path = bp.get_path_name()
    if not ASSETS.save_loaded_asset(bp, False):
        raise RuntimeError(f"Cannot save {path}")
    # Reload only the new Blueprint. Validate serialized defaults before referencing it in a level.
    reloaded, error = ue.EditorLoadingAndSavingUtils.reload_packages(
        [ASSETS.get_package_for_object(bp)], ue.ReloadPackagesInteractionMode.ASSUME_NEGATIVE)
    if not reloaded:
        raise RuntimeError(f"Cannot reload {path}: {error}")
    return ue.load_asset(path)


def create_driving_classes(folder, mesh):
    bus_bp = make_blueprint(folder, "BP_Kotoden1086", "Kotoden1086Pawn")
    ue.BlueprintEditorLibrary.compile_blueprint(bus_bp)
    bus_cdo = ue.get_default_object(bus_bp.generated_class())
    bus_cdo.modify()
    bus_cdo.set_editor_property("bus_mesh_asset", mesh)
    component = bus_cdo.get_component_by_class(ue.SkeletalMeshComponent)
    if not component:
        raise RuntimeError("Bus Blueprint has no chassis skeletal mesh component")
    component.modify()
    component.set_skeletal_mesh_asset(mesh)
    # The bus has a native display component and does not need an animation Blueprint.
    component.set_collision_profile_name("Vehicle")
    body = component.get_editor_property("body_instance")
    body.set_editor_property("simulate_physics", True)
    component.set_editor_property("body_instance", body)
    bus_bp = save_and_reload_blueprint(bus_bp)
    restored = ue.get_default_object(bus_bp.generated_class())
    if restored.get_editor_property("bus_mesh_asset") != mesh:
        raise RuntimeError("Bus mesh assignment did not survive Blueprint save/reload")
    mode_bp = make_blueprint(folder, "BP_KotodenDriveMode", "BusInputGameMode")
    ue.BlueprintEditorLibrary.compile_blueprint(mode_bp)
    mode = ue.get_default_object(mode_bp.generated_class())
    mode.modify()
    mode.set_editor_property("default_pawn_class", bus_bp.generated_class())
    mode_bp = save_and_reload_blueprint(mode_bp)
    if ue.get_default_object(mode_bp.generated_class()).get_editor_property("default_pawn_class") != bus_bp.generated_class():
        raise RuntimeError("GameMode did not retain the bus pawn class")
    return mode_bp


def create_yard(folder, mode_bp):
    level_editor = ue.get_editor_subsystem(ue.LevelEditorSubsystem)
    level_path = f"{folder}/L_1086_Drive"
    if not level_editor.new_level(level_path):
        raise RuntimeError(f"Cannot create {level_path}")
    world = ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world()
    actors = ue.get_editor_subsystem(ue.EditorActorSubsystem)
    settings = world.get_world_settings()
    settings.set_editor_property("default_game_mode", mode_bp.generated_class())
    cube = ue.load_asset("/Engine/BasicShapes/Cube")
    floor = actors.spawn_actor_from_class(ue.StaticMeshActor, ue.Vector(0, 0, -25))
    floor.set_actor_label("Flat driving yard (200 m)")
    floor.static_mesh_component.set_static_mesh(cube)
    floor.static_mesh_component.set_collision_profile_name("BlockAll")
    floor.set_actor_scale3d(ue.Vector(200, 200, 0.5))

    # Posts outside the straight reference lane make speed and steering visible.
    for x in range(-6000, 6001, 1000):
        for y in (-430, 430):
            post = actors.spawn_actor_from_class(ue.StaticMeshActor, ue.Vector(x, y, 40))
            post.static_mesh_component.set_static_mesh(cube)
            post.static_mesh_component.set_collision_profile_name("NoCollision")
            post.set_actor_scale3d(ue.Vector(0.12, 0.12, 0.8))

    actors.spawn_actor_from_class(ue.PlayerStart, ue.Vector(-5500, 0, 125))
    sun = actors.spawn_actor_from_class(ue.DirectionalLight, ue.Vector(0, 0, 600),
                                       ue.Rotator(roll=0, pitch=-48, yaw=135))
    sunlight = sun.get_component_by_class(ue.DirectionalLightComponent)
    sunlight.set_mobility(ue.ComponentMobility.MOVABLE)
    sunlight.set_editor_property("atmosphere_sun_light", True)
    actors.spawn_actor_from_class(ue.SkyAtmosphere, ue.Vector(0, 0, 0))
    skylight = actors.spawn_actor_from_class(ue.SkyLight, ue.Vector(0, 0, 600))
    skylight.light_component.set_mobility(ue.ComponentMobility.MOVABLE)
    skylight.light_component.recapture_sky()
    if not level_editor.save_current_level():
        raise RuntimeError(f"Cannot save {level_path}")
    return level_path


def run():
    if not ue.SystemLibrary.get_engine_version().startswith("5.5.4"):
        raise RuntimeError("Use UE 5.5.4 for this import")
    if ue.EditorLoadingAndSavingUtils.get_dirty_map_packages() or ue.EditorLoadingAndSavingUtils.get_dirty_content_packages():
        raise RuntimeError("Save or discard your unsaved editor changes before importing the bus")
    assets = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir())) / "Art" / "Bus1086"
    data = json.loads((assets / "Bus1086.json").read_text(encoding="utf-8"))
    source = assets / "Bus1086.fbx"
    if not source.is_file():
        raise FileNotFoundError(source)
    if not hasattr(ue, "Kotoden1086ImportLibrary"):
        raise RuntimeError("Build the KotodenBusSimulatorEditor target before running this script")

    folder = new_folder()
    ue.log(f"1086 import: writing new assets to {folder}")
    world = ue.get_editor_subsystem(ue.UnrealEditorSubsystem).get_editor_world()
    mesh = import_bus_mesh(folder, source, world)
    expected = {name: ue.Vector(100*x, -100*y, 100*z) for name, (x, y, z) in data["bones"].items()}
    chassis = ue.Kotoden1086ImportLibrary.create_chassis(mesh, expected)
    if not chassis:
        raise RuntimeError("Chassis creation failed; see LogTemp for the first failing bone or package")
    assign_surface_materials(folder, mesh, data["materials"])
    if not ASSETS.save_directory(folder, False, True):
        raise RuntimeError(f"Cannot save generated assets in {folder}")
    mode_bp = create_driving_classes(folder, mesh)
    level = create_yard(folder, mode_bp)
    ue.log(f"1086: open {level} and press Play. Original assets are unchanged.")


if __name__ == "__main__":
    run()
