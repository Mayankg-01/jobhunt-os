# JobHunt OS

A production-grade, agentic **job application engine**. It turns a job posting
into a complete, ATS-friendly application bundle — tailored résumé (PDF + HTML),
cover letter, and a LinkedIn opener — every word verified against what's really
on your résumé, so nothing is ever fabricated.

Built to be **honest**: the eval layer refuses to ship a bundle that claims a
stat it can't back, misses your contact info, or runs long on a DM.

## What's in a bundle

| Artifact        | What it does                                              |
|-----------------|-----------------------------------------------------------|
| `résumé` (PDF+HTML) | Single-column, ATS-friendly, requirements-first ordering |
| Cover letter    | Real projects, real numbers, tailored per posting        |
| LinkedIn DM     | Short (<320 ch) opener for recruiters                     |
| Evaluation      | Fit %, gaps, and a pass/fail gate before you submit      |

## Quickstart

```bash
pip install -e .            # or: pip install -e ".[dev]" for tests

# Build a bundle for every shortlisted job (CSV from job-scout; defaults to
# your real list in data/jobs.csv when present)
python -m jobhunt demo --limit 8

# Or build one bundle on demand
python -m jobhunt build --company cohere --title "Member of Technical Staff, Agent Code" --keywords "langchain,rag,llm,fastapi"

# Run the API  (health, /api/build, /api/resume/{id}, dashboard at /apply)
python -m jobhunt serve

# One-click apply: opens the posting, stages the cover letter on your clipboard,
# and logs the application — the final submit stays human, by design.
python -m jobhunt apply --company cohere --title "Member of Technical Staff, Agent Code"

# Application pipeline ledger
python -m jobhunt track list
python -m jobhunt track set --job 22f3c0... --status interviewing
```

Common outputs land in `data/applications/<job_id>/` (PDF + HTML + artifacts).
Applications are tracked in `data/applications.jsonl`
(`preparing → ready → applied → interviewing → offer | closed → archived`).

## Apply pipeline (one-click apply)

Every application is staged so the **only** human action on the employer's
portal is the final submit — auto-submitting violates Greenhouse/Lever/LinkedIn
ToS and gets accounts flagged, so this stays permissioned:

| Piece | What the OS does |
|-------|------------------|
| Open the posting | `webbrowser` fires the role page in one click |
| Copy the cover letter | staged on the clipboard via `Set-Clipboard` |
| Copy the LinkedIn DM | ready to paste into the recruiter inbox |
| `mailto:` link | whole letter pre-filled, ready to send |
| Résumé PDF | landing in `data/applications/<job_id>/resume.pdf` |
| Status ledger | `data/applications.jsonl` after each stage |

Dashboard at `/apply` (run `serve`): page ↗, copy cover, copy DM, résumé ↗
buttons per row. Statuses update live from the tracker.

## Self-serve bundle builder (public)

The front door is **you**: anyone can land on `/`, paste their own profile
(JSON) + a posting, and receive a tailored cover letter, LinkedIn DM, and
ATS-ready résumé PDF — all generated from *their* data, nothing persisted,
nothing fabricated. No owner data is exposed.

| Endpoint | Scope |
|----------|-------|
| `GET /` | Landing + builder UI |
| `POST /api/self` | `{profile, job}` → cover, DM, résumé PDF/HTML, mailto |
| `GET /bundles/{run}/*` | the visitor's generated artifacts |
| `/health` | uptime probe |

The owner pipeline (`/api/build`, `/api/applications`, `/apply` dashboard) is
behind `ADMIN_TOKEN` — set it in the environment or in your deploy config, and
those endpoints return `401` without `?token=` / `Authorization: Bearer`.

## Deploy to the public

1. Push this repo to GitHub.
2. **Render (free):** create a blueprint from `render.yaml` in this repo.
   Render builds the Dockerfile, injects a generated `ADMIN_TOKEN`, runs
   `HEALTHCHECK` against `/health`, and serves the builder.
3. Or run anywhere Docker runs: `docker run -p 8020:8020 -v data:/data jobhunt-os`
   (set `-e OPENAI_API_KEY=...` to sharpen research angles).

## Optional LLM credibility boost

Set `OPENAI_API_KEY` (see `.env.example`). With a key we use a real model to
sharpen research angles; without it, everything still works via deterministic,
fact-safe templates — nothing fabricates numbers either way.

## Evaluation (does it clear the gate?)

`tests/` lock the behavior (`pytest`):

- `fit_score >= 0.6` before a bundle is "submittable"
- contact info must appear in the résumé
- four sections (`Summary/Skills/Experience/Projects`) must exist
- **no fabricated statistics** — percentages not in your real record are flagged
- LinkedIn DM must stay ≤320 characters

## Run everywhere

- **Docker**: `docker build -t jobhunt-os . && docker run -p 8020:8020 jobhunt-os`
- **CI**: `.github/workflows/ci.yml` runs the suite on every push.

## Wish list (add weight-bearing)

- [ ] Tailor PDF page per job title in file header
- [ ] Rate each bundle for years-of-experience alignment
- [x] Pipeline status tracker (applied / interviewed / offer)