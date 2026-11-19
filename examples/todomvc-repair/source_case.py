"""Original acceptance contract for the isolated public two-row case."""
from playwright.sync_api import expect

CASE = "TODO-REPAIR-002"
TARGET = "Read notes"
OTHER = "Read notes later"
BINDINGS = {CASE: ["script.complete"]}
SCOPE = dict(project_group="public-repair", product="todomvc", system="todomvc",
             module_path="todos", function="complete", checkpoint="two-items", case_id=CASE,
             environment="test", risk_level="r2-ui-write-test", step_id="COMPLETE")


def assert_rows(todo, *, complete):
    expect(todo.rows).to_have_count(2)
    for text, checked in ((TARGET, complete), (OTHER, False)):
        row = todo.rows.filter(has=todo.page.get_by_text(text, exact=True))
        expect(row).to_have_count(1)
        expect(row.get_by_role("checkbox")).to_be_checked(checked=checked)
    expect(todo.counter).to_have_text("1 item left" if complete else "2 items left")
