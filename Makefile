
.PHONY: help install install-cli run test test-cov lint format format-check security docker-build docker-run docker-push ci-local clean

# Default target
help:
	@echo "Delivery-Bot - CI/CD Pipeline Management Tool"
	@echo ""
	@echo "Available commands:"
	@echo "  install      - Install all dependencies and package in development mode"
	@echo "  install-cli  - Install CLI tool as a system command"
	@echo "  run          - Start the API server"
	@echo "  test         - Run all tests"
	@echo "  test-cov     - Run tests with coverage report"
	@echo "  lint         - Run linting checks"
	@echo "  format       - Format code with black and isort"
	@echo "  format-check - Check code formatting without making changes"
	@echo "  security     - Run security scans (bandit + safety)"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run Docker container"
	@echo "  docker-push  - Push Docker image to registry"
	@echo "  ci-local     - Run full CI pipeline locally"
	@echo "  clean        - Clean up generated files and caches"
	@echo ""
	@echo "CLI Commands:"
	@echo "  cli-help     - Show CLI help"
	@echo "  cli-status   - Check API status"
	@echo "  cli-list     - List all pipelines"
	@echo "  cli-create   - Create pipeline from example"
	@echo "  cli-trigger  - Trigger pipeline (replace <pipeline-id>)"
	@echo "  cli-watch    - Watch pipeline run (replace <run-id>)"
	@echo ""

install:
	@echo "Installing dependencies..."
	python -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e '.[dev]'
	@echo "Installation complete!"

install-cli: install
	@echo "Installing CLI tool..."
	. .venv/bin/activate && pip install -e .
	@echo "CLI tool installed! Use 'python -m cli.cli --help' to get started"

run:
	@echo "Starting Delivery-Bot API server..."
	. .venv/bin/activate && uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload

test:
	@echo "Running tests..."
	. .venv/bin/activate && pytest tests/ -v

test-cov:
	@echo "Running tests with coverage..."
	. .venv/bin/activate && pytest tests/ -v --cov=api --cov-report=html --cov-report=term-missing

lint:
	@echo "Running linting checks..."
	. .venv/bin/activate && flake8 api/ tests/ --count --select=E9,F63,F7,F82 --show-source --statistics
	. .venv/bin/activate && flake8 api/ tests/ --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics
	. .venv/bin/activate && black --check --diff .
	. .venv/bin/activate && isort --check-only --diff .
	. .venv/bin/activate && mypy api/ --ignore-missing-imports --no-strict-optional

format:
	@echo "Formatting code..."
	. .venv/bin/activate && black .
	. .venv/bin/activate && isort .

format-check:
	@echo "Checking code format..."
	. .venv/bin/activate && black --check --diff .
	. .venv/bin/activate && isort --check-only --diff .

security:
	@echo "Running security scans..."
	. .venv/bin/activate && bandit -r api/ -f json -o bandit-report.json
	. .venv/bin/activate && safety check --json --output safety-report.json || true

docker-build:
	@echo "Building Docker image..."
	docker build -t omojaphet/delivery-bot-api:latest .

docker-run:
	@echo "Running Docker container..."
	docker run --rm -p 8080:8080 omojaphet/delivery-bot-api:latest

docker-push:
	@echo "Pushing Docker image..."
	docker push omojaphet/delivery-bot-api:latest

ci-local: format-check lint test-cov security
	@echo "All CI checks passed locally!"

# CLI convenience commands
cli-help:
	@echo "CLI Help - Available commands:"
	. .venv/bin/activate && python -m cli.cli --help

cli-status:
	@echo "Checking API status..."
	. .venv/bin/activate && python -m cli.cli status

cli-list:
	@echo "Listing pipelines..."
	. .venv/bin/activate && python -m cli.cli list

cli-create:
	@echo "Creating pipeline from example..."
	. .venv/bin/activate && python -m cli.cli create pipeline.example.json

cli-trigger:
	@echo "Triggering pipeline (replace <pipeline-id> with actual ID)..."
	. .venv/bin/activate && python -m cli.cli trigger <pipeline-id>

cli-watch:
	@echo "Watching pipeline run (replace <run-id> with actual ID)..."
	. .venv/bin/activate && python -m cli.cli watch <run-id>

# Development workflow commands
dev-setup: install-cli
	@echo "Development environment ready!"
	@echo "  - API: make run"
	@echo "  - Tests: make test"
	@echo "  - CLI: python -m cli.cli --help"

quick-test:
	@echo "Running quick test suite..."
	. .venv/bin/activate && pytest tests/ -x --tb=short

clean:
	@echo "Cleaning up..."
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info/
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	@echo "Cleanup complete!"
