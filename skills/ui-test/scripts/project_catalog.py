"""Refresh the project's SQLite index and offline HTML from saved stage originals."""
import argparse
from pathlib import Path
from ui_test_core.run_catalog import refresh_catalog

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    print(refresh_catalog(parser.parse_args().project))
