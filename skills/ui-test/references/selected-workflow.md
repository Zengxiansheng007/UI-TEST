# Running an approved multi-stage request

From the selected main Skill run `python scripts/ui_test_suite.py workflow REQUEST.json`. The returned request_sha256 identifies the exact request bytes. Without a matching approval argument the command returns before dispatch. Obtain the user's approval for the actual project, installed suite version, current Packet, URL, data, executable files, stage permissions, model exposure and budgets. A request hash binds that decision to the input. Computing a hash does not grant permission. For the approved request invoke:

```text
python scripts/ui_test_suite.py workflow REQUEST.json --approved-sha256 APPROVED_DIGEST
```

The caller reads the JSON status and reason even when the process exits normally. For a stopped workflow, return every completed delivery to the engineer. The test in `tests/test_selected_workflow.py` contains a runnable offline request and both continuation paths.

| Field | Content |
|---|---|
| project, suite | Absolute project root and explicitly selected main Skill directory. |
| scope | Approval reference under approval_ref, exact page, data, disclosure permissions, allowed actions and stage budgets. Keep the exploration authorization intact on continuation. |
| plan | kind of source or packet, file naming the project-relative source. A source invokes the plan producer. The resulting Packet must route to explore and its run.run_id must equal explore.run_id. |
| explore | Fresh run_id, project-relative Node runner, files mapping each reviewed project-relative input, helper and executable to its lowercase SHA-256. Include the planning material, runtime configuration and runner. |
| build (optional) | For an authorized compilation after exploration, supply approval_ref, observations_sha256, checks, display_name, source, test_data, dependencies, module_registry and files. Include ui-test.project.yaml. Optional runtime_material is a reviewed local file reference. The script-build owner returns its versioned release and script digest. |
| formal (optional) | Separate approval_ref, batch, checks, selected nodes, files and optionally the completed observations_sha256. Bind script, project configuration, hooks, dependencies and policy inputs. Each node record contains node (`file.py::test`), case_id and branch_id. Each check identifies case_id, branch_id, attempt_ref and step_id and gives expected fields for verify. |
| formal permissions | Serial by default. Pass parallel_intent only for the separately authorized complete node set and include it in files. For an authorized R2 formal batch use r2_approved=true and a project-relative write_budget_ref in files. Keep the project's existing pytest write gates and stage budget. |

The runner receives UI_TEST_PROJECT, UI_TEST_SUITE, UI_TEST_PYTHON, UI_TEST_EXPLORE_ENTRY and UI_TEST_EXPLORATION_RUN_ID. Run the approved checklist through the explore owner's runExplorationStage. The main entry reads the registered stage, observations, scoped evidence index and report from the project. In each step record the actual observed fields under observed or the read-back string in actual_result (verify uses a visible_text list in that case). Set expected independently in the approved check. Persist unknown writes as write_outcome_unknown and pause the affected case. Its dependent cases wait for confirmation of the original result. Independent exploration cases continue in verified separate top-level browser windows per the explore delivery contract. Return the exploration report for review before advancing to formal execution.

For an exploration-only approval omit formal. The result includes the exploration report and missing formal prerequisites. To continue an existing exploration keep project, suite, scope, plan and explore unchanged. Supply the reviewed checks, nodes and formal permissions in a newly approved request. If scripts must be generated first, use a separately approved build request, review its output and bind the selected script and dependencies by digest on the formal request. Project-local attempt claims prevent redispatch if a process terminates with an unknown outcome. Inspect that attempt before any future operation. An independent explore, verify or script-build invocation returns to its requester and starts zero formal attempts.

Formal submission uses the selected playwright-run owner and its existing pytest contracts. The returned stage ID, task journal, V5 summary and report let the caller verify node, case, branch, attempt and result identity. The exploration monitoring ID is passed to formal execution for the registered cross-stage link.

If an exploration ended on a known blocked case, return its reason and measured evidence. A separately authorized formal request may include reviewed_blockers equal to the returned case, branch, attempt and reason records. Verify only actually observed, successful steps for its selected nodes. Untouched or failed steps cannot qualify. An unknown outcome or unconfirmed executor exit continues to stop the flow.

For new R2 dispatches, bind a UTF-8 JSON budget with the following exact structure. Set task_ref to dispatch_task_ref(absolute_task_journal_path) from ui_test_core.artifact_layout. The workflow journal is the project's `临时/workflow/<exploration-run-id>/formal-task.json`. The batch must match the request. Each node appears at most once. Use the actual case and branch markers, and the project phase identifiers. Use `single` for a project with no staged policy. A count of 1 authorizes one reservation. A zero count, missing phase or absent node grants no write.

```json
{"schema_version":"ui-test.formal-write-budget.v1","task_ref":"CODEX-<task journal digest>","batch":"reviewed-batch","nodes":[{"node":"test_case.py::test_a","case_id":"CASE-A","branch_id":"main","phases":{"single":1}}]}
```

Each reservation remains spent even if the worker stops before recording a result. Unversioned budgets remain readable for a previously completed workflow with the same approved request. A new dispatch needs a reviewed v1 file and its digest.
