
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_create_and_trigger_pipeline():
    payload = {
        "name": "example",
        "repo_url": "https://github.com/example/repo",
        "branch": "main",
        "steps": [
            {"name": "lint", "type": "run", "command": "make lint"},
            {"name": "build", "type": "build", "dockerfile": "Dockerfile", "ecr_repo": "example/repo"},
            {"name": "deploy", "type": "deploy", "manifest": "k8s/deploy.yaml"}
        ]
    }
    r = client.post("/pipelines", json=payload)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    r = client.post(f"/pipelines/{pid}/trigger")
    assert r.status_code == 202
    run_id = r.json()["run_id"]

    # poll for completion
    for _ in range(15):
        run = client.get(f"/runs/{run_id}").json()
        if run["status"] in ("succeeded", "failed"):
            break
    assert run["status"] in ("succeeded", "failed")
    assert isinstance(run["logs"], list)
