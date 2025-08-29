import asyncio
from unittest.mock import Mock, patch

import pytest

from api.models import Pipeline, Run, RunStatus, Step, StepType
from api.pipeline_runner import run_pipeline, simulate_step
from api.storage import InMemoryDB


class TestSimulateStep:
    """Test simulate_step function."""

    def setup_method(self):
        """Set up test environment."""
        self.db = InMemoryDB()
        self.run = Run(pipeline_id="test-pipeline")
        self.db.create_run(self.run)

    @pytest.mark.asyncio
    async def test_simulate_run_step(self):
        """Test simulating a run step."""
        step = Step(name="test-run", type=StepType.run, command="echo hello")
        with patch("api.pipeline_runner.db", self.db):
            await simulate_step(self.run, step, 0)
        # Verify run was updated
        updated_run = self.db.get_run(self.run.id)
        assert updated_run.current_step == 0
        assert len(updated_run.logs) >= 3  # Start, command, finish messages
        # Check log content
        logs = updated_run.logs
        assert "[step 1] Starting 'test-run' of type 'run'" in logs
        assert "Running shell command: 'echo hello'" in logs
        assert "Command finished with exit code 0" in logs

    @pytest.mark.asyncio
    async def test_simulate_build_step(self):
        """Test simulating a build step."""
        step = Step(
            name="test-build",
            type=StepType.build,
            dockerfile="Dockerfile.prod",
            ecr_repo="myapp/backend",
        )
        with patch("api.pipeline_runner.db", self.db):
            await simulate_step(self.run, step, 1)
        # Verify run was updated
        updated_run = self.db.get_run(self.run.id)
        assert updated_run.current_step == 1
        # Check log content
        logs = updated_run.logs
        assert "[step 2] Starting 'test-build' of type 'build'" in logs
        assert (
            "Building Docker image from Dockerfile.prod and pushing to myapp/backend"
            in logs
        )
        assert "Image built and pushed successfully" in logs
        assert "Step 'test-build' completed successfully" in logs

    @pytest.mark.asyncio
    async def test_simulate_deploy_step(self):
        """Test simulating a deploy step."""
        step = Step(
            name="test-deploy", type=StepType.deploy, manifest="k8s/deployment.yaml"
        )
        with patch("api.pipeline_runner.db", self.db):
            await simulate_step(self.run, step, 2)
        # Verify run was updated
        updated_run = self.db.get_run(self.run.id)
        assert updated_run.current_step == 2
        # Check log content
        logs = updated_run.logs
        assert "[step 3] Starting 'test-deploy' of type 'deploy'" in logs
        assert "Applying manifest k8s/deployment.yaml to cluster" in logs
        assert "Deployment applied" in logs

    @pytest.mark.asyncio
    async def test_simulate_step_with_defaults(self):
        """Test simulating steps with default values."""
        # Build step with valid required fields but using default values in logic
        build_step = Step(
            name="build-default",
            type=StepType.build,
            dockerfile="Dockerfile",  # Required field
            ecr_repo="test/repo",  # Required field
        )
        with patch("api.pipeline_runner.db", self.db):
            await simulate_step(self.run, build_step, 0)
        logs = self.db.get_run(self.run.id).logs
        assert "Building Docker image from Dockerfile and pushing to test/repo" in logs
        # Deploy step with valid required field
        self.run.logs = []  # Clear logs
        deploy_step = Step(
            name="deploy-default",
            type=StepType.deploy,
            manifest="k8s/deployment.yaml",  # Required field
        )
        with patch("api.pipeline_runner.db", self.db):
            await simulate_step(self.run, deploy_step, 0)
        logs = self.db.get_run(self.run.id).logs
        assert "Applying manifest k8s/deployment.yaml to cluster" in logs

    @pytest.mark.asyncio
    async def test_simulate_step_unknown_type(self):
        """Test simulating step with unknown type."""

        # Create a mock step object with invalid type that has the expected structure
        class MockStep:
            def __init__(self):
                self.name = "invalid"
                self.type = type(
                    "MockStepType", (), {"value": "unknown"}
                )()  # Mock enum-like object

        mock_step = MockStep()
        with patch("api.pipeline_runner.db", self.db):
            with pytest.raises(ValueError, match="Unknown step type"):
                await simulate_step(self.run, mock_step, 0)
        # Verify error was logged
        updated_run = self.db.get_run(self.run.id)
        logs = updated_run.logs
        assert "Unknown step type encountered" in logs

    @pytest.mark.asyncio
    async def test_simulate_step_db_updates(self):
        """Test that simulate_step updates database correctly."""
        step = Step(name="test", type=StepType.run, command="echo test")
        with patch("api.pipeline_runner.db", self.db) as mock_db:
            mock_db.update_run = Mock(side_effect=self.db.update_run)
            await simulate_step(self.run, step, 0)
            # Verify update_run was called multiple times (for each log message)
            assert mock_db.update_run.call_count >= 3

    @pytest.mark.asyncio
    async def test_simulate_step_timing(self):
        """Test that simulate_step takes appropriate time for each step type."""
        import time

        # Test run step timing
        start = time.time()
        step = Step(name="test", type=StepType.run, command="echo test")
        with patch("api.pipeline_runner.db", self.db):
            await simulate_step(self.run, step, 0)
        duration = time.time() - start
        assert duration >= 1.0  # Should sleep for at least 1 second
        assert duration < 1.5  # But not too long
        # Test build step timing (longer)
        start = time.time()
        build_step = Step(
            name="build", type=StepType.build, dockerfile="Dockerfile", ecr_repo="repo"
        )
        with patch("api.pipeline_runner.db", self.db):
            await simulate_step(self.run, build_step, 1)
        duration = time.time() - start
        assert duration >= 1.5  # Build should take longer


class TestRunPipeline:
    """Test run_pipeline function."""

    def setup_method(self):
        """Set up test environment."""
        self.db = InMemoryDB()
        self.pipeline = Pipeline(
            name="test-pipeline",
            repo_url="https://github.com/example/repo",
            steps=[
                Step(name="lint", type=StepType.run, command="make lint"),
                Step(
                    name="build",
                    type=StepType.build,
                    dockerfile="Dockerfile",
                    ecr_repo="app/backend",
                ),
                Step(name="deploy", type=StepType.deploy, manifest="k8s/deploy.yaml"),
            ],
        )
        self.run = Run(pipeline_id=self.pipeline.id)
        self.db.create_run(self.run)

    @pytest.mark.asyncio
    async def test_run_pipeline_success(self):
        """Test successful pipeline execution."""
        with patch("api.pipeline_runner.db", self.db):
            await run_pipeline(self.pipeline, self.run)
        # Verify final status
        updated_run = self.db.get_run(self.run.id)
        assert updated_run.status == RunStatus.succeeded
        assert updated_run.started_at is not None
        assert updated_run.finished_at is not None
        assert updated_run.finished_at > updated_run.started_at
        # Verify all steps were executed
        assert len(updated_run.logs) >= 9  # Should have logs from all 3 steps
        assert "lint" in " ".join(updated_run.logs)
        assert "build" in " ".join(updated_run.logs)
        assert "deploy" in " ".join(updated_run.logs)

    @pytest.mark.asyncio
    async def test_run_pipeline_with_failure(self):
        """Test pipeline execution with step failure."""
        # Mock the PipelineExecutor.simulate_step method to raise an exception
        with patch("api.pipeline_runner.db", self.db):
            with patch(
                "api.pipeline_runner.PipelineExecutor.simulate_step",
                side_effect=Exception("Step failed"),
            ):
                await run_pipeline(self.pipeline, self.run)
        # Verify final status
        updated_run = self.db.get_run(self.run.id)
        assert updated_run.status == RunStatus.failed
        assert updated_run.started_at is not None
        assert updated_run.finished_at is not None
        # Verify error was logged
        assert "ERROR: Step failed" in updated_run.logs

    @pytest.mark.asyncio
    async def test_run_pipeline_empty_steps(self):
        """Test pipeline with no steps."""
        empty_pipeline = Pipeline(
            name="empty", repo_url="https://github.com/example/repo", steps=[]
        )
        with patch("api.pipeline_runner.db", self.db):
            # Empty pipeline should fail validation
            with pytest.raises(
                ValueError, match="Pipeline must have at least one step"
            ):
                await run_pipeline(empty_pipeline, self.run)

    @pytest.mark.asyncio
    async def test_run_pipeline_status_transitions(self):
        """Test that pipeline status transitions correctly."""
        # Track status changes directly
        initial_status = self.run.status
        with patch("api.pipeline_runner.db", self.db):
            await run_pipeline(self.pipeline, self.run)
        # Verify final status
        updated_run = self.db.get_run(self.run.id)
        # Verify the run went through the expected states
        assert initial_status == RunStatus.pending
        assert updated_run.status == RunStatus.succeeded
        assert updated_run.started_at is not None
        assert updated_run.finished_at is not None

    @pytest.mark.asyncio
    async def test_run_pipeline_concurrent_execution(self):
        """Test concurrent pipeline execution."""
        # Create multiple runs
        run1 = Run(pipeline_id=self.pipeline.id)
        run2 = Run(pipeline_id=self.pipeline.id)
        self.db.create_run(run1)
        self.db.create_run(run2)
        with patch("api.pipeline_runner.db", self.db):
            # Execute pipelines concurrently
            await asyncio.gather(
                run_pipeline(self.pipeline, run1), run_pipeline(self.pipeline, run2)
            )
        # Both should succeed
        updated_run1 = self.db.get_run(run1.id)
        updated_run2 = self.db.get_run(run2.id)
        assert updated_run1.status == RunStatus.succeeded
        assert updated_run2.status == RunStatus.succeeded
        # Verify they ran independently
        assert updated_run1.id != updated_run2.id
        assert len(updated_run1.logs) > 0
        assert len(updated_run2.logs) > 0

    @pytest.mark.asyncio
    async def test_run_pipeline_step_order(self):
        """Test that steps are executed in order."""
        step_order = []

        async def track_step_order(run, step, index):
            step_order.append((index, step.name))
            # Simulate the step execution without calling the original
            run.current_step = index
            run.logs.append(
                f"[step {index + 1}] Starting '{step.name}' of type '{step.type.value}'"
            )
            self.db.update_run(run.id, run)

        with patch("api.pipeline_runner.db", self.db):
            with patch(
                "api.pipeline_runner.PipelineExecutor.simulate_step",
                side_effect=track_step_order,
            ):
                await run_pipeline(self.pipeline, self.run)
        # Verify steps were executed in order
        assert step_order == [(0, "lint"), (1, "build"), (2, "deploy")]

    @pytest.mark.asyncio
    async def test_run_pipeline_exception_in_middle_step(self):
        """Test pipeline failure in middle step."""
        call_count = 0

        async def fail_on_second_step(run, step, index):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Fail on second step
                raise Exception("Build failed")
            # Simulate successful execution for other steps
            run.current_step = index
            run.logs.append(
                f"[step {index + 1}] Starting '{step.name}' of type '{step.type.value}'"
            )
            self.db.update_run(run.id, run)

        with patch("api.pipeline_runner.db", self.db):
            with patch(
                "api.pipeline_runner.PipelineExecutor.simulate_step",
                side_effect=fail_on_second_step,
            ):
                await run_pipeline(self.pipeline, self.run)
        # Should fail and not execute remaining steps
        updated_run = self.db.get_run(self.run.id)
        assert updated_run.status == RunStatus.failed
        assert "ERROR: Build failed" in updated_run.logs
        # Only first two steps should have been attempted
        assert call_count == 2
