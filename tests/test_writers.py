import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobhunt.domain import JobPosting
from jobhunt.evals import evaluate
from jobhunt.profile import load_profile
from jobhunt.resume import build
from jobhunt.writers import cover_letter, linkedin_dm

from jobhunt.domain import ApplicationBundle

PROFILE = load_profile(Path(__file__).resolve().parents[1] / "samples" / "profile.json")


def _job(**kw):
    defaults = dict(id="t", company="Acme", title="Applied AI Engineer",
                    keywords=["langchain", "rag", "llm", "fastapi"])
    defaults.update(kw)
    return JobPosting(**defaults)


def test_cover_letter_cites_real_project_and_company(job):
    text = cover_letter(PROFILE, job)
    assert "Acme" in text
    assert "AI Wildlife Insights Assistant" in text or "Log Classification" in text
    assert PROFILE.email in text


def test_cover_letter_no_invented_numbers(job):
    text = cover_letter(PROFILE, job)
    for fake in ("99% accurate", "93% cheaper", "0.0001%"):
        assert fake not in text


def test_dm_short(job):
    assert len(linkedin_dm(PROFILE, job)) <= 320


def test_eval_passes_clean_bundle(job, tmp_path):
    pdf, html = build(PROFILE, job, tmp_path)
    html_str = html  # build() now returns the HTML string, not a path
    bundle = ApplicationBundle(resume_pdf=str(pdf), resume_html=html_str,
                               cover_letter=cover_letter(PROFILE, job),
                               linkedin_dm=linkedin_dm(PROFILE, job))
    ev = evaluate(PROFILE, job, bundle)
    assert ev.checks["no_fabricated_stats"] is True
    assert ev.checks["contact_present"] is True


def test_eval_catches_fabricated_stats(job, tmp_path):
    bundle = ApplicationBundle(
        resume_pdf="kept.pdf",
        resume_html="Summary Skills Experience Projects " + PROFILE.email,
        cover_letter=f"{PROFILE.email} We reduced 72% fastest.",
        linkedin_dm="a" * 10,
    )
    ev = evaluate(PROFILE, job, bundle)
    assert ev.checks["no_fabricated_stats"] is False  # 72% is not a backed stat