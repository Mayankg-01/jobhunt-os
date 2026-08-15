from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from jobhunt.core.config import settings
from jobhunt.utils.ai import generate_interview_prep


class InterviewEngine:
    def __init__(self):
        self.prep_dir = settings.data_dir / "interviews"
        self.prep_dir.mkdir(parents=True, exist_ok=True)

    async def generate_prep_pack(
        self,
        company_info: dict,
        job_info: dict,
        user_profile: dict,
        round_type: str = "technical",
    ) -> dict:
        prep = await generate_interview_prep(company_info, job_info, user_profile, round_type)

        if "error" in prep:
            return prep

        prep_id = f"prep_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        prep_path = self.prep_dir / prep_id
        prep_path.mkdir(parents=True, exist_ok=True)

        prep["prep_id"] = prep_id
        prep["generated_at"] = datetime.utcnow().isoformat()
        prep["company"] = company_info.get("name", "Unknown")
        prep["role"] = job_info.get("title", "Unknown")
        prep["round_type"] = round_type

        with open(prep_path / "prep.json", "w") as f:
            json.dump(prep, f, indent=2)

        self._generate_markdown(prep, prep_path / "prep.md")

        return prep

    def _generate_markdown(self, prep: dict, output_path: Path) -> None:
        lines = [
            f"# Interview Prep: {prep.get('company', 'Company')} - {prep.get('role', 'Role')}",
            f"**Round:** {prep.get('round_type', '').replace('_', ' ').title()}",
            f"**Generated:** {prep.get('generated_at', '')}",
            "",
            "---",
            "",
            "## Company Research",
            prep.get("company_research", "Not available"),
            "",
            "## Technical Topics to Review",
        ]

        for topic in prep.get("technical_topics", []):
            lines.append(f"- {topic}")

        lines.extend([
            "",
            "## Behavioral Questions (STAR Format)",
        ])

        for q in prep.get("behavioral_questions", []):
            lines.extend([
                f"### {q.get('question', '')}",
                f"**Situation:** {q.get('situation', '')}",
                f"**Task:** {q.get('task', '')}",
                f"**Action:** {q.get('action', '')}",
                f"**Result:** {q.get('result', '')}",
                f"**Company Value Alignment:** {q.get('value_alignment', '')}",
                "",
            ])

        lines.extend([
            "## Questions to Ask Interviewer",
        ])

        for q in prep.get("questions_to_ask", []):
            lines.append(f"- {q}")

        lines.extend([
            "",
            "## Salary Negotiation Data",
            prep.get("salary_data", "Not available"),
            "",
            "## Daily Focus Brief",
            prep.get("daily_brief", "Not available"),
        ])

        output_path.write_text("\n".join(lines))

    def get_daily_brief(self, prep_id: str) -> str:
        prep_path = self.prep_dir / prep_id / "prep.json"
        if not prep_path.exists():
            return "Prep pack not found"

        import json
        with open(prep_path) as f:
            prep = json.load(f)

        today = datetime.utcnow().date()
        scheduled_interviews = prep.get("scheduled_interviews", [])

        brief_lines = [f"# Daily Interview Brief - {today.strftime('%A, %B %d')}", ""]

        todays_interviews = [i for i in scheduled_interviews if i.get("date") == today.isoformat()]
        if todays_interviews:
            brief_lines.append("## Today's Interviews")
            for iv in todays_interviews:
                brief_lines.append(f"- **{iv.get('time', '')}** - {iv.get('company', '')} - {iv.get('round_type', '')} with {', '.join(iv.get('interviewers', []))}")
        else:
            brief_lines.append("## No interviews scheduled today")

        brief_lines.extend(["", "## Focus Areas for Today"])

        prep_progress = prep.get("prep_progress", {})
        for area, status in prep_progress.items():
            icon = "✅" if status == "done" else "🔄" if status == "in_progress" else "⏳"
            brief_lines.append(f"- {icon} {area.replace('_', ' ').title()}")

        brief_lines.extend(["", "## Quick Review"])

        for topic in prep.get("technical_topics", [])[:3]:
            brief_lines.append(f"- {topic}")

        brief_lines.extend(["", "## STAR Story Refresh"])
        for story in prep.get("behavioral_questions", [])[:2]:
            brief_lines.append(f"- **{story.get('question', '')[:60]}...** → {story.get('result', '')[:80]}")

        return "\n".join(brief_lines)

    def list_prep_packs(self) -> list[dict]:
        packs = []
        for prep_dir in self.prep_dir.iterdir():
            if prep_dir.is_dir():
                prep_file = prep_dir / "prep.json"
                if prep_file.exists():
                    import json
                    with open(prep_file) as f:
                        prep = json.load(f)
                    packs.append({
                        "prep_id": prep.get("prep_id"),
                        "company": prep.get("company"),
                        "role": prep.get("role"),
                        "round_type": prep.get("round_type"),
                        "generated_at": prep.get("generated_at"),
                    })
        return sorted(packs, key=lambda x: x["generated_at"], reverse=True)
