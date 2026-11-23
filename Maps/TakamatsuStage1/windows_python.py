"""Run UE's bundled Python separately from the editor and its installed packages."""

import runpy
import sys
from pathlib import Path

source = Path(__file__).resolve().parent
sys.path[:0] = [str(Path(sys.argv.pop(1)).resolve()), str(source)]
if sys.argv[1:] == ["--probe"]:
    try:
        import numpy
        import shapely

        ok = (
            sys.version_info[:2] == (3, 11)
            and hasattr(shapely, "constrained_delaunay_triangles")
            and numpy.__version__ == "1.26.4"
            and shapely.__version__ == "2.1.2"
        )
    except (ImportError, OSError):
        ok = False
    sys.exit(0 if ok else 1)
runpy.run_path(str(source / "prepare.py"), run_name="__main__")
