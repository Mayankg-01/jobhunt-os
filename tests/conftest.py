import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Hermetic data dir so the tracker/bundle tests never touch the repo's real data/
_TESTS_TMP = tempfile.mkdtemp(prefix="jobhunt-tests-")
import os

os.environ.setdefault("JOBHUNT_DATA", _TESTS_TMP)

from jobhunt.domain import JobPosting, Profile
from jobhunt.profile import load_profile

SAMPLE = Path(__file__).resolve().parents[1] / "samples" / "profile.json"


@pytest.fixture()
def profile() -> Profile:
    return load_profile(SAMPLE)


@pytest.fixture()
def job() -> JobPosting:
    return JobPosting(
        id="t",
        company="Acme",
        title="Applied AI Engineer",
        keywords=["langchain", "rag", "llm", "fastapi", "python"],
    )


@pytest.fixture()
def bundle():
    from jobhunt.domain import ApplicationBundle
    return ApplicationBundle(
        resume_pdf="data/applications/t/resume.pdf",
        resume_html="<p>resume</p>",
        cover_letter="Dear Acme, my RAG pipeline cut retrieval latency 40%.",
        linkedin_dm="Hi Acme, saw the AI Engineer role — I've shipped RAG at scale.",
    )


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from jobhunt.api import app
    return TestClient(app)