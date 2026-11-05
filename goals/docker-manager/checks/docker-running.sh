#!/bin/sh
set -eu
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then echo "docker running"; exit 0; fi
if pgrep -x dockerd >/dev/null 2>&1; then echo "dockerd process"; exit 0; fi
echo "docker not running"; exit 1
