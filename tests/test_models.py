import pytest
from uuid import uuid4

from jobhunt.core.models import (
    JobPosting, Company, Contact, Application,
    Interview, OutreachMessage, Document,
    JobStatus, OutreachStatus, ContactType, InterviewRoundType
)


def test_job_posting_creation(test_session):
    job = JobPosting(
        external_id="test-123",
        source="linkedin",
        title="Senior Python Engineer",
        company="Acme Corp",
        location="San Francisco, CA",
        is_remote=True,
        description="We are hiring...",
        url="https://linkedin.com/jobs/123",
    )
    test_session.add(job)
    test_session.flush()

    assert job.id is not None
    assert job.external_id == "test-123"
    assert job.title == "Senior Python Engineer"


def test_company_creation(test_session):
    company = Company(
        name="Acme Corp",
        domain="acme.com",
        industry="FinTech",
        size="100-500",
    )
    test_session.add(company)
    test_session.flush()

    assert company.id is not None
    assert company.name == "Acme Corp"
    assert company.is_blacklisted is False


def test_contact_creation(test_session):
    company = Company(name="Acme Corp")
    test_session.add(company)
    test_session.flush()

    contact = Contact(
        company_id=company.id,
        name="Jane Smith",
        title="Engineering Manager",
        email="jane@acme.com",
        contact_type=ContactType.HIRING_MANAGER,
    )
    test_session.add(contact)
    test_session.flush()

    assert contact.id is not None
    assert contact.contact_type == ContactType.HIRING_MANAGER


def test_application_workflow(test_session):
    company = Company(name="Acme Corp")
    test_session.add(company)
    test_session.flush()

    job = JobPosting(
        external_id="test-123",
        source="linkedin",
        title="Senior Python Engineer",
        company="Acme Corp",
        location="San Francisco, CA",
        description="We are hiring...",
        url="https://linkedin.com/jobs/123",
    )
    test_session.add(job)
    test_session.flush()

    app = Application(
        job_posting_id=job.id,
        company_id=company.id,
        status=JobStatus.DISCOVERED,
        priority=1,
    )
    test_session.add(app)
    test_session.flush()

    assert app.status == JobStatus.DISCOVERED

    app.status = JobStatus.APPLIED
    test_session.flush()

    assert app.status == JobStatus.APPLIED


def test_interview_creation(test_session):
    company = Company(name="Acme Corp")
    test_session.add(company)
    test_session.flush()

    job = JobPosting(
        external_id="test-123",
        source="linkedin",
        title="Senior Python Engineer",
        company="Acme Corp",
        location="San Francisco, CA",
        description="We are hiring...",
        url="https://linkedin.com/jobs/123",
    )
    test_session.add(job)
    test_session.flush()

    app = Application(
        job_posting_id=job.id,
        company_id=company.id,
        status=JobStatus.PHONE_SCREEN,
    )
    test_session.add(app)
    test_session.flush()

    interview = Interview(
        application_id=app.id,
        round_number=1,
        round_type=InterviewRoundType.PHONE_SCREEN,
        status="scheduled",
    )
    test_session.add(interview)
    test_session.flush()

    assert interview.round_type == InterviewRoundType.PHONE_SCREEN


def test_outreach_message(test_session):
    company = Company(name="Acme Corp")
    test_session.add(company)
    test_session.flush()

    contact = Contact(
        company_id=company.id,
        name="Jane Smith",
        title="Engineering Manager",
        email="jane@acme.com",
        linkedin_url="https://linkedin.com/in/janesmith",
        contact_type=ContactType.HIRING_MANAGER,
    )
    test_session.add(contact)
    test_session.flush()

    job = JobPosting(
        external_id="test-123",
        source="linkedin",
        title="Senior Python Engineer",
        company="Acme Corp",
        location="San Francisco, CA",
        description="We are hiring...",
        url="https://linkedin.com/jobs/123",
    )
    test_session.add(job)
    test_session.flush()

    app = Application(
        job_posting_id=job.id,
        company_id=company.id,
        status=JobStatus.OUTREACH_SENT,
    )
    test_session.add(app)
    test_session.flush()

    msg = OutreachMessage(
        application_id=app.id,
        contact_id=contact.id,
        status=OutreachStatus.QUEUED,
        channel="linkedin",
        body="Hi Jane, I'm interested in...",
    )
    test_session.add(msg)
    test_session.flush()

    assert msg.status == OutreachStatus.QUEUED
    assert msg.channel == "linkedin"