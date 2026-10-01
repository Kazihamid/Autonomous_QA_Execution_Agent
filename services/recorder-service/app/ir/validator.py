from __future__ import annotations
from jsonschema import Draft202012Validator
from .schema import AUTOMATION_IR_SCHEMA

ALLOWED_ACTIONS = {"navigate","click","fill","select","check","uncheck","keyboard","uploadFile","assert","checkpoint","extractValue","switchTab","closeTab","manualStep"}
LOCATOR_REQUIRED_ACTIONS = {"click","fill","select","check","uncheck","uploadFile","assert","extractValue"}
SUPPORTED_LOCATOR_STRATEGIES = {"testId","role","label","id","name","placeholder","text","css","xpath"}


def _has_supported_locator(element: dict) -> bool:
    candidates = []
    preferred = element.get("preferred")
    if isinstance(preferred, dict):
        candidates.append(preferred)
    candidates.extend(x for x in (element.get("alternatives") or []) if isinstance(x, dict))
    return any(c.get("strategy") in SUPPORTED_LOCATOR_STRATEGIES and c.get("value") not in (None, "", False) for c in candidates)


def validate_ir(ir: dict) -> list[str]:
    errors = [e.message for e in Draft202012Validator(AUTOMATION_IR_SCHEMA).iter_errors(ir)]
    elements = ir.get("elements", {})
    params = ir.get("parameters", {})
    for step in ir.get("steps", []):
        action = step.get("action")
        if action not in ALLOWED_ACTIONS:
            errors.append(f"Unsupported action: {action}")
        if "element" in step and step["element"] not in elements:
            errors.append(f"Missing element: {step['element']}")
        if action in LOCATOR_REQUIRED_ACTIONS:
            key = step.get("element")
            element = elements.get(key) if key else None
            if not isinstance(element, dict) or not _has_supported_locator(element):
                errors.append(f"LOCATOR_REQUIRED: step {step.get('id')} ({action}) has no supported locator for element {key or 'UNKNOWN'}.")
        val = step.get("value")
        if isinstance(val, dict) and val.get("source") == "parameter" and val.get("reference") not in params:
            errors.append(f"Missing parameter: {val.get('reference')}")
        if isinstance(val, dict) and val.get("source") == "secret" and not val.get("reference"):
            errors.append("Secret value missing reference")
        if action == "uploadFile" and ":\\" in str(step.get("asset", {})):
            errors.append("Absolute local asset path is prohibited")
    return errors
