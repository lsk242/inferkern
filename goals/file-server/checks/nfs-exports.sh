#!/bin/sh
set -eu
if exportfs -v 2>&1 | grep -q "/srv/share"; then echo "nfs export /srv/share"; exit 0; fi
if [ -f /etc/exports ] && grep -q "/srv/share" /etc/exports 2>/dev/null; then echo "nfs exports file"; exit 0; fi
if pgrep -x nfsd >/dev/null 2>&1; then echo "nfsd running"; exit 0; fi
echo "nfs not configured"; exit 1
