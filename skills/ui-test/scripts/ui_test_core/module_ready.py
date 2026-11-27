"""Current-session readiness contract shared by checkpoint and exploration."""
from datetime import datetime, timezone
from uuid import uuid4


def instant(value):
    if not isinstance(value, str):
        raise ValueError("timezone required")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() is None:
        raise ValueError("timezone required")
    return result


def verify_module_signature(route_verified, ui_features_verified, readonly_network_evidence_ref=None, *,
                            host_verified=False, authenticated_session_verified=False, network_evidence=None,
                            session_id=None, run_id=None):
    features = sorted({value.strip() for value in ui_features_verified if isinstance(value, str) and value.strip()})
    network = network_evidence or {}
    matched = bool(session_id and run_id and readonly_network_evidence_ref
                   and network.get("source") == "page-response"
                   and network.get("evidence_ref") == readonly_network_evidence_ref
                   and network.get("session_id") == session_id and network.get("run_id") == run_id
                   and network.get("request_matched") is True and network.get("response_matched") is True
                   and network.get("business_success") is True)
    ok = (host_verified is True and authenticated_session_verified is True and route_verified is True
          and (not (readonly_network_evidence_ref or network_evidence) or matched)
          and (len(features) >= 2 or bool(features and matched)))
    return dict(ok=ok, host_verified=host_verified, authenticated_session_verified=authenticated_session_verified,
                route_verified=route_verified, ui_features_verified=features, network_evidence=network_evidence,
                readonly_network_evidence_ref=readonly_network_evidence_ref, code="OK" if ok else "E_CHECKPOINT_STALE")


def build_module_ready_context(*, session_id, run_id, identity, signature, auth_reference_digest,
                               policy_fingerprint, generated_at, expires_at, evidence_refs):
    context = {**identity, "schema_version": "2.0", "context_id": "mrc-" + uuid4().hex,
               "session_id": session_id, "run_id": run_id, "generated_at": generated_at, "expires_at": expires_at,
               "handoff_status": "ready", "evidence_refs": list(evidence_refs),
               "auth_reference_digest": auth_reference_digest, "policy_fingerprint": policy_fingerprint}
    for field in ("host_verified", "authenticated_session_verified", "route_verified", "ui_features_verified",
                  "network_evidence", "readonly_network_evidence_ref"):
        context[field] = signature.get(field)
    result = validate_module_ready_context(context, session_id=session_id, run_id=run_id, now=generated_at)
    if not result["ok"]:
        raise ValueError(result["code"])
    return context


def validate_module_ready_context(context, *, session_id, run_id, context_id=None, now=None):
    fail = {"ok": False, "code": "E_MODULE_READY_CONTEXT_INVALID", "blocking": True}
    from .case_contracts import validate_document
    if validate_document(context, "module-ready-context-v2.schema.json"):
        return fail
    try:
        generated, expires = instant(context["generated_at"]), instant(context["expires_at"])
        current = instant(now) if now is not None else datetime.now(timezone.utc)
        if not instant(context["run"]["started_at"]) <= generated <= current < expires:
            return fail
        if not (session_id and run_id and context["session_id"] == session_id
                and context["run_id"] == context["run"]["run_id"] == run_id
                and context["case"]["case_id"] and context["branch"]["branch_id"]
                and context["context_id"] and (context_id is None or context_id == context["context_id"])
                and context["schema_version"] == "2.0" and context["handoff_status"] == "ready"
                and context["checkpoint_id"] and context["module_id"] and context["evidence_refs"]):
            return fail
        scope = context["scope"]
        if not all(scope.get(k) for k in ("project_group","product","system","module_path","function","checkpoint","environment","risk_level")):
            return fail
        from .checkpoint_governance import checkpoint_identity
        if context["checkpoint_id"] != checkpoint_identity(scope, context["module_id"])["checkpoint_id"]:
            return fail
        observations = context["ui_observations"]
        if not any(ref in context["evidence_refs"] and obs["verified_selectors"] == context["ui_features_verified"]
                   for ref, obs in observations.items()):
            return fail
        network = context.get("network_evidence")
        if network:
            observed = instant(network["observed_at"])
            if not instant(context["run"]["started_at"]) <= observed <= generated:
                return fail
            if network["evidence_ref"] not in context["evidence_refs"]:
                return fail
        sig = verify_module_signature(context["route_verified"], context["ui_features_verified"],
                                      context.get("readonly_network_evidence_ref"), host_verified=context["host_verified"],
                                      authenticated_session_verified=context["authenticated_session_verified"],
                                      network_evidence=network, session_id=session_id, run_id=run_id)
        if not sig["ok"]:
            return fail
    except (AttributeError, ValueError, TypeError, KeyError):
        return fail
    return {"ok": True, "code": "OK", "blocking": False}

def observe_target(page, target_url, login_selector):
    from urllib.parse import urlsplit
    expected, actual = urlsplit(target_url), urlsplit(page.url)
    return {
        "host_verified": bool(expected.hostname and expected.scheme in ("http", "https")
                              and (expected.scheme, expected.netloc) == (actual.scheme, actual.netloc)),
        "route_verified": (expected.path, expected.query, expected.fragment) == (actual.path, actual.query, actual.fragment),
        "authenticated_session_verified": bool(login_selector and page.locator(login_selector).count() == 1
                                               and page.locator(login_selector).is_visible()),
    }


def visible_features(page, selectors):
    return page.evaluate("""selectors => {
            const unique = new Set(), result = [];
            for (const selector of selectors) {
                const nodes = document.querySelectorAll(selector);
                if (nodes.length !== 1 || unique.has(nodes[0])) continue;
                const node = nodes[0];
                if (node.getBoundingClientRect().width && node.getBoundingClientRect().height &&
                    getComputedStyle(node).visibility === 'visible') {
                    unique.add(node); result.push(selector);
                }
            }
            return result;
        }""", selectors)


class ModuleReadyObserver:
    """Attach before the authorized UI action. Store only matched, redacted results."""
    def __init__(self, page, *, packet, session_id, config):
        from .packet_validator import validate_packet
        if validate_packet(packet) or not session_id or type(config.get("ttl_seconds")) is not int or config["ttl_seconds"] <= 0:
            raise ValueError("E_MODULE_READY_CONFIG")
        if not all(config.get(key) for key in ("target_url","module_id","login_selector","feature_selectors")):
            raise ValueError("E_MODULE_READY_CONFIG")
        self.page, self.packet, self.session_id, self.config = page, packet, session_id, config
        self.latest_request = None
        self.latest_response = None
        self.observed_at = None
        self.closed = False
        page.on("request", self._request_started)
        page.on("response", self._response_arrived)

    def _request_started(self, request):
        from urllib.parse import urlsplit
        rule = self.config.get("response")
        if not rule or request.resource_type not in ("xhr", "fetch"):
            return
        expected, actual = urlsplit(self.config["target_url"]), urlsplit(request.url)
        if ((actual.scheme, actual.netloc, actual.path) == (expected.scheme, expected.netloc, rule["path"])
                and not actual.query and request.method == rule["method"]
                and request.frame == self.page.main_frame):
            self.latest_request = request
            self.latest_response = self.observed_at = None

    def _response_arrived(self, response):
        if self.latest_request is not None and response.request == self.latest_request:
            self.latest_response = response
            self.observed_at = datetime.now(timezone.utc).isoformat()

    def close(self):
        if self.closed:
            return
        self.page.remove_listener("request", self._request_started)
        self.page.remove_listener("response", self._response_arrived)
        self.closed = True
        self.latest_request = self.latest_response = self.observed_at = None

    def _business_evidence(self):
        import hashlib
        from playwright.sync_api import Error
        response = self.latest_response
        if response is None or not response.ok:
            return None
        try:
            data = response.json()
        except (ValueError, Error):
            return None
        rule = self.config["response"]
        if (self.latest_response != response or not isinstance(data, dict)
                or data.get(rule["success_field"]) is not True):
            return None
        return dict(source="page-response", evidence_ref="response-" + uuid4().hex, observed_at=self.observed_at,
                    session_id=self.session_id, run_id=self.packet["run"]["run_id"], request_matched=True,
                    response_matched=True, method=response.request.method, status=response.status,
                    path_digest=hashlib.sha256(rule["path"].encode()).hexdigest(),
                    assertion_digest=hashlib.sha256(rule["success_field"].encode()).hexdigest(), business_success=True)

    def capture(self):
        from datetime import timedelta
        from urllib.parse import urlsplit
        import hashlib
        from .checkpoint_governance import checkpoint_identity
        config, packet = self.config, self.packet
        if self.closed:
            raise ValueError("E_OBSERVATION_WINDOW_CLOSED")
        checks = observe_target(self.page, config["target_url"], config["login_selector"])
        features = visible_features(self.page, config["feature_selectors"])
        network = self._business_evidence()
        self.close()
        ref = network["evidence_ref"] if network else None
        sig = verify_module_signature(ui_features_verified=features, readonly_network_evidence_ref=ref,
                                      network_evidence=network, session_id=self.session_id, run_id=packet["run"]["run_id"], **checks)
        if not sig["ok"]:
            raise ValueError("E_MODULE_SIGNATURE_INSUFFICIENT")
        identity = checkpoint_identity(packet["scope"], config["module_id"])
        identity.update({key:packet[key] for key in ("scope","case","branch","run")})
        ui_ref = "ui-" + uuid4().hex
        identity["ui_observations"] = {ui_ref: {"verified_selectors": sig["ui_features_verified"], **checks}}
        identity["target_digest"] = hashlib.sha256(config["target_url"].encode()).hexdigest()
        generated = datetime.now(timezone.utc)
        context = build_module_ready_context(session_id=self.session_id, run_id=packet["run"]["run_id"], identity=identity,
            signature=sig, generated_at=generated.isoformat(), expires_at=(generated+timedelta(seconds=config["ttl_seconds"])).isoformat(),
            evidence_refs=[ui_ref] + ([ref] if ref else []), auth_reference_digest=None, policy_fingerprint=None)
        if network:
            from .case_contracts import canonical_hash
            captures = getattr(self.page, "_ui_test_response_captures", {})
            # Keep the live provenance on the originating Page; prune expired captures.
            self.page._ui_test_response_captures = {key: end for key, end in captures.items() if end > generated}
            self.page._ui_test_response_captures[canonical_hash(context)] = instant(context["expires_at"])
        return context


def matches_response_rule(network, rule):
    """Compare one response to the reviewed listener configuration."""
    import hashlib
    return (isinstance(network, dict) and isinstance(rule, dict)
            and all(isinstance(rule.get(key), str) and rule[key] for key in ("method", "path", "success_field"))
            and network.get("method") == rule["method"]
            and network.get("path_digest") == hashlib.sha256(rule["path"].encode()).hexdigest()
            and network.get("assertion_digest") == hashlib.sha256(rule["success_field"].encode()).hexdigest())


def consume_ready_context(context, *, packet, session_id, page, config):
    import hashlib
    checks = observe_target(page, config["target_url"], config["login_selector"])
    if (not all(checks.values()) or not all(context.get(k) == packet.get(k) for k in ("scope","case","branch","run"))
        or context.get("target_digest") != hashlib.sha256(config["target_url"].encode()).hexdigest()
        or context.get("module_id") != config["module_id"]):
        return {"ok": False, "code": "E_MODULE_TARGET_CHANGED", "blocking": True}
    current_features = visible_features(page, config.get("feature_selectors", []))
    if not set(context.get("ui_features_verified") or []).issubset(current_features):
        return {"ok": False, "code": "E_MODULE_TARGET_CHANGED", "blocking": True, "missing": "visible_features"}
    network = context.get("network_evidence")
    if network:
        rule = config.get("response") or {}
        if not matches_response_rule(network, rule):
            return {"ok": False, "code": "E_MODULE_RESPONSE_RULE_CHANGED", "blocking": True}
    return validate_module_ready_context(context, session_id=session_id, run_id=packet["run"]["run_id"])
