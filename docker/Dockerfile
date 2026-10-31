FROM alpine:3.20

# Base deps: python, nginx, curl, process tools, openrc for service mgmt
RUN apk add --no-cache \
    python3 py3-pip py3-yaml \
    nginx curl wget ca-certificates \
    openrc busybox-openrc \
    iproute2 procps-ng util-linux \
    bash

# openrc needs a runlevel dir even if we don't use it via openrc
RUN mkdir -p /run/openrc && touch /run/openrc/softlevel

# create dirs the agent expects
RUN mkdir -p /etc/inferkern /var/lib/inferkern /srv/http /goals /state \
 && adduser -D -s /bin/sh -h /home/inferkern inferkern 2>/dev/null || true

# copy python package
COPY pyproject.toml README.md LICENSE* /app/
COPY inferkern /app/inferkern
COPY goals /app/goals

WORKDIR /app

# install python deps (httpx, pyyaml, rich) — try apk first, fallback pip
RUN apk add --no-cache py3-httpx py3-rich 2>/dev/null || pip3 install --no-cache-dir --break-system-packages httpx rich pyyaml || pip3 install --no-cache-dir httpx rich pyyaml

# ensure local import works even without pip install
ENV PYTHONPATH=/app:$PYTHONPATH
ENV INFERKERN_GOAL=/app/goals/web-server/goal.yaml
ENV INFERKERN_STATE_DIR=/var/lib/inferkern

# make checks executable
RUN chmod +x /app/goals/*/checks/*.sh 2>/dev/null || true \
 && chmod +x /goals/*/checks/*.sh 2>/dev/null || true

# supervisor is the entrypoint; it spawns the agent and handles oneshot vs steady-state
COPY docker/entrypoint.sh /usr/local/bin/inferkern-entrypoint
RUN chmod +x /usr/local/bin/inferkern-entrypoint

# default site (overwritten by agent if needed)
RUN echo '<!doctype html><html><body><h1>inferkern placeholder</h1><p>Agent not yet converged.</p></body></html>' > /srv/http/index.html

EXPOSE 80

ENTRYPOINT ["/usr/local/bin/inferkern-entrypoint"]
CMD []
