.PHONY: help test lint docker-build docker-run docker-serve docker-shell vm-build vm-run harness harness-docker demo test-all setup clean

IMAGE ?= inferkern:dev
GOAL ?= web-server
PY ?= python3

# Default: show help
help:
	@echo "inferkern — The Linux distro where PID 1 is an LLM agent loop"
	@echo ""
	@echo "Setup:"
	@echo "  make setup              Full first-time setup (host deps hint, Python deps, docker build, VM rootfs)"
	@echo "  make setup-no-vm        Fast setup without VM (skip rootfs/kernel build)"
	@echo ""
	@echo "Test:"
	@echo "  make test               pytest (14 tests: policy/goal/state/tools/e2e smoke)"
	@echo "  make test-all           Full 7-step suite (pytest, smoke local+cURL, docker smoke/web, detached, harness, VM artifacts)"
	@echo "  make test-all-no-docker Same but skip Docker steps"
	@echo "  make lint               ruff check (if installed)"
	@echo ""
	@echo "Demo (heuristic, no LLM needed):"
	@echo "  make demo-smoke         Smoke-test local (Python http.server :8765, 4 steps)"
	@echo "  make demo-smoke-docker  Smoke-test in Docker"
	@echo "  make demo-web-dry       Web-server dry-run (shows plan, no side effects)"
	@echo "  make demo-web           Web-server in Docker (heuristic, nginx :80, exit after converge)"
	@echo "  make demo-web-serve     Web-server detached on :8080 + curl (keep-alive)"
	@echo ""
	@echo "Docker (Proposal A):"
	@echo "  make docker-build       Build inferkern:dev (Alpine 3.20, nginx, Python)"
	@echo "  make docker-run         Run GOAL=$(GOAL) (heuristic, KEEP_ALIVE=0, --rm)"
	@echo "  make docker-serve       Run GOAL=$(GOAL) detached on :8080 (KEEP_ALIVE=1)"
	@echo "  make docker-shell       Shell into image (for debugging)"
	@echo "  GOAL=smoke-test make docker-run   # any goal via override"
	@echo "  INFERKERN_LLM_ENDPOINT=... make docker-run  # with LLM"
	@echo ""
	@echo "VM (Proposal B):"
	@echo "  make vm-build           Build Alpine rootfs.tar + vmlinuz-virt (needs docker)"
	@echo "  make vm-run             Boot GOAL=$(GOAL) in QEMU (serial stdio, 8080->80)"
	@echo "  make vm-demo-smoke      QEMU smoke-test"
	@echo "  make vm-demo-web        QEMU web-server"
	@echo ""
	@echo "Harness (Proposal D):"
	@echo "  make harness            Local 2-run harness for GOAL=$(GOAL)"
	@echo "  make harness-docker     Docker 2-run harness for GOAL=$(GOAL)"
	@echo ""
	@echo "Other:"
	@echo "  make clean              Remove build artifacts (vm rootfs, state, cache)"

# --- setup ---
setup:
	bash scripts/setup.sh

setup-no-vm:
	bash scripts/setup.sh --no-vm

# --- python ---
test:
	$(PY) -m pytest -q

test-all:
	bash scripts/test-all.sh

test-all-no-docker:
	bash scripts/test-all.sh --no-docker

lint:
	ruff check inferkern/ tests/ harness/ 2>/dev/null || echo "ruff not installed (pip install -e .[dev])"

# --- demo shortcuts ---
demo-smoke:
	bash scripts/demo.sh smoke

demo-smoke-docker:
	bash scripts/demo.sh smoke-docker

demo-web-dry:
	bash scripts/demo.sh web

demo-web:
	bash scripts/demo.sh web-docker

demo-web-serve:
	bash scripts/demo.sh web-serve

demo:
	bash scripts/demo.sh all

# --- docker demo (Proposal A) ---
docker-build:
	docker build -f docker/Dockerfile -t $(IMAGE) .

# One-shot converge then exit (for harness/CI, KEEP_ALIVE=0)
docker-run:
	docker run --rm -it \
	  -e INFERKERN_LLM_ENDPOINT \
	  -e INFERKERN_LLM_API_KEY \
	  -e INFERKERN_LLM_MODEL \
	  -e INFERKERN_GOAL=/goals/$(GOAL)/goal.yaml \
	  -e INFERKERN_MAX_STEPS \
	  -e INFERKERN_TIMEOUT_MIN \
	  -e INFERKERN_DRY_RUN \
	  -e INFERKERN_KEEP_ALIVE=0 \
	  -v $(PWD)/goals:/goals:ro \
	  -p 8080:80 \
	  $(IMAGE)

# Detached keep-alive on :8080 (for demo, curl host)
docker-serve:
	docker run -d --name inferkern-web --rm \
	  -e INFERKERN_LLM_ENDPOINT \
	  -e INFERKERN_LLM_API_KEY \
	  -e INFERKERN_LLM_MODEL \
	  -e INFERKERN_GOAL=/goals/$(GOAL)/goal.yaml \
	  -v $(PWD)/goals:/goals:ro \
	  -p 8080:80 \
	  $(IMAGE)
	@echo "Waiting 6s for converge..."
	@sleep 6
	@docker logs inferkern-web 2>&1 | tail -5
	@curl -sf http://127.0.0.1:8080/ 2>&1 | head -c 400; echo
	@docker ps | grep inferkern-web || true
	@echo "Stop: docker rm -f inferkern-web"

docker-serve-smoke:
	docker run -d --name inferkern-smoke --rm \
	  -e INFERKERN_GOAL=/goals/smoke-test/goal.yaml \
	  -v $(PWD)/goals:/goals:ro \
	  -p 8765:8765 \
	  $(IMAGE)
	@echo "Waiting 5s..."
	@sleep 5
	@curl -sf http://127.0.0.1:8765/ 2>&1 | head -c 400; echo
	@docker ps | grep inferkern-smoke || true

docker-shell:
	docker run --rm -it --entrypoint /bin/sh \
	  -v $(PWD)/goals:/goals:ro \
	  $(IMAGE)

docker-stop:
	docker rm -f inferkern-web inferkern-web-test inferkern-smoke 2>&1 | true

# --- VM demo (Proposal B) ---
vm-build:
	bash vm/build-rootfs.sh

vm-run:
	bash vm/run-qemu.sh --goal $(GOAL)

vm-demo-smoke:
	bash scripts/vm-demo.sh smoke

vm-demo-web:
	bash scripts/vm-demo.sh web

# --- harness (Proposal D v0) ---
harness:
	$(PY) -m harness.run --goal $(GOAL) --runs 2

harness-docker:
	$(PY) -m harness.run --goal $(GOAL) --runs 2 --docker

# --- clean ---
clean:
	rm -rf vm/rootfs vm/disk.img vm/*.log state/ state-*/ .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	rm -rf /tmp/state-test-* /tmp/state-smoke* /tmp/inferkern-smoke 2>/dev/null; true
