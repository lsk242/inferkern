# Goal: docker-manager

name: docker-manager
description: |
  Converge to a Docker host with Compose and Portainer — ready to run containers. Installs Docker Engine, enables service, deploys Portainer on :9000, verifies docker ps.

budget:
  max_steps: 50
  max_tokens: 220000
  timeout_min: 15

llm:
  endpoint: ""
  api_key: ""
  model: ""

accept:
  - "checks/docker-running.sh"
  - "checks/portainer-http.sh"
  - "checks/compose-working.sh"

constraints:
  allow: [exec, apk, write:/etc, write:/srv, write:/var, service, parted, mkfs, mount, probe, read, check, journal]
  deny: []
