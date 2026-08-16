"""Ingest jobs from a tall CSV (job-scout output) into domain objects."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from .domain import JobPosting


def load_jobs(csv_path: str | Path) -> list[JobPosting]:
    jobs: list[JobPosting] = []
    with Path(csv_path).open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            company = (row.get("company") or "").strip()
            title = (row.get("title") or "").strip()
            if not company or not title:
                continue
            key_text = f"{company}|{title}".encode()
            job_id = hashlib.sha1(key_text).hexdigest()[:12]
            jobs.append(JobPosting(
                id=job_id,
                company=company,
                title=title,
                location=(row.get("location") or "").strip(),
                url=(row.get("url") or "").strip(),
                score=float(row.get("score") or 0),
            ))
    return jobs