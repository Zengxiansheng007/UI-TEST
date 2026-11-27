from test_selected_workflow import call, prepare, sha


def test_unknown_write_blocks_formal_even_after_review(tmp_path):
    request, formal = prepare(tmp_path)
    runner = tmp_path / "explore.cjs"
    runner.write_text(runner.read_text().replace("actual_result:'fixture title'",
        "actual_result:'No receipt',write_state:'write_outcome_unknown'"), encoding="utf8")
    request["explore"]["files"][runner.name] = sha(runner)
    request["formal"] = formal
    result = call(tmp_path, request)
    assert result["reason"] == "E_WORKFLOW_WRITE_OR_RESULT_UNKNOWN", result
    assert "explore" in result["deliveries"] and "playwright-run" not in result["deliveries"]
    assert len(list(tmp_path.rglob("report.html"))) == 1
