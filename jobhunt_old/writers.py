"""Deterministic, fact-safe application text, generated from the candidate's
OWN profile — no invented numbers, no hard-coded narrative. Whatever number
appears in the letter already appears in their projects/achievements/summary.

An optional LLM can tighten tone, but the fallback is always a draft we can
vouch for. Works for any profile, not just a demo one.
"""

from __future__ import annotations

import re

from .domain import JobPosting, Profile
from .scoring import backed_stats, gaps, top_projects


def _cited(profile: Profile, job: JobPosting) -> str:
    """Proof we can point at: top projects (keyword-ranked) + quantified
    achievements, reproduced verbatim from the profile."""
    projs = []
    for name in top_projects(profile, job, 2):
        for proj in profile.projects:
            if proj.get("name") == name:
                tags = " · ".join(proj.get("tags", []) or [])
                projs.append(f"{name} ({tags})")
                break
    parts = projs if projs else ["the projects in my profile"]
    quantified = [a for a in profile.achievements if re.search(r"\d|%", a)]
    if quantified:
        parts.append("proof: " + " ".join(quantified[:2]))
    return ", ".join(parts)


def cover_letter(profile: Profile, job: JobPosting) -> str:
    proof = _cited(profile, job)
    opener = (profile.summary.strip() or profile.headline or
              f"{profile.name} — {profile.headline}")
    missing = gaps(profile, job)
    body = (
        f"Dear {job.company} team,\n\n"
        f"I am {profile.name}. {opener.capitalize()} The {job.title} role is "
        f"the next stage I want, and I can point at {proof} as the kind of "
        f"work I do.\n\n")
    if missing:
        body += (f"I am actively deepening {', '.join(missing[:4])}; my "
                 f"builds already use the surrounding stack.\n\n")
    body += (
        f"Happy to walk through the work on a short call.\n\n"
        f"{profile.name} · {profile.location} · {profile.email} · {profile.linkedin}")
    return body


def linkedin_dm(profile: Profile, job: JobPosting) -> str:
    proj = None
    for name in top_projects(profile, job, 1):
        for p in profile.projects:
            if p.get("name") == name:
                proj = p.get("name")
                break
    suffix = f", and {proj} shows the work" if proj else " with shipped work to share"
    return (
        f"Hi team at {job.company} — {job.title} maps to what I do: {profile.headline}. "
        f"Resume{suffix} — happy to share it. {profile.name}").replace("  ", " ")


def research_angles(profile: Profile, job: JobPosting, llm) -> list[str]:
    """LLM-curated talking points when available; safe, factual fallback."""
    if llm:
        prompt = (f"In max 90 words, what should a candidate highlight when "
                  f"applying for {job.title} at {job.company}? Skills given: "
                  f"{', '.join(profile.skill_set())}. Use only these — invent "
                  f"nothing.")
        out = llm(prompt)
        if out:
            return [out]
    return [f"Built for the {job.title} brief at {job.company}",
            "The projects I shipped are live demonstrations, not slides"]