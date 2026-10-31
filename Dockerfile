FROM alpine:3.21

RUN apk add --no-cache python3 py3-pip nginx curl tini procps iproute2 busybox-extras

COPY agent/ /app/agent/
COPY goals/ /etc/inferkern/goals/
COPY supervisor/ /app/supervisor/

# Default goal symlink
RUN ln -sf /etc/inferkern/goals/web-server/goal.md /etc/inferkern/goal.md \
    && mkdir -p /var/lib/inferkern /srv/http /run/nginx \
    && pip install --no-cache-dir --break-system-packages -r /app/agent/requirements.txt 2>&1 | tail -5 || true

# Entrypoint: agent loop as PID 1 via tini (reaping + signal fwd)
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENV PYTHONPATH=/app
ENV INFERKERN_GOAL=/etc/inferkern/goal.md
ENV INFERKERN_STATE_DIR=/var/lib/inferkern

EXPOSE 80

ENTRYPOINT ["/sbin/tini", "--", "/entrypoint.sh"]
