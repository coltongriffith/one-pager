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


# Commodity-specific default palettes (primary, accent). An explicitly supplied
# brand color always wins; these only fill in when no brand color is given.
COMMODITY_THEMES = {
    "lithium": ("#0E7C66", "#E8A33D"),
    "copper": ("#1C3B5A", "#C2703D"),
    "gold": ("#1A1A1A", "#C8A24B"),
    "silver": ("#33373B", "#8C9BA5"),
    "uranium": ("#1F2A22", "#E6C200"),
    "rare earth": ("#23306B", "#8E7CC3"),
    "rare earths": ("#23306B", "#8E7CC3"),
    "nickel": ("#2B4A4A", "#A9B7AE"),
    "graphite": ("#2A2D34", "#6E7B8B"),
    "oil": ("#1B2430", "#3F8F6B"),
    "gas": ("#1B2430", "#3F8F6B"),
    "potash": ("#7A2E2E", "#E0A33D"),
    "diamond": ("#1E2B45", "#7FB7D6"),
}


def commodity_theme(commodity: str | None) -> tuple[str, str] | None:
    """Match a free-text commodity to a (primary, accent) theme, or None."""
    if not commodity:
        return None
    text = commodity.lower()
    for key, theme in COMMODITY_THEMES.items():
        if key in text:
            return theme
    return None


def build_palette(
    primary: str | None,
    accent: str | None,
    logo_path: Path | None,
    commodity: str | None = None,
) -> dict:
    """Derive the full set of palette tokens used by every template.

    Color precedence: explicit brand color > color extracted from a raster
    logo > commodity-specific theme > built-in default.
    """
    theme = commodity_theme(commodity)
    if not primary and logo_path is not None:
        primary = extract_brand_color(logo_path)
    if not primary and theme:
        primary = theme[0]
    if not accent and theme:
        accent = theme[1]
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
