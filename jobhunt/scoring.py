"""Fit scoring: how well the candidate covers a posting's required keywords.

Deterministic: keyword coverage + weighting of agentic/LLM skills. The eval
layer (evals.py) re-checks formatting/claims later.
"""

from __future__ import annotations

import re

from .domain import JobPosting, Profile

STRONG_SKILLS = {"langchain", "langgraph", "fastapi", "pytorch", "tensorflow",
                 "transformers", "chromadb", "openai", "agent", "finetuning",
                 "fine-tuning", "multimodal", "nlp", "mlops", "docker",
                 "kubernetes", "postgresql", "fastapi", "pydantic"}


def normalize(w: str) -> str:
    return re.sub(r"[\W_]+", " ", w.lower()).strip()


def present(required: str, skillset: set[str]) -> bool:
    req = normalize(required)
    if not req:
        return False
    return any(normalize(s) == req for s in skillset)


def profile_context(profile: Profile) -> set[str]:
    """Everything the candidate claims in writing — skills, projects, summary,
    experience, achievements. Honest evidence, nothing invented."""
    ctx: set[str] = set()
    for proj in profile.projects:
        ctx.update(s.lower() for s in proj.get("tags", []) or [])
        ctx.add(normalize(proj.get("desc") or ""))
    ctx.add(normalize(profile.summary))
    for role in profile.experience:
        for b in role.get("bullets", []):
            ctx.add(normalize(b))
    for a in profile.achievements:
        ctx.add(normalize(a))
    return ctx


def backed_stats(profile: Profile) -> set[str]:
    """Every percentage the candidate has already claimed, verbatim. A bundle
    may reproduce these; anything else is fabrication."""
    blobs = [profile.summary, *profile.achievements]
    for role in profile.experience:
        blobs += role.get("bullets", [])
    for proj in profile.projects:
        blobs.append(proj.get("desc", "") or "")
    backed: set[str] = set()
    for text in blobs:
        for m in re.findall(r"\b\d+(?:[.,]\d+)*\s*%", text.lower()):
            backed.add(m.strip())
    return backed


def fit_score(profile: Profile, job: JobPosting) -> float:
    reqs = job.required_keywords()
    if not reqs:
        return 0.5  # nothing to check against — neutral, don't block
    skills = profile.skill_set()
    evidence = skills | profile_context(profile)
    covered = [k for k in reqs if _present(k, evidence)]
    coverage = len(covered) / len(reqs)
    strong = sum(1 for k in covered if normalize(k) in STRONG_SKILLS)
    bonus = min(strong * 0.6, 10) / len(reqs)
    return round(min(1.0, coverage + bonus), 3)


def _present(required: str, evidence: set[str]) -> bool:
    req = normalize(required)
    if not req:
        return False
    return req in evidence or any(req == normalize(e) for e in evidence)


def gaps(profile: Profile, job: JobPosting) -> list[str]:
    reqs = job.required_keywords()
    if not reqs:
        return []
    evidence = profile.skill_set() | profile_context(profile)
    return [k for k in reqs if not _present(k, evidence)]


def top_projects(profile: Profile, job: JobPosting, n: int = 2) -> list[str]:
    """Projects ranked by how much they overlap the role's keywords."""
    reqs = job.required_keywords()
    scored = []
    for proj in profile.projects:
        name = proj.get("name", "")
        blob = (name + " " + " ".join(proj.get("tags", []) or [])).lower()
        overlap = sum(1 for r in reqs if normalize(r) in blob)
        scored.append((overlap, len(name), name))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [name for _, _, name in scored[:n]]


def title_keywords(title: str) -> list[str]:
    """Derive realistic requirement keywords from a posting title when a full
    description isn't available. Deterministic, keeps scoring/VAI honest."""
    t = title.lower()
    out: list[str] = []
    if "agent" in t:
        out += ["langchain", "rag", "llm", "agent", "fastapi"]
    if "vision" in t or "cv" in t or "imaging" in t:
        out += ["computer vision", "opencv", "tensorflow", "pytorch"]
    if "machine learning" in t or "ml" in t:
        out += ["python", "scikit-learn", "tensorflow", "mlops"]
    if "data" in t or "scientist" in t:
        out += ["pandas", "sql", "numpy", "python"]
    if "inference" in t or "infra" in t or "systems" in t:
        out += ["fastapi", "docker", "kubernetes", "mlops"]
    if not out:
        out = ["python", "llm", "fastapi", "git"]
    seen = []
    for k in out:
        if k not in seen:
            seen.append(k)
    return seen