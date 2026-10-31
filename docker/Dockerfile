FROM alpine:3.20

RUN apk add --no-cache \
    python3 py3-pip \
    curl wget ca-certificates \
    nginx \
    busybox-extras

WORKDIR /app

COPY pyproject.toml ./
COPY agent/ ./agent/
RUN pip install --no-cache-dir --break-system-packages -e . \
    || pip install --no-cache-dir --break-system-packages httpx pyyaml rich

COPY checks/ ./checks/
COPY examples/ ./examples/
COPY qemu/ ./qemu/

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN mkdir -p /etc/inferkern /var/lib/inferkern

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--goal", "/etc/inferkern/goal.yaml"]
