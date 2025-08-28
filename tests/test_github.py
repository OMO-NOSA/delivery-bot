import pytest
import requests
from unittest.mock import patch, Mock
from api.gh import trigger_github_workflow


class TestGitHubIntegration:
    """Test GitHub workflow integration."""
    
    @patch('api.gh.requests.post')
    def test_trigger_github_workflow_success(self, mock_post):
        """Test successful GitHub workflow trigger."""
        # Setup mock response
        mock_response = Mock()
        mock_response.status_code = 204  # GitHub API returns 204 for successful dispatch
        mock_post.return_value = mock_response
        
        # Test parameters
        owner = "myorg"
        repo = "myrepo"
        workflow = "pipeline.yml"
        ref = "main"
        token = "ghp_secret123"
        inputs = {
            "pipeline_id": "pipeline-123",
            "repo_url": "https://github.com/example/repo",
            "branch": "main"
        }
        
        # Call function
        status_code = trigger_github_workflow(owner, repo, workflow, ref, token, inputs)
        
        # Verify result
        assert status_code == 204
        
        # Verify API call was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Check URL (first positional argument)
        expected_url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
        assert call_args[0][0] == expected_url
        
        # Check headers
        headers = call_args[1]['headers']
        assert headers['Accept'] == 'application/vnd.github+json'
        assert headers['Authorization'] == f'Bearer {token}'
        assert headers['X-GitHub-Api-Version'] == '2022-11-28'
        assert headers['User-Agent'] == 'cicd-pipelines-api'
        
        # Check payload
        payload = call_args[1]['json']
        assert payload['ref'] == ref
        assert payload['inputs'] == inputs
        
        # Check timeout
        assert call_args[1]['timeout'] == 15
    
    @patch('api.gh.requests.post')
    def test_trigger_github_workflow_auth_error(self, mock_post):
        """Test GitHub workflow trigger with authentication error."""
        # Setup mock response for auth error
        mock_response = Mock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response
        
        status_code = trigger_github_workflow(
            "owner", "repo", "workflow.yml", "main", "invalid-token", {}
        )
        
        assert status_code == 401
    
    @patch('api.gh.requests.post')
    def test_trigger_github_workflow_not_found(self, mock_post):
        """Test GitHub workflow trigger with workflow not found."""
        # Setup mock response for not found
        mock_response = Mock()
        mock_response.status_code = 404
        mock_post.return_value = mock_response
        
        status_code = trigger_github_workflow(
            "owner", "repo", "nonexistent.yml", "main", "token", {}
        )
        
        assert status_code == 404
    
    @patch('api.gh.requests.post')
    def test_trigger_github_workflow_with_complex_inputs(self, mock_post):
        """Test GitHub workflow trigger with complex input data."""
        mock_response = Mock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response
        
        complex_inputs = {
            "pipeline_id": "pipeline-456",
            "repo_url": "https://github.com/complex/repo-name",
            "branch": "feature/complex-branch-name",
            "environment": "staging",
            "deploy_target": "k8s-cluster-west",
            "build_args": "arg1=value1,arg2=value2"
        }
        
        status_code = trigger_github_workflow(
            "owner", "repo", "workflow.yml", "develop", "token", complex_inputs
        )
        
        assert status_code == 204
        
        # Verify complex inputs were passed correctly
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload['inputs'] == complex_inputs
        assert payload['ref'] == "develop"
    
    @patch('api.gh.requests.post')
    def test_trigger_github_workflow_network_error(self, mock_post):
        """Test GitHub workflow trigger with network error."""
        # Setup mock to raise a network exception
        mock_post.side_effect = requests.exceptions.RequestException("Network error")
        
        # Function should re-raise the exception
        with pytest.raises(requests.exceptions.RequestException):
            trigger_github_workflow(
                "owner", "repo", "workflow.yml", "main", "token", {}
            )
    
    @patch('api.gh.requests.post')
    def test_trigger_github_workflow_timeout(self, mock_post):
        """Test GitHub workflow trigger with timeout."""
        # Setup mock to raise timeout exception
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")
        
        # Function should re-raise the exception
        with pytest.raises(requests.exceptions.Timeout):
            trigger_github_workflow(
                "owner", "repo", "workflow.yml", "main", "token", {}
            )
    
    @patch('api.gh.requests.post')
    def test_trigger_github_workflow_server_error(self, mock_post):
        """Test GitHub workflow trigger with server error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response
        
        status_code = trigger_github_workflow(
            "owner", "repo", "workflow.yml", "main", "token", {}
        )
        
        assert status_code == 500
    
    @patch('api.gh.requests.post')
    def test_trigger_github_workflow_rate_limited(self, mock_post):
        """Test GitHub workflow trigger when rate limited."""
        mock_response = Mock()
        mock_response.status_code = 429  # Too Many Requests
        mock_post.return_value = mock_response
        
        status_code = trigger_github_workflow(
            "owner", "repo", "workflow.yml", "main", "token", {}
        )
        
        assert status_code == 429
    
    @patch('api.gh.requests.post')
    def test_trigger_github_workflow_empty_inputs(self, mock_post):
        """Test GitHub workflow trigger with empty inputs."""
        mock_response = Mock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response
        
        status_code = trigger_github_workflow(
            "owner", "repo", "workflow.yml", "main", "token", {}
        )
        
        assert status_code == 204
        
        # Verify empty inputs are handled correctly
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload['inputs'] == {}
    
    @patch('api.gh.requests.post')
    def test_trigger_github_workflow_special_characters(self, mock_post):
        """Test GitHub workflow trigger with special characters in parameters."""
        mock_response = Mock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response
        
        # Test with special characters
        owner = "my-org"
        repo = "my-repo_name"
        workflow = "complex-workflow.yml"
        ref = "feature/special-chars_123"
        
        inputs = {
            "branch": "feature/test-branch_with-special.chars",
            "repo_url": "https://github.com/org/repo-with-dashes",
            "message": "Deploy with spaces and symbols: @#$%"
        }
        
        status_code = trigger_github_workflow(owner, repo, workflow, ref, "token", inputs)
        
        assert status_code == 204
        
        # Verify URL construction with special characters
        call_args = mock_post.call_args
        expected_url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
        assert call_args[0][0] == expected_url
    
    def test_trigger_github_workflow_parameter_types(self):
        """Test that function handles parameter types correctly."""
        # All parameters should be strings
        with patch('api.gh.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 204
            mock_post.return_value = mock_response
            
            # Test with different types (should all be converted to strings or handled properly)
            trigger_github_workflow(
                owner="owner",
                repo="repo", 
                workflow="workflow.yml",
                ref="main",
                token="token",
                inputs={"number": "123", "boolean": "true", "string": "value"}
            )
            
            # Should not raise any type errors
            assert mock_post.called
