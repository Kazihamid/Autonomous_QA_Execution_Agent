# START HERE â€” Autonomous QA Execution Agent v0.2.0

This package contains **Vertical Slice 1 + Vertical Slice 2**.

## What now works

```text
Development Sign-In
  â†’ Workspace
  â†’ Application
  â†’ Environment
  â†’ Record Test
  â†’ Managed Chromium (noVNC)
  â†’ Start / Pause / Resume / Finish
  â†’ Raw Event Normalization
  â†’ Canonical Automation IR
  â†’ Save Scenario
  â†’ Scenario Repository
```

## Requirements

For the Docker-first route install only:

1. Docker Desktop for Windows
2. WSL 2 / virtualization (already required by Docker Desktop)
3. Internet access on the first build so Docker can download images and dependencies

You do **not** need a separate Java, Maven, Node.js, PostgreSQL, Python or Chromium installation.

## First start / upgrade start

1. Start Docker Desktop and confirm **Engine running**.
2. Open the project folder.
3. Double-click `START_PROJECT.bat`.
4. Wait until the script reports:
   - Recorder Worker: UP
   - Control Plane: UP
   - Web UI: ready
5. Open `http://localhost:3000/login`.

The first v0.2.0 build is larger than v0.1.1 because the Recorder Worker installs Chromium + X11/noVNC components.

## Recorder flow

1. Sign in with the local development identity.
2. Open Workspace â†’ Application.
3. On an ACTIVE environment, click **Record Test**.
4. Enter Scenario name, Module and Feature.
5. Click **Launch managed browser**.
6. When status is `READY`, click **Start Recording**.
7. Perform the test manually inside the embedded managed Chromium window.
8. Optional technical controls:
   - Add assertion using a CSS selector
   - Add checkpoint
   - Pause / Resume
9. Click **Finish**.
10. Review the generated Automation IR.
11. Click **Save Scenario**.
12. Open **Scenario repository**.

## Security behavior in this slice

- Password/sensitive input values are not stored as plaintext recorder values.
- Sensitive inputs are converted into secret references in Automation IR.
- Environment target policy is re-applied before provisioning a Recorder session.
- The noVNC and Recorder API ports bind to `127.0.0.1` for local development.
- This local noVNC setup has no VNC password and must not be exposed as a production deployment.

## Ports

- Web UI: `http://localhost:3000`
- Control Plane: `http://localhost:8080`
- Recorder Worker API: `http://localhost:8090/health`
- Managed Browser/noVNC: `http://localhost:6080/vnc.html?autoconnect=1&resize=scale`
- PostgreSQL: `localhost:5432`

## Useful commands

- `START_PROJECT.bat` â€” build/start the full stack
- `STOP_PROJECT.bat` â€” stop containers, preserve database data
- `PROJECT_STATUS.bat` â€” show container + API health
- `VIEW_LOGS.bat` â€” follow logs
- `RESET_PROJECT.bat` â€” delete local database volume (destructive)

## Validation scripts

```text
python scripts/check_slice1.py
python scripts/check_slice2.py
```

## Known MVP boundaries

Vertical Slice 2 intentionally supports one active managed recording session per local Recorder Worker and prioritizes Chromium. Production-grade worker isolation, session authentication for the browser channel, reconnect/expiry policy and Kubernetes worker provisioning remain later hardening work.

The next product phase is **Vertical Slice 3 â€” Automation IR â†’ Code Generator** for Python + Playwright + Pytest and Java + Selenium + TestNG.

