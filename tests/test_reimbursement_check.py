"""Ported from fba-reimbursements/parse.test.ts, plus the reimbursement-check CLI."""
import json

import pytest

import wm_audit_core as core
from conftest import FX, fixture_text, load_script

RC = load_script("reimbursement-check", "reimbursement_check")


def test_parses_tsv_and_totals():
    res = core.parse_reimbursements(fixture_text("reimb_full.tsv"))
    assert res["ok"] and res["delimiter"] == "tab"
    s = res["summary"]
    assert s["row_count"] == 5 and s["currency"] == "USD"
    assert s["total_amount"] == pytest.approx(37.2)
    assert s["reimbursed_amount"] == pytest.approx(49.7)
    assert s["reversal_amount"] == pytest.approx(-12.5)
    assert s["reversal_count"] == 1 and s["units"] == 3
    assert (s["date_from"], s["date_to"]) == ("2026-03-02", "2026-03-14")


def test_reversal_flagged_by_original_id():
    res = core.parse_reimbursements(fixture_text("reimb_full.tsv"))
    assert next(r for r in res["rows"] if r["reimbursement_id"] == "R5")["is_reversal"]


def test_by_reason_nets_reversal():
    s = core.parse_reimbursements(fixture_text("reimb_full.tsv"))["summary"]
    lost = next(r for r in s["by_reason"] if r["reason"] == "Lost:Warehouse")
    assert lost["amount"] == pytest.approx(0) and lost["count"] == 2
    assert next(r for r in s["by_reason"] if r["reason"] == "Damaged:Warehouse")["amount"] == pytest.approx(25)


def test_by_sku_sorted_with_asin():
    s = core.parse_reimbursements(fixture_text("reimb_full.tsv"))["summary"]
    assert s["by_sku"][0]["sku"] == "SKU-DMG" and s["by_sku"][0]["amount"] == pytest.approx(28.2) and s["by_sku"][0]["asin"] == "B002"
    assert next(x for x in s["by_sku"] if x["sku"] == "SKU-LOST")["amount"] == pytest.approx(9)


def test_rejects_other_file_and_accepts_csv():
    bad = core.parse_reimbursements(fixture_text("not_a_report.csv"))
    assert not bad["ok"] and "reimbursement-id" in bad["missing_columns"]
    csv = core.parse_reimbursements(fixture_text("reimb_full.csv"))
    assert csv["ok"] and csv["delimiter"] == "comma" and csv["summary"]["total_amount"] == pytest.approx(37.2)


def test_short_pay_flags_against_unit_cost():
    out = RC.run(fixture_text("demo_reimbursements.tsv"), unit_cost=6.5, sku_costs={"MAT-GREY": 8})
    sp = out["short_pay"]
    ids = {x["reimbursement_id"]: x for x in sp["lines"]}
    assert set(ids) == {"5550001", "5550002", "5550004"}  # 5550003 is 9.00 >= 6.50; reversal skipped
    assert ids["5550001"]["your_cost"] == 8 and ids["5550001"]["shortfall"] == 0.9
    assert ids["5550002"]["per_unit"] == 3.4 and ids["5550002"]["later_reversed"]
    assert ids["5550004"]["inventory_reason"] is False
    assert sp["total_shortfall"] == 9.6 and sp["checked_lines"] == 4


def test_no_cost_no_short_pay_section():
    assert RC.run(fixture_text("reimb_full.tsv"))["short_pay"] is None


def test_reversals_list_original_in_file_or_not():
    out = RC.run(fixture_text("reimb_recovery_reversals.tsv"))
    rv = {x["reimbursement_id"]: x for x in out["reversals"]}
    assert rv["R3"]["original_in_file"] and rv["R3"]["original_reason"] == "CustomerReturn"
    assert not rv["R4"]["original_in_file"]


def test_ledger_match():
    out = RC.run(fixture_text("demo_reimbursements.tsv"), fixture_text("demo_ledger.csv"))
    rows = {x["sku"]: x for x in out["ledger_match"]["rows"]}
    assert rows["MUG-BLUE"]["ledger_lost"] == 4 and rows["MUG-BLUE"]["warehouse_units_reimbursed"] == 1
    assert rows["MUG-BLUE"]["reimbursement_ids"] == ["5550002", "5550005"] and rows["MUG-BLUE"]["not_reimbursed"] == 3
    assert rows["MAT-GREY"]["warehouse_units_reimbursed"] == 1 and rows["MAT-GREY"]["not_reimbursed"] == 1
    assert rows["BOT-500"]["warehouse_units_reimbursed"] == 0  # Lost_Outbound is not a warehouse loss


def test_ledger_match_reimbursed_beyond_ledger():
    out = RC.run(fixture_text("reimb_recovery_mixed.tsv"), fixture_text("ledger_real.tsv"))
    rows = {x["sku"]: x for x in out["ledger_match"]["rows"]}
    assert rows["A"]["ledger_lost"] == 3 and rows["A"]["ledger_damaged"] == 1 and rows["A"]["warehouse_units_reimbursed"] == 2
    assert rows["B"]["warehouse_units_reimbursed"] == 1


def test_cli_markdown(capsys):
    rc = RC.main([FX + "/demo_reimbursements.tsv", "--ledger", FX + "/demo_ledger.csv", "--unit-cost", "6.5", "--sku-cost", "MAT-GREY=8"])
    md = capsys.readouterr().out
    assert rc == 0
    for h in ["Totals", "By reason", "By SKU", "Reversals", "below your unit cost", "vs Inventory Ledger losses"]:
        assert h in md
    assert "does not mean Amazon owes" in md


def test_cli_bad_sku_cost(capsys):
    assert RC.main([FX + "/reimb_full.tsv", "--sku-cost", "nope"]) == 2


def test_cli_json(capsys):
    assert RC.main([FX + "/reimb_full.tsv", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["summary"]["row_count"] == 5
