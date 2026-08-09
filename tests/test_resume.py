import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobhunt.profile import load_profile
from jobhunt.resume import build

PROFILE = load_profile(Path(__file__).resolve().parents[1] / "samples" / "profile.json")


def test_build_writes_pdf_and_html(job, tmp_path):
    pdf, html = build(PROFILE, job, tmp_path)
    assert pdf.exists()
    assert pdf.read_bytes()[:4] == b"%PDF"
    assert "Skills" in html and PROFILE.email in html