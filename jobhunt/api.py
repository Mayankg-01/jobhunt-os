import hashlib
import os
import re
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agents import generate, summarize
from .apply import mailto as build_mailto, one_click, tracker
from .config import SETTINGS
from .domain import ApplicationBundle, JobPosting
from .ingest import load_jobs
from .profile import load_profile
from .public import SelfBuildRequest, build as self_build
from .scoring import fit_score, title_keywords

app = FastAPI(title="JobHunt OS", version="0.3.0")
STATE: list[dict] = []

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()

_BUNDLES_DIR = Path(SETTINGS.data_dir) / "public"
_BUNDLES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/bundles", StaticFiles(directory=str(_BUNDLES_DIR)), name="bundles")

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

def require_admin(authorization: str | None = Header(default=None),
                  token: str | None = Query(default=None)):
    if not ADMIN_TOKEN:
        return
    supplied = token
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:]
    if supplied != ADMIN_TOKEN:
        raise HTTPException(401, "admin token required")


def _active_profile():
    return load_profile(str(SETTINGS.profile_path))


class BuildRequest(BaseModel):
    company: str
    title: str
    location: str = ""
    url: str = ""
    score: float = 0.0
    keywords: list[str] = []


class StatusRequest(BaseModel):
    status: str


class JobsRequest(BaseModel):
    csv: str = ""


class PullRequest(BaseModel):
    url: str


# ------------------------------------------------------------- public

@app.get("/health")
def health():
    return {"status": "ok", "llm": SETTINGS.llm_enabled, "public": True}


@app.get("/", response_class=HTMLResponse)
def workspace():
    return WORKSPACE_HTML


@app.get("/builder", response_class=HTMLResponse)
def public_builder():
    return PUBLIC_BUILDER_HTML


@app.post("/api/self")
def api_self(req: SelfBuildRequest):
    return self_build(req)


# ------------------------------------------------------------ jobs

def _job_row(job: JobPosting, profile) -> dict:
    if not job.keywords:
        job.keywords = title_keywords(job.title)
    tr = tracker().get(job.id) or {}
    return {
        "id": job.id,
        "company": job.company,
        "title": job.title,
        "location": job.location,
        "url": job.url,
        "fit": fit_score(profile, job),
        "status": tr.get("status", "new"),
        "keywords": list(job.keywords),
    }


@app.get("/api/jobs", dependencies=[Depends(require_admin)])
def api_jobs():
    profile = _active_profile()
    try:
        jobs = load_jobs(SETTINGS.jobs_csv_path)
    except Exception:
        jobs = []
    return {"jobs": [_job_row(j, profile) for j in jobs]}


@app.post("/api/jobs", dependencies=[Depends(require_admin)])
def api_jobs_import(req: JobsRequest):
    if not req.csv.strip():
        raise HTTPException(422, "csv is empty")
    path = SETTINGS.data_dir / "jobs.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(req.csv, encoding="utf-8")
    return api_jobs()


@app.post("/api/jobs/pull", dependencies=[Depends(require_admin)])
def api_jobs_pull(req: PullRequest):
    """Best-effort posting extraction from a careers URL: title from <title>,
    company from the host, keywords derived from the title."""
    try:
        resp = httpx.get(req.url, timeout=15, follow_redirects=True,
                         headers={"User-Agent": _UA})
        resp.raise_for_status()
    except Exception as exc:
        raise HTTPException(502, f"could not fetch posting: {exc}")
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", resp.text, re.I | re.S)
    if m:
        title = re.sub(r"\s{2,}", " ", m.group(1)).strip()[:120]
    host = re.sub(r"^www\.", "", req.url.split("//")[-1].split("/")[0]).split(":")[0]
    parts = host.split(".")
    company = parts[-2] if len(parts) >= 2 else parts[0]
    return {"title": title, "company": company.title(), "location": "",
            "url": req.url, "keywords": title_keywords(title)}


# ------------------------------------------------------------ owner

@app.post("/api/build", dependencies=[Depends(require_admin)])
def api_build(req: BuildRequest):
    key = hashlib.sha256(f"{req.company}|{req.title}".encode()).hexdigest()[:12]
    job = JobPosting(id=key, company=req.company, title=req.title,
                     location=req.location, url=req.url, score=req.score,
                     keywords=req.keywords)
    profile = _active_profile()
    out_dir = SETTINGS.data_dir / "applications"
    bundle, ev = generate(profile, job, out_dir)
    record = {
        "id": key, "company": job.company, "title": job.title,
        "url": job.url, "fit": ev.metrics["fit"], "qualified": ev.qualified,
        "summary": summarize(job, profile, ev),
        "resume_pdf_path": bundle.resume_pdf,
        "resume_url": f"/api/resume/{key}",
        "cover_letter": bundle.cover_letter,
        "linkedin_dm": bundle.linkedin_dm,
        "mailto": build_mailto(profile, job, bundle.cover_letter),
        "resume_html": bundle.resume_html,
    }
    STATE.append(record)
    tracker().upsert(key, job.company, job.title, job.url, resume_pdf=bundle.resume_pdf)
    return {"job_id": key, **record}


@app.get("/api/applications", dependencies=[Depends(require_admin)])
def api_list():
    trows = {r["job_id"]: r for r in tracker().list()}
    out = []
    for rec in STATE:
        tr = trows.get(rec["id"], {})
        out.append({**rec, "status": tr.get("status", "new")})
    return out


@app.post("/api/applications/{job_id}/status", dependencies=[Depends(require_admin)])
def api_status(job_id: str, req: StatusRequest):
    row = tracker().set_status(job_id, req.status)
    if row is None:
        raise HTTPException(404, "unknown job")
    return row


@app.post("/api/apply/{job_id}", dependencies=[Depends(require_admin)])
def api_apply(job_id: str):
    rec = next((r for r in STATE if r["id"] == job_id), None)
    if rec is None:
        raise HTTPException(404, "build the bundle first via /api/build")
    profile = _active_profile()
    job = JobPosting(id=rec["id"], company=rec["company"], title=rec["title"], url=rec["url"])
    bundle = ApplicationBundle(resume_pdf=rec.get("resume_pdf_path", ""), resume_html="",
                               cover_letter=rec["cover_letter"], linkedin_dm=rec["linkedin_dm"])
    sheet = one_click(profile, job, bundle, copy=True, open_page=True)
    tracker().set_status(job_id, "ready")
    return sheet


@app.get("/api/resume/{job_id}", dependencies=[Depends(require_admin)])
def api_resume(job_id: str):
    for rec in STATE:
        if rec["id"] == job_id:
            path = rec.get("resume_pdf_path")
            if path and Path(path).exists():
                return FileResponse(path)
            raise HTTPException(404, "resume file missing")
    raise HTTPException(404, "bundle not built")


@app.get("/apply", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def apply_alias():
    return WORKSPACE_HTML


WORKSPACE_HTML = """<!doctype html><meta charset="utf-8"><title>JobHunt OS — workspace</title>
<style>
 body{background:#0a0e0c;color:#e8eee9;font:15px/1.5 ui-sans-serif,system-ui;max-width:1000px;margin:32px auto;padding:0 20px}
 a{color:#41ff9e} h1{font-size:24px} section{border:1px solid #1e251f;padding:18px;margin:16px 0}
 code{background:#141a17;padding:2px 6px;border-radius:4px}
 input,textarea{background:#101512;border:1px solid #232b27;color:#e8eee9;font:14px ui-monospace,monospace;padding:7px;box-sizing:border-box}
 button{padding:8px 14px;border:1px solid #41ff9e;background:transparent;color:#41ff9e;font:inherit;cursor:pointer;margin-right:6px}
 button:hover{background:#41ff9e;color:#0a0e0c}
 table{width:100%;border-collapse:collapse;margin-top:8px} th,td{text-align:left;padding:7px 9px;border-bottom:1px solid #161d18;font-size:13.5px}
 th{color:#9fb3a5;text-transform:uppercase;font-size:11px;letter-spacing:.08em}
 .badge{display:inline-block;font-size:11px;border:1px solid #2b3a31;padding:1px 7px;border-radius:20px;margin-left:6px}
 .ok{color:#41ff9e} .warn{color:#ffd479}
 .status{font-family:ui-monospace,monospace;font-size:12px;border:1px solid #232b27;padding:2px 8px;background:#101512;color:#e8eee9}
 select{background:#101512;border:1px solid #232b27;color:#e8eee9;font:inherit;padding:4px}
 pre{white-space:pre-wrap;font:12.5px/1.6 ui-monospace,monospace;background:#101512;padding:10px;border:1px solid #232b27}
 .row{display:flex;gap:8px;align-items:center;margin:6px 0}
 .hidden{display:none}
</style>
<h1>jobhunt · workspace</h1>
<section>
 <h3>1 · extract jobs</h3>
 <div class="row"><input id="pull" placeholder="https://jobs.ashbyhq.com/cohere/...  (paste a posting URL)"
  style="flex:1"><button onclick="pullJob()">extract →</button></div>
 <div class="row hidden" id="picked"><span id="pickedLabel" style="flex:1"></span><button onclick="importPulled()">build ↗</button></div>
 <label>and/or paste a job-scout CSV (rank,score,company,title,location,url)</label>
 <div class="row"><textarea id="csv" rows="7" style="flex:1" placeholder="rank,score,company,title,location,url"></textarea>
  <button onclick="importJobs()">import</button></div>
</section>
<section>
 <h2>2 · shortlist <button onclick="loadJobs()">refresh</button></h2>
 <table><thead><tr><th>fit</th><th>role</th><th>company</th><th>location</th><th>state</th><th></th></tr></thead>
 <tbody id="rows"></tbody></table>
</section>
<section id="result" class="hidden">
 <h2>3 · bundle + one-click apply</h2>
 <div id="resbody"></div>
</section>
<script>
let jobs=[]; let CUR=null;
const tok = new URLSearchParams(location.search).get('token') || '';
const q = tok ? '?token='+tok : '';
const STATS=['new','ready','applied','interviewing','offer','closed','archived'];
async function loadJobs(){ jobs = (await (await fetch('/api/jobs'+q)).json()).jobs;
 document.getElementById('rows').innerHTML = jobs.map((j,i)=>{
  const fitc = j.fit>=0.6?'ok':'warn';
  return `<tr><td class="${fitc}">${(j.fit*100).toFixed(0)}%</td>
   <td>${j.title}</td><td>${j.company}</td><td>${j.location}</td>
   <td><span class="status">${j.status}</span></td>
   <td><button onclick="buildJob(${i})">build</button></td></tr>`}).join(''); }
async function buildJob(i){ const j=jobs[i]; const r=await (await fetch('/api/build'+q,{method:'POST',
  headers:{'Content-Type':'application/json'},
  body:JSON.stringify({company:j.company,title:j.title,location:j.location,url:j.url,keywords:jobs[i].keywords||[]})})).json();
  r.detail ? show(r.detail) : showResult(r); }
function show(msg){ const el=document.getElementById('result'); el.classList.remove('hidden'); el.scrollIntoView();
 document.getElementById('resbody').innerHTML='<p class="warn">'+msg+'</p>'; }
function showResult(r){
 const el=document.getElementById('result'); el.classList.remove('hidden'); el.scrollIntoView(); CUR=r;
 document.getElementById('resbody').innerHTML =
  '<h3>'+r.company+' · '+r.title+' <span class="'+(r.qualified?'ok':'warn')+' badge">'+(r.qualified?'qualified':'blocked')+'</span>'+
  ' <span class="badge">fit '+(r.fit*100).toFixed(0)+'%</span></h3>'+
  '<p>'+r.summary+'</p>'+
  '<div class="row">'+
  '<button onclick="applyNow()">open page + copy cover</button>'+
  '<button onclick="copyTxt(\'cover_letter\',this)">copy cover</button>'+
  '<button onclick="copyTxt(\'linkedin_dm\',this)">copy DM</button>'+
  '<a href="'+r.mailto+'" target="_blank"><button>email draft</button></a>'+
  '<a href="'+r.resume_url+'" target="_blank"><button>résumé PDF</button></a>'+
  '<select class="status" onchange="setStatus(this.value)">'+STATS.map(s=>'<option'+((r._st||'new')===s?' selected':'')+'>'+s+'</option>').join('')+'</select></div>'+
  '<h3>cover letter</h3><pre>'+r.cover_letter+'</pre>'+
  '<h3>linkedin dm</h3><pre>'+r.linkedin_dm+'</pre>';
}
async function applyNow(){ const r=await (await fetch('/api/apply/'+CUR.job_id+q,{method:'POST'})).json();
 if(r.detail){show(r.detail);} else { alert('page opened + cover staged on your clipboard — final submit stays yours'); } }
async function copyTxt(k,btn){ navigator.clipboard.writeText(CUR[k]).then(()=>{ btn.textContent='copied ✓';
  setTimeout(()=>btn.textContent='copy',900); }); }
async function setStatus(s){ await fetch('/api/applications/'+CUR.job_id+'/status'+q,{method:'POST',
  headers:{'Content-Type':'application/json'},body:JSON.stringify({status:s})}); }
async function pullJob(){ const url=document.getElementById('pull').value.trim(); if(!url) return;
 const r=await (await fetch('/api/jobs/pull'+q,{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({url})})).json();
 if(r.detail){ show(r.detail); return; }
 window._pulled=r;
 document.getElementById('picked').classList.remove('hidden');
 document.getElementById('pickedLabel').textContent=(r.title? r.title+' @ '+r.company : r.url)+'   ['+(r.keywords||[]).join(', ')+']';
}
async function importPulled(){ const r=window._pulled; if(!r || !r.title){ show('could not extract a title from that page'); return; }
 const out=await (await fetch('/api/build'+q,{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({company:r.company,title:r.title,url:r.url,keywords:r.keywords})})).json();
 out.detail?show(out.detail):showResult(out); }
async function importJobs(){ const c=document.getElementById('csv').value; if(!c.trim()){ alert('paste a csv first'); return; }
 const r=await (await fetch('/api/jobs'+q,{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({csv:c})})).json();
 if(r.detail){ show(r.detail); return; } jobs=r.jobs;
 document.getElementById('rows').innerHTML = jobs.map((j,i)=>{
  const fitc=j.fit>=0.6?'ok':'warn';
  return `<tr><td class="${fitc}">${(j.fit*100).toFixed(0)}%</td><td>${j.title}</td><td>${j.company}</td><td>${j.location}</td><td><span class="status">new</span></td><td><button onclick="buildJob(${i})">build</button></td></tr>`}).join(''); }
loadJobs();
</script>
"""

PUBLIC_BUILDER_HTML = """<!doctype html><meta charset="utf-8"><title>JobHunt OS — build your application</title>
<style>
 body{background:#0a0e0c;color:#e8eee9;font:15px/1.5 ui-sans-serif,system-ui;max-width:860px;margin:40px auto;padding:0 20px}
 a{color:#41ff9e} h1{font-size:24px} code{background:#141a17;padding:2px 6px;border-radius:4px}
 .grid{display:grid;grid-template-columns:1fr 1fr;gap:16px} @media(max-width:760px){.grid{grid-template-columns:1fr}}
 label{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#9fb3a5;margin:12px 0 4px}
 input,textarea{width:100%;background:#101512;border:1px solid #232b27;color:#e8eee9;font:14px ui-monospace,monospace;padding:8px;box-sizing:border-box}
 button{padding:10px 18px;border:1px solid #41ff9e;background:transparent;color:#41ff9e;font:inherit;margin-top:14px;cursor:pointer}
 button:hover{background:#41ff9e;color:#0a0e0c}
 .result{border:1px solid #232b27;border-top:1px solid #41ff9e;padding:18px;margin-top:22px;display:none}
 .result.show{display:block} pre{white-space:pre-wrap;font:13px/1.6 ui-monospace,monospace;background:#101512;padding:10px;border:1px solid #232b27}
 .badge{font-size:12px;border:1px solid #41ff9e;padding:2px 8px;border-radius:20px}
 .warn{color:#ffd479} .ok{color:#41ff9e}
</style>
<h1>jobhunt · self-serve bundle builder</h1>
<p>Paste the posting and your own profile — get a tailored cover letter, a
recruiter DM, and an ATS-friendly résumé PDF. Every word comes from
<em>your</em> data; nothing is invented. The final submit stays human.</p>
<div class="grid">
 <div>
  <label>job title</label><input id="jt" placeholder="Senior Machine Learning Engineer">
  <label>company</label><input id="jc" placeholder="Acme">
  <label>location (optional)</label><input id="jl" placeholder="Remote / Bangalore">
  <label>posting url (optional)</label><input id="ju" placeholder="https://careers.acme/...">
  <label>required keywords (comma-separated, optional — auto-derived otherwise)</label>
  <input id="jk" placeholder="pytorch, transformers, mlops">
  <button onclick="build()">build my application →</button>
 </div>
 <div>
  <label>your profile — edit the JSON to match your résumé</label>
  <textarea id="prof" rows="30">{
  "name": "Your Name",
  "headline": "Your one-line pitch",
  "location": "City, Country",
  "email": "you@example.com",
  "phone": "",
  "github": "",
  "linkedin": "",
  "summary": "One paragraph: who you are, what you ship, real numbers only.",
  "skills": ["python", "fastapi", "mlops"],
  "experience": [
    {"title": "Software Engineer", "company": "Company", "period": "2023 - present",
     "bullets": ["What you actually built, real impact, real numbers"]}
  ],
  "projects": [
    {"name": "Project", "desc": "What it does, real numbers only.", "tags": ["pytorch", "deploy"]}
  ],
  "education": [{"degree": "B.S. Computer Science", "school": "University", "period": "2019 - 2023"}],
  "achievements": ["Real, checkable wins"]
}</textarea>
 </div>
</div>
<div class="result" id="res"></div>
<script>
async function build(){
  let profile; try { profile = JSON.parse(document.getElementById('prof').value); }
  catch(e){ alert('profile JSON is invalid: ' + e.message); return; }
  const job = {
    title: document.getElementById('jt').value.trim(),
    company: document.getElementById('jc').value.trim(),
    location: document.getElementById('jl').value.trim(),
    url: document.getElementById('ju').value.trim(),
    keywords: document.getElementById('jk').value.split(',').map(s=>s.trim()).filter(Boolean),
  };
  if(!job.title){ alert('job title is required'); return; }
  document.getElementById('res').className='result show';
  document.getElementById('res').innerHTML='<p>building…</p>';
  try {
    const r = await (await fetch('/api/self', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({profile, job})})).json();
    if(r.detail){ document.getElementById('res').innerHTML='<p class="warn">'+r.detail+'</p>'; return; }
    document.getElementById('res').innerHTML =
      '<h2>'+r.company+' · '+r.title+'</h2>' +
      '<p>fit <b class="'+(r.qualified?'ok':'warn')+'">'+(r.fit*100).toFixed(0)+'%</b>' +
      ' · '+(r.qualified?'<span class="ok">clears the gate</span>':'<span class="warn">needs work before sending</span>')+'</p>' +
      '<p>'+r.summary+'</p>' +
      '<button onclick="copy(\'cover_letter\')">copy cover letter</button>' +
      '<button onclick="copy(\'linkedin_dm\')">copy LinkedIn DM</button>' +
      '<a href="'+r.resume_pdf+'" target="_blank"><button>download résumé PDF</button></a>' +
      '<a href="'+r.resume_html+'" target="_blank"><button>open résumé HTML</button></a>' +
      '<a href="'+r.mailto+'"><button>open email draft</button></a>' +
      '<h3>cover letter</h3><pre>'+r.cover_letter+'</pre>' +
      '<h3>linkedin dm</h3><pre>'+r.linkedin_dm+'</pre>';
    window._cover = r.cover_letter; window._dm = r.linkedin_dm;
  } catch(e){ document.getElementById('res').innerHTML='<p class="warn">error: '+e.message+'</p>'; }
}
function copy(key){ const t = key==='cover_letter' ? window._cover : window._dm;
  navigator.clipboard.writeText(t).then(()=>alert(key==='cover_letter'?'cover letter copied':'dm copied')); }
</script>
"""