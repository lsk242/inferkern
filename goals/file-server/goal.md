# Goal: file-server

name: file-server
description: |
  Converge to a file server — Samba shares + NFS exports on /srv/share, with user quotas. Verifies smbd/nfsd and export config.

budget:
  max_steps: 40
  max_tokens: 180000
  timeout_min: 10

llm:
  endpoint: ""
  api_key: ""
  model: ""

accept:
  - "checks/samba-running.sh"
  - "checks/nfs-exports.sh"

constraints:
  allow: [exec, apk, write:/etc, write:/srv, write:/var, service, parted, mkfs, mount, probe, read, check, journal]
  deny: []
