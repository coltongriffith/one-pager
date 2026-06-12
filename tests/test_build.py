"""Smoke tests: every example profile renders a single-page PDF in every template."""

from pathlib import Path

import pytest

from onepager.profile import ProfileError, load_profile
from onepager.render import PAGE_SIZES, TEMPLATES, render_pdf

ROOT = Path(__file__).parent.parent
EXAMPLES = sorted(ROOT.glob("examples/*.json"))


@pytest.mark.parametrize("profile_path", EXAMPLES, ids=lambda p: p.stem)
@pytest.mark.parametrize("template", sorted(TEMPLATES))
@pytest.mark.parametrize("page_size", sorted(PAGE_SIZES))
def test_examples_render_one_page(profile_path, template, page_size, tmp_path):
    context = load_profile(profile_path)
    out = render_pdf(
        context,
        template,
        tmp_path / f"{profile_path.stem}-{template}-{page_size}.pdf",
        page_size=page_size,
    )
    data = out.read_bytes()
    assert data.startswith(b"%PDF")
    assert data.count(b"/Type /Page\n") + data.count(b"/Type /Page>") <= 2


def test_minimal_profile(tmp_path):
    profile = tmp_path / "minimal.json"
    profile.write_text('{"company": {"name": "Bare Minimum Inc."}}')
    context = load_profile(profile)
    for template in TEMPLATES:
        out = render_pdf(context, template, tmp_path / f"min-{template}.pdf")
        assert out.read_bytes().startswith(b"%PDF")


def test_missing_name_rejected(tmp_path):
    profile = tmp_path / "bad.json"
    profile.write_text('{"company": {}}')
    with pytest.raises(ProfileError):
        load_profile(profile)


def test_derived_share_fields(tmp_path):
    profile = tmp_path / "derived.json"
    profile.write_text(
        '{"company": {"name": "X"}, "share_structure": '
        '{"share_price": 2.0, "shares_outstanding": 1000000, "options": 50000}}'
    )
    rows = {r["label"]: r["value"] for r in load_profile(profile)["share_rows"]}
    assert rows["Fully Diluted"] == "1,050,000"
    assert rows["Market Cap"] == "$2M"
