"""Tests for the investor-factsheet feature set: EV, QR, themes, validation."""

import json

from onepager.colors import build_palette, commodity_theme
from onepager.profile import load_profile
from onepager.qr import qr_data_uri
from onepager.validate import recommend_template, validate_profile


def _write(tmp_path, data):
    path = tmp_path / "p.json"
    path.write_text(json.dumps(data))
    return path


def test_enterprise_value_computed(tmp_path):
    path = _write(
        tmp_path,
        {
            "company": {"name": "EV Co."},
            "share_structure": {
                "share_price": 1.0,
                "shares_outstanding": 100_000_000,
                "cash_position": 20_000_000,
                "debt": 5_000_000,
            },
        },
    )
    rows = {r["label"]: r["value"] for r in load_profile(path)["share_rows"]}
    # EV = 100M market cap - 20M cash + 5M debt = 85M
    assert rows["Enterprise Value"] == "$85M"


def test_auto_key_metrics(tmp_path):
    path = _write(
        tmp_path,
        {
            "company": {"name": "Metric Co."},
            "share_structure": {"cash_position": 11_400_000, "market_cap": 57_000_000},
            "catalysts": [{"timing": "Q1 2027", "catalyst": "Maiden resource"}],
        },
    )
    metrics = load_profile(path)["key_metrics"]
    labels = [m["label"] for m in metrics]
    assert labels == ["Treasury", "Market Cap", "Next Catalyst"]
    assert metrics[2]["value"] == "Q1 2027"


def test_commodity_theme_applied(tmp_path):
    assert commodity_theme("Lithium brine exploration") == ("#0E7C66", "#E8A33D")
    assert commodity_theme("Gold") == ("#1A1A1A", "#C8A24B")
    assert commodity_theme("widgets") is None
    # commodity drives palette when no brand color is given
    palette = build_palette(None, None, None, "Copper porphyry")
    assert palette["primary"] == "#1C3B5A"
    # explicit brand color overrides the commodity theme
    palette = build_palette("#123456", None, None, "Copper")
    assert palette["primary"] == "#123456"


def test_qr_data_uri():
    uri = qr_data_uri("auroralithium.com")
    assert uri and uri.startswith("data:image/svg+xml;base64,")
    assert qr_data_uri(None) is None


def test_qr_in_profile(tmp_path):
    path = _write(
        tmp_path, {"company": {"name": "QR Co.", "deck_url": "example.com/deck"}}
    )
    context = load_profile(path)
    assert context["company"]["qr"].startswith("data:image/svg+xml")
    assert context["company"]["qr_url"] == "example.com/deck"


def test_validation_flags_gaps():
    warnings = validate_profile({"company": {"name": "Sparse Co."}})
    joined = " ".join(warnings)
    assert "logo" in joined
    assert "commodity" in joined
    assert "catalyst" in joined.lower()


def test_validation_market_cap_mismatch():
    data = {
        "company": {"name": "X"},
        "share_structure": {
            "share_price": 1.0,
            "shares_outstanding": 100_000_000,
            "market_cap": 500_000_000,
        },
    }
    assert any("doesn't match" in w for w in validate_profile(data))


def test_recommend_template():
    assert recommend_template({"company": {"stage": "Drill discovery"}}) == "asset"
    assert recommend_template({"company": {"stage": "Conference season"}}) == "catalyst"
    assert recommend_template({"company": {}}) is None
