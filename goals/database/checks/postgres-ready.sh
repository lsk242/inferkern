#!/bin/sh
set -eu
if command -v pg_isready >/dev/null 2>&1 && pg_isready -h 127.0.0.1 2>&1 | grep -q "accepting"; then echo "postgres ready"; exit 0; fi
if pgrep -x postgres >/dev/null 2>&1; then echo "postgres process"; exit 0; fi
if ss -tlnp 2>&1 | grep -q ":5432"; then echo "postgres port 5432"; exit 0; fi
echo "postgres not ready"; exit 1
