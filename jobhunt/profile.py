"""Candidate profile: canonical JSON + optional resume-PDF keyword enrichment."""

from __future__ import annotations

import json
from pathlib import Path

from .domain import Profile

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None


def load_profile(path: str | Path) -> Profile:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Profile(**data)


def resume_keywords(pdf_path: str | Path) -> set[str]:
    """Extra vocabulary pulled from a real résumé PDF (best-effort)."""
    if PdfReader is None:
        return set()
    try:
        reader = PdfReader(str(pdf_path))
        text = " ".join((p.extract_text() or "") for p in reader.pages)
        return {w for w in text.lower().split() if w.isalpha() and len(w) > 2}
    except Exception:
        return set()