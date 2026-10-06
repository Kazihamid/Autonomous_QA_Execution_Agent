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

# Pass 3: environment picker, live run view, edit & save as new

- **Run on any environment**: the Scenario Repository has a "Run on" selector (environments that allow execution). The chosen environment's base URL is passed to the runner, and generated tests now rewrite the recorded host inside the login URL (`redirect_uri`) to the chosen environment (`_rebase`), so a scenario recorded on env27 can run on erpstaging and vice versa. Run results show which environment was used.
- **Live run view**: runs are now background jobs (`POST .../scenario-actions/run-jobs`, `GET .../run-jobs/{id}`). The UI polls once a second and shows overall progress, a spinner per scenario, "Generating code → Running in browser", "step n of N · action", elapsed time and a live terminal view of the test output. The runner has new async endpoints (`POST /api/v1/runs`, `GET /api/v1/runs/{id}`); generated Python tests print `[IR-STEP] …` progress lines. Run jobs are kept in memory (last 50) and are lost on a Control Plane restart.
- **Edit / save as new**: new Edit page per scenario (and "Edit / save as new" on the scenario detail page). You can change parameter values (e.g. user name) and rename secret references (e.g. `SECRET_PASSWORD` → `SECRET_PASSWORD_ENV27`) and save a NEW scenario (`POST .../scenarios/{id}/clone`); the original is untouched. Passwords are still never stored — the value lives in `.env.runtime`.
- Fixed mojibake (`Â·`) in the top bar.
- Not verified here: Java compile and the new endpoints against a running stack (Maven Central unreachable from this workspace).
