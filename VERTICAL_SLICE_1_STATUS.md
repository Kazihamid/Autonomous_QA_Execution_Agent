# MVP Vertical Slice 1 Status

## Implemented

- OIDC/JWT resource-server production security configuration
- local-only dev identity profile
- user provisioning/synchronization on authenticated request
- workspace create/list/get
- workspace membership and role assignment for existing users
- server-side workspace authorization
- application create/list/get/update/archive-state support
- environment create/list/update
- target URL security-policy validation
- audit persistence for state-changing operations
- PostgreSQL/Flyway schema
- OpenAPI baseline
- Next.js UI flow
- CI definitions

## Local validation completed in this package

- required source tree validation
- migration/table presence validation
- OpenAPI YAML parse and required path validation
- obvious source-secret hygiene scan

## Requires target environment / CI validation

- `mvn test` with Java 25
- Spring Boot + PostgreSQL integration startup
- Next.js `npm install`, typecheck and production build
- browser UI smoke test against the running Control Plane
- real enterprise OIDC provider integration

## Security note

Configuration-time target validation is only one layer. Recorder and Runner must independently re-resolve DNS, re-check destination IPs after redirects, and rely on network-level egress controls before making target connections.
