"""CLI: python -m jobhunt demo | serve | build | apply | track"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
from pathlib import Path

from .agents import generate, summarize
from .apply import one_click, tracker
from .config import SETTINGS
from .domain import JobPosting
from .ingest import load_jobs
from .profile import load_profile
from .scoring import title_keywords


def _ascii(s: str) -> str:
    """Console-safe: any codepage (cp1252, cp437, UTF-8...) can render this."""
    return (s.replace("\u00b7", "|").replace("\u2014", "-")
             .encode("ascii", "replace").decode("ascii"))


def _demo(csv_path: str, out: str, limit: int) -> int:
    profile = load_profile(str(SETTINGS.profile_path))
    jobs = load_jobs(csv_path)[:limit]
    for job in jobs:
        if not job.keywords:
            job.keywords = title_keywords(job.title)
        try:
            bundle, ev = generate(profile, job, Path(out) / "applications")
        except Exception as exc:  # pragma: no cover
            print(f"  ! {_ascii(job.company)} / {_ascii(job.title)}: {exc}")
            continue
        tracker().upsert(job.id, job.company, job.title, job.url,
                         "ready", resume_pdf=bundle.resume_pdf)
        print(_ascii(summarize(job, profile, ev)))
    print(f"processed {len(jobs)} jobs -> {Path(out) / 'applications'}")
    return 0


def _serve(host: str, port: int, no_open: bool = False) -> int:
    import time
    import urllib.request

    def _open():
        if no_open:
            return
        import webbrowser
        webbrowser.open(f"http://{host}:{port}/")

    def _alive() -> bool:
        try:
            with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=1) as r:
                return r.status == 200
        except Exception:
            return False

    if _alive():
        # something is already serving on this port — just open the browser
        threading.Timer(0.2, _open).start()
        print(f"jobhunt already running at http://{host}:{port}/")
        return 0

    import uvicorn
    from .api import app

    t = threading.Timer(0.2, lambda: _sync_open(host, port, no_open))
    t.daemon = True
    t.start()

    print(f"jobhunt workspace -> http://{host}:{port}/   (Ctrl+C to stop)")
    try:
        uvicorn.run(app, host=host, port=port, log_level="warning")
    except OSError as exc:
        print(f"could not bind {host}:{port} - {exc}")
        return 1
    return 0


def _sync_open(host: str, port: int, no_open: bool) -> None:
    """Open the browser only once the app is actually responding."""
    if no_open:
        return
    import time
    import urllib.request
    for _ in range(40):  # ~20s budget for cold start
        try:
            with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=1) as r:
                if r.status == 200:
                    import webbrowser
                    webbrowser.open(f"http://{host}:{port}/")
                    return
        except Exception:
            pass
        time.sleep(0.5)


def _doctor() -> int:
    """Environment self-diagnostic — run if anything feels broken."""
    import platform
    good = True

    def check(name: str, detail: str, ok: bool) -> None:
        nonlocal good
        if not ok:
            good = False
        print(f"  [{'OK  ' if ok else 'FAIL'}] {name}: {detail}")

    check("python", platform.python_version(), True)
    for mod in ("fastapi", "uvicorn", "reportlab", "httpx", "pydantic"):
        try:
            __import__(mod)
            check(mod, "installed", True)
        except Exception:
            check(mod, "MISSING - run: python -m pip install -e .", False)
    try:
        profile = load_profile(str(SETTINGS.profile_path))
        check("profile", f"{_ascii(profile.name)} ({SETTINGS.profile_path})", True)
    except Exception as exc:
        check("profile", f"cannot load: {exc}", False)
    try:
        jobs = load_jobs(SETTINGS.jobs_csv_path)
        check("jobs shortlist", f"{len(jobs)} roles -> {SETTINGS.jobs_csv_path}", True)
    except Exception as exc:
        check("jobs shortlist", f"cannot read: {exc}", False)
    try:
        tr = tracker()
        check("tracker", f"{len(tr.list())} applications -> {tr.path}", True)
    except Exception as exc:
        check("tracker", f"error: {exc}", False)
    try:
        probe = SETTINGS.data_dir / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        check("data dir writes", str(SETTINGS.data_dir), True)
    except Exception as exc:
        check("data dir writes", f"NOT writable: {exc}", False)
    check("llm", "enabled (OPENAI_API_KEY set)" if SETTINGS.llm_enabled
          else "off - deterministic mode, works fine", True)
    return 0 if good else 1


def _build(company: str, title: str, keywords: str, url: str = "") -> int:
    profile = load_profile(str(SETTINGS.profile_path))
    job = JobPosting(id=hashlib.sha256(f"{company}|{title}".encode()).hexdigest()[:12],
                     company=company, title=title, url=url,
                     keywords=[k.strip() for k in keywords.split(",") if k.strip()])
    bundle, ev = generate(profile, job, Path(SETTINGS.data_dir) / "applications")
    print(_ascii(summarize(job, profile, ev)))
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
    print(f"staged {company} | {title} -> opened page, cover on clipboard, status=ready")
    print(json.dumps(sheet, indent=2))
    return job.id


def _track(cmd: str, job_id: str, status: str | None) -> int:
    tr = tracker()
    if cmd == "list":
        rows = tr.list()
        if not rows:
            print("no applications tracked yet - build one first")
            return 0
        for r in rows:
            print(f"{r.get('status','?'):12} {r['job_id']}  {r['company']} - {r['title']}")
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

    s = sub.add_parser("serve", help="run the jobhunt workspace locally")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8020)
    s.add_argument("--no-open", action="store_true", help="do not auto-open the browser")

    d_ = sub.add_parser("doctor", help="diagnose your environment")

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
    if args.cmd is None:
        p.print_help()
        print("\nstart the workspace:   python -m jobhunt serve")
        print("diagnose first:         python -m jobhunt doctor")
        return 1
    if args.cmd == "demo":
        return _demo(args.csv, args.out, args.limit)
    if args.cmd == "serve":
        return _serve(args.host, args.port, no_open=args.no_open)
    if args.cmd == "doctor":
        return _doctor()
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