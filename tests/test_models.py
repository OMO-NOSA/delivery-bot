from datetime import datetime
import pytest
from pydantic import ValidationError
from api.models import Pipeline, Run, RunStatus, Step, StepType
class TestStep:
    """Test Step model validation and edge cases."""
    def test_valid_run_step(self):
        """Test creating a valid run step."""
        step = Step(name="test-step", type=StepType.run, command="echo hello")
        assert step.name == "test-step"
        assert step.type == StepType.run
        assert step.command == "echo hello"
        assert step.timeout_seconds == 300  # default
        assert step.continue_on_error is False  # default
    def test_valid_build_step(self):
        """Test creating a valid build step."""
        step = Step(
            name="build-step",
            type=StepType.build,
            dockerfile="Dockerfile.prod",
            ecr_repo="my-app/backend",
        )
        assert step.type == StepType.build
        assert step.dockerfile == "Dockerfile.prod"
        assert step.ecr_repo == "my-app/backend"
    def test_valid_deploy_step(self):
        """Test creating a valid deploy step."""
        step = Step(
            name="deploy-step", type=StepType.deploy, manifest="k8s/deployment.yaml"
        )
        assert step.type == StepType.deploy
        assert step.manifest == "k8s/deployment.yaml"
    def test_run_step_missing_command_fails(self):
        """Test that run step without command fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            Step(name="bad-run", type=StepType.run)
        error = exc_info.value.errors()[0]
        assert "`command` is required for step type 'run'" in str(error["ctx"])
    def test_build_step_missing_dockerfile_fails(self):
        """Test that build step without dockerfile fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            Step(name="bad-build", type=StepType.build, ecr_repo="repo")
        error = exc_info.value.errors()[0]
        assert "`dockerfile` and `ecr_repo` are required for step type 'build'" in str(
            error["ctx"]
        )
    def test_build_step_missing_ecr_repo_fails(self):
        """Test that build step without ecr_repo fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            Step(name="bad-build", type=StepType.build, dockerfile="Dockerfile")
        error = exc_info.value.errors()[0]
        assert "`dockerfile` and `ecr_repo` are required for step type 'build'" in str(
            error["ctx"]
        )
    def test_deploy_step_missing_manifest_fails(self):
        """Test that deploy step without manifest fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            Step(name="bad-deploy", type=StepType.deploy)
        error = exc_info.value.errors()[0]
        assert "`manifest` is required for step type 'deploy'" in str(error["ctx"])
    def test_timeout_bounds(self):
        """Test timeout_seconds field bounds."""
        # Valid timeout
        step = Step(name="test", type=StepType.run, command="echo", timeout_seconds=600)
        assert step.timeout_seconds == 600
        # Too low timeout
        with pytest.raises(ValidationError):
            Step(name="test", type=StepType.run, command="echo", timeout_seconds=0)
        # Too high timeout
        with pytest.raises(ValidationError):
            Step(name="test", type=StepType.run, command="echo", timeout_seconds=3601)
    def test_continue_on_error_flag(self):
        """Test continue_on_error flag."""
        step = Step(
            name="test", type=StepType.run, command="echo", continue_on_error=True
        )
        assert step.continue_on_error is True
class TestPipeline:
    """Test Pipeline model validation and edge cases."""
    def test_valid_pipeline(self):
        """Test creating a valid pipeline."""
        steps = [
            Step(name="lint", type=StepType.run, command="make lint"),
            Step(
                name="build",
                type=StepType.build,
                dockerfile="Dockerfile",
                ecr_repo="app/backend",
            ),
        ]
        pipeline = Pipeline(
            name="test-pipeline",
            repo_url="https://github.com/example/repo",
            branch="develop",
            steps=steps,
        )
        assert pipeline.name == "test-pipeline"
        assert str(pipeline.repo_url) == "https://github.com/example/repo"
        assert pipeline.branch == "develop"
        assert len(pipeline.steps) == 2
        assert pipeline.id is not None
        assert isinstance(pipeline.created_at, datetime)
        assert isinstance(pipeline.updated_at, datetime)
    def test_pipeline_defaults(self):
        """Test pipeline default values."""
        pipeline = Pipeline(name="test", repo_url="https://github.com/example/repo")
        assert pipeline.branch == "main"  # default
        assert pipeline.steps == []  # default empty list
    def test_invalid_repo_url(self):
        """Test invalid repository URL fails validation."""
        with pytest.raises(ValidationError):
            Pipeline(name="test", repo_url="not-a-url")
    def test_pipeline_with_invalid_steps(self):
        """Test pipeline with invalid steps fails validation."""
        bad_step = {"name": "bad", "type": "run"}  # missing command
        with pytest.raises(ValidationError):
            Pipeline(
                name="test",
                repo_url="https://github.com/example/repo",
                steps=[bad_step],
            )
    def test_unique_pipeline_ids(self):
        """Test that each pipeline gets a unique ID."""
        p1 = Pipeline(name="test1", repo_url="https://github.com/example/repo")
        p2 = Pipeline(name="test2", repo_url="https://github.com/example/repo")
        assert p1.id != p2.id
class TestRun:
    """Test Run model validation and edge cases."""
    def test_valid_run(self):
        """Test creating a valid run."""
        run = Run(pipeline_id="pipeline-123")
        assert run.pipeline_id == "pipeline-123"
        assert run.status == RunStatus.pending  # default
        assert run.started_at is None
        assert run.finished_at is None
        assert run.current_step is None
        assert run.logs == []  # default empty list
        assert run.id is not None
    def test_run_with_all_fields(self):
        """Test run with all fields populated."""
        now = datetime.utcnow()
        run = Run(
            pipeline_id="pipeline-456",
            status=RunStatus.running,
            started_at=now,
            current_step=2,
            logs=["Step 1 complete", "Starting step 2"],
        )
        assert run.status == RunStatus.running
        assert run.started_at == now
        assert run.current_step == 2
        assert len(run.logs) == 2
    def test_unique_run_ids(self):
        """Test that each run gets a unique ID."""
        r1 = Run(pipeline_id="pipeline-1")
        r2 = Run(pipeline_id="pipeline-2")
        assert r1.id != r2.id
    def test_run_status_enum_values(self):
        """Test all RunStatus enum values are valid."""
        statuses = [
            RunStatus.pending,
            RunStatus.running,
            RunStatus.succeeded,
            RunStatus.failed,
            RunStatus.cancelled,
        ]
        for status in statuses:
            run = Run(pipeline_id="test", status=status)
            assert run.status == status
    def test_invalid_run_status_fails(self):
        """Test invalid status fails validation."""
        with pytest.raises(ValidationError):
            Run(pipeline_id="test", status="invalid-status")
class TestStepType:
    """Test StepType enum."""
    def test_step_type_values(self):
        """Test all StepType enum values."""
        assert StepType.run == "run"
        assert StepType.build == "build"
        assert StepType.deploy == "deploy"
    def test_step_type_comparison(self):
        """Test StepType enum comparison."""
        step = Step(name="test", type="run", command="echo")
        assert step.type == StepType.run
        assert step.type != StepType.build
