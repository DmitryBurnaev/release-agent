.DEFAULT_GOAL := help

MAKEFILE_TARGET := $(filter-out --help Makefile,$(MAKECMDGOALS))
-include .env

ANALYTICS_SEED_ROWS ?= 500
ANALYTICS_SEED_DAYS_RANGE ?= 30
RELEASES_SEED_START ?= 2023.1.1
RELEASES_SEED_END ?= 2026.9.2
LOAD_TEST_REQUESTS ?= 100000
LOAD_TEST_CONCURRENCY ?= 20
LOAD_TEST_TIMEOUT ?= 30
LOAD_TEST_PROGRESS_EVERY ?= 5000
LOAD_TEST_INSTALLATIONS ?= 1000

.PHONY: help
help: ## This help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*? / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: lint
lint: ## Linting project
	@echo Linting...
	uv run ruff check
	uv run mypy .

.PHONY: format
format: ## Apply formatting using black
	@echo Formatting...
	uv run black .
	uv run ruff check --fix

.PHONY: install
install: ## Install dependencies
	@echo Installing dependencies...
	uv venv
	uv sync

.PHONY: deps
deps: ## Update dependencies
	@echo Updating dependencies...
	uv lock --upgrade
	uv sync --reinstall

.PHONY: run
run: .env ## Run app
	@echo Run project...
	uv run python -m src.main

.PHONY: run
run-in-docker: .env ## Run app
	@echo Run project in container...
	docker compose up app --build

.PHONY: test
test: .env ## Run tests with coverage report
	@echo Test project with coverage...
	uv run coverage run -m pytest -v
	uv run coverage report
	rm .coverage

.PHONY: run
test-in-docker: .env  ## Run tests inside docker container
	@echo Run project in container...
	docker compose up test --build

.PHONY: run
lint-in-docker: .env  ## Run linting inside docker container
	@echo Run project in container...
	docker compose up lint --build

.PHONY: migration
migration: .env ## Make DB migrations
	@read -p "Revision: " db_revision; \
	uv run alembic revision --autogenerate -m "$$db_revision"

.PHONY: migrations-upgrade
migrate: .env ## Apply DB migrations
	@echo Migrations: apply revisions...
	uv run alembic upgrade head

.PHONY: migrations
downgrade: .env ## Downgrade (unapply) DB migration (last revision)
	@echo Migrations: downgrade last revisions...
	uv run alembic downgrade -1

.PHONY: secrets
secrets: .env ## Create new secrets
	@echo Encryption: creating new key
	uv run python -m src.modules.cli.generate_secrets

.PHONY: seed-analytics
seed-analytics: .env ## Fill ClickHouse analytics table with fake release requests
	@echo Analytics: seeding ClickHouse release request data...
	uv run python -m src.modules.cli.management seed-analytics --rows "$(ANALYTICS_SEED_ROWS)" --days-range "$(ANALYTICS_SEED_DAYS_RANGE)" $(if $(ANALYTICS_SEED_RANDOM_SEED),--random-seed "$(ANALYTICS_SEED_RANDOM_SEED)",)

.PHONY: seed-releases
seed-releases: .env ## Fill PostgreSQL with sequential active releases
	@echo Releases: seeding PostgreSQL release data...
	uv run python -m src.modules.cli.management seed-releases --start "$(RELEASES_SEED_START)" --end "$(RELEASES_SEED_END)"

.PHONY: load-test
load-test: .env ## Send GET requests to RELEASES_URL with at most 20 concurrent workers
	uv run python -m src.modules.cli.management load-test --url "$(RELEASES_URL)" --requests "$(LOAD_TEST_REQUESTS)" --concurrency "$(LOAD_TEST_CONCURRENCY)" --timeout "$(LOAD_TEST_TIMEOUT)" --progress-every "$(LOAD_TEST_PROGRESS_EVERY)" --installations "$(LOAD_TEST_INSTALLATIONS)" $(if $(LOAD_TEST_RANDOM_SEED),--random-seed "$(LOAD_TEST_RANDOM_SEED)",)
