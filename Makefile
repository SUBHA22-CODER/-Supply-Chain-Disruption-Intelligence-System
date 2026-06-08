.PHONY: dev-up dev-down test lint migrate install

dev-up:
	docker compose up -d

dev-down:
	docker compose down -v

test:
	pytest

lint:
	pre-commit run --all-files

migrate:
	alembic upgrade head

install:
	pip install -e .[ml,data,dev]
