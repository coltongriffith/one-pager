"""Load and normalize a company profile JSON into template-ready context."""

from __future__ import annotations

import json
from pathlib import Path

from .colors import build_palette

SHARE_FIELDS = [
    ("share_price", "Share Price"),
    ("shares_outstanding", "Shares Outstanding"),
    ("options", "Options"),
    ("warrants", "Warrants"),
    ("fully_diluted", "Fully Diluted"),
    ("market_cap", "Market Cap"),
    ("week52_range", "52-Week Range"),
    ("cash_position", "Cash Position"),
    ("insider_ownership", "Insider Ownership"),
]

MONEY_FIELDS = {"share_price", "market_cap", "cash_position"}


class ProfileError(ValueError):
    """Raised when a profile file is missing required data."""


def fmt_number(value) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if isinstance(value, float) and not value.is_integer():
            return f"{value:,.2f}"
        return f"{int(value):,}"
    return str(value)


def fmt_compact_money(value) -> str:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return str(value)
    for threshold, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= threshold:
            scaled = value / threshold
            return f"${scaled:,.1f}{suffix}".replace(".0" + suffix, suffix)
    if isinstance(value, float) and value < 100:
        return f"${value:,.2f}"
    return f"${value:,.0f}"


def fmt_money(value) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if abs(value) >= 100_000:
            return fmt_compact_money(value)
        if isinstance(value, float) and not value.is_integer():
            return f"${value:,.2f}"
        return f"${int(value):,}"
    return str(value)


def _resolve_asset(base_dir: Path, value) -> str | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    if not path.exists():
        raise ProfileError(f"Asset not found: {path}")
    return path.resolve().as_uri()


def _share_rows(structure: dict) -> list[dict]:
    rows = []
    for key, label in SHARE_FIELDS:
        if key not in structure or structure[key] in (None, ""):
            continue
        value = structure[key]
        formatted = fmt_money(value) if key in MONEY_FIELDS else fmt_number(value)
        rows.append({"key": key, "label": label, "value": formatted})
    for extra in structure.get("extra", []):
        rows.append({"key": "extra", "label": extra["label"], "value": str(extra["value"])})
    return rows


def _autofill_share_structure(structure: dict) -> dict:
    structure = dict(structure)
    numeric = lambda k: (
        structure.get(k)
        if isinstance(structure.get(k), (int, float)) and not isinstance(structure.get(k), bool)
        else None
    )
    if "fully_diluted" not in structure:
        parts = [numeric(k) for k in ("shares_outstanding", "options", "warrants")]
        if parts[0] is not None:
            structure["fully_diluted"] = sum(p for p in parts if p is not None)
    if "market_cap" not in structure:
        price, shares = numeric("share_price"), numeric("shares_outstanding")
        if price is not None and shares is not None:
            structure["market_cap"] = price * shares
    return structure


def load_profile(path: str | Path) -> dict:
    """Read a profile JSON and return a normalized template context."""
    path = Path(path)
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ProfileError(f"Invalid JSON in {path}: {exc}") from exc
    base_dir = path.parent.resolve()

    company = data.get("company") or {}
    if not company.get("name"):
        raise ProfileError("Profile must include company.name")

    listings = data.get("listings") or []
    ticker_line = " | ".join(
        f"{item['exchange']}: {item['ticker']}" for item in listings if item.get("ticker")
    )

    structure = _autofill_share_structure(data.get("share_structure") or {})

    context = {
        "company": {
            "name": company["name"],
            "tagline": company.get("tagline", ""),
            "description": company.get("description", ""),
            "sector": company.get("sector", ""),
            "website": company.get("website", ""),
            "email": company.get("email", ""),
            "phone": company.get("phone", ""),
            "address": company.get("address", ""),
            "logo": _resolve_asset(base_dir, company.get("logo")),
            "hero_image": _resolve_asset(base_dir, company.get("hero_image")),
        },
        "listings": listings,
        "ticker_line": ticker_line,
        "share_rows": _share_rows(structure),
        "share_as_of": structure.get("as_of", ""),
        "highlights": [
            {
                "title": h.get("title", ""),
                "text": h.get("text", ""),
                "icon": h.get("icon", "star"),
            }
            for h in data.get("highlights", [])
        ],
        "projects": [
            {
                "name": p.get("name", ""),
                "location": p.get("location", ""),
                "summary": p.get("summary", ""),
                "bullets": p.get("bullets", []),
                "image": _resolve_asset(base_dir, p.get("image")),
            }
            for p in data.get("projects", [])
        ],
        "team": data.get("team", []),
        "news": data.get("news", []),
        "disclaimer": data.get(
            "disclaimer",
            "This document is for informational purposes only and does not constitute an "
            "offer to sell or a solicitation to buy any securities. All figures are "
            "approximate and subject to change. Investors should conduct their own due "
            "diligence and consult a registered investment advisor.",
        ),
    }

    brand = data.get("brand") or {}
    logo_local = None
    if company.get("logo"):
        logo_local = Path(company["logo"])
        if not logo_local.is_absolute():
            logo_local = base_dir / logo_local
    context["palette"] = build_palette(brand.get("primary"), brand.get("accent"), logo_local)
    return context
