import hashlib
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .agents import generate, summarize
from .apply import mailto as build_mailto, one_click, tracker
from .config import SETTINGS
from .domain import ApplicationBundle, JobPosting
from .profile import load_profile
from .public import SelfBuildRequest, build as self_build

app = FastAPI(title="JobHunt OS", version="0.2.0")
STATE: list[dict] = []

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "").strip()

_BUNDLES_DIR = Path(SETTINGS.data_dir) / "public"
_BUNDLES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/bundles", StaticFiles(directory=str(_BUNDLES_DIR)), name="bundles")


def require_admin(authorization: str | None = Header(default=None),
                  token: str | None = Query(default=None)):
    if not ADMIN_TOKEN:
        return
    supplied = token
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:]
    if supplied != ADMIN_TOKEN:
        raise HTTPException(401, "admin token required")


class BuildRequest(BaseModel):
    company: str
    title: str
    location: str = ""
    url: str = ""
    score: float = 0.0
    keywords: list[str] = []


class StatusRequest(BaseModel):
    status: str


def _active_profile():
    return load_profile(str(SETTINGS.profile_path))


# ------------------------------------------------------------- public

@app.get("/health")
def health():
    return {"status": "ok", "llm": SETTINGS.llm_enabled, "public": True}


@app.get("/", response_class=HTMLResponse)
def landing():
    return LANDING_HTML


@app.post("/api/self")
def api_self(req: SelfBuildRequest):
    return self_build(req)


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
        "resume_pdf": bundle.resume_pdf,
        "cover_letter": bundle.cover_letter,
        "linkedin_dm": bundle.linkedin_dm,
        "mailto": build_mailto(profile, job, bundle.cover_letter),
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
        out.append({**rec, "status": tr.get("status", "preparing")})
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
    bundle = ApplicationBundle(resume_pdf=rec["resume_pdf"], resume_html="",
                               cover_letter=rec["cover_letter"], linkedin_dm=rec["linkedin_dm"])
    sheet = one_click(profile, job, bundle, copy=True, open_page=True)
    tracker().set_status(job_id, "ready")
    return sheet


@app.get("/api/resume/{job_id}", dependencies=[Depends(require_admin)])
def api_resume(job_id: str):
    for rec in STATE:
        if rec["id"] == job_id:
            return FileResponse(rec["resume_pdf"])
    raise HTTPException(404, "bundle not built")


@app.get("/apply", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def dashboard():
    return DASHBOARD_HTML


LANDING_HTML = """<!doctype html><meta charset="utf-8"><title>JobHunt OS — build your application</title>
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

DASHBOARD_HTML = """<!doctype html><meta charset="utf-8"><title>JobHunt apply</title>
<style>
 body{background:#0a0e0c;color:#e8eee9;font:15px/1.5 ui-sans-serif,system-ui;max-width:820px;margin:40px auto;padding:0 20px}
 a{color:#41ff9e} button{cursor:pointer}
 .card{border:1px solid #232b27;border-top:1px solid #41ff9e;padding:18px;margin:14px 0}
 .status{font-family:ui-monospace,monospace;font-size:13px;border:1px solid #232b27;padding:3px 8px;margin-left:8px}
 .actions{margin-top:12px;display:flex;gap:8px;flex-wrap:wrap}
 button{padding:7px 13px;border:1px solid #41ff9e;background:transparent;color:#41ff9e;font:inherit}
 button:hover{background:#41ff9e;color:#0a0e0c}
</style>
<h1>jobhunt · one click apply</h1>
<p>Open the posting, copy the staged cover letter &amp; DM (one click each), paste
in the portal, submit. The final submit stays human — by design.</p>
<div id="list">loading…</div>
<script>
const tok = new URLSearchParams(location.search).get('token') || '';
const q = tok ? '?token='+tok : '';
let rows=[];
async function init(){rows=await (await fetch('/api/applications'+q)).json();
 document.getElementById('list').innerHTML=rows.map((r,i)=>{
   return `<div class="card"><b>${r.company} — ${r.title}</b><span class="status">${r.status}</span>
     <div class="actions">
       <button onclick="window.open('${r.url}','_blank')">page ↗</button>
       <button onclick="copy(${i},'cover_letter',this)">copy cover</button>
       <button onclick="copy(${i},'linkedin_dm',this)">copy DM</button>
       <button onclick="window.open('${r.resume_pdf}','_blank')">résumé ↗</button>
     </div></div>`).join('');}
function copy(i,key,btn){navigator.clipboard.writeText(rows[i][key]).then(()=>{
  btn.textContent='copied ✓';setTimeout(()=>btn.textContent='copy '+(key==='cover_letter'?'cover':'DM'),900);});}
init();
</script>
"""