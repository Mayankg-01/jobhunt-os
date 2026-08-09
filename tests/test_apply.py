import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobhunt.apply import application_sheet, mailto, one_click, tracker
from jobhunt.track import Tracker


def test_tracker_ledger_roundtrip(tmp_path):
    tr = Tracker(tmp_path / "apps.jsonl")
    assert tr.upsert("j1", "Acme", "Engineer", "https://acme/j1")["status"] == "ready"
    tr.set_status("j1", "applied")
    assert tr.get("j1")["status"] == "applied"
    assert [r["job_id"] for r in tr.list()] == ["j1"]
    assert tr.set_status("ghost", "applied") is None


def test_tracker_rejects_bad_status(tmp_path):
    import pytest
    tr = Tracker(tmp_path / "apps.jsonl")
    with pytest.raises(ValueError):
        tr.set_status("j1", "nonsense")


def test_mailto_builds_valid_action(profile, job, bundle):
    import urllib.parse
    url = mailto(profile, job, bundle.cover_letter)
    assert url.startswith("mailto:")
    decoded = urllib.parse.unquote_plus(url)
    assert profile.email in decoded
    assert job.title in decoded


def test_application_sheet_shape(profile, job, bundle):
    sheet = application_sheet(profile, job, bundle)
    assert sheet["job_id"] == job.id
    assert sheet["resume_pdf"] == bundle.resume_pdf
    assert sheet["mailto"].startswith("mailto:")
    assert sheet["cover_letter"] == bundle.cover_letter


def test_one_click_pure(profile, job, bundle):
    sheet = one_click(profile, job, bundle, copy=False, open_page=False)
    assert sheet["page_opened"] is False
    assert sheet["cover_copied"] is False


def test_default_tracker_lives_in_data_dir(monkeypatch):
    import jobhunt.apply as apply_mod
    assert Path(str(apply_mod.tracker().path)).suffix == ".jsonl"