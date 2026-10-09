AUTONOMOUS QA EXECUTION AGENT v0.2.0 - EASY RUN
========================================

1. Start Docker Desktop and confirm Engine running.
2. Double-click START_PROJECT.bat.
3. Open http://localhost:3000/login.
4. Open Workspace > Application > Environment.
5. Click Record Test to launch the managed Chromium recorder.
6. Finish the recording, review Automation IR, and save the Scenario.

Useful files:
- START_HERE.md
- START_PROJECT.bat
- STOP_PROJECT.bat
- PROJECT_STATUS.bat
- VIEW_LOGS.bat
- RESET_PROJECT.bat
- VERTICAL_SLICE_2_STATUS.md

V0.1.2 RUNTIME NOTE
-------------------
Passwords live in .env (copy .env.example; never commit it). The runner picks the password for the
environment and user being tested, e.g. SECRET_PASSWORD_ERPSTAGING_153872 (one user), SECRET_PASSWORD_ENV27 (all users
on env27) or SECRET_PASSWORD (fallback). The file is read on every run, so a changed password needs no restart.
If a run still uses an old value, run: docker compose up -d --force-recreate runner

Existing scenarios recorded before the v0.1.2 locator update may need to be re-recorded.

