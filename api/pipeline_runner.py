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
Classes:
    PipelineExecutor: Main executor class with dependency injection
Author: Nosa Omorodion
Version: 0.2.0
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from .models import Pipeline, Run, RunStatus, Step, StepType
from .storage import db

# Default logger for backward compatibility
default_logger = logging.getLogger("cicd")


class LoggerInterface(ABC):
    """Abstract logger interface for dependency injection."""

    @abstractmethod
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        pass

    @abstractmethod
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        pass

    @abstractmethod
    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        pass

    @abstractmethod
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        pass


class StandardLogger(LoggerInterface):
    """Standard logger implementation using Python's logging module."""

    def __init__(self, logger_name: str = "cicd"):
        self.logger = logging.getLogger(logger_name)

    def info(self, message: str, **kwargs: Any) -> None:
        self.logger.info(message, extra=kwargs if kwargs else None)

    def warning(self, message: str, **kwargs: Any) -> None:
        self.logger.warning(message, extra=kwargs if kwargs else None)

    def error(self, message: str, **kwargs: Any) -> None:
        self.logger.error(message, extra=kwargs if kwargs else None)

    def debug(self, message: str, **kwargs: Any) -> None:
        self.logger.debug(message, extra=kwargs if kwargs else None)


class PipelineExecutor:
    """Main pipeline executor with dependency injection and improved error handling."""

    def __init__(
        self, logger: Optional[LoggerInterface] = None, storage: Optional[Any] = None
    ):
        """
        Initialize pipeline executor.
        Args:
            logger: Logger implementation (defaults to StandardLogger)
            storage: Storage implementation (defaults to global db)
        """
        self.logger = logger or StandardLogger()
        self.storage = storage or db
        self.logger.info("Pipeline executor initialized")

    def validate_pipeline(self, pipeline: Pipeline) -> None:
        """
        Validate pipeline configuration.
        Args:
            pipeline: Pipeline to validate
        Raises:
            ValueError: If pipeline is invalid
        """
        if not pipeline:
            raise ValueError("Pipeline cannot be None")
        if not pipeline.steps:
            raise ValueError("Pipeline must have at least one step")
        if not pipeline.id:
            raise ValueError("Pipeline must have an ID")
        # Validate each step
        for i, step in enumerate(pipeline.steps):
            if not step.name:
                raise ValueError(f"Step {i} must have a name")
            if not step.type:
                raise ValueError(f"Step {i} must have a type")
            # Validate step-specific fields
            if step.type == StepType.run and not step.command:
                raise ValueError(f"Run step {i} must have a command")
            if step.type == StepType.build and not step.dockerfile:
                self.logger.warning(
                    f"Build step {i} has no dockerfile specified, using default"
                )
            if step.type == StepType.deploy and not step.manifest:
                self.logger.warning(
                    f"Deploy step {i} has no manifest specified, using default"
                )

    def validate_run(self, run: Run) -> None:
        """
        Validate run configuration.
        Args:
            run: Run to validate
        Raises:
            ValueError: If run is invalid
        """
        if not run:
            raise ValueError("Run cannot be None")
        if not run.id:
            raise ValueError("Run must have an ID")
        if not run.pipeline_id:
            raise ValueError("Run must have a pipeline ID")

    async def simulate_step(self, run: Run, step: Step, index: int) -> None:
        """
        Simulate execution of a single pipeline step.
        Args:
            run: The run instance being executed
            step: The step configuration to execute
            index: Zero-based index of this step in the pipeline
        """

        async def log(msg: str) -> None:
            """Add a log message and update the run in storage."""
            run.logs.append(msg)
            self.storage.update_run(run.id, run)

        try:
            # Update current step and log start
            run.current_step = index
            await log(
                f"[step {index + 1}] Starting '{step.name}' of type '{step.type.value}'"
            )
            self.logger.info(
                f"Executing step {index + 1}: {step.name}",
                extra={
                    "step_name": step.name,
                    "step_type": step.type.value,
                    "step_index": index,
                    "pipeline_id": run.pipeline_id,
                    "run_id": run.id,
                },
            )
            if step.type == StepType.run:
                # Simulate shell command execution
                await log(f"Running shell command: {step.command!r}")
                await asyncio.sleep(1.0)  # Simulate command execution time
                await log("Command finished with exit code 0")
            elif step.type == StepType.build:
                # Simulate Docker image build and push
                dockerfile = step.dockerfile or "Dockerfile"
                ecr_repo = step.ecr_repo or "ecr://example"
                await log(
                    f"Building Docker image from {dockerfile} and pushing to {ecr_repo}"
                )
                await asyncio.sleep(1.5)  # Build steps take longer
                await log("Image built and pushed successfully")
            elif step.type == StepType.deploy:
                # Simulate Kubernetes deployment
                manifest = step.manifest or "k8s/deploy.yaml"
                await log(f"Applying manifest {manifest} to cluster")
                await asyncio.sleep(1.0)  # Simulate deployment time
                await log("Deployment applied")
            else:
                # Handle unknown step types
                await log("Unknown step type encountered")
                raise ValueError(f"Unknown step type: {step.type}")
            await log(f"Step '{step.name}' completed successfully")
        except Exception as e:
            error_msg = f"Step '{step.name}' failed: {e}"
            await log(error_msg)
            self.logger.error(
                error_msg,
                extra={
                    "step_name": step.name,
                    "step_type": step.type.value,
                    "step_index": index,
                    "pipeline_id": run.pipeline_id,
                    "run_id": run.id,
                    "error": str(e),
                },
            )
            raise

    async def run_pipeline(self, pipeline: Pipeline, run: Run) -> None:
        """
        Execute a complete pipeline asynchronously.
        Args:
            pipeline: The pipeline configuration to execute
            run: The run instance to track execution
        """
        # Validate inputs
        self.validate_pipeline(pipeline)
        self.validate_run(run)
        # Initialize run execution
        run.status = RunStatus.running
        run.started_at = datetime.utcnow()
        self.storage.update_run(run.id, run)
        self.logger.info(
            "Pipeline execution started",
            extra={
                "pipeline_id": pipeline.id,
                "run_id": run.id,
                "total_steps": len(pipeline.steps),
            },
        )
        try:
            # Execute each step in sequence
            for idx, step in enumerate(pipeline.steps):
                await self.simulate_step(run, step, idx)
            # Mark as successful if all steps completed
            run.status = RunStatus.succeeded
            self.logger.info(
                "Pipeline execution succeeded",
                extra={
                    "pipeline_id": pipeline.id,
                    "run_id": run.id,
                    "total_steps": len(pipeline.steps),
                },
            )
        except Exception as exc:
            # Handle any errors during execution
            run.logs.append(f"ERROR: {exc}")
            run.status = RunStatus.failed
            self.logger.error(
                f"Pipeline execution failed: {exc}",
                extra={"pipeline_id": pipeline.id, "run_id": run.id, "error": str(exc)},
            )
        finally:
            # Always set completion time and update storage
            run.finished_at = datetime.utcnow()
            self.storage.update_run(run.id, run)
            self.logger.info(
                "Pipeline execution completed",
                extra={
                    "pipeline_id": pipeline.id,
                    "run_id": run.id,
                    "status": run.status.value,
                },
            )


# Backward compatibility functions
async def simulate_step(run: Run, step: Step, index: int) -> None:
    """
    Backward compatibility function for simulating a single step.
    Args:
        run: The run instance being executed
        step: The step configuration to execute
        index: Zero-based index of this step in the pipeline
    """
    executor = PipelineExecutor()
    await executor.simulate_step(run, step, index)


async def run_pipeline(pipeline: Pipeline, run: Run) -> None:
    """
    Backward compatibility function for running a complete pipeline.
    Args:
        pipeline: The pipeline configuration to execute
        run: The run instance to track execution
    """
    executor = PipelineExecutor()
    await executor.run_pipeline(pipeline, run)
