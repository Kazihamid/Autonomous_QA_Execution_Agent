# Run on Windows — Docker-First v0.2.0

## Prerequisite

Start **Docker Desktop for Windows** and wait for **Engine running**.

No separate Java, Maven, Node.js, PostgreSQL, Python or Chromium installation is required for the recommended Docker-first path.

## Start

Double-click `START_PROJECT.bat`.

The script builds/starts:

- PostgreSQL 18
- Recorder Worker (FastAPI + Playwright + managed Chromium + noVNC)
- Spring Boot Control Plane
- Next.js Web UI

Then open `http://localhost:3000/login`.

## Recorder

Open Workspace → Application → an ACTIVE Environment → **Record Test**.

The managed browser is served locally through noVNC on port `6080`.

## Stop / Status / Logs

- `STOP_PROJECT.bat` — stop containers, preserve database data
- `PROJECT_STATUS.bat` — status + backend/recorder health
- `VIEW_LOGS.bat` — follow logs
- `RESET_PROJECT.bat` — destructive clean reset; deletes database volume

See `START_HERE.md` for the full beginner flow.
