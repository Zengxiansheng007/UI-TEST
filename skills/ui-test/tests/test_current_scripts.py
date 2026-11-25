"""Project-local current scripts are distinct from the immutable copies of past attempts."""
import json
import sqlite3
from contextlib import closing

from scripts.ui_test_core.run_catalog import refresh_catalog


def test_two_nodes_in_unpublished_script_rename_and_source_disappearance(tmp_path):
    script = tmp_path / "test_cases.py"
    script.write_text("def test_first(): pass\ndef test_second(): pass\n", encoding="utf8")
    items = [dict(case_id=c, branch_id="main", display_name="查询", node_id=f"test_cases.py::test_{n}")
             for c,n in [("A","first"),("B","second")]]
    def publish():
        (tmp_path/"current-cases.json").write_text(json.dumps({"cases":items}),encoding="utf8")
        refresh_catalog(tmp_path)
        with closing(sqlite3.connect(tmp_path/"runs.sqlite3")) as db:
            return db.execute("SELECT case_id,display_name,status,entry FROM current_scripts ORDER BY case_id").fetchall()
    assert publish() == [("A","查询","current","test_cases.py"),("B","查询","current","test_cases.py")]
    items[0]["display_name"] = "新名称"
    script.write_text("def test_second(): pass\n", encoding="utf8")
    assert publish() == [("A","新名称","pending",None),("B","查询","current","test_cases.py")]
    assert "新名称" in (tmp_path/"index.html").read_text("utf8")
    script.unlink()
    assert all(row[2:] == ("missing",None) for row in publish())


def test_current_declarations_do_not_expose_private_or_ambiguous_entries(tmp_path):
    path = tmp_path/"test_case.py"
    path.write_text("@pytest.mark.case_id('A')\ndef test_row(): pass\n",encoding="utf8")
    valid = dict(case_id="A",branch_id="one",display_name="读取",node_id="test_case.py::test_row")
    rows = [valid, valid, dict(valid,case_id="B"),dict(valid,case_id="C",node_id="_PRIVATE/s.py::test_row")]
    (tmp_path/"current-cases.json").write_text(json.dumps(dict(cases=rows)),encoding="utf8")
    refresh_catalog(tmp_path)
    with closing(sqlite3.connect(tmp_path/"runs.sqlite3")) as db:
        assert db.execute("SELECT case_id,status,entry FROM current_scripts ORDER BY case_id").fetchall() == [
            ("A","pending",None), ("B","pending",None), ("C","pending",None)]
