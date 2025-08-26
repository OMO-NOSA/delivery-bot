
from __future__ import annotations
import asyncio
import logging
from .models import Pipeline, Run, RunStatus, StepType
from .storage import db
from datetime import datetime

logger = logging.getLogger('cicd')

async def simulate_step(run: Run, step, index: int) -> None:
    async def log(msg: str) -> None:
        run.logs.append(msg)
        db.update_run(run.id, run)

    run.current_step = index
    await log(f"[step {index+1}] Starting '{step.name}' of type '{step.type}'")

    if step.type == StepType.run:
        await log(f"Running shell command: {step.command!r}")
        await asyncio.sleep(1.0)
        await log("Command finished with exit code 0")
    elif step.type == StepType.build:
        await log(f"Building Docker image from {step.dockerfile or 'Dockerfile'} and pushing to {step.ecr_repo or 'ecr://example'}")
        await asyncio.sleep(1.5)
        await log("Image built and pushed successfully")
        logger.info('build_step_complete')
    elif step.type == StepType.deploy:
        await log(f"Applying manifest {step.manifest or 'k8s/deploy.yaml'} to cluster")
        await asyncio.sleep(1.0)
        await log("Deployment applied")
    else:
        await log("Unknown step type encountered")
        raise ValueError("Unknown step type")

async def run_pipeline(pipeline: Pipeline, run: Run) -> None:
    run.status = RunStatus.running
    run.started_at = datetime.utcnow()
    db.update_run(run.id, run)

    try:
        for idx, step in enumerate(pipeline.steps):
            await simulate_step(run, step, idx)
        run.status = RunStatus.succeeded
    except Exception as exc:
        run.logs.append(f"ERROR: {exc}")
        run.status = RunStatus.failed
    finally:
        run.finished_at = datetime.utcnow()
        db.update_run(run.id, run)
