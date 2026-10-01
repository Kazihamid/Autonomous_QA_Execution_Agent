from __future__ import annotations
from collections import OrderedDict
from typing import Iterable
from .models import RawEvent, SemanticAction

SPECIAL_KEYS = {"Enter", "Tab", "Escape"}
NON_ACTIONABLE_CLICK_TAGS = {"html", "body", "form", "ul", "ol", "section", "main"}

def _is_actionable_click_target(target: dict) -> bool:
    tag = str(target.get("tag") or "").lower()
    role = str(target.get("role") or "").lower()
    if tag in {"a", "button", "input", "select", "textarea", "label"}:
        return True
    if role in {"button", "link", "menuitem", "tab", "option", "checkbox", "radio"}:
        return True
    if target.get("testId"):
        return True
    if tag in NON_ACTIONABLE_CLICK_TAGS:
        return False
    # Custom controls are allowed only when they expose an identifier/name or
    # a concise accessible name. This suppresses accidental container clicks.
    name = str(target.get("accessibleName") or "").strip()
    return bool(target.get("id") or target.get("name") or (name and len(name) <= 80))


def _identity(ev: RawEvent) -> tuple:
    t = ev.target
    return (ev.pageId, ev.frameId, t.get("testId") or t.get("id") or t.get("name") or t.get("label") or t.get("accessibleName") or t.get("tag"))


def _parameter_name(target: dict) -> str:
    raw = str(target.get("name") or target.get("label") or target.get("testId") or target.get("id") or "value")
    if raw.replace('_', '').isalnum() and ' ' not in raw and '-' not in raw:
        return raw[:1].lower() + raw[1:]
    words = ''.join(ch if ch.isalnum() else ' ' for ch in raw).split()
    if not words:
        return "value"
    return words[0].lower() + ''.join(w[:1].upper()+w[1:] for w in words[1:])


def normalize(events: Iterable[RawEvent]) -> list[SemanticAction]:
    evs = list(events)
    actions: list[SemanticAction] = []
    pending_inputs: OrderedDict[tuple, dict] = OrderedDict()
    last_click_by_identity: dict[tuple, int] = {}

    def flush_input(key: tuple):
        data = pending_inputs.pop(key, None)
        if not data:
            return
        ev: RawEvent = data["event"]
        target = ev.target
        if target.get("sensitive"):
            ref = "SECRET_PASSWORD" if target.get("type") == "password" else f"SECRET_{_parameter_name(target).upper()}"
            actions.append(SemanticAction(action="fill", pageId=ev.pageId, frameId=ev.frameId, target=target,
                                          valueSource="secret", reference=ref, sourceEvents=data["seqs"]))
        else:
            actions.append(SemanticAction(action="fill", pageId=ev.pageId, frameId=ev.frameId, target=target,
                                          value=target.get("value"), valueSource="parameter",
                                          reference=_parameter_name(target), sourceEvents=data["seqs"]))

    for idx, ev in enumerate(evs):
        ident = _identity(ev)
        et = ev.eventType
        t = ev.target

        if et in {"input"} and t.get("type") not in {"checkbox", "radio", "file"} and t.get("tag") != "select":
            entry = pending_inputs.setdefault(ident, {"event": ev, "seqs": []})
            entry["event"] = ev
            entry["seqs"].append(ev.sequence)
            continue

        if et in {"blur", "submit"}:
            flush_input(ident)
            if et == "submit":
                continue

        # flush other pending field when interaction moves elsewhere
        for key in list(pending_inputs.keys()):
            if key != ident and et in {"click", "change", "keydown", "navigation"}:
                flush_input(key)

        if et == "navigation":
            # Initial recording navigation is retained. Navigation immediately after click is metadata only.
            if actions and actions[-1].action == "click" and ev.sequence - actions[-1].sourceEvents[-1] <= 2:
                actions[-1].metadata["navigatedTo"] = ev.context.get("url")
            else:
                actions.append(SemanticAction(action="navigate", pageId=ev.pageId, frameId=ev.frameId,
                                              value=ev.context.get("url"), sourceEvents=[ev.sequence]))
        elif et == "change":
            typ = t.get("type")
            tag = t.get("tag")
            # suppress generic click already seen on same control
            if actions and actions[-1].action == "click" and _identity_from_action(actions[-1]) == ident:
                actions.pop()
            if typ == "checkbox":
                actions.append(SemanticAction(action="check" if t.get("checked") else "uncheck", pageId=ev.pageId, frameId=ev.frameId, target=t, sourceEvents=[ev.sequence]))
            elif typ == "radio":
                actions.append(SemanticAction(action="check", pageId=ev.pageId, frameId=ev.frameId, target=t, sourceEvents=[ev.sequence]))
            elif typ == "file":
                files = t.get("files") or []
                logical = files[0]["name"] if files else "asset"
                actions.append(SemanticAction(action="uploadFile", pageId=ev.pageId, frameId=ev.frameId, target=t,
                                              valueSource="asset", reference=logical, sourceEvents=[ev.sequence]))
            elif tag == "select":
                actions.append(SemanticAction(action="select", pageId=ev.pageId, frameId=ev.frameId, target=t,
                                              value=t.get("value"), valueSource="parameter", reference=_parameter_name(t), sourceEvents=[ev.sequence]))
        elif et == "click":
            if t.get("type") in {"checkbox", "radio", "file"} or t.get("tag") == "select":
                # wait for change event to express semantic intent
                continue
            if not _is_actionable_click_target(t):
                continue
            if last_click_by_identity.get(ident) == ev.sequence - 1:
                continue
            actions.append(SemanticAction(action="click", pageId=ev.pageId, frameId=ev.frameId, target=t, sourceEvents=[ev.sequence]))
            last_click_by_identity[ident] = ev.sequence
        elif et == "keydown" and ev.context.get("key") in SPECIAL_KEYS:
            # Preserve user intent: text entered in a field must be emitted before
            # Enter/Tab/Escape on that same field.
            if ident in pending_inputs:
                flush_input(ident)
            actions.append(SemanticAction(action="keyboard", pageId=ev.pageId, frameId=ev.frameId, target=t,
                                          value=ev.context.get("key"), sourceEvents=[ev.sequence]))
        elif et == "assertion":
            actions.append(SemanticAction(action="assert", pageId=ev.pageId, frameId=ev.frameId, target=t,
                                          value=ev.context.get("expected"), metadata={"assertionType": ev.context.get("assertionType", "visible")}, sourceEvents=[ev.sequence]))
        elif et == "checkpoint":
            actions.append(SemanticAction(action="checkpoint", pageId=ev.pageId, frameId=ev.frameId,
                                          metadata={"description": ev.context.get("description", "")}, sourceEvents=[ev.sequence]))
        elif et == "extract":
            actions.append(SemanticAction(action="extractValue", pageId=ev.pageId, frameId=ev.frameId, target=t,
                                          reference=ev.context.get("variableName"), metadata={"property": ev.context.get("property", "text")}, sourceEvents=[ev.sequence]))

    for key in list(pending_inputs.keys()):
        flush_input(key)
    return actions


def _identity_from_action(action: SemanticAction) -> tuple:
    t = action.target
    return (action.pageId, action.frameId, t.get("testId") or t.get("id") or t.get("name") or t.get("label") or t.get("accessibleName") or t.get("tag"))
