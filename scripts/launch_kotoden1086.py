"""Entry point used by -ExecutePythonScript when the Unreal Editor launches.

Writes a durable report for troubleshooting so the user does not need to copy an entire Output Log.
"""
import runpy
import traceback
from datetime import datetime
from pathlib import Path

import unreal as ue


def main():
    project = Path(ue.Paths.convert_relative_path_to_full(ue.Paths.project_dir()))
    output_dir = project / "Saved" / "Setup1086"
    output_dir.mkdir(parents=True, exist_ok=True)
    report = output_dir / "LatestImportResult.txt"
    importer = project / "scripts" / "import_kotoden1086.py"
    report.write_text(
        "RUNNING\n" + datetime.now().isoformat() + "\n" + str(importer),
        encoding="utf-8",
    )
    try:
        if not importer.is_file():
            raise FileNotFoundError(importer)
        runpy.run_path(str(importer), run_name="__main__")
    except Exception:
        details = traceback.format_exc()
        report.write_text(
            "FAILED\n" + datetime.now().isoformat() + "\n" + details,
            encoding="utf-8",
        )
        ue.log_error("KOTODEN 1086 IMPORT FAILED. See " + str(report))
        raise
    else:
        report.write_text(
            "SUCCESS\n" + datetime.now().isoformat()
            + "\nImport script returned normally. Confirm the new L_1086_Drive map and test in PIE.",
            encoding="utf-8",
        )
        ue.log("KOTODEN 1086 IMPORT SCRIPT COMPLETED. See " + str(report))


main()
