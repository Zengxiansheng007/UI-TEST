"""Run the selected checkpoint owner's original CLI regression."""
from pathlib import Path
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import checkpoint_runtime

owner = Path(checkpoint_runtime.__path__[0]).parents[1]
if __name__ == "__main__":
    runpy.run_path(str(owner / "tests/run_tests.py"), run_name="__main__")
