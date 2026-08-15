from __future__ import annotations

import asyncio
from datetime import datetime
from uuid import UUID

from jobhunt.core.config import settings
from jobhunt.storage.database import session_scope
from jobhunt.storage.repositories import (
    CompanyRepository,
    JobPostingRepository,
    SearchQueryRepository,
)


class JobSearchEngine:
    def __init__(self):
        self.sources = settings.search.sources
        self.results_per_source = settings.search.results_per_source

    async def search(
        self,
        query: str,
        location: str = "",
        is_remote: bool = False,
        job_type: str = "",
        experience_level: str = "",
        date_posted_days: int = 7,
        **kwargs,
    ) -> list[dict]:
        try:
            from jobspy import scrape_jobs
        except ImportError:
            return [{"error": "jobspy not installed. Run: pip install python-jobspy"}]

        all_jobs = []
        for source in self.sources:
            try:
                jobs = scrape_jobs(
                    site_name=[source],
                    search_term=query,
                    location=location,
                    is_remote=is_remote,
                    job_type=job_type,
                    experience_level=experience_level,
                    hours_old=date_posted_days * 24,
                    results_wanted=self.results_per_source,
                )
                for _, job in jobs.iterrows():
                    job_dict = job.to_dict()
                    job_dict["source"] = source
                    all_jobs.append(job_dict)
            except Exception as e:
                all_jobs.append({"source": source, "error": str(e)})

        return all_jobs

    async def search_and_store(
        self,
        query: str,
        location: str = "",
        is_remote: bool = False,
        **kwargs,
    ) -> dict:
        jobs = await self.search(query, location, is_remote, **kwargs)

        stored = 0
        errors = 0

        with session_scope() as session:
            job_repo = JobPostingRepository(session)
            company_repo = CompanyRepository(session)

            for job in jobs:
                if "error" in job:
                    errors += 1
                    continue

                company = company_repo.get_or_create(
                    name=job.get("company", "Unknown"),
                    domain=job.get("company_url", ""),
                )

                existing = job_repo.get_by_external(
                    job.get("id", ""), job.get("source", "unknown")
                )
                if existing:
                    continue

                job_repo.create(
                    external_id=job.get("id", ""),
                    source=job.get("source", "unknown"),
                    title=job.get("title", ""),
                    company=job.get("company", ""),
                    company_domain=job.get("company_url", ""),
                    location=job.get("location", ""),
                    is_remote=job.get("is_remote", False),
                    job_type=job.get("job_type", ""),
                    experience_level=job.get("experience_level", ""),
                    salary_min=job.get("salary_min"),
                    salary_max=job.get("salary_max"),
                    description=job.get("description", ""),
                    description_html=job.get("description_html", ""),
                    requirements=job.get("requirements", []),
                    responsibilities=job.get("responsibilities", []),
                    benefits=job.get("benefits", []),
                    tech_stack=self._extract_tech_stack(job.get("description", "")),
                    url=job.get("job_url", ""),
                    apply_url=job.get("apply_url", ""),
                    posted_date=self._parse_date(job.get("date_posted")),
                    raw_data=job,
                )
                stored += 1

        return {"searched": len(jobs), "stored": stored, "errors": errors}

    def _extract_tech_stack(self, description: str) -> list[str]:
        tech_keywords = [
            "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#",
            "react", "vue", "angular", "svelte", "next.js", "node.js", "express",
            "django", "flask", "fastapi", "spring", "rails", "laravel",
            "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "ansible",
            "postgresql", "mysql", "mongodb", "redis", "elasticsearch", "kafka",
            "spark", "hadoop", "airflow", "dbt", "snowflake", "bigquery",
            "git", "ci/cd", "jenkins", "github actions", "gitlab",
            "machine learning", "deep learning", "nlp", "computer vision", "llm",
            "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy",
        ]
        desc_lower = description.lower()
        return [kw for kw in tech_keywords if kw in desc_lower]

    def _parse_date(self, date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d %b %Y", "%B %d, %Y"]:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None

    def save_search_query(
        self,
        name: str,
        query: str,
        filters: dict,
        schedule: str | None = None,
    ) -> UUID:
        with session_scope() as session:
            query_repo = SearchQueryRepository(session)
            sq = query_repo.create(name=name, query=query, filters=filters, schedule=schedule)
            return sq.id

    def run_scheduled_searches(self) -> list[dict]:
        with session_scope() as session:
            query_repo = SearchQueryRepository(session)
            queries = query_repo.get_active()

        results = []
        for sq in queries:
            if sq.schedule:
                result = asyncio.run(self.search_and_store(
                    sq.query, **sq.filters
                ))
                result["query_name"] = sq.name
                results.append(result)

                with session_scope() as session:
                    query_repo = SearchQueryRepository(session)
                    sq.last_run = datetime.utcnow()
                    sq.results_count = result.get("stored", 0)
                    session.flush()

        return results
