
from __future__ import annotations
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List
from .config import settings
from .models import Pipeline, Run, RunStatus, Step
from .storage import db
import asyncio
import logging, sys, time
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI(title=settings.api_title, version=settings.api_version)

# Logging
logger = logging.getLogger("cicd")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        status = getattr(locals().get('response', None), 'status_code', 500)
        logger.info("request", extra={"props": {"method": request.method, "path": request.url.path, "status": status, "duration_ms": int(duration_ms)}})

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

class CreatePipelineRequest(BaseModel):
    name: str
    repo_url: HttpUrl
    branch: str = "main"
    steps: List[Step]

@app.post("/pipelines", response_model=Pipeline, status_code=201)
def create_pipeline(req: CreatePipelineRequest):
    p = Pipeline(name=req.name, repo_url=req.repo_url, branch=req.branch, steps=req.steps)
    return db.create_pipeline(p)

@app.get("/pipelines", response_model=List[Pipeline])
def list_pipelines():
    return db.list_pipelines()

@app.get("/pipelines/{pipeline_id}", response_model=Pipeline)
def get_pipeline(pipeline_id: str):
    p = db.get_pipeline(pipeline_id)
    if not p:
        raise HTTPException(404, "Pipeline not found")
    return p

@app.put("/pipelines/{pipeline_id}", response_model=Pipeline)
def update_pipeline(pipeline_id: str, req: CreatePipelineRequest):
    current = db.get_pipeline(pipeline_id)
    if not current:
        raise HTTPException(404, "Pipeline not found")
    updated = Pipeline(id=pipeline_id, name=req.name, repo_url=req.repo_url, branch=req.branch, steps=req.steps, created_at=current.created_at)
    saved = db.update_pipeline(pipeline_id, updated)
    assert saved
    return saved

@app.delete("/pipelines/{pipeline_id}", status_code=204)
def delete_pipeline(pipeline_id: str):
    ok = db.delete_pipeline(pipeline_id)
    if not ok:
        raise HTTPException(404, "Pipeline not found")
    return

class TriggerResponse(BaseModel):
    run_id: str
    status: RunStatus

@app.post("/pipelines/{pipeline_id}/trigger", response_model=TriggerResponse, status_code=202)
def trigger_pipeline(pipeline_id: str):
    p = db.get_pipeline(pipeline_id)
    if not p:
        raise HTTPException(404, "Pipeline not found")

    run = Run(pipeline_id=pipeline_id)
    db.create_run(run)

    # Optional GitHub Actions dispatch
    if settings.github_owner and settings.github_repo and settings.github_token:
        try:
            from .gh import trigger_github_workflow
            code = trigger_github_workflow(
                settings.github_owner,
                settings.github_repo,
                settings.github_workflow,
                settings.github_ref,
                settings.github_token,
                inputs={"pipeline_id": p.id, "repo_url": str(p.repo_url), "branch": p.branch},
            )
            run.logs.append(f"Triggered GitHub Actions workflow with status code {code}")
        except Exception as e:
            run.logs.append(f"Warning: failed to trigger GitHub workflow: {e}")

    # Run asynchronously on app loop
    from .pipeline_runner import run_pipeline
    loop = asyncio.get_event_loop()
    loop.create_task(run_pipeline(p, run))

    return TriggerResponse(run_id=run.id, status=run.status)

@app.get("/runs/{run_id}", response_model=Run)
def get_run(run_id: str):
    r = db.get_run(run_id)
    if not r:
        raise HTTPException(404, "Run not found")
    return r

# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("validation_error", extra={"props": {"path": request.url.path, "errors": exc.errors()}})
    return JSONResponse(status_code=422, content={"detail": exc.errors()})

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.warning("http_exception", extra={"props": {"path": request.url.path, "status": exc.status_code, "detail": str(exc.detail)}})
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_exception")
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
