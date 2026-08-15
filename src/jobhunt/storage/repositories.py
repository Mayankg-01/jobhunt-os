from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from jobhunt.core.models import (
    Application,
    Company,
    Contact,
    Document,
    Interview,
    JobPosting,
    JobStatus,
    OutreachMessage,
    OutreachStatus,
    SearchQuery,
)


class BaseRepository:
    def __init__(self, session: Session):
        self.session = session


class JobPostingRepository(BaseRepository):
    def create(self, **kwargs) -> JobPosting:
        job = JobPosting(**kwargs)
        self.session.add(job)
        self.session.flush()
        return job

    def get(self, job_id: UUID) -> JobPosting | None:
        return self.session.get(JobPosting, job_id)

    def get_by_external(self, external_id: str, source: str) -> JobPosting | None:
        stmt = select(JobPosting).where(
            JobPosting.external_id == external_id,
            JobPosting.source == source,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list(
        self,
        *,
        company: str | None = None,
        status: JobStatus | None = None,
        is_remote: bool | None = None,
        location: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[JobPosting]:
        stmt = select(JobPosting)
        if company:
            stmt = stmt.where(JobPosting.company.ilike(f"%{company}%"))
        if is_remote is not None:
            stmt = stmt.where(JobPosting.is_remote == is_remote)
        if location:
            stmt = stmt.where(JobPosting.location.ilike(f"%{location}%"))
        stmt = stmt.order_by(JobPosting.discovered_at.desc()).limit(limit).offset(offset)
        return list(self.session.execute(stmt).scalars())

    def count(self, **filters) -> int:
        stmt = select(func.count(JobPosting.id))
        for key, value in filters.items():
            if hasattr(JobPosting, key):
                stmt = stmt.where(getattr(JobPosting, key) == value)
        return self.session.execute(stmt).scalar() or 0


class CompanyRepository(BaseRepository):
    def create(self, **kwargs) -> Company:
        company = Company(**kwargs)
        self.session.add(company)
        self.session.flush()
        return company

    def get(self, company_id: UUID) -> Company | None:
        return self.session.get(Company, company_id)

    def get_by_name(self, name: str) -> Company | None:
        stmt = select(Company).where(Company.name.ilike(name))
        return self.session.execute(stmt).scalar_one_or_none()

    def get_or_create(self, name: str, **kwargs) -> Company:
        company = self.get_by_name(name)
        if company is None:
            company = self.create(name=name, **kwargs)
        return company


class ContactRepository(BaseRepository):
    def create(self, **kwargs) -> Contact:
        contact = Contact(**kwargs)
        self.session.add(contact)
        self.session.flush()
        return contact

    def get(self, contact_id: UUID) -> Contact | None:
        return self.session.get(Contact, contact_id)

    def list_by_company(self, company_id: UUID) -> list[Contact]:
        stmt = select(Contact).where(Contact.company_id == company_id)
        return list(self.session.execute(stmt).scalars())

    def get_by_email(self, email: str) -> Contact | None:
        stmt = select(Contact).where(Contact.email == email)
        return self.session.execute(stmt).scalar_one_or_none()


class ApplicationRepository(BaseRepository):
    def create(self, **kwargs) -> Application:
        app = Application(**kwargs)
        self.session.add(app)
        self.session.flush()
        return app

    def get(self, app_id: UUID) -> Application | None:
        stmt = select(Application).options(
            joinedload(Application.job_posting),
            joinedload(Application.company),
            joinedload(Application.interviews),
            joinedload(Application.outreach_messages),
            joinedload(Application.documents),
        ).where(Application.id == app_id)
        return self.session.execute(stmt).unique().scalar_one_or_none()

    def list(
        self,
        *,
        status: JobStatus | None = None,
        company_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Application]:
        stmt = select(Application).options(joinedload(Application.company))
        if status:
            stmt = stmt.where(Application.status == status)
        if company_id:
            stmt = stmt.where(Application.company_id == company_id)
        stmt = stmt.order_by(Application.updated_at.desc()).limit(limit).offset(offset)
        return list(self.session.execute(stmt).unique().scalars())

    def get_by_job_posting(self, job_posting_id: UUID) -> Application | None:
        stmt = select(Application).where(Application.job_posting_id == job_posting_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def update_status(self, app_id: UUID, status: JobStatus) -> Application | None:
        app = self.get(app_id)
        if app:
            app.status = status
            app.updated_at = datetime.utcnow()
            self.session.flush()
        return app


class InterviewRepository(BaseRepository):
    def create(self, **kwargs) -> Interview:
        interview = Interview(**kwargs)
        self.session.add(interview)
        self.session.flush()
        return interview

    def get(self, interview_id: UUID) -> Interview | None:
        return self.session.get(Interview, interview_id)

    def list_by_application(self, application_id: UUID) -> list[Interview]:
        stmt = select(Interview).where(Interview.application_id == application_id).order_by(Interview.round_number)
        return list(self.session.execute(stmt).scalars())

    def get_upcoming(self, days: int = 7) -> list[Interview]:
        from datetime import timedelta
        now = datetime.utcnow()
        stmt = select(Interview).options(joinedload(Interview.application).joinedload(Application.company)).where(
            Interview.scheduled_at >= now,
            Interview.scheduled_at <= now + timedelta(days=days),
            Interview.status == "scheduled",
        ).order_by(Interview.scheduled_at)
        return list(self.session.execute(stmt).unique().scalars())


class OutreachRepository(BaseRepository):
    def create(self, **kwargs) -> OutreachMessage:
        msg = OutreachMessage(**kwargs)
        self.session.add(msg)
        self.session.flush()
        return msg

    def get(self, msg_id: UUID) -> OutreachMessage | None:
        return self.session.get(OutreachMessage, msg_id)

    def list_pending_followups(self) -> list[OutreachMessage]:
        now = datetime.utcnow()
        stmt = select(OutreachMessage).options(
            joinedload(OutreachMessage.contact),
            joinedload(OutreachMessage.application).joinedload(Application.company),
        ).where(
            OutreachMessage.status.in_([
                OutreachStatus.SENT_CONNECT,
                OutreachStatus.CONNECT_ACCEPTED,
                OutreachStatus.SENT_MESSAGE,
            ]),
            OutreachMessage.next_follow_up_at <= now,
        ).order_by(OutreachMessage.next_follow_up_at)
        return list(self.session.execute(stmt).unique().scalars())

    def list_by_application(self, application_id: UUID) -> list[OutreachMessage]:
        stmt = select(OutreachMessage).where(OutreachMessage.application_id == application_id).order_by(OutreachMessage.created_at)
        return list(self.session.execute(stmt).scalars())


class DocumentRepository(BaseRepository):
    def create(self, **kwargs) -> Document:
        doc = Document(**kwargs)
        self.session.add(doc)
        self.session.flush()
        return doc

    def list_by_application(self, application_id: UUID) -> list[Document]:
        stmt = select(Document).where(Document.application_id == application_id).order_by(Document.created_at.desc())
        return list(self.session.execute(stmt).scalars())


class SearchQueryRepository(BaseRepository):
    def create(self, **kwargs) -> SearchQuery:
        query = SearchQuery(**kwargs)
        self.session.add(query)
        self.session.flush()
        return query

    def get_active(self) -> list[SearchQuery]:
        stmt = select(SearchQuery).where(SearchQuery.is_active == True)
        return list(self.session.execute(stmt).scalars())
