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
- Error handling for API failures

Functions:
    trigger_github_workflow: Dispatch a GitHub Actions workflow
    create_pipeline_workflow: Create a new workflow file via Pull Request
    create_branch_from_ref: Create a new branch from an existing reference
    create_pull_request: Create a Pull Request on GitHub
    workflow_exists: Check if a workflow file exists
    ensure_pipeline_workflow: Ensure a workflow exists, creating via PR if needed

Dependencies:
    - requests: For HTTP API calls to GitHub
    - GitHub token: Personal access token with workflow permissions

Author: Nosa Omorodion
Version: 0.1.0
"""

import base64
import json

import requests


def generate_workflow_steps(pipeline_steps: list) -> str:
    """
    Generate GitHub Actions workflow steps based on pipeline configuration.

    Args:
        pipeline_steps (list): List of pipeline step objects from the API

    Returns:
        str: YAML string representing the workflow steps
    """
    if not pipeline_steps:
        return generate_default_workflow_steps()

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


def trigger_github_workflow(
    owner: str, repo: str, workflow: str, ref: str, token: str, inputs: dict
) -> int:
    """
    Trigger a GitHub Actions workflow via the REST API.

    Sends a workflow dispatch event to GitHub Actions, which can trigger
    automated builds, deployments, or other CI/CD processes in parallel
    with the internal pipeline execution.

    Args:
        owner (str): GitHub organization or username that owns the repository
        repo (str): Repository name where the workflow is defined
        workflow (str): Filename of the workflow (e.g., 'pipeline.yml')
        ref (str): Git reference (branch, tag, or commit SHA) to run against
        token (str): GitHub personal access token with workflow permissions
        inputs (dict): Key-value pairs to pass as workflow inputs

    Returns:
        int: HTTP status code from the GitHub API
            - 204: Workflow successfully triggered
            - 401: Authentication failed (invalid token)
            - 404: Repository or workflow not found
            - 422: Validation error (invalid inputs or ref)

    Raises:
        requests.exceptions.RequestException: For network errors or timeouts
        requests.exceptions.Timeout: If the request times out (15s timeout)

    Example:
        >>> status = trigger_github_workflow(
        ...     owner="myorg",
        ...     repo="myapp",
        ...     workflow="deploy.yml",
        ...     ref="main",
        ...     token="ghp_xxxxxxxxxxxx",
        ...     inputs={"environment": "staging", "version": "1.2.3"}
        ... )
        >>> if status == 204:
        ...     print("Workflow triggered successfully")

    GitHub API Reference:
        https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event

    Token Permissions:
        The token must have 'actions:write' permission for the repository.
        For organization repositories, additional permissions may be required.

    Note:
        The function returns immediately after triggering the workflow.
        It does not wait for the workflow to complete or monitor its status.
    """
    # Construct the GitHub API URL for workflow dispatch
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"

    # Set required headers for GitHub API
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "cicd-pipelines-api",
    }

    # Prepare the request payload
    payload = {"ref": ref, "inputs": inputs}

    # Send the dispatch request with timeout
    response = requests.post(url, headers=headers, json=payload, timeout=15)

    return response.status_code


def create_branch_from_ref(
    owner: str, repo: str, base_ref: str, new_branch: str, token: str
) -> bool:
    """
    Create a new branch from an existing reference.

    Args:
        owner (str): GitHub organization or username
        repo (str): Repository name
        base_ref (str): Base reference (branch, tag, or commit SHA)
        new_branch (str): Name of the new branch to create
        token (str): GitHub personal access token

    Returns:
        bool: True if branch created successfully, False otherwise
    """
    try:
        print(f"Attempting to create branch '{new_branch}' from base '{base_ref}'")

        # First, get the SHA of the base reference
        url = f"https://api.github.com/repos/{owner}/{repo}/git/ref/heads/{base_ref}"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "cicd-pipelines-api",
        }

        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(
                f"Failed to get SHA for base ref '{base_ref}'. Status: {response.status_code}"
            )
            print(f"Response: {response.text}")
            return False

        base_sha = response.json()["object"]["sha"]
        print(f"Got base SHA: {base_sha[:8]}...")

        # Now create the new branch
        url = f"https://api.github.com/repos/{owner}/{repo}/git/refs"
        payload = {"ref": f"refs/heads/{new_branch}", "sha": base_sha}

        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 201:
            print(f"Branch '{new_branch}' created successfully")
            return True
        else:
            print(
                f"Failed to create branch '{new_branch}'. Status: {response.status_code}"
            )
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print(f"Exception in create_branch_from_ref: {e}")
        return False


def create_pull_request(
    owner: str, repo: str, base: str, head: str, title: str, body: str, token: str
) -> bool:
    """
    Create a Pull Request on GitHub.

    Args:
        owner (str): GitHub organization or username
        repo (str): Repository name
        base (str): Base branch for the PR
        head (str): Head branch for the PR
        title (str): PR title
        body (str): PR description/body
        token (str): GitHub personal access token

    Returns:
        bool: True if PR created successfully, False otherwise
    """
    try:
        print(f"Creating Pull Request: {head} -> {base}")
        print(f"Title: {title}")

        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "cicd-pipelines-api",
        }

        payload = {"title": title, "body": body, "head": head, "base": base}

        print(f"PR payload: {payload}")

        response = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"PR creation response: {response.status_code}")

        if response.status_code == 201:
            print("Pull Request created successfully")
            return True
        else:
            print(f"Failed to create Pull Request. Status: {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print(f"Exception in create_pull_request: {e}")
        return False


def create_pipeline_workflow(
    owner: str,
    repo: str,
    workflow_name: str,
    ref: str,
    token: str,
    pipeline_id: str,
    pipeline_steps: list = None,
) -> int:
    """
    Create a new GitHub Actions workflow file via Pull Request.

    Creates a workflow file that can be manually triggered via the GitHub API.
    Instead of writing directly to the repository, this creates a Pull Request
    for proper code review and collaboration.

    Args:
        owner (str): GitHub organization or username that owns the repository
        repo (str): Repository name where the workflow will be created
        workflow_name (str): Name of the workflow file (e.g., 'pipeline.yml')
        ref (str): Git reference (branch, tag, or commit SHA) to create the workflow on
        token (str): GitHub personal access token with contents:write permission
        pipeline_id (str): ID of the pipeline this workflow is associated with

    Returns:
        int: HTTP status code from the GitHub API
            - 201: Pull Request created successfully
            - 401: Authentication failed (invalid token)
            - 403: Permission denied (insufficient permissions)
            - 404: Repository not found
            - 422: Validation error

    Raises:
        requests.exceptions.RequestException: For network errors or timeouts
        requests.exceptions.Timeout: If the request times out (15s timeout)

    Note:
        The token must have 'contents:write' permission for the repository.
        The workflow will be created in a new branch via Pull Request.
    """
    # Create a new branch name for the workflow
    branch_name = f"add-pipeline-workflow-{pipeline_id}"

    # First, create a new branch from the base ref
    branch_created = create_branch_from_ref(owner, repo, ref, branch_name, token)
    if not branch_created:
        return 500  # Internal error creating branch

    # Construct the GitHub API URL for creating/updating file content in the new branch
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/.github/workflows/{workflow_name}"

    # Set required headers for GitHub API
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "cicd-pipelines-api",
    }

    # Generate dynamic workflow steps based on pipeline configuration for create_pipeline_workflow function
    workflow_steps = generate_workflow_steps(pipeline_steps)

    # Create the workflow YAML content
    workflow_content = f"""name: "Pipeline {pipeline_id}"

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
        
    - name: Simulate build step
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
        
    - name: Pipeline execution completed
      run: |
        echo "Pipeline ${{{{ github.event.inputs.pipeline_id }}}} completed successfully!"
        echo "Finished at: $(date)"
"""

    # Encode the content to base64
    content_encoded = base64.b64encode(workflow_content.encode("utf-8")).decode("utf-8")

    # Prepare the request payload for the new branch
    payload = {
        "message": f"Add pipeline workflow for {pipeline_id}",
        "content": content_encoded,
        "branch": branch_name,
    }

    # Send the create request with timeout
    response = requests.put(url, headers=headers, json=payload, timeout=15)

    if response.status_code == 201:
        # File created successfully, now create a Pull Request
        pr_created = create_pull_request(
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
            token,
        )

        if pr_created:
            return 201  # Success: PR created
        else:
            return 500  # File created but PR failed
    else:
        return response.status_code


def workflow_exists(
    owner: str, repo: str, workflow_name: str, ref: str, token: str
) -> bool:
    """
    Check if a GitHub Actions workflow file exists.

    Args:
        owner (str): GitHub organization or username that owns the repository
        repo (str): Repository name to check
        workflow_name (str): Name of the workflow file to check
        ref (str): Git reference (branch, tag, or commit SHA) to check (not used for workflow lookup)
        token (str): GitHub personal access token

    Returns:
        bool: True if the workflow file exists, False otherwise

    Raises:
        requests.exceptions.RequestException: For network errors or timeouts
    """
    # Construct the GitHub API URL for checking file content
    # Note: Workflows are always created in the main branch, so we check there
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/.github/workflows/{workflow_name}"

    # Set required headers for GitHub API
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "cicd-pipelines-api",
    }

    # Always check in main branch since that's where workflows are created
    params = {"ref": "main"}

    # Send the request to check if file exists
    response = requests.get(url, headers=headers, params=params, timeout=15)

    if response.status_code == 200:
        print(f"Workflow {workflow_name} found in main branch")
        return True
    else:
        print(
            f"Workflow {workflow_name} not found in main branch. Status: {response.status_code}"
        )
        return False


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
    Ensure a pipeline workflow exists, creating it via Pull Request if necessary.

    This is a convenience function that checks if a workflow exists and
    creates it via a Pull Request if it doesn't. This ensures the workflow
    is always available for triggering while maintaining proper code review.

    Args:
        owner (str): GitHub organization or username that owns the repository
        repo (str): Repository name where the workflow should exist
        workflow_name (str): Name of the workflow file
        ref (str): Git reference (branch, tag, or commit SHA)
        token (str): GitHub personal access token with necessary permissions
        pipeline_id (str): ID of the pipeline this workflow is associated with

    Returns:
        bool: True if the workflow exists or was created successfully via PR, False otherwise

    Note:
        The token must have both 'contents:write' and 'actions:write' permissions.
        If a workflow doesn't exist, a Pull Request will be created instead of
        writing directly to the repository.
    """
    try:
        # Check if workflow already exists
        if workflow_exists(owner, repo, workflow_name, ref, token):
            return True

        # Create the workflow via Pull Request if it doesn't exist
        status_code = create_pipeline_workflow(
            owner, repo, workflow_name, ref, token, pipeline_id, pipeline_steps
        )
        return status_code == 201

    except Exception:
        return False


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
    Create a GitHub Actions workflow file and automatically merge the Pull Request.

    This function creates a workflow file in a new branch, creates a Pull Request,
    and then automatically merges it to make the workflow immediately available.

    Args:
        owner (str): GitHub organization or username that owns the repository
        repo (str): Repository name where the workflow will be created
        workflow_name (str): Name of the workflow file (e.g., 'pipeline-{id}.yml')
        ref (str): Git reference (branch, tag, or commit SHA) to create the workflow on
        token (str): GitHub personal access token with contents:write permission
        pipeline_id (str): ID of the pipeline this workflow is associated with

    Returns:
        bool: True if workflow was created and merged successfully, False otherwise

    Note:
        The token must have 'contents:write' permission for the repository.
        The workflow will be created and immediately available for triggering.
    """
    print(
        f"Creating and auto-merging workflow for pipeline {pipeline_id} in {owner}/{repo}"
    )

    # Create a new branch name for the workflow
    branch_name = f"add-pipeline-workflow-{pipeline_id}"
    print(f"Creating branch: {branch_name}")

    # First, try to create a new branch from the user's specified ref
    # If that fails, fall back to the default branch (main)
    branch_created = create_branch_from_ref(owner, repo, ref, branch_name, token)
    if not branch_created:
        print(
            f"Failed to create branch {branch_name} from {ref}, trying main branch..."
        )
        # Fall back to main branch if user's specified branch doesn't exist
        branch_created = create_branch_from_ref(owner, repo, "main", branch_name, token)
        if not branch_created:
            print(f"Failed to create branch {branch_name} from main branch")
            return False
        else:
            print(f"Created branch {branch_name} from main branch (fallback)")
    else:
        print(f"Created branch {branch_name} from {ref}")

    print(f"Branch {branch_name} created successfully")

    # Construct the GitHub API URL for creating/updating file content in the new branch
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/.github/workflows/{workflow_name}"
    print(f"Creating workflow file at: {url}")

    # Set required headers for GitHub API
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "cicd-pipelines-api",
    }

    # Generate dynamic workflow steps based on pipeline configuration
    print(
        f"Generating workflow steps for {len(pipeline_steps) if pipeline_steps else 0} steps"
    )
    try:
        workflow_steps = generate_workflow_steps(pipeline_steps)
        print("Dynamic workflow steps generated successfully")
    except Exception as e:
        print(f"Error generating dynamic workflow steps: {e}")
        # Fallback to default steps
        workflow_steps = generate_default_workflow_steps()
        print("Using default workflow steps as fallback")

    # Create the workflow YAML content
    workflow_content = f"""name: "Pipeline {pipeline_id}"

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

    # Encode the content to base64
    content_encoded = base64.b64encode(workflow_content.encode("utf-8")).decode("utf-8")

    # Prepare the request payload for the new branch
    payload = {
        "message": f"Add pipeline workflow for {pipeline_id}",
        "content": content_encoded,
        "branch": branch_name,
    }

    # Send the create request with timeout
    print("Uploading workflow file...")
    response = requests.put(url, headers=headers, json=payload, timeout=15)

    print(f"Workflow file upload response: {response.status_code}")

    if response.status_code == 201:
        print("Workflow file created successfully, now creating Pull Request...")
        # File created successfully, now create a Pull Request
        # Always create PR to main branch, regardless of user's specified branch
        pr_created = create_pull_request(
            owner,
            repo,
            "main",
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
            token,
        )

        if pr_created:
            print("Pull Request created successfully, now auto-merging...")
            # Auto-merge the PR
            pr_merged = auto_merge_pull_request(owner, repo, branch_name, token)
            if pr_merged:
                print("Pull Request auto-merged successfully!")
                return True
            else:
                print("Failed to auto-merge Pull Request")
                return False
        else:
            print("Failed to create Pull Request")
            return False
    else:
        print(f"Failed to create workflow file. Status: {response.status_code}")
        if response.status_code == 422:
            print("This usually means the workflow file already exists")
        print(f"Response: {response.text}")
        return False


def auto_merge_pull_request(
    owner: str, repo: str, branch_name: str, token: str
) -> bool:
    """
    Automatically merge a Pull Request.

    Args:
        owner (str): GitHub organization or username
        repo (str): Repository name
        branch_name (str): Branch name of the PR to merge
        token (str): GitHub personal access token

    Returns:
        bool: True if PR was merged successfully, False otherwise
    """
    try:
        # First, get the PR number for the branch
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "cicd-pipelines-api",
        }

        params = {"head": f"{owner}:{branch_name}"}
        response = requests.get(url, headers=headers, params=params, timeout=15)

        if response.status_code != 200 or not response.json():
            print(f"Failed to find PR for branch {branch_name}")
            return False

        pr_number = response.json()[0]["number"]
        print(f"Found PR #{pr_number} for branch {branch_name}")

        # Now merge the PR
        merge_url = (
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/merge"
        )
        merge_payload = {
            "merge_method": "squash",
            "commit_title": f"Merge PR #{pr_number}: Add pipeline workflow",
            "commit_message": "Auto-merge pipeline workflow addition",
        }

        response = requests.put(
            merge_url, headers=headers, json=merge_payload, timeout=15
        )

        if response.status_code == 200:
            print(f"PR #{pr_number} merged successfully!")
            return True
        else:
            print(
                f"Failed to merge PR #{pr_number}. Status: {response.status_code}, Response: {response.text}"
            )
            return False

    except Exception as e:
        print(f"Exception in auto_merge_pull_request: {e}")
        return False
