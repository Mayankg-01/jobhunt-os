import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from jobhunt.api import app


def test_api_starts_and_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_payload_builds_bundle(client):
    payload = {
        "company": "Acme",
        "title": "Applied AI Engineer",
        "keywords": ["langchain", "rag", "llm", "fastapi", "python"],
    }
    resp = client.post("/api/build", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert "job_id" in body
    assert body["qualified"] is True


def test_application_status_lifecycle(client):
    payload = {
        "company": "Acme",
        "title": "Applied AI Engineer",
        "keywords": ["langchain", "rag", "llm", "fastapi", "python"],
    }
    job_id = client.post("/api/build", json=payload).json()["job_id"]
    resp = client.post(f"/api/applications/{job_id}/status", json={"status": "applied"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "applied"
    rows = client.get("/api/applications").json()
    assert any(r["id"] == job_id and r["status"] == "applied" for r in rows)


def test_apply_endpoint_stages_and_tracks(client, monkeypatch):
    import jobhunt.api as api_mod
    payload = {
        "company": "Acme",
        "title": "Applied AI Engineer",
        "keywords": ["langchain", "rag", "llm", "fastapi", "python"],
    }
    job_id = client.post("/api/build", json=payload).json()["job_id"]

    def fake_one_click(profile, job, bundle, copy=True, open_page=True):
        return {"job_id": job.id, "mailto": "mailto:x@y", "page_opened": True, "cover_copied": True}
    monkeypatch.setattr(api_mod, "one_click", fake_one_click)

    resp = client.post(f"/api/apply/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["page_opened"] is True
    rows = client.get("/api/applications").json()
    assert next(r for r in rows if r["id"] == job_id)["status"] == "ready"


def test_dashboard_renders(client):
    resp = client.get("/apply")
    assert resp.status_code == 200
    assert "one click apply" in resp.text
    assert "navigator.clipboard" in resp.text