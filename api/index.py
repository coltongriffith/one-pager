"""Vercel entrypoint: exposes the FastAPI app as an ASGI function.

All non-/api routes are rewritten here (see vercel.json), so the builder UI,
/example, /parse-captable, and /generate are served by this function. PDF
printing happens in api/pdf.js because WeasyPrint's native libraries are not
available in the serverless Python runtime — /generate detects that and
returns self-contained HTML instead.

If the app fails to import, a minimal ASGI app serves the traceback and
environment details so the failure is debuggable from the browser instead of
surfacing as an opaque FUNCTION_INVOCATION_FAILED.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from onepager.web import app  # noqa: F401
except Exception:  # pragma: no cover - serverless bootstrap diagnostics
    import traceback

    _traceback = traceback.format_exc()

    def _environment_report() -> str:
        lines = [
            "onepager failed to start. Startup traceback:",
            "",
            _traceback,
            "-" * 60,
            f"python: {sys.version}",
            f"entrypoint: {__file__}",
            f"project root: {ROOT}",
            "sys.path:",
            *[f"  {p}" for p in sys.path],
            f"root contents: {sorted(p.name for p in ROOT.iterdir())}"
            if ROOT.exists()
            else "root missing",
        ]
        onepager_dir = ROOT / "onepager"
        if onepager_dir.exists():
            lines.append(
                f"onepager contents: {sorted(p.name for p in onepager_dir.iterdir())}"
            )
        else:
            lines.append("onepager package directory MISSING from bundle")
        return "\n".join(lines)

    async def app(scope, receive, send):  # type: ignore[no-redef]
        if scope["type"] != "http":
            return
        body = _environment_report().encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [(b"content-type", b"text/plain; charset=utf-8")],
            }
        )
        await send({"type": "http.response.body", "body": body})
