# Goal: database

name: database
description: |
  Converge to a database server — PostgreSQL 16 with Redis cache, ready for apps. Installs postgres, creates app DB/user, verifies pg_isready and redis ping.

budget:
  max_steps: 45
  max_tokens: 200000
  timeout_min: 12

llm:
  endpoint: ""
  api_key: ""
  model: ""

accept:
  - "checks/postgres-ready.sh"
  - "checks/redis-ping.sh"

constraints:
  allow: [exec, apk, write:/etc, write:/srv, write:/var, service, parted, mkfs, mount, probe, read, check, journal]
  deny: []
