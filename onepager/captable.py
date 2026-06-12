"""Parse a corporate cap table (xlsx / csv / pdf / pasted text) into share_structure fields.

The parser is heuristic by design: cap tables arrive in countless shapes, so we
scan label/value pairs and map recognizable labels onto the profile's
share_structure keys. Anything we can't confidently map is returned separately
so the UI can show it instead of silently dropping it.
"""

from __future__ import annotations

import csv
import io
import re

# share_structure key -> label patterns (matched against a normalized label)
LABEL_PATTERNS: list[tuple[str, list[str]]] = [
    ("shares_outstanding", [
        r"shares?\s+(issued\s+and\s+)?outstanding", r"\bbasic\s+shares\b",
        r"common\s+shares", r"issued\s+(and|&)\s+outstanding", r"\bshares?\s+issued\b",
        r"outstanding\s+shares",
    ]),
    ("fully_diluted", [r"fully[\s-]*diluted", r"\bdiluted\s+shares?\b", r"\bfd\s+shares?\b"]),
    ("options", [r"\b(stock\s+|incentive\s+)?options\b"]),
    ("warrants", [r"\bwarrants?\b"]),
    ("share_price", [
        r"share\s+price", r"stock\s+price", r"(last|closing|current)\s+price", r"^price$",
    ]),
    ("market_cap", [r"market\s+cap(italization)?"]),
    ("week52_range", [r"52[\s-]*(week|wk)"]),
    ("cash_position", [r"\bcash(\s+(position|balance|on\s+hand))?\b", r"\btreasury\b"]),
    ("insider_ownership", [r"insider", r"management\s+ownership"]),
    ("as_of", [r"\bas\s+(of|at)\b", r"\bdate\b"]),
]

_NUMBER_RE = re.compile(
    r"\$?\s*\(?-?\d[\d,]*(\.\d+)?\)?\s*(%|[KMB]|million|billion|thousand)?",
    re.IGNORECASE,
)
_SUFFIX = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}


def _normalize_label(label: str) -> str:
    label = re.sub(r"\(.*?\)", " ", label)  # drop parentheticals like "(in 000s)"
    label = re.sub(r"[^a-z0-9&\s-]", " ", label.lower())
    return re.sub(r"\s+", " ", label).strip()


def _match_key(label: str) -> str | None:
    normalized = _normalize_label(label)
    if not normalized:
        return None
    for key, patterns in LABEL_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, normalized):
                return key
    return None


def parse_value(raw: str | int | float, key: str | None = None):
    """Turn a raw cell/token into a number where possible, else a cleaned string."""
    if isinstance(raw, (int, float)):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    if key in ("week52_range", "as_of", "insider_ownership"):
        return text
    if "%" in text:
        return text
    # ranges like "$0.31 - $0.88" stay strings
    if re.search(r"\d\s*[–—-]\s*\$?\d", text):
        return text
    match = _NUMBER_RE.fullmatch(text)
    if not match:
        return text
    cleaned = text.replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
    suffix = 1.0
    for token, factor in _SUFFIX.items():
        if cleaned.lower().endswith(token):
            cleaned = cleaned.lower().removesuffix(token).strip()
            suffix = factor
            break
    try:
        value = float(cleaned) * suffix
    except ValueError:
        return text
    return int(value) if value == int(value) else value


def _collect(pairs: list[tuple[str, str | int | float]]) -> dict:
    """Map (label, value) pairs onto share_structure keys."""
    structure: dict = {}
    unmatched: list[dict] = []
    for label, raw in pairs:
        value = parse_value(raw, _match_key(label))
        if value in (None, ""):
            continue
        key = _match_key(label)
        if key and key not in structure:
            structure[key] = value
        elif not key:
            unmatched.append({"label": str(label).strip(), "value": value})
    if unmatched:
        structure["_unmatched"] = unmatched[:8]
    return structure


def parse_text(text: str) -> dict:
    """Parse pasted text or text extracted from a PDF: one label/value per line."""
    pairs = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # split label from trailing value: tabs, 2+ spaces, colon, or last number
        parts = re.split(r"\t+|\s{2,}|:", line, maxsplit=1)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            pairs.append((parts[0], parts[1]))
            continue
        match = re.search(
            r"^(.*?[a-zA-Z)])\s+(\$?\(?-?[\d.,]+\)?\s*(?:%|[KMB]\b|million|billion)?"
            r"(?:\s*[–—-]\s*\$?[\d.,]+)?)\s*$",
            line,
            re.IGNORECASE,
        )
        if match:
            pairs.append((match.group(1), match.group(2)))
    return _collect(pairs)


def parse_csv(data: bytes) -> dict:
    text = data.decode("utf-8-sig", errors="replace")
    dialect = csv.excel
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t")
    except csv.Error:
        pass
    pairs = []
    for row in csv.reader(io.StringIO(text), dialect):
        cells = [c.strip() for c in row if c and c.strip()]
        if len(cells) >= 2:
            pairs.append((cells[0], cells[1]))
    return _collect(pairs)


def parse_xlsx(data: bytes) -> dict:
    from openpyxl import load_workbook

    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    pairs = []
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows(max_row=200, values_only=True):
            cells = [c for c in row if c is not None and str(c).strip() != ""]
            if len(cells) < 2:
                continue
            label = cells[0]
            if not isinstance(label, str):
                continue
            pairs.append((label, cells[1]))
    workbook.close()
    return _collect(pairs)


def parse_pdf(data: bytes) -> dict:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    text = "\n".join(page.extract_text() or "" for page in reader.pages[:5])
    return parse_text(text)


def parse_captable(data: bytes, filename: str = "") -> dict:
    """Dispatch on file extension; falls back to plain-text parsing."""
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix in ("xlsx", "xlsm"):
        return parse_xlsx(data)
    if suffix == "pdf" or data[:5] == b"%PDF-":
        return parse_pdf(data)
    if suffix in ("csv", "tsv"):
        return parse_csv(data)
    return parse_text(data.decode("utf-8", errors="replace"))
