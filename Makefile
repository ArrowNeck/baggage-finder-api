.PHONY: help install run test cov lint format revision migrate downgrade clean full-clean

help:
	@echo "Available commands:"
	@echo ""
	@echo "  make install                - Create venv and install dependencies (uv)"
	@echo "  make run                    - Run FastAPI app with auto reload"
	@echo "  make revision MSG='message' - Create an Alembic autogenerate migration"
	@echo "  make migrate                - Apply all migrations"
	@echo "  make downgrade              - Roll back the last migration"
	@echo "  make test                   - Run tests"
	@echo "  make cov                    - Run tests with coverage"
	@echo "  make lint                   - Run Ruff linter"
	@echo "  make format                 - Run Ruff formatter"
	@echo "  make clean                  - Remove cache/build files"
	@echo "  make full-clean             - Remove cache + virtual environment"

install:
	uv venv
	uv pip install -e ".[dev]"
	@echo "→ Activate with: source .venv/bin/activate"

run:
	uvicorn app.main:app --reload

revision:
	alembic revision --autogenerate -m "$(MSG)"

migrate:
	alembic upgrade head

downgrade:
	alembic downgrade -1

test:
	pytest -v

cov:
	pytest --cov=app --cov-report=term-missing

lint:
	ruff check app/ tests/ alembic/

format:
	ruff format app/ tests/ alembic/

clean:
	find . -type d -name "__pycache__" -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name "*.pyc" -not -path "./.venv/*" -delete
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov dist build *.egg-info *.db

full-clean: clean
	rm -rf .venv
	@echo "✓ Project fully cleaned"
