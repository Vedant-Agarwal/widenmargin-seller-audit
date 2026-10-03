"""Ported from settlement-report/parse.test.ts (CSV primitives + Flat File V2 parser)."""
import pytest

import wm_audit_core as core
from conftest import fixture_text


@pytest.mark.parametrize("raw,expected", [
    ("1234.56", 1234.56), ("-1234.56", -1234.56), ("-1,234.56", -1234.56), ("(1,234.56)", -1234.56),
    ("₹1,234.56", 1234.56), ("$1,234.56", 1234.56), ("  -0.01 ", -0.01), ("+12", 12), ('"-9.99"', -9.99),
    ("1 234.56", 1234.56), ("1 234.56", 1234.56), ("USD 5.00", 5.0),
])
def test_parse_amount_reads_real_shapes(raw, expected):
    assert core.parse_amount(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", None, "n/a", "--5", "."])
def test_parse_amount_none_not_zero(raw):
    assert core.parse_amount(raw) is None


@pytest.mark.parametrize("raw", ["settlement-id", "Settlement ID", "settlement_id", " SETTLEMENT-ID ", '"settlement-id"', "﻿settlement-id"])
def test_normalise_column(raw):
    assert core.normalise_column(raw) == "settlement-id"


def test_split_records_quoting():
    recs = core.split_records('a,"b,c","line\nbreak","say ""hi"""\n', ",")
    assert len(recs) == 1
    assert recs[0][0] == ["a", "b,c", "line\nbreak", 'say "hi"']


def test_split_records_blank_lines_crlf_and_line_numbers():
    assert [r[0] for r in core.split_records("a\tb\r\n\r\nc\td\r\n", "\t")] == [["a", "b"], ["c", "d"]]
    assert [r[1] for r in core.split_records("a\tb\n\nc\td\n", "\t")] == [1, 3]


def test_split_records_limit_matches_full_split():
    text = "\n".join("r%d\t%d" % (i, i) for i in range(100))
    assert core.split_records(text, "\t", limit=40) == core.split_records(text, "\t")[:40]


def test_settlement_awkward_bom_preamble_carry_forward():
    res = core.parse_settlement_report(fixture_text("settlement_in_awkward.tsv"))
    assert res["ok"]
    assert res["headers"][0] == "settlement-id"
    assert len(res["rows"]) == 4
    assert all(r["settlement_id"] == "9001" for r in res["rows"])
    assert all(r["currency"] == "INR" for r in res["rows"])
    assert [r["amount"] for r in res["rows"]] == [None, 1000, -90, -250]
    assert res["marketplace"] == "in"


def test_settlement_us_quoted_csv():
    res = core.parse_settlement_report(fixture_text("settlement_us_quoted.csv"))
    assert res["ok"] and res["delimiter"] == "comma" and res["marketplace"] == "us"
    assert [r["sku"] for r in res["rows"]] == ["", "BOTTLE, 750ml", "BOTTLE, 750ml", ""]
    assert res["rows"][3]["amount_description"] == 'Storage Fee "August"'


def test_settlement_turns_down_other_files():
    res = core.parse_settlement_report(fixture_text("not_a_report.csv"))
    assert not res["ok"]
    for c in core.SETTLEMENT_REQUIRED_COLUMNS:
        assert c in res["message"]
    v1 = core.parse_settlement_report(fixture_text("settlement_v1.tsv"))
    assert not v1["ok"] and "Flat File V1" in v1["message"] and "Flat File V2" in v1["message"]
    assert "amount-type" in v1["missing_columns"] and "settlement-id" in v1["found_columns"]
    assert not core.parse_settlement_report("")["ok"]
    assert not core.parse_settlement_report("   \n\n ")["ok"]
    hdr = core.parse_settlement_report("settlement-id\tamount-type\tamount-description\tamount\n")
    assert not hdr["ok"] and "no transaction lines" in hdr["message"]


def test_settlement_unparsable_amount_and_no_summary_warnings():
    res = core.parse_settlement_report(fixture_text("settlement_unparsable.tsv"))
    assert res["ok"] and len(res["rows"]) == 2 and res["rows"][1]["amount"] is None
    codes = [w["code"] for w in res["warnings"]]
    assert "unparsable-amount" in codes and "no-summary-row" in codes


def test_settlement_repeated_header_ignored():
    res = core.parse_settlement_report(fixture_text("settlement_concatenated.tsv"))
    assert res["ok"] and len(res["rows"]) == 2
    assert all(r["amount_description"] == "Principal" for r in res["rows"])


def test_js_round_matches_math_round():
    assert [core.js_round(x) for x in (2.5, -2.5, 1.5, -1.5, 0.4, -0.6)] == [3, -2, 2, -1, 0, -1]


def test_read_text_encodings(tmp_path):
    p = tmp_path / "f.txt"
    p.write_bytes("﻿a\tb\n".encode("utf-16"))
    assert core.read_text(str(p)).lstrip("﻿") == "a\tb\n"
    p.write_bytes(b"title\tx\nCaf\xe9\t1\n")  # Windows-1252, not valid UTF-8
    assert "Café" in core.read_text(str(p))
