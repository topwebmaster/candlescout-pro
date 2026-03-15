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
