from __future__ import annotations
import re
from typing import Any

_DYNAMIC_ID = re.compile(r"(?:[0-9]{6,}|[0-9a-f]{8}-[0-9a-f-]{20,}|react[-_:]?\d+|ember\d+)", re.I)

BASE_SCORES = {
    "testId": 100,
    "role": 95,
    "label": 92,
    "id": 85,
    "name": 80,
    "placeholder": 75,
    "text": 70,
    "css": 45,
    "xpath": 30,
}


def _confidence(score: float) -> float:
    return round(max(0.0, min(1.0, score / 100)), 2)


def build_candidates(target: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    def add(strategy: str, value: Any, score: float | None = None):
        if value in (None, "", False):
            return
        candidates.append({"strategy": strategy, "value": value, "score": score if score is not None else BASE_SCORES[strategy]})

    add("testId", target.get("testId"))
    role = target.get("role")
    acc = target.get("accessibleName") or target.get("text")
    if role and acc:
        add("role", {"role": role, "name": acc})
    add("label", target.get("label"))
    el_id = target.get("id")
    if el_id:
        score = BASE_SCORES["id"] - (45 if _DYNAMIC_ID.search(el_id) else 0)
        add("id", el_id, score)
    add("name", target.get("name"))
    add("placeholder", target.get("placeholder"))
    txt = (target.get("text") or "").strip()
    if txt and len(txt) <= 80 and not re.search(r"\d{4}-\d{2}-\d{2}|\d{2}:\d{2}:\d{2}", txt):
        add("text", txt)
    # Recorder-provided structural fallbacks are intentionally lower priority
    # than semantic locators, but guarantee that ordinary actionable elements
    # still have a deterministic Playwright/Selenium candidate.
    add("css", target.get("css"))
    add("xpath", target.get("xpath"))
    if el_id:
        add("css", f"#{el_id}")
    elif target.get("name"):
        add("css", f"[name='{target['name']}']")

    # De-duplicate equivalent strategy/value pairs while keeping the highest score.
    unique: dict[str, dict[str, Any]] = {}
    for c in candidates:
        key = f"{c['strategy']}::{repr(c['value'])}"
        previous = unique.get(key)
        if previous is None or c["score"] > previous["score"]:
            unique[key] = c
    candidates = list(unique.values())
    for c in candidates:
        c["confidence"] = _confidence(c["score"])
    return sorted(candidates, key=lambda x: x["score"], reverse=True)


def choose_preferred(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    top = dict(candidates[0])
    top["preferred"] = True
    return top
