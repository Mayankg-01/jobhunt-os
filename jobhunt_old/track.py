"""Application pipeline tracker — a JSONL ledger so you never lose a thread.

Statuses:
  preparing -> ready -> applied -> interviewing -> offer | closed | archived
"""

from __future__ import annotations

import json
import time
from pathlib import Path

STATUSES = {"preparing", "ready", "applied", "interviewing", "offer", "closed", "archived"}


class Tracker:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.rows: list[dict] = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    self.rows.append(json.loads(line))
                except Exception:
                    pass

    def _flush(self) -> None:
        with self.path.open("w", encoding="utf-8") as fh:
            for r in self.rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    def upsert(self, job_id: str, company: str, title: str, url: str,
               status: str = "ready", resume_pdf: str = "") -> dict:
        row = next((r for r in self.rows if r["job_id"] == job_id), None)
        if row is None:
            row = {"job_id": job_id, "company": company, "title": title,
                   "url": url, "status": status, "resume_pdf": resume_pdf,
                   "events": [{"status": status, "at": time.time()}]}
            self.rows.append(row)
        else:
            old = row.get("status")
            if status in STATUSES:
                row["status"] = status
            row["company"] = company or row.get("company")
            row["title"] = title or row.get("title")
            row["url"] = url or row.get("url")
            if old != row["status"]:
                row.setdefault("events", []).append({"status": row["status"], "at": time.time()})
        self._flush()
        return row

    def set_status(self, job_id: str, status: str) -> dict | None:
        if status not in STATUSES:
            raise ValueError(f"unknown status {status!r}; choose from {sorted(STATUSES)}")
        row = self.get(job_id)
        if row is None:
            return None
        return self.upsert(job_id, row.get("company", ""), row.get("title", ""),
                           row.get("url", ""), status)

    def get(self, job_id: str) -> dict | None:
        return next((r for r in self.rows if r["job_id"] == job_id), None)

    def list(self) -> list[dict]:
        return list(self.rows)