from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

class SessionStatus(str, Enum):
    REQUESTED = "REQUESTED"
    PROVISIONING = "PROVISIONING"
    STARTING_BROWSER = "STARTING_BROWSER"
    READY = "READY"
    RECORDING = "RECORDING"
    PAUSED = "PAUSED"
    FINISHING = "FINISHING"
    NORMALIZING = "NORMALIZING"
    BUILDING_IR = "BUILDING_IR"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class RawEvent(BaseModel):
    sessionId: str
    sequence: int
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    pageId: str
    frameId: str
    eventType: str
    target: dict[str, Any] = Field(default_factory=dict)
    context: dict[str, Any] = Field(default_factory=dict)

class SemanticAction(BaseModel):
    action: str
    pageId: str
    frameId: str = "frame-main"
    target: dict[str, Any] = Field(default_factory=dict)
    value: Any | None = None
    valueSource: str | None = None
    reference: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    sourceEvents: list[int] = Field(default_factory=list)

class RecordingSession(BaseModel):
    sessionId: str
    startUrl: str
    scenarioName: str = "Recorded Scenario"
    browser: str = "chromium"
    headless: bool = False
    status: SessionStatus = SessionStatus.REQUESTED
    createdAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: str | None = None
