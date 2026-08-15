from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

from jobhunt.core.config import settings
from jobhunt.core.models import JobStatus
from jobhunt.storage.database import session_scope
from jobhunt.storage.repositories import (
    ApplicationRepository,
    DocumentRepository,
    InterviewRepository,
    OutreachRepository,
)


class PipelineTracker:
    def __init__(self):
        self.export_dir = settings.data_dir / "exports"
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def get_pipeline_summary(self) -> dict:
        with session_scope() as session:
            app_repo = ApplicationRepository(session)
            interview_repo = InterviewRepository(session)
            outreach_repo = OutreachRepository(session)

            all_apps = app_repo.list(limit=1000)
            upcoming_interviews = interview_repo.get_upcoming(days=14)
            pending_followups = outreach_repo.list_pending_followups()

            status_counts = {}
            for app in all_apps:
                status_counts[app.status.value] = status_counts.get(app.status.value, 0) + 1

            return {
                "total_applications": len(all_apps),
                "by_status": status_counts,
                "upcoming_interviews": len(upcoming_interviews),
                "pending_followups": len(pending_followups),
                "response_rate": self._calc_response_rate(all_apps),
                "interview_rate": self._calc_interview_rate(all_apps),
                "offer_rate": self._calc_offer_rate(all_apps),
            }

    def _calc_response_rate(self, apps: list) -> float:
        contacted = sum(1 for a in apps if a.status.value in [
            "outreach_sent", "outreach_accepted", "outreach_replied",
            "phone_screen", "technical_interview", "onsite_interview",
            "offer", "negotiating", "accepted"
        ])
        applied = sum(1 for a in apps if a.status.value != "discovered")
        return round(contacted / max(applied, 1) * 100, 1)

    def _calc_interview_rate(self, apps: list) -> float:
        interviewed = sum(1 for a in apps if a.status.value in [
            "phone_screen", "technical_interview", "onsite_interview",
            "offer", "negotiating", "accepted"
        ])
        applied = sum(1 for a in apps if a.status.value != "discovered")
        return round(interviewed / max(applied, 1) * 100, 1)

    def _calc_offer_rate(self, apps: list) -> float:
        offers = sum(1 for a in apps if a.status.value in ["offer", "negotiating", "accepted"])
        interviewed = sum(1 for a in apps if a.status.value in [
            "phone_screen", "technical_interview", "onsite_interview",
            "offer", "negotiating", "accepted"
        ])
        return round(offers / max(interviewed, 1) * 100, 1)

    def get_application_details(self, app_id: UUID) -> dict | None:
        with session_scope() as session:
            app_repo = ApplicationRepository(session)
            app = app_repo.get(app_id)
            if not app:
                return None

            doc_repo = DocumentRepository(session)
            docs = doc_repo.list_by_application(app_id)

            interview_repo = InterviewRepository(session)
            interviews = interview_repo.list_by_application(app_id)

            outreach_repo = OutreachRepository(session)
            messages = outreach_repo.list_by_application(app_id)

            return {
                "application": {
                    "id": str(app.id),
                    "status": app.status.value,
                    "priority": app.priority,
                    "applied_at": app.applied_at.isoformat() if app.applied_at else None,
                    "company": app.company.name,
                    "job_title": app.job_posting.title if app.job_posting else "N/A",
                    "resume_version": app.resume_version,
                    "cover_letter_version": app.cover_letter_version,
                    "notes": app.notes,
                    "salary_offered": app.salary_offered,
                },
                "documents": [
                    {"type": d.type, "version": d.version, "score": d.score, "path": d.file_path}
                    for d in docs
                ],
                "interviews": [
                    {
                        "round": i.round_number,
                        "type": i.round_type.value,
                        "scheduled": i.scheduled_at.isoformat() if i.scheduled_at else None,
                        "status": i.status,
                        "score": i.score,
                    }
                    for i in interviews
                ],
                "outreach": [
                    {
                        "status": m.status.value,
                        "channel": m.channel,
                        "sent_at": m.sent_at.isoformat() if m.sent_at else None,
                        "follow_ups": m.follow_up_count,
                        "next_followup": m.next_follow_up_at.isoformat() if m.next_follow_up_at else None,
                    }
                    for m in messages
                ],
            }

    def update_status(self, app_id: UUID, status: JobStatus, **kwargs) -> bool:
        with session_scope() as session:
            app_repo = ApplicationRepository(session)
            app = app_repo.update_status(app_id, status)
            if app and kwargs:
                for key, value in kwargs.items():
                    if hasattr(app, key):
                        setattr(app, key, value)
                session.flush()
            return app is not None

    def add_interview(
        self,
        app_id: UUID,
        round_number: int,
        round_type: str,
        scheduled_at: datetime | None = None,
        interviewers: list[dict] | None = None,
    ) -> UUID | None:
        from jobhunt.core.models import InterviewRoundType

        with session_scope() as session:
            interview_repo = InterviewRepository(session)
            interview = interview_repo.create(
                application_id=app_id,
                round_number=round_number,
                round_type=InterviewRoundType(round_type),
                scheduled_at=scheduled_at,
                interviewers=interviewers or [],
                status="scheduled",
            )
            return interview.id

    def export_to_csv(self, filepath: Path | None = None) -> Path:
        if filepath is None:
            filepath = self.export_dir / f"pipeline_export_{datetime.utcnow().strftime('%Y%m%d')}.csv"

        with session_scope() as session:
            app_repo = ApplicationRepository(session)
            apps = app_repo.list(limit=10000)

            fieldnames = [
                "Application ID", "Company", "Job Title", "Status", "Priority",
                "Applied Date", "Resume Version", "Cover Letter Version",
                "Salary Offered", "Equity Offered", "Bonus Offered",
                "Interview Count", "Last Interview Date", "Next Interview",
                "Outreach Count", "Last Outreach", "Next Followup",
                "Notes", "Created At", "Updated At",
            ]

            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

                for app in apps:
                    interviews = [i for i in app.interviews]
                    outreach = [m for m in app.outreach_messages]

                    writer.writerow({
                        "Application ID": str(app.id),
                        "Company": app.company.name,
                        "Job Title": app.job_posting.title if app.job_posting else "N/A",
                        "Status": app.status.value,
                        "Priority": app.priority,
                        "Applied Date": app.applied_at.strftime("%Y-%m-%d") if app.applied_at else "",
                        "Resume Version": app.resume_version or "",
                        "Cover Letter Version": app.cover_letter_version or "",
                        "Salary Offered": app.salary_offered or "",
                        "Equity Offered": app.equity_offered or "",
                        "Bonus Offered": app.bonus_offered or "",
                        "Interview Count": len(interviews),
                        "Last Interview Date": max([i.scheduled_at for i in interviews if i.scheduled_at], default="").strftime("%Y-%m-%d") if interviews else "",
                        "Next Interview": min([i.scheduled_at for i in interviews if i.scheduled_at and i.scheduled_at > datetime.utcnow()], default="").strftime("%Y-%m-%d") if interviews else "",
                        "Outreach Count": len(outreach),
                        "Last Outreach": max([m.sent_at for m in outreach if m.sent_at], default="").strftime("%Y-%m-%d") if outreach else "",
                        "Next Followup": min([m.next_follow_up_at for m in outreach if m.next_follow_up_at and m.next_follow_up_at > datetime.utcnow()], default="").strftime("%Y-%m-%d") if outreach else "",
                        "Notes": app.notes or "",
                        "Created At": app.created_at.strftime("%Y-%m-%d"),
                        "Updated At": app.updated_at.strftime("%Y-%m-%d"),
                    })

        return filepath

    def export_to_json(self, filepath: Path | None = None) -> Path:
        if filepath is None:
            filepath = self.export_dir / f"pipeline_export_{datetime.utcnow().strftime('%Y%m%d')}.json"

        with session_scope() as session:
            app_repo = ApplicationRepository(session)
            apps = app_repo.list(limit=10000)

            data = []
            for app in apps:
                data.append({
                    "id": str(app.id),
                    "company": app.company.name,
                    "job_title": app.job_posting.title if app.job_posting else None,
                    "status": app.status.value,
                    "priority": app.priority,
                    "applied_at": app.applied_at.isoformat() if app.applied_at else None,
                    "resume_version": app.resume_version,
                    "cover_letter_version": app.cover_letter_version,
                    "salary_offered": app.salary_offered,
                    "equity_offered": app.equity_offered,
                    "bonus_offered": app.bonus_offered,
                    "notes": app.notes,
                    "interviews": [
                        {
                            "round": i.round_number,
                            "type": i.round_type.value,
                            "scheduled_at": i.scheduled_at.isoformat() if i.scheduled_at else None,
                            "status": i.status,
                            "score": i.score,
                        }
                        for i in app.interviews
                    ],
                    "outreach": [
                        {
                            "status": m.status.value,
                            "channel": m.channel,
                            "sent_at": m.sent_at.isoformat() if m.sent_at else None,
                            "follow_up_count": m.follow_up_count,
                            "next_follow_up_at": m.next_follow_up_at.isoformat() if m.next_follow_up_at else None,
                        }
                        for m in app.outreach_messages
                    ],
                    "documents": [
                        {
                            "type": d.type,
                            "version": d.version,
                            "score": d.score,
                            "path": d.file_path,
                        }
                        for d in app.documents
                    ],
                    "created_at": app.created_at.isoformat(),
                    "updated_at": app.updated_at.isoformat(),
                })

            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)

        return filepath


class GoogleSheetsSync:
    def __init__(self):
        self.enabled = settings.google.enabled
        self.credentials_file = Path(settings.google.credentials_file).expanduser()
        self.token_file = Path(settings.google.token_file).expanduser()
        self.sheets_id = settings.google.sheets_id

    def sync(self, tracker: PipelineTracker) -> dict:
        if not self.enabled:
            return {"success": False, "error": "Google Sheets sync not enabled"}

        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError:
            return {"success": False, "error": "gspread not installed. Run: pip install jobhunt-os[google]"}

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(self.credentials_file, scopes=scopes)
        client = gspread.authorize(creds)

        sheet = client.open_by_key(self.sheets_id)
        worksheet = sheet.sheet1

        headers = [
            "Application ID", "Company", "Job Title", "Status", "Priority",
            "Applied Date", "Resume Version", "Salary Offered",
            "Interview Count", "Outreach Count", "Next Followup", "Notes",
        ]

        with session_scope() as session:
            app_repo = ApplicationRepository(session)
            apps = app_repo.list(limit=1000)

            rows = [headers]
            for app in apps:
                rows.append([
                    str(app.id)[:8],
                    app.company.name,
                    app.job_posting.title if app.job_posting else "N/A",
                    app.status.value,
                    app.priority,
                    app.applied_at.strftime("%Y-%m-%d") if app.applied_at else "",
                    app.resume_version or "",
                    app.salary_offered or "",
                    len(app.interviews),
                    len(app.outreach_messages),
                    min([m.next_follow_up_at for m in app.outreach_messages if m.next_follow_up_at], default="").strftime("%Y-%m-%d") if app.outreach_messages else "",
                    app.notes or "",
                ])

            worksheet.clear()
            worksheet.update("A1", rows)

        return {"success": True, "rows_synced": len(rows) - 1}
