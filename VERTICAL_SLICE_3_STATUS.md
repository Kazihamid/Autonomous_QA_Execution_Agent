# Vertical Slice 3 — Framework-Neutral Code Generator

Status: **IMPLEMENTED — runtime validation required on the target Docker Desktop machine**

## Implemented
- Code Generator service with plugin-style target dispatch.
- Canonical Automation IR 1.0.0 input only; generator never treats generated code as source of truth.
- Python + Playwright + Pytest generation.
- Java + Selenium + TestNG + Maven generation.
- Deterministic source bundle hashing.
- IR Step ID traceability markers and machine-readable source maps.
- Secret references remain environment-variable references; secret scan runs before persistence.
- Environment-relative navigation; captured QA hostnames are not emitted into generated test source.
- Generated Page Object + business test separation.
- Immutable Automation Implementation versions persisted in PostgreSQL.
- Code viewer, validation metadata, source map view and ZIP download.
- Audit events for generation request/completion.

## Deliberately deferred
- Java compilation/Maven dependency validation runs in the future isolated validation/Runner environment, not inside Control Plane or Code Generator.
- JUnit target plugin.
- Customized-code editor and three-way regeneration merge.
- Asynchronous generation jobs for large suites.
- Test execution (Vertical Slice 4).
