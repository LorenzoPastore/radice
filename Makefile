.PHONY: up down restart logs logs-backend shell-backend shell-db migrate makemigrations test-backend test-frontend lint-backend lint-frontend install-hooks

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

shell-backend:
	docker compose exec backend python manage.py shell

shell-db:
	docker compose exec postgres psql -U radice -d radice

migrate:
	docker compose exec backend python manage.py migrate

makemigrations:
	docker compose exec backend python manage.py makemigrations $(app)

test-backend:
	docker compose exec backend pytest $(args)

test-frontend:
	docker compose exec frontend pnpm test

lint-backend:
	docker compose exec backend ruff check . && ruff format --check .

lint-frontend:
	docker compose exec frontend pnpm lint

install-hooks:
	pre-commit install --hook-type commit-msg
	pre-commit install
