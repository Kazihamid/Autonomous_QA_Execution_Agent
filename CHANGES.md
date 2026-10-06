# Changes in this cleanup pass

**Repo hygiene**
- Removed 8 `RecorderWorkerClient.java.bak-*`, 3 `pom.xml.bak*`, 10 applied `FIX_*.ps1` patch scripts (all in git history), `control-plane-build.log`, `__pycache__`/`.pytest_cache`.
- Removed `.env.runtime` (contained a real-looking password; **rotate it**). Use `.env.runtime.example`.
- `.gitignore` now covers `*.bak*`, `*.log`, `*.pyc`, `.env.*` (except examples).
- README updated (version, status, security notes; mojibake/BOM removed). BOM removed from two Python files.

**Security**
- Compose: Postgres, control-plane and web ports bound to `127.0.0.1`; `POSTGRES_PASSWORD` overridable; `.env.runtime` optional.
- New `DevProfileGuard`: `dev` profile (header-based auth) refuses to start unless `PLATFORM_ENV=local` (+ unit test). Compose sets `PLATFORM_ENV=local`.
- Runner: tests run with a minimal environment plus only the secrets declared in the generated project's `.env.example` (previously inherited the whole container env). Added 4 runner tests.

**CI**
- Restored `.github/workflows/ci.yml` and extended it: structural checks (slices 1-3), pytest for the 3 Python services, Maven tests, web typecheck/build.
- Fixed structural check scripts that already failed (test-file false positive for "secret literal").

**Not done / still recommended**: real runner sandboxing (separate container, no network egress), service-to-service auth, async run jobs, generator heuristics refactor, `infra/docker/docker-compose.yml` duplicate (still differs from root file). Java and Docker changes could not be compiled/run here; run `mvn test` and `docker compose up --build`.

# Pass 2: run failure, duplicates, order-based runs

- **Run failure (`TimeoutError … locator("#overlay")`)**: recorded clicks on transient overlays/backdrops (`#overlay`, `.modal-backdrop`, loaders) are now skipped in generated Playwright and Selenium code (`_is_transient_overlay` + tests). Re-run the scenario from the list; it regenerates code on every run. Real buttons with a `loading` class are not affected.
- **Duplicates**: saving a scenario is now idempotent per recording session, and a new recording with the same module/feature/name (case-insensitive) becomes a new *version* of the existing scenario instead of a second row. The list shows a **Duplicate** badge for existing duplicates (delete the extra rows manually).
- **Order-based execution**: new `execution_order` column (migration `V005`), `PUT …/scenarios/order`, ▲▼ ordering in the Scenario Repository, "Run selected (in order)", **Stop on first failure** option (remaining scenarios reported as `SKIPPED`), and a "Last run order" panel. The server always runs selected scenarios in the saved order, regardless of click order.
- Not verified here: Java compile and Flyway V005 (Maven Central unreachable from this workspace) — run `mvn test` / `docker compose up --build`. Python tests and `tsc --noEmit` pass.
- Known limit: each scenario still runs in its own browser session (each replays its own login). Sharing one logged-in session across ordered scenarios is a separate feature.
