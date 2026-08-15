from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class JobStatus(str, enum.Enum):
    DISCOVERED = "discovered"
    INTERESTED = "interested"
    APPLYING = "applying"
    APPLIED = "applied"
    OUTREACH_SENT = "outreach_sent"
    OUTREACH_ACCEPTED = "outreach_accepted"
    OUTREACH_REPLIED = "outreach_replied"
    PHONE_SCREEN = "phone_screen"
    TECHNICAL_INTERVIEW = "technical_interview"
    ONSITE_INTERVIEW = "onsite_interview"
    OFFER = "offer"
    NEGOTIATING = "negotiating"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    GHOSTED = "ghosted"


class OutreachStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    SENT_CONNECT = "sent_connect"
    CONNECT_ACCEPTED = "connect_accepted"
    SENT_MESSAGE = "sent_message"
    REPLIED = "replied"
    BOUNCED = "bounced"
    FAILED = "failed"
    SKIPPED = "skipped"


class ContactType(str, enum.Enum):
    HIRING_MANAGER = "hiring_manager"
    RECRUITER = "recruiter"
    TEAM_MEMBER = "team_member"
    REFERRAL = "referral"
    UNKNOWN = "unknown"


class InterviewRoundType(str, enum.Enum):
    PHONE_SCREEN = "phone_screen"
    TECHNICAL = "technical"
    SYSTEM_DESIGN = "system_design"
    BEHAVIORAL = "behavioral"
    CASE_STUDY = "case_study"
    TAKE_HOME = "take_home"
    CULTURE_FIT = "culture_fit"
    EXECUTIVE = "executive"
    FINAL = "final"


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    external_id: Mapped[str] = mapped_column(String(255), index=True)
    source: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(500))
    company: Mapped[str] = mapped_column(String(255), index=True)
    company_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str] = mapped_column(String(255))
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False)
    job_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    experience_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    salary_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_currency: Mapped[str] = mapped_column(String(3), default="USD")
    description: Mapped[str] = mapped_column(Text)
    description_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirements: Mapped[list[str]] = mapped_column(JSON, default=list)
    responsibilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    benefits: Mapped[list[str]] = mapped_column(JSON, default=list)
    tech_stack: Mapped[list[str]] = mapped_column(JSON, default=list)
    url: Mapped[str] = mapped_column(String(1000))
    apply_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    posted_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    raw_data: Mapped[dict] = mapped_column(JSON, default=dict)

    applications: Mapped[list[Application]] = relationship(back_populates="job_posting", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("external_id", "source", name="uq_job_external_source"),
        Index("ix_job_company_title", "company", "title"),
        Index("ix_job_location_remote", "location", "is_remote"),
        Index("ix_job_posted_date", "posted_date"),
    )


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    glassdoor_rating: Mapped[float | None] = mapped_column(nullable=True)
    blind_rating: Mapped[float | None] = mapped_column(nullable=True)
    is_blacklisted: Mapped[bool] = mapped_column(Boolean, default=False)
    blacklist_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    contacts: Mapped[list[Contact]] = relationship(back_populates="company", cascade="all, delete-orphan")
    applications: Mapped[list[Application]] = relationship(back_populates="company")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("companies.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contact_type: Mapped[ContactType] = mapped_column(Enum(ContactType), default=ContactType.UNKNOWN, index=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(50), default="manual")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    company: Mapped[Company] = relationship(back_populates="contacts")
    outreach_messages: Mapped[list[OutreachMessage]] = relationship(back_populates="contact", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_contact_company_type", "company_id", "contact_type"),
        Index("ix_contact_email", "email"),
    )


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    job_posting_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("job_postings.id"), nullable=True, index=True)
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("companies.id"), index=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.DISCOVERED, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resume_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cover_letter_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    referral_contact_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    salary_offered: Mapped[int | None] = mapped_column(Integer, nullable=True)
    equity_offered: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bonus_offered: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    meta: Mapped[dict] = mapped_column(JSON, default=dict)

    job_posting: Mapped[JobPosting | None] = relationship(back_populates="applications")
    company: Mapped[Company] = relationship(back_populates="applications")
    referral_contact: Mapped[Contact | None] = relationship()
    interviews: Mapped[list[Interview]] = relationship(back_populates="application", cascade="all, delete-orphan")
    outreach_messages: Mapped[list[OutreachMessage]] = relationship(back_populates="application", cascade="all, delete-orphan")
    documents: Mapped[list[Document]] = relationship(back_populates="application", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_app_company_status", "company_id", "status"),
        Index("ix_app_status_date", "status", "created_at"),
    )


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("applications.id"), index=True)
    round_number: Mapped[int] = mapped_column(Integer)
    round_type: Mapped[InterviewRoundType] = mapped_column(Enum(InterviewRoundType))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interviewers: Mapped[list[dict]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(50), default="scheduled")
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(nullable=True)
    prep_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    application: Mapped[Application] = relationship(back_populates="interviews")

    __table_args__ = (
        Index("ix_interview_app_date", "application_id", "scheduled_at"),
        Index("ix_interview_status", "status"),
    )


class OutreachMessage(Base):
    __tablename__ = "outreach_messages"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    application_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("applications.id"), nullable=True, index=True)
    contact_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("contacts.id"), index=True)
    status: Mapped[OutreachStatus] = mapped_column(Enum(OutreachStatus), default=OutreachStatus.PENDING, index=True)
    channel: Mapped[str] = mapped_column(String(50), default="linkedin")
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body: Mapped[str] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    follow_up_count: Mapped[int] = mapped_column(Integer, default=0)
    last_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    application: Mapped[Application | None] = relationship(back_populates="outreach_messages")
    contact: Mapped[Contact] = relationship(back_populates="outreach_messages")

    __table_args__ = (
        Index("ix_outreach_contact_status", "contact_id", "status"),
        Index("ix_outreach_next_followup", "next_follow_up_at"),
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    application_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("applications.id"), index=True)
    type: Mapped[str] = mapped_column(String(50))
    version: Mapped[str] = mapped_column(String(100))
    file_path: Mapped[str] = mapped_column(String(500))
    content_hash: Mapped[str] = mapped_column(String(64))
    score: Mapped[float | None] = mapped_column(nullable=True)
    quality_checks: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    application: Mapped[Application] = relationship(back_populates="documents")

    __table_args__ = (
        Index("ix_doc_app_type", "application_id", "type"),
    )


class SearchQuery(Base):
    __tablename__ = "search_queries"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    query: Mapped[str] = mapped_column(Text)
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    results_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
