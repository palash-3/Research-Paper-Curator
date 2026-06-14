.PHONY: start stop restart status logs health setup format lint test test-cov clean help

start:
	docker compose up --build -d

stop:
	docker compose down

restart:
	docker compose down
	docker compose up --build -d

status:
	docker compose ps

logs:
	docker compose logs -f

health:
	curl -s http://localhost:8000/api/v1/health | python3 -m json.tool

setup:
	uv sync

format:
	uv run ruff format src/ tests/

lint:
	uv run ruff check src/ tests/ && uv run mypy src/

test:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ --cov=src --cov-report=html

clean:
	docker compose down -v --remove-orphans

help:
	@echo "Available commands:"
	@echo "  make start      - Start all services"
	@echo "  make stop       - Stop all services"
	@echo "  make restart    - Restart all services"
	@echo "  make status     - Show service status"
	@echo "  make logs       - Show service logs"
	@echo "  make health     - Check all services health"
	@echo "  make setup      - Install Python dependencies"
	@echo "  make format     - Format code"
	@echo "  make lint       - Lint and type check"
	@echo "  make test       - Run tests"
	@echo "  make test-cov   - Run tests with coverage"
	@echo "  make clean      - Clean up everything"