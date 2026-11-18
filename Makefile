# Thin wrapper around ./tut so people and CI run the same commands.
# `make` or `make help` lists the targets.

PY      ?= python3
T       ?=
V       ?=
BASE    ?=
REF     ?= main
DRY_RUN ?= true

export NO_MKDOCS_2_WARNING := 1
.DEFAULT_GOAL := help
.PHONY: help setup sync lint test site check ui list run run-keep matrix release-plan release

help: ## Show this help
	@grep -hE '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

setup: ## Install the Python dependencies (Python 3.11+)
	$(PY) -m pip install -r tools/requirements.txt

sync: ## Regenerate the <!-- tut:... --> regions
	./tut sync

lint: ## Check every rule (BASE=origin/main also checks frozen parts)
	./tut lint $(if $(BASE),--base $(BASE))

test: ## Tests for the rules, the runner and the UI session
	PYTHONPATH=tools $(PY) -m pytest -q tools/tests

site: ## Build the static site into build/site
	./tut site
	mkdocs build --strict

check: ## Everything CI checks without a cluster: lint, tests, site
	@$(MAKE) --no-print-directory lint test site

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
