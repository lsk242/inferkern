#!/bin/sh
# inferkern init — PID 1 shell wrapper for QEMU boot.
# This is the `init=` target in the kernel cmdline; it execs the Python supervisor.
# Kept as a shell script so we can add early setup that Python can't do yet.
set -e

echo "[inferkern:init] starting (cmdline: $(cat /proc/cmdline 2>/dev/null || echo 'N/A'))" >&2

# Export goal from kernel cmdline if present: inferkern.goal=/dev/vdb1
for arg in $(cat /proc/cmdline 2>/dev/null); do
  case "$arg" in
    inferkern.goal=*) export INFERKERN_GOAL_SRC="${arg#inferkern.goal=}" ;;
    inferkern.state=*) export INFERKERN_STATE_SRC="${arg#inferkern.state=}" ;;
  esac
done

# Pass through to Python supervisor
exec python3 -m qemu.supervisor \
  ${INFERKERN_GOAL_SRC:+--goal-src="$INFERKERN_GOAL_SRC"} \
  ${INFERKERN_STATE_SRC:+--state-src="$INFERKERN_STATE_SRC"} \
  "$@"
