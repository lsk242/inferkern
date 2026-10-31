# Use cases: what should the agent converge *to*?

The agent needs a primary goal to guide it — "manage the system" is too vague
to test. Each goal ships as `goals/<name>/goal.yaml` + `checks/*.sh` + expected
end state for the harness. Run any via `GOAL=<name> make docker-run` — see `make help`.

## Implemented recipes (16 goals, ready to run)

All are heuristic-friendly (converge without an LLM) and Docker/VM testable.

| # | Goal | What it does | Checks |
|---|------|--------------|--------|
| 1 | `web-server` | nginx on :80 serving `/srv/http/index.html` | http-200, nginx-running |
| 2 | `smoke-test` | Python http.server on :8765 + file | http-200, file-exists |
| 3 | `demo-static` | Minimal static site (nginx or Python fallback) | http-200 |
| 4 | `container-host` | Docker/Podman host with volumes + restart policies | docker-running, http-200 |
| 5 | `docker-manager` | Docker Engine + Compose + Portainer on :9000 | docker-running, portainer-http, compose-working |
| 6 | `network-manager` | DHCP/DNS/VLAN gateway (dnsmasq/NetworkManager) | dns-listening, dhcp-config |
| 7 | `firewall` | nftables/iptables drop-all + allow 22/80/443 + fail2ban | nft-rules, fail2ban-running |
| 8 | `media-server` | Jellyfin on :8096, library at /srv/media | jellyfin-http, media-dir |
| 9 | `vpn-server` | WireGuard 10.8.0.0/24, UDP :51820, IP forward | wireguard-interface, ip-forward |
| 10 | `database` | PostgreSQL 16 + Redis cache | postgres-ready, redis-ping |
| 11 | `monitoring` | Prometheus :9090 + Grafana :3000 | prometheus-http, grafana-http |
| 12 | `reverse-proxy` | Caddy/Traefik with auto-TLS, :80→backends | caddy-running, proxy-config |
| 13 | `home-automation` | Home Assistant :8123 + Mosquitto MQTT :1883 | homeassistant-http, mqtt-broker |
| 14 | `file-server` | Samba :445 + NFS /srv/share with quotas | samba-running, nfs-exports |
| 15 | `dns-server` | Pi-hole/AdGuard Home DNS filter :53 + UI :8000 | dns-filter-http, dns-blocking |
| 16 | `backup-server` | Restic + Borg with cron, local + S3 | restic-repo, borg-repo |

Each has an individual PR `feat/recipe-<name>` → `main` (12 PRs for the advanced set) plus the mega-branch `feat/phase1-docker-vm` with all goals. Try `make test-all` to verify.

## Original sequence (first 3)

### 1. Web server (first goal — recommended)

- Goal: serve a static site / reverse-proxy an app over HTTP(S) on port 80/443.
- Why first: concrete, small tool surface, trivially verifiable (`curl` returns 200), maps directly to Proposal A/B exit criteria.
- Acceptance checks: HTTP 200 on `/`, service survives agent-loop restart, reboot re-converges without human input.

### 2. Container host

- Goal: Docker/Podman running, a declared set of containers up (e.g. nginx + postgres), volumes on the right disk, restart policies set.
- Why second: exercises storage management (volumes, mounts), multi-service orchestration, and the "run applications" half of the vision.
- Note: Docker on musl/Alpine works but has quirks; this goal may force the glibc-fallback decision (see [base options](research/base-options.md)).

### 3. OpenClaw-style assistant node

- Goal: the machine becomes a self-hosted AI assistant box (chat gateway + agent + tools), i.e. "install and configure OpenClaw toward a declared personality/accounts setup".
- Why third: the most ambitious and most on-brand — the machine assembles its own higher-level agent. But it needs 1+2 working first (services, containers, secrets) plus secret injection (chat tokens, API keys), which is its own design problem (see [llm runtime](research/llm-runtime.md)).
- This is the "it could just be another agent like OpenClaw" endgame: inferkern converges bare metal into an OpenClaw node with zero manual setup.

### Later candidates (still parked)

- **Kiosk / appliance**: single-purpose locked-down image (signage, sensor gateway). Pairs well with the Buildroot phase.
- **Rescue/diagnostics**: boot unknown hardware, report what's there, fix what's fixable. Actually a degenerate case of the discovery layer every goal needs.

## Other interesting options (future)

Beyond the 16 implemented, these would showcase the agent's reasoning:

- **K3s / Kubernetes edge node**: single-node cluster with Helm chart deploy.
- **Dev box**: users, SSH keys, toolchains, dotfiles from a repo.
- **CI runner**: GitHub Actions self-hosted runner or Woodpecker.
- **AI inference node**: Ollama + Open WebUI on GPU, model fetch.
- **Game server**: Minecraft/Valheim dedicated server with persistence.
- **Email / mail gateway**: Postfix + Dovecot + Rspamd.
- **IoT gateway**: Zigbee2MQTT + Node-RED.
- **Static site generator**: Hugo/Jekyll build + nginx, git webhook.

Pick any — the pattern is the same: `goal.yaml` describes desired state, `checks/*.sh` are 0/1, agent probes → reasons → acts → verifies until converge.

## Goal format (actual, v1)

```yaml
# goals/<name>/goal.yaml
name: web-server
description: |
  Converge to an nginx web server serving static content on port 80.
llm:
  endpoint: ""  # or $INFERKERN_LLM_ENDPOINT
  api_key: ""
  model: ""
budget:
  max_steps: 40
  max_tokens: 180000
  timeout_min: 12
accept:
  - "checks/http-200.sh"
  - "checks/nginx-running.sh"
constraints:
  allow: [probe, exec, read_file, write_file, pkg_install, service_start, run_checks]
  deny: []
```

Checks are plain shell scripts returning 0/1 — runnable by the agent during convergence and by the harness afterward. Same scripts, both places.
