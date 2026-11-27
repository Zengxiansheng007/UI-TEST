"""Schedule only the project's retention preview using a logged-in Windows user token."""
import csv
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree as ET

from ui_test_core.asset_revision import encoded, replace
from ui_test_core.file_lock import exclusive_file_lock
from ui_test_core.path_planner import validate_existing_path_containment
from ui_test_core.path_utils import short_id
from .retention_preview import publish_preview

NAMESPACE = "http://schemas.microsoft.com/windows/2004/02/mit/task"


def due_preview(project, first_due, *, now=None):
    """Wall-clock dates match the local calendar and interactive logon triggers."""
    elapsed = (now or datetime.now()) - first_due
    if elapsed < timedelta(0):
        return None
    cycle = first_due + timedelta(days=30 * (elapsed.days // 30))
    return publish_preview(project, request_id="schedule:" + cycle.date().isoformat())


def task_definition(project, first_due, sid, *, trial=False):
    task = ET.Element("Task", version="1.2", xmlns=NAMESPACE)
    def add(parent, name, value=None, **attrs):
        child = ET.SubElement(parent, name, attrs)
        child.text = value
        return child
    triggers = add(task, "Triggers")
    trigger = add(triggers, "TimeTrigger" if trial else "CalendarTrigger")
    boundary = first_due.isoformat(timespec="seconds")
    add(trigger, "StartBoundary", boundary)
    if not trial:
        add(add(trigger, "ScheduleByDay"), "DaysInterval", "30")
        add(add(triggers, "LogonTrigger"), "UserId", sid)
    principal = add(add(task, "Principals"), "Principal", id="CurrentUser")
    add(principal, "UserId", sid)
    add(principal, "LogonType", "InteractiveToken")
    add(principal, "RunLevel", "LeastPrivilege")
    settings = add(task, "Settings")
    for name,value in (("MultipleInstancesPolicy","IgnoreNew"),("DisallowStartIfOnBatteries","false"),
                       ("StopIfGoingOnBatteries","false"),("StartWhenAvailable","true")):
        add(settings,name,value)
    action = add(add(task,"Actions",Context="CurrentUser"),"Exec")
    executable = Path(sys.executable).resolve()
    windowless = executable.with_name("pythonw.exe")
    add(action,"Command",str(windowless if windowless.is_file() else executable))
    from ui_test_core.suite import selected_suite
    entry = selected_suite().root / "scripts/project_governance.py"
    args = ["-B","-X","utf8", str(entry),"scheduled-preview",str(project),"--first-due",boundary]
    add(action,"Arguments",subprocess.list2cmdline(args))
    return ET.tostring(task, encoding="utf-16", xml_declaration=True)


def same_definition(saved, expected):
    """Compare the principal, triggers and complete action; Windows supplies other defaults."""
    def fields(raw):
        tree = ET.fromstring(raw)
        ns = {"t": NAMESPACE}
        value = lambda field: tree.findtext(".//t:" + field, namespaces=ns)
        triggers = [(node.tag, node.findtext("t:StartBoundary",namespaces=ns),
                     node.findtext("t:ScheduleByDay/t:DaysInterval",namespaces=ns),
                     node.findtext("t:UserId",namespaces=ns)) for node in tree.find("t:Triggers",ns)]
        enabled = [node.findtext("t:Enabled",default="true",namespaces=ns) for node in tree.find("t:Triggers",ns)]
        enabled.append(tree.findtext("t:Settings/t:Enabled",default="true",namespaces=ns))
        actions = [(a.tag, tuple((child.tag,child.text) for child in a)) for a in tree.find("t:Actions",ns)]
        principal = tree.find("t:Principals/t:Principal",ns)
        # Windows omits its default Limited run level when exporting registered tasks.
        return (principal.findtext("t:UserId",namespaces=ns),value("LogonType"),value("RunLevel") or "LeastPrivilege",
                value("DisallowStartIfOnBatteries"),value("StopIfGoingOnBatteries"),value("StartWhenAvailable"),
                triggers,enabled,actions)
    return fields(saved)==fields(expected)


def enable_schedule(project, *, trial_minutes=None):
    if os.name != "nt":
        raise ValueError("Windows Task Scheduler required")
    if trial_minutes is not None and trial_minutes < 1:
        raise ValueError("Test trigger must be in the future")
    root = Path(project).resolve(strict=True)
    system = Path(os.environ["SystemRoot"]) / "System32"
    identity = subprocess.check_output([str(system/"whoami.exe"),"/user","/fo","csv","/nh"], encoding="mbcs")
    sid = next(csv.reader(identity.splitlines()))[-1].strip()
    if not sid.startswith("S-1-"):
        raise ValueError("E_SCHEDULE_USER_IDENTITY")
    trial = trial_minutes is not None
    kind = "test" if trial else "periodic"
    name = "UI-Test-Preview-" + short_id(sid,os.path.normcase(str(root))) + "-" + kind
    folder = root / "治理" / "调度"
    state = folder / (kind+".json")
    xml = folder / (kind+".xml")
    lock = folder / ".register.lock"
    for path in (state, xml, lock):
        validate_existing_path_containment(root, path)
    with exclusive_file_lock(lock):
        if state.exists():
            record = json.loads(state.read_bytes())
            if record["task"] != name or record["project"] != str(root):
                raise ValueError("E_SCHEDULE_PROJECT_CONFLICT")
            first_due = datetime.fromisoformat(record["first_due"])
        else:
            interval = timedelta(minutes=trial_minutes) if trial else timedelta(days=30)
            first_due = (datetime.now()+interval).replace(microsecond=0)
            record = dict(task=name,project=str(root),first_due=first_due.isoformat(),mode=kind)
        expected = task_definition(root,first_due,sid,trial=trial)
        program = str(system/"schtasks.exe")
        existing = subprocess.run([program,"/query","/tn",name,"/xml"],capture_output=True)
        if existing.returncode == 0:
            # schtasks can write UTF-16 XML with a BOM or console-encoded Unicode text.
            raw = existing.stdout
            if raw.startswith(b"<?xml"):
                raw = raw.decode("mbcs")
            if not same_definition(raw, expected):
                raise ValueError("E_SCHEDULE_EXISTING_TASK_CONFLICT")
        else:
            replace(state,encoded(record))
            replace(xml,expected)
            subprocess.run([program,"/create","/tn",name,"/xml",str(xml)],check=True,
                           stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL)
        if not state.exists():
            replace(state,encoded(record))
    return record
