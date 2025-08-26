
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_404_get_pipeline():
    r = client.get("/pipelines/does-not-exist")
    assert r.status_code == 404
    assert r.json()["detail"] == "Pipeline not found"

def test_404_delete_pipeline():
    r = client.delete("/pipelines/nope")
    assert r.status_code == 404

def test_404_run():
    r = client.get("/runs/unknown")
    assert r.status_code == 404

def test_update_pipeline_and_validation():
    payload = {
        "name": "ex2",
        "repo_url": "https://github.com/example/repo",
        "branch": "dev",
        "steps": [{"name": "lint", "type": "run", "command": "echo hi"}],
    }
    r = client.post("/pipelines", json=payload)
    assert r.status_code == 201
    pid = r.json()["id"]

    payload["name"] = "ex2-updated"
    r = client.put(f"/pipelines/{pid}", json=payload)
    assert r.status_code == 200
    assert r.json()["name"] == "ex2-updated"

def test_validation_errors_for_steps():
    bad = {
        "name": "bad",
        "repo_url": "https://github.com/example/repo",
        "branch": "main",
        "steps": [{"name": "build", "type": "build"}],
    }
    r = client.post("/pipelines", json=bad)
    assert r.status_code == 422

    bad2 = {
        "name": "bad2",
        "repo_url": "https://github.com/example/repo",
        "steps": [{"name": "deploy", "type": "deploy"}],
    }
    r = client.post("/pipelines", json=bad2)
    assert r.status_code == 422
