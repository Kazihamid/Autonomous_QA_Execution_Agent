import asyncio
import pytest
from app.recorder.manager import RecorderManager, RuntimeSession
from app.recorder.models import RawEvent, RecordingSession, SessionStatus


def _session(status):
    model = RecordingSession(sessionId="s1", startUrl="https://example.test/", scenarioName="x", browser="chromium", status=status)
    rt = RuntimeSession(model=model)
    rt.events.append(RawEvent(sessionId="s1", sequence=1, timestamp="t", pageId="page-1", frameId="frame-main", eventType="click", target={}, context={}))
    rt.sequence = 1
    return rt


def _mgr(rt):
    m = RecorderManager()
    m.sessions["s1"] = rt
    return m


@pytest.mark.parametrize("status", [SessionStatus.RECORDING, SessionStatus.PAUSED])
def test_cancel_during_take_returns_to_ready_and_clears_events(status):
    rt = _session(status)
    model = asyncio.run(_mgr(rt).cancel("s1"))
    assert model.status == SessionStatus.READY
    assert rt.events == [] and rt.sequence == 0


def test_cancel_before_start_still_ends_session():
    rt = _session(SessionStatus.READY)
    model = asyncio.run(_mgr(rt).cancel("s1"))
    assert model.status == SessionStatus.CANCELLED


def test_paste_requires_active_session():
    rt = _session(SessionStatus.CANCELLED)
    with pytest.raises(ValueError):
        asyncio.run(_mgr(rt).paste_text("s1", "abc"))
