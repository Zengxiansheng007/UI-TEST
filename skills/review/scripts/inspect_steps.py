"""Read one UI test source from the selected suite and print the redacted delivery."""
import argparse
import json
from pathlib import Path

from ui_test_core.suite import selected_suite


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--run-root", type=Path, help="directory containing relative V5 evidence references")
    parser.add_argument("--original", type=Path, help="original observations or V5 when reviewing an index")
    args = parser.parse_args()
    try:
        capability = selected_suite().load_package("review")
        result = capability.review_file(args.source, run_root=args.run_root, original=args.original)
    except FileNotFoundError:
        parser.exit(2, "E_STEP_FILE_MISSING\n")
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
        code = str(exc).split(":", 1)[0]
        parser.exit(2, (code if code.startswith("E_") and code.replace("_", "").isalnum() else "E_STEP_SOURCE_INVALID") + "\n")
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
