# Goal: firewall

name: firewall
description: |
  Converge to a hardened firewall — nftables/iptables drop-all-default with allow 22/80/443, plus fail2ban. Verifies rules loaded and fail2ban active.

budget:
  max_steps: 40
  max_tokens: 180000
  timeout_min: 10

llm:
  endpoint: ""
  api_key: ""
  model: ""

accept:
  - "checks/nft-rules.sh"
  - "checks/fail2ban-running.sh"

constraints:
  allow: [exec, apk, write:/etc, write:/srv, write:/var, service, parted, mkfs, mount, probe, read, check, journal]
  deny: []
