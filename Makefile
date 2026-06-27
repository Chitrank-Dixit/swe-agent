.PHONY: help build build-no-cache up down restart logs clean test run-cli init devcoach tark-swe resume

help:
	@echo "Available commands (all execution occurs inside Docker Compose):"
	@echo "  make build           Build the Docker compose services"
	@echo "  make build-no-cache  Build the Docker compose services without cache"
	@echo "  make up              Run the FastAPI server in Docker containers (detached)"
	@echo "  make down            Stop and remove all Docker containers"
	@echo "  make restart         Restart all Docker containers"
	@echo "  make logs            Follow container logging streams"
	@echo "  make clean           Remove database volumes, local caches, and log files"
	@echo "  make test            Run the pytest suite inside the Docker environment"
	@echo "  make init            Initialize repository (scan structure and generate AGENTS.md)"
	@echo "  make run-cli         Start the interactive coaching CLI inside the Docker container"
	@echo "  make resume          Resume previous session. Usage: make resume session=<session_id>"
	@echo "  make devcoach        Start the interactive coaching CLI (DevCoach)"
	@echo "  make tark-swe        Alias command to start the interactive coaching CLI"

build:
	docker compose build

build-no-cache:
	docker compose build --no-cache

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose down && docker compose up -d

logs:
	docker compose logs -f

clean:
	docker compose down -v
	rm -rf data/coach.db coach.db .pytest_cache coach_workflow.log

test:
	docker compose run --rm -e PYTHONPATH=. api pytest

run-cli:
	docker compose run --rm -e PYTHONPATH=. api python src/cli.py

init:
	docker compose run --rm -e PYTHONPATH=. api python src/cli.py init

devcoach: run-cli
tark-swe: run-cli

resume:
	@if [ -z "$(session)" ]; then \
		echo "Usage: make resume session=<session_id>"; \
		exit 1; \
	fi
	docker compose run --rm -e PYTHONPATH=. api python src/cli.py $(session)
