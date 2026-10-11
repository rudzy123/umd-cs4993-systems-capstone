.PHONY: install postgres up down migrate test test-frontend lint build-frontend smoke

COMPOSE = docker compose

install:
	python3 -m pip install -e "./backend[dev]" -e "./worker[dev]"
	cd frontend && npm install

postgres:
	$(COMPOSE) up -d --wait postgres

up:
	$(COMPOSE) up --build -d --wait

down:
	$(COMPOSE) down

migrate: postgres
	$(COMPOSE) run --rm --build api python -m northstar.migrate

test: postgres
	pytest

test-frontend:
	cd frontend && npm test

lint:
	ruff check backend worker tests conftest.py scripts
	ruff format --check backend worker tests conftest.py scripts
	mypy
	cd frontend && npm run lint

build-frontend:
	cd frontend && npm run build

smoke:
	python3 scripts/smoke_test.py
