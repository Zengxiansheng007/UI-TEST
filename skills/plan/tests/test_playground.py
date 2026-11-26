import csv
from pathlib import Path
import unittest


class PlaygroundCoverageTests(unittest.TestCase):
    def test_all_sections_have_locatable_behaviors_and_independent_pending_phases(self):
        path = Path(__file__).resolve().parents[1] / "assets" / "playground-coverage.csv"
        with path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual([int(row["section"]) for row in rows], list(range(1, 53)))
        categories = {row["category"] for row in rows}
        self.assertEqual(len(categories), 9)
        self.assertEqual({row["category"] for row in rows if row["representative"] == "yes"}, categories)
        for row in rows:
            for field in ("target", "locator_basis", "action", "expected"):
                self.assertTrue(row[field], (row["section"], field))
            for phase in ("midscene", "playwright"):
                self.assertEqual(row[f"{phase}_status"], "pending")
                self.assertEqual(row[f"{phase}_actual"], "")
                self.assertEqual(row[f"{phase}_evidence"], "")
                self.assertTrue(row[f"{phase}_missing_reason"])
