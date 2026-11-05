#!/bin/sh
set -eu
if ss -tlnp 2>&1 | grep -q ":1883"; then echo "MQTT :1883"; exit 0; fi
if pgrep -x mosquitto >/dev/null 2>&1; then echo "mosquitto running"; exit 0; fi
if [ -f /etc/mosquitto/mosquitto.conf ]; then echo "mosquitto config"; exit 0; fi
echo "mqtt not ready"; exit 1
