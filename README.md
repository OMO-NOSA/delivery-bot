
# Delivery-Bot -- Delivery-Bot API + CLI

A minimal, production-ready REST API to define and trigger simple CI/CD pipelines, plus a utility CLI.
Execution is simulated (no real Docker/ECR/Kubernetes) but models realistic interactions and logs.

## Features
- REST API (FastAPI) with OpenAPI docs at `/docs`
- Endpoints to create, list, get, update, delete pipelines; trigger runs; fetch run status/logs
- In-memory storage (swap with a DB later without changing handlers)
- Async run execution with per-step simulated logs
- CLI (Typer + Rich) to interact with the server (create/list/get/update/delete/trigger/watch)
- Unit tests with `pytest`
- Docker image and GitHub Actions workflow
- CORS enabled; health endpoint at `/healthz`

## Data Model
**Pipeline**
- `name`, `repo_url`, `branch`
- `steps[]` of types: `run`, `build`, `deploy`
  - `run`: `command`
  - `build`: `dockerfile`, `ecr_repo`
  - `deploy`: `manifest`

**Run**
- `status`: pending|running|succeeded|failed|cancelled
- `logs[]`, timestamps

## Quickstart (local)
```bash
python -m venv .venv && . .venv/bin/activate
pip install -U pip
pip install -e '.[dev]'
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
# Open http://localhost:8080/docs
```

## Docker
```bash
docker build -t cicd-pipelines-api:local .
docker run --rm -p 8080:8080 cicd-pipelines-api:local
```

## CLI Usage
Create a pipeline (save as `pipeline.json`) then:
```bash
python -m cli.cli create pipeline.json
python -m cli.cli list
python -m cli.cli trigger <PIPELINE_ID>
python -m cli.cli watch <RUN_ID>
```

## GitHub Actions as the Pipeline Engine (optional)
If you want the API to also dispatch a GitHub Actions workflow on trigger, set:
```
export APP_GITHUB_OWNER=<org-or-username>
export APP_GITHUB_REPO=<repo-name>
export APP_GITHUB_WORKFLOW=pipeline.yml
export APP_GITHUB_REF=main
export APP_GITHUB_TOKEN=<PAT with workflow scope>
```

## Assumptions
- Execution is simulated; logs mimic real steps.
- In-memory store for this exercise.
- No auth by default.
- Step-field validation enforced: run/command; build/dockerfile+ecr_repo; deploy/manifest.

## Logging
- `cicd` logger to stdout; level from `APP_LOG_LEVEL` (default `INFO`)
- Request middleware logs method, path, status, duration_ms
- Exceptions are logged with context

## Error Handling
- 404 for missing resources
- 422 for invalid payloads (Pydantic)
- 500 handler returns generic message (details in logs)

## Developer Steps
1. Install: `pip install -e .[dev]`
2. Run API: `uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload`
3. Use CLI: `python -m cli.cli ...`
4. Tests: `pytest -q`
5. Lint/Format: `ruff check .` / `ruff format .`
6. Docker: build and run above
7. Optional GH Actions dispatch: set `APP_GITHUB_*` and trigger a pipeline
