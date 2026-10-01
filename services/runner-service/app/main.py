from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Autonomous QA Execution Agent Local Runner", version="0.3.2")


class GeneratedFile(BaseModel):
    path: str
    content: str


class RunRequest(BaseModel):
    scenarioId: str
    scenarioName: str
    baseUrl: str
    files: list[GeneratedFile]
    timeoutSeconds: int = Field(default=120, ge=5, le=600)


class RunResponse(BaseModel):
    scenarioId: str
    scenarioName: str
    status: Literal["PASSED", "FAILED", "TIMED_OUT", "ERROR"]
    exitCode: int | None = None
    durationMs: int
    stdout: str = ""
    stderr: str = ""


def safe_relative_path(value: str) -> Path:
    normalized = value.replace("\\", "/")
    posix = PurePosixPath(normalized)
    if posix.is_absolute() or ".." in posix.parts or not posix.parts:
        raise HTTPException(status_code=422, detail=f"Unsafe generated path: {value}")
    return Path(*posix.parts)


def clipped(value: str, limit: int = 16000) -> str:
    if len(value) <= limit:
        return value
    return value[-limit:] + "\n[output clipped]"


def required_runtime_variables(root: Path) -> list[str]:
    env_example = root / ".env.example"
    if not env_example.exists():
        return []
    required: list[str] = []
    ignored = {"BASE_URL", "BROWSER", "HEADLESS"}
    for raw in env_example.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in ignored and not value.strip():
            required.append(key)
    return sorted(set(required))


def ir_parameter_defaults(root: Path) -> dict[str, str]:
    path = root / "automation-ir.json"
    if not path.exists():
        return {}
    try:
        import json
        ir = json.loads(path.read_text(encoding="utf-8"))
        out: dict[str, str] = {}
        for key, config in (ir.get("parameters") or {}).items():
            if not isinstance(config, dict):
                continue
            value = config.get("default")
            if value is not None:
                out[str(key)] = str(value)
        return out
    except Exception:
        return {}


@app.get("/health")
def health():
    return {"status": "UP", "service": "runner", "version": "0.3.2"}


@app.post("/api/v1/run", response_model=RunResponse)
def run(request: RunRequest):
    if not request.files:
        raise HTTPException(status_code=422, detail="Generated project contains no files.")

    started = time.monotonic()
    try:
        with tempfile.TemporaryDirectory(prefix="automation-run-") as tmp:
            root = Path(tmp)
            for item in request.files:
                target = root / safe_relative_path(item.path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(item.content, encoding="utf-8")

            if not (root / "pytest.ini").exists() and not (root / "tests").exists():
                raise HTTPException(status_code=422, detail="Local runner currently supports Playwright + Pytest implementations only.")

            env = os.environ.copy()
            env["BASE_URL"] = request.baseUrl
            env["BROWSER"] = "chromium"
            env["HEADLESS"] = "true"
            env["PYTHONUNBUFFERED"] = "1"
            for key, value in ir_parameter_defaults(root).items():
                env.setdefault(key, value)

            missing = [key for key in required_runtime_variables(root) if not env.get(key)]
            if missing:
                return RunResponse(
                    scenarioId=request.scenarioId,
                    scenarioName=request.scenarioName,
                    status="ERROR",
                    durationMs=int((time.monotonic() - started) * 1000),
                    stderr=(
                        "Missing runtime environment variable(s): "
                        + ", ".join(missing)
                        + ". Configure them in the runner runtime environment (for local Docker, use .env.runtime) and restart the runner."
                    ),
                )

            try:
                completed = subprocess.run(
                    [sys.executable, "-m", "pytest", "-q"],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=request.timeoutSeconds,
                    check=False,
                )
                status: Literal["PASSED", "FAILED"] = "PASSED" if completed.returncode == 0 else "FAILED"
                return RunResponse(
                    scenarioId=request.scenarioId,
                    scenarioName=request.scenarioName,
                    status=status,
                    exitCode=completed.returncode,
                    durationMs=int((time.monotonic() - started) * 1000),
                    stdout=clipped(completed.stdout),
                    stderr=clipped(completed.stderr),
                )
            except subprocess.TimeoutExpired as ex:
                return RunResponse(
                    scenarioId=request.scenarioId,
                    scenarioName=request.scenarioName,
                    status="TIMED_OUT",
                    durationMs=int((time.monotonic() - started) * 1000),
                    stdout=clipped((ex.stdout or "") if isinstance(ex.stdout, str) else ""),
                    stderr=clipped((ex.stderr or "") if isinstance(ex.stderr, str) else ""),
                )
    except HTTPException:
        raise
    except Exception as ex:
        return RunResponse(
            scenarioId=request.scenarioId,
            scenarioName=request.scenarioName,
            status="ERROR",
            durationMs=int((time.monotonic() - started) * 1000),
            stderr=str(ex),
        )

