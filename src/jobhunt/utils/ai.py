from __future__ import annotations

import json
import os
from uuid import uuid4

import httpx

from jobhunt.core.config import settings


class AIClient:
    def __init__(self):
        self.provider = settings.ai.provider
        self.api_key = settings.ai.api_key or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        self.model = settings.ai.model
        self.temperature = settings.ai.temperature
        self.max_tokens = settings.ai.max_tokens
        self.timeout = settings.ai.timeout

        if self.provider == "openai":
            self.base_url = "https://api.openai.com/v1"
            self.headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        elif self.provider == "anthropic":
            self.base_url = "https://api.anthropic.com/v1"
            self.headers = {"x-api-key": self.api_key, "Content-Type": "application/json", "anthropic-version": "2023-06-01"}
        elif self.provider == "openrouter":
            self.base_url = "https://openrouter.ai/api/v1"
            self.headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        else:
            raise ValueError(f"Unknown AI provider: {self.provider}")

    async def chat(self, messages: list[dict], **kwargs) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if self.provider == "anthropic":
                payload["system"] = messages[0]["content"] if messages[0]["role"] == "system" else ""
                payload["messages"] = [m for m in messages if m["role"] != "system"]
                response = await client.post(f"{self.base_url}/messages", headers=self.headers, json=payload)
                data = response.json()
                return data["content"][0]["text"]
            response = await client.post(f"{self.base_url}/chat/completions", headers=self.headers, json=payload)
            data = response.json()
            return data["choices"][0]["message"]["content"]

    def chat_sync(self, messages: list[dict], **kwargs) -> str:
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.chat(messages, **kwargs))


ai_client = AIClient()


RESUME_TAILOR_SYSTEM = """You are an expert resume writer and career coach. Your task is to tailor a base resume to a specific job description.

Guidelines:
1. Keep the resume to ONE PAGE maximum
2. Match keywords from the JD naturally in experience bullets
3. Quantify achievements with metrics (%, $, numbers)
4. Prioritize relevant experience for the target role
5. Use strong action verbs
6. Remove irrelevant details
7. Maintain honest representation - don't fabricate

Output format: Return ONLY the tailored resume as structured JSON with these sections:
- header: {name, email, phone, location, linkedin, github, portfolio}
- summary: 2-3 lines tailored to the role
- skills: categorized (languages, frameworks, tools, cloud, etc.)
- experience: list of {company, title, dates, location, bullets[]}
- education: list of {degree, school, year, honors}
- projects: list of {name, description, tech_stack, link} (optional)
- certifications: list (optional)
"""

RESUME_QUALITY_GATE_SYSTEM = """You are a senior hiring manager reviewing a tailored resume. Score it 1-10 and provide specific feedback.

Evaluate on:
1. JD keyword alignment (0-10)
2. Quantified achievements (0-10)
3. Relevance to role (0-10)
4. Formatting & brevity (0-10)
5. Honesty check (0-10) - flag any likely exaggerations
6. ATS compatibility (0-10)

Return JSON: {score: int, passed: bool, feedback: string, issues: list[str], warnings: list[str]}"""

OUTREACH_DRAFT_SYSTEM = """You are an expert at writing personalized LinkedIn outreach messages.

Guidelines:
1. Connection requests: <300 chars, mention specific reason, no ask
2. Follow-up messages: reference their work, show genuine interest, soft CTA
3. Tone: professional, concise, human
4. Personalize with company/role specifics
5. Never sound templated

Return JSON: {connection_note: str, follow_up_message: str, subject_line: str (if email)}"""

INTERVIEW_PREP_SYSTEM = """You are an interview coach preparing a candidate for a specific role at a specific company.

Create a comprehensive prep pack including:
1. Company research summary (mission, products, recent news, tech stack, culture)
2. Role-specific technical topics to review
3. Behavioral questions mapped to company values (STAR format)
4. Questions to ask interviewer
5. Salary negotiation data points
6. Daily focus brief

Return as structured JSON."""


async def tailor_resume(base_resume: dict, job_description: str, user_profile: dict) -> dict:
    messages = [
        {"role": "system", "content": RESUME_TAILOR_SYSTEM},
        {"role": "user", "content": f"""
Base Resume: {json.dumps(base_resume, indent=2)}
Job Description: {job_description}
User Profile: {json.dumps(user_profile, indent=2)}

Tailor the resume for this specific role. Return ONLY the JSON resume.
"""},
    ]
    response = await ai_client.chat(messages)
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {"error": "Failed to parse AI response", "raw": response}


async def quality_gate_resume(tailored_resume: dict, job_description: str) -> dict:
    messages = [
        {"role": "system", "content": RESUME_QUALITY_GATE_SYSTEM},
        {"role": "user", "content": f"""
Tailored Resume: {json.dumps(tailored_resume, indent=2)}
Job Description: {job_description}

Score and provide feedback.
"""},
    ]
    response = await ai_client.chat(messages)
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {"error": "Failed to parse AI response", "raw": response}


async def draft_outreach(
    contact_info: dict,
    company_info: dict,
    job_info: dict | None,
    user_profile: dict,
    message_type: str = "connection",
) -> dict:
    messages = [
        {"role": "system", "content": OUTREACH_DRAFT_SYSTEM},
        {"role": "user", "content": f"""
Contact: {json.dumps(contact_info, indent=2)}
Company: {json.dumps(company_info, indent=2)}
Job: {json.dumps(job_info, indent=2) if job_info else "N/A - general networking"}
User: {json.dumps(user_profile, indent=2)}
Message Type: {message_type}

Draft a personalized outreach message.
"""},
    ]
    response = await ai_client.chat(messages)
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {"error": "Failed to parse AI response", "raw": response}


async def generate_interview_prep(
    company_info: dict,
    job_info: dict,
    user_profile: dict,
    round_type: str = "technical",
) -> dict:
    messages = [
        {"role": "system", "content": INTERVIEW_PREP_SYSTEM},
        {"role": "user", "content": f"""
Company: {json.dumps(company_info, indent=2)}
Job: {json.dumps(job_info, indent=2)}
User: {json.dumps(user_profile, indent=2)}
Round Type: {round_type}

Generate comprehensive interview prep pack.
"""},
    ]
    response = await ai_client.chat(messages)
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        return {"error": "Failed to parse AI response", "raw": response}


def generate_resume_id() -> str:
    return f"res_{uuid4().hex[:12]}"


def generate_application_id() -> str:
    return f"app_{uuid4().hex[:12]}"
