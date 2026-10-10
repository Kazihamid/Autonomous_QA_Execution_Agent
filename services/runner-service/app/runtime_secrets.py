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


_HOST_ONLY = {"PATH", "HOME", "LANG", "LC_ALL", "TZ", "TMPDIR", "HOSTNAME", "PWD", "OLDPWD", "SHLVL", "USER", "USERNAME", "LOGNAME", "TERM",
              "PLAYWRIGHT_BROWSERS_PATH", "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD", "PYTHONUNBUFFERED", "PYTHON_VERSION", "_"}


def export_env(example_text: str, source: dict[str, str] | None = None) -> dict:
    """Builds the .env of an exported project from the project's .env.example and the platform's own .env.

    Only the names that appear in the example are looked up (so nothing else in the platform .env can leave), each one the
    way a run on the platform finds it: password lines by environment and user, test-data lines by NAME__SCENARIO then NAME,
    and the optional settings the example lists (# optional: NAME) when they are set. Values are returned, never logged.
    """
    raw_source = source if source is not None else load_source()
    src = {k: v for k, v in raw_source.items() if k not in _HOST_ONLY and not k.startswith("PYTHON")}
    active: list[tuple[str, str]] = []
    optional: list[str] = []
    for raw in (example_text or "").splitlines():
        line = raw.strip()
        if line.lower().startswith("# optional:"):
            name = line.split(":", 1)[1].strip()
            if name and name.replace("_", "").isalnum():
                optional.append(name)
            continue
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        active.append((key.strip(), value))
    defaults = dict(active)
    base_url = defaults.get("BASE_URL", "")
    parameters: dict[str, str] = {}
    for key, value in active:
        if "__" in key and value:
            parameters.setdefault(key.split("__", 1)[0], value)
    out: list[str] = []
    from_platform: list[str] = []
    missing: list[str] = []
    written: set[str] = set()
    for key, value in active:
        final = value
        if key == "BASE_URL":
            pass
        elif value.strip() == "":
            found, _ = resolve(key, base_url, parameters, src)
            if found:
                final = found
                from_platform.append(key)
            else:
                missing.append(key)
        elif "__" in key:
            name = key.split("__", 1)[0]
            found, _ = resolve(key, base_url, parameters, src)
            if not found:
                found, _ = resolve(name, base_url, parameters, src)
            if found:
                final = found
                if found != value:
                    from_platform.append(key)
        out.append(f"{key}={final}")
        written.add(key.upper())
        written.add(key.split("__", 1)[0].upper())
    for name in dict.fromkeys(optional):
        if "__" in name and name.split("__", 1)[0].upper() in written:
            continue
        if name.upper() in written:
            continue
        found, _ = resolve(name, base_url, parameters, src)
        if found:
            out.append(f"{name}={found}")
            from_platform.append(name)
            written.add(name.upper())
    header = ["# Settings for running these tests on your computer, taken from the platform's own .env.",
              "# This file holds real passwords: keep it private and do not commit it or send it to anyone.",
              "# BASE_URL is the website the tests run on. Change it to use another environment.",
              ""]
    for key in missing:
        header.append(f"# No value for {key} was found in the platform .env: type it after the = sign below.")
    return {"env": "\n".join(header + out) + "\n", "fromPlatform": sorted(set(from_platform)), "missing": missing}
