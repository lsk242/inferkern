#!/bin/sh
set -eu
if command -v borg >/dev/null 2>&1 && borg list 2>&1 | grep -q "borg"; then echo "borg repo"; exit 0; fi
if [ -d /srv/borg ] || [ -f /etc/borgmatic/config.yaml ]; then echo "borg config"; exit 0; fi
if crontab -l 2>&1 | grep -q "borg\|restic\|backup"; then echo "backup cron"; exit 0; fi
echo "borg not configured"; exit 1
