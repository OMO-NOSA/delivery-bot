"""
GitHub Actions Integration for Delivery-Bot API.
This module provides integration with GitHub Actions to trigger workflows
when pipelines are executed. It uses the GitHub REST API to dispatch
workflow events with custom inputs and create new workflows via Pull Requests.
The integration allows:
- Triggering GitHub Actions workflows from pipeline execution
- Creating new workflows with manual dispatch support via Pull Requests
- Passing pipeline metadata as workflow inputs
- Proper authentication using GitHub tokens
- Comprehensive error handling and retry logic
Classes:
    GitHubClient: Main client for GitHub API operations
    WorkflowManager: Manages workflow creation and triggering
    BranchManager: Handles branch operations
    PRManager: Manages pull request operations
Dependencies:
    - requests: For HTTP API calls to GitHub
    - tenacity: For retry logic
    - logging: For structured logging
    - GitHub token: Personal access token with workflow permissions
Author: Nosa Omorodion
Version: 0.2.0
"""
import base64
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
logger = logging.getLogger(__name__)


class GitHubAPIError(Exception):
    """Base exception for GitHub API errors."""
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_text: Optional[str] = None
    ):
        self.message = message
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(self.message)


class GitHubRateLimitError(GitHubAPIError):
    """Exception raised when GitHub API rate limit is exceeded."""
    pass


class GitHubNotFoundError(GitHubAPIError):
    """Exception raised when a resource is not found."""
    pass


class GitHubPermissionError(GitHubAPIError):
    """Exception raised when insufficient permissions."""
    pass


class HTTPClient(ABC):
    """Abstract HTTP client interface for dependency injection."""
    @abstractmethod
    def get(
        self,
        url: str,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 15
    ) -> requests.Response:
        """Make a GET request."""
        pass

    @abstractmethod
    def post(
        self,
        url: str,
        headers: Dict[str, str],
        json_data: Optional[Dict[str, Any]] = None,
        timeout: int = 15
    ) -> requests.Response:
        """Make a POST request."""
        pass

    @abstractmethod
    def put(
        self,
        url: str,
        headers: Dict[str, str],
        json_data: Optional[Dict[str, Any]] = None,
        timeout: int = 15
    ) -> requests.Response:
        """Make a PUT request."""
        pass


class RequestsHTTPClient(HTTPClient):
    """Concrete HTTP client implementation using requests library."""
    def get(
        self,
        url: str,
        headers: Dict[str, str],
        params: Optional[Dict[str, Any]] = None,
        timeout: int = 15
    ) -> requests.Response:
        return requests.get(url, headers=headers, params=params, timeout=timeout)

    def post(
        self,
        url: str,
        headers: Dict[str, str],
        json_data: Optional[Dict[str, Any]] = None,
        timeout: int = 15
    ) -> requests.Response:
        return requests.post(url, headers=headers, json=json_data, timeout=timeout)
    def put(
        self,
        url: str,
        headers: Dict[str, str],
        json_data: Optional[Dict[str, Any]] = None,
        timeout: int = 15
    ) -> requests.Response:
        return requests.put(url, headers=headers, json=json_data, timeout=timeout)
class GitHubClient:
    """Main client for GitHub API operations."""
    BASE_URL = "https://api.github.com"
    API_VERSION = "2022-11-28"
    USER_AGENT = "delivery-bot-api"
    def __init__(self, token: str, http_client: Optional[HTTPClient] = None):
        """
        Initialize GitHub client.
        Args:
            token: GitHub personal access token
            http_client: HTTP client implementation (defaults to RequestsHTTPClient)
        """
        self.token = token
        self.http_client = http_client or RequestsHTTPClient()
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": self.API_VERSION,
            "User-Agent": self.USER_AGENT,
        }
        logger.info("GitHub client initialized", extra={"props": {"api_version": self.API_VERSION}})
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make a request to GitHub API with retry logic.
        Args:
            method: HTTP method (GET, POST, PUT)
            endpoint: API endpoint (e.g., '/repos/owner/repo')
            **kwargs: Additional arguments for the request
        Returns:
            Response object
        Raises:
            GitHubAPIError: For API errors
            GitHubRateLimitError: For rate limit errors
        """
        url = urljoin(self.BASE_URL, endpoint)
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=4, max=10),
            retry=retry_if_exception_type((requests.RequestException, GitHubRateLimitError))
        )
        def _retry_request():
            logger.debug(f"Making {method} request to {url}")
            if method.upper() == "GET":
                response = self.http_client.get(url, headers=self._headers, **kwargs)
            elif method.upper() == "POST":
                response = self.http_client.post(url, headers=self._headers, **kwargs)
            elif method.upper() == "PUT":
                response = self.http_client.put(url, headers=self._headers, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            # Handle rate limiting
            if response.status_code == 403 and "rate limit" in response.text.lower():
                logger.warning("GitHub API rate limit exceeded")
                raise GitHubRateLimitError("Rate limit exceeded", response.status_code, response.text)
            # Handle common error status codes
            if response.status_code == 401:
                raise GitHubAPIError("Authentication failed", response.status_code, response.text)
            elif response.status_code == 403:
                raise GitHubPermissionError("Insufficient permissions", response.status_code, response.text)
            elif response.status_code == 404:
                raise GitHubNotFoundError("Resource not found", response.status_code, response.text)
            elif response.status_code >= 500:
                raise GitHubAPIError(f"GitHub server error: {response.status_code}", response.status_code, response.text)
            return response
        try:
            return _retry_request()
        except (GitHubRateLimitError, GitHubAPIError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error in GitHub API request: {e}")
            raise GitHubAPIError(f"Unexpected error: {str(e)}")
class WorkflowManager:
    """Manages GitHub Actions workflow operations."""
    def __init__(self, github_client: GitHubClient):
        """
        Initialize workflow manager.
        Args:
            github_client: GitHub client instance
        """
        self.github_client = github_client
        logger.info("Workflow manager initialized")
    def trigger_workflow(
        self,
        owner: str,
        repo: str,
        workflow: str,
        ref: str,
        inputs: Dict[str, Any],
        return_status_code: bool = False
    ) -> Union[bool, int]:
        """
        Trigger a GitHub Actions workflow via the REST API.
        Args:
            owner: GitHub organization or username
            repo: Repository name
            workflow: Workflow filename
            ref: Git reference (branch, tag, or commit SHA)
            inputs: Key-value pairs to pass as workflow inputs
            return_status_code: If True, return the actual HTTP status code instead of boolean
        Returns:
            True if workflow was triggered successfully, or HTTP status code if return_status_code=True
        Raises:
            GitHubAPIError: For API errors
        """
        logger.info(
            "Triggering GitHub workflow",
            extra={
                "props": {
                    "owner": owner,
                    "repo": repo,
                    "workflow": workflow,
                    "ref": ref,
                    "inputs_count": len(inputs)
                }
            }
        )
        endpoint = f"/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
        payload = {"ref": ref, "inputs": inputs}
        try:
            response = self.github_client._make_request("POST", endpoint, json_data=payload)
            if return_status_code:
                return response.status_code
            else:
                if response.status_code == 204:
                    logger.info("Workflow triggered successfully")
                    return True
                else:
                    logger.error(f"Failed to trigger workflow: {response.status_code}")
                    return False
        except GitHubAPIError as e:
            logger.error(f"Error triggering workflow: {e.message}")
            if return_status_code:
                # Return appropriate status code for the error
                if e.status_code:
                    return e.status_code
                elif isinstance(e, GitHubNotFoundError):
                    return 404
                elif isinstance(e, GitHubPermissionError):
                    return 403
                elif isinstance(e, GitHubRateLimitError):
                    return 429
                else:
                    return 500
            else:
                raise
    def workflow_exists(self, owner: str, repo: str, workflow_name: str, ref: str = "main") -> bool:
        """
        Check if a GitHub Actions workflow file exists.
        Args:
            owner: GitHub organization or username
            repo: Repository name
            workflow_name: Name of the workflow file
            ref: Git reference (defaults to main)
        Returns:
            True if workflow exists, False otherwise
        """
        logger.debug(f"Checking if workflow {workflow_name} exists in {owner}/{repo}")
        endpoint = f"/repos/{owner}/{repo}/contents/.github/workflows/{workflow_name}"
        params = {"ref": ref}
        try:
            response = self.github_client._make_request("GET", endpoint, params=params)
            exists = response.status_code == 200
            if exists:
                logger.info(f"Workflow {workflow_name} found in {owner}/{repo}")
            else:
                logger.info(f"Workflow {workflow_name} not found in {owner}/{repo}")
            return exists
        except GitHubNotFoundError:
            logger.info(f"Workflow {workflow_name} not found in {owner}/{repo}")
            return False
        except GitHubAPIError as e:
            logger.error(f"Error checking workflow existence: {e.message}")
            return False
class BranchManager:
    """Handles GitHub branch operations."""
    def __init__(self, github_client: GitHubClient):
        """
        Initialize branch manager.
        Args:
            github_client: GitHub client instance
        """
        self.github_client = github_client
        logger.info("Branch manager initialized")
    def create_branch_from_ref(
        self,
        owner: str,
        repo: str,
        base_ref: str,
        new_branch: str
    ) -> bool:
        """
        Create a new branch from an existing reference.
        Args:
            owner: GitHub organization or username
            repo: Repository name
            base_ref: Base reference (branch, tag, or commit SHA)
            new_branch: Name of the new branch to create
        Returns:
            True if branch created successfully, False otherwise
        """
        logger.info(
            "Creating branch from reference",
            extra={
                "props": {
                    "owner": owner,
                    "repo": repo,
                    "base_ref": base_ref,
                    "new_branch": new_branch
                }
            }
        )
        try:
            # Get the SHA of the base reference
            endpoint = f"/repos/{owner}/{repo}/git/ref/heads/{base_ref}"
            response = self.github_client._make_request("GET", endpoint)
            if response.status_code != 200:
                logger.error(f"Failed to get SHA for base ref '{base_ref}': {response.status_code}")
                return False
            base_sha = response.json()["object"]["sha"]
            logger.debug(f"Got base SHA: {base_sha[:8]}...")
            # Create the new branch
            endpoint = f"/repos/{owner}/{repo}/git/refs"
            payload = {"ref": f"refs/heads/{new_branch}", "sha": base_sha}
            response = self.github_client._make_request("POST", endpoint, json_data=payload)
            if response.status_code == 201:
                logger.info(f"Branch '{new_branch}' created successfully")
                return True
            else:
                logger.error(f"Failed to create branch '{new_branch}': {response.status_code}")
                return False
        except GitHubAPIError as e:
            logger.error(f"Error creating branch: {e.message}")
            return False
class PRManager:
    """Manages GitHub pull request operations."""
    def __init__(self, github_client: GitHubClient):
        """
        Initialize PR manager.
        Args:
            github_client: GitHub client instance
        """
        self.github_client = github_client
        logger.info("PR manager initialized")
    def create_pull_request(
        self,
        owner: str,
        repo: str,
        base: str,
        head: str,
        title: str,
        body: str
    ) -> bool:
        """
        Create a Pull Request on GitHub.
        Args:
            owner: GitHub organization or username
            repo: Repository name
            base: Base branch for the PR
            head: Head branch for the PR
            title: PR title
            body: PR description/body
        Returns:
            True if PR created successfully, False otherwise
        """
        logger.info(
            "Creating pull request",
            extra={
                "props": {
                    "owner": owner,
                    "repo": repo,
                    "base": base,
                    "head": head,
                    "title": title
                }
            }
        )
        endpoint = f"/repos/{owner}/{repo}/pulls"
        payload = {"title": title, "body": body, "head": head, "base": base}
        try:
            response = self.github_client._make_request("POST", endpoint, json_data=payload)
            if response.status_code == 201:
                logger.info("Pull request created successfully")
                return True
            else:
                logger.error(f"Failed to create pull request: {response.status_code}")
                return False
        except GitHubAPIError as e:
            logger.error(f"Error creating pull request: {e.message}")
            return False
    def auto_merge_pull_request(self, owner: str, repo: str, branch_name: str) -> bool:
        """
        Automatically merge a Pull Request.
        Args:
            owner: GitHub organization or username
            repo: Repository name
            branch_name: Branch name of the PR to merge
        Returns:
            True if PR was merged successfully, False otherwise
        """
        logger.info(f"Auto-merging PR for branch {branch_name}")
        try:
            # First, get the PR number for the branch
            endpoint = f"/repos/{owner}/{repo}/pulls"
            params = {"head": f"{owner}:{branch_name}"}
            response = self.github_client._make_request("GET", endpoint, params=params)
            if response.status_code != 200 or not response.json():
                logger.error(f"Failed to find PR for branch {branch_name}")
                return False
            pr_number = response.json()[0]["number"]
            logger.info(f"Found PR #{pr_number} for branch {branch_name}")
            # Now merge the PR
            merge_endpoint = f"/repos/{owner}/{repo}/pulls/{pr_number}/merge"
            merge_payload = {
                "merge_method": "squash",
                "commit_title": f"Merge PR #{pr_number}: Add pipeline workflow",
                "commit_message": "Auto-merge pipeline workflow addition",
            }
            response = self.github_client._make_request("PUT", merge_endpoint, json_data=merge_payload)
            if response.status_code == 200:
                logger.info(f"PR #{pr_number} merged successfully!")
                return True
            else:
                logger.error(f"Failed to merge PR #{pr_number}: {response.status_code}")
                return False
        except GitHubAPIError as e:
            logger.error(f"Error auto-merging PR: {e.message}")
            return False
class WorkflowGenerator:
    """Generates GitHub Actions workflow content."""
    @staticmethod
    def generate_workflow_steps(pipeline_steps: Optional[List[Any]]) -> str:
        """
        Generate GitHub Actions workflow steps based on pipeline configuration.
        Args:
            pipeline_steps: List of pipeline step objects from the API
        Returns:
            YAML string representing the workflow steps
        """
        if not pipeline_steps:
            return WorkflowGenerator.generate_default_workflow_steps()
        workflow_steps = []
        for i, step in enumerate(pipeline_steps, 1):
            # Access attributes directly since these are Pydantic model objects
            step_name = getattr(step, "name", f"Step {i}")
            step_type = getattr(step, "type", "run")
            if step_type == "run":
                command = getattr(step, "command", 'echo "No command specified"')
                if command:
                    workflow_steps.append(
                        f"""    - name: {step_name}
      run: |
        echo "Executing: {command}"
        {command}
        echo "Step completed successfully"
"""
                    )
                else:
                    workflow_steps.append(
                        f"""    - name: {step_name}
      run: |
        echo "No command specified for run step"
        echo "Step completed successfully"
"""
                    )
            elif step_type == "build":
                dockerfile = getattr(step, "dockerfile", "./Dockerfile")
                ecr_repo = getattr(step, "ecr_repo", "my-app-repo")
                workflow_steps.append(
                    f"""    - name: {step_name}
      run: |
        echo "Building Docker image from {dockerfile}"
        echo "Target ECR repository: {ecr_repo}"
        echo "Simulating Docker build..."
        sleep 3
        echo "Docker build completed successfully"
"""
                )
            elif step_type == "deploy":
                manifest = getattr(step, "manifest", "./k8s/deployment.yaml")
                workflow_steps.append(
                    f"""    - name: {step_name}
      run: |
        echo "Deploying using manifest: {manifest}"
        echo "Simulating Kubernetes deployment..."
        sleep 2
        echo "Deployment completed successfully"
"""
                )
            else:
                # Fallback for unknown step types
                workflow_steps.append(
                    f"""    - name: {step_name}
      run: |
        echo "Executing {step_type} step: {step_name}"
        echo "Step completed successfully"
"""
                )
        return "\n".join(workflow_steps)
    @staticmethod
    def generate_default_workflow_steps() -> str:
        """Generate default workflow steps when no pipeline steps are provided."""
        return """    - name: Simulate build step
      run: |
        echo "Building application..."
        sleep 2
        echo "Build completed successfully"
    - name: Simulate test step
      run: |
        echo "Running tests..."
        sleep 1
        echo "All tests passed"
    - name: Simulate deploy step
      run: |
        echo "Deploying to ${{{{ github.event.inputs.environment }}}}..."
        sleep 2
        echo "Deployment completed successfully"
"""
    @staticmethod
    def generate_workflow_content(
        pipeline_id: str,
        workflow_steps: str
    ) -> str:
        """
        Generate complete workflow YAML content.
        Args:
            pipeline_id: ID of the pipeline
            workflow_steps: Generated workflow steps
        Returns:
            Complete workflow YAML content
        """
        return f"""name: "Pipeline {pipeline_id}"
on:
  workflow_dispatch:
    inputs:
      pipeline_id:
        description: 'Pipeline ID'
        required: true
        type: string
        default: '{pipeline_id}'
      repo_url:
        description: 'Repository URL'
        required: true
        type: string
      branch:
        description: 'Branch name'
        required: true
        type: string
      environment:
        description: 'Deployment environment'
        required: false
        type: string
        default: 'staging'
jobs:
  pipeline:
    runs-on: ubuntu-latest
    steps:
    - name: Checkout repository
      uses: actions/checkout@v4
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - name: Pipeline execution started
      run: |
        echo "Pipeline ${{{{ github.event.inputs.pipeline_id }}}} triggered!"
        echo "Repository: ${{{{ github.event.inputs.repo_url }}}}"
        echo "Branch: ${{{{ github.event.inputs.branch }}}}"
        echo "Environment: ${{{{ github.event.inputs.environment }}}}"
        echo "Started at: $(date)"
{workflow_steps}
    - name: Pipeline execution completed
      run: |
        echo "Pipeline ${{{{ github.event.inputs.pipeline_id }}}} completed successfully!"
        echo "Finished at: $(date)"
"""
class GitHubIntegration:
    """Main integration class that orchestrates all GitHub operations."""
    def __init__(self, token: str, http_client: Optional[HTTPClient] = None):
        """
        Initialize GitHub integration.
        Args:
            token: GitHub personal access token
            http_client: HTTP client implementation
        """
        self.github_client = GitHubClient(token, http_client)
        self.workflow_manager = WorkflowManager(self.github_client)
        self.branch_manager = BranchManager(self.github_client)
        self.pr_manager = PRManager(self.github_client)
        logger.info("GitHub integration initialized")
    def trigger_workflow(
        self,
        owner: str,
        repo: str,
        workflow: str,
        ref: str,
        inputs: Dict[str, Any]
    ) -> bool:
        """
        Trigger a GitHub Actions workflow.
        Args:
            owner: GitHub organization or username
            repo: Repository name
            workflow: Workflow filename
            ref: Git reference
            inputs: Workflow inputs
        Returns:
            True if workflow was triggered successfully
        """
        return self.workflow_manager.trigger_workflow(owner, repo, workflow, ref, inputs)
    def create_pipeline_workflow(
        self,
        owner: str,
        repo: str,
        workflow_name: str,
        ref: str,
        pipeline_id: str,
        pipeline_steps: Optional[List[Any]] = None,
    ) -> bool:
        """
        Create a new GitHub Actions workflow file via Pull Request.
        Args:
            owner: GitHub organization or username
            repo: Repository name
            workflow_name: Name of the workflow file
            ref: Git reference
            pipeline_id: ID of the pipeline
            pipeline_steps: Pipeline steps configuration
        Returns:
            True if workflow was created successfully via PR
        """
        logger.info(
            "Creating pipeline workflow via PR",
            extra={
                "props": {
                    "owner": owner,
                    "repo": repo,
                    "workflow_name": workflow_name,
                    "pipeline_id": pipeline_id
                }
            }
        )
        # Create a new branch name for the workflow
        branch_name = f"add-pipeline-workflow-{pipeline_id}"
        # First, create a new branch from the base ref
        branch_created = self.branch_manager.create_branch_from_ref(owner, repo, ref, branch_name)
        if not branch_created:
            logger.error("Failed to create branch for workflow")
            return False
        # Generate workflow content
        workflow_steps = WorkflowGenerator.generate_workflow_steps(pipeline_steps)
        workflow_content = WorkflowGenerator.generate_workflow_content(pipeline_id, workflow_steps)
        # Encode the content to base64
        content_encoded = base64.b64encode(workflow_content.encode("utf-8")).decode("utf-8")
        # Create the workflow file
        endpoint = f"/repos/{owner}/{repo}/contents/.github/workflows/{workflow_name}"
        payload = {
            "message": f"Add pipeline workflow for {pipeline_id}",
            "content": content_encoded,
            "branch": branch_name,
        }
        try:
            response = self.github_client._make_request("PUT", endpoint, json_data=payload)
            if response.status_code == 201:
                logger.info("Workflow file created successfully, creating PR...")
                # Create a Pull Request
                pr_created = self.pr_manager.create_pull_request(
                    owner,
                    repo,
                    ref,
                    branch_name,
                    f"Add Pipeline Workflow for {pipeline_id}",
                    f"""## Pipeline Workflow Addition
This PR adds a new GitHub Actions workflow for pipeline **{pipeline_id}**.
### What's Added
- New workflow file: `.github/workflows/{workflow_name}`
- Manual dispatch support via `workflow_dispatch`
- Standardized pipeline execution steps
- Environment configuration support
### Workflow Features
- Manual triggering via API
- Pipeline metadata inputs
- Simulated build, test, and deploy steps
- Detailed logging and status reporting
### Usage
The workflow can be triggered manually or via the Delivery-Bot API with:
- Pipeline ID
- Repository URL
- Branch name
- Environment (optional, defaults to staging)
### Review Required
Please review the workflow configuration and approve if everything looks correct.
""",
                )
                if pr_created:
                    logger.info("Pipeline workflow created successfully via PR")
                    return True
                else:
                    logger.error("Workflow file created but PR failed")
                    return False
            else:
                logger.error(f"Failed to create workflow file: {response.status_code}")
                return False
        except GitHubAPIError as e:
            logger.error(f"Error creating workflow: {e.message}")
            return False
    def ensure_pipeline_workflow(
        self,
        owner: str,
        repo: str,
        workflow_name: str,
        ref: str,
        pipeline_id: str,
        pipeline_steps: Optional[List[Any]] = None,
    ) -> bool:
        """
        Ensure a pipeline workflow exists, creating it via Pull Request if necessary.
        Args:
            owner: GitHub organization or username
            repo: Repository name
            workflow_name: Name of the workflow file
            ref: Git reference
            pipeline_id: ID of the pipeline
            pipeline_steps: Pipeline steps configuration
        Returns:
            True if workflow exists or was created successfully
        """
        logger.info(f"Ensuring pipeline workflow exists: {workflow_name}")
        try:
            # Check if workflow already exists
            if self.workflow_manager.workflow_exists(owner, repo, workflow_name, ref):
                logger.info(f"Workflow {workflow_name} already exists")
                return True
            # Create the workflow via Pull Request if it doesn't exist
            logger.info(f"Creating workflow {workflow_name} via PR")
            return self.create_pipeline_workflow(
                owner, repo, workflow_name, ref, pipeline_id, pipeline_steps
            )
        except Exception as e:
            logger.error(f"Error ensuring pipeline workflow: {e}")
            return False
    def create_and_merge_workflow_pr(
        self,
        owner: str,
        repo: str,
        workflow_name: str,
        ref: str,
        pipeline_id: str,
        pipeline_steps: Optional[List[Any]] = None,
    ) -> bool:
        """
        Create a GitHub Actions workflow file and automatically merge the Pull Request.
        Args:
            owner: GitHub organization or username
            repo: Repository name
            workflow_name: Name of the workflow file
            ref: Git reference
            pipeline_id: ID of the pipeline
            pipeline_steps: Pipeline steps configuration
        Returns:
            True if workflow was created and merged successfully
        """
        logger.info(f"Creating and auto-merging workflow for pipeline {pipeline_id}")
        # Create a new branch name for the workflow
        branch_name = f"add-pipeline-workflow-{pipeline_id}"
        # First, try to create a new branch from the user's specified ref
        # If that fails, fall back to the default branch (main)
        branch_created = self.branch_manager.create_branch_from_ref(owner, repo, ref, branch_name)
        if not branch_created:
            logger.warning(f"Failed to create branch {branch_name} from {ref}, trying main branch...")
            # Fall back to main branch if user's specified branch doesn't exist
            branch_created = self.branch_manager.create_branch_from_ref(owner, repo, "main", branch_name)
            if not branch_created:
                logger.error(f"Failed to create branch {branch_name} from main branch")
                return False
            else:
                logger.info(f"Created branch {branch_name} from main branch (fallback)")
        else:
            logger.info(f"Created branch {branch_name} from {ref}")
        # Generate workflow content
        workflow_steps = WorkflowGenerator.generate_workflow_steps(pipeline_steps)
        workflow_content = WorkflowGenerator.generate_workflow_content(pipeline_id, workflow_steps)
        # Encode the content to base64
        content_encoded = base64.b64encode(workflow_content.encode("utf-8")).decode("utf-8")
        # Create the workflow file
        endpoint = f"/repos/{owner}/{repo}/contents/.github/workflows/{workflow_name}"
        payload = {
            "message": f"Add pipeline workflow for {pipeline_id}",
            "content": content_encoded,
            "branch": branch_name,
        }
        try:
            response = self.github_client._make_request("PUT", endpoint, json_data=payload)
            if response.status_code == 201:
                logger.info("Workflow file created successfully, creating PR...")
                # Create a Pull Request
                pr_created = self.pr_manager.create_pull_request(
                    owner,
                    repo,
                    "main",  # Always create PR to main branch
                    branch_name,
                    f"Add Pipeline Workflow for {pipeline_id}",
                    f"""## Pipeline Workflow Addition
This PR adds a new GitHub Actions workflow for pipeline **{pipeline_id}**.
### What's Added
- New workflow file: `.github/workflows/{workflow_name}`
- Manual dispatch support via `workflow_dispatch`
- Standardized pipeline execution steps
- Environment configuration support
### Workflow Features
- Manual triggering via API
- Pipeline metadata inputs
- Simulated build, test, and deploy steps
- Detailed logging and status reporting
### Usage
The workflow can be triggered manually or via the Delivery-Bot API with:
- Pipeline ID
- Repository URL
- Branch name
- Environment (optional, defaults to staging)
### Auto-Merge
This PR will be automatically merged to make the workflow immediately available.
""",
                )
                if pr_created:
                    logger.info("Pull request created successfully, auto-merging...")
                    # Auto-merge the PR
                    pr_merged = self.pr_manager.auto_merge_pull_request(owner, repo, branch_name)
                    if pr_merged:
                        logger.info("Pull request auto-merged successfully!")
                        return True
                    else:
                        logger.error("Failed to auto-merge pull request")
                        return False
                else:
                    logger.error("Failed to create pull request")
                    return False
            else:
                logger.error(f"Failed to create workflow file: {response.status_code}")
                if response.status_code == 422:
                    logger.info("This usually means the workflow file already exists")
                return False
        except GitHubAPIError as e:
            logger.error(f"Error creating workflow: {e.message}")
            return False
# Backward compatibility functions for existing code
def trigger_github_workflow(
    owner: str, repo: str, workflow: str, ref: str, token: str, inputs: dict
) -> int:
    """
    Backward compatibility function for triggering GitHub workflows.
    Args:
        owner: GitHub organization or username
        repo: Repository name
        workflow: Workflow filename
        ref: Git reference
        token: GitHub personal access token
        inputs: Workflow inputs
    Returns:
        HTTP status code from GitHub API (204 for success, error codes for failures)
    """
    try:
        integration = GitHubIntegration(token)
        return integration.workflow_manager.trigger_workflow(owner, repo, workflow, ref, inputs, return_status_code=True)
    except Exception:
        return 500
def create_pipeline_workflow(
    owner: str,
    repo: str,
    workflow_name: str,
    ref: str,
    token: str,
    pipeline_id: str,
    pipeline_steps: list = None,
) -> bool:
    """
    Backward compatibility function for creating pipeline workflows.
    Args:
        owner: GitHub organization or username
        repo: Repository name
        workflow_name: Name of the workflow file
        ref: Git reference
        token: GitHub personal access token
        pipeline_id: ID of the pipeline
        pipeline_steps: Pipeline steps configuration
    Returns:
        True if workflow was created successfully
    """
    integration = GitHubIntegration(token)
    return integration.create_pipeline_workflow(
        owner, repo, workflow_name, ref, pipeline_id, pipeline_steps
    )
def workflow_exists(
    owner: str, repo: str, workflow_name: str, ref: str, token: str
) -> bool:
    """
    Backward compatibility function for checking workflow existence.
    Args:
        owner: GitHub organization or username
        repo: Repository name
        workflow_name: Name of the workflow file
        ref: Git reference
        token: GitHub personal access token
    Returns:
        True if workflow exists, False otherwise
    """
    integration = GitHubIntegration(token)
    return integration.workflow_manager.workflow_exists(owner, repo, workflow_name, ref)
def ensure_pipeline_workflow(
    owner: str,
    repo: str,
    workflow_name: str,
    ref: str,
    token: str,
    pipeline_id: str,
    pipeline_steps: list = None,
) -> bool:
    """
    Backward compatibility function for ensuring pipeline workflows.
    Args:
        owner: GitHub organization or username
        repo: Repository name
        workflow_name: Name of the workflow file
        ref: Git reference
        token: GitHub personal access token
        pipeline_id: ID of the pipeline
        pipeline_steps: Pipeline steps configuration
    Returns:
        True if workflow exists or was created successfully
    """
    integration = GitHubIntegration(token)
    return integration.ensure_pipeline_workflow(
        owner, repo, workflow_name, ref, pipeline_id, pipeline_steps
    )
def create_and_merge_workflow_pr(
    owner: str,
    repo: str,
    workflow_name: str,
    ref: str,
    token: str,
    pipeline_id: str,
    pipeline_steps: list = None,
) -> bool:
    """
    Backward compatibility function for creating and merging workflow PRs.
    Args:
        owner: GitHub organization or username
        repo: Repository name
        workflow_name: Name of the workflow file
        ref: Git reference
        token: GitHub personal access token
        pipeline_id: ID of the pipeline
        pipeline_steps: Pipeline steps configuration
    Returns:
        True if workflow was created and merged successfully
    """
    integration = GitHubIntegration(token)
    return integration.create_and_merge_workflow_pr(
        owner, repo, workflow_name, ref, pipeline_id, pipeline_steps
    )
