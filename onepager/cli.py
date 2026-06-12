"""Command-line interface for generating investor one-pager PDFs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .icons import available_icons
from .profile import ProfileError, load_profile
from .render import DEFAULT_PAGE_SIZE, PAGE_SIZES, TEMPLATES, render_pdf

STARTER_PROFILE = {
    "company": {
        "name": "Example Resources Corp.",
        "tagline": "A short positioning statement for investors",
        "description": "Two to four sentences describing the company, what it does, "
        "and why it matters. Pulled from public filings, the corporate website, "
        "or an investor presentation.",
        "sector": "Sector / Industry",
        "website": "www.example.com",
        "email": "ir@example.com",
        "phone": "+1 (555) 000-0000",
        "address": "City, Country",
        "logo": None,
        "hero_image": None,
    },
    "listings": [{"exchange": "TSXV", "ticker": "XYZ"}],
    "share_structure": {
        "as_of": "June 2026",
        "share_price": 0.45,
        "shares_outstanding": 85000000,
        "options": 4500000,
        "warrants": 12000000,
        "week52_range": "$0.18 – $0.62",
        "cash_position": 6200000,
    },
    "highlights": [
        {"icon": "growth", "title": "Highlight One", "text": "Why this matters to investors."},
        {"icon": "shield", "title": "Highlight Two", "text": "Another key strength."},
        {"icon": "users", "title": "Highlight Three", "text": "A third differentiator."},
    ],
    "projects": [
        {
            "name": "Flagship Asset",
            "location": "Region, Country",
            "summary": "One-line overview of the asset or business unit.",
            "bullets": ["Key fact one", "Key fact two", "Key fact three"],
            "image": None,
        }
    ],
    "team": [{"name": "Jane Doe", "title": "Chief Executive Officer"}],
    "news": [{"date": "2026-05-01", "title": "Recent press release headline"}],
    "brand": {"primary": "#16365C", "accent": "#E8A33D"},
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="onepager",
        description="Generate beautifully designed investor one-pager PDFs from a "
        "company profile JSON.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Render a profile JSON to PDF")
    build.add_argument("profile", help="Path to the company profile JSON")
    build.add_argument(
        "-t",
        "--template",
        default="boardroom",
        choices=sorted(TEMPLATES),
        help="Template to use (default: boardroom)",
    )
    build.add_argument(
        "-o",
        "--output",
        help="Output PDF path, or a directory when using --all "
        "(default: <profile-name>-<template>.pdf)",
    )
    build.add_argument(
        "--all",
        action="store_true",
        help="Render the profile with every template",
    )
    build.add_argument(
        "-p",
        "--page-size",
        default=DEFAULT_PAGE_SIZE,
        choices=sorted(PAGE_SIZES),
        help=f"Page size for printing (default: {DEFAULT_PAGE_SIZE})",
    )

    list_parser = sub.add_parser("templates", help="List available templates")
    list_parser.add_argument(
        "--icons", action="store_true", help="Also list available highlight icons"
    )

    init = sub.add_parser("init", help="Write a starter profile JSON to fill in")
    init.add_argument("path", help="Destination for the starter profile JSON")

    serve = sub.add_parser("serve", help="Run the browser UI (requires fastapi + uvicorn)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    args = parser.parse_args(argv)

    if args.command == "serve":
        try:
            import uvicorn
        except ImportError:
            print(
                "The web UI needs extra packages: pip install fastapi uvicorn python-multipart",
                file=sys.stderr,
            )
            return 1
        uvicorn.run("onepager.web:app", host=args.host, port=args.port)
        return 0

    if args.command == "templates":
        for name in sorted(TEMPLATES):
            print(f"{name:<12} {TEMPLATES[name]}")
        if args.icons:
            print("\nicons:", ", ".join(available_icons()))
        return 0

    if args.command == "init":
        dest = Path(args.path)
        if dest.exists():
            print(f"Refusing to overwrite existing file: {dest}", file=sys.stderr)
            return 1
        dest.write_text(json.dumps(STARTER_PROFILE, indent=2) + "\n")
        print(f"Starter profile written to {dest}")
        return 0

    # build
    try:
        context = load_profile(args.profile)
    except (ProfileError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    stem = Path(args.profile).stem
    templates = sorted(TEMPLATES) if args.all else [args.template]
    for template in templates:
        if args.all:
            out_dir = Path(args.output) if args.output else Path.cwd()
            out = out_dir / f"{stem}-{template}.pdf"
        else:
            out = Path(args.output) if args.output else Path(f"{stem}-{template}.pdf")
        result = render_pdf(context, template, out, page_size=args.page_size)
        print(f"Wrote {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
