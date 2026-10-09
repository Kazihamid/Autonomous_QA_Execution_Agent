"""Resolves the secret (password) a generated test needs for the environment and user it runs against.

A scenario stores only a secret NAME (for example SECRET_PASSWORD). At run time the runner looks the value up, most specific first:

    SECRET_PASSWORD_<ENV>_<USER>   one user on one environment   (e.g. SECRET_PASSWORD_ERPSTAGING_153872)
    SECRET_PASSWORD_<ENV>          every user on one environment  (e.g. SECRET_PASSWORD_ENV27)
    SECRET_PASSWORD_<USER>         one user on any environment
    SECRET_PASSWORD                fallback for everything

<ENV> is the first part of the website address (env27.erp.bracits.net -> ENV27, erpstaging.brac.net -> ERPSTAGING) and
<USER> is the scenario's user name parameter. The values come from a file that is read again on every run, so a changed
password takes effect on the next run without restarting anything. Values are never logged, only the variable NAME used.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_SECRETS_FILE = "/run/runtime/.env"
USER_PARAMETERS = ("username", "userName", "user", "userId", "userid", "login", "loginId")


def tag(value: str) -> str:
    """Upper-case letters/digits/underscores only, e.g. 'erp-staging' -> 'ERP_STAGING'."""
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value or "")).strip("_").upper()


def environment_tag(base_url: str) -> str:
    host = urlparse(base_url or "").hostname or ""
    return tag(host.split(".")[0]) if host else ""


def login_user(parameters: dict[str, str]) -> str:
    for key in USER_PARAMETERS:
        if parameters.get(key):
            return tag(parameters[key])
    return ""


def candidates(name: str, base_url: str, parameters: dict[str, str]) -> list[str]:
    base, env, user = tag(name), environment_tag(base_url), login_user(parameters)
    out: list[str] = []
    if env and user:
        out.append(f"{base}_{env}_{user}")
    if env:
        out.append(f"{base}_{env}")
    if user:
        out.append(f"{base}_{user}")
    out.append(base)
    # A secret recorded under a name that already ends with the user (SECRET_PASSWORD_153872) also finds the
    # per-environment line written without it: SECRET_PASSWORD_ERPSTAGING_153872, SECRET_PASSWORD_ERPSTAGING, SECRET_PASSWORD.
    if user and base.endswith("_" + user) and len(base) > len(user) + 1:
        stem = base[: -(len(user) + 1)]
        if env:
            out.append(f"{stem}_{env}_{user}")
            out.append(f"{stem}_{env}")
        out.append(f"{stem}_{user}")
        out.append(stem)
    return list(dict.fromkeys(out))


def parse_env_text(text: str) -> dict[str, str]:
    """Parses KEY=VALUE lines. Supports comments, 'export ', and single or double quoted values (quotes removed)."""
    values: dict[str, str] = {}
    for raw in text.lstrip("\ufeff").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def load_source(path: str | None = None) -> dict[str, str]:
    """Container environment overlaid with the secrets file, read fresh each call."""
    source = {k: v for k, v in os.environ.items()}
    file_path = Path(path or os.environ.get("RUNTIME_SECRETS_FILE", DEFAULT_SECRETS_FILE))
    try:
        if file_path.is_file():
            source.update(parse_env_text(file_path.read_text(encoding="utf-8")))
    except OSError:
        pass
    return source


def resolve(name: str, base_url: str, parameters: dict[str, str], source: dict[str, str]) -> tuple[str | None, str | None]:
    """Returns (value, variable name used). Variable names are matched case-insensitively."""
    upper = {k.upper(): (k, v) for k, v in source.items()}
    for candidate in candidates(name, base_url, parameters):
        hit = upper.get(candidate)
        if hit and hit[1] != "":
            return hit[1], hit[0]
    return None, None
