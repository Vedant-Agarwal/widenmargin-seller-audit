#!/usr/bin/env python3
"""
ledger-audit: FBA units lost or damaged in a fulfillment center that do not show a matching
warehouse reimbursement, with each remaining unit dated against the 60-day claim window.

Usage:
  python3 ledger_audit.py LEDGER_FILE [--reimbursements FILE] [--unit-cost 6.50] [--today YYYY-MM-DD] [--json]

Inputs are the seller's own Seller Central downloads (tab- or comma-separated). Nothing is sent
anywhere: this script only reads the files named on the command line and prints a report.
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wm_audit_core as core  # noqa: E402

FACTS_AS_OF = "2026-10-03"


def run(ledger_text, reimb_text=None, unit_cost=None, today=None, closing_days=45, expired_days=60):
    """Pure entry point used by the CLI and the tests. Returns a dict (ok False on a bad file)."""
    ledger = core.parse_inventory_ledger(ledger_text)
    if not ledger["ok"]:
        return {"ok": False, "file": "ledger", "message": ledger["message"], "found_columns": ledger["found_columns"]}
    reimb = None
    reimbursed = []
    reimb_breakdown = None
    if reimb_text is not None:
        reimb = core.parse_reimbursements(reimb_text)
        if not reimb["ok"]:
            return {"ok": False, "file": "reimbursements", "message": reimb["message"], "found_columns": reimb["found_columns"]}
        reimbursed = core.reimbursed_units_for_recovery(reimb["rows"])
        reimb_breakdown = core.classify_reimbursement_rows_for_recovery(reimb["rows"])
    unit_costs = {}
    if unit_cost is not None and unit_cost > 0:
        for loss in ledger["losses"]:
            unit_costs[loss["sku"]] = unit_cost
    result = core.reconcile(ledger["losses"], reimbursed, unit_costs=unit_costs, today=today,
                            closing_days=closing_days, expired_days=expired_days)
    return {
        "ok": True,
        "ledger": {k: ledger[k] for k in ("delimiter", "headers", "reasons", "event_types", "found_units_offset",
                                          "check_units", "unreconciled_units", "warnings", "data_rows", "loss_date_range")},
        "reimbursements": None if reimb is None else {
            "delimiter": reimb["delimiter"], "rows": reimb["summary"]["row_count"],
            "date_from": reimb["summary"]["date_from"], "date_to": reimb["summary"]["date_to"],
            "warnings": reimb["summary"]["warnings"], "read_as": reimb_breakdown,
            "warehouse_units_by_sku": reimbursed,
        },
        "unit_cost": unit_cost if unit_cost and unit_cost > 0 else None,
        "result": result,
        "claimable_units_total": sum(c["claimable_units"] for c in result["cases"]),
    }


def draft_message(case, have_reimb):
    inside = [e for e in case["remaining_events"] if e["inside_window"]]
    lines = []
    lines.append("Subject: Please review FBA units recorded lost/damaged in a fulfillment center — SKU %s" % case["sku"])
    lines.append("")
    lines.append("Hello,")
    lines.append("")
    if have_reimb:
        lines.append("Our FBA Inventory Ledger (Detailed view) shows the units below recorded as lost or damaged inside an "
                     "Amazon fulfillment center. We could not find a matching Lost_Warehouse or Damaged_Warehouse "
                     "reimbursement for them in our Reimbursements report. Could you please check whether these units "
                     "were found or reimbursed and, if not, review them for reimbursement under the FBA inventory "
                     "reimbursement policy?")
    else:
        lines.append("Our FBA Inventory Ledger (Detailed view) shows the units below recorded as lost or damaged inside an "
                     "Amazon fulfillment center. Could you please check whether these units were found or reimbursed and, "
                     "if not, review them for reimbursement under the FBA inventory reimbursement policy?")
    lines.append("")
    lines.append("Item")
    lines.append("- SKU: %s" % case["sku"])
    lines.append("- FNSKU: %s" % (case["fnsku"] or "(not in file)"))
    lines.append("- ASIN: %s" % (case["asin"] or "(not in file)"))
    if case["product_name"]:
        lines.append("- Title: %s" % case["product_name"])
    lines.append("")
    lines.append("Inventory Ledger events (date / fulfillment center / reference ID / reason / units)")
    for e in inside:
        lines.append("- %s / %s / %s / %s / %d" % (e["date"] or "(no date)", e["fulfillment_center"] or "(not in file)",
                                                   e["reference_id"] or "(not in file)", e["reason"], e["units"]))
    lines.append("")
    lines.append("Units in question: %d" % case["claimable_units"])
    lines.append("")
    lines.append("Thank you.")
    return "\n".join(lines)


def render_markdown(out, names):
    r = out["result"]
    L = out["ledger"]
    cases = r["cases"]
    have_reimb = out["reimbursements"] is not None
    md = []
    md.append("# FBA lost & damaged inventory check")
    md.append("")
    files = "Ledger: `%s` (%s-separated, %d data rows)" % (names.get("ledger", "ledger"), L["delimiter"], L["data_rows"])
    if have_reimb:
        R = out["reimbursements"]
        files += " · Reimbursements: `%s` (%d rows, approval dates %s to %s)" % (
            names.get("reimbursements", "reimbursements"), R["rows"], R["date_from"] or "?", R["date_to"] or "?")
    else:
        files += " · Reimbursements: **not provided** (nothing subtracted as already reimbursed, so figures are an upper bound)"
    md.append(files)
    md.append("")
    md.append("Checked as of **%s**. Window: each unit is dated from its own ledger event; inside %d days = still claimable, "
              "\"closing\" from day %d." % (r["today"], r["expired_days"], r["closing_days"]))
    md.append("")
    md.append("## Summary")
    md.append("")
    md.append("- Lost/damaged units without a matching warehouse reimbursement: **%d units** across %d SKU%s" % (
        r["total_recoverable_units"], len(cases), "" if len(cases) == 1 else "s"))
    md.append("- Of those, still inside the %d-day window: **%d units**" % (r["expired_days"], out["claimable_units_total"]))
    md.append("- SKUs by window status: open %d · closing %d · past %d days %d" % (
        r["open_count"], r["closing_count"], r["expired_days"], r["expired_count"]))
    md.append("- Units removed (lost + warehouse-damaged, after netting found units): %d · warehouse units already reimbursed: %d" % (
        r["total_removed_units"], r["total_reimbursed_units"]))
    if out["unit_cost"]:
        md.append("- Rough value at your average cost of %s/unit: %s — your number × units, not what Amazon will reimburse "
                  "(Amazon uses its own valuation)" % (core.fmt_money(out["unit_cost"]), core.fmt_money(r["total_est_value"])))
    md.append("- Found units (F/N) netted against earlier losses of the same SKU: %d" % L["found_units_offset"])
    md.append("- Carrier-damaged (6) and disposed (D) units shown for review but never counted: %d" % L["check_units"])
    if L["unreconciled_units"] is not None:
        md.append("- \"Unreconciled Quantity\" column total in your ledger: %d" % L["unreconciled_units"])
    md.append("")
    md.append("## How your ledger was read")
    md.append("")
    md.append("Every reason code in the file, what Amazon's code means, and what this check did with it. "
              "Please confirm this matches your file before relying on any number below.")
    md.append("")
    md.append(core.md_table(["Reason", "Meaning", "Treatment", "Rows", "Units"],
                            [[x["reason"], x["meaning"], core.TREATMENT_LABEL[x["treatment"]], x["rows"], x["units"]] for x in L["reasons"]]))
    md.append("")
    md.append(core.md_table(["Event type", "Rows", "Units"], [[x["type"], x["rows"], x["units"]] for x in L["event_types"]]))
    md.append("")
    if have_reimb:
        md.append("## How your reimbursements file was read")
        md.append("")
        md.append("Only Lost_Warehouse / Damaged_Warehouse lines (and reversals of those) offset warehouse losses. Outbound, "
                  "inbound, customer-return and fee lines are a different event and are not subtracted.")
        md.append("")
        md.append(core.md_table(["Reason", "Counted against warehouse losses?", "Rows", "Units"],
                                [[x["reason"], "Yes" if x["counted"] else "No", x["rows"], x["units"]] for x in out["reimbursements"]["read_as"]]))
        md.append("")
    md.append("## SKUs worth checking")
    md.append("")
    if not cases:
        md.append("Nothing to check: every lost or warehouse-damaged unit in this ledger is matched by a warehouse "
                  "reimbursement (or there were none). That is the expected outcome now that Amazon reimburses most "
                  "warehouse losses automatically.")
    else:
        hdr = ["SKU", "FNSKU", "ASIN", "Lost", "Damaged", "Reimbursed", "Not reimbursed", "Inside window", "Oldest remaining", "Status"]
        if out["unit_cost"]:
            hdr.append("Rough value")
        rows = []
        for c in cases:
            row = [c["sku"], c["fnsku"], c["asin"], c["lost_units"], c["damaged_units"], c["reimbursed_units"],
                   c["recoverable_units"], c["claimable_units"], c["oldest_event"],
                   {"open": "Open", "closing": "Closing soon", "expired": "Past %d days" % r["expired_days"]}[c["window_status"]]]
            if out["unit_cost"]:
                row.append(core.fmt_money(c["est_value"]))
            rows.append(row)
        md.append(core.md_table(hdr, rows))
        md.append("")
        md.append("### Each remaining unit against the window")
        md.append("")
        ev_rows = []
        for c in cases:
            for e in c["remaining_events"]:
                ev_rows.append([c["sku"], e["date"], e["reason"], e["units"], e["reference_id"], e["fulfillment_center"], e["age_days"],
                                ("%d days left" % e["days_left"]) if e["inside_window"] else "past %d days" % r["expired_days"]])
        md.append(core.md_table(["SKU", "Ledger date", "Reason", "Units", "Reference ID", "FC", "Age (days)", "Window"], ev_rows))
        md.append("")
    open_cases = [c for c in cases if c["claimable_units"] > 0]
    if open_cases:
        md.append("## Draft case messages (DRAFTS — verify each event in Seller Central before sending)")
        md.append("")
        md.append("One per SKU with units still inside the window. Copy, check, and send only what you have verified.")
        md.append("")
        for c in open_cases:
            md.append("### %s" % c["sku"])
            md.append("")
            md.append("```")
            md.append(draft_message(c, have_reimb))
            md.append("```")
            md.append("")
    warnings = list(L["warnings"]) + (list(out["reimbursements"]["warnings"]) if have_reimb else [])
    if warnings:
        md.append("## Warnings")
        md.append("")
        for w in warnings:
            md.append("- %s" % w)
        md.append("")
    md.append("## Read this before acting")
    md.append("")
    md.append("- These are units **worth checking**, not money Amazon owes. Amazon may have found the units, reimbursed them "
              "under a different SKU/FNSKU, or reimbursed them after the period your reimbursements file covers.")
    md.append("- Dated facts (as of %s; see `references/claim-rules.md` for sources): since 23 Oct 2024 claims for units lost "
              "or damaged in a fulfillment center must be filed within 60 days of the loss being reported (was 18 months); "
              "since 1 Nov 2024 Amazon reimburses most of these automatically; since 31 Mar 2025 such reimbursements are "
              "valued at the item's manufacturing cost." % FACTS_AS_OF)
    md.append("- Reason-code meanings: `references/reason-codes.md`. Not affiliated with Amazon. Not legal or tax advice.")
    return "\n".join(md)


def main(argv=None):
    p = argparse.ArgumentParser(description="FBA lost & damaged inventory check (Inventory Ledger vs Reimbursements).")
    p.add_argument("ledger", help="Inventory Ledger, Detailed view (CSV/TSV/TXT)")
    p.add_argument("--reimbursements", help="Reimbursements report for the same dates (optional)")
    p.add_argument("--unit-cost", type=float, help="Your average cost per unit, for a rough value (optional)")
    p.add_argument("--today", help="Date to measure the window from, YYYY-MM-DD (default: today, UTC)")
    p.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    a = p.parse_args(argv)
    try:
        ledger_text = core.read_text(a.ledger)
        reimb_text = core.read_text(a.reimbursements) if a.reimbursements else None
    except OSError as e:
        print("Could not open a file: %s" % e, file=sys.stderr)
        return 2
    out = run(ledger_text, reimb_text, unit_cost=a.unit_cost, today=a.today)
    if not out["ok"]:
        msg = "%s file: %s" % (out["file"], out["message"])
        if out["found_columns"]:
            msg += " Columns found: %s." % ", ".join(out["found_columns"])
        print(msg, file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        names = {"ledger": os.path.basename(a.ledger)}
        if a.reimbursements:
            names["reimbursements"] = os.path.basename(a.reimbursements)
        print(render_markdown(out, names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
