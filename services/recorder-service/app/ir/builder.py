from __future__ import annotations
from typing import Any
from app.recorder.locator import build_candidates, choose_preferred
from app.recorder.models import SemanticAction


def _element_key(target: dict[str, Any]) -> str:
    basis = target.get("testId") or target.get("label") or target.get("name") or target.get("id") or target.get("accessibleName") or target.get("tag", "element")
    slug = ''.join(c.lower() if c.isalnum() else '-' for c in str(basis)).strip('-')
    return slug[:60] or "element"


def build_ir(actions: list[SemanticAction], scenario_id: str = "TC-EMP-001", scenario_name: str = "Create Employee Successfully") -> dict[str, Any]:
    elements: dict[str, Any] = {}
    parameters: dict[str, Any] = {}
    steps: list[dict[str, Any]] = []

    for i, action in enumerate(actions, start=1):
        step: dict[str, Any] = {"id": f"step-{i:03d}", "action": action.action, "metadata": {"sourceEvents": action.sourceEvents, **action.metadata}}
        if action.target:
            key = _element_key(action.target)
            candidates = build_candidates(action.target)
            # Keyboard events can legitimately occur on body/document where there is no
            # stable element locator. Keep the keyboard action but omit the element ref
            # so code generators can use the active element/global keyboard.
            if candidates:
                if key not in elements:
                    elements[key] = {
                        "key": key,
                        "description": action.target.get("label") or action.target.get("accessibleName") or key,
                        "preferred": choose_preferred(candidates),
                        "alternatives": candidates[1:]
                    }
                step["element"] = key
            elif action.action == "keyboard":
                step["metadata"]["locatorOmitted"] = "No stable locator was available; use the active element/global keyboard."
            else:
                if key not in elements:
                    elements[key] = {
                        "key": key,
                        "description": action.target.get("label") or action.target.get("accessibleName") or key,
                        "preferred": None,
                        "alternatives": []
                    }
                step["element"] = key
        if action.action == "navigate":
            step["url"] = action.value
        elif action.action in {"fill", "select"}:
            if action.valueSource == "secret":
                step["value"] = {"source": "secret", "reference": action.reference}
            else:
                ref = action.reference or f"param{i}"
                parameters.setdefault(ref, {"type": "string", "default": action.value})
                step["value"] = {"source": "parameter", "reference": ref}
        elif action.action == "uploadFile":
            step["asset"] = {"source": "asset", "reference": action.reference}
        elif action.action == "keyboard":
            step["key"] = action.value
        elif action.action == "assert":
            step["assertion"] = {"type": action.metadata.get("assertionType", "visible"), "expected": action.value}
        elif action.action == "checkpoint":
            step["description"] = action.metadata.get("description", "")
        elif action.action == "extractValue":
            step["variable"] = action.reference
            step["property"] = action.metadata.get("property", "text")
        steps.append(step)

    return {
        "$schema": "./schemas/automation-ir-v1.schema.json",
        "irSchemaVersion": "1.0.0",
        "scenario": {"id": scenario_id, "name": scenario_name},
        "configuration": {"browser": "chromium"},
        "parameters": parameters,
        "elements": elements,
        "steps": steps,
        "metadata": {"generatedBy": "Recorder Worker v0.2.0", "source": "recording"}
    }
