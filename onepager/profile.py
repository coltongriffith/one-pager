"""Load and normalize a company profile JSON into template-ready context."""

from __future__ import annotations

import json
from pathlib import Path

from .colors import build_palette
from .qr import qr_data_uri

SHARE_FIELDS = [
    ("share_price", "Share Price"),
    ("shares_outstanding", "Shares Outstanding"),
    ("options", "Options"),
    ("warrants", "Warrants"),
    ("fully_diluted", "Fully Diluted"),
    ("market_cap", "Market Cap"),
    ("enterprise_value", "Enterprise Value"),
    ("week52_range", "52-Week Range"),
    ("cash_position", "Cash Position"),
    ("debt", "Debt"),
    ("insider_ownership", "Insider Ownership"),
]

MONEY_FIELDS = {"share_price", "market_cap", "cash_position", "enterprise_value", "debt"}

# Stat keys investors prioritize on a conference handout (used to compress the
# factsheet sidebar to its most decision-relevant rows).
PRIORITY_SHARE_KEYS = [
    "market_cap",
    "enterprise_value",
    "cash_position",
    "shares_outstanding",
    "fully_diluted",
    "insider_ownership",
    "week52_range",
]


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


_MIME_BY_SUFFIX = {
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def _resolve_asset(base_dir: Path, value, inline: bool = False) -> str | None:
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    if not path.exists():
        raise ProfileError(f"Asset not found: {path}")
    if inline:
        import base64

        mime = _MIME_BY_SUFFIX.get(path.suffix.lower(), "application/octet-stream")
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{encoded}"
    return path.resolve().as_uri()


def _share_rows(structure: dict, keys: list | None = None) -> list[dict]:
    fields = SHARE_FIELDS if keys is None else [(k, dict(SHARE_FIELDS)[k]) for k in keys]
    rows = []
    for key, label in fields:
        if key not in structure or structure[key] in (None, ""):
            continue
        value = structure[key]
        formatted = fmt_money(value) if key in MONEY_FIELDS else fmt_number(value)
        rows.append({"key": key, "label": label, "value": formatted})
    if keys is None:
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
    # Enterprise value = market cap - cash + debt (debt defaults to 0)
    if "enterprise_value" not in structure:
        market_cap, cash = numeric("market_cap"), numeric("cash_position")
        if market_cap is not None and cash is not None:
            structure["enterprise_value"] = market_cap - cash + (numeric("debt") or 0)
    return structure


def _auto_key_metrics(context: dict, structure: dict) -> list[dict]:
    """Build a 3-metric headline strip when the profile doesn't supply one."""
    metrics = []
    cash = structure.get("cash_position")
    if isinstance(cash, (int, float)) and not isinstance(cash, bool):
        metrics.append({"label": "Treasury", "value": fmt_money(cash)})
    market_cap = structure.get("market_cap")
    if isinstance(market_cap, (int, float)) and not isinstance(market_cap, bool):
        metrics.append({"label": "Market Cap", "value": fmt_money(market_cap)})
    if context["catalysts"]:
        nxt = context["catalysts"][0]
        metrics.append(
            {"label": "Next Catalyst", "value": nxt.get("timing") or nxt.get("catalyst", "")}
        )
    elif structure.get("week52_range"):
        metrics.append({"label": "52-Week Range", "value": str(structure["week52_range"])})
    return metrics[:3]


def load_profile(path: str | Path, inline_assets: bool = False) -> dict:
    """Read a profile JSON and return a normalized template context.

    With `inline_assets=True`, images become data URIs instead of file:// URLs
    so the rendered HTML is portable (e.g. for printing in a remote browser).
    """
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

    # subhead like "Lithium brine exploration | Argentina & Chile"
    subhead = " | ".join(
        part for part in (company.get("commodity"), company.get("jurisdiction")) if part
    )

    context = {
        "company": {
            "name": company["name"],
            "tagline": company.get("tagline", ""),
            "description": company.get("description", ""),
            "sector": company.get("sector", ""),
            "commodity": company.get("commodity", ""),
            "jurisdiction": company.get("jurisdiction", ""),
            "subhead": subhead,
            "website": company.get("website", ""),
            "email": company.get("email", ""),
            "phone": company.get("phone", ""),
            "address": company.get("address", ""),
            "logo": _resolve_asset(base_dir, company.get("logo"), inline_assets),
            "hero_image": _resolve_asset(base_dir, company.get("hero_image"), inline_assets),
        },
        "listings": listings,
        "ticker_line": ticker_line,
        "share_rows": _share_rows(structure),
        "priority_share_rows": _share_rows(structure, PRIORITY_SHARE_KEYS),
        "share_as_of": structure.get("as_of", ""),
        "market_meta": {
            "currency": structure.get("currency", ""),
            "as_of": structure.get("as_of", ""),
            "source": structure.get("source", ""),
        },
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
                "stage": p.get("stage", ""),
                "size": p.get("size", ""),
                "ownership": p.get("ownership", ""),
                "key_point": p.get("key_point", ""),
                "image": _resolve_asset(base_dir, p.get("image"), inline_assets),
            }
            for p in data.get("projects", [])
        ],
        "team": [
            {
                "name": m.get("name", ""),
                "title": m.get("title", ""),
                "note": m.get("note", "") or m.get("bio", ""),
            }
            for m in data.get("team", [])
        ],
        "news": data.get("news", []),
        "catalysts": [
            {"timing": c.get("timing", ""), "catalyst": c.get("catalyst", "")}
            for c in data.get("catalysts", [])
        ],
        "why_now": data.get("why_now", []),
        "disclaimer": data.get(
            "disclaimer",
            "This document is for informational purposes only and does not constitute an "
            "offer to sell or a solicitation to buy any securities. All figures are "
            "approximate and subject to change. Investors should conduct their own due "
            "diligence and consult a registered investment advisor.",
        ),
    }

    context["key_metrics"] = [
        {"label": m.get("label", ""), "value": m.get("value", "")}
        for m in data.get("key_metrics", [])
    ] or _auto_key_metrics(context, structure)

    brand = data.get("brand") or {}
    logo_local = None
    if company.get("logo"):
        logo_local = Path(company["logo"])
        if not logo_local.is_absolute():
            logo_local = base_dir / logo_local
    context["palette"] = build_palette(
        brand.get("primary"), brand.get("accent"), logo_local, company.get("commodity")
    )

    qr_target = company.get("qr_url") or company.get("deck_url") or company.get("website")
    context["company"]["qr"] = qr_data_uri(qr_target, dark=context["palette"]["primary"])
    context["company"]["qr_url"] = qr_target or ""
    return context
