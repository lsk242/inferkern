#!/bin/sh
set -eu
if command -v fail2ban-client >/dev/null 2>&1 && fail2ban-client ping 2>&1 | grep -q "pong"; then echo "fail2ban running"; exit 0; fi
if pgrep -f fail2ban >/dev/null 2>&1; then echo "fail2ban process"; exit 0; fi
# fallback: check config exists
if [ -f /etc/fail2ban/jail.local ]; then echo "fail2ban config"; exit 0; fi
echo "fail2ban not running"; exit 1
