
.PHONY: install run test lint format docker-build docker-run

install:
	python -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e '.[dev]'

run:
	uvicorn api.main:app --host 0.0.0.0 --port 8080 --workers 2 --proxy-headers

test:
	pytest -q

lint:
	ruff check .

format:
	ruff format .

docker-build:
	docker build -t ghcr.io/OWNER/cicd-pipelines-api:latest .

docker-run:
	docker run --rm -p 8080:8080 ghcr.io/OWNER/cicd-pipelines-api:latest
