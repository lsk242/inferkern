#!/bin/sh
set -eu
if [ -d /srv/media ] && [ "$(ls -A /srv/media 2>/dev/null)" != "" ] || [ -d /srv/media ]; then echo "media dir exists"; exit 0; fi
echo "media dir missing"; exit 1
