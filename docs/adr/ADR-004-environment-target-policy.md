# ADR-004: Environment Target Policy and SSRF Boundary

## Decision

Environment configuration performs an early URL-policy validation, but configuration-time validation is not considered sufficient authorization for network access.

## Controls

- allow HTTP/HTTPS only;
- reject embedded URL credentials;
- block localhost/loopback, link-local, multicast and cloud-metadata targets;
- private targets are disabled by default;
- optional host allowlist is supported;
- DNS failure produces `UNVERIFIED` rather than silently assuming safety;
- Recorder/Runner must re-resolve and revalidate DNS/IP and redirects at connection time;
- execution plane egress policy remains the final network enforcement boundary.
