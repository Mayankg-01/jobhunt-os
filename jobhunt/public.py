"""Public self-serve bundle builder.

Anyone can POST their own profile + a job posting and receive a tailored
cover letter, LinkedIn DM, and résumé PDF — all generated from their own
data; nothing fabricated, nothing persisted beyond the artifacts.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException
from pydantic import BaseModel, Field

from .agents import generate, summarize
from .apply import mailto
from .config import SETTINGS
from .domain import JobPosting, Profile
from .scoring import title_keywords


class SelfProfile(BaseModel):
    name: str
    headline: str = ""
    location: str = ""
    email: str = ""
    phone: str = ""
    github: str = ""
    linkedin: str = ""
    summary: str = ""
    skills: dict | list = Field(default_factory=dict)
    experience: list = Field(default_factory=list)
    projects: list = Field(default_factory=list)
    education: list = Field(default_factory=list)
    achievements: list = Field(default_factory=list)


class SelfJob(BaseModel):
    title: str
    company: str
    location: str = ""
    url: str = ""
    keywords: list[str] = Field(default_factory=list)


class SelfBuildRequest(BaseModel):
    profile: SelfProfile
    job: SelfJob


def to_profile(req: SelfProfile) -> Profile:
    data = req.model_dump()
    skills = data.get("skills")
    if isinstance(skills, list):
        data["skills"] = {"core": list(skills)}
    elif skills:
        data["skills"] = {k: (v if isinstance(v, list) else [v]) for k, v in skills.items()}
    else:
        data["skills"] = {}
    return Profile(**data)


def build(request: SelfBuildRequest) -> dict:
    """Generate a bundle from visitor-supplied data. Persists only the
    artifacts (under <data>/public/<run>/); the profile itself is not stored."""
    profile = to_profile(request.profile)
    if not profile.name.strip() or not request.job.title.strip():
        raise HTTPException(422, "name and job title are required")
    job = JobPosting(
        id=uuid.uuid4().hex[:12],
        company=request.job.company.strip() or "the team",
        title=request.job.title.strip(),
        location=request.job.location,
        url=request.job.url,
        keywords=request.job.keywords or title_keywords(request.job.title),
    )
    out_dir = Path(SETTINGS.data_dir) / "public"
    bundle, ev = generate(profile, job, out_dir)
    return {
        "job_id": job.id,
        "company": job.company,
        "title": job.title,
        "fit": ev.metrics.get("fit", 0),
        "qualified": ev.qualified,
        "checks": ev.checks,
        "summary": summarize(job, profile, ev),
        "cover_letter": bundle.cover_letter,
        "linkedin_dm": bundle.linkedin_dm,
        "resume_pdf": f"/bundles/{job.id}/resume_tailored.pdf",
        "resume_html": f"/bundles/{job.id}/resume_tailored.html",
        "mailto": mailto(profile, job, bundle.cover_letter),
    }