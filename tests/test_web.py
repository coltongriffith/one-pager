"""Web UI endpoint tests."""

import json
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from onepager.web import app

ROOT = Path(__file__).parent.parent
client = TestClient(app)


def test_index_serves_ui():
    res = client.get("/")
    assert res.status_code == 200
    assert "Generate PDF" in res.text


def test_example_endpoint_strips_local_assets():
    res = client.get("/example/aurora-lithium")
    assert res.status_code == 200
    data = res.json()
    assert "logo" not in data["company"]
    assert all("image" not in p for p in data["projects"])


def test_example_unknown_404():
    assert client.get("/example/does-not-exist").status_code == 404


def test_generate_pdf():
    profile = json.dumps({"company": {"name": "Web Test Corp."}})
    res = client.post("/generate", data={"profile": profile, "template": "catalyst"})
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")


def test_generate_with_logo_upload():
    profile = json.dumps({"company": {"name": "Web Test Corp."}})
    logo = (ROOT / "examples/assets/northbeam-logo.png").read_bytes()
    res = client.post(
        "/generate",
        data={"profile": profile, "template": "factsheet"},
        files={"logo": ("logo.png", logo, "image/png")},
    )
    assert res.status_code == 200
    assert res.content.startswith(b"%PDF")


def test_validate_endpoint():
    res = client.post("/validate", data={"profile": '{"company": {"name": "Sparse Co."}}'})
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body["warnings"], list) and body["warnings"]
    # malformed JSON yields an empty (non-crashing) result
    assert client.post("/validate", data={"profile": "{bad"}).json()["warnings"] == []


def test_parse_captable_text():
    res = client.post("/parse-captable", data={"text": "Shares Outstanding\t92,450,000"})
    assert res.status_code == 200
    assert res.json()["shares_outstanding"] == 92450000


def test_parse_captable_rejects_bad_format():
    res = client.post(
        "/parse-captable",
        files={"file": ("cap.exe", b"MZ", "application/octet-stream")},
    )
    assert res.status_code == 400
    assert client.post("/parse-captable", data={"text": ""}).status_code == 400


def test_generate_html_fallback(monkeypatch):
    """Without WeasyPrint (e.g. on Vercel), /generate returns printable HTML."""
    import onepager.web as web

    monkeypatch.setenv("ONEPAGER_DISABLE_WEASYPRINT", "1")
    web.weasyprint_available.cache_clear()
    try:
        profile = json.dumps({"company": {"name": "Serverless Corp."}})
        res = client.post("/generate", data={"profile": profile, "template": "catalyst"})
        assert res.status_code == 200
        body = res.json()
        assert body["filename"] == "Serverless-Corp.-catalyst.pdf"
        assert "<!DOCTYPE html>" in body["html"]
        assert "data:font/ttf;base64," in body["html"]
    finally:
        web.weasyprint_available.cache_clear()


def test_generate_rejects_bad_input():
    assert client.post("/generate", data={"profile": "{bad", "template": "catalyst"}).status_code == 400
    assert client.post("/generate", data={"profile": "{}", "template": "nope"}).status_code == 400
    res = client.post(
        "/generate",
        data={"profile": '{"company": {"name": "X"}}', "template": "catalyst"},
        files={"logo": ("evil.exe", b"MZ", "application/octet-stream")},
    )
    assert res.status_code == 400
