# JobHunt OS

> **AI-native job hunt operating system** — Resume tailoring, outreach automation, interview prep, and pipeline tracking. All in one CLI.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://docker.com)

## Features

| Engine | Capabilities |
|--------|--------------|
| **Resume** | JD-parsing → AI tailoring → Quality gate (13 checks) → PDF/DOCX generation |
| **Outreach** | LinkedIn connect + message drafting → Queued sending → Follow-up automation |
| **Interview** | Company research → Technical topics → STAR stories → Daily briefs |
| **Pipeline** | Application tracking → Status workflow → Analytics → Google Sheets sync |
| **Search** | Multi-source (LinkedIn, Indeed, Glassdoor, Google) → Scheduled searches → Local storage |

## Quick Start

### Option 1: Local Install (Recommended)

```bash
# Clone and install
git clone https://github.com/yourusername/jobhunt-os
cd jobhunt-os
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env with your API keys

# Initialize database
jobhunt db init

# Create your profile
jobhunt profile create

# Start hunting!
jobhunt search run "Senior Python Engineer" --location "San Francisco" --remote
jobhunt resume tailor ~/resume.pdf "paste job description here"
jobhunt outreach draft "Jane Smith" "Acme Corp" --title "Engineering Manager"
jobhunt interview prep "Acme Corp" "Senior Python Engineer"
jobhunt pipeline summary
```

### Option 2: Docker (Production)

```bash
# Configure
cp .env.example .env
# Edit .env with your values
# Generate secure password: openssl rand -hex 32

# Start stack
cd infrastructure
docker compose up -d

# Run commands inside container
docker exec -it jobhunt-os jobhunt profile create
docker exec -it jobhunt-os jobhunt search run "Senior Python Engineer"
```

## Commands Overview

```bash
# Profile management
jobhunt profile show
jobhunt profile create --interactive

# Resume tailoring
jobhunt resume tailor resume.pdf "Job description..."
jobhunt resume parse resume.pdf
jobhunt resume quality tailored_resume.json "Job description..."

# Job search
jobhunt search run "Python Engineer" --location "NYC" --remote --save --name "python-nyc"
jobhunt search list --limit 50 --company "Google"

# Outreach automation
jobhunt outreach draft "John Doe" "Acme Corp" --title "Hiring Manager" --job "Senior Engineer"
jobhunt outreach queue <app-id> <contact-id> "Connection note" --followup "Follow up message"
jobhunt outreach send --max 10
jobhunt outreach followups

# Interview prep
jobhunt interview prep "Acme Corp" "Senior Engineer" --round technical
jobhunt interview brief <prep-id>
jobhunt interview list

# Pipeline tracking
jobhunt pipeline summary
jobhunt pipeline list --status applied
jobhunt pipeline detail <app-id>
jobhunt pipeline update <app-id> phone_screen --salary 180000
jobhunt pipeline export --format csv
jobhunt pipeline sync-sheets

# Company & contact management
jobhunt company add "Acme Corp" --domain acme.com --industry "FinTech"
jobhunt company contact "Acme Corp" "Jane Smith" --title "Eng Manager" --email "jane@acme.com"

# Database
jobhunt db init
jobhunt db reset --yes
```

## Configuration

### Required
- **AI Provider**: OpenAI, Anthropic, or OpenRouter API key in `.env`

### Optional
- **LinkedIn**: Enable with `JH_LI_ENABLED=true` and add `li_at` cookie
- **Google Sheets**: Enable with `JH_GOOGLE_ENABLED=true` and service account credentials
- **PostgreSQL**: Use `JH_DB_TYPE=postgresql` for production

## Architecture

```
jobhunt-os/
├── src/jobhunt/
│   ├── core/          # Config, models, settings
│   ├── engines/       # Resume, Outreach, Interview, Pipeline, Search
│   ├── storage/       # SQLAlchemy models, repositories
│   ├── cli/           # Typer CLI commands
│   └── utils/         # AI client, helpers
├── infrastructure/    # Docker, Docker Compose
├── tests/             # Pytest suite
└── landing/           # Marketing page (GitHub Pages)
```

## Data Privacy

- **Local-first**: SQLite by default, your data never leaves your machine
- **No telemetry**: Zero tracking, no analytics
- **Credentials**: Stored in `.env` (gitignored) or OS keyring
- **LinkedIn**: Uses your own session cookie, no third-party access

## Deployment

### GitHub Pages (Landing Page)
The `landing/` folder deploys automatically to GitHub Pages via Actions.

### Docker Production
```bash
# Server setup
docker compose -f infrastructure/docker-compose.yml up -d

# Scheduled searches (cron or systemd)
docker exec jobhunt-scheduler jobhunt search run "your queries"
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .
ruff format .

# Type check
mypy src/
```

## Roadmap

- [ ] Web dashboard (FastAPI + React)
- [ ] Email outreach (Gmail/Outlook API)
- [ ] Resume versioning & A/B testing
- [ ] Interview scheduler integration (Calendly)
- [ ] Salary negotiation coach
- [ ] Multi-user support for teams

## License

MIT — See [LICENSE](LICENSE) for details.

## Contributing

1. Fork the repo
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a PR

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/jobhunt-os/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/jobhunt-os/discussions)
- **Email**: mittal.shreya91@gmail.com

---

Built with ❤️ by [Shreya Mittal](https://linkedin.com/in/shreya-mittal-65404b4b)