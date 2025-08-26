
from __future__ import annotations
import json, time
from typing import Optional
import requests, typer
from rich.console import Console
from rich.table import Table
from rich import box

app = typer.Typer(help="CLI for interacting with the Delivery-Bot API")
console = Console()
DEFAULT_BASE = "http://localhost:8080"

def _base_url(base: Optional[str]) -> str:
    return base or DEFAULT_BASE

@app.command("create")
def create_pipeline(config: str = typer.Argument(..., help="Path to JSON pipeline file"),
                    base: Optional[str] = typer.Option(None, "--base", "-b", help="Base API URL")):
    with open(config, "r") as f:
        data = json.load(f)
    r = requests.post(f"{_base_url(base)}/pipelines", json=data, timeout=10)
    r.raise_for_status()
    console.print(f"[green]Created pipeline:[/green] {r.json()['id']}")

@app.command("list")
def list_pipelines(base: Optional[str] = typer.Option(None, "--base", "-b")):
    r = requests.get(f"{_base_url(base)}/pipelines", timeout=10)
    r.raise_for_status()
    items = r.json()
    table = Table(title="Pipelines", box=box.SIMPLE_HEAVY)
    table.add_column("ID", style="bold")
    table.add_column("Name")
    table.add_column("Repo")
    table.add_column("Branch")
    for p in items:
        table.add_row(p["id"], p["name"], p["repo_url"], p["branch"])
    console.print(table)

@app.command("get")
def get_pipeline(pipeline_id: str, base: Optional[str] = typer.Option(None, "--base", "-b")):
    r = requests.get(f"{_base_url(base)}/pipelines/{pipeline_id}", timeout=10)
    r.raise_for_status()
    console.print_json(data=r.json())

@app.command("delete")
def delete_pipeline(pipeline_id: str, base: Optional[str] = typer.Option(None, "--base", "-b")):
    r = requests.delete(f"{_base_url(base)}/pipelines/{pipeline_id}", timeout=10)
    if r.status_code == 204:
        console.print(f"[yellow]Deleted pipeline[/yellow] {pipeline_id}")
    else:
        r.raise_for_status()

@app.command("update")
def update_pipeline(pipeline_id: str, config: str, base: Optional[str] = typer.Option(None, "--base", "-b")):
    with open(config, "r") as f:
        data = json.load(f)
    r = requests.put(f"{_base_url(base)}/pipelines/{pipeline_id}", json=data, timeout=10)
    r.raise_for_status()
    console.print(f"[green]Updated pipeline:[/green] {pipeline_id}")

@app.command("trigger")
def trigger(pipeline_id: str, base: Optional[str] = typer.Option(None, "--base", "-b")):
    r = requests.post(f"{_base_url(base)}/pipelines/{pipeline_id}/trigger", timeout=10)
    r.raise_for_status()
    out = r.json()
    console.print(f"[green]Triggered run[/green]: {out['run_id']} (status {out['status']})")

@app.command("watch")
def watch(run_id: str, base: Optional[str] = typer.Option(None, "--base", "-b")):
    url = f"{_base_url(base)}/runs/{run_id}"
    status = "pending"
    last_len = 0
    while status in ("pending", "running"):
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        run = r.json()
        status = run["status"]
        logs = run["logs"]
        for line in logs[last_len:]:
            console.print(line)
        last_len = len(logs)
        if status in ("pending", "running"):
            time.sleep(1)
    console.print(f"[bold]Run finished with status: {status}[/bold]")

if __name__ == "__main__":
    app()
