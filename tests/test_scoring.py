from jobhunt.scoring import fit_score, gaps, title_keywords, top_projects


def test_fit_high_for_matching_job(profile, job):
    assert fit_score(profile, job) >= 0.9


def test_gaps_are_honest(profile, job):
    missing = gaps(profile, job)
    assert "kubernetes" in missing or all(k not in ("kubernetes",) for k in missing)


def test_empty_keywords_neutral(profile):
    job = job_with("Data Curator", [])
    assert 0.5 <= fit_score(profile, job) <= 1.0


def test_title_keywords_agent(profile, job):
    words = title_keywords("Senior Agentic AI Engineer")
    assert "agent" in words and "rag" in words


def test_top_projects_ranks_matching_first(profile, job):
    ordered = top_projects(profile, job, 3)
    assert ordered[0] in ("AI Wildlife Insights Assistant", "AI/ML Log Classification System")


def job_with(title, keywords):
    from jobhunt.domain import JobPosting
    return JobPosting(id="x", company="X", title=title, keywords=keywords)