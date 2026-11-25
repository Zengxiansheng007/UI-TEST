"""Read project-scoped artifact sizes and reference ownership without consulting archive media."""
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.request import url2pathname

from .legacy_inventory import CONFIG as LEGACY_CONFIG
from .artifact_layout import ProjectLayout
from .asset_revision import AssetCatalog
from .case_contracts import canonical_hash
from .migration_cleanup import classify_asset
from .path_planner import validate_existing_path_containment
from .strict_json import load_strict_json
from .stage_events import replay_stage

PRIVATE = {"_private", ".git", ".codex", ".aws", ".ssh", "runtime-values", "storage-state.json",
           "storagestate.json", "credential-index.yaml", "runtime-value-index.yaml"}
DEFAULT_ROOTS = ("用例", "运行", "临时", "版本")
LABELS = {"report":"阶段报告", "stage":"阶段记录", "execution":"执行记录", "evidence":"证据",
          "version":"脚本与版本", "asset":"共享资产", "legacy":"历史资料", "temporary":"临时文件",
          "cache":"缓存", "plan":"用例与计划", "related":"修复、恢复与交接", "unknown":"未识别文件"}


def private(path):
    return any(p.casefold() in PRIVATE or p.casefold() == ".env" or p.casefold().startswith(".env.")
               for p in path.parts)


class ReportReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images, self.urls = [], []
        self.base = None

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "base":
            if self.base is None:
                self.base = attrs.get("href")
            return
        if attrs.get("data-image-metadata"):
            self.images.append(json.loads(attrs["data-image-metadata"]))
        for key in ("href", "src"):
            value = attrs.get(key)
            if value and not value.startswith(("#","data:")):
                self.urls.append(value)


class ProjectInventory:
    def __init__(self, project, archived_files=None):
        self.root = Path(project).resolve(strict=True)
        self.archived_files = archived_files or {}  # Only verified, previously released paths supplied by recovery.
        self.files, self.stages, self.issues = {}, {}, []
        self.versions = defaultdict(list)
        self.related = defaultdict(list)
        settings = self.settings("governance-settings.json")
        old = self.settings(LEGACY_CONFIG).get("directories", [])
        extra = settings.get("inventory_roots", [])
        if not isinstance(old,list) or not isinstance(extra,list):
            raise ValueError("E_INVENTORY_ROOTS")
        self.legacy = {self.directory(p) for p in old}
        self.roots = {self.directory(p) for p in (*DEFAULT_ROOTS,*extra)} | self.legacy
        batches = settings.get("legacy_batches", {})
        if not isinstance(batches, dict):
            raise ValueError("E_INVENTORY_LEGACY_BATCH")
        self.batches = {key:self.directory(path) for key,path in batches.items()}
        if any(not key.strip() or not any(path.is_relative_to(old) for old in self.legacy)
               for key,path in self.batches.items()):
            raise ValueError("E_INVENTORY_LEGACY_BATCH")
        if any(left != right and a.is_relative_to(b) for left, a in self.batches.items()
               for right, b in self.batches.items()):
            raise ValueError("E_INVENTORY_LEGACY_BATCH_OVERLAP")
        original = settings.get("original_project_root")
        self.original = Path(original) if original else None
        if self.original and not self.original.is_absolute():
            raise ValueError("E_INVENTORY_ORIGINAL_ROOT")

    def settings(self, name):
        file = self.root / name
        validate_existing_path_containment(self.root,file)
        result = load_strict_json(file) if file.is_file() else {}
        if not isinstance(result, dict):
            raise ValueError("E_INVENTORY_SETTINGS")
        return result

    def directory(self, value):
        if not isinstance(value,str) or not value.strip():
            raise ValueError("E_INVENTORY_ROOT")
        rel = Path(value)
        if not rel.parts or rel.anchor or ".." in rel.parts or private(rel) or rel.parts[0]=="治理":
            raise ValueError("E_INVENTORY_ROOT")
        path = self.root / rel
        validate_existing_path_containment(self.root,path)
        return path

    def scan(self):
        for base in sorted(self.roots):
            if not base.is_dir():
                continue
            def walk_error(error):
                self.issues.append(dict(path=Path(error.filename).relative_to(self.root).as_posix(),reason="目录无法读取"))
            for current, dirs, names in os.walk(base,onerror=walk_error):
                here = Path(current)
                dirs[:] = [d for d in dirs if self.allowed(here/d)]
                for name in names:
                    self.scan_file(here/name)
        for path in self.archived_files:
            if any(path.is_relative_to(base) for base in self.roots):
                self.scan_file(path)

    def source(self, path):
        return self.archived_files.get(path,path)

    def scan_file(self, path):
        if path in self.files or not self.allowed(path):
            return
        rel = path.relative_to(self.root).as_posix()
        if classify_asset(rel) == "cache":
            category = "cache"
        elif any(path.is_relative_to(folder) for folder in self.legacy):
            category = "legacy"
        elif path.is_relative_to(self.root/"临时"):
            category = "temporary"
        elif path.is_relative_to(self.root/"版本") or ("releases" in path.parts and path.suffix == ".py"):
            category = "version"
        elif path.name in {"case.json", "plan.json", "source-case.json"}:
            category = "plan"
        elif path.parent.name in {"修复", "恢复", "交接"} and path.suffix == ".json":
            category = "related"
        else:
            category = "unknown"
        try:
            size = self.source(path).stat().st_size
        except OSError:
            self.issues.append(dict(path=rel,reason="盘点时文件不可读取"))
            return
        self.files[path] = dict(path=rel,size=size,category=category,consumers=[],
                                legacy_batches=sorted(k for k,v in self.batches.items() if path.is_relative_to(v)))
        if category == "related":
            self.related[path.parent.parent].append(path)

    def allowed(self, path):
        if private(path.relative_to(self.root)):
            return False
        try:
            validate_existing_path_containment(self.root,path)
            return True
        except (OSError,ValueError):
            self.issues.append(dict(path=path.relative_to(self.root).as_posix(),reason="重解析点或路径不可读"))
            return False

    def check_named_batches(self):
        valid = dict(self.batches)
        for path, row in self.files.items():
            if path.name != "stage.json" or not row["legacy_batches"]:
                continue
            try:
                sid = load_strict_json(self.source(path))["stage_id"]
            except (OSError, TypeError, KeyError, ValueError):
                sid = None
            for batch in row["legacy_batches"]:
                if sid != batch or path.parent != self.batches[batch]:
                    valid.pop(batch, None)
                    self.issues.append(dict(stage_id=sid,legacy_batch=batch,path=row["path"],
                                            reason="点名批次与阶段身份不一致或无法核实"))
        for row in self.files.values():
            row["legacy_batches"] = [key for key in row["legacy_batches"] if key in valid]
        self.batches = valid

    def bind(self, base, ref, owner, role):
        if not isinstance(ref,str) or not ref:
            return None
        path = Path(os.path.abspath(base / ref))  # References belong to their originating contract's base.
        if self.original and path.is_relative_to(self.original) and not path.is_relative_to(self.root):
            path = self.root / path.relative_to(self.original)
        consumer = {**owner,"role":role}
        if not path.is_relative_to(self.root) or private(path.relative_to(self.root)):
            self.issues.append(dict(**consumer,reason="引用超出盘点范围"))
            return None
        row = self.files.get(path)
        if row is None:
            reason = "引用缺件" if any(path.is_relative_to(p) for p in self.roots) else "引用未在配置范围"
            self.issues.append(dict(**consumer,path=path.relative_to(self.root).as_posix(),reason=reason))
            return None
        if consumer not in row["consumers"]:
            row["consumers"].append(consumer)
        if row["category"] in {"unknown","temporary","cache","legacy"} or (row["category"] == "evidence" and role in {"report","stage","version"}):
            row["category"]=role
        return path

    def report(self, path, owner, cases=()):
        parsed = ReportReferences()
        parsed.feed(self.source(path).read_text("utf-8-sig", errors="replace"))
        for meta in parsed.images:
            fields = {k:meta[k] for k in ("case_id","branch_id","attempt_ref","step_id") if meta.get(k)}
            if fields.get("case_id") and not fields.get("branch_id"):
                branches = {case["branch_id"] for case in cases if case["case_id"] == fields["case_id"]
                            and any(a["attempt_ref"] == fields.get("attempt_ref") for a in case["attempts"])}
                if len(branches) == 1:
                    fields["branch_id"] = branches.pop()
            self.bind(path.parent,meta.get("path"),{**owner,**fields},"evidence")
        base = urljoin(path.as_uri(),parsed.base or "")
        for raw in parsed.urls:
            url = urlsplit(urljoin(base,raw))
            if url.scheme=="file" and url.netloc in {"","localhost"}:
                target = Path(url2pathname(url.path))
                if url.fragment.startswith("stage-") and (target == self.root / "index.html" or
                        (self.original and target == self.original / "index.html")):
                    continue  # The generated catalog is a navigation route, not an original owned by this stage.
                self.bind(path.parent,str(target),owner,"evidence")

    def attempt(self, stage, owner, attempt):
        binding = attempt.get("binding") or {}
        if binding:
            for item in [binding, *binding.get("dependencies", [])]:
                self.bind(self.root, item.get("entry"), owner, "version")
        execution = self.bind(self.root,attempt.get("execution_ref"),owner,"execution")
        self.bind(self.root,attempt.get("evidence_ref"),owner,"evidence")
        if not execution or execution.suffix.lower()!=".json":
            return
        data = load_strict_json(self.source(execution))
        if not isinstance(data,dict):
            return
        if data.get("schema_version")=="ui-test.run-result.v5":
            if execution.parent.name=="objects" and execution.parent.parent.name=="finalization":
                base = execution.parents[2]
            else:
                base = execution.parent
            self.bind(base, data.get("resolved_test_data_ref"), owner, "evidence")
            self.bind(base, data.get("approval_ref"), owner, "evidence")
            if data.get("transaction_id") and execution.parent.parent.name == "finalization":
                for name in ("finalization-commit.json","finalization-receipt.json"):
                    self.bind(execution.parent.parent, name, owner, "execution")
            context = data.get("execution_context_ref")
            if context:
                candidates = self.contexts.get(Path(context).parent.name, [])
                matches = [path for path in candidates if path.parts[-len(Path(context).parts):] == Path(context).parts
                           and canonical_hash(load_strict_json(self.source(path))) == data.get("execution_context_hash")]
                if len(matches) == 1:
                    self.bind(self.root, str(matches[0]), owner, "execution")
                else:
                    self.issues.append(dict(**owner,path=context,reason="执行上下文引用缺失或无法唯一核实"))
            for ref in data.get("evidence_refs",[]):
                self.bind(base,ref,owner,"evidence")
            for step in data.get("step_results",[]):
                scoped = {**owner,"step_id":step["step_id"]}
                for ref in step.get("evidence_refs",[]):
                    self.bind(base,ref,scoped,"evidence")
        elif stage["stage_type"] == "midscene":
            if data.get("stage") == "midscene" and data.get("run_id") == stage["stage_id"]:
                cases = data.get("cases", [])
            else:
                cases = [data["observation"]] if "observation" in data else []
            base = (execution.parent.parent if execution.parent.name == "events" else execution.parent)
            for case in cases:
                identity=(case.get("case_id"), case.get("branch_id",case.get("case_id")), case.get("attempt_ref"))
                if identity!=(owner["case_id"],owner["branch_id"],owner["attempt_ref"]):
                    continue
                for step in case.get("steps",[]):
                    scoped={**owner,"step_id":step.get("step_id")}
                    images = step.get("images") or ([step["ui_evidence"]] if step.get("ui_evidence") else [])
                    for image in images:
                        self.bind(base,image.get("path"),scoped,"evidence")
                        capture_id = image.get("capture_id")
                        if isinstance(capture_id, str) and re.fullmatch(r"[0-9a-f-]{36}",capture_id):
                            self.bind(base,"images/" + capture_id + ".json",scoped,"evidence")

    def stage(self, path):
        native = path.parent.parent == self.root / "运行"
        stage = (replay_stage(self.root,path.parent,archived_files=self.archived_files)
                 if native else load_strict_json(self.source(path)))
        sid = stage["stage_id"]
        if (path.parent.parent == self.root/"运行" and
                ProjectLayout(self.root).run_dir(stage["stage_type"],sid) != path.parent):
            raise ValueError("E_INVENTORY_STAGE_PATH")
        if sid in self.stages:
            self.issues.append(dict(stage_id=sid,path=path.relative_to(self.root).as_posix(),reason="相同阶段号有多份记录"))
            raise ValueError("E_INVENTORY_STAGE_ID_COLLISION")
        owner = {"stage_id":sid}
        legacy = any(path.is_relative_to(folder) for folder in self.legacy)
        named = self.batches.get(sid) == path.parent
        summary = {key: stage.get(key) for key in ("stage_id", "stage_type", "status", "started_at", "ended_at")}
        summary.update(source_ref=path.relative_to(self.root).as_posix(),cases=[],
                       disposition_scope=("named_legacy" if named else "inventory_only") if legacy else "stage")
        self.stages[sid] = summary
        origin = stage.get("origin") or {}
        if origin.get("kind") == "exploration":
            summary["origin"] = dict(kind="exploration",stage_id=origin["stage_id"])
            for key in ("report", "observations"):
                linked = self.bind(self.root,origin.get(key),dict(**owner,linked_stage_id=origin["stage_id"]),"evidence")
                if key=="report" and linked:
                    self.report(linked,dict(**owner,linked_stage_id=origin["stage_id"]))
        self.bind(self.root,path.as_posix(),owner,"stage")
        if native:
            start = path.parent / "start.json"
            if start in self.files:
                self.bind(path.parent, "start.json", owner, "stage")
                for event in self.events[path.parent]:
                    case_id, branch_id, attempt_ref = load_strict_json(self.source(event))["identity"]
                    identity = dict(**owner,case_id=case_id,branch_id=branch_id,attempt_ref=attempt_ref)
                    self.bind(event.parent,event.name,identity,"execution")
        report = self.bind(self.root,stage.get("report_ref"),owner,"report")
        summary["report_ref"] = self.files[report]["path"] if report else None
        if report:
            self.report(report,owner,stage["cases"])
        for name,role in (("execution-summary.json","execution"),("evidence-index.json","evidence")):
            candidate = path.parent/name
            if candidate in self.files:
                self.bind(path.parent,name,owner,role)
        for candidate in self.related[path.parent]:
            self.bind(candidate.parent, candidate.name, owner, "related")
            self.bind(candidate.parent,load_strict_json(self.source(candidate)).get("source"),owner,"related")
        for case in stage["cases"]:
            attempts = [{key: a.get(key) for key in ("attempt_ref", "status", "version")} for a in case["attempts"]]
            summary["cases"].append(dict(case_id=case["case_id"],branch_id=case["branch_id"],
                                         status=case.get("status"),attempts=attempts))
            if report:
                self.bind(self.root,stage["report_ref"],dict(**owner,case_id=case["case_id"],branch_id=case["branch_id"]),"report")
            for attempt in case["attempts"]:
                scoped = dict(stage_id=sid,case_id=case["case_id"],branch_id=case["branch_id"],
                              attempt_ref=attempt["attempt_ref"])
                if attempt.get("version"):
                    self.versions[(case["case_id"],case["branch_id"],attempt["version"])].append(scoped)
                self.attempt(stage,scoped,attempt)

    def assets(self):
        catalog = self.settings("reuse-project.json")
        declarations = dict(catalog.get("assets",{}))
        directory = self.root / catalog.get("directory", ".")
        for sidecar in sorted(p for p in self.files if p.name.endswith(".asset.json") and p.is_relative_to(directory)):
            for aid in load_strict_json(self.source(sidecar)).get("assets",{}):
                if aid in declarations:
                    self.issues.append(dict(asset_id=aid,reason="共享资产有多份声明"))
                # Sidecars alone describe unapproved candidates, not active consumers.
        state_pointer = self.root / ".reuse-state/current.json"
        validate_existing_path_containment(self.root,state_pointer)
        if state_pointer.is_file():
            sha = load_strict_json(state_pointer)["sha256"]
            if not re.fullmatch("[a-f0-9]{64}",sha):
                raise ValueError("E_INVENTORY_ASSET_STATE")
            validate_existing_path_containment(self.root,state_pointer.parent/"records"/sha[:32])
            declarations.update(AssetCatalog(self.root).state()["assets"])
        def bind_asset(asset, owner, steps):
            for base,ref in ((self.root / catalog.get("directory","."),asset.get("source")),(self.root,asset.get("recovery_source"))):
                if not ref:
                    continue
                file = Path(os.path.abspath(base/ref))
                if file.is_relative_to(self.root) and self.allowed(file) and file.is_file() and file not in self.files:
                    self.files[file] = dict(path=file.relative_to(self.root).as_posix(),size=file.stat().st_size,
                                            category="asset",consumers=[],legacy_batches=[])
                for step_id in steps or [None]:
                    self.bind(base,ref,{**owner,"step_id":step_id},"asset")
        if (self.root / "current-cases.json").is_file():
            from .current_scripts import current_scripts
            from .legacy_inventory import discover_legacy
            for row in current_scripts(self.root, discover_legacy(self.root)):
                if row["source"] == "current-cases.json" and row["status"] == "current":
                    owner = dict(asset_id="active-script",case_id=row["case_id"],branch_id=row["branch_id"])
                    bind_asset(dict(recovery_source=row["entry"]), owner, [])
        for aid, asset in sorted(declarations.items()):
            if asset.get("enabled") is not True:
                continue
            owner = dict(asset_id=aid,version=asset.get("version"))
            bind_asset(asset, owner, asset.get("steps"))
            pending, seen = list(asset.get("dependencies", [])), {aid}
            while pending:
                key = pending.pop()
                if key in seen:
                    continue
                seen.add(key)
                dependency = declarations.get(key)
                if not dependency:
                    self.issues.append(dict(**owner,dependency_id=key,reason="共享资产依赖无法核实"))
                    continue
                bind_asset(dependency, dict(**owner,dependency_id=key), asset.get("steps"))
                pending.extend(dependency.get("dependencies", []))
        for pointer in [path for path in self.files if path.name=="active.json" and path.parent.parent==self.root/"用例"]:
            data = load_strict_json(self.source(pointer))
            owner = dict(case_id=data["case_id"],branch_id=data["branch_id"],asset_id="active-release",version=data["build_fingerprint"])
            manifest = self.bind(pointer.parent,data["manifest_ref"],owner,"version")
            if manifest:
                for name in load_strict_json(self.source(manifest)).get("artifacts",{}):
                    self.bind(manifest.parent,name,owner,"version")
        for manifest in [p for p in self.files if p.name=="manifest.json" and p.parent.parent.name=="releases"]:
            data=load_strict_json(self.source(manifest))
            identity=(data.get("case_id"),data.get("branch_id"),data.get("build_fingerprint"))
            if identity[2]!="sha256:"+manifest.parent.name:
                continue
            for owner in self.versions.get(identity,[]):
                self.bind(manifest.parent,"manifest.json",owner,"version")
                for ref in data.get("artifacts",{}):
                    self.bind(manifest.parent,ref,owner,"version")

    def build(self):
        self.scan()
        self.check_named_batches()
        self.events = defaultdict(list)
        self.contexts = defaultdict(list)
        for path in self.files:
            if path.parent.name == "events" and path.suffix == ".json":
                self.events[path.parent.parent].append(path)
            if path.name == "execution-context.json":
                self.contexts[path.parent.name].append(path)
        for path in sorted(self.files):
            canonical = path.name == "stage.json" or (path.name == "start.json" and path.with_name("stage.json") not in self.files)
            native = path.parent.parent == self.root / "运行" and canonical
            historic = path.name == "stage.json" and any(path.is_relative_to(p) for p in self.legacy)
            if native or historic:
                try:
                    self.stage(path)
                except (OSError,ValueError,TypeError,KeyError) as error:
                    owners = self.files[path]["consumers"]
                    bound = owners[0].get("stage_id") if owners else None
                    self.issues.append(dict(stage_id=bound,path=path.relative_to(self.root).as_posix(),
                                            reason="阶段原件或引用格式无法核实 " + type(error).__name__))
        for path in sorted(self.files):
            row = self.files[path]
            if path.suffix.lower() not in {".html",".htm"} or row["category"]!="legacy":
                continue
            owner = {"legacy_report":row["path"]}
            for batch in row["legacy_batches"] or [None]:
                scope = {**owner,"legacy_batch":batch} if batch else owner
                self.bind(path.parent,path.name,scope,"report")
                try:
                    self.report(path,scope)
                except (OSError,ValueError,TypeError) as error:
                    self.issues.append(dict(**scope,path=row["path"],reason="历史报告引用无法核实 "+type(error).__name__))
        try:
            self.assets()
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.issues.append(dict(reason="在用资产引用无法核实 " + type(error).__name__))
        totals = defaultdict(lambda: {"count":0,"bytes":0})
        rows = []
        for path,row in sorted(self.files.items()):
            legacy=any(path.is_relative_to(folder) for folder in self.legacy)
            known_legacy = row["legacy_batches"] and (row["consumers"] or path.suffix.lower() in {".html",".htm"})
            if legacy:
                eligibility="named_legacy" if known_legacy else "inventory_only"
            else:
                eligible = any(self.stages[c["stage_id"]]["disposition_scope"] != "inventory_only"
                               for c in row["consumers"] if c.get("stage_id") in self.stages)
                eligibility = "stage_referenced" if eligible else "inventory_only"
            row["eligibility"]=eligibility
            totals[row["category"]]["count"]+=1
            totals[row["category"]]["bytes"]+=row["size"]
            rows.append(row)
        return dict(generated_at=datetime.now(timezone.utc).isoformat(),files=rows,stages=self.stages,
                    legacy_batches={k:v.relative_to(self.root).as_posix() for k,v in self.batches.items()},
                    categories=[dict(category=k,**v) for k,v in sorted(totals.items())],issues=self.issues)


def inventory_project(root):
    return ProjectInventory(root).build()
