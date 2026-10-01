# Autonomous QA Execution Agent

Docker-first, AI-assisted QA automation platform for recording browser workflows, generating reusable Automation IR, producing runnable test code, and executing scenarios from a central repository.

## Core capabilities

- Workspace, application, and environment management
- Managed Chromium recording with noVNC
- Sensitive-input redaction and secret references
- Canonical Automation IR
- Scenario Repository
- Python + Playwright + Pytest generation
- Java + Selenium + TestNG generation
- Local execution through the Runner service
- Single and bulk scenario execution
- Combined multi-scenario project export

## Architecture

- **Web:** Next.js / React / TypeScript
- **Control Plane:** Java / Spring Boot / JPA / Flyway
- **Database:** PostgreSQL
- **Recorder:** Python / FastAPI / Chromium / Xvfb / noVNC
- **Code Generator:** Python / FastAPI
- **Runner:** Python / Playwright / Pytest
- **Runtime:** Docker Compose

## Requirements

For the Docker-first workflow, install only:

1. Git
2. Docker Desktop
3. WSL 2 / virtualization required by Docker Desktop
4. Internet access for the first image/dependency download

You do **not** need separate host installations of Java, Maven, Node.js, PostgreSQL, Python, Playwright, or Chromium.

## Fresh clone

```powershell
git clone https://github.com/Kazihamid/Autonomous_QA_Execution_Agent.git
cd Autonomous_QA_Execution_Agent
.\START_PROJECT.bat
```

On first start, the startup script creates `.env.runtime` from `.env.runtime.example` when needed.

For scenarios that require secrets, edit `.env.runtime` locally:

```env
SECRET_PASSWORD=
```

Never commit real credentials.

Then open:

```text
http://localhost:3000
```

## Useful commands

```powershell
docker compose up -d --build
docker compose ps
docker compose logs -f
docker compose down
```

Stopping the project with `docker compose down` preserves PostgreSQL data.

## Ports

- Web UI: `http://localhost:3000`
- Control Plane: `http://localhost:8080`
- Recorder API: `http://localhost:8090/health`
- Managed Browser/noVNC: `http://localhost:6080/vnc.html?autoconnect=1&resize=scale`
- Code Generator: `http://localhost:8100/health`
- Runner: `http://localhost:8110/health`
- PostgreSQL: `localhost:5432`

## Data portability

A fresh clone creates a fresh PostgreSQL volume. Workspaces, applications, environments, recorded scenarios, Automation IR versions, and execution history are database data and are not stored in GitHub.

Use database backup/restore for moving existing runtime data between machines.

## Target-environment access

The platform itself can run locally with Docker. Executing tests against protected QA environments may additionally require VPN or organization-network access from the machine running the Runner.

## Security notes

- `.env.runtime` is ignored by Git.
- Recorder and runner helper ports are bound to localhost where appropriate.
- Sensitive inputs are represented as secret references rather than persisted plaintext values.
- The local noVNC setup is intended for development use and should not be exposed publicly.

## CI

GitHub Actions currently validates the project structure, Control Plane tests, and Web build/type checking. Recorder, Code Generator, Runner, and broader integration checks can be added incrementally.
