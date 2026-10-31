# Goal: web-server

name: web-server
description: >
  Boot to a running HTTP server on port 80 serving a static page.
  The blank virtual disk (if present) should be partitioned, formatted,
  and used for persistent state at /var/lib/inferkern.

budget:
  max_steps: 60
  max_tokens: 200000
  timeout_min: 30

accept:
  - checks/http-200.sh
  - checks/service-persists.sh

constraints:
  allow: [exec, apk, write:/etc, write:/srv, write:/var, service, parted, mkfs, mount, probe, read, check, journal]
  deny: []

# State persistence
state_dir: /var/lib/inferkern   # on blank disk if available, else rootfs
