"""Profile validation: surface gaps that weaken an investor one-pager.

These are advisory warnings, not errors — the document still renders. They help
users produce a conference-ready sheet (quote date, currency, a catalyst, a
visual, a contact, internally consistent market data, concise copy).
"""

from __future__ import annotations

import re

# Soft content-length limits (characters) that keep a single page uncluttered.
LENGTH_LIMITS = {
    "tagline": 80,
    "description": 360,
    "highlight": 220,
    "bullet": 120,
    "bio": 110,
}


def _num(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def validate_profile(data: dict) -> list[str]:
    """Return a list of human-readable warnings for a raw profile dict."""
    warnings: list[str] = []
    company = data.get("company") or {}
    share = data.get("share_structure") or {}

    if not company.get("logo"):
        warnings.append("No logo uploaded — the header will show the company name as text.")
    if not company.get("hero_image") and not any(
        p.get("image") for p in data.get("projects") or []
    ):
        warnings.append(
            "No image or map — add a hero image or a project map; mining/asset "
            "one-pagers feel incomplete without a visual."
        )
    if not company.get("commodity"):
        warnings.append("No commodity set — add one to drive the subhead and color theme.")
    if not company.get("jurisdiction"):
        warnings.append("No jurisdiction set — investors want to know where the assets are.")
    if not (company.get("qr_url") or company.get("deck_url") or company.get("website")):
        warnings.append("No website/deck link — add one to generate a scannable QR code.")
    if not (company.get("email") or company.get("phone")):
        warnings.append("No contact details — add an investor email or phone.")

    if share:
        if not share.get("as_of"):
            warnings.append("No quote date (share_structure.as_of) for the market data.")
        if not share.get("currency"):
            warnings.append("No currency label (e.g. CAD/USD) on the market data.")
        if not share.get("source"):
            warnings.append("No data source noted for the market figures.")
        price, shares, market_cap = (
            _num(share.get("share_price")),
            _num(share.get("shares_outstanding")),
            _num(share.get("market_cap")),
        )
        if price is not None and shares is not None and market_cap is not None:
            implied = price * shares
            if implied and abs(market_cap - implied) / implied > 0.05:
                warnings.append(
                    f"Market cap ({market_cap:,.0f}) doesn't match share price × shares "
                    f"outstanding ({implied:,.0f}) — off by more than 5%."
                )
    else:
        warnings.append("No share structure / cap table provided.")

    if not data.get("catalysts"):
        warnings.append(
            "No upcoming catalysts — investors care most about what's coming next."
        )
    for project in data.get("projects") or []:
        if not project.get("location"):
            warnings.append(f"Project '{project.get('name', '?')}' has no location.")

    for highlight in data.get("highlights") or []:
        text = f"{highlight.get('title', '')} {highlight.get('text', '')}"
        if not re.search(r"\d", text):
            warnings.append(
                f"Highlight '{highlight.get('title', '?')}' has no number — "
                "evidence-based claims land harder than generic ones."
            )

    # length / clutter checks
    if len(company.get("tagline", "")) > LENGTH_LIMITS["tagline"]:
        warnings.append("Headline is long — aim for 8–12 words.")
    if len(company.get("description", "")) > LENGTH_LIMITS["description"]:
        warnings.append("Company summary is long — aim for 35–55 words.")
    for highlight in data.get("highlights") or []:
        if len(highlight.get("text", "")) > LENGTH_LIMITS["highlight"]:
            warnings.append(f"Highlight '{highlight.get('title', '?')}' text is long.")
            break
    for project in data.get("projects") or []:
        if any(len(b) > LENGTH_LIMITS["bullet"] for b in project.get("bullets") or []):
            warnings.append(f"Project '{project.get('name', '?')}' has a long bullet.")
            break

    return warnings


# Company stage → recommended template, for auto layout-mode selection.
STAGE_TEMPLATES = {
    "early exploration": "factsheet",
    "exploration": "factsheet",
    "drill": "asset",
    "discovery": "asset",
    "resource": "asset",
    "development": "asset",
    "producer": "factsheet",
    "production": "factsheet",
    "royalty": "factsheet",
    "conference": "catalyst",
    "financing": "catalyst",
}


def recommend_template(data: dict) -> str | None:
    """Suggest a template from company.stage, or None."""
    stage = ((data.get("company") or {}).get("stage") or "").lower()
    if not stage:
        return None
    for key, template in STAGE_TEMPLATES.items():
        if key in stage:
            return template
    return None
