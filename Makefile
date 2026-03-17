.PHONY: up down build migrate makemigrations shell test test-unit test-integration test-e2e test-slow coverage lint format typecheck clean logs

# ── Docker ────────────────────────────────────────────────────────
up:
	docker compose up -d --build

down:
	docker compose down -v

build:
	docker compose build

logs:
	docker compose logs -f

# ── Django ────────────────────────────────────────────────────────
migrate:
	docker compose run --rm django-migrate

makemigrations:
	docker compose exec fastapi python /app/django_app/manage.py makemigrations

shell:
	docker compose exec fastapi python /app/django_app/manage.py shell

createsuperuser:
	docker compose exec fastapi python /app/django_app/manage.py createsuperuser

# ── Tests ─────────────────────────────────────────────────────────
test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -m unit -v --no-cov

test-integration:
	pytest tests/integration/ -m integration -v

test-e2e:
	pytest tests/e2e/ -m e2e -v

test-slow:
	pytest tests/backtesting/ -m slow -v --timeout=300

coverage:
	pytest --cov=. --cov-report=html --cov-report=term-missing
	@echo "Coverage report: htmlcov/index.html"

# ── Code quality ──────────────────────────────────────────────────
lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy . --ignore-missing-imports

# ── Utilities ─────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	rm -rf .pytest_cache htmlcov .coverage

generate-fernet-key:
	python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

generate-secret-key:
	python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# ── Database ──────────────────────────────────────────────────────
db-shell:
	docker compose exec timescaledb psql -U candlescout -d candlescout

db-backup:
	docker compose exec timescaledb pg_dump -U candlescout candlescout > backup_$$(date +%Y%m%d_%H%M%S).sql

db-restore:
	docker compose exec -T timescaledb psql -U candlescout -d candlescout < $(FILE)

# ── Redis ─────────────────────────────────────────────────────────
redis-cli:
	docker compose exec redis redis-cli

redis-flush:
	docker compose exec redis redis-cli FLUSHALL

redis-monitor:
	docker compose exec redis redis-cli MONITOR

# ── Services ──────────────────────────────────────────────────────
start-data-ingestion:
	docker compose up -d data-ingestion

start-analysis:
	docker compose up -d analysis-pipeline

start-ml:
	docker compose up -d ml-service

start-dispatcher:
	docker compose up -d signal-dispatcher

start-executor:
	docker compose up -d trade-executor

start-position-manager:
	docker compose up -d position-manager

start-api:
	docker compose up -d api-service

# ── Monitoring ────────────────────────────────────────────────────
start-monitoring:
	docker compose up -d prometheus grafana

open-grafana:
	open http://localhost:3000 || xdg-open http://localhost:3000

open-prometheus:
	open http://localhost:9090 || xdg-open http://localhost:9090

# ── Development ───────────────────────────────────────────────────
dev-setup:
	@echo "Setting up CandleScout Pro development environment..."
	cp .env.example .env
	@echo "✓ Created .env file"
	@echo "✓ Edit .env with your API keys and configuration"
	@echo "Run 'make up' to start all services"

status:
	docker compose ps
