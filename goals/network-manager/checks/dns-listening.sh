#!/bin/sh
set -eu
if ss -tlnp 2>&1 | grep -q ":53 "; then echo "DNS listening :53"; exit 0; fi
if ss -ulnp 2>&1 | grep -q ":53 "; then echo "DNS UDP :53"; exit 0; fi
echo "DNS not listening"; exit 1
