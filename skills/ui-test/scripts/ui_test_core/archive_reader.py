"""Offline stage reader. Original paths are lookup keys and are never opened."""
import hashlib
import json
import os
import re
import struct
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import url2pathname

from .asset_revision import digest
from .case_contracts import canonical_hash
from .path_planner import validate_existing_path_containment
from .strict_json import load_strict_json


class ArchiveFiles:
    def __init__(self, folder, manifest):
        self.folder, self.manifest = folder, manifest
        self.roots = [Path(p) for p in (manifest["project"],manifest.get("original_project_root")) if p]
        self.keys = {Path(key):key for key in manifest["files"]}

    def path(self, name):
        name = Path(name)
        if name.anchor or not name.parts or ".." in name.parts:
            raise ValueError("E_ARCHIVE_PACKAGE_REF")
        target = self.folder / name
        validate_existing_path_containment(self.folder, target)
        return target

    def key(self, base, value):
        if not isinstance(value, str) or not value:
            raise ValueError("E_ARCHIVE_MISSING_REFERENCE")
        name = Path(os.path.normpath(Path(base) / value))
        if name.is_absolute():
            for root in self.roots:
                if name.is_relative_to(root):
                    name = name.relative_to(root)
                    break
        if name not in self.keys:
            raise ValueError("E_ARCHIVE_MISSING_REFERENCE " + str(name))
        return self.keys[name]

    def row(self, base, value):
        return self.manifest["files"][self.key(base, value)]

    def json(self, key):
        return load_strict_json(self.path(self.row("",key)["archived_ref"]))


class ReportReader(HTMLParser):
    def __init__(self, archive, origin, document=None):
        super().__init__(convert_charrefs=False)
        self.archive, self.origin = archive, origin
        self.document = document or archive.manifest["report_ref"]
        self.base = (archive.roots[0] / self.document).as_uri()
        self.parts, self.photo, self.images = [], None, []
        self.cases, self.case, self.in_header, self.field = [], None, False, None

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "section" and re.fullmatch(r"case-[0-9]+", attrs.get("id","")):
            self.case = {"label":"", "status":""}
            self.cases.append(self.case)
        elif tag == "header" and self.case is not None:
            self.in_header = True
        elif self.in_header and tag in {"h2","strong"}:
            self.field = "label" if tag == "h2" else "status"
        if tag == "base":
            self.base = urljoin(self.base,attrs.get("href",""))
            return
        meta = json.loads(attrs["data-image-metadata"]) if attrs.get("data-image-metadata") else {}
        if meta.get("path"):
            row = self.archive.row(Path(self.document).parent,meta["path"])
            if meta.get("sha256") and meta["sha256"].removeprefix("sha256:") != row["sha256"]:
                raise ValueError("E_ARCHIVE_IMAGE_DIGEST " + str(meta.get("step_id")))
            self.photo = row["archived_ref"]
            self.images.append(dict(original_ref=row["original_ref"],case_id=meta.get("case_id"),step_id=meta.get("step_id")))
            meta["path"] = self.photo
            attrs.update({"data-image-path":self.photo,"data-image-metadata":json.dumps(meta,ensure_ascii=False)})
        for key in ("href","src"):
            raw = attrs.get(key)
            if not raw or raw.startswith("#"):
                continue
            if tag=="img" and key=="src" and self.photo:
                attrs[key] = self.photo
                continue
            if raw.startswith("data:"):
                continue
            parsed = urlsplit(urljoin(self.base,raw))
            if parsed.scheme != "file" or parsed.netloc not in {"","localhost"}:
                raise ValueError("E_ARCHIVE_NONLOCAL_REPORT_REFERENCE")
            target = Path(url2pathname(parsed.path))
            if parsed.fragment.startswith("stage-") and any(target == root/"index.html" for root in self.archive.roots):
                attrs[key] = "#archive-info" if self.document == self.archive.manifest["report_ref"] else "index.html#archive-info"
                continue
            row = self.archive.row("",str(target))
            if self.origin.get("kind")=="exploration" and row["original_ref"]==self.origin.get("report"):
                attrs[key] = "related.html"
            else:
                attrs[key] = row["archived_ref"] + ("#" + parsed.fragment if parsed.fragment else "")
        rendered = "".join(" " + key + ('="' + escape(value,quote=True) + '"' if value is not None else "")
                           for key,value in attrs.items())
        self.parts.append("<"+tag+rendered+">")

    def handle_endtag(self, tag):
        if tag in {"h2","strong"}:
            self.field = None
        elif tag=="header":
            self.in_header = False
        elif tag=="section":
            self.case = None
        if tag == "button":
            self.photo = None
        self.parts.append("</"+tag+">")

    def handle_data(self, value):
        if self.case is not None and self.field:
            self.case[self.field] += value
        self.parts.append(value)

    def handle_entityref(self, name):
        if self.case is not None and self.field:
            self.case[self.field] += unescape("&"+name+";")
        self.parts.append("&"+name+";")

    def handle_charref(self, name):
        if self.case is not None and self.field:
            self.case[self.field] += unescape("&#"+name+";")
        self.parts.append("&#"+name+";")

    def handle_decl(self, value):
        self.parts.append("<!"+value+">")

    def handle_comment(self, value):
        self.parts.append("<!--"+value+"-->")


def verify_attempt(files, source, case, attempt, stage_index):
    sid = source["stage_id"]
    key = files.key("",attempt.get("execution_ref"))
    result = files.json(key)
    files.key("",attempt.get("evidence_ref"))
    binding = attempt.get("binding") or {}
    if not binding or binding.get("version") != attempt.get("version"):
        raise ValueError("E_ARCHIVE_VERSION_BINDING " + case["case_id"])
    for item in [binding,*binding.get("dependencies",[])]:
        if files.row("",item["entry"])["sha256"] != item["sha256"]:
            raise ValueError("E_ARCHIVE_VERSION_DIGEST " + item["entry"])
    if source["stage_type"] == "midscene":
        if (result.get("stage"),result.get("run_id")) != ("midscene",sid):
            raise ValueError("E_ARCHIVE_OBSERVATION_IDENTITY")
        owners = [row for row in result["cases"] if (row["case_id"],row.get("branch_id",row["case_id"]),row["attempt_ref"])
                  == (case["case_id"],case["branch_id"],attempt["attempt_ref"])]
        if len(owners)!=1 or owners[0]["status"] != attempt["status"]:
            raise ValueError("E_ARCHIVE_OBSERVATION_RESULT " + case["case_id"])
        if owners[0].get("binding") and owners[0]["binding"] != binding:
            raise ValueError("E_ARCHIVE_OBSERVATION_VERSION " + case["case_id"])
        if (stage_index.get("case_id") != case["case_id"] or stage_index.get("branch_id",case["branch_id"]) != case["branch_id"]
                or files.key(Path(source["report_ref"]).parent,stage_index["source"]) != key):
            raise ValueError("E_ARCHIVE_OBSERVATION_INDEX " + case["case_id"])
        for step in owners[0].get("steps",[]):
            images = step.get("images") or ([step["ui_evidence"]] if step.get("ui_evidence") else [])
            for image in images:
                if image.get("path"):
                    check_image(files,Path(key).parent,image,step["step_id"],case,attempt)
    elif result.get("schema_version") == "ui-test.run-result.v5":
        if (result.get("case_id"),result.get("branch_id"),result.get("attempt_ref"),result["overall_status"]) != (
                case["case_id"],case["branch_id"],attempt["attempt_ref"],attempt["status"]):
            raise ValueError("E_ARCHIVE_V5_RESULT " + case["case_id"])
        directory = Path(key).parent
        if directory.name == "objects" and directory.parent.name == "finalization":
            directory = directory.parent.parent
        index = files.json(attempt["evidence_ref"])
        if (index != stage_index or canonical_hash({k:v for k,v in result.items() if k != "run_result_hash"}) != result["run_result_hash"]
                or index.get("run_result_hash") != result.get("run_result_hash") or index.get("run_id") != result["run_id"]
                or files.key(Path(key).parent.parent, index["run_result_ref"]) != key):
            raise ValueError("E_ARCHIVE_V5_EVIDENCE_INDEX")
        context = Path(result["execution_context_ref"])
        matches = [ref for ref in files.manifest["files"] if Path(ref).parts[-len(context.parts):] == context.parts]
        contexts = [files.json(ref) for ref in matches]
        if not any(canonical_hash(ctx) == result.get("execution_context_hash")
                   and ctx.get("runner_digest","").removeprefix("sha256:")==binding["sha256"]
                   and ctx.get("binding",binding)==binding for ctx in contexts):
            raise ValueError("E_ARCHIVE_V5_CONTEXT " + case["case_id"])
        for name in ("approval_ref","resolved_test_data_ref"):
            if result.get(name):
                files.key(directory,result[name])
        for ref in result.get("evidence_refs",[]):
            files.key(directory,ref)
        for step in result["step_results"]:
            for ref in step.get("evidence_refs",[]):
                files.key(directory,ref)
            for image in step.get("images",[]):
                if image.get("path"):
                    check_image(files,directory,image,step["step_id"],case,attempt)
    else:
        raise ValueError("E_ARCHIVE_EXECUTION_FORMAT " + case["case_id"])


def check_image(files, base, image, step, case, attempt):
    row = files.row(base,image["path"])
    scoped = (case["case_id"],case["branch_id"],attempt["attempt_ref"],step)
    if not any(tuple(c.get(k) for k in ("case_id","branch_id","attempt_ref","step_id"))==scoped for c in row["consumers"]):
        raise ValueError("E_ARCHIVE_IMAGE_OWNER " + " / ".join(scoped))
    if image.get("sha256") and row["sha256"] != image["sha256"].removeprefix("sha256:"):
        raise ValueError("E_ARCHIVE_IMAGE_DIGEST " + step)
    with files.path(row["archived_ref"]).open("rb") as stream:
        header = stream.read(24)
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            if len(header)!=24 or header[12:16]!=b"IHDR":
                raise ValueError("E_ARCHIVE_IMAGE_HEADER " + step)
            width,height = struct.unpack(">II",header[16:24])
            if not min(width,height) or (image.get("width",width),image.get("height",height)) != (width,height):
                raise ValueError("E_ARCHIVE_IMAGE_DIMENSIONS " + step)
        elif not (header.startswith((b"\xff\xd8\xff", b"GIF87a", b"GIF89a")) or
                  (header.startswith(b"RIFF") and header[8:12] == b"WEBP")):
            raise ValueError("E_ARCHIVE_IMAGE_HEADER " + step)


def archive_view(folder, manifest):
    files = ArchiveFiles(folder,manifest)
    if len({row["archived_ref"] for row in manifest["files"].values()}) != len(manifest["files"]):
        raise ValueError("E_ARCHIVE_OBJECT_COLLISION")
    for key,row in manifest["files"].items():
        raw = files.path(row["archived_ref"])
        if (key != row["original_ref"] or raw.stat().st_size != row["size"] or not re.fullmatch(
                r"objects/[a-f0-9]{24}\.[a-z0-9]{1,8}",row["archived_ref"])):
            raise ValueError("E_ARCHIVE_FILE_IDENTITY " + key)
        with raw.open("rb") as stream:
            if hashlib.file_digest(stream,"sha256").hexdigest() != row["sha256"]:
                raise ValueError("E_ARCHIVE_FILE_DIGEST " + key)
    source = files.json(manifest["source_ref"])
    sid = manifest["stage"]["stage_id"]
    if (source["stage_id"],source["stage_type"],source["status"],source["report_ref"]) != (
            sid,manifest["stage"]["stage_type"],manifest["stage"]["status"],manifest["report_ref"]):
        raise ValueError("E_ARCHIVE_STAGE_IDENTITY")
    projection = [dict(case_id=c["case_id"],branch_id=c["branch_id"],status=c["status"],
                       attempts=[{k:a.get(k) for k in ("attempt_ref","status","version")} for a in c["attempts"]])
                  for c in source["cases"]]
    if projection != manifest["stage"]["cases"] or any(source.get(k)!=manifest["stage"].get(k) for k in ("started_at","ended_at")):
        raise ValueError("E_ARCHIVE_STAGE_PROJECTION")
    report = Path(source["report_ref"])
    summary = files.json((report.parent/"execution-summary.json").as_posix())
    index = files.json((report.parent/"evidence-index.json").as_posix())
    if (any((record["stage"],record["run_id"]) != (source["stage_type"],sid) for record in (summary,index))
            or len(summary["cases"])!=len(index["cases"])):
        raise ValueError("E_ARCHIVE_STAGE_RESULTS")
    origin = source.get("origin") or {"kind":"unknown"}
    related = None
    if origin.get("kind")=="exploration":
        files.key("",origin["report"])
        if files.json(origin["observations"])["run_id"]!=origin["stage_id"]:
            raise ValueError("E_ARCHIVE_LINEAGE_IDENTITY")
        upstream = ReportReader(files, {}, origin["report"])
        upstream.feed(files.path(files.row("",origin["report"])["archived_ref"]).read_text("utf-8-sig"))
        upstream.close()
        related = "".join(upstream.parts).encode("utf8")
    results = []
    unused = list(summary["cases"])
    for case in source["cases"]:
        attempts = case["attempts"] or [None]
        for attempt in attempts:
            matches = [row for row in unused if row.get("case_id",row.get("node_id"))==case["case_id"]
                       and row.get("branch_id",case["branch_id"])==case["branch_id"]
                       and (not attempt or (row.get("attempt_ref") or row.get("run_id"))==attempt["attempt_ref"])]
            status = attempt["status"] if attempt else case["status"]
            if len(matches)!=1 or matches[0]["status"].replace("-","_")!=status.replace("-","_"):
                raise ValueError("E_ARCHIVE_CASE_RESULT " + case["case_id"])
            unused.remove(matches[0])
            if attempt:
                verify_attempt(files,source,case,attempt,index["cases"][summary["cases"].index(matches[0])])
            results.append(dict(case_id=case["case_id"],branch_id=case["branch_id"],status=status,
                                attempt_ref=attempt["attempt_ref"] if attempt else None))
    if unused:
        raise ValueError("E_ARCHIVE_UNMATCHED_CASE")
    reader = ReportReader(files,origin)
    reader.feed(files.path(files.row("",source["report_ref"])["archived_ref"]).read_text("utf-8-sig"))
    reader.close()
    html = "".join(reader.parts)
    if escape(sid) not in html or len(reader.cases)!=len(results):
        raise ValueError("E_ARCHIVE_REPORT_CASES")
    remaining = list(reader.cases)
    for item in results:
        labels = {item["case_id"], item["case_id"] + " / " + item["branch_id"]}
        matched = next((c for c in remaining if c["label"].strip() in labels and
                        c["status"].split(" · ",1)[0].strip().replace("-","_")==item["status"].replace("-","_")), None)
        if matched is None:
            raise ValueError("E_ARCHIVE_REPORT_RESULT " + item["case_id"])
        remaining.remove(matched)
    info = ['<aside id="archive-info"><h2>阶段归档原件</h2><p>阶段 '+escape(sid)+'</p>']
    if origin.get("kind")=="exploration":
        info.append('<p>来源探索 <a href="related.html">'+escape(origin["stage_id"])+'</a> · <a href="'+files.row("",origin["observations"])["archived_ref"]+'">探索观察原件</a></p>')
    for child in manifest.get("downstream",[]):
        info.append("<p>关联正式执行 " + escape(child) + "</p>")
    info.append("<ul>")
    for ref,row in sorted(manifest["files"].items()):
        archived = quote(row["archived_ref"])
        users = sorted({" / ".join(str(c[k]) for k in ("stage_id","linked_stage_id","case_id","branch_id","attempt_ref","step_id") if c.get(k)) for c in row["consumers"]})
        download = " download" if ref.lower().endswith((".html",".htm")) else ""
        info.append(f'<li><a href="{archived}"{download}>{escape(ref)}</a> · {escape("，".join(filter(None,users)))}</li>')
    info.append("</ul></aside>")
    body = html.replace("</body>","".join(info)+"</body>",1) if "</body>" in html else html+"".join(info)
    return body.encode("utf8"), dict(stage_id=sid,cases=results,images=reader.images,origin=origin), related


def verify_archive(archive_dir):
    folder = Path(archive_dir).absolute()
    file = folder/"manifest.json"
    validate_existing_path_containment(folder,file)
    manifest = load_strict_json(file)
    if manifest.get("schema_version")!="ui-test.stage-archive.v1":
        raise ValueError("E_ARCHIVE_MANIFEST_VERSION")
    _, checks, related = archive_view(folder,manifest)
    view = folder/"index.html"
    validate_existing_path_containment(folder,view)
    if checks!=manifest["verification"] or digest(view.read_bytes())!=manifest["reader_sha256"]:
        raise ValueError("E_ARCHIVE_READER_DIGEST")
    if related is not None:
        link = folder/"related.html"
        validate_existing_path_containment(folder,link)
        if digest(link.read_bytes()) != manifest.get("related_sha256"):
            raise ValueError("E_ARCHIVE_LINEAGE_READER_DIGEST")
    return manifest
