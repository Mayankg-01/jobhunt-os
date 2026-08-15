from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta
from pathlib import Path

from jobhunt.core.config import settings
from jobhunt.utils.ai import draft_outreach


class OutreachEngine:
    def __init__(self):
        self.outreach_dir = settings.data_dir / "outreach"
        self.outreach_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = Path(settings.linkedin.session_file).expanduser()
        self.rate_limit = settings.linkedin.rate_limit_per_hour
        self.sent_this_hour = 0
        self.hour_start = datetime.utcnow()

    async def draft_messages(
        self,
        contact: dict,
        company: dict,
        job: dict | None,
        user_profile: dict,
        message_type: str = "connection",
    ) -> dict:
        return await draft_outreach(contact, company, job, user_profile, message_type)

    async def queue_outreach(
        self,
        application_id: str,
        contact_id: str,
        messages: dict,
        channel: str = "linkedin",
    ) -> dict:
        from jobhunt.core.models import OutreachStatus
        from jobhunt.storage.database import session_scope
        from jobhunt.storage.repositories import OutreachRepository

        with session_scope() as session:
            repo = OutreachRepository(session)

            conn_msg = repo.create(
                application_id=application_id,
                contact_id=contact_id,
                status=OutreachStatus.QUEUED,
                channel=channel,
                subject=messages.get("subject_line"),
                body=messages.get("connection_note", ""),
                next_follow_up_at=datetime.utcnow() + timedelta(hours=random.randint(1, 3)),
            )

            if messages.get("follow_up_message"):
                repo.create(
                    application_id=application_id,
                    contact_id=contact_id,
                    status=OutreachStatus.PENDING,
                    channel=channel,
                    body=messages["follow_up_message"],
                    next_follow_up_at=datetime.utcnow() + timedelta(days=3),
                )

            return {"connection_message_id": str(conn_msg.id), "status": "queued"}

    def check_rate_limit(self) -> bool:
        now = datetime.utcnow()
        if now - self.hour_start > timedelta(hours=1):
            self.sent_this_hour = 0
            self.hour_start = now
        return self.sent_this_hour < self.rate_limit

    async def send_linkedin_connect(self, contact_url: str, note: str) -> dict:
        if not self.check_rate_limit():
            return {"success": False, "error": "Rate limit exceeded"}

        if settings.linkedin.enabled and settings.linkedin.li_at_cookie:
            try:
                result = await self._send_via_playwright(contact_url, note, "connect")
                if result["success"]:
                    self.sent_this_hour += 1
                return result
            except Exception as e:
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "LinkedIn not configured - enable in settings and add li_at cookie"}

    async def send_linkedin_message(self, contact_url: str, message: str) -> dict:
        if not self.check_rate_limit():
            return {"success": False, "error": "Rate limit exceeded"}

        if settings.linkedin.enabled and settings.linkedin.li_at_cookie:
            try:
                result = await self._send_via_playwright(contact_url, message, "message")
                if result["success"]:
                    self.sent_this_hour += 1
                return result
            except Exception as e:
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "LinkedIn not configured"}

    async def _send_via_playwright(self, url: str, text: str, action: str) -> dict:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return {"success": False, "error": "Playwright not installed. Run: pip install playwright && playwright install chromium"}

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=settings.linkedin.headless)
            context = await browser.new_context()
            page = await context.new_page()

            if self.session_file.exists():
                await context.add_cookies([{"name": "li_at", "value": settings.linkedin.li_at_cookie, "domain": ".linkedin.com", "path": "/"}])

            await page.goto(url, wait_until="networkidle")

            if action == "connect":
                connect_btn = await page.query_selector("button:has-text('Connect')")
                if connect_btn:
                    await connect_btn.click()
                    await page.wait_for_selector("button:has-text('Add a note')")
                    await page.click("button:has-text('Add a note')")
                    await page.fill("textarea[name='message']", text)
                    await page.click("button:has-text('Send')")
                    await page.wait_for_timeout(2000)
                    return {"success": True, "action": "connect_sent"}
                return {"success": False, "error": "Connect button not found"}

            if action == "message":
                message_btn = await page.query_selector("button:has-text('Message')")
                if message_btn:
                    await message_btn.click()
                    await page.wait_for_selector("div[role='textbox']")
                    await page.fill("div[role='textbox']", text)
                    await page.click("button:has-text('Send')")
                    await page.wait_for_timeout(2000)
                    return {"success": True, "action": "message_sent"}
                return {"success": False, "error": "Message button not found"}

            await browser.close()
            return {"success": False, "error": "Unknown action"}

    def process_followups(self) -> list[dict]:
        from jobhunt.core.models import OutreachStatus
        from jobhunt.storage.database import session_scope
        from jobhunt.storage.repositories import OutreachRepository

        results = []
        with session_scope() as session:
            repo = OutreachRepository(session)
            followups = repo.list_pending_followups()

            for msg in followups:
                if msg.follow_up_count >= 3:
                    msg.status = OutreachStatus.SKIPPED
                    continue

                if msg.channel == "linkedin" and msg.contact.linkedin_url:
                    result = asyncio.run(self.send_linkedin_message(msg.contact.linkedin_url, msg.body))
                    if result["success"]:
                        msg.status = OutreachStatus.SENT_MESSAGE
                        msg.sent_at = datetime.utcnow()
                        msg.follow_up_count += 1
                        msg.last_follow_up_at = datetime.utcnow()
                        msg.next_follow_up_at = datetime.utcnow() + timedelta(days=5)
                        results.append({"message_id": str(msg.id), "status": "sent"})
                    else:
                        msg.error_message = result.get("error")
                        results.append({"message_id": str(msg.id), "status": "failed", "error": result.get("error")})

        return results


class OutreachQueue:
    def __init__(self, engine: OutreachEngine):
        self.engine = engine

    async def daily_send(self, max_sends: int = 10) -> list[dict]:
        from jobhunt.core.models import OutreachStatus
        from jobhunt.storage.database import session_scope
        from jobhunt.storage.repositories import OutreachRepository

        sent = []
        with session_scope() as session:
            repo = OutreachRepository(session)
            stmt = repo.session.query(repo.session.query(OutreachMessage).filter(
                OutreachMessage.status == OutreachStatus.QUEUED
            ).order_by(OutreachMessage.next_follow_up_at)).limit(max_sends).statement

            queued = repo.session.execute(stmt).scalars().all()

            for msg in queued:
                if not self.engine.check_rate_limit():
                    break

                if msg.channel == "linkedin" and msg.contact.linkedin_url:
                    result = await self.engine.send_linkedin_connect(msg.contact.linkedin_url, msg.body)
                    if result["success"]:
                        msg.status = OutreachStatus.SENT_CONNECT
                        msg.sent_at = datetime.utcnow()
                        msg.next_follow_up_at = datetime.utcnow() + timedelta(days=7)
                        self.engine.sent_this_hour += 1
                        sent.append({"message_id": str(msg.id), "status": "connect_sent"})
                    else:
                        msg.error_message = result.get("error")
                        sent.append({"message_id": str(msg.id), "status": "failed", "error": result.get("error")})

        return sent
