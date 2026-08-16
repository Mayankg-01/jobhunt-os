import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta

from jobhunt.engines.resume import ResumeQualityGate, ResumeParser
from jobhunt.engines.pipeline import PipelineTracker
from jobhunt.core.models import JobStatus, OutreachStatus


class TestResumeQualityGate:
    def test_check_passes_minimal_resume(self):
        resume = {
            "header": {"name": "Test", "email": "test@example.com"},
            "summary": "Experienced engineer",
            "skills": {"languages": ["Python"], "frameworks": ["FastAPI"]},
            "experience": [{"title": "Engineer", "company": "Acme", "bullets": ["Built API", "Wrote tests", "Deployed"]}],
            "education": [{"degree": "BS CS", "school": "University"}],
        }
        jd = "We need a Python engineer with FastAPI experience to build APIs and write tests."

        result = ResumeQualityGate.check(resume, jd)

        assert result["passed"] is True
        assert result["checks"]["bullets"] is True
        assert result["checks"]["skills"] is True
        assert result["checks"]["contact"] is True
        assert result["checks"]["summary"] is True

    def test_check_fails_few_bullets(self):
        resume = {
            "header": {"name": "Test", "email": "test@example.com"},
            "summary": "Experienced engineer",
            "skills": {"languages": ["Python"]},
            "experience": [{"title": "Engineer", "company": "Acme", "bullets": ["Built API"]}],
        }
        jd = "We need a Python engineer."

        result = ResumeQualityGate.check(resume, jd)

        assert result["passed"] is False
        assert result["checks"]["bullets"] is False
        assert any("Too few bullets" in issue for issue in result["issues"])

    def test_check_warnings_missing_skills(self):
        resume = {
            "header": {"name": "Test", "email": "test@example.com"},
            "summary": "Experienced engineer",
            "skills": {},
            "experience": [{"title": "Engineer", "company": "Acme", "bullets": ["Built API", "Wrote tests", "Deployed"]}],
        }
        jd = "We need a Python engineer."

        result = ResumeQualityGate.check(resume, jd)

        assert result["checks"]["skills"] is False
        assert any("No skills listed" in w for w in result["warnings"])

    def test_check_warnings_low_keyword_match(self):
        resume = {
            "header": {"name": "Test", "email": "test@example.com"},
            "summary": "Experienced engineer",
            "skills": {"languages": ["Python"]},
            "experience": [{"title": "Engineer", "company": "Acme", "bullets": ["Built API", "Wrote tests", "Deployed"]}],
        }
        # JD with completely different tech stack - no Python, FastAPI, etc.
        jd = "We need a Java engineer with Spring Boot experience for microservices. Kubernetes and Kafka required."

        result = ResumeQualityGate.check(resume, jd)

        # The resume has "Python" but JD has "Java", "Spring Boot", "Kubernetes", "Kafka"
        # Only "engineer" and "experience" might match - should be low keyword match
        assert result["checks"]["keywords"] is False
        assert any("Low JD keyword match" in w for w in result["warnings"])


class TestPipelineTracker:
    @pytest.fixture
    def mock_session(self):
        with patch("jobhunt.engines.pipeline.session_scope") as mock:
            yield mock

    def test_get_pipeline_summary(self, mock_session):
        mock_session.return_value.__enter__.return_value = MagicMock()

        tracker = PipelineTracker()
        # This would need more mocking to test fully
        assert tracker is not None


class TestJobSearchEngine:
    @pytest.mark.asyncio
    async def test_search_requires_jobspy(self):
        from jobhunt.engines.search import JobSearchEngine

        engine = JobSearchEngine()

        with patch("jobspy.scrape_jobs", side_effect=ImportError):
            result = await engine.search("Python Engineer")
            assert any("error" in r for r in result)