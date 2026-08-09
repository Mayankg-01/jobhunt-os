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
    resp = client.get("/")
    assert resp.status_code == 200
    assert "jobhunt · workspace" in resp.text
    assert "extract jobs" in resp.text


def test_jobs_list_uses_shortlist_csv(client):
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    jobs = resp.json()["jobs"]
    assert jobs and all("fit" in j and "title" in j for j in jobs)
    assert any("Agent" in j["title"] for j in jobs)


def test_jobs_can_be_imported_via_csv(client):
    csv = "rank,score,company,title,location,url\n1,50,greenwave,ML Engineer,Remote,https://x"
    resp = client.post("/api/jobs", json={"csv": csv})
    assert resp.status_code == 200
    titles = [j["title"] for j in resp.json()["jobs"]]
    assert "ML Engineer" in titles


class _FakeResp:
    def raise_for_status(self):
        pass
    text = "<title>Senior Agentic AI Engineer — Acme</title>\n<p>job body</p>"


def test_job_pull_extracts_posting(client, monkeypatch):
    import jobhunt.api as api_mod
    monkeypatch.setattr(api_mod.httpx, "get", lambda *a, **k: _FakeResp())
    resp = client.post("/api/jobs/pull", json={"url": "https://jobs.example.com/123"})
    assert resp.status_code == 200
    body = resp.json()
    assert "Agentic AI Engineer" in body["title"]
    assert body["company"] == "Example"
    assert "agent" in body["keywords"]