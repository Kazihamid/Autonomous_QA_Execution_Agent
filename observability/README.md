# Observability baseline

Production implementation will use OpenTelemetry instrumentation with metrics, logs and traces routed to the approved Prometheus/Grafana/Loki/Tempo or equivalent enterprise stack. Correlation IDs must connect API → workflow → execution → evidence.
