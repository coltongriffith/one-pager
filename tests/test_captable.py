"""Cap table parser tests across pasted text, csv, xlsx, and pdf inputs."""

import io

import pytest

from onepager.captable import parse_captable, parse_text, parse_value

PASTED = """Capitalization Table
Common Shares Issued and Outstanding\t92,450,000
Stock Options    6,150,000
Warrants: 14,200,000
Fully Diluted Shares 112,800,000
Closing Price $0.62
Market Capitalization $57.3M
52-Week Range $0.31 - $0.88
Cash Position $11.4 million
Insider Ownership 21%
Escrowed Shares 2,000,000
"""


def test_parse_pasted_text():
    result = parse_text(PASTED)
    assert result["shares_outstanding"] == 92450000
    assert result["options"] == 6150000
    assert result["warrants"] == 14200000
    assert result["fully_diluted"] == 112800000
    assert result["share_price"] == 0.62
    assert result["market_cap"] == 57300000
    assert result["week52_range"] == "$0.31 - $0.88"
    assert result["cash_position"] == 11400000
    assert result["insider_ownership"] == "21%"
    assert result["_unmatched"][0]["label"] == "Escrowed Shares"


def test_parse_csv():
    data = b'Shares Outstanding,"92,450,000"\nWarrants,14200000\n'
    result = parse_captable(data, "cap.csv")
    assert result["shares_outstanding"] == 92450000
    assert result["warrants"] == 14200000


def test_parse_xlsx():
    openpyxl = pytest.importorskip("openpyxl")
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(("Common shares outstanding", 92450000))
    sheet.append(("Share price", 0.62))
    buffer = io.BytesIO()
    workbook.save(buffer)
    result = parse_captable(buffer.getvalue(), "cap.xlsx")
    assert result["shares_outstanding"] == 92450000
    assert result["share_price"] == 0.62


def test_parse_pdf():
    pytest.importorskip("pypdf")
    from weasyprint import HTML

    pdf = HTML(string="<pre>Shares Outstanding   92,450,000\nWarrants   14,200,000</pre>").write_pdf()
    result = parse_captable(pdf, "cap.pdf")
    assert result["shares_outstanding"] == 92450000
    assert result["warrants"] == 14200000


def test_parse_value_suffixes():
    assert parse_value("$57.3M") == 57300000
    assert parse_value("1.2 billion") == 1200000000
    assert parse_value("21%") == "21%"
    assert parse_value("92,450,000") == 92450000
