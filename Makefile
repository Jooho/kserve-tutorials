# Thin wrapper around ./tut so people and CI run the same commands.
# `make` or `make help` lists the targets.
#
# Two kinds of dependencies, kept apart:
#   make setup   what ./tut itself needs: a .venv with the Python packages
#   tutorials    each environment installs its own CLI tools (envs/*/tools.env)
#                into .tools/<tool>/<version>/ when its setup step runs;
#                `make tools` only downloads them ahead of time.
# Docker, git and curl are yours to install; `make doctor` checks them.

VENV    := .venv
PY      ?= $(if $(wildcard $(VENV)/bin/python),$(VENV)/bin/python,python3)
ENV     ?=
CLUSTER ?=
T       ?=
V       ?=
BASE    ?=
REF     ?= main
DRY_RUN ?= true

export NO_MKDOCS_2_WARNING := 1
ifneq ($(CLUSTER),)
export KIND_CLUSTER_NAME := $(CLUSTER)
endif
.DEFAULT_GOAL := help
.PHONY: help setup config doctor tools sync lint test site check precommit ui list run run-keep matrix release-plan release

help: ## Show this help
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

setup: ## Prepare ./tut itself: .venv + Python packages (needs Python 3.11+)
	@test -x $(VENV)/bin/python || python3 -m venv $(VENV)
	$(VENV)/bin/python -m pip install -q --upgrade pip
	$(VENV)/bin/python -m pip install -q -r tools/requirements.txt
	@./tut doctor --toolkit
	@echo "Next: make doctor   (can this machine run the tutorials?)"

config: ## Remember personal settings in .tut.env: make config CLUSTER=tut (no args: show)
	./tut config $(if $(CLUSTER),KIND_CLUSTER_NAME=$(CLUSTER))

doctor: ## Check this machine: toolkit, Docker/host, environments (T=<id> for one tutorial)
	./tut doctor $(if $(T),--tutorial $(T))

tools: ## Download the CLI tools of an environment ahead of time (ENV=kind-llmisvc/v1; default all)
	@for f in $(if $(ENV),envs/$(ENV)/tools.env,$(wildcard envs/*/*/tools.env)); do tools/install-tools.sh $$f; done

sync: ## Regenerate the <!-- tut:... --> regions
	./tut sync

lint: ## Check every rule (BASE=origin/main also checks frozen parts)
	./tut lint $(if $(BASE),--base $(BASE))

test: ## Tests for the rules, the runner and the UI session
	PYTHONPATH=tools $(PY) -m pytest -q tools/tests

site: ## Build the static site into build/site
	./tut site
	$(PY) -m mkdocs build --strict

check: ## Everything CI checks without a cluster: lint, tests, site
	@$(MAKE) --no-print-directory lint test site

precommit: ## Before every commit: ./tut sync, then make check (CI runs the same checks, without sync)
	./tut sync
	@$(MAKE) --no-print-directory check
	@if [ -n "$$(git status --short)" ]; then printf '\nNot committed yet (./tut sync may have updated some):\n'; git status --short; fi

ui: ## Start the local runner UI
	./tut ui

list: ## List tutorials
	./tut list

run: ## Run a tutorial end to end: make run T=<id> [V=<kserve-version>]
	@test -n "$(T)" || { echo "usage: make run T=<tutorial-id> [V=<kserve-version>]"; exit 2; }
	./tut run $(T) $(if $(V),--kserve-version $(V))

run-keep: ## Like run, but keep resources when a step fails
	@test -n "$(T)" || { echo "usage: make run-keep T=<tutorial-id> [V=<kserve-version>]"; exit 2; }
	./tut run $(T) $(if $(V),--kserve-version $(V)) --keep-on-failure

matrix: ## What a release and the weekly run verify
	./tut matrix --scheduled

release-plan: ## Show the next release version and what it would verify
	@echo "next version: $$(./tut release next-version)"
	@./tut release can-ff $$(git rev-parse $(REF)) || true
	@echo "matrix:"
	@./tut matrix --scheduled | sed 's/^/  /'

release: ## Start the release workflow on GitHub: make release [REF=main] [DRY_RUN=false]
	gh workflow run release.yml -f ref=$(REF) -f dry_run=$(DRY_RUN)
	@echo "Follow it in the Actions tab, or: gh run watch"
