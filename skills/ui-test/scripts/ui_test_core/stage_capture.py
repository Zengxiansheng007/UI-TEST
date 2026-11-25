"""Capture masked pixels from the live Playwright page at a case-owned assertion."""
import hashlib
from pathlib import Path
from uuid import uuid4

POINTS = {"pre_submit", "receipt", "final", "timeout", "failure", "blocked", "unknown", "query", "author", "ordinary"}
STANDARD_MASK = 'input[type=password], [data-ui-sensitive], [autocomplete=cc-number], [autocomplete=one-time-code]'


def capture_step(page, step, *, context, run_root, point, object_ref, observation, reason=None,
                 full_page=False, mask_selectors=(), ref=None, preferred=False, support="direct",
                 state_ref=None, moment_ref=None, final_goal=None):
    """Append evidence without changing the action, issuing requests or granting a verdict."""
    fields = [object_ref, observation, step["step_id"]]
    if point == "author":
        fields.append(reason)
    qualifiers = {"state_ref": state_ref, "moment_ref": moment_ref, "final_goal": final_goal}
    fields.extend(value for value in qualifiers.values() if value is not None)
    if (point not in POINTS or type(full_page) is not bool or type(preferred) is not bool
            or support not in ("direct", "context") or (final_goal is not None and (point != "receipt" or support != "direct"))
            or not all(isinstance(s, str) and s.strip() for s in fields)):
        raise ValueError("Invalid capture point, object or observation")
    root = Path(run_root).resolve()
    relative = Path(ref or f"images/{uuid4().hex}.png")
    target = (root / relative).resolve()
    if relative.is_absolute() or relative.drive or ".." in relative.parts or not target.is_relative_to(root):
        raise ValueError("Invalid screenshot path")
    if root.parent.parent.name == "运行":
        from .artifact_layout import checked_path
        checked_path(target)
    image = {key: context[key] for key in ("run_id", "case_id", "attempt_ref")}
    image.update(stage="playwright", step_id=step["step_id"], point=point, object_ref=object_ref,
                 observation=observation, caption=" · ".join((object_ref, point, observation)),
                 role="ordinary" if point == "ordinary" else "key", full_page=full_page)
    image.update(preferred=preferred, support=support)
    image.update({key: value for key, value in qualifiers.items() if value is not None})
    if reason:
        step["key_reason"] = image["reason"] = reason
    step["actual_result"] = observation
    step.setdefault("images", []).append(image)
    try:
        masks = [frame.locator(selector) for frame in page.frames for selector in (STANDARD_MASK, *mask_selectors)]
        pixels = page.screenshot(type="png", full_page=full_page, mask=masks, mask_color="#000000")
    except Exception:
        image["missing_reason"] = "Masked page capture unavailable"
        return image
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(pixels)
    except OSError:
        image["missing_reason"] = "Masked page capture could not be stored"
        return image
    image.update(path=relative.as_posix(), sha256=hashlib.sha256(pixels).hexdigest(),
                 width=int.from_bytes(pixels[16:20], "big"), height=int.from_bytes(pixels[20:24], "big"))
    step.setdefault("evidence_refs", []).append(image["path"])
    return image
