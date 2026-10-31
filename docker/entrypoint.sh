#!/bin/sh
set -e

GOAL_DEFAULT="/etc/inferkern/goal.yaml"
GOAL_FALLBACK="/app/examples/goals/web-server/goal.yaml"

if [ "$1" = "--goal" ] && [ ! -f "$2" ] 2>/dev/null; then
  echo "[entrypoint] goal file $2 not found, using fallback $GOAL_FALLBACK" >&2
  set -- --goal "$GOAL_FALLBACK"
elif [ $# -eq 0 ]; then
  if [ -f "$GOAL_DEFAULT" ]; then
    set -- --goal "$GOAL_DEFAULT"
  else
    echo "[entrypoint] no goal at $GOAL_DEFAULT, using fallback $GOAL_FALLBACK" >&2
    set -- --goal "$GOAL_FALLBACK"
  fi
elif [ "$1" != "--goal" ] && [ "$1" != "--dry-run" ] && [ "$1" != "--once" ]; then
  if [ -f "$1" ]; then
    set -- --goal "$@"
  fi
fi

echo "[entrypoint] starting agent: inferkern-agent $*" >&2
exec python3 -m agent.main "$@"
