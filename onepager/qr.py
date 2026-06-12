"""QR code generation as inline SVG data URIs.

Used on conference handouts so investors can scan straight through to the
website or investor deck. Returns None when no link is given or segno is
unavailable, so callers can treat QR codes as optional.
"""

from __future__ import annotations

import base64
import io


def _normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        return value
    if not value.startswith(("http://", "https://")):
        return "https://" + value
    return value


def qr_data_uri(data: str | None, dark: str = "#000000") -> str | None:
    """Render `data` (a URL) as an SVG QR code data URI, or None."""
    if not data:
        return None
    try:
        import segno
    except ImportError:
        return None
    try:
        code = segno.make(_normalize_url(data), error="m")
        buffer = io.BytesIO()
        code.save(
            buffer, kind="svg", xmldecl=False, svgns=True, scale=1, border=0, dark=dark
        )
        svg = buffer.getvalue().decode("utf-8")
    except Exception:
        return None
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"
