"""Evaluation harness: quantifiable pass/fail gates for each application
bundle. Catches the embarrassing stuff — missing contact info, fabricated
stats, over-long DMs — before it ships to a recruiter."""

from __future__ import annotations

import re

from .domain import ApplicationBundle, Evaluation, JobPosting, Profile
from .scoring import _present, backed_stats, fit_score, profile_context


def _suspicious_stats(text: str, profile: Profile) -> list[str]:
    """Any percentage claims not backed by the candidate's real numbers."""
    found = re.findall(r"\b\d+(?:[.,]\d+)*\s*%", text.lower())
    backed = backed_stats(profile)
    return [f for f in found if f.strip() not in backed]


def evaluate(profile: Profile, job: JobPosting, bundle: ApplicationBundle) -> Evaluation:
    reqs = job.required_keywords()
    evidence = profile.skill_set() | profile_context(profile)
    fit = fit_score(profile, job)
    managed = [k for k in reqs if _present(k, evidence)]
    metrics = {
        "fit": fit,
        "required_keywords": len(reqs),
        "covered_keywords": len(managed),
    }
    checks = {
        "fit_gate": fit >= 0.6,
        "contact_present": profile.email in bundle.resume_html
                           or profile.email in bundle.cover_letter,
        "sections_present": all(
            s in bundle.resume_html
            for s in ("Summary", "Skills", "Experience", "Projects")),
        "no_fabricated_stats": not _suspicious_stats(bundle.cover_letter, profile),
        "dm_length_ok": len(bundle.linkedin_dm) <= 320,
    }
    return Evaluation(metrics=metrics, checks=checks)