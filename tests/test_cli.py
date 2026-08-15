import pytest
from typer.testing import CliRunner

from jobhunt.cli.main import app


runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "JobHunt OS" in result.output


def test_profile_show():
    result = runner.invoke(app, ["profile", "show"])
    assert result.exit_code == 0
    assert "Profile" in result.output


def test_resume_tailor_help():
    result = runner.invoke(app, ["resume", "tailor", "--help"])
    assert result.exit_code == 0
    assert "Tailor resume" in result.output


def test_search_run_help():
    result = runner.invoke(app, ["search", "run", "--help"])
    assert result.exit_code == 0
    assert "Run a job search" in result.output


def test_outreach_draft_help():
    result = runner.invoke(app, ["outreach", "draft", "--help"])
    assert result.exit_code == 0
    assert "Draft outreach messages" in result.output


def test_interview_prep_help():
    result = runner.invoke(app, ["interview", "prep", "--help"])
    assert result.exit_code == 0
    assert "Generate interview prep" in result.output


def test_pipeline_summary_help():
    result = runner.invoke(app, ["pipeline", "summary", "--help"])
    assert result.exit_code == 0
    assert "Show pipeline summary" in result.output


def test_db_init_help():
    result = runner.invoke(app, ["db", "init", "--help"])
    assert result.exit_code == 0
    assert "Initialize database" in result.output