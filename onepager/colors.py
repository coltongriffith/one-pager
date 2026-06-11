"""Color helpers: hex math, shade derivation, and brand color extraction from logos."""

from __future__ import annotations

from pathlib import Path

DEFAULT_PRIMARY = "#16365C"
DEFAULT_ACCENT = "#E8A33D"


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, round(c))) for c in rgb))


def mix(color: str, other: str, amount: float) -> str:
    """Mix `color` toward `other` by `amount` (0..1)."""
    a = hex_to_rgb(color)
    b = hex_to_rgb(other)
    return rgb_to_hex(tuple(a[i] + (b[i] - a[i]) * amount for i in range(3)))


def lighten(color: str, amount: float) -> str:
    return mix(color, "#FFFFFF", amount)


def darken(color: str, amount: float) -> str:
    return mix(color, "#000000", amount)


def luminance(color: str) -> float:
    r, g, b = hex_to_rgb(color)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255


def text_on(color: str) -> str:
    """Readable text color (white or near-black) for a given background."""
    return "#FFFFFF" if luminance(color) < 0.55 else "#1A1A1A"


def rgba(color: str, alpha: float) -> str:
    r, g, b = hex_to_rgb(color)
    return f"rgba({r}, {g}, {b}, {alpha})"


def extract_brand_color(logo_path: Path) -> str | None:
    """Pick the most saturated prominent color from a raster logo.

    Returns None for SVG logos or when nothing usable is found.
    """
    if logo_path.suffix.lower() == ".svg":
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        img = Image.open(logo_path).convert("RGBA")
    except Exception:
        return None
    background = Image.new("RGBA", img.size, (255, 255, 255, 255))
    img = Image.alpha_composite(background, img).convert("RGB")
    img.thumbnail((96, 96))
    counts = img.getcolors(96 * 96) or []
    best, best_score = None, 0.0
    for count, (r, g, b) in counts:
        mx, mn = max(r, g, b), min(r, g, b)
        saturation = (mx - mn) / mx if mx else 0
        brightness = mx / 255
        if saturation < 0.25 or brightness < 0.15 or brightness > 0.97:
            continue
        score = count * saturation
        if score > best_score:
            best, best_score = (r, g, b), score
    return rgb_to_hex(best) if best else None


def build_palette(primary: str | None, accent: str | None, logo_path: Path | None) -> dict:
    """Derive the full set of palette tokens used by every template."""
    if not primary and logo_path is not None:
        primary = extract_brand_color(logo_path)
    primary = primary or DEFAULT_PRIMARY
    accent = accent or DEFAULT_ACCENT
    return {
        "primary": primary,
        "accent": accent,
        "primary_dark": darken(primary, 0.25),
        "primary_deep": darken(primary, 0.45),
        "primary_soft": lighten(primary, 0.88),
        "primary_mist": lighten(primary, 0.94),
        "primary_mid": lighten(primary, 0.35),
        "accent_soft": lighten(accent, 0.85),
        "accent_dark": darken(accent, 0.2),
        "on_primary": text_on(primary),
        "on_accent": text_on(accent),
        "ink": "#1B2430",
        "muted": "#5A6572",
        "line": "#DEE3EA",
        "paper": "#FFFFFF",
    }
