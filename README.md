# Autonomous QA Execution Agent Starter v0.2.0

Docker-first runtime for the AI-Powered No-Code / Low-Code Intelligent Test Automation Platform.

## Implemented vertical slices

### Vertical Slice 1

`Identity â†’ Workspace â†’ Application â†’ Environment â†’ Target Validation`

### Vertical Slice 2

`Environment â†’ Recorder Session â†’ Managed Chromium â†’ Capture â†’ Normalize â†’ Automation IR â†’ Scenario Repository`

## Main components

- **Web:** Next.js / React / TypeScript
- **Control Plane:** Java 25 / Spring Boot 4 / JPA / Flyway
- **Database:** PostgreSQL 18
- **Recorder Worker:** Python / FastAPI / Playwright
- **Managed browser display:** Xvfb + x11vnc + noVNC
- **Canonical source of truth:** framework-neutral Automation IR

## Recorder lifecycle

The MVP implements the key lifecycle states:

`PROVISIONING â†’ STARTING_BROWSER â†’ READY â†’ RECORDING â†” PAUSED â†’ FINISHING â†’ NORMALIZING â†’ BUILDING_IR â†’ VALIDATING â†’ COMPLETED`

It also supports `FAILED` and `CANCELLED`.

## Scenario repository hierarchy

The UI represents:

`Application â†’ Module â†’ Feature â†’ Scenario â†’ Version â†’ Automation IR`

Version 1 is created from a completed recorder session.

## Security controls retained from the design

- server-side Workspace authorization;
- SSRF/target URL policy validation;
- target revalidation before recording;
- sensitive input redaction at browser instrumentation time;
- secret-reference generation instead of plaintext password persistence;
- local Recorder/noVNC ports bound to loopback only;
- audit records for high-value Recorder operations.

## Quick start

Use `START_PROJECT.bat`. See `START_HERE.md` for the exact flow.

## Validation completed when packaging

- Python source compilation: PASS
- Recorder normalizer / locator / IR unit tests: **5/5 PASS**
- Java source syntax parse: PASS
- TypeScript/TSX syntax parse: PASS
- Docker Compose YAML parse: PASS
- OpenAPI YAML parse: PASS
- Vertical Slice 2 structural/security validation: PASS

The artifact-generation environment did not run Docker Engine, so the complete containerized stack must still be executed on the developer workstation. Docker build/runtime issues, if any, should be diagnosed from the workstation logs rather than assumed successful.

## Next phase

**Vertical Slice 3 â€” Code Generation**

The same saved Automation IR will generate equivalent runnable projects for:

- Python + Playwright + Pytest
- Java + Selenium + TestNG

