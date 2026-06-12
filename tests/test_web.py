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
    res = client.post("/generate", data={"profile": profile, "template": "summit"})
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF")


def test_generate_with_logo_upload():
    profile = json.dumps({"company": {"name": "Web Test Corp."}})
    logo = (ROOT / "examples/assets/northbeam-logo.png").read_bytes()
    res = client.post(
        "/generate",
        data={"profile": profile, "template": "boardroom"},
        files={"logo": ("logo.png", logo, "image/png")},
    )
    assert res.status_code == 200
    assert res.content.startswith(b"%PDF")


def test_generate_rejects_bad_input():
    assert client.post("/generate", data={"profile": "{bad", "template": "summit"}).status_code == 400
    assert client.post("/generate", data={"profile": "{}", "template": "nope"}).status_code == 400
    res = client.post(
        "/generate",
        data={"profile": '{"company": {"name": "X"}}', "template": "summit"},
        files={"logo": ("evil.exe", b"MZ", "application/octet-stream")},
    )
    assert res.status_code == 400
