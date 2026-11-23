"""Short-lived editor stage used only when no complete 1086 driving level exists."""
import json
import os
from pathlib import Path
import runpy
import traceback

import unreal as ue


def prepare():
    project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
    api = runpy.run_path(str(project / "scripts" / "import_kotoden1086.py"))
    root = project / "Content" / "Kotoden1086"
    # A usable local skeleton/Physics Asset is sufficient. Create only missing driving
    # infrastructure in a new folder; never save the old mesh or its materials.
    for directory in sorted(root.glob("Build_[0-9][0-9][0-9]"), reverse=True):
        for path in sorted(directory.glob("SK_Kotoden1086*.uasset")):
            mesh = ue.load_asset(f"/Game/Kotoden1086/{directory.name}/{path.stem}")
            if isinstance(mesh, ue.SkeletalMesh) and mesh.get_editor_property("physics_asset"):
                folder = api["new_folder"]()
                mode = api["create_driving_classes"](folder, mesh)
                return api["create_yard"](folder, mode)
    return api["run"]()  # Fresh installation into an unused numbered Build folder.


if __name__ == "__main__":
    report = Path(os.environ["KOTODEN_UPGRADE_RESULT"])
    try:
        level = prepare()
        if not level or not ue.EditorAssetLibrary.does_asset_exist(level):
            raise RuntimeError(f"Saved driving level could not be found: {level}")
        result = {"status": "ok", "level": level}
    except Exception:
        result = {"status": "failed", "error": traceback.format_exc()}
        ue.log_error(result["error"])
    report.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
