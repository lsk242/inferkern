#!/bin/sh
set -eu
if command -v restic >/dev/null 2>&1 && [ -f /etc/restic/backup.conf ]; then echo "restic config"; exit 0; fi
if restic snapshots 2>&1 | grep -q "snapshot"; then echo "restic repo"; exit 0; fi
if [ -d /srv/backup ] || [ -f /etc/cron.d/restic-backup ]; then echo "backup dir/cron"; exit 0; fi
echo "restic not configured"; exit 1
