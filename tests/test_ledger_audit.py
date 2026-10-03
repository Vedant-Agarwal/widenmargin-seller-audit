"""Ported from fba-inventory-ledger/parse.test.ts and fba-recovery/*.test.ts, plus the ledger-audit CLI."""
import json

import wm_audit_core as core
from conftest import FX, fixture_text, load_script

LA = load_script("ledger-audit", "ledger_audit")


def real():
    res = core.parse_inventory_ledger(fixture_text("ledger_real.tsv"))
    assert res["ok"], res
    return res


# ---------------------------------------------------------------- parse: real format with reason codes
def test_reads_real_headers():
    res = real()
    assert res["delimiter"] == "tab"
    assert "Unreconciled Quantity" in res["headers"]


def test_found_units_net_oldest_loss_across_year_boundary():
    res = real()
    a_lost = [l for l in res["losses"] if l["sku"] == "A" and l["category"] == "lost"]
    assert len(a_lost) == 1
    assert a_lost[0]["units"] == 3
    assert a_lost[0]["date"] == "2026-01-10"  # the 12/15/2025 loss was the one cancelled by F
    assert res["found_units_offset"] == 2


def test_warehouse_damage_counted_once_p_readd_ignored():
    res = real()
    a_dmg = [l for l in res["losses"] if l["sku"] == "A" and l["category"] == "damaged"]
    assert len(a_dmg) == 1 and a_dmg[0]["units"] == 1


def test_never_claims_customer_damage_disposition_changes_or_unknown_codes():
    res = real()
    b = [l for l in res["losses"] if l["sku"] == "B"]
    assert len(b) == 1
    assert b[0]["category"] == "lost" and b[0]["units"] == 4
    assert "not recognised" in " ".join(res["warnings"])


def test_carrier_damaged_and_disposed_are_check_only():
    res = real()
    assert res["check_units"] == 3
    assert next(r for r in res["reasons"] if r["reason"] == "6")["treatment"] == "check"


def test_reason_breakdown_and_unreconciled_total():
    res = real()
    m = next(r for r in res["reasons"] if r["reason"] == "M")
    assert (m["treatment"], m["rows"], m["units"]) == ("lost", 2, 5)
    assert next(r for r in res["reasons"] if r["reason"] == "P")["treatment"] == "ignored"
    assert res["unreconciled_units"] == 3


def test_feeds_recovery_engine_end_to_end():
    res = real()
    r = core.reconcile(res["losses"], [{"sku": "B", "units": 1, "amount": 9}], today="2026-03-01")
    by = {c["sku"]: c for c in r["cases"]}
    assert by["A"]["recoverable_units"] == 4  # 3 lost + 1 damaged
    assert by["B"]["recoverable_units"] == 3  # 4 lost - 1 reimbursed
    assert r["total_recoverable_units"] == 7
    assert by["A"]["oldest_event"] == "2026-01-10"


def test_reference_ids_and_fc_carried_for_drafts():
    res = real()
    a = next(l for l in res["losses"] if l["sku"] == "A" and l["category"] == "lost")
    assert a["reference_id"] == "R1" and a["fulfillment_center"] == "PHX6" and a["reason_code"] == "M"


def test_free_text_reasons_fallback():
    res = core.parse_inventory_ledger(fixture_text("ledger_freetext.tsv"))
    assert res["ok"]
    a = next(l for l in res["losses"] if l["sku"] == "SKU-A")
    assert (a["category"], a["units"]) == ("lost", 2)
    b = [l for l in res["losses"] if l["sku"] == "SKU-B"]
    assert len(b) == 1 and (b[0]["category"], b[0]["units"]) == ("damaged", 2)
    assert res["check_units"] == 1


def test_helpers():
    assert core.to_iso_date("", "01/10/2026") == "2026-01-10"
    assert core.to_iso_date("", "1/5/26") == "2026-01-05"
    assert core.to_iso_date("2026-01-10T08:15:00-08:00", "01/10/2026") == "2026-01-10"
    assert core.to_iso_date("", "12/31/2025") == "2025-12-31"
    assert core.classify("Adjustments", "M", -1)["treatment"] == "lost"
    assert core.classify("Adjustments", "m", -1)["treatment"] == "lost"
    assert core.classify("Adjustments", "H", -1)["treatment"] == "ignored"
    assert core.classify("Adjustments", "Z", -1)["meaning"] == "Unrecognised reason"


def test_rejects_non_ledger():
    res = core.parse_inventory_ledger("name,value\nfoo,1")
    assert not res["ok"] and "event-type" in res["missing_columns"]


# ---------------------------------------------------------------- recovery engine (reconcile.test.ts)
def cases():
    return json.load(open(FX + "/reconcile_cases.json"))


def test_reconcile_main():
    c = cases()["main"]
    r = core.reconcile(c["losses"], c["reimbursed"], unit_costs=c["unit_costs"], today=c["today"])
    skus = [x["sku"] for x in r["cases"]]
    assert "SKU-A" in skus and "SKU-C" in skus and "SKU-D" in skus and "SKU-B" not in skus
    a = next(x for x in r["cases"] if x["sku"] == "SKU-A")
    assert (a["removed_units"], a["reimbursed_units"], a["recoverable_units"], a["est_value"]) == (10, 4, 6, 48)
    assert (r["total_removed_units"], r["total_reimbursed_units"], r["total_recoverable_units"], r["total_est_value"]) == (17, 8, 9, 58)
    st = {x["sku"]: x["window_status"] for x in r["cases"]}
    assert st == {"SKU-A": "open", "SKU-C": "closing", "SKU-D": "expired"}
    assert (r["open_count"], r["closing_count"], r["expired_count"]) == (1, 1, 1)
    assert [x["sku"] for x in r["cases"]][:2] == ["SKU-A", "SKU-C"]
    r2 = core.reconcile(c["losses"], c["reimbursed"], today=c["today"])
    assert r2["total_est_value"] is None and r2["total_recoverable_units"] == 9


def test_reconcile_per_unit_window():
    c = cases()
    r = core.reconcile(c["old_hides_recent"]["losses"], [], today="2026-09-24")
    assert (r["cases"][0]["recoverable_units"], r["cases"][0]["claimable_units"], r["cases"][0]["window_status"]) == (3, 1, "open")
    r = core.reconcile(c["fifo"]["losses"], c["fifo"]["reimbursed"], today="2026-09-24")
    x = r["cases"][0]
    assert (x["recoverable_units"], x["claimable_units"], x["window_status"], x["oldest_event"]) == (1, 1, "open", "2026-09-01")
    assert core.reconcile(c["closing"]["losses"], [], today="2026-09-24")["cases"][0]["window_status"] == "closing"
    e = core.reconcile(c["expired"]["losses"], [], today="2026-09-24")["cases"][0]
    assert (e["window_status"], e["claimable_units"]) == ("expired", 0)


def test_reconcile_window_boundaries_day_45_and_60():
    c = cases()["boundary_day_45_and_60"]
    st = {x["sku"]: x["window_status"] for x in core.reconcile(c["losses"], [], today=c["today"])["cases"]}
    assert st == {"D45": "closing", "D44": "open", "D60": "expired", "D59": "closing"}


# ---------------------------------------------------------------- which reimbursements offset (from-reimbursements.test.ts)
def units(name):
    res = core.parse_reimbursements(fixture_text(name))
    assert res["ok"]
    return {r["sku"]: r["units"] for r in core.reimbursed_units_for_recovery(res["rows"])}


def test_warehouse_lines_net_of_their_reversals_only():
    u = units("reimb_recovery_mixed.tsv")
    assert u["A"] == 2 and u["B"] == 1


def test_outbound_reimbursements_do_not_offset():
    assert units("reimb_recovery_outbound.tsv")["A"] == 1


def test_customer_return_reversal_and_unknown_original_ignored():
    assert units("reimb_recovery_reversals.tsv")["A"] == 2


def test_warehouse_reason_spellings():
    for r in ["Lost_Warehouse", "Damaged_Warehouse", "Lost:Warehouse", "damaged warehouse"]:
        assert core.is_warehouse_loss_reason(r)
    for r in ["Lost_Outbound", "Damaged_Inbound", "CustomerReturn", "FeeCorrection", ""]:
        assert not core.is_warehouse_loss_reason(r)


# ---------------------------------------------------------------- the skill script
def test_cli_run_demo():
    out = LA.run(fixture_text("demo_ledger.csv"), fixture_text("demo_reimbursements.tsv"), unit_cost=6.5, today="2026-10-03")
    assert out["ok"]
    r = out["result"]
    by = {c["sku"]: c for c in r["cases"]}
    assert by["MUG-BLUE"]["recoverable_units"] == 3 and by["MUG-BLUE"]["window_status"] == "open"
    assert by["MAT-GREY"]["window_status"] == "closing"
    assert by["BOT-500"]["claimable_units"] == 4  # Lost_Outbound does not offset
    assert by["LAMP-01"]["window_status"] == "expired"
    assert out["claimable_units_total"] == 8
    assert r["total_est_value"] == 58.5


def test_cli_markdown_has_breakdown_drafts_and_framing(capsys):
    rc = LA.main([FX + "/demo_ledger.csv", "--reimbursements", FX + "/demo_reimbursements.tsv", "--today", "2026-10-03"])
    md = capsys.readouterr().out
    assert rc == 0
    assert "How your ledger was read" in md and "How your reimbursements file was read" in md
    assert md.count("Subject: Please review FBA units") == 3  # BOT-500, MUG-BLUE, MAT-GREY (LAMP-01 expired)
    assert "9876543311" in md and "X00MUG01" in md  # reference ID + FNSKU in the draft
    assert "worth checking" in md and "owes you" not in md.lower()
    assert "1 Nov 2024" in md and "23 Oct 2024" in md


def test_cli_without_reimbursements_is_upper_bound(capsys):
    assert LA.main([FX + "/ledger_real.tsv", "--today", "2026-03-01"]) == 0
    md = capsys.readouterr().out
    assert "not provided" in md and "upper bound" in md


def test_cli_rejects_wrong_file(capsys):
    assert LA.main([FX + "/not_a_report.csv"]) == 2
    assert "does not look like an Amazon FBA inventory ledger" in capsys.readouterr().err


def test_cli_json(capsys):
    assert LA.main([FX + "/ledger_real.tsv", "--today", "2026-03-01", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["result"]["total_recoverable_units"] == 8  # no reimbursements file: A 4 + B 4
