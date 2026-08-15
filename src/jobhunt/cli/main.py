from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from jobhunt.core.config import UserProfile, load_profile, save_profile, settings
from jobhunt.core.models import JobStatus
from jobhunt.engines.interview import InterviewEngine
from jobhunt.engines.outreach import OutreachEngine, OutreachQueue
from jobhunt.engines.pipeline import GoogleSheetsSync, PipelineTracker
from jobhunt.engines.resume import ResumeParser, ResumeQualityGate, ResumeTailor
from jobhunt.engines.search import JobSearchEngine
from jobhunt.storage.database import init_db, reset_db, session_scope
from jobhunt.storage.repositories import (
    ApplicationRepository,
    CompanyRepository,
    ContactRepository,
    JobPostingRepository,
)

app = typer.Typer(
    name="jobhunt",
    help="JobHunt OS - AI-native job hunt operating system",
    rich_markup_mode="rich",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool):
    if value:
        console.print("JobHunt OS v0.1.0")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[Optional[bool], typer.Option("--version", "-v", callback=version_callback)] = None,
):
    pass


# ============ PROFILE COMMANDS ============
profile_app = typer.Typer(name="profile", help="Manage user profiles")
app.add_typer(profile_app)


@profile_app.command("show")
def profile_show(profile_name: str = "default"):
    """Show current profile"""
    profile = load_profile(profile_name)
    console.print(Panel.fit(f"[bold]{profile.name}[/bold]", title="Profile"))
    console.print(f"Email: {profile.email}")
    console.print(f"Location: {profile.location}")
    console.print(f"Target Roles: {', '.join(profile.target_roles)}")
    console.print(f"Target Industries: {', '.join(profile.target_industries)}")
    console.print(f"Target Locations: {', '.join(profile.target_locations)}")
    console.print(f"Experience: {profile.years_experience} years")
    console.print(f"Visa: {profile.visa_status}")
    console.print(f"Salary Range: ${profile.salary_min:,} - ${profile.salary_max:,}")


@profile_app.command("create")
def profile_create(
    profile_name: str = "default",
    interactive: bool = typer.Option(True, "--interactive/--no-interactive", "-i/-I"),
):
    """Create a new profile"""
    if interactive:
        console.print("[bold]Creating new profile...[/bold]")
        name = Prompt.ask("Name", default="Your Name")
        email = Prompt.ask("Email", default="you@example.com")
        location = Prompt.ask("Location", default="City, State")
        linkedin = Prompt.ask("LinkedIn URL", default="")
        github = Prompt.ask("GitHub URL", default="")
        portfolio = Prompt.ask("Portfolio URL", default="")
        years_exp = int(Prompt.ask("Years of Experience", default="5"))
        visa = Prompt.ask("Visa Status", default="US Citizen")
        salary_min = int(Prompt.ask("Min Salary", default="150000"))
        salary_max = int(Prompt.ask("Max Salary", default="300000"))

        roles = Prompt.ask("Target Roles (comma-separated)", default="Software Engineer,Senior Software Engineer")
        industries = Prompt.ask("Target Industries (comma-separated)", default="Technology,FinTech,AI/ML")
        locations = Prompt.ask("Target Locations (comma-separated)", default="San Francisco,Remote")

        profile = UserProfile(
            name=name,
            email=email,
            location=location,
            linkedin_url=linkedin,
            github_url=github,
            portfolio_url=portfolio,
            years_experience=years_exp,
            visa_status=visa,
            salary_min=salary_min,
            salary_max=salary_max,
            target_roles=[r.strip() for r in roles.split(",")],
            target_industries=[i.strip() for i in industries.split(",")],
            target_locations=[l.strip() for l in locations.split(",")],
        )
    else:
        profile = UserProfile()

    save_profile(profile, profile_name)
    console.print(f"[green]Profile '{profile_name}' saved![/green]")


# ============ RESUME COMMANDS ============
resume_app = typer.Typer(name="resume", help="Resume tailoring and management")
app.add_typer(resume_app)


@resume_app.command("tailor")
def resume_tailor(
    resume_path: Annotated[Path, typer.Argument(help="Path to base resume (PDF or DOCX)")],
    job_description: Annotated[str, typer.Argument(help="Job description text or path to file")],
    profile_name: str = typer.Option("default", "--profile", "-p"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o"),
):
    """Tailor resume to a job description"""
    if not resume_path.exists():
        console.print(f"[red]Resume not found: {resume_path}[/red]")
        raise typer.Exit(1)

    if Path(job_description).exists():
        job_description = Path(job_description).read_text()

    profile = load_profile(profile_name)
    tailor = ResumeTailor()

    console.print("[bold]Tailoring resume...[/bold]")
    result = asyncio.run(tailor.tailor(resume_path, job_description, profile.model_dump(), output_dir))

    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        return

    console.print("[green]Resume tailored successfully![/green]")
    console.print(f"Resume ID: {result['resume_id']}")
    console.print(f"Quality Score: {result['quality_gate'].get('score', 'N/A')}/10")
    console.print(f"Passed: {result['quality_gate'].get('passed', False)}")

    if result['quality_gate'].get('feedback'):
        console.print(Panel(result['quality_gate']['feedback'], title="Feedback"))

    for file_type, path in result['files'].items():
        console.print(f"  {file_type}: {path}")


@resume_app.command("parse")
def resume_parse(
    resume_path: Annotated[Path, typer.Argument(help="Path to resume (PDF or DOCX)")],
):
    """Parse and display resume structure"""
    if not resume_path.exists():
        console.print(f"[red]Resume not found: {resume_path}[/red]")
        raise typer.Exit(1)

    parser = ResumeParser()
    if resume_path.suffix == ".pdf":
        result = parser.parse_pdf(resume_path)
    else:
        result = parser.parse_docx(resume_path)

    console.print(Panel(result.get("raw_text", "")[:2000], title="Parsed Content"))


@resume_app.command("quality")
def resume_quality(
    resume_path: Annotated[Path, typer.Argument(help="Path to tailored resume JSON")],
    job_description: Annotated[str, typer.Argument(help="Job description text or path to file")],
):
    """Run quality gate on a tailored resume"""
    import json
    if Path(job_description).exists():
        job_description = Path(job_description).read_text()

    with open(resume_path) as f:
        resume = json.load(f)

    result = ResumeQualityGate.check(resume, job_description)
    console.print(f"Passed: {result['passed']}")
    if result['issues']:
        console.print("[red]Issues:[/red]")
        for issue in result['issues']:
            console.print(f"  - {issue}")
    if result['warnings']:
        console.print("[yellow]Warnings:[/yellow]")
        for warn in result['warnings']:
            console.print(f"  - {warn}")


# ============ SEARCH COMMANDS ============
search_app = typer.Typer(name="search", help="Job search and discovery")
app.add_typer(search_app)


@search_app.command("run")
def search_run(
    query: Annotated[str, typer.Argument(help="Search query")],
    location: str = typer.Option("", "--location", "-l"),
    remote: bool = typer.Option(False, "--remote", "-r"),
    job_type: str = typer.Option("", "--type", "-t"),
    experience: str = typer.Option("", "--experience", "-e"),
    days: int = typer.Option(7, "--days", "-d"),
    save: bool = typer.Option(False, "--save", "-s"),
    name: str = typer.Option("", "--name", "-n"),
):
    """Run a job search"""
    engine = JobSearchEngine()

    console.print(f"[bold]Searching for: {query}[/bold]")
    result = asyncio.run(engine.search_and_store(
        query=query,
        location=location,
        is_remote=remote,
        job_type=job_type,
        experience_level=experience,
        date_posted_days=days,
    ))

    console.print(f"[green]Found: {result['searched']} jobs, Stored: {result['stored']}[/green]")

    if save and name:
        engine.save_search_query(name, query, {
            "location": location,
            "is_remote": remote,
            "job_type": job_type,
            "experience_level": experience,
            "date_posted_days": days,
        })
        console.print(f"[green]Search query '{name}' saved![/green]")


@search_app.command("list")
def search_list(
    limit: int = typer.Option(20, "--limit"),
    company: str = typer.Option("", "--company"),
    remote: bool = typer.Option(None, "--remote/--onsite"),
):
    """List stored job postings"""
    with session_scope() as session:
        repo = JobPostingRepository(session)
        jobs = repo.list(company=company or None, is_remote=remote, limit=limit)

    table = Table(title="Job Postings")
    table.add_column("Company", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Location", style="green")
    table.add_column("Remote", style="yellow")
    table.add_column("Source", style="magenta")

    for job in jobs:
        table.add_row(job.company, job.title[:50], job.location, "✓" if job.is_remote else "✗", job.source)

    console.print(table)


# ============ OUTREACH COMMANDS ============
outreach_app = typer.Typer(name="outreach", help="LinkedIn outreach automation")
app.add_typer(outreach_app)


@outreach_app.command("draft")
def outreach_draft(
    contact_name: Annotated[str, typer.Argument(help="Contact name")],
    company_name: Annotated[str, typer.Argument(help="Company name")],
    contact_title: str = typer.Option("", "--title"),
    contact_email: str = typer.Option("", "--email"),
    contact_linkedin: str = typer.Option("", "--linkedin"),
    job_title: str = typer.Option("", "--job"),
    profile_name: str = typer.Option("default", "--profile", "-p"),
    message_type: str = typer.Option("connection", "--type"),
):
    """Draft outreach messages"""
    profile = load_profile(profile_name)

    contact = {"name": contact_name, "title": contact_title, "email": contact_email, "linkedin_url": contact_linkedin}
    company = {"name": company_name}
    job = {"title": job_title} if job_title else None

    console.print("[bold]Drafting outreach...[/bold]")
    result = asyncio.run(OutreachEngine().draft_messages(contact, company, job, profile.model_dump(), message_type))

    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        return

    console.print(Panel(result.get("connection_note", ""), title="Connection Note"))
    console.print(Panel(result.get("follow_up_message", ""), title="Follow-up Message"))
    if result.get("subject_line"):
        console.print(f"Subject: {result['subject_line']}")


@outreach_app.command("queue")
def outreach_queue(
    application_id: Annotated[str, typer.Argument(help="Application ID")],
    contact_id: Annotated[str, typer.Argument(help="Contact ID")],
    connection_note: Annotated[str, typer.Argument(help="Connection note")],
    follow_up: str = typer.Option("", "--followup"),
    subject: str = typer.Option("", "--subject"),
):
    """Queue outreach messages for sending"""
    messages = {"connection_note": connection_note, "follow_up_message": follow_up, "subject_line": subject}
    result = asyncio.run(OutreachEngine().queue_outreach(application_id, contact_id, messages))
    console.print(f"[green]Queued: {result}[/green]")


@outreach_app.command("send")
def outreach_send(
    max_sends: int = typer.Option(10, "--max", "-m"),
):
    """Send queued outreach messages"""
    console.print(f"[bold]Sending up to {max_sends} messages...[/bold]")
    result = asyncio.run(OutreachQueue(OutreachEngine()).daily_send(max_sends))
    console.print(f"Sent: {len(result)}")
    for r in result:
        console.print(f"  {r['message_id'][:8]} - {r['status']}")


@outreach_app.command("followups")
def outreach_followups():
    """Process follow-up messages"""
    engine = OutreachEngine()
    results = engine.process_followups()
    console.print(f"Processed: {len(results)} follow-ups")
    for r in results:
        console.print(f"  {r['message_id'][:8]} - {r['status']}")


# ============ INTERVIEW COMMANDS ============
interview_app = typer.Typer(name="interview", help="Interview preparation")
app.add_typer(interview_app)


@interview_app.command("prep")
def interview_prep(
    company_name: Annotated[str, typer.Argument(help="Company name")],
    job_title: Annotated[str, typer.Argument(help="Job title")],
    profile_name: str = typer.Option("default", "--profile", "-p"),
    round_type: str = typer.Option("technical", "--round", "-r"),
):
    """Generate interview prep pack"""
    profile = load_profile(profile_name)

    with session_scope() as session:
        company_repo = CompanyRepository(session)
        company = company_repo.get_by_name(company_name)
        company_info = {"name": company_name}
        if company:
            company_info = {
                "name": company.name,
                "industry": company.industry,
                "size": company.size,
                "description": company.description,
            }

    job_info = {"title": job_title}

    console.print("[bold]Generating interview prep...[/bold]")
    result = asyncio.run(InterviewEngine().generate_prep_pack(company_info, job_info, profile.model_dump(), round_type))

    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        return

    console.print(f"[green]Prep pack generated: {result['prep_id']}[/green]")
    console.print(f"Files saved to: {settings.data_dir}/interviews/{result['prep_id']}/")


@interview_app.command("brief")
def interview_brief(
    prep_id: Annotated[str, typer.Argument(help="Prep pack ID")],
):
    """Get daily interview brief"""
    brief = InterviewEngine().get_daily_brief(prep_id)
    console.print(Panel(brief, title="Daily Brief"))


@interview_app.command("list")
def interview_list():
    """List all prep packs"""
    packs = InterviewEngine().list_prep_packs()
    table = Table(title="Interview Prep Packs")
    table.add_column("ID", style="cyan")
    table.add_column("Company", style="white")
    table.add_column("Role", style="green")
    table.add_column("Round", style="yellow")
    table.add_column("Generated", style="magenta")

    for p in packs:
        table.add_row(p["prep_id"], p["company"], p["role"], p["round_type"], p["generated_at"][:10])

    console.print(table)


# ============ PIPELINE COMMANDS ============
pipeline_app = typer.Typer(name="pipeline", help="Application pipeline tracking")
app.add_typer(pipeline_app)


@pipeline_app.command("summary")
def pipeline_summary():
    """Show pipeline summary"""
    tracker = PipelineTracker()
    summary = tracker.get_pipeline_summary()

    console.print(Panel.fit(
        f"[bold]Total Applications:[/bold] {summary['total_applications']}\n"
        f"[bold]Response Rate:[/bold] {summary['response_rate']}%\n"
        f"[bold]Interview Rate:[/bold] {summary['interview_rate']}%\n"
        f"[bold]Offer Rate:[/bold] {summary['offer_rate']}%\n"
        f"[bold]Upcoming Interviews:[/bold] {summary['upcoming_interviews']}\n"
        f"[bold]Pending Follow-ups:[/bold] {summary['pending_followups']}",
        title="Pipeline Summary"
    ))

    table = Table(title="Applications by Status")
    table.add_column("Status", style="cyan")
    table.add_column("Count", style="white")
    for status, count in sorted(summary['by_status'].items(), key=lambda x: -x[1]):
        table.add_row(status, str(count))
    console.print(table)


@pipeline_app.command("list")
def pipeline_list(
    status: str = typer.Option("", "--status", "-s"),
    limit: int = typer.Option(20, "--limit"),
):
    """List applications"""
    with session_scope() as session:
        repo = ApplicationRepository(session)
        apps = repo.list(status=JobStatus(status) if status else None, limit=limit)

    table = Table(title="Applications")
    table.add_column("ID", style="dim")
    table.add_column("Company", style="cyan")
    table.add_column("Role", style="white")
    table.add_column("Status", style="green")
    table.add_column("Priority", style="yellow")
    table.add_column("Applied", style="magenta")

    for app in apps:
        table.add_row(
            str(app.id)[:8],
            app.company.name,
            app.job_posting.title[:30] if app.job_posting else "N/A",
            app.status.value,
            str(app.priority),
            app.applied_at.strftime("%Y-%m-%d") if app.applied_at else "",
        )
    console.print(table)


@pipeline_app.command("detail")
def pipeline_detail(
    app_id: Annotated[str, typer.Argument(help="Application ID")],
):
    """Show application details"""
    from uuid import UUID
    tracker = PipelineTracker()
    details = tracker.get_application_details(UUID(app_id))

    if not details:
        console.print("[red]Application not found[/red]")
        return

    console.print(Panel.fit(
        f"Company: {details['application']['company']}\n"
        f"Role: {details['application']['job_title']}\n"
        f"Status: {details['application']['status']}\n"
        f"Applied: {details['application']['applied_at'] or 'Not yet'}\n"
        f"Salary: {details['application']['salary_offered'] or 'N/A'}",
        title=f"Application {app_id[:8]}"
    ))

    if details['interviews']:
        table = Table(title="Interviews")
        table.add_column("Round")
        table.add_column("Type")
        table.add_column("Scheduled")
        table.add_column("Status")
        table.add_column("Score")
        for iv in details['interviews']:
            table.add_row(str(iv['round']), iv['type'], iv['scheduled'] or '', iv['status'], str(iv['score'] or ''))
        console.print(table)

    if details['outreach']:
        table = Table(title="Outreach")
        table.add_column("Status")
        table.add_column("Channel")
        table.add_column("Sent")
        table.add_column("Follow-ups")
        table.add_column("Next")
        for msg in details['outreach']:
            table.add_row(msg['status'], msg['channel'], msg['sent_at'] or '', str(msg['follow_ups']), msg['next_followup'] or '')
        console.print(table)


@pipeline_app.command("update")
def pipeline_update(
    app_id: Annotated[str, typer.Argument(help="Application ID")],
    status: Annotated[str, typer.Argument(help="New status")],
    salary: int = typer.Option(0, "--salary"),
    notes: str = typer.Option("", "--notes"),
):
    """Update application status"""
    from uuid import UUID
    tracker = PipelineTracker()
    kwargs = {}
    if salary:
        kwargs["salary_offered"] = salary
    if notes:
        kwargs["notes"] = notes

    success = tracker.update_status(UUID(app_id), JobStatus(status), **kwargs)
    console.print("[green]Updated[/green]" if success else "[red]Failed[/red]")


@pipeline_app.command("export")
def pipeline_export(
    format: str = typer.Option("csv", "--format", "-f"),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
):
    """Export pipeline to CSV or JSON"""
    tracker = PipelineTracker()
    if format == "csv":
        path = tracker.export_to_csv(output)
    else:
        path = tracker.export_to_json(output)
    console.print(f"[green]Exported to: {path}[/green]")


@pipeline_app.command("sync-sheets")
def pipeline_sync_sheets():
    """Sync pipeline to Google Sheets"""
    tracker = PipelineTracker()
    sync = GoogleSheetsSync()
    result = sync.sync(tracker)
    if result["success"]:
        console.print(f"[green]Synced {result['rows_synced']} rows[/green]")
    else:
        console.print(f"[red]Error: {result['error']}[/red]")


# ============ COMPANY COMMANDS ============
company_app = typer.Typer(name="company", help="Company management")
app.add_typer(company_app)


@company_app.command("add")
def company_add(
    name: Annotated[str, typer.Argument(help="Company name")],
    domain: str = typer.Option("", "--domain"),
    industry: str = typer.Option("", "--industry"),
    size: str = typer.Option("", "--size"),
    blacklist: bool = typer.Option(False, "--blacklist"),
    reason: str = typer.Option("", "--reason"),
):
    """Add or update a company"""
    with session_scope() as session:
        repo = CompanyRepository(session)
        company = repo.get_or_create(name=name, domain=domain or None, industry=industry or None, size=size or None)
        if blacklist:
            company.is_blacklisted = True
            company.blacklist_reason = reason
        session.flush()
    console.print(f"[green]Company '{name}' saved[/green]")


@company_app.command("contact")
def company_contact(
    company_name: Annotated[str, typer.Argument(help="Company name")],
    name: Annotated[str, typer.Argument(help="Contact name")],
    title: str = typer.Option("", "--title"),
    email: str = typer.Option("", "--email"),
    linkedin: str = typer.Option("", "--linkedin"),
    contact_type: str = typer.Option("hiring_manager", "--type"),
):
    """Add a contact to a company"""
    with session_scope() as session:
        company_repo = CompanyRepository(session)
        contact_repo = ContactRepository(session)
        company = company_repo.get_by_name(company_name)
        if not company:
            console.print(f"[red]Company not found: {company_name}[/red]")
            return
        contact = contact_repo.create(
            company_id=company.id,
            name=name,
            title=title or None,
            email=email or None,
            linkedin_url=linkedin or None,
            contact_type=contact_type,
        )
    console.print(f"[green]Contact added: {contact.name}[/green]")


# ============ DB COMMANDS ============
db_app = typer.Typer(name="db", help="Database management")
app.add_typer(db_app)


@db_app.command("init")
def db_init():
    """Initialize database"""
    init_db()
    console.print("[green]Database initialized[/green]")


@db_app.command("reset")
def db_reset(
    confirm: bool = typer.Option(False, "--yes", "-y"),
):
    """Reset database (destructive)"""
    if not confirm:
        confirm = Confirm.ask("This will delete all data. Continue?")
    if confirm:
        reset_db()
        console.print("[green]Database reset[/green]")


# ============ CONFIG COMMANDS ============
config_app = typer.Typer(name="config", help="Configuration")
app.add_typer(config_app)


@config_app.command("show")
def config_show():
    """Show current configuration"""
    console.print(Panel.fit(
        f"Data Dir: {settings.data_dir}\n"
        f"AI Provider: {settings.ai.provider}\n"
        f"AI Model: {settings.ai.model}\n"
        f"Database: {settings.database.type}\n"
        f"LinkedIn Enabled: {settings.linkedin.enabled}\n"
        f"Google Sheets Enabled: {settings.google.enabled}",
        title="Configuration"
    ))


@config_app.command("set-ai")
def config_set_ai(
    provider: Annotated[str, typer.Argument(help="Provider: openai, anthropic, openrouter")],
    api_key: Annotated[str, typer.Argument(help="API key")],
    model: str = typer.Option("", "--model"),
):
    """Set AI configuration"""
    env_path = Path(".env")
    content = env_path.read_text() if env_path.exists() else ""
    lines = [l for l in content.split("\n") if not l.startswith("JH_AI_")]
    lines.append(f"JH_AI_PROVIDER={provider}")
    lines.append(f"JH_AI_API_KEY={api_key}")
    if model:
        lines.append(f"JH_AI_MODEL={model}")
    env_path.write_text("\n".join(lines))
    console.print("[green]AI config saved to .env[/green]")


if __name__ == "__main__":
    app()
