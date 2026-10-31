# Goal: monitoring

name: monitoring
description: |
  Converge to a monitoring stack — Prometheus scraping node-exporter + Grafana dashboards on :3000. Verifies metrics HTTP and Grafana login page.

budget:
  max_steps: 50
  max_tokens: 220000
  timeout_min: 15

llm:
  endpoint: ""
  api_key: ""
  model: ""

accept:
  - "checks/prometheus-http.sh"
  - "checks/grafana-http.sh"

constraints:
  allow: [exec, apk, write:/etc, write:/srv, write:/var, service, parted, mkfs, mount, probe, read, check, journal]
  deny: []
