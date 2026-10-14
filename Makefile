# LEDGEIT — common tasks. See README.md.
SHELL := /bin/bash
PY ?= .venv/bin/python
PIP ?= .venv/bin/pip
COMPOSE := docker compose -f infra/docker-compose.yml

.PHONY: dev-start dev-stop dev-status worker help install install-py install-js test test-py test-ts test-contracts lint up down logs migrate seed schema vectors

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-16s %s\n", $$1, $$2}'

install: install-py install-js ## Install everything for local development

install-py: ## Python venv + packages
	test -d .venv || python3 -m venv .venv
	$(PIP) install -q --upgrade pip
	$(PIP) install -q -e packages/proof-core/python -r apps/api/requirements.txt -r apps/api/requirements-dev.txt
	$(PIP) install -q -e apps/api -r services/ai-inspector/requirements.txt -e services/edge-simulator

install-js: ## npm deps for proof-core TS and contracts
	npm ci --prefix packages/proof-core/ts
	npm ci --prefix contracts

test: test-py test-ts test-contracts ## Run all test suites

test-py: ## Python tests (needs Postgres, see TEST_DATABASE_URL)
	$(PY) -m pytest -q packages/proof-core/python apps/api
	cd services/ai-inspector && ../../$(PY) -m pytest -q

test-ts:
	cd packages/proof-core/ts && npx vitest run

test-contracts:
	cd contracts && npx hardhat test

lint: ## Ruff + TS typecheck
	.venv/bin/ruff check .
	cd packages/proof-core/ts && npx tsc --noEmit

up: ## Start the full stack with docker compose
	$(COMPOSE) up -d --build

down: ## Stop the stack
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

migrate: ## Apply DB migrations
	$(PY) -m ledgeit_api.db.migrate

seed: migrate ## Seed demo plant, lines, devices, users
	$(PY) -m ledgeit_api.db.seed

openapi: ## Export docs/api/openapi.json
	$(PY) -c "import json; from ledgeit_api.main import create_app; open('docs/api/openapi.json','w').write(json.dumps(create_app().openapi(), indent=1)+'\n')"

schema: ## Regenerate infra/db/schema.sql from migrations
	$(PY) -m ledgeit_api.db.migrate --dump infra/db/schema.sql

vectors: ## Regenerate proof-core test vectors
	$(PY) packages/proof-core/scripts/gen_vectors.py

dev-start: ## Run the stack natively (no Docker): hardhat, ai, api, worker, web
	scripts/dev.sh start

dev-stop:
	scripts/dev.sh stop

dev-status:
	scripts/dev.sh status

worker: ## Anchor everything pending right now (one tick, flush all windows)
	$(PY) -m ledgeit_api.anchoring.run --once --flush
