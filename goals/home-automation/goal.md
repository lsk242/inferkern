# Goal: home-automation

name: home-automation
description: |
  Converge to Home Assistant — smart home hub on :8123 with Mosquitto MQTT. Verifies HA HTTP and MQTT broker.

budget:
  max_steps: 50
  max_tokens: 220000
  timeout_min: 15

llm:
  endpoint: ""
  api_key: ""
  model: ""

accept:
  - "checks/homeassistant-http.sh"
  - "checks/mqtt-broker.sh"

constraints:
  allow: [exec, apk, write:/etc, write:/srv, write:/var, service, parted, mkfs, mount, probe, read, check, journal]
  deny: []
