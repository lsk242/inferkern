# Goal: backup-server

name: backup-server
description: |
  Converge to a backup server — Restic + Borg with cron, local + S3 target, verify schedule. Checks backup tools and cron job.

budget:
  max_steps: 40
  max_tokens: 180000
  timeout_min: 10

llm:
  endpoint: ""
  api_key: ""
  model: ""

accept:
  - "checks/restic-repo.sh"
  - "checks/borg-repo.sh"

constraints:
  allow: [exec, apk, write:/etc, write:/srv, write:/var, service, parted, mkfs, mount, probe, read, check, journal]
  deny: []
