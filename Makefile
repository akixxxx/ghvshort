# ============================================================
# Makefile for ghvshort
#
# Developer convenience only.
# Debian packaging is handled by debian/rules (dh/pybuild).
# This Makefile intentionally avoids overriding dh targets.
# ============================================================

SHELL := /bin/bash

PROJECT := ghvshort
UV ?= uv

# Dev config (macOS / local)
CONFIG_DEV := $(CURDIR)/etc/ghvshort/config.dev.toml

# Docker / Debian build
DEB_IMAGE ?= ghvshort-deb:bookworm
DEB_DOCKERFILE ?= Dockerfile.deb.bookworm

# ------------------------------------------------------------
# Help
# ------------------------------------------------------------
.PHONY: help
help:
	@echo "Targets:"
	@echo "  dev                  - sync dev deps (uv) + init db (dev config)"
	@echo "  precommit            - install pre-commit hooks"
	@echo "  fmt                  - format code (ruff)"
	@echo "  lint                 - ruff lint + mypy"
	@echo "  test                 - run pytest"
	@echo "  check                - fmt(check) + lint + test"
	@echo "  run                  - run service locally (dev config)"
	@echo "  smoke                - simple CLI+HTTP smoke test (local)"
	@echo "  deb-version          - set debian version YYYY.MM.DD-1 (local dch)"
	@echo "  deb-version-docker   - set debian version YYYY.MM.DD-1 (via Docker)"
	@echo "  deb-image            - build Docker image for Debian build"
	@echo "  deb-docker-dist      - build .deb in Docker, artifacts to ./dist"
	@echo "  deb-docker-dist-clean- clean ./dist"
	@echo "  purge-dev            - remove local dev artifacts"

# ------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------
.PHONY: _uv
_uv:
	@command -v $(UV) >/dev/null || (echo "uv not found. Install uv first." && exit 1)

.PHONY: _localdirs
_localdirs:
	@mkdir -p $(CURDIR)/.local

# ------------------------------------------------------------
# Development
# ------------------------------------------------------------
.PHONY: dev
dev: _uv _localdirs
	$(UV) sync --extra dev
	@echo "GHVSHORT_CONFIG=$(CONFIG_DEV)"
	@GHVSHORT_CONFIG="$(CONFIG_DEV)" $(UV) run $(PROJECT) db-init >/dev/null
	@echo "OK"

.PHONY: precommit
precommit: _uv
	$(UV) sync --extra dev
	@$(UV) run pre-commit install
	@echo "pre-commit installed"

.PHONY: fmt
fmt: _uv
	$(UV) sync --extra dev
	@$(UV) run ruff format .

.PHONY: lint
lint: _uv
	$(UV) sync --extra dev
	@$(UV) run ruff check .
	@$(UV) run mypy --config-file mypy.ini

.PHONY: test
test: _uv
	$(UV) sync --extra dev
	@$(UV) run pytest

.PHONY: check
check: _uv
	$(UV) sync --extra dev
	@$(UV) run ruff format --check .
	@$(UV) run ruff check .
	@$(UV) run mypy --config-file mypy.ini
	@$(UV) run pytest

.PHONY: run
run: _uv _localdirs
	$(UV) sync --extra dev
	@echo "Running on http://127.0.0.1:8731 (config: $(CONFIG_DEV))"
	@GHVSHORT_CONFIG="$(CONFIG_DEV)" \
	  $(UV) run $(PROJECT) serve --host 127.0.0.1 --port 8731

.PHONY: smoke
smoke: _uv _localdirs
	$(UV) sync --extra dev
	@command -v curl >/dev/null || (echo "curl not found." && exit 1)
	@echo "1) init db"
	@GHVSHORT_CONFIG="$(CONFIG_DEV)" $(UV) run $(PROJECT) db-init >/dev/null
	@echo "2) add test link"
	@GHVSHORT_CONFIG="$(CONFIG_DEV)" $(UV) run $(PROJECT) add test https://example.org --code 302 >/dev/null || true
	@echo "3) start server (background)"
	@GHVSHORT_CONFIG="$(CONFIG_DEV)" \
	  $(UV) run $(PROJECT) serve --host 127.0.0.1 --port 8731 >/tmp/$(PROJECT).smoke.log 2>&1 & \
	  echo $$! > /tmp/$(PROJECT).smoke.pid
	@sleep 1
	@echo "4) curl redirect"
	@curl -s -o /dev/null -D - http://127.0.0.1:8731/test | head -n 8
	@echo "5) stop server"
	@kill `cat /tmp/$(PROJECT).smoke.pid` >/dev/null 2>&1 || true
	@rm -f /tmp/$(PROJECT).smoke.pid
	@echo "OK"

# ------------------------------------------------------------
# Debian versioning
# ------------------------------------------------------------
.PHONY: deb-version
deb-version:
	@command -v dch >/dev/null || (echo "dch not found. Install devscripts or use deb-version-docker." && exit 1)
	dch --newversion "$$(date +%Y.%m.%d)-1" "Release build"
	@echo "Updated debian/changelog to $$(date +%Y.%m.%d)-1 (commit this)."

.PHONY: deb-version-docker
deb-version-docker: deb-image
	docker run --rm -t -v "$$PWD":/src -w /src $(DEB_IMAGE) bash -lc '\
	  set -euo pipefail; \
	  dch --newversion "$$(date +%Y.%m.%d)-1" "Release build" \
	'
	@echo "Updated debian/changelog (please review & commit)."

# ------------------------------------------------------------
# Debian build in Docker (bookworm)
# ------------------------------------------------------------
.PHONY: deb-image
deb-image:
	docker build -f $(DEB_DOCKERFILE) -t $(DEB_IMAGE) .

.PHONY: deb-docker-dist
deb-docker-dist: deb-image
	@mkdir -p dist
	docker run --rm -t \
	  -v "$$PWD":/src \
	  -w /build/src \
	  $(DEB_IMAGE) \
	  bash -lc '\
	    set -euo pipefail; \
	    rm -rf /build && mkdir -p /build/src; \
	    cd /src; \
	    tar -cf - \
	      --exclude=dist \
	      --exclude=.git \
	      --exclude=.venv \
	      --exclude=.uv \
	      --exclude=__pycache__ \
	      --exclude=.pytest_cache \
	      --exclude=.mypy_cache \
	      --exclude=.ruff_cache \
	      . | tar -xf - -C /build/src; \
	    cd /build/src; \
	    dpkg-buildpackage -us -uc; \
	    mkdir -p /src/dist; \
	    cp -v /build/*.deb /src/dist/ 2>/dev/null || true; \
	    cp -v /build/*.buildinfo /src/dist/ 2>/dev/null || true; \
	    cp -v /build/*.changes /src/dist/ 2>/dev/null || true; \
	  '
	@echo "Done. Artifacts in ./dist/"

.PHONY: deb-docker-dist-clean
deb-docker-dist-clean:
	rm -rf dist/*

# ------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------
.PHONY: purge-dev
purge-dev:
	@echo "Removing local dev artifacts"
	@find . -maxdepth 4 -type f \( -name "*.db" -o -name "*.sqlite" -o -name "*.sqlite3" -o -name "*.log" \) -print -delete || true
	@rm -rf __pycache__ */__pycache__ .pytest_cache .mypy_cache .ruff_cache .local || true
