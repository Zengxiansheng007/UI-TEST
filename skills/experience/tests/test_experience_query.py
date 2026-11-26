import json

from ui_test_core.suite import selected_suite


def test_known_experience_with_original_source(tmp_path):
    suite = selected_suite()
    packet = json.loads((suite.root / "assets/experience-packet.example.json").read_bytes())
    (tmp_path / "candidate.json").write_text(json.dumps(packet))
    (tmp_path / "other.json").write_text("[]")
    owner = suite.load_package("experience")
    result = owner.query(tmp_path, packet["scope"])
    found, = result["records"]
    assert found["source_run_ids"] == ["RUN-EXAMPLE-001"]
    assert found["scope"] == packet["scope"] and found["experience_status"] == "candidate"
    assert found["evidence_refs"] == ["EV-EXAMPLE-001"] and found["source_step_ids"] == ["CP3"]
    assert result["calls"] == ["experience"] and result["business_attempts_added"] == 0
    assert owner.query(tmp_path, {"environment": "test"})["missing"]
    assert owner.query(tmp_path / "unknown", packet["scope"])["missing"]
    assert owner.query(tmp_path, dict(packet["scope"], environment="other"))["records"] == []

def test_scoped_strategy_candidate_from_project_store(tmp_path_factory):
    from ui_test_core.case_contracts import canonical_hash

    tmp_path = tmp_path_factory.mktemp("exp")  # Keep content-addressed filenames within the Windows path limit.
    scope = dict(project_group="team", product="demo", system="web", module_path=["form"],
                 function="next", checkpoint=None, environment="test", risk_level="read",
                 case_id="A", step_id="next")
    asset = {"id": "next-button", "version": 2}
    source = dict(run_id="R", session_id="S", attempt_ref="A", step_id="next", result_hash="H",
                  evidence_refs=["visible"])
    candidate = dict(scope=scope, asset=asset, build="buildA", source=source,
                     strategy="wait", pattern="success")
    folder = tmp_path / "reuse-experiences/candidates"
    folder.mkdir(parents=True)
    identity = canonical_hash(candidate).split(":")[-1]
    (folder / (identity + ".json")).write_text(json.dumps(candidate))
    owner = selected_suite().load_package("experience")
    result = owner.query(project=tmp_path, scope=scope, asset=asset, build="buildA")
    record, = result["records"]
    assert record["source"] == source and record["scope"] == scope and record["experience_id"] == identity
    assert record["experience_status"] == "candidate" and record["advisory_only"]
    assert owner.query(project=tmp_path, scope=scope, asset=asset, build="other")["records"] == []
