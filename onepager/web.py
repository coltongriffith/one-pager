"""Browser UI: edit a company profile, upload artwork, and download the PDF."""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

from .profile import ProfileError, load_profile
from .render import TEMPLATES, render_pdf

ROOT = Path(__file__).parent.parent
EXAMPLES_DIR = ROOT / "examples"

app = FastAPI(title="onepager", docs_url=None, redoc_url=None)

ALLOWED_IMAGE_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".webp", ".gif"}

PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>onepager — investor one-pager generator</title>
<style>
  :root {
    --primary: #16365C; --accent: #E8A33D; --ink: #1B2430;
    --muted: #5A6572; --line: #DEE3EA; --mist: #F2F5F9;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: system-ui, -apple-system, 'Segoe UI', sans-serif; color: var(--ink); background: var(--mist); }
  header { background: linear-gradient(90deg, #0D2240, var(--primary)); color: #fff; padding: 22px 32px; }
  header h1 { font-size: 22px; letter-spacing: -0.3px; }
  header h1 span { color: var(--accent); }
  header p { opacity: 0.85; font-size: 14px; margin-top: 4px; }
  .wrap { display: flex; gap: 24px; padding: 24px 32px; max-width: 1400px; margin: 0 auto; }
  .pane { background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 20px; }
  .left { flex: 1.1; min-width: 0; }
  .right { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  h2 { font-size: 15px; margin-bottom: 12px; }
  label.small { display: block; font-size: 12px; font-weight: 600; color: var(--muted); margin: 12px 0 4px; }
  textarea {
    width: 100%; height: 420px; font-family: ui-monospace, 'SF Mono', Menlo, monospace;
    font-size: 12px; line-height: 1.5; border: 1px solid var(--line); border-radius: 8px;
    padding: 12px; resize: vertical;
  }
  textarea:focus { outline: 2px solid var(--primary); border-color: transparent; }
  .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
  .tpl { display: flex; gap: 10px; margin: 6px 0 4px; flex-wrap: wrap; }
  .tpl label {
    border: 1.5px solid var(--line); border-radius: 8px; padding: 8px 14px;
    font-size: 13px; cursor: pointer; background: #fff;
  }
  .tpl input { margin-right: 6px; }
  .tpl label:has(input:checked) { border-color: var(--primary); background: #EAF0F8; font-weight: 600; }
  input[type=file] { font-size: 12px; }
  .examples button {
    background: #fff; border: 1px solid var(--line); border-radius: 6px;
    padding: 6px 12px; font-size: 12px; cursor: pointer;
  }
  .examples button:hover { border-color: var(--primary); }
  .generate {
    margin-top: 16px; width: 100%;
    background: var(--primary); color: #fff; border: none; border-radius: 8px;
    padding: 13px; font-size: 15px; font-weight: 600; cursor: pointer;
  }
  .generate:hover { background: #0D2240; }
  .generate:disabled { opacity: 0.6; cursor: wait; }
  #error { color: #B3261E; font-size: 13px; margin-top: 10px; white-space: pre-wrap; display: none; }
  #preview { flex: 1; min-height: 640px; border: 1px solid var(--line); border-radius: 8px; width: 100%; background: #fff; }
  .hint { font-size: 12px; color: var(--muted); margin-top: 8px; }
  .dl { margin-top: 10px; font-size: 13px; display: none; }
  .dl a { color: var(--primary); font-weight: 600; }
  @media (max-width: 980px) { .wrap { flex-direction: column; } }
</style>
</head>
<body>
<header>
  <h1>one<span>pager</span></h1>
  <p>Paste public company information, pick a template, get an investor-ready PDF.</p>
</header>
<div class="wrap">
  <div class="pane left">
    <h2>1 &middot; Company profile</h2>
    <div class="row examples">
      <span style="font-size:12px;color:var(--muted)">Start from:</span>
      <button type="button" onclick="loadExample('starter')">Blank starter</button>
      <button type="button" onclick="loadExample('aurora-lithium')">Mining example</button>
      <button type="button" onclick="loadExample('northbeam-health')">Tech example</button>
    </div>
    <label class="small">Profile JSON</label>
    <textarea id="profile" spellcheck="false"></textarea>

    <h2 style="margin-top:18px">2 &middot; Artwork (optional)</h2>
    <div class="row">
      <div>
        <label class="small">Logo (SVG / PNG / JPG)</label>
        <input type="file" id="logo" accept=".svg,.png,.jpg,.jpeg,.webp">
      </div>
      <div>
        <label class="small">Hero image</label>
        <input type="file" id="hero" accept=".svg,.png,.jpg,.jpeg,.webp">
      </div>
    </div>
    <p class="hint">Uploaded files override the <code>logo</code> / <code>hero_image</code> paths in the JSON.
    Without a logo the company name is set in type; brand colors are auto-extracted from raster logos.</p>

    <h2 style="margin-top:18px">3 &middot; Template</h2>
    <div class="tpl" id="templates"></div>

    <button class="generate" id="go" onclick="generate()">Generate PDF</button>
    <div id="error"></div>
    <div class="dl" id="dl"><a id="dl-link" download="onepager.pdf" href="#">&#8595; Download PDF</a></div>
  </div>
  <div class="pane right">
    <h2>Preview</h2>
    <iframe id="preview" title="PDF preview"></iframe>
  </div>
</div>
<script>
const TEMPLATES = __TEMPLATES__;
const tplBox = document.getElementById('templates');
TEMPLATES.forEach(([name, desc], i) => {
  const label = document.createElement('label');
  label.title = desc;
  label.innerHTML = `<input type="radio" name="tpl" value="${name}" ${i === 0 ? 'checked' : ''}>${name}`;
  tplBox.appendChild(label);
});

async function loadExample(name) {
  const res = await fetch(`/example/${name}`);
  const data = await res.json();
  document.getElementById('profile').value = JSON.stringify(data, null, 2);
}

async function generate() {
  const btn = document.getElementById('go');
  const err = document.getElementById('error');
  err.style.display = 'none';
  btn.disabled = true;
  btn.textContent = 'Generating…';
  try {
    const form = new FormData();
    form.append('profile', document.getElementById('profile').value);
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
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    document.getElementById('preview').src = url;
    const dl = document.getElementById('dl');
    document.getElementById('dl-link').href = url;
    dl.style.display = 'block';
  } catch (e) {
    err.textContent = e.message;
    err.style.display = 'block';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generate PDF';
  }
}

loadExample('aurora-lithium');
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    templates = json.dumps([[name, TEMPLATES[name]] for name in sorted(TEMPLATES)])
    return PAGE.replace("__TEMPLATES__", templates)


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


def _save_upload(upload: UploadFile, directory: Path, stem: str) -> str | None:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_SUFFIXES:
        return None
    dest = directory / f"{stem}{suffix}"
    with dest.open("wb") as fh:
        shutil.copyfileobj(upload.file, fh)
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
                return JSONResponse({"error": "Unsupported logo file type"}, status_code=400)
            company["logo"] = saved
        if hero is not None and hero.filename:
            saved = _save_upload(hero, tmp_path, "hero")
            if saved is None:
                return JSONResponse({"error": "Unsupported hero image type"}, status_code=400)
            company["hero_image"] = saved

        profile_path = tmp_path / "profile.json"
        profile_path.write_text(json.dumps(data))
        try:
            context = load_profile(profile_path)
            pdf_path = render_pdf(context, template, tmp_path / "out.pdf")
        except (ProfileError, ValueError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        company_name = (company.get("name") or "onepager").strip().replace(" ", "-")
        return Response(
            content=pdf_path.read_bytes(),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{company_name}-{template}.pdf"'
            },
        )
