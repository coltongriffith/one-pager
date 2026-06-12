"""Vercel entrypoint: exposes the FastAPI app as an ASGI function.

All non-/api routes are rewritten here (see vercel.json), so the builder UI,
/example, /parse-captable, and /generate are served by this function. PDF
printing happens in api/pdf.js because WeasyPrint's native libraries are not
available in the serverless Python runtime — /generate detects that and
returns self-contained HTML instead.

If the app fails to import, a minimal ASGI app serves the traceback and
environment details so the failure is debuggable from the browser instead of
surfacing as an opaque FUNCTION_INVOCATION_FAILED.

Note: Vercel's Python builder statically looks for a module-level `app`
variable to detect an ASGI function — keep the `app = _load_app()` assignment
at top level.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _diagnostic_app(traceback_text: str):
    def _report() -> str:
        lines = [
            "onepager failed to start. Startup traceback:",
            "",
            traceback_text,
            "-" * 60,
            f"python: {sys.version}",
            f"entrypoint: {__file__}",
            f"project root: {ROOT}",
            "sys.path:",
            *[f"  {p}" for p in sys.path],
        ]
        if ROOT.exists():
            lines.append(f"root contents: {sorted(p.name for p in ROOT.iterdir())}")
        package_dir = ROOT / "onepager"
        if package_dir.exists():
            lines.append(
                f"onepager contents: {sorted(p.name for p in package_dir.iterdir())}"
            )
        else:
            lines.append("onepager package directory MISSING from bundle")
        return "\n".join(lines)

    async def asgi(scope, receive, send):
        if scope["type"] != "http":
            return
        await send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [(b"content-type", b"text/plain; charset=utf-8")],
            }
        )
        await send({"type": "http.response.body", "body": _report().encode("utf-8")})

    return asgi


def _load_app():
    try:
        from onepager.web import app as fastapi_app

        return fastapi_app
    except Exception:  # pragma: no cover - serverless bootstrap diagnostics
        import traceback

        return _diagnostic_app(traceback.format_exc())


app = _load_app()
