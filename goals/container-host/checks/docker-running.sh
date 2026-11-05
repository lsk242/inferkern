#!/bin/sh
set -eu
if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    echo "docker running"
    exit 0
  fi
  echo "docker installed but not running"
  exit 1
fi
if command -v podman >/dev/null 2>&1; then
  if podman info >/dev/null 2>&1; then
    echo "podman running"
    exit 0
  fi
fi
echo "no container runtime running"
exit 1
