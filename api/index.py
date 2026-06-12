"""Vercel entrypoint: exposes the FastAPI app as an ASGI function.

All non-/api routes are rewritten here (see vercel.json), so the builder UI,
/example, /parse-captable, and /generate are served by this function. PDF
printing happens in api/pdf.js because WeasyPrint's native libraries are not
available in the serverless Python runtime — /generate detects that and
returns self-contained HTML instead.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from onepager.web import app  # noqa: E402, F401
