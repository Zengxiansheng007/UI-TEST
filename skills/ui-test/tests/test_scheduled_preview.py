import json
from datetime import datetime,timedelta
from pathlib import Path
import pytest

from scripts.ui_test_core.preview_schedule import due_preview, task_definition


def test_login_catchup_reuses_current_period_and_failed_preview_retries(tmp_path):
    first = datetime(2026, 1, 8, 10)
    assert due_preview(tmp_path, first, now=first-timedelta(seconds=1)) is None
    policy = tmp_path / "governance-settings.json"
    policy.write_text('{"recent_per_branch":-1}')
    with pytest.raises(ValueError):
        due_preview(tmp_path, first, now=first)
    policy.write_text('{}')
    one = due_preview(tmp_path, first, now=first)
    assert due_preview(tmp_path, first, now=first+timedelta(days=29)) == one
    late = due_preview(tmp_path, first, now=first+timedelta(days=61))
    assert late != one and due_preview(tmp_path, first, now=first+timedelta(days=70)) == late
    assert len(list((tmp_path/"治理/清单").glob("*.json"))) == 2


def test_production_and_trial_triggers_share_only_the_readonly_preview_action(tmp_path):
    from xml.etree import ElementTree as ET
    ns = {"t":"http://schemas.microsoft.com/windows/2004/02/mit/task"}
    first = datetime(2026, 1, 8, 10)
    for trial,expected in [(False,["CalendarTrigger","LogonTrigger"]),(True,["TimeTrigger"])]:
        xml = ET.fromstring(task_definition(tmp_path, first, "S-1-5-21-10", trial=trial))
        assert [x.tag.split("}")[-1] for x in xml.find("t:Triggers",ns)] == expected
        assert xml.findtext(".//t:RunLevel",namespaces=ns) == "LeastPrivilege"
        assert xml.findtext(".//t:LogonType",namespaces=ns) == "InteractiveToken"
        assert "scheduled-preview" in xml.findtext(".//t:Arguments",namespaces=ns)
        assert xml.find(".//t:Exec/t:WorkingDirectory", ns) is None
        if not trial:
            assert xml.findtext(".//t:DaysInterval",namespaces=ns) == "30"


def test_windows_export_can_omit_default_limited_privilege(tmp_path):
    from xml.etree import ElementTree as ET
    from scripts.ui_test_core.preview_schedule import NAMESPACE, same_definition
    wanted = task_definition(tmp_path,datetime(2026,1,8),"S-1-5-21-10",trial=True)
    exported = ET.fromstring(wanted)
    principal = exported.find(".//{"+NAMESPACE+"}Principal")
    principal.remove(principal.find("{"+NAMESPACE+"}RunLevel"))
    assert same_definition(ET.tostring(exported),wanted)
    ET.SubElement(principal,"{"+NAMESPACE+"}RunLevel").text="HighestAvailable"
    assert not same_definition(ET.tostring(exported),wanted)
