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
For scenarios that use secrets, populate .env.runtime locally (for example SECRET_PASSWORD=...).
Do not commit or share .env.runtime. After changing it, run:
docker compose up -d --force-recreate runner

Existing scenarios recorded before the v0.1.2 locator update may need to be re-recorded.

