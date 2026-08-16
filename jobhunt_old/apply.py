"""One-click apply: everything prepped and staged so the ONLY human action is
the final submit inside the employer's portal.

What this intentionally does NOT do: drive a headless browser to fill
Greenhouse/Lever/LinkedIn forms. Auto-submitting violates their ToS, gets
accounts flagged, and floods recruiters with low-signal applications — that
hurts a real job hunt. We prep, we open, we copy; you click submit.
"""

from __future__ import annotations

import subprocess
import urllib.parse
import webbrowser
from pathlib import Path

from .config import SETTINGS
from .domain import ApplicationBundle, JobPosting, Profile
from .track import Tracker


def _clipboard(text: str) -> bool:
    """Best-effort clipboard on Windows via PowerShell Set-Clipboard."""
    try:
        ps = f"Set-Clipboard -Value ([Console]::In.ReadToEnd())"
        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-Command", ps],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        proc.communicate(text.encode("utf-8"), timeout=10)
        return proc.returncode == 0
    except Exception:
        return False


def mailto(profile: Profile, job: JobPosting, cover: str, to: str = "") -> str:
    subject = f"Application: {job.title} — {job.company}"
    body = cover + "\n\n" + f"View the role: {job.url}"
    q = urllib.parse.urlencode({"subject": subject, "body": body})
    return f"mailto:{to or profile.email}?{q}"


def application_sheet(profile: Profile, job: JobPosting, bundle: ApplicationBundle) -> dict:
    """The full payload a human needs to finish applying — in one block."""
    return {
        "job_id": job.id,
        "company": job.company,
        "title": job.title,
        "url": job.url,
        "cover_letter": bundle.cover_letter,
        "linkedin_dm": bundle.linkedin_dm,
        "resume_pdf": bundle.resume_pdf,
        "mailto": mailto(profile, job, bundle.cover_letter),
    }


def open_apply_page(url: str) -> bool:
    if not url:
        return False
    try:
        webbrowser.open(url)
        return True
    except Exception:
        return False


def one_click(profile: Profile, job: JobPosting, bundle: ApplicationBundle,
              copy: bool = True, open_page: bool = True) -> dict:
    """Stage the application: open the posting + stage clipboard + track state."""
    sheet = application_sheet(profile, job, bundle)
    if open_page:
        sheet["page_opened"] = open_apply_page(job.url)
    else:
        sheet["page_opened"] = False
    if copy:
        sheet["cover_copied"] = _clipboard(sheet["cover_letter"])
    else:
        sheet["cover_copied"] = False
    return sheet


def tracker_path() -> Path:
    return Path(SETTINGS.data_dir) / "applications.jsonl"


def tracker() -> Tracker:
    return Tracker(tracker_path())