
"""
Delivery-Bot API Main Module.

This module provides a FastAPI-based REST API for managing CI/CD pipelines.
It includes endpoints for creating, updating, deleting, and triggering pipelines,
as well as monitoring pipeline runs.

The API supports the following operations:
- Pipeline CRUD operations (Create, Read, Update, Delete)
- Pipeline execution triggering with background task processing
- Run status monitoring and log retrieval
- Optional GitHub Actions integration for workflow dispatch

Dependencies:
    - FastAPI for the web framework
    - Pydantic for data validation
    - asyncio for asynchronous pipeline execution

Author: Nosa Omorodion
Version: 0.1.0
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from typing import List

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import settings
from .models import Pipeline, Run, RunStatus, Step
from .storage import db

# Initialize FastAPI application with configuration from settings
app = FastAPI(title=settings.api_title, version=settings.api_version)

# Configure logging
logger = logging.getLogger("cicd")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log HTTP requests with timing information.

    Middleware that logs all incoming HTTP requests including method, path,
    status code, and response time. This provides observability for API usage
    and performance monitoring.

    Args:
        request: The incoming HTTP request
        call_next: The next middleware/handler in the chain

    Returns:
        HTTP response from the next handler
    """
    start = time.perf_counter()
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        status = getattr(locals().get('response', None), 'status_code', 500)
        logger.info(
            "request",
            extra={
                "props": {
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": int(duration_ms)
                }
            }
        )


# Configure CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """
    Health check endpoint.

    Returns a simple status indicator to verify the API is running.
    This endpoint is typically used by load balancers, monitoring systems,
    and container orchestrators to check service health.

    Returns:
        dict: Simple status object with "ok" status
    """
    return {"status": "ok"}


class CreatePipelineRequest(BaseModel):
    """
    Request model for creating or updating pipelines.

    Defines the required and optional fields for pipeline creation/updates.
    This model is used for both POST (create) and PUT (update) operations.

    Attributes:
        name (str): Human-readable name for the pipeline
        repo_url (HttpUrl): Git repository URL to clone and build from
        branch (str): Git branch to use (defaults to "main")
        steps (List[Step]): List of steps to execute in the pipeline
    """

    name: str
    repo_url: HttpUrl
    branch: str = "main"
    steps: List[Step]

@app.post("/pipelines", response_model=Pipeline, status_code=201)
def create_pipeline(req: CreatePipelineRequest):
    """
    Create a new pipeline.

    Creates a new CI/CD pipeline with the specified configuration.
    The pipeline will be assigned a unique ID and timestamp.

    Args:
        req (CreatePipelineRequest): Pipeline configuration including name,
            repository URL, branch, and build/deploy steps

    Returns:
        Pipeline: The created pipeline object with generated ID and timestamps

    Raises:
        HTTPException: 422 if validation fails for any field or step configuration
    """
    pipeline = Pipeline(
        name=req.name,
        repo_url=req.repo_url,
        branch=req.branch,
        steps=req.steps
    )
    
    created_pipeline = db.create_pipeline(pipeline)
    
    # GitHub Actions integration - create workflow and merge PR automatically
    if settings.github_token:
        try:
            from .gh import create_and_merge_workflow_pr
            from urllib.parse import urlparse

            # Extract owner and repo from user's repository URL
            parsed_url = urlparse(str(req.repo_url))
            if parsed_url.hostname == "github.com":
                path_parts = parsed_url.path.strip("/").split("/")
                if len(path_parts) >= 2:
                    user_owner = path_parts[0]
                    user_repo = path_parts[1]
                    
                    # Use a unique workflow name for each pipeline
                    workflow_name = f"pipeline-{created_pipeline.id}.yml"
                    
                    # Create the workflow and merge the PR automatically
                    if settings.github_auto_create_workflow:
                        logger.info(f"Attempting to create GitHub workflow for pipeline {created_pipeline.id} in {user_owner}/{user_repo}")
                        logger.info(f"Using branch: {req.branch}, workflow name: {workflow_name}")
                        logger.info(f"Pipeline has {len(req.steps)} steps")
                        
                        workflow_created = create_and_merge_workflow_pr(
                            user_owner,
                            user_repo,
                            workflow_name,
                            req.branch,  # Use user's specified branch
                            settings.github_token,
                            created_pipeline.id,
                            req.steps  # Pass the pipeline steps for dynamic workflow generation
                        )
                        
                        if workflow_created:
                            logger.info(f"GitHub Actions workflow created and merged for pipeline {created_pipeline.id} in {user_owner}/{user_repo}")
                        else:
                            logger.warning(f"Failed to create/merge GitHub Actions workflow for pipeline {created_pipeline.id}")
                    else:
                        logger.info("GitHub workflow auto-creation is disabled")
                else:
                    logger.warning(f"Invalid GitHub repository URL format: {req.repo_url}")
            else:
                logger.warning(f"Repository is not on GitHub: {req.repo_url}")
                
        except Exception as e:
            logger.warning(f"GitHub integration failed for pipeline {created_pipeline.id}: {e}")
    
    return created_pipeline


@app.get("/pipelines", response_model=List[Pipeline])
def list_pipelines():
    """
    List all pipelines.

    Returns a list of all pipelines currently stored in the system.
    Pipelines are returned in the order they were created.

    Returns:
        List[Pipeline]: List of all pipeline objects
    """
    return db.list_pipelines()


@app.get("/pipelines/{pipeline_id}", response_model=Pipeline)
def get_pipeline(pipeline_id: str):
    """
    Get a specific pipeline by ID.

    Retrieves the configuration and metadata for a single pipeline.

    Args:
        pipeline_id (str): Unique identifier of the pipeline to retrieve

    Returns:
        Pipeline: The requested pipeline object

    Raises:
        HTTPException: 404 if the pipeline with the given ID is not found
    """
    pipeline = db.get_pipeline(pipeline_id)
    if not pipeline:
        raise HTTPException(404, "Pipeline not found")
    return pipeline


@app.put("/pipelines/{pipeline_id}", response_model=Pipeline)
def update_pipeline(pipeline_id: str, req: CreatePipelineRequest):
    """
    Update an existing pipeline.

    Updates the configuration of an existing pipeline while preserving
    its ID and creation timestamp. The updated_at timestamp will be
    refreshed to the current time.

    Args:
        pipeline_id (str): Unique identifier of the pipeline to update
        req (CreatePipelineRequest): New pipeline configuration

    Returns:
        Pipeline: The updated pipeline object

    Raises:
        HTTPException: 404 if the pipeline with the given ID is not found
        HTTPException: 422 if validation fails for any field or step configuration
    """
    current = db.get_pipeline(pipeline_id)
    if not current:
        raise HTTPException(404, "Pipeline not found")

    updated = Pipeline(
        id=pipeline_id,
        name=req.name,
        repo_url=req.repo_url,
        branch=req.branch,
        steps=req.steps,
        created_at=current.created_at
    )
    saved = db.update_pipeline(pipeline_id, updated)
    assert saved is not None, "Failed to update pipeline"
    return saved


@app.delete("/pipelines/{pipeline_id}", status_code=204)
def delete_pipeline(pipeline_id: str):
    """
    Delete a pipeline.

    Permanently removes a pipeline from the system. This operation
    cannot be undone. Associated runs may be preserved.

    Args:
        pipeline_id (str): Unique identifier of the pipeline to delete

    Returns:
        None: No content returned on successful deletion

    Raises:
        HTTPException: 404 if the pipeline with the given ID is not found
    """
    success = db.delete_pipeline(pipeline_id)
    if not success:
        raise HTTPException(404, "Pipeline not found")

class TriggerResponse(BaseModel):
    """
    Response model for pipeline trigger requests.

    Contains the essential information returned when a pipeline is triggered,
    including the run ID for tracking and the initial status.

    Attributes:
        run_id (str): Unique identifier for the created run
        status (RunStatus): Initial status of the run (typically "pending")
    """

    run_id: str
    status: RunStatus


@app.post("/pipelines/{pipeline_id}/trigger", response_model=TriggerResponse, status_code=202)
def trigger_pipeline(pipeline_id: str):
    """
    Trigger execution of a pipeline.

    Creates a new run for the specified pipeline and starts its execution
    asynchronously. If GitHub integration is configured, also dispatches
    a GitHub Actions workflow.

    The pipeline execution runs in the background, and the client can poll
    the run status using the returned run_id.

    Args:
        pipeline_id (str): Unique identifier of the pipeline to trigger

    Returns:
        TriggerResponse: Contains the run ID and initial status

    Raises:
        HTTPException: 404 if the pipeline with the given ID is not found

    Note:
        The response is returned immediately (status 202 Accepted) while
        the actual pipeline execution continues in the background.
    """
    pipeline = db.get_pipeline(pipeline_id)
    if not pipeline:
        raise HTTPException(404, "Pipeline not found")

    # Create a new run for this pipeline
    run = Run(pipeline_id=pipeline_id)
    db.create_run(run)

    # Debug: Log GitHub settings for troubleshooting
    logger.info(
        "GitHub integration debug",
        extra={
            "props": {
                "github_owner": settings.github_owner,
                "github_repo": settings.github_repo,
                "github_token": "***MASKED***" if settings.github_token else None,
                "github_workflow": settings.github_workflow,
                "github_ref": settings.github_ref,
                "integration_enabled": bool(settings.github_owner and settings.github_repo and settings.github_token)
            }
        }
    )

    # GitHub Actions integration - trigger workflow if it exists
    if settings.github_token:
        try:
            from .gh import trigger_github_workflow, workflow_exists
            from urllib.parse import urlparse

            # Extract owner and repo from pipeline's repository URL
            parsed_url = urlparse(str(pipeline.repo_url))
            if parsed_url.hostname == "github.com":
                path_parts = parsed_url.path.strip("/").split("/")
                if len(path_parts) >= 2:
                    user_owner = path_parts[0]
                    user_repo = path_parts[1]
                    
                    # Use the pipeline-specific workflow name
                    workflow_name = f"pipeline-{pipeline.id}.yml"
                    
                    # Check if the workflow exists
                    workflow_exists_check = workflow_exists(
                        user_owner,
                        user_repo,
                        workflow_name,
                        pipeline.branch,  # Use pipeline's specified branch
                        settings.github_token
                    )
                    
                    if workflow_exists_check:
                        run.logs.append(f"GitHub Actions workflow found in {user_owner}/{user_repo}, triggering...")
                        
                        # Trigger the existing workflow
                        status_code = trigger_github_workflow(
                            user_owner,
                            user_repo,
                            workflow_name,
                            pipeline.branch,  # Use pipeline's specified branch
                            settings.github_token,
                            inputs={
                                "pipeline_id": pipeline.id,
                                "repo_url": str(pipeline.repo_url),
                                "branch": pipeline.branch,
                                "environment": "staging"
                            },
                        )
                        
                        if status_code == 204:
                            run.logs.append("GitHub Actions workflow triggered successfully")
                        else:
                            run.logs.append(f"GitHub Actions workflow trigger returned status code {status_code}")
                    else:
                        run.logs.append(f"GitHub Actions workflow not found in {user_owner}/{user_repo} - create pipeline first to generate workflow")
                else:
                    run.logs.append(f"Invalid GitHub repository URL format: {pipeline.repo_url}")
            else:
                run.logs.append(f"Repository is not on GitHub: {pipeline.repo_url}")
                
        except Exception as e:
            run.logs.append(f"GitHub integration error: {e}")
            logger.warning(f"GitHub integration failed for pipeline {pipeline.id}: {e}")

    # Start pipeline execution asynchronously
    from .pipeline_runner import run_pipeline

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(run_pipeline(pipeline, run))
    except RuntimeError:
        # No running loop, run synchronously for now
        # In a real production environment, you might want to use a task queue
        logger.warning("No running event loop, pipeline will run synchronously")
        # For now, we'll just log that the pipeline would run
        run.logs.append("Pipeline execution queued (no async context available)")

    return TriggerResponse(run_id=run.id, status=run.status)


@app.get("/runs/{run_id}", response_model=Run)
def get_run(run_id: str):
    """
    Get the status and details of a pipeline run.

    Retrieves comprehensive information about a pipeline run including
    its current status, execution logs, timing information, and any
    error details.

    Args:
        run_id (str): Unique identifier of the run to retrieve

    Returns:
        Run: Complete run object with status, logs, and metadata

    Raises:
        HTTPException: 404 if the run with the given ID is not found
    """
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run

# Exception handlers


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Handle Pydantic validation errors.

    Catches validation errors from request body parsing and parameter validation,
    logs the error details, and returns a structured error response to the client.

    Args:
        request: The HTTP request that caused the validation error
        exc: The validation error exception with detailed error information

    Returns:
        JSONResponse: 422 status with validation error details
    """
    # Convert errors to JSON-serializable format
    errors = []
    for error in exc.errors():
        error_dict = {
            "type": error.get("type"),
            "loc": error.get("loc", []),
            "msg": str(error.get("msg", "")),
            "input": str(error.get("input", "")) if error.get("input") is not None else None
        }
        # Handle context which might contain non-serializable objects
        if "ctx" in error and error["ctx"]:
            error_dict["ctx"] = {k: str(v) for k, v in error["ctx"].items()}
        errors.append(error_dict)

    logger.warning(
        "validation_error",
        extra={
            "props": {
                "path": request.url.path,
                "errors": errors
            }
        }
    )
    return JSONResponse(status_code=422, content={"detail": errors})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """
    Handle HTTP exceptions (4xx and 5xx errors).

    Catches HTTP exceptions like 404 Not Found, logs the error,
    and returns a properly formatted error response.

    Args:
        request: The HTTP request that caused the exception
        exc: The HTTP exception with status code and detail message

    Returns:
        JSONResponse: Response with the original status code and error detail
    """
    logger.warning(
        "http_exception",
        extra={
            "props": {
                "path": request.url.path,
                "status": exc.status_code,
                "detail": str(exc.detail)
            }
        }
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions.

    Catches any unhandled exceptions that occur during request processing,
    logs the full exception traceback, and returns a generic error response
    to avoid exposing internal details to clients.

    Args:
        request: The HTTP request that caused the exception
        exc: The unhandled exception

    Returns:
        JSONResponse: 500 status with generic error message
    """
    logger.exception("unhandled_exception")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"}
    )
