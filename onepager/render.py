"""Render a normalized profile context to PDF through Jinja2 + WeasyPrint."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from .icons import icon_svg

PACKAGE_DIR = Path(__file__).parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
FONTS_DIR = PACKAGE_DIR / "fonts"

TEMPLATES = {
    "boardroom": "Structured two-column corporate layout with a dark stats panel "
    "and an investment-highlights grid.",
    "horizon": "Hero-image layout with centered branding, icon feature cards, "
    "and a share-information table.",
    "summit": "Modern full-height brand sidebar with large display type and "
    "stacked key statistics.",
}


def _font_face_css() -> str:
    faces = [
        ("Inter", 400, "normal", "Inter-400.ttf"),
        ("Inter", 500, "normal", "Inter-500.ttf"),
        ("Inter", 600, "normal", "Inter-600.ttf"),
        ("Inter", 700, "normal", "Inter-700.ttf"),
        ("Inter", 400, "italic", "Inter-Italic-400.ttf"),
        ("Space Grotesk", 500, "normal", "SpaceGrotesk-500.ttf"),
        ("Space Grotesk", 700, "normal", "SpaceGrotesk-700.ttf"),
    ]
    rules = []
    for family, weight, style, filename in faces:
        url = (FONTS_DIR / filename).resolve().as_uri()
        rules.append(
            f"@font-face {{ font-family: '{family}'; font-weight: {weight}; "
            f"font-style: {style}; src: url('{url}'); }}"
        )
    return "\n".join(rules)


def _environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html"]),
    )
    env.filters["icon"] = lambda name: Markup(icon_svg(name))
    return env


def render_pdf(context: dict, template: str, output_path: str | Path) -> Path:
    """Render `context` with the named template and write a PDF."""
    if template not in TEMPLATES:
        raise ValueError(
            f"Unknown template '{template}'. Available: {', '.join(sorted(TEMPLATES))}"
        )
    from weasyprint import HTML

    env = _environment()
    html_source = env.get_template(f"{template}/page.html").render(
        **context, font_faces=Markup(_font_face_css())
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_source, base_url=str(TEMPLATES_DIR)).write_pdf(str(output_path))
    return output_path
