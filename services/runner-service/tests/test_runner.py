import os
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import build_child_env, required_runtime_variables, safe_relative_path  # noqa: E402


@pytest.mark.parametrize("bad", ["/etc/passwd", "../x", "a/../../x", "", "C:\\..\\x"])
def test_unsafe_paths_rejected(bad):
    with pytest.raises(HTTPException):
        safe_relative_path(bad)


def test_safe_path_ok():
    assert safe_relative_path("tests/test_a.py") == Path("tests/test_a.py")


def test_child_env_withholds_unrelated_secrets(monkeypatch):
    monkeypatch.setenv("SECRET_PASSWORD", "pw")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "leak")
    env = build_child_env("https://qa.example", ["SECRET_PASSWORD"], {"USER_NAME": "bob"})
    assert env["SECRET_PASSWORD"] == "pw"
    assert env["BASE_URL"] == "https://qa.example"
    assert env["USER_NAME"] == "bob"
    assert "AWS_SECRET_ACCESS_KEY" not in env


def test_required_variables(tmp_path):
    (tmp_path / ".env.example").write_text("BASE_URL=\nSECRET_X=\nOPT=1\n# c\n")
    assert required_runtime_variables(tmp_path) == ["SECRET_X"]


def _wait(client, run_id, timeout=30):
    import time
    end = time.time() + timeout
    while time.time() < end:
        st = client.get(f"/api/v1/runs/{run_id}").json()
        if st["status"] not in ("QUEUED", "RUNNING"):
            return st
        time.sleep(0.2)
    raise AssertionError("run did not finish")


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


PASSING = {"path": "tests/test_demo.py", "content": 'def test_demo():\n    print("[IR-STEP] step-001 navigate (1/2)", flush=True)\n    print("[IR-STEP] step-002 click (2/2)", flush=True)\n    assert True\n'}
FAILING = {"path": "tests/test_demo.py", "content": 'def test_demo():\n    print("[IR-STEP] step-001 navigate (1/3)", flush=True)\n    assert False\n'}


def test_async_run_streams_steps_and_passes():
    c = _client()
    h = c.post("/api/v1/runs", json={"scenarioId": "s", "scenarioName": "n", "baseUrl": "https://x.example", "files": [PASSING]}).json()
    st = _wait(c, h["runId"])
    assert st["status"] == "PASSED" and st["exitCode"] == 0
    assert st["totalSteps"] == 2 and st["currentStep"] == 2 and st["currentAction"] == "click"
    assert "[IR-STEP] step-001" in st["output"]


def test_async_run_failure_reports_failed_with_output():
    c = _client()
    h = c.post("/api/v1/runs", json={"scenarioId": "s", "scenarioName": "n", "baseUrl": "https://x.example", "files": [FAILING]}).json()
    st = _wait(c, h["runId"])
    assert st["status"] == "FAILED" and st["exitCode"] != 0
    assert "assert False" in st["output"]


def test_async_run_unknown_id_is_404():
    assert _client().get("/api/v1/runs/nope").status_code == 404
