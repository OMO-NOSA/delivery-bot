from __future__ import annotations

import json
import time
from typing import Optional

import requests
import typer
from rich import box
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="CLI for interacting with the Delivery-Bot API")
console = Console()
DEFAULT_BASE = "http://localhost:8080"


def _base_url(base: Optional[str]) -> str:
    return base or DEFAULT_BASE


@app.command("create")
def create_pipeline(
    config: str = typer.Argument(..., help="Path to JSON pipeline file"),
    base: Optional[str] = typer.Option(None, "--base", "-b", help="Base API URL"),
):
    """Create a new pipeline from a JSON configuration file."""
    try:
        with open(config, "r") as f:
            data = json.load(f)
        r = requests.post(f"{_base_url(base)}/pipelines", json=data, timeout=10)
        r.raise_for_status()
        console.print(f"[green]Created pipeline:[/green] {r.json()['id']}")
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Configuration file '{config}' not found")
        raise typer.Exit(1)
    except json.JSONDecodeError:
        console.print(
            f"[red]Error:[/red] Invalid JSON in configuration file '{config}'"
        )
        raise typer.Exit(1)
    except requests.RequestException as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("list")
def list_pipelines(
    base: Optional[str] = typer.Option(None, "--base", "-b", help="Base API URL"),
):
    """List all available pipelines."""
    try:
        r = requests.get(f"{_base_url(base)}/pipelines", timeout=10)
        r.raise_for_status()
        items = r.json()

        if not items:
            console.print("[yellow]No pipelines found[/yellow]")
            return

        table = Table(title="Pipelines", box=box.SIMPLE_HEAVY)
        table.add_column("ID", style="bold cyan")
        table.add_column("Name", style="bold")
        table.add_column("Repository", style="blue")
        table.add_column("Branch", style="green")
        table.add_column("Steps", style="yellow")

        for p in items:
            step_count = len(p.get("steps", []))
            table.add_row(
                p["id"][:8] + "...",
                p["name"],
                p["repo_url"],
                p.get("branch", "main"),
                str(step_count),
            )
        console.print(table)
    except requests.RequestException as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("get")
def get_pipeline(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID to retrieve"),
    base: Optional[str] = typer.Option(None, "--base", "-b", help="Base API URL"),
):
    """Get detailed information about a specific pipeline."""
    try:
        r = requests.get(f"{_base_url(base)}/pipelines/{pipeline_id}", timeout=10)
        r.raise_for_status()
        console.print_json(data=r.json())
    except requests.RequestException as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("delete")
def delete_pipeline(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID to delete"),
    base: Optional[str] = typer.Option(None, "--base", "-b", help="Base API URL"),
):
    """Delete a pipeline by ID."""
    try:
        r = requests.delete(f"{_base_url(base)}/pipelines/{pipeline_id}", timeout=10)
        if r.status_code == 204:
            console.print(f"[green]Deleted pipeline[/green] {pipeline_id}")
        else:
            r.raise_for_status()
    except requests.RequestException as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("update")
def update_pipeline(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID to update"),
    config: str = typer.Argument(..., help="Path to JSON pipeline file"),
    base: Optional[str] = typer.Option(None, "--base", "-b", help="Base API URL"),
):
    """Update an existing pipeline with new configuration."""
    try:
        with open(config, "r") as f:
            data = json.load(f)
        r = requests.put(
            f"{_base_url(base)}/pipelines/{pipeline_id}", json=data, timeout=10
        )
        r.raise_for_status()
        console.print(f"[green]Updated pipeline:[/green] {pipeline_id}")
    except FileNotFoundError:
        console.print(f"[red]Error:[/red] Configuration file '{config}' not found")
        raise typer.Exit(1)
    except json.JSONDecodeError:
        console.print(
            f"[red]Error:[/red] Invalid JSON in configuration file '{config}'"
        )
        raise typer.Exit(1)
    except requests.RequestException as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("trigger")
def trigger(
    pipeline_id: str = typer.Argument(..., help="Pipeline ID to trigger"),
    base: Optional[str] = typer.Option(None, "--base", "-b", help="Base API URL"),
):
    """Trigger execution of a pipeline."""
    try:
        r = requests.post(
            f"{_base_url(base)}/pipelines/{pipeline_id}/trigger", timeout=10
        )
        r.raise_for_status()
        out = r.json()
        console.print(
            f"[green]Triggered run[/green]: {out['run_id']} (status: {out['status']})"
        )
        console.print(
            f"[blue]Tip:[/blue] Use 'python -m cli.cli watch {out['run_id']}' to monitor execution"
        )
    except requests.RequestException as e:
        console.print(f"[red]API Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("watch")
def watch(
    run_id: str = typer.Argument(..., help="Run ID to watch"),
    base: Optional[str] = typer.Option(None, "--base", "-b", help="Base API URL"),
):
    """Watch a pipeline run in real-time."""
    try:
        url = f"{_base_url(base)}/runs/{run_id}"
        status = "pending"
        last_len = 0

        console.print(f"[blue]Watching run:[/blue] {run_id}")
        console.print("[yellow]Waiting for updates...[/yellow]")

        while status in ("pending", "running"):
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            run = r.json()
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
        console.print(f"[red]API Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("status")
def status(
    base: Optional[str] = typer.Option(None, "--base", "-b", help="Base API URL"),
):
    """Check the health status of the Delivery-Bot API."""
    try:
        r = requests.get(f"{_base_url(base)}/health", timeout=5)
        if r.status_code == 200:
            console.print("[green]Delivery-Bot API is running[/green]")
            console.print(f"[blue]Base URL:[/blue] {_base_url(base)}")
        else:
            console.print(
                f"[yellow]API responded with status: {r.status_code}[/yellow]"
            )
    except requests.RequestException as e:
        console.print(f"[red]Cannot connect to API:[/red] {e}")
        console.print(f"[blue]Attempted URL:[/blue] {_base_url(base)}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
