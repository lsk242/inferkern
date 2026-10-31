# Goal: media-server

name: media-server
description: |
  Converge to a media server — Jellyfin with hardware transcode, serving on :8096. Installs Jellyfin, configures library at /srv/media, verifies HTTP 200.

budget:
  max_steps: 50
  max_tokens: 220000
  timeout_min: 15

llm:
  endpoint: ""
  api_key: ""
  model: ""

accept:
  - "checks/jellyfin-http.sh"
  - "checks/media-dir.sh"

constraints:
  allow: [exec, apk, write:/etc, write:/srv, write:/var, service, parted, mkfs, mount, probe, read, check, journal]
  deny: []
