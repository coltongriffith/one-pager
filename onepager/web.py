"""Browser UI: a one-page landing + builder that turns company info into a PDF.

Routes:
  GET  /               landing page with the guided builder form
  GET  /example/{name} example profiles for one-click loading
  POST /parse-captable extract share_structure fields from xlsx/csv/pdf/pasted text
  POST /generate       render a profile (+ optional artwork uploads) to PDF
"""

from __future__ import annotations

import json
import os
import tempfile
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

from .captable import parse_captable, parse_text
from .profile import ProfileError, load_profile
from .render import TEMPLATES, render_html, render_pdf


@lru_cache(maxsize=1)
def weasyprint_available() -> bool:
    """True when the local WeasyPrint engine can run.

    On serverless hosts without Pango (e.g. Vercel) this is False and
    /generate returns self-contained HTML for a browser-based PDF printer
    (see api/pdf.js) instead of PDF bytes.
    """
    if os.environ.get("ONEPAGER_DISABLE_WEASYPRINT"):
        return False
    try:
        import weasyprint  # noqa: F401
    except Exception:
        return False
    return True

ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = ROOT / "examples"

app = FastAPI(title="onepager", docs_url=None, redoc_url=None)

ALLOWED_IMAGE_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif"}
ALLOWED_CAPTABLE_SUFFIXES = {".xlsx", ".xlsm", ".csv", ".tsv", ".pdf", ".txt"}
MAX_UPLOAD_BYTES = 8 * 1024 * 1024

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>onepager — investor one-pager generator</title>
<style>
  :root {
    --primary: #16365C; --primary-deep: #0D2240; --accent: #E8A33D;
    --ink: #1B2430; --muted: #5A6572; --line: #DEE3EA; --mist: #F2F5F9;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; color: var(--ink); background: var(--mist); }
  .hero { background: linear-gradient(120deg, var(--primary-deep), var(--primary)); color: #fff; padding: 40px 32px 34px; text-align: center; }
  .hero h1 { font-size: 32px; letter-spacing: -0.6px; }
  .hero h1 span { color: var(--accent); }
  .hero p { max-width: 620px; margin: 10px auto 0; font-size: 15.5px; line-height: 1.55; opacity: 0.9; }
  .hero p.checklist { font-size: 12.5px; opacity: 0.7; margin-top: 12px; }
  .wrap { display: flex; gap: 24px; padding: 24px 32px 48px; max-width: 1480px; margin: 0 auto; align-items: flex-start; }
  .pane { background: #fff; border: 1px solid var(--line); border-radius: 12px; padding: 22px; }
  .left { flex: 1.15; min-width: 0; }
  .right { flex: 1; min-width: 0; position: sticky; top: 16px; display: flex; flex-direction: column; }
  h2 { font-size: 15px; margin: 22px 0 10px; padding-top: 18px; border-top: 1px solid var(--line); }
  h2:first-of-type { margin-top: 0; padding-top: 0; border-top: none; }
  h2 small { color: var(--muted); font-weight: 500; }
  label.small { display: block; font-size: 12px; font-weight: 600; color: var(--muted); margin: 10px 0 4px; }
  input[type=text], textarea, select {
    width: 100%; border: 1px solid var(--line); border-radius: 7px; padding: 8px 10px;
    font-size: 13.5px; font-family: inherit; background: #fff;
  }
  textarea { resize: vertical; line-height: 1.5; }
  textarea.mono { font-family: ui-monospace, 'SF Mono', Menlo, monospace; font-size: 12px; }
  input:focus, textarea:focus { outline: 2px solid var(--primary); border-color: transparent; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; }
  .grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 0 14px; }
  .tabs { display: flex; gap: 8px; margin-bottom: 18px; }
  .tabs button {
    border: 1.5px solid var(--line); background: #fff; border-radius: 8px;
    padding: 8px 16px; font-size: 13px; font-weight: 600; cursor: pointer; color: var(--muted);
  }
  .tabs button.active { border-color: var(--primary); color: var(--primary); background: #EAF0F8; }
  .tpl { display: flex; gap: 10px; flex-wrap: wrap; }
  .tpl label { border: 1.5px solid var(--line); border-radius: 8px; padding: 8px 14px; font-size: 13px; cursor: pointer; }
  .tpl label:has(input:checked) { border-color: var(--primary); background: #EAF0F8; font-weight: 600; }
  .tpl input { margin-right: 6px; }
  .examples { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 14px; }
  .examples button, .minor {
    background: #fff; border: 1px solid var(--line); border-radius: 6px;
    padding: 6px 12px; font-size: 12px; cursor: pointer;
  }
  .examples button:hover, .minor:hover { border-color: var(--primary); }
  .cap-box { border: 1.5px dashed var(--line); border-radius: 10px; padding: 14px; background: var(--mist); }
  .cap-box .row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  .parse-note { font-size: 12px; margin-top: 8px; display: none; }
  .parse-note.ok { color: #146C2E; }
  .parse-note.warn { color: #8A5B12; }
  .generate {
    margin-top: 20px; width: 100%; background: var(--primary); color: #fff; border: none;
    border-radius: 9px; padding: 14px; font-size: 15px; font-weight: 600; cursor: pointer;
  }
  .generate:hover { background: var(--primary-deep); }
  .generate:disabled { opacity: 0.6; cursor: wait; }
  #error { color: #B3261E; font-size: 13px; margin-top: 10px; white-space: pre-wrap; display: none; }
  #preview { flex: 1; min-height: 690px; border: 1px solid var(--line); border-radius: 8px; width: 100%; background: #fff; }
  .hint { font-size: 11.5px; color: var(--muted); margin-top: 5px; line-height: 1.5; }
  .dl { margin-top: 10px; font-size: 13px; display: none; }
  .dl a { color: var(--primary); font-weight: 600; }
  input[type=file] { font-size: 12px; max-width: 100%; }
  details { margin-top: 14px; }
  details summary { cursor: pointer; font-size: 13px; font-weight: 600; color: var(--primary); }
  details summary small { color: var(--muted); font-weight: 500; }
  @media (max-width: 1020px) { .wrap { flex-direction: column; } .right { position: static; width: 100%; } }
</style>
</head>
<body>

<div class="hero">
  <h1>one<span>pager</span></h1>
  <p>Answer a few questions about a listed company, drop in the logo and the
  latest cap table (Excel, PDF, CSV, or copied text) — and download an
  investor-ready one-pager PDF.</p>
  <p class="checklist">Have handy: the company's website &middot; a recent press release or
  corporate presentation &middot; the logo file &middot; the latest cap table. That's it.</p>
</div>

<div class="wrap">
  <div class="pane left">
    <div class="tabs">
      <button id="tab-builder" class="active" onclick="setTab('builder')">Builder</button>
      <button id="tab-json" onclick="setTab('json')">JSON (advanced)</button>
    </div>

    <div id="panel-builder">
      <div class="examples">
        <span style="font-size:12px;color:var(--muted)">Load an example:</span>
        <button type="button" onclick="loadExample('aurora-lithium')">Mining company</button>
        <button type="button" onclick="loadExample('northbeam-health')">Tech company</button>
        <button type="button" onclick="clearForm()">Clear</button>
      </div>

      <h2>1 · Who is the company? <small>— copy from the header of any press release</small></h2>
      <div class="grid2">
        <div><label class="small">Company name *</label><input type="text" id="c_name" placeholder="Aurora Lithium Corp."></div>
        <div><label class="small">Tickers <small>— “TSXV: AUL, OTCQB: AULCF”</small></label><input type="text" id="c_tickers" placeholder="TSXV: AUL, OTCQB: AULCF"></div>
      </div>
      <label class="small">What does the company do? <small>— 2–4 sentences from their website’s About
      section or latest news release. Written to continue the name: “is a TSX Venture listed …”</small></label>
      <textarea id="c_desc" rows="4" placeholder="is a TSX Venture listed exploration company focused on …"></textarea>
      <div class="grid2">
        <div><label class="small">One-line pitch / tagline <small>— the headline of the page</small></label><input type="text" id="c_tagline" placeholder="Powering the Battery Supply Chain of Tomorrow"></div>
        <div><label class="small">Sector / industry</label><input type="text" id="c_sector" placeholder="Lithium Exploration & Development"></div>
      </div>
      <label class="small" style="margin-top:14px">How do investors reach them? <small>— from the “Contact”
      block at the bottom of any press release</small></label>
      <div class="grid2">
        <div><label class="small">Website</label><input type="text" id="c_website" placeholder="www.example.com"></div>
        <div><label class="small">Investor email</label><input type="text" id="c_email" placeholder="ir@example.com"></div>
      </div>
      <div class="grid2">
        <div><label class="small">Phone</label><input type="text" id="c_phone" placeholder="+1 (604) 555-0148"></div>
        <div><label class="small">Head office</label><input type="text" id="c_address" placeholder="Vancouver, BC, Canada"></div>
      </div>

      <h2>2 · What does the brand look like?</h2>
      <div class="grid2">
        <div><label class="small">Logo (SVG / PNG / JPG)</label><input type="file" id="logo" accept=".svg,.png,.jpg,.jpeg,.webp"></div>
        <div><label class="small">Hero image <small>— optional banner photo (used by the horizon template)</small></label><input type="file" id="hero" accept=".svg,.png,.jpg,.jpeg,.webp"></div>
      </div>
      <div class="grid2">
        <div><label class="small">Brand color <small>— leave blank to auto-extract from a PNG/JPG logo</small></label><input type="text" id="b_primary" placeholder="#0E7C66"></div>
        <div><label class="small">Accent color <small>— optional second color</small></label><input type="text" id="b_accent" placeholder="#E8A33D"></div>
      </div>

      <h2>3 · What’s the share structure? <small>— drop in the latest cap table, we’ll read it</small></h2>
      <div class="cap-box">
        <div class="row">
          <input type="file" id="cap_file" accept=".xlsx,.xlsm,.csv,.tsv,.pdf,.txt">
          <span style="font-size:12px;color:var(--muted)">or paste below, then</span>
          <button type="button" class="minor" onclick="parseCaptable()">Parse cap table</button>
        </div>
        <textarea id="cap_text" rows="4" class="mono" style="margin-top:10px"
          placeholder="Shares Outstanding&#9;92,450,000&#10;Options&#9;6,150,000&#10;Warrants&#9;14,200,000&#10;Share Price&#9;$0.62"></textarea>
        <div class="parse-note" id="parse_note"></div>
      </div>
      <p class="hint">Parsed values land in the fields below — review and edit before generating.
      Fully diluted and market cap are computed automatically when left blank.</p>
      <div class="grid3">
        <div><label class="small">Share price</label><input type="text" id="s_share_price"></div>
        <div><label class="small">Shares outstanding</label><input type="text" id="s_shares_outstanding"></div>
        <div><label class="small">Options</label><input type="text" id="s_options"></div>
        <div><label class="small">Warrants</label><input type="text" id="s_warrants"></div>
        <div><label class="small">Fully diluted</label><input type="text" id="s_fully_diluted"></div>
        <div><label class="small">Market cap</label><input type="text" id="s_market_cap"></div>
        <div><label class="small">52-week range</label><input type="text" id="s_week52_range"></div>
        <div><label class="small">Cash position</label><input type="text" id="s_cash_position"></div>
        <div><label class="small">Insider ownership</label><input type="text" id="s_insider_ownership"></div>
      </div>
      <div class="grid3"><div><label class="small">Figures as of</label><input type="text" id="s_as_of" placeholder="May 2026"></div></div>

      <h2>4 · Why should investors care?</h2>
      <label class="small">3–6 investment highlights <small>— the bullet points from the investor
      presentation's "Why invest" slide. One per line: “icon | Short title | One sentence why it matters”
      (icons: __ICONS__)</small></label>
      <textarea id="f_highlights" rows="4" class="mono" placeholder="battery | Critical Commodity | Lithium demand is forecast to triple by 2035.&#10;users | Proven Team | Leadership with multiple discoveries and exits."></textarea>

      <details>
        <summary>Add projects, leadership &amp; recent news <small>— recommended, one entry per line</small></summary>
        <label class="small">Key projects, assets, or products <small>— “Name | Location | One-line summary”,
        add facts as “-” bullet lines underneath</small></label>
        <textarea id="f_projects" rows="4" class="mono" placeholder="Salar Grande Project | Salta, Argentina | Flagship brine project covering 31,000 ha.&#10;- Historic sampling up to 540 mg/L lithium&#10;- Phase 1 drilling intersected brine over 180 m"></textarea>
        <div class="grid2">
          <div>
            <label class="small">Who runs it? <small>— “Name | Title”</small></label>
            <textarea id="f_team" rows="3" class="mono" placeholder="Elena Vásquez | President &amp; CEO"></textarea>
          </div>
          <div>
            <label class="small">Latest headlines <small>— “YYYY-MM-DD | Headline”</small></label>
            <textarea id="f_news" rows="3" class="mono" placeholder="2026-05-12 | Phase 1 drilling confirms thick brine horizons"></textarea>
          </div>
        </div>
      </details>
    </div>

    <div id="panel-json" style="display:none">
      <p class="hint" style="margin-bottom:8px">Full control: edit the raw profile JSON.
      <button type="button" class="minor" onclick="formToJson()">Copy current form into JSON</button></p>
      <textarea id="profile_json" rows="28" class="mono" spellcheck="false"></textarea>
    </div>

    <h2>5 · Template</h2>
    <div class="tpl" id="templates"></div>

    <button class="generate" id="go" onclick="generate()">Generate PDF</button>
    <div id="error"></div>
    <div class="dl" id="dl"><a id="dl-link" download="onepager.pdf" href="#">&#8595; Download PDF</a></div>
  </div>

  <div class="pane right">
    <h2 style="margin:0;padding:0;border:none">Preview</h2>
    <iframe id="preview" title="PDF preview" style="margin-top:10px"></iframe>
  </div>
</div>

<script>
const TEMPLATES = __TEMPLATES__;
const SHARE_KEYS = ['share_price','shares_outstanding','options','warrants','fully_diluted',
                    'market_cap','week52_range','cash_position','insider_ownership'];
let activeTab = 'builder';

const tplBox = document.getElementById('templates');
TEMPLATES.forEach(([name, desc], i) => {
  const label = document.createElement('label');
  label.title = desc;
  label.innerHTML = `<input type="radio" name="tpl" value="${name}" ${i === 0 ? 'checked' : ''}>${name}`;
  tplBox.appendChild(label);
});

function setTab(tab) {
  activeTab = tab;
  document.getElementById('panel-builder').style.display = tab === 'builder' ? '' : 'none';
  document.getElementById('panel-json').style.display = tab === 'json' ? '' : 'none';
  document.getElementById('tab-builder').classList.toggle('active', tab === 'builder');
  document.getElementById('tab-json').classList.toggle('active', tab === 'json');
}

const val = id => document.getElementById(id).value.trim();
const setVal = (id, v) => { document.getElementById(id).value = v == null ? '' : String(v); };
const lines = id => val(id).split('\\n').map(l => l.trim()).filter(Boolean);

function parseNumeric(text) {
  if (!text) return null;
  const cleaned = text.replace(/[$,\\s]/g, '');
  return /^-?\\d+(\\.\\d+)?$/.test(cleaned) ? parseFloat(cleaned) : text;
}

function buildProfile() {
  const profile = { company: {
    name: val('c_name'), tagline: val('c_tagline'), description: val('c_desc'),
    sector: val('c_sector'), website: val('c_website'), email: val('c_email'),
    phone: val('c_phone'), address: val('c_address'),
  }};
  const listings = val('c_tickers').split(/[,;\\n]/).map(t => t.trim()).filter(Boolean).map(t => {
    const m = t.match(/^([^:\\s]+)\\s*[:\\s]\\s*(.+)$/);
    return m ? { exchange: m[1], ticker: m[2].trim() } : { exchange: '', ticker: t };
  });
  if (listings.length) profile.listings = listings;

  const share = {};
  SHARE_KEYS.forEach(k => {
    const v = val('s_' + k);
    if (v) share[k] = ['week52_range','insider_ownership'].includes(k) ? v : parseNumeric(v);
  });
  if (val('s_as_of')) share.as_of = val('s_as_of');
  if (Object.keys(share).length) profile.share_structure = share;

  const highlights = lines('f_highlights').map(l => {
    const parts = l.split('|').map(s => s.trim());
    if (parts.length >= 3) return { icon: parts[0], title: parts[1], text: parts.slice(2).join(' | ') };
    if (parts.length === 2) return { title: parts[0], text: parts[1] };
    return { title: parts[0], text: '' };
  });
  if (highlights.length) profile.highlights = highlights;

  const projects = [];
  lines('f_projects').forEach(l => {
    if (l.startsWith('-')) {
      if (projects.length) (projects[projects.length-1].bullets ||= []).push(l.replace(/^-+\\s*/, ''));
      return;
    }
    const parts = l.split('|').map(s => s.trim());
    projects.push({ name: parts[0], location: parts[1] || '', summary: parts.slice(2).join(' | ') });
  });
  if (projects.length) profile.projects = projects;

  const team = lines('f_team').map(l => {
    const parts = l.split('|').map(s => s.trim());
    return { name: parts[0], title: parts[1] || '' };
  });
  if (team.length) profile.team = team;

  const news = lines('f_news').map(l => {
    const parts = l.split('|').map(s => s.trim());
    return { date: parts[0], title: parts.slice(1).join(' | ') };
  });
  if (news.length) profile.news = news;

  if (val('b_primary') || val('b_accent')) {
    profile.brand = {};
    if (val('b_primary')) profile.brand.primary = val('b_primary');
    if (val('b_accent')) profile.brand.accent = val('b_accent');
  }
  return profile;
}

function formToJson() {
  setVal('profile_json', JSON.stringify(buildProfile(), null, 2));
  setTab('json');
}

function fillForm(data) {
  clearForm();
  const c = data.company || {};
  setVal('c_name', c.name); setVal('c_tagline', c.tagline); setVal('c_desc', c.description);
  setVal('c_sector', c.sector); setVal('c_website', c.website); setVal('c_email', c.email);
  setVal('c_phone', c.phone); setVal('c_address', c.address);
  setVal('c_tickers', (data.listings || []).map(l => `${l.exchange}: ${l.ticker}`).join(', '));
  const share = data.share_structure || {};
  SHARE_KEYS.forEach(k => setVal('s_' + k, share[k]));
  setVal('s_as_of', share.as_of);
  setVal('f_highlights', (data.highlights || []).map(h => [h.icon || 'star', h.title, h.text].join(' | ')).join('\\n'));
  setVal('f_projects', (data.projects || []).flatMap(p =>
    [[p.name, p.location || '', p.summary || ''].join(' | '), ...(p.bullets || []).map(b => '- ' + b)]).join('\\n'));
  setVal('f_team', (data.team || []).map(m => `${m.name} | ${m.title}`).join('\\n'));
  setVal('f_news', (data.news || []).map(n => `${n.date} | ${n.title}`).join('\\n'));
  setVal('b_primary', (data.brand || {}).primary); setVal('b_accent', (data.brand || {}).accent);
  if (data.projects || data.team || data.news) document.querySelector('details').open = true;
}

function clearForm() {
  document.querySelectorAll('#panel-builder input[type=text], #panel-builder textarea')
    .forEach(el => el.value = '');
  const note = document.getElementById('parse_note');
  note.style.display = 'none';
}

async function loadExample(name) {
  const res = await fetch(`/example/${name}`);
  fillForm(await res.json());
  setTab('builder');
}

async function parseCaptable() {
  const note = document.getElementById('parse_note');
  note.style.display = 'none';
  const form = new FormData();
  const file = document.getElementById('cap_file').files[0];
  if (file) form.append('file', file);
  const text = val('cap_text');
  if (text) form.append('text', text);
  if (!file && !text) {
    note.textContent = 'Choose a file or paste the cap table first.';
    note.className = 'parse-note warn'; note.style.display = 'block';
    return;
  }
  const res = await fetch('/parse-captable', { method: 'POST', body: form });
  const data = await res.json();
  if (!res.ok) {
    note.textContent = data.error || 'Could not parse the cap table.';
    note.className = 'parse-note warn'; note.style.display = 'block';
    return;
  }
  let filled = 0;
  SHARE_KEYS.concat(['as_of']).forEach(k => {
    if (data[k] != null) { setVal('s_' + k, data[k]); filled++; }
  });
  const skipped = (data._unmatched || []).map(u => u.label);
  note.className = 'parse-note ' + (filled ? 'ok' : 'warn');
  note.textContent = filled
    ? `Filled ${filled} field${filled === 1 ? '' : 's'} below — review before generating.`
      + (skipped.length ? ` Not recognized: ${skipped.join(', ')}.` : '')
    : 'No recognizable cap table rows found — fill the fields below manually.';
  note.style.display = 'block';
}

document.getElementById('cap_file').addEventListener('change', () => parseCaptable());

async function generate() {
  const btn = document.getElementById('go');
  const err = document.getElementById('error');
  err.style.display = 'none';
  let profileText;
  if (activeTab === 'json') {
    profileText = val('profile_json');
  } else {
    const profile = buildProfile();
    if (!profile.company.name) {
      err.textContent = 'Company name is required.';
      err.style.display = 'block';
      return;
    }
    profileText = JSON.stringify(profile);
  }
  btn.disabled = true;
  btn.textContent = 'Generating…';
  try {
    const form = new FormData();
    form.append('profile', profileText);
    form.append('template', document.querySelector('input[name=tpl]:checked').value);
    const logo = document.getElementById('logo').files[0];
    const hero = document.getElementById('hero').files[0];
    if (logo) form.append('logo', logo);
    if (hero) form.append('hero', hero);
    const res = await fetch('/generate', { method: 'POST', body: form });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.error || `Server error (${res.status})`);
    }
    let blob;
    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/pdf')) {
      blob = await res.blob();
    } else {
      // serverless host: print the returned HTML with the Chromium function
      const { html } = await res.json();
      btn.textContent = 'Printing…';
      const printRes = await fetch('/api/pdf', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ html }),
      });
      if (!printRes.ok) {
        const detail = await printRes.json().catch(() => ({}));
        throw new Error(detail.error || `PDF printing failed (${printRes.status})`);
      }
      blob = await printRes.blob();
    }
    const url = URL.createObjectURL(blob);
    document.getElementById('preview').src = url;
    document.getElementById('dl-link').href = url;
    document.getElementById('dl').style.display = 'block';
  } catch (e) {
    err.textContent = e.message;
    err.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generate PDF';
  }
}
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    from .icons import available_icons

    templates = json.dumps([[name, TEMPLATES[name]] for name in sorted(TEMPLATES)])
    return PAGE.replace("__TEMPLATES__", templates).replace(
        "__ICONS__", ", ".join(available_icons())
    )


@app.get("/example/{name}")
def example(name: str) -> JSONResponse:
    if name == "starter":
        from .cli import STARTER_PROFILE

        return JSONResponse(STARTER_PROFILE)
    path = EXAMPLES_DIR / f"{name}.json"
    if not path.is_file() or path.parent != EXAMPLES_DIR:
        return JSONResponse({"error": "Unknown example"}, status_code=404)
    data = json.loads(path.read_text())
    # strip asset paths that only exist relative to the examples directory
    for key in ("logo", "hero_image"):
        data.get("company", {}).pop(key, None)
    for project in data.get("projects", []):
        project.pop("image", None)
    return JSONResponse(data)


def _read_upload(upload: UploadFile) -> bytes | None:
    data = upload.file.read(MAX_UPLOAD_BYTES + 1)
    return None if len(data) > MAX_UPLOAD_BYTES else data


@app.post("/parse-captable")
def parse_captable_endpoint(
    file: UploadFile | None = File(None),
    text: str = Form(""),
) -> JSONResponse:
    if file is not None and file.filename:
        suffix = Path(file.filename).suffix.lower()
        if suffix not in ALLOWED_CAPTABLE_SUFFIXES:
            return JSONResponse(
                {"error": f"Unsupported cap table format '{suffix}'. "
                          "Use xlsx, csv, pdf, or plain text."},
                status_code=400,
            )
        data = _read_upload(file)
        if data is None:
            return JSONResponse({"error": "File too large (8 MB max)."}, status_code=400)
        try:
            return JSONResponse(parse_captable(data, file.filename))
        except Exception:
            return JSONResponse(
                {"error": "Could not read that file — try pasting the rows as text."},
                status_code=400,
            )
    if text.strip():
        return JSONResponse(parse_text(text))
    return JSONResponse({"error": "Provide a file or pasted text."}, status_code=400)


def _save_upload(upload: UploadFile, directory: Path, stem: str) -> str | None:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_SUFFIXES:
        return None
    data = _read_upload(upload)
    if data is None:
        return None
    dest = directory / f"{stem}{suffix}"
    dest.write_bytes(data)
    return dest.name


@app.post("/generate")
def generate(
    profile: str = Form(...),
    template: str = Form("boardroom"),
    logo: UploadFile | None = File(None),
    hero: UploadFile | None = File(None),
) -> Response:
    if template not in TEMPLATES:
        return JSONResponse({"error": f"Unknown template '{template}'"}, status_code=400)
    try:
        data = json.loads(profile)
    except json.JSONDecodeError as exc:
        return JSONResponse({"error": f"Profile is not valid JSON: {exc}"}, status_code=400)
    if not isinstance(data, dict):
        return JSONResponse({"error": "Profile JSON must be an object"}, status_code=400)

    with tempfile.TemporaryDirectory(prefix="onepager-") as tmp:
        tmp_path = Path(tmp)
        company = data.setdefault("company", {})
        if logo is not None and logo.filename:
            saved = _save_upload(logo, tmp_path, "logo")
            if saved is None:
                return JSONResponse(
                    {"error": "Unsupported or oversized logo file"}, status_code=400
                )
            company["logo"] = saved
        if hero is not None and hero.filename:
            saved = _save_upload(hero, tmp_path, "hero")
            if saved is None:
                return JSONResponse(
                    {"error": "Unsupported or oversized hero image"}, status_code=400
                )
            company["hero_image"] = saved

        profile_path = tmp_path / "profile.json"
        profile_path.write_text(json.dumps(data))
        use_weasyprint = weasyprint_available()
        try:
            context = load_profile(profile_path, inline_assets=not use_weasyprint)
            if use_weasyprint:
                pdf_path = render_pdf(context, template, tmp_path / "out.pdf")
            else:
                html = render_html(context, template, inline_fonts=True)
        except (ProfileError, ValueError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        company_name = (company.get("name") or "onepager").strip().replace(" ", "-")
        filename = f"{company_name}-{template}.pdf"
        if not use_weasyprint:
            # client forwards this HTML to the /api/pdf Chromium printer
            return JSONResponse({"html": html, "filename": filename})
        return Response(
            content=pdf_path.read_bytes(),
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
