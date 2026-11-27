"""Only file creations stand in for UI effects in this controlled batch."""
import json
import os
from pathlib import Path

import pytest
from scripts.ui_test_core.case_contracts import canonical_hash
from test_stage_write_budget import session

pytestmark = [pytest.mark.ui_test, pytest.mark.branch_id("main"), pytest.mark.r2]


@pytest.mark.case_id("CASE-STAGES")
def test_a(ui_test_execution_context):
    ctx = ui_test_execution_context
    root = Path(os.environ["CONTROLLED_UI_EVIDENCE"]) / "runs" / ctx.run_id
    state = session(root, None, ctx.run_id)
    boundary = dict(run_id=ctx.run_id, case_id=ctx.case_id, environment=ctx.environment,
                    allowed_action=ctx.branch_id, channel="visible-ui", max_submit_count=1)
    approval = dict(boundary, schema_version="ui-test.r2-approval-record.v3", approval_id=ctx.run_id+"-approval",
                    approval_source=ctx.approval_source, node_id=ctx.node_id, branch_id=ctx.branch_id,
                    decision="approved", boundary_hash=canonical_hash(boundary), credential_values_persisted=False,
                    reusable_across_runs=False, risk_level=ctx.risk_level, runner_digest=ctx.runner_digest)
    (root/"approval.json").write_text(json.dumps(approval))
    state.authorize_business_write().consume()
    Path("first.clicked").touch()
    fresh = session(root/"second-session", None, ctx.run_id)
    with pytest.raises(ValueError, match="E_FORMAL_BUDGET_EXHAUSTED"):
        fresh.authorize_business_write().consume()
        Path("second.clicked").touch()
    Path("exhausted.checked").touch()
    (root/"observed.json").write_text(json.dumps(dict(write_state="write_succeeded_verified", submit_count=1)))


@pytest.mark.case_id("CASE-B")
def test_b(ui_test_execution_context):
    Path("unlisted.entered").touch()


@pytest.mark.case_id("CASE-C")
def test_c(ui_test_execution_context):
    os._exit(23)  # Simulate a worker interruption before it records the outcome.
