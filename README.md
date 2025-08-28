
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
- CORS enabled; health endpoint at `/health`
- GitHub integration with automatic workflow creation via Pull Requests

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
python3 -m venv .venv && . .venv/bin/activate
pip install -U pip
pip install -e '.[dev]'
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
# Open http://localhost:8080/docs
```

## Docker
```bash
docker build -t delivery-bot-api:local .
docker run --rm -p 8080:8080 delivery-bot-api:local
```

## CLI Usage

The Delivery-Bot comes with a powerful command-line interface for easy interaction with the API.

### Installation

```bash
# Install the CLI as a system command
make install-cli

# or manually
pip install -e .

# Note: Due to package structure, use the module approach:
python -m cli.cli --help
```

### Available Commands
```bash
# Show help
python -m cli.cli --help

# Check API status
python -m cli.cli status

# Create a pipeline from JSON file
python -m cli.cli create pipeline.example.json

# List all pipelines
python -m cli.cli list

# Get pipeline details
python -m cli.cli get <pipeline-id>

# Update a pipeline
python -m cli.cli update <pipeline-id> pipeline.example.json

# Delete a pipeline
python -m cli.cli delete <pipeline-id>

# Trigger a pipeline execution
python -m cli.cli trigger <pipeline-id>

# Watch a pipeline run in real-time
python -m cli.cli watch <run-id>

# Use custom API base URL
python -m cli.cli list --base http://localhost:9000
```

### Example Workflow
```bash
# 1. Start the API server (in one terminal)
make run

# 2. Use the CLI (in another terminal)
# Check if API is running
python -m cli.cli status

# Create a pipeline
python -m cli.cli create pipeline.example.json

# List pipelines to get the ID
python -m cli.cli list

# Trigger the pipeline (replace with actual ID)
python -m cli.cli trigger <pipeline-id>

# Watch the execution
python -m cli.cli watch <run-id>
```

### CLI Features
- **Rich Output**: Beautiful tables and colored output using Rich
- **Error Handling**: Comprehensive error messages and validation
- **Real-time Monitoring**: Watch pipeline execution with live updates
- **Flexible Configuration**: Use custom API endpoints with `--base` flag
- **Help System**: Detailed help for all commands and options

## Makefile Commands

The project includes a comprehensive Makefile for common development tasks:

```bash
# Development setup
make help          # Show all available commands
make install       # Install dependencies
make install-cli   # Install CLI tool
make dev-setup     # Complete development environment setup

# Running the application
make run           # Start API server
make test          # Run tests
make test-cov      # Run tests with coverage
make quick-test    # Run tests with fast failure

# Code quality
make lint          # Run linting checks
make format        # Format code
make format-check  # Check formatting without changes
make security      # Run security scans

# CLI convenience
make cli-help      # Show CLI help
make cli-status    # Check API status
make cli-list      # List pipelines

# Docker operations
make docker-build  # Build Docker image
make docker-run    # Run Docker container
make docker-push   # Push to registry

# CI/CD
make ci-local      # Run full CI pipeline locally
make clean         # Clean up generated files
```

## GitHub Actions as the Pipeline Engine (optional)
If you want the API to also dispatch a GitHub Actions workflow on trigger, set:
```bash
export APP_GITHUB_OWNER=<org-or-username>
export APP_GITHUB_REPO=<repo-name>
export APP_GITHUB_WORKFLOW=pipeline.yml
export APP_GITHUB_REF=main
export APP_GITHUB_TOKEN=<PAT with workflow scope>
export APP_GITHUB_AUTO_CREATE_WORKFLOW=true
```

**Note**: The GitHub integration creates workflows via Pull Requests instead of writing directly to the repository, ensuring proper code review and collaboration.

---

## API Reference

### Base URL
```
http://localhost:8080
```

### Authentication
Currently, the API doesn't require authentication.

---

## API Endpoints

### 1. Health Check

#### GET /health
**Description**: Check if the API is running

**Request**:
```bash
curl -X GET "http://localhost:8080/health"
```

**Response**:
```json
{
  "status": "ok"
}
```

---

### 2. Pipeline Management

#### POST /pipelines
**Description**: Create a new pipeline

**Request**:
```bash
curl -X POST "http://localhost:8080/pipelines" \
  -H "Content-Type: application/json" \
  -d @pipeline_payload.json
```

**Sample Payloads**:

**Simple Pipeline with Run Steps**:
```json
{
  "name": "Simple Test Pipeline",
  "repo_url": "https://github.com/example/test-repo",
  "branch": "main",
  "steps": [
    {
      "name": "Check Dependencies",
      "type": "run",
      "command": "npm install",
      "timeout_seconds": 300,
      "continue_on_error": false
    },
    {
      "name": "Run Tests",
      "type": "run",
      "command": "npm test",
      "timeout_seconds": 600,
      "continue_on_error": false
    }
  ]
}
```

**Build Pipeline with Docker**:
```json
{
  "name": "Docker Build Pipeline",
  "repo_url": "https://github.com/example/docker-app",
  "branch": "develop",
  "steps": [
    {
      "name": "Build Docker Image",
      "type": "build",
      "dockerfile": "./Dockerfile",
      "ecr_repo": "my-app-repo",
      "timeout_seconds": 900,
      "continue_on_error": false
    },
    {
      "name": "Run Integration Tests",
      "type": "run",
      "command": "docker run my-app:latest npm run test:integration",
      "timeout_seconds": 300,
      "continue_on_error": true
    }
  ]
}
```

**Full CI/CD Pipeline**:
```json
{
  "name": "Production Deployment Pipeline",
  "repo_url": "https://github.com/example/production-app",
  "branch": "main",
  "steps": [
    {
      "name": "Install Dependencies",
      "type": "run",
      "command": "npm ci --only=production",
      "timeout_seconds": 300,
      "continue_on_error": false
    },
    {
      "name": "Run Unit Tests",
      "type": "run",
      "command": "npm run test:unit",
      "timeout_seconds": 180,
      "continue_on_error": false
    },
    {
      "name": "Build Docker Image",
      "type": "build",
      "dockerfile": "./Dockerfile.prod",
      "ecr_repo": "production-app-repo",
      "timeout_seconds": 900,
      "continue_on_error": false
    },
    {
      "name": "Deploy to Staging",
      "type": "deploy",
      "manifest": "./k8s/staging-deployment.yaml",
      "timeout_seconds": 600,
      "continue_on_error": false
    },
    {
      "name": "Deploy to Production",
      "type": "deploy",
      "manifest": "./k8s/production-deployment.yaml",
      "timeout_seconds": 600,
      "continue_on_error": false
    }
  ]
}
```

#### GET /pipelines
**Description**: List all pipelines

**Request**:
```bash
curl -X GET "http://localhost:8080/pipelines"
```

#### GET /pipelines/{pipeline_id}
**Description**: Get a specific pipeline by ID

**Request**:
```bash
curl -X GET "http://localhost:8080/pipelines/550e8400-e29b-41d4-a716-446655440000"
```

#### PUT /pipelines/{pipeline_id}
**Description**: Update an existing pipeline

**Request**:
```bash
curl -X PUT "http://localhost:8080/pipelines/550e8400-e29b-41d4-a716-446655440000" \
  -H "Content-Type: application/json" \
  -d @update_pipeline_payload.json
```

#### DELETE /pipelines/{pipeline_id}
**Description**: Delete a pipeline

**Request**:
```bash
curl -X DELETE "http://localhost:8080/pipelines/550e8400-e29b-41d4-a716-446655440000"
```

**Response**: HTTP 204 No Content

---

### 3. Pipeline Execution

#### POST /pipelines/{pipeline_id}/trigger
**Description**: Trigger execution of a pipeline

**Request**:
```bash
curl -X POST "http://localhost:8080/pipelines/550e8400-e29b-41d4-a716-446655440000/trigger"
```

**Response**:
```json
{
  "run_id": "660e8400-e29b-41d4-a716-446655440000",
  "status": "pending"
}
```

---

### 4. Run Monitoring

#### GET /runs/{run_id}
**Description**: Get the status and details of a pipeline run

**Request**:
```bash
curl -X GET "http://localhost:8080/runs/660e8400-e29b-41d4-a716-446655440000"
```

**Response**:
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "pipeline_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "running",
  "started_at": "2024-01-15T12:00:00Z",
  "finished_at": null,
  "current_step": 1,
  "logs": [
    "Pipeline execution started",
    "Step 1: Install Dependencies - Starting",
    "Running shell command: npm ci --only=production",
    "Command finished with exit code 0",
    "Step 2: Run Tests - Starting",
    "Running shell command: npm run test"
  ]
}
```

---

## Step Type Examples

### Run Step
```json
{
  "name": "Install Dependencies",
  "type": "run",
  "command": "npm install",
  "timeout_seconds": 300,
  "continue_on_error": false
}
```

### Build Step
```json
{
  "name": "Build Docker Image",
  "type": "build",
  "dockerfile": "./Dockerfile",
  "ecr_repo": "my-app-repo",
  "timeout_seconds": 900,
  "continue_on_error": false
}
```

### Deploy Step
```json
{
  "name": "Deploy to Kubernetes",
  "type": "deploy",
  "manifest": "./k8s/deployment.yaml",
  "timeout_seconds": 600,
  "continue_on_error": false
}
```

---

## Complete Workflow Example

### Step 1: Create a Pipeline
```bash
curl -X POST "http://localhost:8080/pipelines" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My First Pipeline",
    "repo_url": "https://github.com/example/my-app",
    "branch": "main",
    "steps": [
      {
        "name": "Install Dependencies",
        "type": "run",
        "command": "npm install",
        "timeout_seconds": 300
      },
      {
        "name": "Run Tests",
        "type": "run",
        "command": "npm test",
        "timeout_seconds": 300
      }
    ]
  }'
```

### Step 2: Trigger the Pipeline
```bash
# Use the pipeline ID from the previous response
curl -X POST "http://localhost:8080/pipelines/550e8400-e29b-41d4-a716-446655440000/trigger"
```

### Step 3: Monitor the Run
```bash
# Use the run ID from the trigger response
curl -X GET "http://localhost:8080/runs/660e8400-e29b-41d4-a716-446655440000"
```

---

## Common Use Cases

### Simple CI Pipeline
```json
{
  "name": "CI Pipeline",
  "repo_url": "https://github.com/example/app",
  "steps": [
    {
      "name": "Install",
      "type": "run",
      "command": "npm install"
    },
    {
      "name": "Test",
      "type": "run",
      "command": "npm test"
    },
    {
      "name": "Build",
      "type": "run",
      "command": "npm run build"
    }
  ]
}
```

### Docker Build Pipeline
```json
{
  "name": "Docker Pipeline",
  "repo_url": "https://github.com/example/docker-app",
  "steps": [
    {
      "name": "Build Image",
      "type": "build",
      "dockerfile": "./Dockerfile",
      "ecr_repo": "my-app"
    },
    {
      "name": "Test Image",
      "type": "run",
      "command": "docker run my-app:latest npm test"
    }
  ]
}
```

### Kubernetes Deployment Pipeline
```json
{
  "name": "K8s Deployment",
  "repo_url": "https://github.com/example/k8s-app",
  "steps": [
    {
      "name": "Deploy to Staging",
      "type": "deploy",
      "manifest": "./k8s/staging.yaml"
    },
    {
      "name": "Run Tests",
      "type": "run",
      "command": "kubectl exec -it deployment/staging-app -- npm test"
    },
    {
      "name": "Deploy to Production",
      "type": "deploy",
      "manifest": "./k8s/production.yaml"
    }
  ]
}
```

---

## Environment Variables

To enable GitHub integration, set these environment variables:

```bash
# Required for GitHub integration
APP_GITHUB_OWNER=your-github-username-or-org
APP_GITHUB_REPO=your-repo-name
APP_GITHUB_TOKEN=your-personal-access-token

# Optional
APP_GITHUB_WORKFLOW=pipeline.yml
APP_GITHUB_REF=main
APP_GITHUB_AUTO_CREATE_WORKFLOW=true
```

---

## Testing with cURL

### Test Health Endpoint
```bash
curl -v "http://localhost:8080/health"
```

### Test Pipeline Creation
```bash
curl -v -X POST "http://localhost:8080/pipelines" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Pipeline",
    "repo_url": "https://github.com/example/test",
    "steps": []
  }'
```

### Test Pipeline Trigger
```bash
curl -v -X POST "http://localhost:8080/pipelines/YOUR_PIPELINE_ID/trigger"
```

---

## Assumptions

- Only Github repository is used within the Organization
- Execution is simulated; logs mimic real steps.
- In-memory store for this exercise.
- No auth by default.


## Logging
- `cicd` logger to stdout; level from `APP_LOG_LEVEL` (default `INFO`)
- Request middleware logs method, path, status, duration_ms
- Exceptions are logged with context

## Error Handling
- 404 for missing resources
- 422 for invalid payloads (Pydantic)
- 500 handler returns generic message (details in logs)

## Developer Steps
1. **Setup**: `make dev-setup` (installs everything + CLI)
2. **Run API**: `make run` (starts server with auto-reload)
3. **Use CLI**: `delivery-bot --help` (shows all available commands)
4. **Run Tests**: `make test` (runs full test suite)
5. **Code Quality**: `make lint` (linting), `make format` (formatting)
6. **Security**: `make security` (bandit + safety scans)
7. **Full CI**: `make ci-local` (runs all checks locally)

## Troubleshooting

### CLI Import Issues
If you encounter import errors with the CLI:
```bash
# Reinstall the package
make clean
make install-cli

# Or manually
pip uninstall delivery-bot -y
pip install -e .

# Use the module approach instead:
python -m cli.cli --help
```

### API Connection Issues
```bash
# Check if API is running
python -m cli.cli status

# Check API health
curl http://localhost:8080/health
```


## Notes

- All timestamps are in ISO 8601 format (UTC)
- Pipeline IDs and Run IDs are UUID4 strings
- The API returns HTTP 202 Accepted for pipeline triggers (asynchronous execution)
- GitHub integration automatically creates workflows via Pull Requests when enabled
- Step validation ensures required fields are present based on step type
- Timeout values are in seconds (1-3600 range)
- The `continue_on_error` flag allows pipelines to continue even if individual steps fail
- CLI provides rich, colored output for better user experience
- All CLI commands include comprehensive error handling and user-friendly messages
