
from __future__ import annotations
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
import uuid

class StepType(str, Enum):
    run = "run"
    build = "build"
    deploy = "deploy"

class Step(BaseModel):
    name: str = Field(..., description="Name of the step")
    type: StepType
    command: Optional[str] = Field(None, description="Shell command to run for 'run' steps")
    dockerfile: Optional[str] = Field(None, description="Path to Dockerfile for 'build' steps")
    ecr_repo: Optional[str] = Field(None, description="ECR repo name for 'build' steps")
    manifest: Optional[str] = Field(None, description="Path to k8s manifest for 'deploy' steps")
    timeout_seconds: int = Field(300, ge=1, le=3600)
    continue_on_error: bool = False

    from pydantic import model_validator
    @model_validator(mode="after")
    def _validate_by_type(self):
        if self.type == StepType.run and not self.command:
            raise ValueError("`command` is required for step type 'run'")
        if self.type == StepType.build and (not self.dockerfile or not self.ecr_repo):
            raise ValueError("`dockerfile` and `ecr_repo` are required for step type 'build'")
        if self.type == StepType.deploy and not self.manifest:
            raise ValueError("`manifest` is required for step type 'deploy'")
        return self

class Pipeline(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    repo_url: HttpUrl
    branch: str = "main"
    steps: List[Step] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class RunStatus(str, Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"

class Run(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pipeline_id: str
    status: RunStatus = RunStatus.pending
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    current_step: Optional[int] = None
    logs: List[str] = Field(default_factory=list)
