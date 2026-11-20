SHELL := /bin/sh
export BUILDX_CONFIG := $(CURDIR)/.cache/buildx
-include .env
export
HOST_UID := $(shell id -u)
HOST_GID := $(shell id -g)
export HOST_UID HOST_GID
COMPOSE := docker compose -f docker/compose.yaml $(if $(wildcard .env),--env-file .env,)
UV_IMAGE := ghcr.io/astral-sh/uv:0.9.15-python3.14-bookworm-slim
NODE_IMAGE := node:24.8.0-alpine3.22
TEST_PATHS ?= tests
FORMAT_PATHS ?= src tests

.PHONY: help lock build up down verify fresh-verify clean test lint fmt smoke browser logs shell review profile

help:
	@printf '%s\n' 'Everyday:' '  build   Build locked dependencies and the app image' '  up      Start the app at http://127.0.0.1:8765' '  down    Stop the app' '  verify  Run lint, tests, API smoke and browser checks' '  clean   Remove project containers and generated files' '' 'Developing:' '  test    Run pytest in the container' '  lint    Run Ruff checks in the container' '  fmt     Format Python in the container' '  smoke   Check a real analysis API response' '  browser Check desktop/mobile plots and PNG export in Chromium' '  profile Time and profile an exclusion analysis on the demo data' '  fresh-verify  Verify the committed revision from a new local clone' '  review  Show Git status and validate patch whitespace' '  logs    Follow app logs' '  shell   Open a shell in the app container' '' 'Dependencies:' '  lock    Update Python and frontend dependency locks'

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

verify: lint test smoke browser

test: build
	$(COMPOSE) run --rm app pytest -c docker/pyproject.toml -q $(TEST_PATHS)

profile: build
	$(COMPOSE) run --rm app python tests/profile_analysis.py

lint: build
	$(COMPOSE) run --rm app ruff check --config docker/pyproject.toml src tests

fmt: build
	$(COMPOSE) run --rm -v "$(CURDIR)/src:/work/src" -v "$(CURDIR)/tests:/work/tests" app ruff format --config docker/pyproject.toml $(FORMAT_PATHS)

browser:
	mkdir -p artifacts
	$(COMPOSE) --profile browser build browser
	$(COMPOSE) --profile browser run --rm browser

review:
	git diff --check
	git status --short --branch
	git diff --stat

fresh-verify:
	@mkdir -p .cache
	@set -eu; \
	checkout=$$(mktemp -d "$(CURDIR)/.cache/fresh-verify.XXXXXX"); \
	git clone --quiet --no-hardlinks . "$$checkout"; \
	$(MAKE) -C "$$checkout" verify

smoke:
	@set -eu; \
	trap '$(COMPOSE) down >/dev/null' EXIT; \
	$(COMPOSE) up -d --build; \
	for attempt in 1 2 3 4 5 6 7 8 9 10; do \
		response=$$(curl --fail --silent http://127.0.0.1:$${FMR_PORT:-8765}/api/analysis || true); \
		if [ -n "$$response" ]; then break; fi; \
		if [ "$$attempt" -eq 10 ]; then echo 'API smoke check: the app did not respond.'; exit 1; fi; \
		sleep 2; \
	done; \
	printf '%s' "$$response" | grep -Eq '"g_factor":[0-9]' || { echo 'API smoke check failed: no numeric g factor.'; exit 1; }; \
	printf '%s' "$$response" | grep -Eq '"damping":[0-9]' || { echo 'API smoke check failed: no numeric damping.'; exit 1; }; \
	printf '%s' "$$response" | grep -q '"fit_error":null' || { echo 'API smoke check failed: fit_error is set.'; exit 1; }; \
	echo 'API smoke check passed: numeric g factor and damping, no fit error.'

logs:
	$(COMPOSE) logs -f app

shell:
	$(COMPOSE) run --rm app /bin/sh

clean:
	$(COMPOSE) --profile browser down --rmi all --volumes --remove-orphans
	rm -rf .pytest_cache .ruff_cache artifacts .cache
