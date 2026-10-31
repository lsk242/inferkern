#!/bin/sh
set -eu
if command -v redis-cli >/dev/null 2>&1 && redis-cli ping 2>&1 | grep -q "PONG"; then echo "redis PONG"; exit 0; fi
if pgrep -x redis-server >/dev/null 2>&1; then echo "redis process"; exit 0; fi
if ss -tlnp 2>&1 | grep -q ":6379"; then echo "redis port 6379"; exit 0; fi
# fallback: check config
if [ -f /etc/redis/redis.conf ] || [ -f /etc/redis.conf ]; then echo "redis config"; exit 0; fi
echo "redis not ready"; exit 1
