from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.recorder.manager import recorder_manager

router = APIRouter(prefix="/api/v1")

class CreateSession(BaseModel):
    startUrl: str
    browser: str = "chromium"
    headless: bool = False
    scenarioName: str = "Recorded Scenario"

class AssertionRequest(BaseModel):
    selector: str
    assertionType: str = "visible"
    expected: str | None = None

class PasteRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)

class CheckpointRequest(BaseModel):
    description: str = Field(min_length=1, max_length=500)

@router.post("/sessions")
async def create_session(req: CreateSession):
    if recorder_manager.has_active_session():
        raise HTTPException(409, "A managed browser recording session is already active in this MVP worker.")
    model = await recorder_manager.create_session(req.startUrl, req.browser, req.headless, req.scenarioName)
    if model.status.value == "FAILED":
        raise HTTPException(502, model.error or "Managed browser failed to start.")
    return model.model_dump()

@router.get("/sessions/{sid}")
async def get_session(sid: str):
    try:
        return recorder_manager.model(sid).model_dump()
    except KeyError:
        raise HTTPException(404, "Session not found")

@router.post("/sessions/{sid}/start")
async def start(sid: str):
    try:
        return (await recorder_manager.start(sid)).model_dump()
    except KeyError:
        raise HTTPException(404, "Session not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))

@router.post("/sessions/{sid}/pause")
async def pause(sid: str):
    try:
        return (await recorder_manager.pause(sid)).model_dump()
    except KeyError:
        raise HTTPException(404, "Session not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))

@router.post("/sessions/{sid}/resume")
async def resume(sid: str):
    try:
        return (await recorder_manager.resume(sid)).model_dump()
    except KeyError:
        raise HTTPException(404, "Session not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))

@router.post("/sessions/{sid}/assertions")
async def add_assertion(sid: str, req: AssertionRequest):
    try:
        await recorder_manager.add_assertion(sid, req.selector, req.assertionType, req.expected)
        return {"ok": True}
    except KeyError:
        raise HTTPException(404, "Session not found")
    except Exception as exc:
        raise HTTPException(400, str(exc))

@router.post("/sessions/{sid}/checkpoints")
async def checkpoint(sid: str, req: CheckpointRequest):
    try:
        await recorder_manager.add_checkpoint(sid, req.description)
        return {"ok": True}
    except KeyError:
        raise HTTPException(404, "Session not found")
    except Exception as exc:
        raise HTTPException(400, str(exc))

@router.post("/sessions/{sid}/paste")
async def paste(sid: str, req: PasteRequest):
    try:
        await recorder_manager.paste_text(sid, req.text)
        return {"ok": True}
    except KeyError:
        raise HTTPException(404, "Session not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    except Exception:
        raise HTTPException(400, "Text could not be inserted. Click the field in the browser first.")

@router.post("/sessions/{sid}/finish")
async def finish(sid: str):
    try:
        return await recorder_manager.finish(sid)
    except KeyError:
        raise HTTPException(404, "Session not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))

@router.post("/sessions/{sid}/cancel")
async def cancel(sid: str):
    try:
        return (await recorder_manager.cancel(sid)).model_dump()
    except KeyError:
        raise HTTPException(404, "Session not found")

@router.get("/sessions/{sid}/events")
async def events(sid: str):
    try:
        return recorder_manager.events(sid)
    except KeyError:
        raise HTTPException(404, "Session not found")

@router.get("/sessions/{sid}/ir")
async def ir(sid: str):
    try:
        return recorder_manager.ir(sid)
    except KeyError:
        raise HTTPException(404, "Session not found")
