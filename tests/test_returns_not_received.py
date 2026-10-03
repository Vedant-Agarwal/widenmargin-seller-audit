"""Ported from fba-returns/reconcile.test.ts, plus multiple settlement files and the CLI."""
import json

import wm_audit_core as core
from conftest import FX, fixture_text, load_script

RN = load_script("returns-not-received", "returns_not_received")
TODAY = "2026-09-24"


def main_result():
    s = core.parse_settlement_report(fixture_text("settlement_returns.tsv"))
    r = core.parse_customer_returns(fixture_text("returns.tsv"))
    m = core.parse_reimbursements(fixture_text("reimb_returns.tsv"))
    assert s["ok"] and r["ok"] and m["ok"]
    return r, m, core.find_unreturned_refunds(s["rows"], r["rows"], m["rows"], today=TODAY)


def test_reads_returns_report_and_reimbursement_order_id():
    r, m, _ = main_result()
    assert (r["rows"][0]["order_id"], r["rows"][0]["sku"], r["rows"][0]["quantity"]) == ("O-2", "MAT", 1)
    assert m["rows"][0]["amazon_order_id"] == "O-3"


def test_finds_fba_refunds_never_returned_nor_reimbursed():
    _, _, res = main_result()
    assert [c["order_id"] for c in res["cases"]] == ["O-1", "O-4", "O-5"]
    c = res["cases"][0]
    assert (c["status"], c["missing_units"], c["refunded_principal"], c["days_since_refund"]) == ("claim-now", 1, 20, 90)


def test_window_wait_before_60_too_late_after_120():
    _, _, res = main_result()
    o4 = next(c for c in res["cases"] if c["order_id"] == "O-4")
    assert (o4["status"], o4["claimable_from"]) == ("wait", "2026-11-03")
    assert next(c for c in res["cases"] if c["order_id"] == "O-5")["status"] == "too-late"


def test_skips_returned_reimbursed_and_mfn():
    _, _, res = main_result()
    assert (res["refunded_lines"], res["returned_lines"], res["reimbursed_lines"], res["mfn_skipped"]) == (5, 1, 1, 1)
    assert (res["claim_now"], res["waiting"], res["too_late"]) == (1, 1, 1)


def test_rejects_non_returns_file():
    assert not core.parse_customer_returns("name,value\nx,1")["ok"]


def _o9(reimb_fixture):
    s = core.parse_settlement_report(fixture_text("settlement_o9.tsv"))
    m = core.parse_reimbursements(fixture_text(reimb_fixture))
    return core.find_unreturned_refunds(s["rows"], [], m["rows"], today=TODAY)


def test_fee_line_does_not_clear_a_return():
    assert [c["order_id"] for c in _o9("reimb_o9_fee.tsv")["cases"]] == ["O-9"]


def test_customer_return_reimbursement_clears_and_its_reversal_reopens():
    assert _o9("reimb_o9_customer.tsv")["cases"] == []
    assert [c["order_id"] for c in _o9("reimb_o9_reversed.tsv")["cases"]] == ["O-9"]


def test_day_boundaries():
    s = core.parse_settlement_report(fixture_text("settlement_o9.tsv"))  # refund 2026-06-26
    st = lambda today: core.find_unreturned_refunds(s["rows"], [], [], today=today)["cases"][0]["status"]  # noqa: E731
    assert st("2026-08-24") == "wait"        # day 59
    assert st("2026-08-25") == "claim-now"   # day 60
    assert st("2026-10-24") == "claim-now"   # day 120
    assert st("2026-10-25") == "too-late"    # day 121


def test_multiple_settlement_files_combined_same_as_one():
    one = RN.run([("all", fixture_text("settlement_returns.tsv"))], fixture_text("returns.tsv"), fixture_text("reimb_returns.tsv"), today=TODAY)
    two = RN.run([("p1", fixture_text("settlement_part1.tsv")), ("p2", fixture_text("settlement_part2.tsv"))],
                 fixture_text("returns.tsv"), fixture_text("reimb_returns.tsv"), today=TODAY)
    strip = lambda cases: [{k: v for k, v in c.items() if k != "settlement_ids"} for c in cases]  # noqa: E731
    assert strip(one["result"]["cases"]) == strip(two["result"]["cases"])
    assert len(two["settlement_files"]) == 2
    assert next(c for c in two["result"]["cases"] if c["order_id"] == "O-4")["settlement_ids"] == ["S2"]


def test_cli_markdown_and_draft(capsys):
    rc = RN.main(["--settlement", FX + "/settlement_part1.tsv", FX + "/settlement_part2.tsv", "--returns", FX + "/returns.tsv",
                  "--reimbursements", FX + "/reimb_returns.tsv", "--today", TODAY])
    md = capsys.readouterr().out
    assert rc == 0
    assert md.count("Subject: Refunded FBA order") == 1 and "O-1" in md
    assert "adjustment ID A1" in md
    assert "Seller-fulfilled (MFN) refunds skipped: 1" in md
    assert "worth checking" in md and "day 60 to day 120" in md


def test_cli_bad_settlement_file(capsys):
    assert RN.main(["--settlement", FX + "/settlement_v1.tsv", "--returns", FX + "/returns.tsv"]) == 2
    assert "Flat File V2" in capsys.readouterr().err


def test_cli_json(capsys):
    assert RN.main(["--settlement", FX + "/settlement_returns.tsv", "--returns", FX + "/returns.tsv", "--today", TODAY, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["reimbursements"] is None
    assert [c["order_id"] for c in data["result"]["cases"]] == ["O-3", "O-1", "O-4", "O-5"]  # without reimbursements, O-3 stays (claim-now, oldest first)
