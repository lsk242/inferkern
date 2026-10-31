# Goal: dns-server

name: dns-server
description: |
  Converge to a DNS filter — Pi-hole/AdGuard Home blocking ads on :53 with dashboard on :8000. Verifies DNS + web UI.

budget:
  max_steps: 45
  max_tokens: 200000
  timeout_min: 12

llm:
  endpoint: ""
  api_key: ""
  model: ""

accept:
  - "checks/dns-filter-http.sh"
  - "checks/dns-blocking.sh"

constraints:
  allow: [exec, apk, write:/etc, write:/srv, write:/var, service, parted, mkfs, mount, probe, read, check, journal]
  deny: []
