# Goal: network-manager

name: network-manager
description: |
  Converge to a network gateway — DHCP, DNS forwarding, and VLAN routing. Configures dnsmasq/NetworkManager, verifies DHCP lease range and DNS on :53.

budget:
  max_steps: 45
  max_tokens: 200000
  timeout_min: 12

llm:
  endpoint: ""
  api_key: ""
  model: ""

accept:
  - "checks/dns-listening.sh"
  - "checks/dhcp-config.sh"

constraints:
  allow: [exec, apk, write:/etc, write:/srv, write:/var, service, parted, mkfs, mount, probe, read, check, journal]
  deny: []
