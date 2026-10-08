from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from .instrumentation import RECORDER_INIT_SCRIPT
from .models import RawEvent, RecordingSession, SessionStatus
from .normalizer import normalize
from app.ir.builder import build_ir
from app.ir.validator import validate_ir

TERMINAL = {SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.CANCELLED}

@dataclass
class RuntimeSession:
    model: RecordingSession
    playwright: Playwright | None = None
    browser_obj: Browser | None = None
    context: BrowserContext | None = None
    pages: dict[Page, str] = field(default_factory=dict)
    frames: dict[Any, str] = field(default_factory=dict)
    events: list[RawEvent] = field(default_factory=list)
    sequence: int = 0
    ir: dict | None = None

class RecorderManager:
    def __init__(self):
        self.sessions: dict[str, RuntimeSession] = {}

    def has_active_session(self) -> bool:
        return any(rt.model.status not in TERMINAL for rt in self.sessions.values())

    async def discard_active(self) -> int:
        """Ends every session that is still open and closes its browser.

        The MVP worker drives a single managed browser. A session that was left open (a closed tab, a recording that was never
        finished or cancelled) would otherwise block every later recording until the worker was restarted.
        """
        ended = 0
        for rt in list(self.sessions.values()):
            if rt.model.status in TERMINAL:
                continue
            rt.model.status = SessionStatus.CANCELLED
            await self._cleanup(rt)
            ended += 1
        return ended

    async def create_session(self, start_url: str, browser: str = "chromium", headless: bool = False, scenario_name: str = "Recorded Scenario") -> RecordingSession:
        sid = str(uuid.uuid4())
        model = RecordingSession(
            sessionId=sid,
            startUrl=start_url,
            scenarioName=scenario_name,
            browser=browser,
            headless=headless,
            status=SessionStatus.PROVISIONING,
        )
        rt = RuntimeSession(model=model)
        self.sessions[sid] = rt
        try:
            model.status = SessionStatus.STARTING_BROWSER
            rt.playwright = await async_playwright().start()
            browser_key = browser.lower()
            if browser_key != "chromium":
                raise ValueError("Vertical Slice 2 managed-browser MVP currently supports Chromium only.")
            launch_kwargs: dict[str, Any] = {
                "headless": headless,
                "args": ["--no-sandbox", "--disable-dev-shm-usage", "--start-maximized"],
            }
            chromium_path = os.getenv("RECORDER_CHROMIUM_PATH", "/usr/bin/chromium")
            if os.path.exists(chromium_path):
                launch_kwargs["executable_path"] = chromium_path
            rt.browser_obj = await rt.playwright.chromium.launch(**launch_kwargs)
            rt.context = await rt.browser_obj.new_context(
                ignore_https_errors=True,
                viewport=None if not headless else {"width": 1440, "height": 900},
            )
            await rt.context.expose_binding("__recorderEmit", lambda source, payload: self._on_browser_event(sid, source, payload))
            await rt.context.add_init_script(RECORDER_INIT_SCRIPT)
            rt.context.on("page", lambda p: asyncio.create_task(self._register_page(sid, p)))
            page = await rt.context.new_page()
            await self._register_page(sid, page)
            await page.goto(start_url, wait_until="domcontentloaded", timeout=60000)
            model.status = SessionStatus.READY
        except Exception as exc:
            model.status = SessionStatus.FAILED
            model.error = str(exc)
            await self._cleanup(rt)
        return model

    async def _register_page(self, sid: str, page: Page):
        rt = self.sessions[sid]
        if page in rt.pages:
            return
        rt.pages[page] = f"page-{len(rt.pages)+1}"
        page.on("framenavigated", lambda frame: asyncio.create_task(self._on_navigation(sid, page, frame)))

    async def _on_navigation(self, sid: str, page: Page, frame):
        rt = self.sessions.get(sid)
        if not rt or rt.model.status != SessionStatus.RECORDING or frame != page.main_frame:
            return
        await self._append_event(rt, page, frame, {"eventType": "navigation", "target": {}, "context": {"url": frame.url}})

    async def _on_browser_event(self, sid: str, source: dict, payload: dict):
        rt = self.sessions.get(sid)
        if not rt or rt.model.status != SessionStatus.RECORDING:
            return
        page = source.get("page")
        frame = source.get("frame")
        if page and page not in rt.pages:
            await self._register_page(sid, page)
        await self._append_event(rt, page, frame, payload)

    async def _append_event(self, rt: RuntimeSession, page: Page | None, frame: Any, payload: dict):
        rt.sequence += 1
        page_id = rt.pages.get(page, "page-unknown")
        frame_id = "frame-main"
        if page and frame and frame != page.main_frame:
            if frame not in rt.frames:
                rt.frames[frame] = f"frame-{len(rt.frames)+1}"
            frame_id = rt.frames[frame]
        rt.events.append(RawEvent(
            sessionId=rt.model.sessionId,
            sequence=rt.sequence,
            timestamp=datetime.now(timezone.utc).isoformat(),
            pageId=page_id,
            frameId=frame_id,
            eventType=payload.get("eventType", "unknown"),
            target=payload.get("target") or {},
            context=payload.get("context") or {},
        ))

    async def start(self, sid: str) -> RecordingSession:
        rt = self._get(sid)
        if rt.model.status not in {SessionStatus.READY, SessionStatus.PAUSED}:
            raise ValueError(f"Invalid start transition from {rt.model.status}")
        rt.model.status = SessionStatus.RECORDING
        page = self.active_page(sid)
        await self._append_event(rt, page, page.main_frame, {"eventType": "navigation", "target": {}, "context": {"url": page.url}})
        return rt.model

    async def pause(self, sid: str) -> RecordingSession:
        rt = self._get(sid)
        if rt.model.status != SessionStatus.RECORDING:
            raise ValueError(f"Invalid pause transition from {rt.model.status}")
        rt.model.status = SessionStatus.PAUSED
        return rt.model

    async def resume(self, sid: str) -> RecordingSession:
        return await self.start(sid)

    async def add_assertion(self, sid: str, selector: str, assertion_type: str = "visible", expected: str | None = None):
        rt = self._get(sid)
        if rt.model.status != SessionStatus.RECORDING:
            raise ValueError("Session is not recording")
        page = self.active_page(sid)
        payload = await page.eval_on_selector(selector, """(el, args) => ({
          eventType:'assertion',
          target:{tag:el.tagName.toLowerCase(), type:(el.getAttribute('type')||'').toLowerCase(), id:el.id||'', name:el.getAttribute('name')||'', role:el.getAttribute('role')||'', accessibleName:(el.getAttribute('aria-label')||el.innerText||'').trim(), label:(el.labels&&el.labels.length?Array.from(el.labels).map(x=>x.innerText).join(' '):''), placeholder:el.getAttribute('placeholder')||'', text:(el.innerText||'').trim(), testId:el.getAttribute('data-testid')||'', sensitive:false},
          context:{url:location.href, assertionType:args.assertionType, expected:args.expected}
        })""", {"assertionType": assertion_type, "expected": expected})
        await self._append_event(rt, page, page.main_frame, payload)

    async def add_checkpoint(self, sid: str, description: str):
        rt = self._get(sid)
        if rt.model.status != SessionStatus.RECORDING:
            raise ValueError("Session is not recording")
        page = self.active_page(sid)
        await self._append_event(rt, page, page.main_frame, {
            "eventType": "checkpoint",
            "target": {},
            "context": {"url": page.url, "description": description},
        })

    async def finish(self, sid: str) -> dict:
        rt = self._get(sid)
        if rt.model.status not in {SessionStatus.RECORDING, SessionStatus.PAUSED}:
            raise ValueError(f"Invalid finish transition from {rt.model.status}")
        rt.model.status = SessionStatus.FINISHING
        rt.model.status = SessionStatus.NORMALIZING
        actions = normalize(rt.events)
        rt.model.status = SessionStatus.BUILDING_IR
        rt.ir = build_ir(actions, scenario_id=rt.model.sessionId, scenario_name=rt.model.scenarioName)
        rt.model.status = SessionStatus.VALIDATING
        errors = validate_ir(rt.ir)
        if errors:
            rt.model.status = SessionStatus.FAILED
            rt.model.error = "; ".join(errors)
        else:
            rt.model.status = SessionStatus.COMPLETED
        response = {
            "session": rt.model.model_dump(),
            "rawEventCount": len(rt.events),
            "semanticActionCount": len(actions),
            "errors": errors,
            "ir": rt.ir,
        }
        await self._cleanup(rt)
        return response

    async def cancel(self, sid: str) -> RecordingSession:
        rt = self._get(sid)
        if rt.model.status in {SessionStatus.RECORDING, SessionStatus.PAUSED}:
            # Cancelling a take in progress discards what was captured and returns to READY so the user can press
            # "Start Recording" again. The managed browser stays open and is sent back to the start page.
            await self._reset_take(rt)
            return rt.model
        rt.model.status = SessionStatus.CANCELLED
        await self._cleanup(rt)
        return rt.model

    async def _reset_take(self, rt: RuntimeSession):
        rt.model.status = SessionStatus.READY
        rt.events.clear()
        rt.frames.clear()
        rt.sequence = 0
        rt.ir = None
        rt.model.error = None
        if not rt.context:
            return
        try:
            await rt.context.clear_cookies()
            pages = list(rt.context.pages)
            for extra in pages[1:]:
                try:
                    await extra.close()
                except Exception:
                    pass
            page = rt.context.pages[0] if rt.context.pages else await rt.context.new_page()
            await self._register_page(rt.model.sessionId, page)
            await page.goto(rt.model.startUrl, wait_until="domcontentloaded", timeout=60000)
        except Exception:
            # The take is already discarded; a failed reload must not leave the session unusable.
            pass

    async def paste_text(self, sid: str, text: str) -> None:
        """Inserts text into the focused element of the managed browser, like a paste (fires input events)."""
        rt = self._get(sid)
        if rt.model.status in TERMINAL or not rt.context:
            raise ValueError("Session is not active")
        page = self.active_page(sid)
        await page.keyboard.insert_text(text)

    async def _cleanup(self, rt: RuntimeSession):
        try:
            if rt.context:
                await rt.context.close()
        except Exception:
            pass
        try:
            if rt.browser_obj:
                await rt.browser_obj.close()
        except Exception:
            pass
        try:
            if rt.playwright:
                await rt.playwright.stop()
        except Exception:
            pass
        rt.context = None
        rt.browser_obj = None
        rt.playwright = None

    def active_page(self, sid: str) -> Page:
        rt = self._get(sid)
        if not rt.context:
            raise RuntimeError("Browser context unavailable")
        pages = rt.context.pages
        if not pages:
            raise RuntimeError("No active page")
        return pages[-1]

    def events(self, sid: str) -> list[dict]:
        return [e.model_dump() for e in self._get(sid).events]

    def ir(self, sid: str) -> dict | None:
        return self._get(sid).ir

    def model(self, sid: str) -> RecordingSession:
        return self._get(sid).model

    def _get(self, sid: str) -> RuntimeSession:
        if sid not in self.sessions:
            raise KeyError(sid)
        return self.sessions[sid]

recorder_manager = RecorderManager()
