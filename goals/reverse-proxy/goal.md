# Goal: reverse-proxy

name: reverse-proxy
description: |
  Converge to a reverse proxy — Caddy/Traefik with automatic TLS, routing *:80 -> backends. Verifies proxy config and HTTP proxy headers.

budget:
  max_steps: 40
  max_tokens: 180000
  timeout_min: 10

llm:
  endpoint: ""
  api_key: ""
  model: ""

accept:
  - "checks/caddy-running.sh"
  - "checks/proxy-config.sh"

constraints:
  allow: [exec, apk, write:/etc, write:/srv, write:/var, service, parted, mkfs, mount, probe, read, check, journal]
  deny: []
