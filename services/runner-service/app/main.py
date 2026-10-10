from __future__ import annotations

import collections
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import runtime_secrets

app = FastAPI(title="Autonomous QA Execution Agent Local Runner", version="0.4.0")


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


def optional_runtime_variables(root: Path) -> list[str]:
    """Names listed in .env.example as '# optional: NAME'. They are passed on when set in the .env file and are never required."""
    env_example = root / ".env.example"
    if not env_example.exists():
        return []
    names: list[str] = []
    for raw in env_example.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.lower().startswith("# optional:"):
            name = line.split(":", 1)[1].strip()
            if name and name.replace("_", "").isalnum():
                names.append(name)
    return sorted(set(names))


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


# Only these host variables are visible to generated test code. Everything else in the
# runner container environment (including unrelated secrets) is withheld.
SAFE_HOST_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "TZ", "TMPDIR",
                 "PLAYWRIGHT_BROWSERS_PATH", "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD")


def build_child_env(base_url: str, required: list[str], ir_defaults: dict[str, str],
                    secrets_source: dict[str, str] | None = None, notes: list[str] | None = None) -> dict[str, str]:
    env = {k: os.environ[k] for k in SAFE_HOST_ENV if k in os.environ}
    env.update({"BASE_URL": base_url, "BROWSER": "chromium", "HEADLESS": "true", "PYTHONUNBUFFERED": "1"})
    # Secrets: only the variables the generated project declares in its .env.example. Each is resolved for the
    # environment and user being tested (see runtime_secrets), from a file that is re-read on every run.
    source = secrets_source if secrets_source is not None else runtime_secrets.load_source()
    for key in required:
        value, used = runtime_secrets.resolve(key, base_url, ir_defaults, source)
        if value:
            env[key] = value
            if notes is not None:
                notes.append(f"[runner] secret {key} taken from {used}")
        elif notes is not None:
            notes.append(f"[runner] secret {key} not found; looked for: " + ", ".join(runtime_secrets.candidates(key, base_url, ir_defaults)))
    for key, value in ir_defaults.items():
        env.setdefault(key, value)
    # A signed-in session is kept for the environment for a while, so the scenario run after a sign-in scenario starts signed in.
    try:
        import hashlib
        from urllib.parse import urlsplit
        parts = urlsplit(base_url)
        folder = Path(tempfile.gettempdir()) / "aqea-session"
        folder.mkdir(parents=True, exist_ok=True)
        env["SESSION_STATE_FILE"] = str(folder / (hashlib.sha1(f"{parts.scheme}://{parts.netloc}".encode()).hexdigest()[:16] + ".json"))
    except Exception:
        pass
    return env


@app.get("/health")
def health():
    return {"status": "UP", "service": "runner", "version": "0.4.0"}


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

            runtime_defaults = ir_parameter_defaults(root)
            required = required_runtime_variables(root)
            secret_notes: list[str] = []
            env = build_child_env(request.baseUrl, required, runtime_defaults, notes=secret_notes)
            for _opt in optional_runtime_variables(root):
                _value, _used = runtime_secrets.resolve(_opt, request.baseUrl, runtime_defaults, runtime_secrets.load_source())
                if _value:
                    env[_opt] = _value

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
                        + ". Add one of the names below to the .env file in the project folder; no restart is needed.\n" + "\n".join(secret_notes)
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



# ---------------------------------------------------------------------------
# Asynchronous runs with live output (used by the Control Plane run jobs)
# ---------------------------------------------------------------------------
STEP_RE = re.compile(r"\[IR-STEP\]\s+(\S+)\s+(\S+)\s+\((\d+)/(\d+)\)")
MAX_RUNS_KEPT = 100
MAX_OUTPUT_CHARS = 64000
_runs: "collections.OrderedDict[str, dict]" = collections.OrderedDict()
_runs_lock = threading.Lock()
_slots = threading.Semaphore(2)


class RunHandle(BaseModel):
    runId: str


class RunStatus(BaseModel):
    runId: str
    status: Literal["QUEUED", "RUNNING", "PASSED", "FAILED", "TIMED_OUT", "ERROR"]
    exitCode: int | None = None
    durationMs: int = 0
    output: str = ""
    currentStep: int = 0
    totalSteps: int = 0
    currentStepId: str = ""
    currentAction: str = ""
    message: str = ""


def _snapshot(rec: dict) -> RunStatus:
    with _runs_lock:
        started = rec["started"]
        end = rec["ended"] or time.monotonic()
        return RunStatus(
            runId=rec["runId"], status=rec["status"], exitCode=rec["exitCode"],
            durationMs=int((end - started) * 1000) if started else 0,
            output=clipped("".join(rec["output"]), 16000),
            currentStep=rec["currentStep"], totalSteps=rec["totalSteps"],
            currentStepId=rec["currentStepId"], currentAction=rec["currentAction"],
            message=rec["message"],
        )


def _append(rec: dict, text: str) -> None:
    with _runs_lock:
        rec["output"].append(text)
        rec["size"] += len(text)
        while rec["size"] > MAX_OUTPUT_CHARS and len(rec["output"]) > 1:
            rec["size"] -= len(rec["output"].pop(0))


def _finish(rec: dict, status: str, exit_code: int | None = None, message: str = "") -> None:
    with _runs_lock:
        rec["status"] = status
        rec["exitCode"] = exit_code
        rec["message"] = message
        rec["ended"] = time.monotonic()


def _execute_async(rec: dict, request: RunRequest) -> None:
    with _slots:
        rec["started"] = time.monotonic()
        with _runs_lock:
            rec["status"] = "RUNNING"
        try:
            with tempfile.TemporaryDirectory(prefix="automation-run-") as tmp:
                root = Path(tmp)
                for item in request.files:
                    target = root / safe_relative_path(item.path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(item.content, encoding="utf-8")
                if not (root / "pytest.ini").exists() and not (root / "tests").exists():
                    _finish(rec, "ERROR", None, "Local runner currently supports Playwright + Pytest implementations only.")
                    return
                required = required_runtime_variables(root)
                secret_notes: list[str] = []
                env = build_child_env(request.baseUrl, required, ir_parameter_defaults(root), notes=secret_notes)
                for _opt in optional_runtime_variables(root):
                    _value, _used = runtime_secrets.resolve(_opt, request.baseUrl, ir_parameter_defaults(root), runtime_secrets.load_source())
                    if _value:
                        env[_opt] = _value
                        secret_notes.append(f"[runner] optional {_opt} taken from {_used}")
                missing = [key for key in required if not env.get(key)]
                if missing:
                    msg = ("Missing runtime environment variable(s): " + ", ".join(missing)
                           + ". Add one of the names below to the .env file in the project folder; no restart is needed.\n" + "\n".join(secret_notes))
                    _append(rec, msg + "\n")
                    _finish(rec, "ERROR", None, msg)
                    return
                _append(rec, f"[runner] BASE_URL={request.baseUrl}\n")
                for note in secret_notes:
                    _append(rec, note + "\n")
                proc = subprocess.Popen(
                    [sys.executable, "-u", "-m", "pytest", "-q", "-s", "--tb=short", "-p", "no:cacheprovider"],
                    cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                )
                timed_out = threading.Event()

                def kill_on_timeout() -> None:
                    timed_out.set()
                    try:
                        proc.kill()
                    except Exception:
                        pass

                timer = threading.Timer(request.timeoutSeconds, kill_on_timeout)
                timer.start()
                try:
                    assert proc.stdout is not None
                    for line in proc.stdout:
                        _append(rec, line)
                        m = STEP_RE.search(line)
                        if m:
                            with _runs_lock:
                                rec["currentStepId"], rec["currentAction"] = m.group(1), m.group(2)
                                rec["currentStep"], rec["totalSteps"] = int(m.group(3)), int(m.group(4))
                    code = proc.wait()
                finally:
                    timer.cancel()
                if timed_out.is_set():
                    _finish(rec, "TIMED_OUT", None, f"Timed out after {request.timeoutSeconds}s")
                else:
                    _finish(rec, "PASSED" if code == 0 else "FAILED", code)
        except HTTPException as ex:
            _finish(rec, "ERROR", None, str(ex.detail))
        except Exception as ex:  # noqa: BLE001
            _append(rec, f"[runner] {ex}\n")
            _finish(rec, "ERROR", None, str(ex))


@app.post("/api/v1/runs", response_model=RunHandle)
def start_run(request: RunRequest):
    if not request.files:
        raise HTTPException(status_code=422, detail="Generated project contains no files.")
    run_id = uuid.uuid4().hex
    rec = {"runId": run_id, "status": "QUEUED", "exitCode": None, "started": None, "ended": None, "output": [], "size": 0,
           "currentStep": 0, "totalSteps": 0, "currentStepId": "", "currentAction": "", "message": ""}
    with _runs_lock:
        _runs[run_id] = rec
        while len(_runs) > MAX_RUNS_KEPT:
            _runs.popitem(last=False)
    threading.Thread(target=_execute_async, args=(rec, request), daemon=True, name=f"run-{run_id[:8]}").start()
    return RunHandle(runId=run_id)


@app.get("/api/v1/runs/{run_id}", response_model=RunStatus)
def get_run(run_id: str):
    with _runs_lock:
        rec = _runs.get(run_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return _snapshot(rec)
