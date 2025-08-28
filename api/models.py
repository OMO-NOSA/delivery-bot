
"""
Data Models for Delivery-Bot API.

This module defines the Pydantic models used throughout the Delivery-Bot API
for data validation, serialization, and API documentation. It includes models
for pipeline configuration, execution steps, runs, and their various states.

The models provide:
- Type-safe data structures with automatic validation
- JSON serialization/deserialization
- API documentation through field descriptions
- Cross-field validation for complex business rules

Classes:
    StepType: Enumeration of supported pipeline step types
    Step: Configuration for individual pipeline steps
    Pipeline: Complete pipeline configuration and metadata
    RunStatus: Enumeration of pipeline run states
    Run: Pipeline execution instance with status and logs

Author: Nosa Omorodion
Version: 0.1.0
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl, model_validator


class StepType(str, Enum):
    """
    Enumeration of supported pipeline step types.

    Defines the different types of steps that can be included in a pipeline.
    Each step type has specific requirements and behavior during execution.

    Attributes:
        run: Execute shell commands or scripts
        build: Build and push Docker images to ECR
        deploy: Deploy applications using Kubernetes manifests
    """

    run = "run"
    build = "build"
    deploy = "deploy"


class Step(BaseModel):
    """
    Configuration for a single pipeline step.

    Represents one step in a pipeline's execution sequence. The step type
    determines which fields are required and how the step will be executed.

    Attributes:
        name (str): Human-readable name for the step
        type (StepType): Type of step (run, build, or deploy)
        command (Optional[str]): Shell command for 'run' steps
        dockerfile (Optional[str]): Path to Dockerfile for 'build' steps
        ecr_repo (Optional[str]): ECR repository name for 'build' steps
        manifest (Optional[str]): Kubernetes manifest path for 'deploy' steps
        timeout_seconds (int): Maximum execution time (default: 300, max: 3600)
        continue_on_error (bool): Whether to continue pipeline if step fails

    Validation:
        - 'run' steps require a command
        - 'build' steps require both dockerfile and ecr_repo
        - 'deploy' steps require a manifest
        - timeout_seconds must be between 1 and 3600 seconds
    """

    name: str = Field(..., description="Name of the step")
    type: StepType
    command: Optional[str] = Field(
        None, description="Shell command to run for 'run' steps"
    )
    dockerfile: Optional[str] = Field(
        None, description="Path to Dockerfile for 'build' steps"
    )
    ecr_repo: Optional[str] = Field(
        None, description="ECR repo name for 'build' steps"
    )
    manifest: Optional[str] = Field(
        None, description="Path to k8s manifest for 'deploy' steps"
    )
    timeout_seconds: int = Field(300, ge=1, le=3600)
    continue_on_error: bool = False

    @model_validator(mode="after")
    def _validate_by_type(self):
        """
        Validate step configuration based on step type.

        Ensures that required fields are present for each step type and
        raises detailed error messages for missing required fields.

        Returns:
            Step: The validated step instance

        Raises:
            ValueError: If required fields are missing for the step type
        """
        if self.type == StepType.run and not self.command:
            raise ValueError("`command` is required for step type 'run'")
        if self.type == StepType.build and (not self.dockerfile or not self.ecr_repo):
            raise ValueError(
                "`dockerfile` and `ecr_repo` are required for step type 'build'"
            )
        if self.type == StepType.deploy and not self.manifest:
            raise ValueError("`manifest` is required for step type 'deploy'")
        return self

class Pipeline(BaseModel):
    """
    Complete pipeline configuration and metadata.

    Represents a CI/CD pipeline with all its configuration, steps, and metadata.
    Pipelines are the primary entity that users create and manage through the API.

    Attributes:
        id (str): Unique identifier, automatically generated
        name (str): Human-readable name for the pipeline
        repo_url (HttpUrl): Git repository URL to clone and build from
        branch (str): Git branch to use (defaults to "main")
        steps (List[Step]): Ordered list of steps to execute
        created_at (datetime): Timestamp when pipeline was created
        updated_at (datetime): Timestamp when pipeline was last modified

    Note:
        The id is automatically generated using UUID4 when creating new pipelines.
        Timestamps are automatically set and updated by the storage layer.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    repo_url: HttpUrl
    branch: str = "main"
    steps: List[Step] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class RunStatus(str, Enum):
    """
    Enumeration of possible pipeline run states.

    Defines the lifecycle states a pipeline run can be in, from initial
    creation through completion or failure.

    Attributes:
        pending: Run created but not yet started
        running: Run is currently executing
        succeeded: Run completed successfully
        failed: Run completed with errors
        cancelled: Run was cancelled before completion

    Note:
        State transitions typically follow: pending -> running -> (succeeded|failed|cancelled)
    """

    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class Run(BaseModel):
    """
    Pipeline execution instance with status and logs.

    Represents a single execution of a pipeline, tracking its progress,
    status, timing, and detailed logs throughout the execution process.

    Attributes:
        id (str): Unique identifier, automatically generated
        pipeline_id (str): ID of the pipeline being executed
        status (RunStatus): Current execution status (default: pending)
        started_at (Optional[datetime]): When execution began
        finished_at (Optional[datetime]): When execution completed
        current_step (Optional[int]): Index of currently executing step
        logs (List[str]): Detailed execution logs and messages

    Lifecycle:
        1. Created with status 'pending'
        2. Status changes to 'running' when execution begins
        3. current_step tracks progress through pipeline steps
        4. logs accumulate messages during execution
        5. Status changes to 'succeeded', 'failed', or 'cancelled' when done
        6. finished_at timestamp is set upon completion

    Note:
        The id is automatically generated using UUID4 when creating new runs.
        Timing fields are managed by the pipeline runner during execution.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str
    status: RunStatus = RunStatus.pending
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    current_step: Optional[int] = None
    logs: List[str] = Field(default_factory=list)
