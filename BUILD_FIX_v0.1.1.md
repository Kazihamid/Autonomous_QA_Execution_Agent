# Build Fix v0.1.1

Changes:
- Migrated AuditService from Jackson 2 (`com.fasterxml.jackson`) to Spring Boot 4 / Jackson 3 (`tools.jackson`).
- Made Maven Docker build output verbose to expose compiler errors if another issue occurs.

Recommended:
`docker compose build --no-cache control-plane`
then
`docker compose up --build`
