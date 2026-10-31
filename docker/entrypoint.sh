#!/bin/sh
set -eu

# inferkern Docker entrypoint — runs supervisor in oneshot container mode
# Env: INFERKERN_GOAL (default /app/goals/web-server/goal.yaml), INFERKERN_LLM_*, INFERKERN_STATE_DIR, INFERKERN_ONESHOT

GOAL="${INFERKERN_GOAL:-/app/goals/web-server/goal.yaml}"
STATE_DIR="${INFERKERN_STATE_DIR:-/var/lib/inferkern}"

# if /goals is mounted, prefer goals there (allows live editing)
if [ -d /goals ]; then
  BASENAME="$(basename "$GOAL")"
  GOAL_NAME="$(basename "$(dirname "$GOAL")")"
  if [ -f "/goals/$GOAL_NAME/goal.yaml" ]; then
    GOAL="/goals/$GOAL_NAME/goal.yaml"
  elif [ -f "/goals/$BASENAME" ]; then
    GOAL="/goals/$BASENAME"
  fi
else
  # ensure at least /app/goals present
  mkdir -p /app/goals 2>/dev/null || true
fi

echo "[entrypoint] goal=$GOAL state=$STATE_DIR keep_alive=${INFERKERN_KEEP_ALIVE:-1}"
echo "[entrypoint] llm_endpoint=${INFERKERN_LLM_ENDPOINT:-<none> (heuristic mode)}"

# fix permissions for state
mkdir -p "$STATE_DIR" 2>/dev/null || true

# Default: keep container alive after converge for demo (override with INFERKERN_KEEP_ALIVE=0 to exit)
if [ -z "${INFERKERN_KEEP_ALIVE:-}" ]; then
  export INFERKERN_KEEP_ALIVE=1
fi

# delegate to supervisor (oneshot by default in container)
exec python3 -m inferkern.supervisor.sup "$GOAL" --state-dir "$STATE_DIR" "$@"
