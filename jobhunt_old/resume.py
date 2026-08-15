"""Tailored résumé renderer. Same content, two outputs:
  - PDF via reportlab (single column, Helvetica — ATS-friendly)
  - self-contained HTML for instant preview in the browser

Tailoring = reorder skills/projects so the role's keywords lead the page.
"""

from __future__ import annotations

import html as html_mod
from pathlib import Path

from .domain import JobPosting, Profile
from .scoring import normalize, present, top_projects

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (HRFlowable, Paragraph, SimpleDocTemplate, Spacer)


def _tuned_summary(profile: Profile, job: JobPosting) -> str:
    reqs = job.required_keywords()
    if not reqs:
        return profile.summary
    top = ", ".join(reqs[:6])
    suffix = f" Optimized for {top}." if top else ""
    return profile.summary + suffix


def _tuned_skills(profile: Profile, job: JobPosting) -> list[str]:
    skillset = profile.skill_set()
    reqs = job.required_keywords()
    def rank(k):
        return 0 if k in reqs else 1   # matched keywords lead
    flat = sorted(skillset, key=rank)
    # dedupe keys already normalized in skill_set()
    return flat


def build(profile: Profile, job: JobPosting, out_dir: Path) -> tuple[Path, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "resume_tailored.pdf"
    _pdf(profile, job, pdf_path)
    html_str = _html(profile, job)
    html_path = out_dir / "resume_tailored.html"
    html_path.write_text(html_str, encoding="utf-8")
    return pdf_path, html_str


# ---------------------------------------------------------------- pdf
_LABEL = ParagraphStyle("lbl", fontName="Helvetica-Bold", fontSize=7.5,
                        textColor="#1f8a55", spaceBefore=10, spaceAfter=2)
_P = ParagraphStyle("p", fontName="Helvetica", fontSize=9, leading=12.5)
_B = ParagraphStyle("b", fontName="Helvetica-Bold", fontSize=9.5, leading=12)
_H = ParagraphStyle("h", fontName="Helvetica", fontSize=11, leading=13)


def _pdf(profile: Profile, job: JobPosting, out: Path) -> None:
    doc = SimpleDocTemplate(str(out), pagesize=A4,
                            leftMargin=18*mm, rightMargin=18*mm,
                            topMargin=14*mm, bottomMargin=14*mm)
    story = []
    story.append(Paragraph(f"{profile.name} — {profile.headline}", _H))
    story.append(Paragraph(
        f"{profile.location} · {profile.email} · {profile.phone} · "
        f"{profile.github} · {profile.linkedin}", _LABEL))
    story.append(HRFlowable(width="100%", thickness=0.7, color="#232b27"))
    story.append(Paragraph(_tuned_summary(profile, job), _P))
    story.append(Paragraph("SKILLS", _LABEL))
    story.append(Paragraph(", ".join(_tuned_skills(profile, job)), _P))
    story.append(Paragraph("EXPERIENCE", _LABEL))
    for role in profile.experience:
        story.append(Paragraph(f"<b>{role['title']}</b> — {role['company']} · {role.get('period','')}", _P))
        for b in role.get("bullets", []):
            story.append(Paragraph(f"• {b}", _P))
    story.append(Paragraph("PROJECTS", _LABEL))
    wanted = top_projects(profile, job, 3)
    for proj in profile.projects:
        if proj.get("name") not in wanted:
            continue
        tags = " · ".join(proj.get("tags", []) or [])
        story.append(Paragraph(f"<b>{proj['name']}</b> — {proj.get('desc','')} ({tags})", _P))
    story.append(Paragraph("EDUCATION", _LABEL))
    for edu in profile.education:
        story.append(Paragraph(f"<b>{edu['degree']}</b> — {edu['school']} · {edu.get('period','')}", _P))
    doc.build(story)


# ------------------------------------------------------------ html
def _html(profile: Profile, job: JobPosting) -> str:
    skills = ", ".join(_tuned_skills(profile, job))
    projects = []
    for proj in profile.projects[:3]:
        projects.append(f"<li><b>{html_mod.escape(proj.get('name',''))}</b> — "
                        f"{html_mod.escape(proj.get('desc','') or '')}</li>")
    exp = ""
    for role in profile.experience:
        exp += f"<h4>{html_mod.escape(role['title'])} — {html_mod.escape(role['company'])} · {role.get('period','')}</h4><ul>"
        exp += "".join(f"<li>{html_mod.escape(b)}</li>" for b in role.get("bullets", []))
        exp += "</ul>"
    return f"""<!doctype html><meta charset="utf-8"><title>Resume</title>
<style>body{{font:14px/1.5 ui-sans-serif,system-ui;max-width:640px;margin:32px auto}}
h1{{font-size:20px}} h3{{color:#1f8a55;text-transform:uppercase;font-size:11px;letter-spacing:.08em;margin-top:20px}}
a{{color:#1b7f50}} ul{{margin:4px 0}}</style>
<h1>{profile.name} — {html_mod.escape(profile.headline)}</h1>
<p><a href="mailto:{profile.email}">{profile.email}</a> · {profile.location} · <a href="{profile.github}">{profile.github}</a> · <a href="{profile.linkedin}">{profile.linkedin}</a></p>
<p><i>Tailored for: {html_mod.escape(job.title)} @ {html_mod.escape(job.company)}</i></p>
<h2>Summary</h2><p>{html_mod.escape(_tuned_summary(profile, job))}</p>
<h2>Skills</h2><p>{html_mod.escape(skills)}</p>
<h2>Experience</h2>{exp}
<h2>Projects</h2><ul>{''.join(projects)}</ul>
"""