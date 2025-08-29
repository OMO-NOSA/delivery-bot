"""
Tests for the refactored GitHub integration module.
This module tests the new class-based architecture, error handling,
retry logic, and dependency injection capabilities.
"""
import pytest
from unittest.mock import Mock, patch
from api.gh import (
    GitHubIntegration,
    GitHubClient,
    WorkflowManager,
    BranchManager,
    PRManager,
    WorkflowGenerator,
    GitHubAPIError,
    GitHubNotFoundError,
    RequestsHTTPClient,
)
class TestWorkflowGenerator:
    """Test the WorkflowGenerator class."""
    def test_generate_default_workflow_steps(self):
        """Test default workflow steps generation."""
        steps = WorkflowGenerator.generate_default_workflow_steps()
        assert "Simulate build step" in steps
        assert "Simulate test step" in steps
        assert "Simulate deploy step" in steps
    def test_generate_workflow_steps_with_pipeline_steps(self):
        """Test workflow steps generation with pipeline steps."""
        # Mock pipeline steps
        mock_steps = [
            Mock(name="Build App", type="build", dockerfile="./Dockerfile", ecr_repo="my-repo"),
            Mock(name="Deploy", type="deploy", manifest="./k8s/deploy.yaml"),
            Mock(name="Run Tests", type="run", command="npm test"),
        ]
        steps = WorkflowGenerator.generate_workflow_steps(mock_steps)
        assert "Build App" in steps
        assert "Deploy" in steps
        assert "Run Tests" in steps
        assert "npm test" in steps
    def test_generate_workflow_content(self):
        """Test complete workflow content generation."""
        pipeline_id = "test-pipeline-123"
        workflow_steps = "    - name: Test Step\n      run: echo 'test'"
        content = WorkflowGenerator.generate_workflow_content(pipeline_id, workflow_steps)
        assert f"Pipeline {pipeline_id}" in content
        assert "workflow_dispatch" in content
        assert "Test Step" in content
class TestRequestsHTTPClient:
    """Test the concrete HTTP client implementation."""
    def test_http_client_methods(self):
        """Test that HTTP client methods delegate to requests correctly."""
        client = RequestsHTTPClient()
        with patch('requests.get') as mock_get:
            mock_get.return_value = Mock(status_code=200)
            client.get("http://test.com", {}, timeout=10)
            mock_get.assert_called_once_with("http://test.com", headers={}, params=None, timeout=10)
        with patch('requests.post') as mock_post:
            mock_post.return_value = Mock(status_code=201)
            client.post("http://test.com", {}, json_data={"test": "data"}, timeout=10)
            mock_post.assert_called_once_with("http://test.com", headers={}, json={"test": "data"}, timeout=10)
class TestGitHubClient:
    """Test the GitHub client class."""
    def test_initialization(self):
        """Test GitHub client initialization."""
        token = "test-token"
        client = GitHubClient(token)
        assert client.token == token
        assert "Bearer test-token" in client._headers["Authorization"]
        assert client._headers["X-GitHub-Api-Version"] == "2022-11-28"
    def test_make_request_with_retry(self):
        """Test that requests are made with retry logic."""
        token = "test-token"
        client = GitHubClient(token)
        with patch.object(client.http_client, 'get') as mock_get:
            mock_response = Mock(status_code=200)
            mock_get.return_value = mock_response
            response = client._make_request("GET", "/test")
            mock_get.assert_called_once()
            assert response == mock_response
    def test_make_request_rate_limit_error(self):
        """Test rate limit error handling."""
        token = "test-token"
        client = GitHubClient(token)
        with patch.object(client.http_client, 'get') as mock_get:
            mock_response = Mock(status_code=403, text="rate limit exceeded")
            mock_get.return_value = mock_response
            # The retry logic will retry 3 times, then raise the final error
            with pytest.raises(GitHubAPIError, match="Unexpected error"):
                client._make_request("GET", "/test")
    def test_make_request_auth_error(self):
        """Test authentication error handling."""
        token = "test-token"
        client = GitHubClient(token)
        with patch.object(client.http_client, 'get') as mock_get:
            mock_response = Mock(status_code=401, text="Unauthorized")
            mock_get.return_value = mock_response
            with pytest.raises(GitHubAPIError, match="Authentication failed"):
                client._make_request("GET", "/test")
class TestWorkflowManager:
    """Test the WorkflowManager class."""
    def test_trigger_workflow_success(self):
        """Test successful workflow triggering."""
        mock_client = Mock()
        mock_response = Mock(status_code=204)
        mock_client._make_request.return_value = mock_response
        manager = WorkflowManager(mock_client)
        result = manager.trigger_workflow("owner", "repo", "workflow.yml", "main", {"env": "prod"})
        assert result is True
        mock_client._make_request.assert_called_once()
    def test_trigger_workflow_failure(self):
        """Test workflow triggering failure."""
        mock_client = Mock()
        mock_response = Mock(status_code=404)
        mock_client._make_request.return_value = mock_response
        manager = WorkflowManager(mock_client)
        result = manager.trigger_workflow("owner", "repo", "workflow.yml", "main", {"env": "prod"})
        assert result is False
    def test_workflow_exists_true(self):
        """Test workflow existence check when workflow exists."""
        mock_client = Mock()
        mock_response = Mock(status_code=200)
        mock_client._make_request.return_value = mock_response
        manager = WorkflowManager(mock_client)
        result = manager.workflow_exists("owner", "repo", "workflow.yml")
        assert result is True
    def test_workflow_exists_false(self):
        """Test workflow existence check when workflow doesn't exist."""
        mock_client = Mock()
        mock_client._make_request.side_effect = GitHubNotFoundError("Not found")
        manager = WorkflowManager(mock_client)
        result = manager.workflow_exists("owner", "repo", "workflow.yml")
        assert result is False
class TestBranchManager:
    """Test the BranchManager class."""
    def test_create_branch_success(self):
        """Test successful branch creation."""
        mock_client = Mock()
        # Mock the SHA retrieval
        sha_response = Mock(status_code=200)
        sha_response.json.return_value = {"object": {"sha": "abc123"}}
        # Mock the branch creation
        branch_response = Mock(status_code=201)
        mock_client._make_request.side_effect = [sha_response, branch_response]
        manager = BranchManager(mock_client)
        result = manager.create_branch_from_ref("owner", "repo", "main", "feature-branch")
        assert result is True
        assert mock_client._make_request.call_count == 2
    def test_create_branch_sha_failure(self):
        """Test branch creation failure when getting SHA."""
        mock_client = Mock()
        sha_response = Mock(status_code=404)
        mock_client._make_request.return_value = sha_response
        manager = BranchManager(mock_client)
        result = manager.create_branch_from_ref("owner", "repo", "main", "feature-branch")
        assert result is False
class TestPRManager:
    """Test the PRManager class."""
    def test_create_pull_request_success(self):
        """Test successful PR creation."""
        mock_client = Mock()
        mock_response = Mock(status_code=201)
        mock_client._make_request.return_value = mock_response
        manager = PRManager(mock_client)
        result = manager.create_pull_request("owner", "repo", "main", "feature", "Title", "Body")
        assert result is True
        mock_client._make_request.assert_called_once()
    def test_create_pull_request_failure(self):
        """Test PR creation failure."""
        mock_client = Mock()
        mock_response = Mock(status_code=422)
        mock_client._make_request.return_value = mock_response
        manager = PRManager(mock_client)
        result = manager.create_pull_request("owner", "repo", "main", "feature", "Title", "Body")
        assert result is False
class TestGitHubIntegration:
    """Test the main GitHub integration class."""
    def test_initialization(self):
        """Test GitHub integration initialization."""
        integration = GitHubIntegration("test-token")
        assert integration.github_client is not None
        assert integration.workflow_manager is not None
        assert integration.branch_manager is not None
        assert integration.pr_manager is not None
    def test_trigger_workflow_delegation(self):
        """Test that workflow triggering is delegated correctly."""
        integration = GitHubIntegration("test-token")
        with patch.object(integration.workflow_manager, 'trigger_workflow') as mock_trigger:
            mock_trigger.return_value = True
            result = integration.trigger_workflow("owner", "repo", "workflow.yml", "main", {"env": "prod"})
            assert result is True
            mock_trigger.assert_called_once_with("owner", "repo", "workflow.yml", "main", {"env": "prod"})
class TestBackwardCompatibility:
    """Test that backward compatibility functions still work."""
    def test_trigger_github_workflow_function(self):
        """Test the legacy function still works."""
        with patch('api.gh.GitHubIntegration') as mock_integration_class:
            mock_integration = Mock()
            mock_workflow_manager = Mock()
            mock_integration.workflow_manager = mock_workflow_manager
            mock_workflow_manager.trigger_workflow.return_value = 204
            mock_integration_class.return_value = mock_integration
            from api.gh import trigger_github_workflow
            result = trigger_github_workflow("owner", "repo", "workflow.yml", "main", "token", {"env": "prod"})
            assert result == 204
            mock_workflow_manager.trigger_workflow.assert_called_once_with("owner", "repo", "workflow.yml", "main", {"env": "prod"}, return_status_code=True)
if __name__ == "__main__":
    pytest.main([__file__])
