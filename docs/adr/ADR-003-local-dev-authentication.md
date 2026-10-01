# ADR-003: Local Development Authentication Profile

## Decision

Production authentication remains OAuth2/OIDC JWT resource-server based. Local development uses an explicit Spring `dev` profile that creates an authenticated principal from `X-Dev-User-*` headers.

## Rationale

Developers must be able to exercise Workspace/Application/Environment flows without requiring the enterprise IdP on every laptop. The development mechanism must not become a production fallback.

## Guardrails

- `DevSecurityConfig` is active only under profile `dev`.
- non-dev profiles require JWT authentication.
- CI includes a dedicated dev-profile integration path only for tests.
- production deployment configuration must never activate `dev`.
