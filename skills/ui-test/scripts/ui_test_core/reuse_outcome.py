"""Classify observed reuse outcomes without executing an asset or a business action."""
import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from .execution_data_session import ExecutionDataError


SCOPE = ("case_id", "step_id", "environment")


class ReuseFailure(RuntimeError):
    """An explicit observation supplied by the component which detected the failure."""

    def __init__(self, cause, reason):
        if cause not in {'asset', 'business', 'environment', 'data', 'unknown'}:
            raise ValueError('unsupported failure cause')
        super().__init__(reason)
        self.cause = cause
        self.reason = reason


def failure_outcome(error, use):
    cause = error.cause if isinstance(error, ReuseFailure) else 'unknown'
    reason = error.reason if isinstance(error, ReuseFailure) else 'unclassified_failure'
    pause = None
    if isinstance(error, ExecutionDataError):
        cause, reason = 'data', str(error).split(':')[0]
    if cause == 'asset' and all(use.get(key) is not None for key in ('asset_id', 'version', *SCOPE)):
        pause = {key: use[key] for key in ('asset_id', 'version', *SCOPE)}
    return {'cause': cause, 'reason': reason, 'pause_scope': pause, 'stop_dependents': True}


def _pause_file(project, identity):
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return Path(project) / 'reuse-decisions' / 'paused' / (key + '.json')


def persist_pause(project, failure):
    identity = failure['pause_scope']
    if identity is None:
        return
    target = _pause_file(project, identity)
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile('w', dir=target.parent, delete=False, encoding='utf-8') as output:
        json.dump(identity, output, sort_keys=True)
    Path(output.name).replace(target)  # Identical immutable decision keys are idempotent.


def is_paused(project, asset_id, version, scope):
    if any(key not in scope for key in SCOPE):
        # An incomplete query cannot establish that a partial restriction is irrelevant.
        folder = Path(project) / 'reuse-decisions' / 'paused'
        for marker in folder.glob('*.json'):
            identity = json.loads(marker.read_text(encoding='utf-8'))
            if identity['asset_id'] == asset_id and identity['version'] == version and all(
                    key not in scope or scope[key] == identity[key] for key in SCOPE):
                return True
        return False
    return _pause_file(project, dict(asset_id=asset_id, version=version,
                                     **{key: scope[key] for key in SCOPE})).is_file()


def reuse_verdict(use, context, step_id):
    if not use or any(use.get(key) != context[key] for key in ('run_id', 'case_id', 'attempt_ref')):
        return 'unproven'
    if use.get('step_id') == step_id and use.get('asset_id') and use.get('version') is not None:
        if use.get('discovered') and use.get('selected') and use.get('entered') is False:
            return 'selected_not_entered'
    if (use.get('step_id') == step_id and use.get('asset_id') and use.get('version') is not None
            and use.get('entered') is True and use.get('action_result') == 'passed'
            and use.get('assertion_result') == 'passed'):
        return 'verified'
    return 'unproven'
