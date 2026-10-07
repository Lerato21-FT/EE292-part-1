SHELL := /bin/sh
-include .env
export
HOST_UID := $(shell id -u)
HOST_GID := $(shell id -g)
export HOST_UID HOST_GID
COMPOSE := docker compose -f docker/compose.yaml $(if $(wildcard .env),--env-file .env,)
UV_IMAGE := ghcr.io/astral-sh/uv:0.9.15-python3.14-bookworm-slim
NODE_IMAGE := node:24.8.0-alpine3.22

.PHONY: help lock build up down verify clean test lint fmt smoke logs shell

help:
	@printf '%s\n' 'Everyday:' '  build   Build locked dependencies and the app image' '  up      Start the app at http://127.0.0.1:8765' '  down    Stop the app' '  verify  Run lint, tests, and API smoke checks' '  clean   Remove this project''s containers and generated files' '' 'Developing:' '  test    Run pytest in the container' '  lint    Run Ruff checks in the container' '  fmt     Format Python in the container' '  smoke   Check a real analysis API response' '  logs    Follow app logs' '  shell   Open a shell in the app container' '' 'Dependencies:' '  lock    Update Python and frontend dependency locks'

lock:
	docker run --rm -v "$(CURDIR)/docker:/work" -w /work $(UV_IMAGE) uv lock
	docker run --rm -v "$(CURDIR)/docker:/work" -w /work $(NODE_IMAGE) npm install --package-lock-only --ignore-scripts

build:
	@test -f docker/uv.lock -a -f docker/package-lock.json || { echo 'Dependency locks are missing; run make lock.'; exit 1; }
	$(COMPOSE) build

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

verify: lint test smoke

test: build
	$(COMPOSE) run --rm app pytest -c docker/pyproject.toml -q

lint: build
	$(COMPOSE) run --rm app ruff check --config docker/pyproject.toml src tests

fmt: build
	$(COMPOSE) run --rm -v "$(CURDIR)/src:/work/src" -v "$(CURDIR)/tests:/work/tests" app ruff format --config docker/pyproject.toml src tests

smoke:
	@set -eu; \
	trap '$(COMPOSE) down >/dev/null' EXIT; \
	$(COMPOSE) up -d --build; \
	for attempt in 1 2 3 4 5 6 7 8 9 10; do \
		if curl --fail --silent http://127.0.0.1:$${FMR_PORT:-8765}/api/analysis | grep -q '"kittel_fit"'; then break; fi; \
		if [ "$$attempt" -eq 10 ]; then echo 'API smoke check did not return a Kittel fit.'; exit 1; fi; \
		sleep 2; \
	done; \
	echo 'API smoke check passed: Kittel fit returned.'

logs:
	$(COMPOSE) logs -f app

shell:
	$(COMPOSE) run --rm app /bin/sh

clean:
	$(COMPOSE) down --rmi local --volumes --remove-orphans
	rm -rf .pytest_cache .ruff_cache
