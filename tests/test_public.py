import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobhunt.public import SelfBuildRequest, SelfJob, SelfProfile, to_profile
from jobhunt.domain import Profile


def _payload():
    return {
        "profile": {
            "name": "Ada Lovelace",
            "headline": "ML engineer shipping retrieval systems",
            "location": "London, UK",
            "email": "ada@example.com",
            "phone": "+44 20 0000 0000",
            "github": "https://github.com/ada",
            "linkedin": "https://linkedin.com/in/ada",
            "summary": "Engineer building RAG pipelines; cut retrieval latency 98%.",
            "skills": ["python", "fastapi", "rag", "mlops", "pytorch", "langchain"],
            "experience": [{
                "title": "ML Engineer", "company": "Turing", "period": "2023 - present",
                "bullets": ["Shipped a retrieval service that cut latency 98%.",
                            "Deployed FastAPI microservices to production."],
            }],
            "projects": [{
                "name": "Needle", "desc": "RAG with citations across 10k docs.",
                "tags": ["rag", "langchain", "fastapi", "python"],
            }],
            "education": [{"degree": "B.Sc. CS", "school": "Cambridge", "period": "2019 - 2022"}],
            "achievements": ["98% retrieval accuracy on internal eval"],
        },
        "job": {
            "title": "Applied AI Engineer",
            "company": "Acme",
            "keywords": ["rag", "langchain", "python", "fastapi", "mlops"],
        },
    }


def test_to_profile_normalizes_flat_skills():
    req = SelfProfile(name="x", skills=["python", "fastapi"])
    pf = to_profile(req)
    assert isinstance(pf, Profile)
    assert pf.skill_set() == {"python", "fastapi"}


def test_self_service_builds_bundle(client):
    body = client.post("/api/self", json=_payload())
    assert body.status_code == 200
    r = body.json()
    assert r["company"] == "Acme"
    assert r["qualified"] is True
    assert r["cover_letter"].startswith("Dear Acme team")
    assert r["linkedin_dm"]
    assert r["resume_pdf"].startswith("/bundles/")
    assert r["mailto"].startswith("mailto:")


def test_self_bundle_artifacts_are_served(client):
    r = client.post("/api/self", json=_payload()).json()
    pdf = client.get(r["resume_pdf"])
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    html = client.get(r["resume_html"])
    assert html.status_code == 200
    assert "Ada Lovelace" in html.text


def test_admin_gate_blocks_owner_routes(client, monkeypatch):
    import jobhunt.api as api_mod
    monkeypatch.setattr(api_mod, "ADMIN_TOKEN", "s3cret")
    assert client.post("/api/build",
                       json={"company": "Acme", "title": "Engineer",
                             "keywords": ["python"]}).status_code == 401
    assert client.get("/api/applications").status_code == 401
    ok = client.get("/api/applications", params={"token": "s3cret"})
    assert ok.status_code == 200


def test_public_routes_stay_open(client, monkeypatch):
    import jobhunt.api as api_mod
    monkeypatch.setattr(api_mod, "ADMIN_TOKEN", "s3cret")
    assert client.get("/").status_code == 200
    body = client.post("/api/self", json=_payload())
    assert body.status_code == 200