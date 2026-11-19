from ui_test_core.reuse_outcome import ReuseFailure


def unique_row(locator):
    count = locator.count()
    if count != 1:
        raise ReuseFailure("asset", f"source_row_matches_{count}")
    return locator


def check_target(ready, locator, before_check):
    row = ready(locator)
    before_check()  # A failed uniqueness check spends no checkbox action.
    row.get_by_role("checkbox").check()
