
from fastapi.testclient import TestClient
from api.main import app


class TestNotFoundErrors:
    """Test 404 error handling for various endpoints."""
    
    def setup_method(self):
        """Set up test client for each test."""
        self.client = TestClient(app)
    
    def test_get_nonexistent_pipeline(self):
        """Test getting a pipeline that doesn't exist returns 404."""
        response = self.client.get("/pipelines/does-not-exist")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Pipeline not found"
    
    def test_delete_nonexistent_pipeline(self):
        """Test deleting a pipeline that doesn't exist returns 404."""
        response = self.client.delete("/pipelines/nope")
        
        assert response.status_code == 404
        # Note: delete endpoint returns 404 without specific detail message
    
    def test_get_nonexistent_run(self):
        """Test getting a run that doesn't exist returns 404."""
        response = self.client.get("/runs/unknown")
        
        assert response.status_code == 404
        # Should return 404 for unknown run ID
    
    def test_update_nonexistent_pipeline(self):
        """Test updating a pipeline that doesn't exist returns 404."""
        update_payload = {
            "name": "updated-name",
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "test", "type": "run", "command": "echo"}]
        }
        
        response = self.client.put("/pipelines/nonexistent-id", json=update_payload)
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Pipeline not found"
    
    def test_trigger_nonexistent_pipeline(self):
        """Test triggering a pipeline that doesn't exist returns 404."""
        response = self.client.post("/pipelines/nonexistent-id/trigger")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "Pipeline not found"


class TestPipelineUpdates:
    """Test pipeline update functionality."""
    
    def setup_method(self):
        """Set up test client for each test."""
        self.client = TestClient(app)
    
    def test_update_pipeline_success(self):
        """Test successfully updating an existing pipeline."""
        # Create initial pipeline
        initial_payload = {
            "name": "ex2",
            "repo_url": "https://github.com/example/repo",
            "branch": "dev",
            "steps": [{"name": "lint", "type": "run", "command": "echo hi"}],
        }
        
        create_response = self.client.post("/pipelines", json=initial_payload)
        assert create_response.status_code == 201
        pipeline_id = create_response.json()["id"]
        original_created_at = create_response.json()["created_at"]
        
        # Update the pipeline
        update_payload = initial_payload.copy()
        update_payload["name"] = "ex2-updated"
        update_payload["branch"] = "main"  # Change branch too
        
        update_response = self.client.put(f"/pipelines/{pipeline_id}", json=update_payload)
        
        assert update_response.status_code == 200
        updated_data = update_response.json()
        assert updated_data["name"] == "ex2-updated"
        assert updated_data["branch"] == "main"
        assert updated_data["id"] == pipeline_id
        assert updated_data["created_at"] == original_created_at  # Should preserve original created_at
        assert updated_data["updated_at"] != original_created_at  # Should have new updated_at
    
    def test_update_pipeline_with_new_steps(self):
        """Test updating a pipeline with completely different steps."""
        # Create initial pipeline
        initial_payload = {
            "name": "step-update-test",
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "old-step", "type": "run", "command": "echo old"}],
        }
        
        create_response = self.client.post("/pipelines", json=initial_payload)
        assert create_response.status_code == 201
        pipeline_id = create_response.json()["id"]
        
        # Update with new steps
        update_payload = {
            "name": "step-update-test",
            "repo_url": "https://github.com/example/repo",
            "steps": [
                {"name": "new-step-1", "type": "run", "command": "echo new1"},
                {"name": "new-step-2", "type": "build", "dockerfile": "Dockerfile", "ecr_repo": "new/repo"},
                {"name": "new-step-3", "type": "deploy", "manifest": "k8s/new-deploy.yaml"}
            ]
        }
        
        update_response = self.client.put(f"/pipelines/{pipeline_id}", json=update_payload)
        
        assert update_response.status_code == 200
        updated_data = update_response.json()
        assert len(updated_data["steps"]) == 3
        assert updated_data["steps"][0]["name"] == "new-step-1"
        assert updated_data["steps"][1]["type"] == "build"
        assert updated_data["steps"][2]["type"] == "deploy"
    
    def test_update_pipeline_repo_url(self):
        """Test updating a pipeline's repository URL."""
        # Create initial pipeline
        initial_payload = {
            "name": "repo-update-test",
            "repo_url": "https://github.com/example/old-repo",
            "steps": [{"name": "test", "type": "run", "command": "echo test"}],
        }
        
        create_response = self.client.post("/pipelines", json=initial_payload)
        assert create_response.status_code == 201
        pipeline_id = create_response.json()["id"]
        
        # Update repository URL
        update_payload = initial_payload.copy()
        update_payload["repo_url"] = "https://github.com/example/new-repo"
        
        update_response = self.client.put(f"/pipelines/{pipeline_id}", json=update_payload)
        
        assert update_response.status_code == 200
        updated_data = update_response.json()
        assert str(updated_data["repo_url"]) == "https://github.com/example/new-repo"


class TestValidationErrors:
    """Test validation error handling for invalid requests."""
    
    def setup_method(self):
        """Set up test client for each test."""
        self.client = TestClient(app)
    
    def test_validation_error_build_step_missing_dockerfile(self):
        """Test validation error for build step missing dockerfile."""
        bad_payload = {
            "name": "bad-build-dockerfile",
            "repo_url": "https://github.com/example/repo",
            "branch": "main",
            "steps": [{"name": "build", "type": "build", "ecr_repo": "repo"}],  # Missing dockerfile
        }
        
        response = self.client.post("/pipelines", json=bad_payload)
        
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("dockerfile" in str(error).lower() for error in errors)
    
    def test_validation_error_build_step_missing_ecr_repo(self):
        """Test validation error for build step missing ECR repo."""
        bad_payload = {
            "name": "bad-build-ecr",
            "repo_url": "https://github.com/example/repo",
            "branch": "main",
            "steps": [{"name": "build", "type": "build", "dockerfile": "Dockerfile"}],  # Missing ecr_repo
        }
        
        response = self.client.post("/pipelines", json=bad_payload)
        
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("ecr_repo" in str(error).lower() for error in errors)
    
    def test_validation_error_build_step_missing_both_fields(self):
        """Test validation error for build step missing both required fields."""
        bad_payload = {
            "name": "bad-build-both",
            "repo_url": "https://github.com/example/repo",
            "branch": "main",
            "steps": [{"name": "build", "type": "build"}],  # Missing both dockerfile and ecr_repo
        }
        
        response = self.client.post("/pipelines", json=bad_payload)
        
        assert response.status_code == 422
    
    def test_validation_error_deploy_step_missing_manifest(self):
        """Test validation error for deploy step missing manifest."""
        bad_payload = {
            "name": "bad-deploy",
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "deploy", "type": "deploy"}],  # Missing manifest
        }
        
        response = self.client.post("/pipelines", json=bad_payload)
        
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("manifest" in str(error).lower() for error in errors)
    
    def test_validation_error_run_step_missing_command(self):
        """Test validation error for run step missing command."""
        bad_payload = {
            "name": "bad-run",
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "run", "type": "run"}],  # Missing command
        }
        
        response = self.client.post("/pipelines", json=bad_payload)
        
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert any("command" in str(error).lower() for error in errors)
    
    def test_validation_error_invalid_step_type(self):
        """Test validation error for invalid step type."""
        bad_payload = {
            "name": "bad-step-type",
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "invalid", "type": "invalid-type", "command": "echo"}],
        }
        
        response = self.client.post("/pipelines", json=bad_payload)
        
        assert response.status_code == 422
    
    def test_validation_error_invalid_repo_url(self):
        """Test validation error for invalid repository URL."""
        bad_payload = {
            "name": "bad-url",
            "repo_url": "not-a-valid-url",
            "steps": [{"name": "test", "type": "run", "command": "echo"}],
        }
        
        response = self.client.post("/pipelines", json=bad_payload)
        
        assert response.status_code == 422
    
    def test_validation_error_missing_required_fields(self):
        """Test validation error for missing required fields."""
        # Missing name
        bad_payload = {
            "repo_url": "https://github.com/example/repo",
            "steps": [{"name": "test", "type": "run", "command": "echo"}],
        }
        
        response = self.client.post("/pipelines", json=bad_payload)
        assert response.status_code == 422
        
        # Missing repo_url
        bad_payload = {
            "name": "test",
            "steps": [{"name": "test", "type": "run", "command": "echo"}],
        }
        
        response = self.client.post("/pipelines", json=bad_payload)
        assert response.status_code == 422
        
        # Missing steps
        bad_payload = {
            "name": "test",
            "repo_url": "https://github.com/example/repo",
        }
        
        response = self.client.post("/pipelines", json=bad_payload)
        assert response.status_code == 422
