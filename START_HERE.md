# START HERE — Autonomous QA Execution Agent

## Quick start

1. Start Docker Desktop and confirm the engine is running.
2. Open the cloned project folder.
3. Run `START_PROJECT.bat`.
4. Wait for Recorder, Code Generator, Runner, Control Plane, and Web UI health checks.
5. Open `http://localhost:3000`.

The startup script creates `.env.runtime` from `.env.runtime.example` if it does not exist.

For scenarios that require a runtime secret, configure:

```env
SECRET_PASSWORD=
```

Do not commit `.env.runtime`.

## Recorder flow

`Environment → Record Test → Managed Chromium → Start → Perform workflow → Finish → Review Automation IR → Save Scenario → Scenario Repository`

## Scenario execution flow

`Scenario Repository → Run / Run Selected → Code Generation → Runner → Result`

## Requirements

Docker-first setup requires only:

- Docker Desktop
- WSL 2 / virtualization required by Docker Desktop
- Git
- Internet access for first build

No separate Java, Maven, Node.js, PostgreSQL, Python, Playwright, or Chromium installation is required on the host.

## Important note about data

A fresh clone starts with a fresh PostgreSQL volume. Existing workspaces, environments, scenarios, and execution history are not stored in GitHub. Use database backup/restore when moving runtime data to another machine.

## Useful commands

```powershell
docker compose up -d --build
docker compose ps
docker compose logs -f
docker compose down
```

Use `RESET_PROJECT.bat` only when you intentionally want to remove local PostgreSQL data.
