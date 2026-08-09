"""Domain models for JobHunt OS."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Profile:
    name: str
    headline: str
    location: str
    email: str
    phone: str
    github: str
    linkedin: str
    summary: str
    skills: dict = field(default_factory=dict)          # {"gate": ["python", ...], ...}
    experience: list = field(default_factory=list)      # dict items
    projects: list = field(default_factory=list)        # dict items
    education: list = field(default_factory=list)
    achievements: list = field(default_factory=list)

    def skill_set(self) -> set[str]:
        return {s.lower() for group in self.skills.values() for s in group}


@dataclass
class JobPosting:
    id: str
    company: str
    title: str
    location: str = ""
    url: str = ""
    score: float = 0.0
    keywords: list = field(default_factory=list)        # requirements to target

    def required_keywords(self) -> list[str]:
        return [k.strip().lower() for k in self.keywords if k and k.strip()]


@dataclass
class Research:
    angles: list[str] = field(default_factory=list)     # legit talking points


@dataclass
class ApplicationBundle:
    resume_pdf: str
    resume_html: str
    cover_letter: str
    linkedin_dm: str
    script_notes: str = ""


@dataclass
class Evaluation:
    metrics: dict = field(default_factory=dict)          # scores
    checks: dict = field(default_factory=dict)           # pass/fail booleans

    @property
    def qualified(self) -> bool:
        return all(self.checks.values())