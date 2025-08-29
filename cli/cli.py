"""
CLI for interacting with the Delivery-Bot API.
This module provides a command-line interface for managing CI/CD pipelines,
including creation, updates, monitoring, and triggering of pipeline executions.
Commands:
    create: Create a new pipeline from JSON configuration
    list: List all available pipelines
    get: Get detailed information about a specific pipeline
    update: Update an existing pipeline
    delete: Delete a pipeline
    trigger: Trigger execution of a pipeline
    watch: Monitor a pipeline run in real-time
    status: Check API health status
Author: Nosa Omorodion
Version: 0.2.0
"""
import json
import logging
import os
import time
from typing import Any, Dict, Optional
import requests
import typer
from rich import box
from rich.console import Console
from rich.table import Table
app = typer.Typer(help="CLI for interacting with the Delivery-Bot API")
console = Console()
# Configuration
DEFAULT_BASE = os.getenv("DELIVERY_BOT_API_URL", "http://localhost:8080")
DEFAULT_TIMEOUT = int(os.getenv("DELIVERY_BOT_TIMEOUT", "10"))
MAX_WATCH_TIME = int(os.getenv("DELIVERY_BOT_MAX_WATCH_TIME", "300"))  # 5 minutes
def _base_url(base: Optional[str]) -> str:
    """Get the base URL for API requests."""
    return base or DEFAULT_BASE
def _setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
class APIClient:
    """Centralized API client for handling HTTP requests."""
    def __init__(self, base_url: str, timeout: int = DEFAULT_TIMEOUT):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
    def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> requests.Response:
        """
        Make an HTTP request to the API.
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            json_data: JSON data to send (for POST/PUT)
            **kwargs: Additional request arguments
        Returns:
            Response object
        Raises:
            requests.RequestException: For HTTP errors
        """
        url = f"{self.base_url}{endpoint}"
        # Set default timeout if not provided
        if "timeout" not in kwargs:
            kwargs["timeout"] = self.timeout
        try:
            if method.upper() == "GET":
                response = self.session.get(url, **kwargs)
            elif method.upper() == "POST":
                response = self.session.post(url, json=json_data, **kwargs)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=json_data, **kwargs)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            # Log the full exception for debugging
            logging.debug(f"API request failed: {e}", exc_info=True)
            raise
    def get(self, endpoint: str, **kwargs) -> requests.Response:
        """Make a GET request."""
        return self._make_request("GET", endpoint, **kwargs)
    def post(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None, **kwargs) -> requests.Response:
        """Make a POST request."""
        return self._make_request("POST", endpoint, json_data, **kwargs)
    def put(self, endpoint: str, json_data: Optional[Dict[str, Any]] = None, **kwargs) -> requests.Response:
        """Make a PUT request."""
        return self._make_request("PUT", endpoint, json_data, **kwargs)
    def delete(self, endpoint: str, **kwargs) -> requests.Response:
        """Make a DELETE request."""
        return self._make_request("DELETE", endpoint, **kwargs)
def _load_pipeline_config(config_path: str) -> Dict[str, Any]:
    """
    Load pipeline configuration from JSON file.
    Args:
        config_path: Path to the JSON configuration file
    Returns:
        Pipeline configuration data
    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If config file has invalid JSON
    """
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file '{config_path}' not found")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON in configuration file '{config_path}': {e}", e.doc, e.pos)
def _handle_api_error(error: requests.RequestException, operation: str) -> None:
    """
    Handle API errors consistently.
    Args:
        error: The request exception that occurred
        operation: Description of the operation that failed
    """
    if hasattr(error, 'response') and error.response is not None:
        console.print(f"[red]API Error ({operation}):[/red] {error.response.status_code} - {error}")
    else:
        console.print(f"[red]API Error ({operation}):[/red] {error}")
    # Log full exception for debugging
    logging.debug(f"API error during {operation}", exc_info=True)
@app.command("create")
def create_pipeline(
    config: str = typer.Argument(..., help="Path to JSON pipeline file"),
    base: Optional[str] = typer.Option(None, "--base", "-b", help="Base API URL"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Create a new pipeline from a JSON configuration file."""
    _setup_logging(verbose)
    try:
        data = _load_pipeline_config(config)
        api_client = APIClient(_base_url(base))
        response = api_client.post("/pipelines", json_data=data)
        pipeline_id = response.json()["id"]
        console.print(f"[green]Created pipeline:[/green] {pipeline_id}")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except requests.RequestException as e:
        _handle_api_error(e, "pipeline creation")
        raise typer.Exit(1)
@app.command("list")
def list_pipelines(
    base: Optional[str] = typer.Option(None, "--base", "-b", help="Base API URL"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """List all available pipelines."""
    _setup_logging(verbose)
    try:
        api_client = APIClient(_base_url(base))
        response = api_client.get("/pipelines")
        items = response.json()
        if not items:
            console.print("[yellow]No pipelines found[/yellow]")
            return
        table = Table(title="Pipelines", box=box.SIMPLE_HEAVY)
        table.add_column("ID", style="bold cyan")
        table.add_column("Name", style="bold")
        table.add_column("Repository", style="blue")
        table.add_column("Branch", style="green")
        table.add_column("Steps", style="yellow")
        for pipeline in items:
            step_count = len(pipeline.get("steps", []))
            table.add_row(
                pipeline["id"][:8] + "...",
                pipeline["name"],
                pipeline["repo_url"],
                pipeline.get("branch", "main"),
                str(step_count),
            )
        console.print(table)
    except requests.RequestException as e:
        _handle_api_error(e, "listing pipelines")
        raise typer.Exit(1)
@app.command("get")
def get_pipeline(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID to retrieve"),
    base: Optional[str] = typer.Option(None, "--base", "-b", help="Base API URL"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Get detailed information about a specific pipeline."""
    _setup_logging(verbose)
    try:
        api_client = APIClient(_base_url(base))
        response = api_client.get(f"/pipelines/{pipeline_id}")
        console.print_json(data=response.json())
    except requests.RequestException as e:
        _handle_api_error(e, f"retrieving pipeline {pipeline_id}")
        raise typer.Exit(1)
@app.command("delete")
def delete_pipeline(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID to delete"),
    base: Optional[str] = typer.Option(None, "--base", "-b", help="Base API URL"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Delete a pipeline by ID."""
    _setup_logging(verbose)
    try:
        api_client = APIClient(_base_url(base))
        response = api_client.delete(f"/pipelines/{pipeline_id}")
        if response.status_code == 204:
            console.print(f"[green]Deleted pipeline[/green] {pipeline_id}")
        else:
            response.raise_for_status()
    except requests.RequestException as e:
        _handle_api_error(e, f"deleting pipeline {pipeline_id}")
        raise typer.Exit(1)
def _update_pipeline_common(
    pipeline_id: str,
    config_path: str,
    base: Optional[str],
    verbose: bool,
    operation: str
) -> None:
    """
    Common logic for pipeline update operations.
    Args:
        pipeline_id: ID of the pipeline to update
        config_path: Path to the configuration file
        base: Base API URL
        verbose: Enable verbose logging
        operation: Description of the operation (create/update)
    """
    _setup_logging(verbose)
    try:
        data = _load_pipeline_config(config_path)
        api_client = APIClient(_base_url(base))
        if operation == "create":
            response = api_client.post("/pipelines", json_data=data)
            pipeline_id = response.json()["id"]
        else:  # update
            response = api_client.put(f"/pipelines/{pipeline_id}", json_data=data)
        console.print(f"[green]{operation.title()}d pipeline:[/green] {pipeline_id}")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)
    except requests.RequestException as e:
        _handle_api_error(e, f"pipeline {operation}")
        raise typer.Exit(1)
@app.command("update")
def update_pipeline(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID to update"),
    config: str = typer.Argument(..., help="Path to JSON pipeline file"),
    base: Optional[str] = typer.Option(None, "--base", "-b", help="Base API URL"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Update an existing pipeline with new configuration."""
    _update_pipeline_common(pipeline_id, config, base, verbose, "update")
@app.command("trigger")
def trigger(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID to trigger"),
    base: Optional[str] = typer.Option(None, "--base", "-b", help="Base API URL"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Trigger execution of a pipeline."""
    _setup_logging(verbose)
    try:
        api_client = APIClient(_base_url(base))
        response = api_client.post(f"/pipelines/{pipeline_id}/trigger")
        result = response.json()
        console.print(
            f"[green]Triggered run[/green]: {result['run_id']} (status: {result['status']})"
        )
        console.print(
            f"[blue]Tip:[/blue] Use 'python -m cli.cli watch {result['run_id']}' to monitor execution"
        )
    except requests.RequestException as e:
        _handle_api_error(e, f"triggering pipeline {pipeline_id}")
        raise typer.Exit(1)
@app.command("watch")
def watch(
    run_id: str = typer.Argument(..., help="Run ID to watch"),
    base: Optional[str] = typer.Option(None, "--base", "-b", help="Base API URL"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
    max_time: Optional[int] = typer.Option(None, "--max-time", "-t", help="Maximum watch time in seconds"),
) -> None:
    """Watch a pipeline run in real-time."""
    _setup_logging(verbose)
    try:
        api_client = APIClient(_base_url(base))
        status = "pending"
        last_len = 0
        start_time = time.time()
        max_watch_time = max_time or MAX_WATCH_TIME
        console.print(f"[blue]Watching run:[/blue] {run_id}")
        console.print(f"[blue]Max watch time:[/blue] {max_watch_time} seconds")
        console.print("[yellow]Waiting for updates...[/yellow]")
        while status in ("pending", "running"):
            # Check if we've exceeded max time
            if time.time() - start_time > max_watch_time:
                console.print(f"[yellow]Maximum watch time ({max_watch_time}s) exceeded. Exiting.[/yellow]")
                break
            response = api_client.get(f"/runs/{run_id}")
            run = response.json()
            status = run["status"]
            logs = run.get("logs", [])
            # Print new log lines
            for line in logs[last_len:]:
                console.print(f"  {line}")
            last_len = len(logs)
            if status in ("pending", "running"):
                time.sleep(1)
        # Final status
        if status == "succeeded":
            console.print("[green]Run completed successfully![/green]")
        elif status == "failed":
            console.print("[red]Run failed[/red]")
        elif status == "cancelled":
            console.print("[yellow]Run was cancelled[/yellow]")
        else:
            console.print(f"[blue]Run finished with status: {status}[/blue]")
    except requests.RequestException as e:
        _handle_api_error(e, f"watching run {run_id}")
        raise typer.Exit(1)
@app.command("status")
def status(
    base: Optional[str] = typer.Option(None, "--base", "-b", help="Base API URL"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
) -> None:
    """Check the health status of the Delivery-Bot API."""
    _setup_logging(verbose)
    try:
        api_client = APIClient(_base_url(base), timeout=5)
        response = api_client.get("/health")
        if response.status_code == 200:
            health_data = response.json()
            console.print("[green]Delivery-Bot API is running[/green]")
            console.print(f"[blue]Base URL:[/blue] {_base_url(base)}")
            console.print(f"[blue]Version:[/blue] {health_data.get('version', 'unknown')}")
            console.print(f"[blue]Environment:[/blue] {health_data.get('environment', 'unknown')}")
        else:
            console.print(f"[yellow]API responded with status: {response.status_code}[/yellow]")
    except requests.RequestException as e:
        console.print(f"[red]Cannot connect to API:[/red] {e}")
        console.print(f"[blue]Attempted URL:[/blue] {_base_url(base)}")
        raise typer.Exit(1)
if __name__ == "__main__":
    app()
