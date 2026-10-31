.PHONY: help install lint test docker docker-run docker-test qemu-rootfs harness clean

IMAGE ?= inferkern:dev
GOAL ?= examples/goals/web-server/goal.yaml

help:
	@echo "inferkern — make targets:"
	@echo "  install       pip install -e .[dev]"
	@echo "  lint          ruff check + format"
	@echo "  test          pytest"
	@echo "  docker        build Docker image ($(IMAGE))"
	@echo "  docker-run    run agent in Docker (GOAL=$(GOAL))"
	@echo "  docker-test   verify checks pass inside Docker"
	@echo "  qemu-rootfs   build Alpine rootfs for QEMU"
	@echo "  harness       run convergence harness (N=3)"
	@echo "  clean         remove build artifacts"

install:
	pip install -e ".[dev]"

lint:
	ruff check .
	ruff format --check .

test:
	pytest -v

docker:
	docker build -f docker/Dockerfile -t $(IMAGE) .

docker-run:
	docker run --rm -p 8080:80 $(IMAGE) --goal /app/$(GOAL)

docker-test:
	docker run --rm $(IMAGE) --once --goal /app/$(GOAL)

qemu-rootfs:
	qemu/build-rootfs.sh

harness:
	python -m harness.run --image $(IMAGE) --runs 3

harness-build:
	python -m harness.run --image $(IMAGE) --runs 3 --build

clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache
	rm -rf qemu/rootfs qemu/*.qcow2
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
