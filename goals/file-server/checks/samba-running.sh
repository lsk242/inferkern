#!/bin/sh
set -eu
if pgrep -x smbd >/dev/null 2>&1 || pgrep smbd >/dev/null 2>&1; then echo "smbd running"; exit 0; fi
if ss -tlnp 2>&1 | grep -q ":445"; then echo "samba :445"; exit 0; fi
if [ -f /etc/samba/smb.conf ] && grep -q "\[share" /etc/samba/smb.conf 2>/dev/null; then echo "samba config"; exit 0; fi
echo "samba not ready"; exit 1
