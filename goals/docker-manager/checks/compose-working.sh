#!/bin/sh
set -eu
if docker compose version >/dev/null 2>&1 || docker-compose version >/dev/null 2>&1; then echo "compose available"; exit 0; fi
echo "compose not found"; exit 1
