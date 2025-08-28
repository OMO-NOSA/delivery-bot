"""
Pipeline Execution Engine for Delivery-Bot API.

This module handles the asynchronous execution of CI/CD pipelines. It provides
simulation of real pipeline steps (build, test, deploy) with proper logging,
status tracking, and error handling.

The execution engine:
- Runs pipelines asynchronously without blocking the API
- Simulates realistic execution times for different step types
- Provides detailed logging throughout execution
- Updates run status and progress in real-time
- Handles errors gracefully with proper cleanup

Functions:
    simulate_step: Execute a single pipeline step with simulation
    run_pipeline: Orchestrate complete pipeline execution

Author: Nosa Omorodion
Version: 0.1.0
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from .models import Pipeline, Run, RunStatus, Step, StepType
from .storage import db

logger = logging.getLogger("cicd")


async def simulate_step(run: Run, step: Step, index: int) -> None:
    """
    Simulate execution of a single pipeline step.

    Executes one step of a pipeline with realistic timing and logging.
    Different step types have different execution patterns and durations.

    The step execution process:
    1. Updates the run's current_step index
    2. Logs the step start
    3. Simulates step-specific work with appropriate delays
    4. Logs completion or error details
    5. Updates the run in storage after each log message

    Args:
        run (Run): The run instance being executed
        step (Step): The step configuration to execute
        index (int): Zero-based index of this step in the pipeline

    Raises:
        ValueError: If the step type is unknown/unsupported

    Step Types:
        - run: Executes shell commands (1 second simulation)
        - build: Builds and pushes Docker images (1.5 seconds simulation)
        - deploy: Applies Kubernetes manifests (1 second simulation)

    Note:
        This is a simulation for demo purposes. In a real implementation,
        this would execute actual commands, Docker builds, etc.
    """

    async def log(msg: str) -> None:
        """Add a log message and update the run in storage."""
        run.logs.append(msg)
        db.update_run(run.id, run)

    # Update current step and log start
    run.current_step = index
    await log(f"[step {index+1}] Starting '{step.name}' of type '{step.type.value}'")

    if step.type == StepType.run:
        # Simulate shell command execution
        await log(f"Running shell command: {step.command!r}")
        await asyncio.sleep(1.0)  # Simulate command execution time
        await log("Command finished with exit code 0")

    elif step.type == StepType.build:
        # Simulate Docker image build and push
        dockerfile = step.dockerfile or "Dockerfile"
        ecr_repo = step.ecr_repo or "ecr://example"
        await log(f"Building Docker image from {dockerfile} and pushing to {ecr_repo}")
        await asyncio.sleep(1.5)  # Build steps take longer
        await log("Image built and pushed successfully")
        logger.info("build_step_complete")  # Additional structured logging

    elif step.type == StepType.deploy:
        # Simulate Kubernetes deployment
        manifest = step.manifest or "k8s/deploy.yaml"
        await log(f"Applying manifest {manifest} to cluster")
        await asyncio.sleep(1.0)  # Simulate deployment time
        await log("Deployment applied")

    else:
        # Handle unknown step types
        await log("Unknown step type encountered")
        raise ValueError("Unknown step type")


async def run_pipeline(pipeline: Pipeline, run: Run) -> None:
    """
    Execute a complete pipeline asynchronously.

    Orchestrates the execution of all steps in a pipeline, managing the
    overall run lifecycle from start to completion. Handles errors
    gracefully and ensures proper cleanup.

    Execution Flow:
    1. Set run status to 'running' and record start time
    2. Execute each step in sequence
    3. Set final status based on success/failure
    4. Record completion time
    5. Update the run in storage

    Args:
        pipeline (Pipeline): The pipeline configuration to execute
        run (Run): The run instance to track execution

    Status Transitions:
        - pending -> running (at start)
        - running -> succeeded (if all steps complete successfully)
        - running -> failed (if any step fails or raises exception)

    Error Handling:
        - Exceptions during step execution are caught and logged
        - Run status is set to 'failed' with error details in logs
        - Completion timestamp is always set in the finally block

    Note:
        This function runs asynchronously and should be scheduled as a
        background task. It does not return any value but updates the
        run object in storage throughout execution.
    """
    # Initialize run execution
    run.status = RunStatus.running
    run.started_at = datetime.utcnow()
    db.update_run(run.id, run)

    try:
        # Execute each step in sequence
        for idx, step in enumerate(pipeline.steps):
            await simulate_step(run, step, idx)

        # Mark as successful if all steps completed
        run.status = RunStatus.succeeded

    except Exception as exc:
        # Handle any errors during execution
        run.logs.append(f"ERROR: {exc}")
        run.status = RunStatus.failed

    finally:
        # Always set completion time and update storage
        run.finished_at = datetime.utcnow()
        db.update_run(run.id, run)
