.PHONY: docker-build docker-run vm-build vm-run harness test lint clean

IMAGE ?= inferkern:dev
GOAL ?= web-server
DOCKER_GOAL_DIR ?= goals/$(GOAL)
VM_DIR ?= vm

# --- python ---
PY ?= python3

test:
	$(PY) -m pytest -q

lint:
	ruff check inferkern/ tests/ harness/ 2>/dev/null || echo "ruff not installed (pip install -e .[dev])"

# --- docker demo (Proposal A) ---
docker-build:
	docker build -f docker/Dockerfile -t $(IMAGE) .

docker-run:
	docker run --rm -it \
	  -e INFERKERN_LLM_ENDPOINT \
	  -e INFERKERN_LLM_API_KEY \
	  -e INFERKERN_LLM_MODEL \
	  -e INFERKERN_GOAL=/goals/$(GOAL)/goal.yaml \
	  -e INFERKERN_MAX_STEPS \
	  -e INFERKERN_DRY_RUN \
	  -v $(PWD)/goals:/goals:ro \
	  -p 8080:80 \
	  $(IMAGE)

docker-run-shell:
	docker run --rm -it --entrypoint /bin/sh \
	  -v $(PWD)/goals:/goals:ro \
	  $(IMAGE)

# --- VM demo (Proposal B) ---
vm-build:
	bash vm/build-rootfs.sh

vm-run:
	bash vm/run-qemu.sh --goal $(GOAL)

# --- harness (Proposal D v0) ---
harness:
	$(PY) -m harness.run --goal $(GOAL) --runs 2

clean:
	rm -rf vm/rootfs vm/disk.img vm/*.log state/ .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
