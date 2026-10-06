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
