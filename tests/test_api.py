"""
Test API endpoints comprehensively.

This module tests all API endpoints with various scenarios including:
- Happy path scenarios
- Error conditions
- Edge cases
- Validation errors
- GitHub integration

Version: 0.1.0
"""

from unittest.mock import patch

from fastapi.testclient import TestClient

from api.main import app
from api.models import Pipeline, Step, StepType
from api.storage import InMemoryDB


class TestAPIEndpoints:
    """Test all API endpoints comprehensively."""

    def setup_method(self):
        """Set up test environment before each test."""
        self.client = TestClient(app)
        self.db = InMemoryDB()

        # Create a test pipeline for testing
        self.test_pipeline = Pipeline(
            name="test-pipeline",
            repo_url="https://github.com/example/repo",
            branch="main",
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

        # Mock the database to use our test instance
        self.db_patcher = patch("api.main.db", self.db)
        self.db_patcher.start()

    def teardown_method(self):
        """Clean up after each test."""
        self.db_patcher.stop()

    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_create_pipeline_minimal(self):
        """Test creating pipeline with minimal required fields."""
        payload = {
            "name": "minimal-pipeline",
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "test", "type": "run", "command": "echo hello"}],
        }

        response = self.client.post("/pipelines", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "minimal-pipeline"
        assert data["branch"] == "main"  # Default value
        assert data["id"] is not None
        assert len(data["steps"]) == 1
        assert data["steps"][0]["name"] == "test"
        assert data["steps"][0]["type"] == "run"
        assert data["steps"][0]["command"] == "echo hello"

    def test_create_pipeline_with_all_fields(self):
        """Test creating pipeline with all optional fields."""
        payload = {
            "name": "full-pipeline",
            "repo_url": "https://github.com/example/full-repo",
            "branch": "develop",
            "steps": [
                {
                    "name": "lint",
                    "type": "run",
                    "command": "make lint",
                    "timeout_seconds": 600,
                    "continue_on_error": True,
                },
                {
                    "name": "build",
                    "type": "build",
                    "dockerfile": "Dockerfile.prod",
                    "ecr_repo": "myapp/backend",
                    "timeout_seconds": 1800,
                },
            ],
        }

        response = self.client.post("/pipelines", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "full-pipeline"
        assert data["branch"] == "develop"
        assert len(data["steps"]) == 2
        assert data["steps"][0]["timeout_seconds"] == 600
        assert data["steps"][0]["continue_on_error"] is True
        assert data["steps"][1]["timeout_seconds"] == 1800

    def test_create_pipeline_invalid_url(self):
        """Test creating pipeline with invalid repo URL."""
        payload = {
            "name": "bad-url",
            "repo_url": "not-a-valid-url",
            "steps": [{"name": "test", "type": "run", "command": "echo"}],
        }

        response = self.client.post("/pipelines", json=payload)

        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("url" in str(error).lower() for error in errors)

    def test_create_pipeline_missing_required_fields(self):
        """Test creating pipeline with missing required fields."""
        payload = {
            "repo_url": "https://github.com/example/repo"
            # Missing name and steps
        }

        response = self.client.post("/pipelines", json=payload)

        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("name" in str(error).lower() for error in errors)
        assert any("steps" in str(error).lower() for error in errors)

    def test_create_pipeline_invalid_step_validation(self):
        """Test creating pipeline with invalid step configuration."""
        payload = {
            "name": "invalid-steps",
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "test", "type": "invalid_type", "command": "echo"}],
        }

        response = self.client.post("/pipelines", json=payload)

        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("type" in str(error).lower() for error in errors)

    def test_list_pipelines_empty(self):
        """Test listing pipelines when none exist."""
        response = self.client.get("/pipelines")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_list_pipelines_with_data(self):
        """Test listing pipelines with existing data."""
        # Create a pipeline first
        payload = {
            "name": "list-test",
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "test", "type": "run", "command": "echo"}],
        }
        create_response = self.client.post("/pipelines", json=payload)
        assert create_response.status_code == 201

        # Now list pipelines
        response = self.client.get("/pipelines")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "list-test"

    def test_get_pipeline_exists(self):
        """Test getting a specific pipeline that exists."""
        # Create a pipeline first
        payload = {
            "name": "get-test",
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "test", "type": "run", "command": "echo"}],
        }
        create_response = self.client.post("/pipelines", json=payload)
        pipeline_id = create_response.json()["id"]

        # Get the pipeline
        response = self.client.get(f"/pipelines/{pipeline_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == pipeline_id
        assert data["name"] == "get-test"

    def test_get_pipeline_not_found(self):
        """Test getting a pipeline that doesn't exist."""
        response = self.client.get("/pipelines/non-existent-id")

        assert response.status_code == 404
        assert response.json()["detail"] == "Pipeline not found"

    @patch("api.gh.create_and_merge_workflow_pr")
    def test_update_pipeline_success(self, mock_create_workflow):
        """Test that pipeline updates work correctly."""
        # Mock GitHub workflow creation to succeed
        mock_create_workflow.return_value = True

        # Create a pipeline first
        payload = {
            "name": "update-test",
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "test", "type": "run", "command": "echo"}],
        }
        create_response = self.client.post("/pipelines", json=payload)
        pipeline_id = create_response.json()["id"]

        # Update the pipeline
        update_payload = {
            "name": "updated-pipeline",
            "repo_url": "https://github.com/example/updated-repo",
            "steps": [
                {"name": "lint", "type": "run", "command": "make lint"},
                {
                    "name": "build",
                    "type": "build",
                    "dockerfile": "Dockerfile",
                    "ecr_repo": "app/backend",
                },
            ],
        }

        response = self.client.put(f"/pipelines/{pipeline_id}", json=update_payload)

        # Should return 200 OK since PUT is implemented
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "updated-pipeline"
        assert data["repo_url"] == "https://github.com/example/updated-repo"
        assert len(data["steps"]) == 2

    def test_update_pipeline_not_found(self):
        """Test updating a pipeline that doesn't exist."""
        update_payload = {
            "name": "updated",
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "test", "type": "run", "command": "echo"}],
        }

        response = self.client.put("/pipelines/non-existent-id", json=update_payload)

        assert response.status_code == 404
        assert response.json()["detail"] == "Pipeline not found"

    def test_delete_pipeline_success(self):
        """Test deleting an existing pipeline."""
        # Create a pipeline first
        payload = {
            "name": "delete-test",
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "test", "type": "run", "command": "echo"}],
        }
        create_response = self.client.post("/pipelines", json=payload)
        pipeline_id = create_response.json()["id"]

        # Delete the pipeline
        response = self.client.delete(f"/pipelines/{pipeline_id}")

        assert response.status_code == 204

        # Verify it's gone
        get_response = self.client.get(f"/pipelines/{pipeline_id}")
        assert get_response.status_code == 404

    def test_delete_pipeline_not_found(self):
        """Test deleting a pipeline that doesn't exist."""
        response = self.client.delete("/pipelines/non-existent-id")

        assert response.status_code == 404
        assert response.json()["detail"] == "Pipeline not found"

    def test_trigger_pipeline_success(self):
        """Test successful pipeline trigger."""
        # Create pipeline
        payload = {
            "name": "trigger-test",
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "test", "type": "run", "command": "echo hello"}],
        }
        create_response = self.client.post("/pipelines", json=payload)
        pipeline_id = create_response.json()["id"]

        # Trigger pipeline
        trigger_response = self.client.post(f"/pipelines/{pipeline_id}/trigger")

        assert trigger_response.status_code == 202
        data = trigger_response.json()
        assert "run_id" in data
        assert data["status"] == "pending"

    def test_trigger_pipeline_not_found(self):
        """Test triggering non-existent pipeline."""
        response = self.client.post("/pipelines/non-existent-id/trigger")

        assert response.status_code == 404
        assert response.json()["detail"] == "Pipeline not found"

    @patch("api.main.settings")
    def test_trigger_pipeline_with_github_integration(self, mock_settings):
        """Test pipeline trigger with GitHub integration enabled."""
        # Configure GitHub settings
        mock_settings.github_owner = "test-owner"
        mock_settings.github_repo = "test-repo"
        mock_settings.github_token = "test-token"
        mock_settings.github_workflow = "pipeline.yml"
        mock_settings.github_ref = "main"

        # Mock GitHub functions to avoid real API calls
        with (
            patch("api.gh.create_and_merge_workflow_pr") as mock_create_workflow,
            patch("api.gh.workflow_exists") as mock_workflow_exists,
            patch("api.gh.trigger_github_workflow") as mock_gh_trigger,
        ):

            mock_create_workflow.return_value = True  # Workflow creation succeeds
            mock_workflow_exists.return_value = True  # Workflow exists
            mock_gh_trigger.return_value = 204

            # Create and trigger pipeline
            payload = {
                "name": "github-test",
                "repo_url": "https://github.com/example/repo",
                "steps": [{"name": "test", "type": "run", "command": "echo"}],
            }
            create_response = self.client.post("/pipelines", json=payload)
            pipeline_id = create_response.json()["id"]

            trigger_response = self.client.post(f"/pipelines/{pipeline_id}/trigger")

            assert trigger_response.status_code == 202
            # GitHub trigger should have been called
            mock_gh_trigger.assert_called_once()

    def test_get_run_exists(self):
        """Test getting a specific run that exists."""
        # Create a pipeline and trigger it
        payload = {
            "name": "run-test",
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "test", "type": "run", "command": "echo"}],
        }
        create_response = self.client.post("/pipelines", json=payload)
        pipeline_id = create_response.json()["id"]

        # Trigger the pipeline to create a run
        trigger_response = self.client.post(f"/pipelines/{pipeline_id}/trigger")
        run_id = trigger_response.json()["run_id"]

        # Get the run
        response = self.client.get(f"/runs/{run_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == run_id
        assert data["pipeline_id"] == pipeline_id
        assert data["status"] in ["pending", "running", "succeeded", "failed"]

    def test_get_run_not_found(self):
        """Test getting a run that doesn't exist."""
        response = self.client.get("/runs/non-existent-id")

        assert response.status_code == 404
        assert response.json()["detail"] == "Run not found"

    def test_list_runs_not_implemented(self):
        """Test that listing all runs is not implemented (GET /runs endpoint doesn't exist)."""
        response = self.client.get("/runs")

        # Should return 404 since the endpoint doesn't exist
        assert response.status_code == 404

    def test_list_runs_with_data_not_implemented(self):
        """Test that listing runs with data is not implemented (GET /runs endpoint doesn't exist)."""
        # Create a pipeline and trigger it to create a run
        payload = {
            "name": "runs-list-test",
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "test", "type": "run", "command": "echo"}],
        }
        create_response = self.client.post("/pipelines", json=payload)
        pipeline_id = create_response.json()["id"]

        # Trigger the pipeline
        self.client.post(f"/pipelines/{pipeline_id}/trigger")

        # Try to list runs (should fail since endpoint doesn't exist)
        response = self.client.get("/runs")

        # Should return 404 since the endpoint doesn't exist
        assert response.status_code == 404

    def test_invalid_json_request(self):
        """Test handling of invalid JSON in request body."""
        response = self.client.post(
            "/pipelines",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    def test_missing_content_type(self):
        """Test handling of missing content type."""
        response = self.client.post("/pipelines", data='{"name": "test"}')

        # FastAPI should handle this gracefully
        assert response.status_code in [400, 422]

    def test_very_long_pipeline_name(self):
        """Test handling of very long pipeline name."""
        long_name = "a" * 1000  # Very long name
        payload = {
            "name": long_name,
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "test", "type": "run", "command": "echo"}],
        }

        response = self.client.post("/pipelines", json=payload)

        # Should either accept it or return validation error
        assert response.status_code in [201, 422]

    def test_special_characters_in_names(self):
        """Test handling of special characters in names."""
        special_names = [
            "test-pipeline",
            "test_pipeline",
            "test.pipeline",
            "test pipeline",
            "test@pipeline",
            "test#pipeline",
        ]

        for name in special_names:
            payload = {
                "name": name,
                "repo_url": "https://github.com/example/repo",
                "steps": [{"name": "test", "type": "run", "command": "echo"}],
            }

            response = self.client.post("/pipelines", json=payload)

            # Should handle all these gracefully
            assert response.status_code in [201, 422]

    def test_empty_steps_array(self):
        """Test pipeline with empty steps array."""
        payload = {
            "name": "empty-steps",
            "repo_url": "https://github.com/example/repo",
            "steps": [],
        }

        response = self.client.post("/pipelines", json=payload)

        # Should allow empty steps
        assert response.status_code == 201

    def test_sequential_pipeline_operations(self):
        """Test sequential pipeline operations to avoid threading issues."""
        results = []

        # Create multiple pipelines sequentially (safer than threading with TestClient)
        for i in range(5):
            payload = {
                "name": f"sequential-{i}",
                "repo_url": "https://github.com/example/repo",
                "steps": [{"name": "test", "type": "run", "command": "echo"}],
            }
            response = self.client.post("/pipelines", json=payload)
            results.append(response.status_code)

        # All should succeed
        assert all(status == 201 for status in results)
        assert len(results) == 5

    def test_pipeline_with_complex_steps(self):
        """Test creating pipeline with complex step configurations."""
        payload = {
            "name": "complex-steps",
            "repo_url": "https://github.com/example/complex-repo",
            "steps": [
                {
                    "name": "setup",
                    "type": "run",
                    "command": "npm install",
                    "timeout_seconds": 300,
                    "continue_on_error": False,
                },
                {
                    "name": "build",
                    "type": "build",
                    "dockerfile": "Dockerfile.prod",
                    "ecr_repo": "myapp/frontend",
                    "timeout_seconds": 1200,
                    "continue_on_error": False,
                },
                {
                    "name": "deploy",
                    "type": "deploy",
                    "manifest": "k8s/frontend.yaml",
                    "timeout_seconds": 600,
                    "continue_on_error": True,
                },
            ],
        }

        response = self.client.post("/pipelines", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "complex-steps"
        assert len(data["steps"]) == 3

        # Verify step details
        setup_step = data["steps"][0]
        assert setup_step["name"] == "setup"
        assert setup_step["type"] == "run"
        assert setup_step["command"] == "npm install"
        assert setup_step["timeout_seconds"] == 300
        assert setup_step["continue_on_error"] is False

        build_step = data["steps"][1]
        assert build_step["name"] == "build"
        assert build_step["type"] == "build"
        assert build_step["dockerfile"] == "Dockerfile.prod"
        assert build_step["ecr_repo"] == "myapp/frontend"

        deploy_step = data["steps"][2]
        assert deploy_step["name"] == "deploy"
        assert deploy_step["type"] == "deploy"
        assert deploy_step["manifest"] == "k8s/frontend.yaml"
        assert deploy_step["continue_on_error"] is True

    @patch("api.gh.create_and_merge_workflow_pr")
    def test_pipeline_update_with_step_changes(self, mock_create_workflow):
        """Test that pipeline updates with step changes work correctly."""
        # Mock GitHub workflow creation to succeed
        mock_create_workflow.return_value = True

        # Create initial pipeline
        initial_payload = {
            "name": "update-steps-test",
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "old-step", "type": "run", "command": "echo old"}],
        }
        create_response = self.client.post("/pipelines", json=initial_payload)
        pipeline_id = create_response.json()["id"]

        # Update with new steps
        update_payload = {
            "name": "updated-steps",
            "repo_url": "https://github.com/example/new-repo",
            "steps": [
                {"name": "new-step-1", "type": "run", "command": "echo new1"},
                {
                    "name": "new-step-2",
                    "type": "build",
                    "dockerfile": "Dockerfile",
                    "ecr_repo": "app/backend",
                },
            ],
        }

        response = self.client.put(f"/pipelines/{pipeline_id}", json=update_payload)

        # Should return 200 OK since PUT is implemented
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "updated-steps"
        assert data["repo_url"] == "https://github.com/example/new-repo"
        assert len(data["steps"]) == 2
        assert data["steps"][0]["name"] == "new-step-1"
        assert data["steps"][1]["name"] == "new-step-2"
        assert data["steps"][1]["type"] == "build"

    def test_pipeline_validation_edge_cases(self):
        """Test pipeline validation with edge case inputs."""
        # Test with very short name
        short_name_payload = {
            "name": "a",  # Very short name
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "test", "type": "run", "command": "echo"}],
        }
        response = self.client.post("/pipelines", json=short_name_payload)
        assert response.status_code in [201, 422]  # Should either accept or validate

        # Test with special characters in repo URL
        special_url_payload = {
            "name": "special-url",
            "repo_url": "https://github.com/user-name/repo_name.with-dots",
            "steps": [{"name": "test", "type": "run", "command": "echo"}],
        }
        response = self.client.post("/pipelines", json=special_url_payload)
        assert response.status_code == 201  # Should accept valid GitHub URLs

        # Test with step names containing special characters
        special_step_payload = {
            "name": "special-steps",
            "repo_url": "https://github.com/example/repo",
            "steps": [
                {"name": "step-with-dashes", "type": "run", "command": "echo"},
                {"name": "step_with_underscores", "type": "run", "command": "echo"},
                {"name": "step.with.dots", "type": "run", "command": "echo"},
            ],
        }
        response = self.client.post("/pipelines", json=special_step_payload)
        assert response.status_code == 201
        data = response.json()
        assert len(data["steps"]) == 3
