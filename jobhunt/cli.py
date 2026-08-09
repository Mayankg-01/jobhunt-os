"""CLI: python -m jobhunt demo | serve | build | apply | track"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .agents import generate, summarize
from .apply import one_click, tracker
from .config import SETTINGS
from .domain import JobPosting
from .ingest import load_jobs
from .profile import load_profile
from .scoring import title_keywords


def _demo(csv_path: str, out: str, limit: int) -> int:
    profile = load_profile(str(SETTINGS.profile_path))
    jobs = load_jobs(csv_path)[:limit]
    for job in jobs:
        if not job.keywords:
            job.keywords = title_keywords(job.title)
        try:
            bundle, ev = generate(profile, job, Path(out) / "applications")
        except Exception as exc:  # pragma: no cover
            print(f"  ! {job.company} / {job.title}: {exc}")
            continue
        print(summarize(job, profile, ev))
    print(f"processed {len(jobs)} jobs -> {Path(out) / 'applications'}")
    return 0


def _serve(host: str, port: int) -> int:
    import uvicorn
    from .api import app
    uvicorn.run(app, host=host, port=port)
    return 0


def _build(company: str, title: str, keywords: str, url: str = "") -> int:
    profile = load_profile(str(SETTINGS.profile_path))
    job = JobPosting(id=hashlib.sha256(f"{company}|{title}".encode()).hexdigest()[:12],
                     company=company, title=title, url=url,
                     keywords=[k.strip() for k in keywords.split(",") if k.strip()])
    bundle, ev = generate(profile, job, Path(SETTINGS.data_dir) / "applications")
    print(summarize(job, profile, ev))
    print("resume:", bundle.resume_pdf)
    return 0


def _apply(company: str, title: str) -> int:
    """One-click apply: stage bundle -> open page + copy cover from the tray.
    Final submit stays human, by design."""
    profile = load_profile(str(SETTINGS.profile_path))
    job = JobPosting(id=hashlib.sha256(f"{company}|{title}".encode()).hexdigest()[:12],
                     company=company, title=title,
                     keywords=title_keywords(title))
    bundle, ev = generate(profile, job, Path(SETTINGS.data_dir) / "applications")
    sheet = one_click(profile, job, bundle, copy=True, open_page=True)
    tracker().upsert(job.id, company, title, job.url, "ready", resume_pdf=bundle.resume_pdf)
    print(f"staged {company} · {title} -> opened page, cover on clipboard, status=ready")
    print(json.dumps(sheet, indent=2))
    return job.id


def _track(cmd: str, job_id: str, status: str | None) -> int:
    tr = tracker()
    if cmd == "list":
        for r in tr.list():
            print(f"{r.get('status','?'):12} {r['job_id']}  {r['company']} — {r['title']}")
        return 0
    if cmd == "set":
        row = tr.set_status(job_id, status)
        print(json.dumps(row) if row else "not found")
        return 0 if row else 1
    return 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="jobhunt")
    sub = p.add_subparsers(dest="cmd")

    d = sub.add_parser("demo", help="build bundles for every job in a scout CSV")
    d.add_argument("--csv", default=str(SETTINGS.jobs_csv_path))
    d.add_argument("--out", default=str(SETTINGS.data_dir))
    d.add_argument("--limit", type=int, default=8)

    s = sub.add_parser("serve", help="run the FastAPI service (dashboard at /apply)")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8020)

    b = sub.add_parser("build", help="build one application bundle")
    b.add_argument("--company", required=True)
    b.add_argument("--title", required=True)
    b.add_argument("--keywords", required=True)
    b.add_argument("--url", default="")

    a = sub.add_parser("apply", help="one-click apply: open + stage clipboard")
    a.add_argument("--company", required=True)
    a.add_argument("--title", required=True)

    t = sub.add_parser("track", help="application pipeline ledger")
    t.add_argument("action", choices=["list", "set"])
    t.add_argument("--job", default="")
    t.add_argument("--status", default="applied")

    args = p.parse_args(argv)
    if args.cmd == "demo":
        return _demo(args.csv, args.out, args.limit)
    if args.cmd == "serve":
        return _serve(args.host, args.port)
    if args.cmd == "build":
        return _build(args.company, args.title, args.keywords, args.url)
    if args.cmd == "apply":
        _apply(args.company, args.title)
        return 0
    if args.cmd == "track":
        return _track(args.action, args.job, args.status)
    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())