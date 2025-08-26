
import requests

def trigger_github_workflow(owner: str, repo: str, workflow: str, ref: str, token: str, inputs: dict) -> int:
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "cicd-pipelines-api"
    }
    payload = {"ref": ref, "inputs": inputs}
    r = requests.post(url, headers=headers, json=payload, timeout=15)
    return r.status_code
