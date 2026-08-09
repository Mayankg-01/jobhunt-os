"""The pipeline: job posting -> tailored application bundle -> evaluation.

Keeps the LLM optional: without a key you get deterministic, fact-safe
outputs; with a key, research angles tighten the narrative.
"""

from __future__ import annotations

from pathlib import Path

from . import llm, writers
from .config import SETTINGS
from .domain import ApplicationBundle, Evaluation, JobPosting, Profile
from .evals import evaluate
from .resume import build as build_resume
from .scoring import fit_score, gaps


def generate(profile: Profile, job: JobPosting, out_dir: Path) -> tuple[ApplicationBundle, Evaluation]:
    pdf_path, html_str = build_resume(profile, job, out_dir / job.id)
    angles = writers.research_angles(profile, job, llm.chat)
    cover = writers.cover_letter(profile, job)
    dm = writers.linkedin_dm(profile, job)
    bundle = ApplicationBundle(
        resume_pdf=str(pdf_path),
        resume_html=html_str,
        cover_letter=cover,
        linkedin_dm=dm,
        script_notes="\n".join(f"- {a}" for a in angles),
    )
    eval_ = evaluate(profile, job, bundle)
    return bundle, eval_


def summarize(job: JobPosting, profile: Profile, ev: Evaluation) -> str:
    parts = [f"{job.company} · {job.title}  ->  fit {ev.metrics.get('fit', 0):.0%}"]
    missing = gaps(profile, job)
    if missing:
        parts.append("gap:" + ",".join(missing[:4]))
    if not ev.qualified:
        failed = [k for k, ok in ev.checks.items() if not ok]
        parts.append("blocked by " + ",".join(failed))
    return " | ".join(parts)