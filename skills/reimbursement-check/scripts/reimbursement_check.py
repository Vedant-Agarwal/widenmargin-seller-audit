#!/usr/bin/env python3
"""
reimbursement-check: what Amazon has already reimbursed, by reason and SKU with reversals
netted; lines reimbursed below the seller's own unit cost; and (with an Inventory Ledger) which
warehouse reimbursements line up with which ledger losses.

Usage:
  python3 reimbursement_check.py REIMBURSEMENTS_FILE [--ledger LEDGER_FILE]
                                 [--unit-cost 6.50] [--sku-cost SKU=COST ...] [--json]

Reads only the files named on the command line; sends nothing anywhere. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wm_audit_core as core  # noqa: E402

FACTS_AS_OF = "2026-10-03"
_INVENTORY_REASON = re.compile(r"(lost|damag).*(warehouse|inbound)|(warehouse|inbound).*(lost|damag)", re.IGNORECASE)


def _cost_for(sku, unit_cost, sku_costs):
    c = sku_costs.get(sku)
    if c is not None and c > 0:
        return c
    if unit_cost is not None and unit_cost > 0:
        return unit_cost
    return None


def run(reimb_text, ledger_text=None, unit_cost=None, sku_costs=None):
    """Pure entry point used by the CLI and tests."""
    sku_costs = sku_costs or {}
    reimb = core.parse_reimbursements(reimb_text)
    if not reimb["ok"]:
        return {"ok": False, "file": "reimbursements", "message": reimb["message"], "found_columns": reimb["found_columns"]}
    rows = reimb["rows"]
    summary = reimb["summary"]
    has_cash_col = "quantity-reimbursed-cash" in reimb["has_columns"]

    # Reversals, and whether the reimbursement each one takes back is in this file.
    by_id = {}
    for r in rows:
        if not r["is_reversal"] and r["reimbursement_id"]:
            by_id.setdefault(r["reimbursement_id"], r)
    reversed_ids = {}
    reversals = []
    for r in rows:
        if not r["is_reversal"]:
            continue
        orig = by_id.get(r["original_reimbursement_id"])
        if r["original_reimbursement_id"]:
            reversed_ids[r["original_reimbursement_id"]] = reversed_ids.get(r["original_reimbursement_id"], 0) + (r["amount_total"] or 0)
        reversals.append({
            "reimbursement_id": r["reimbursement_id"], "approval_date": r["approval_date"], "sku": r["sku"],
            "amount": r["amount_total"], "units": r["quantity_total"],
            "original_reimbursement_id": r["original_reimbursement_id"],
            "original_in_file": orig is not None,
            "original_reason": orig["reason"] if orig is not None else (r["original_reimbursement_type"] or ""),
            "reason": r["reason"],
        })

    # Lines reimbursed below the seller's own unit cost (only when a cost is given).
    short = []
    checked = 0
    if unit_cost or sku_costs:
        for r in rows:
            if r["is_reversal"] or r["amount_total"] is None or r["amount_total"] <= 0:
                continue
            basis = r["quantity_cash"] if has_cash_col else r["quantity_total"]
            if not basis or basis <= 0:
                continue
            key = r["sku"] or r["fnsku"] or r["asin"]
            cost = _cost_for(key, unit_cost, sku_costs)
            if cost is None:
                continue
            checked += 1
            per_unit = r["amount_total"] / basis
            if per_unit + 0.005 < cost:
                short.append({
                    "reimbursement_id": r["reimbursement_id"], "approval_date": r["approval_date"], "sku": key,
                    "reason": r["reason"], "units": basis, "amount_total": r["amount_total"],
                    "per_unit": round(per_unit, 2), "your_cost": cost,
                    "shortfall": round((cost - per_unit) * basis, 2),
                    "inventory_reason": bool(_INVENTORY_REASON.search(r["reason"] or "")),
                    "later_reversed": r["reimbursement_id"] in reversed_ids,
                    "case_id": r["case_id"], "amazon_order_id": r["amazon_order_id"],
                })

    # Which warehouse reimbursements correspond to ledger losses (optional).
    ledger_match = None
    if ledger_text is not None:
        ledger = core.parse_inventory_ledger(ledger_text)
        if not ledger["ok"]:
            return {"ok": False, "file": "ledger", "message": ledger["message"], "found_columns": ledger["found_columns"]}
        warehouse = {w["sku"]: w for w in core.reimbursed_units_for_recovery(rows)}
        per_sku = {}
        for loss in ledger["losses"]:
            a = per_sku.setdefault(loss["sku"], {"sku": loss["sku"], "fnsku": loss["fnsku"], "lost": 0, "damaged": 0,
                                                 "first": loss["date"], "last": loss["date"]})
            a["lost" if loss["category"] == "lost" else "damaged"] += loss["units"]
            if loss["date"] and loss["date"] < a["first"]:
                a["first"] = loss["date"]
            if loss["date"] and loss["date"] > a["last"]:
                a["last"] = loss["date"]
        match_rows = []
        for sku in list(per_sku.keys()) + [s for s in warehouse.keys() if s not in per_sku]:
            a = per_sku.get(sku, {"sku": sku, "fnsku": "", "lost": 0, "damaged": 0, "first": "", "last": ""})
            w = warehouse.get(sku, {"units": 0, "amount": 0, "reimbursement_ids": []})
            ledger_units = a["lost"] + a["damaged"]
            match_rows.append({
                "sku": sku, "fnsku": a["fnsku"], "ledger_lost": a["lost"], "ledger_damaged": a["damaged"],
                "ledger_first": a["first"], "ledger_last": a["last"],
                "warehouse_units_reimbursed": w["units"], "warehouse_amount": w["amount"],
                "reimbursement_ids": w["reimbursement_ids"],
                "not_reimbursed": max(0, ledger_units - w["units"]),
                "reimbursed_beyond_ledger": max(0, w["units"] - ledger_units),
            })
        ledger_match = {"rows": match_rows, "reasons": ledger["reasons"], "warnings": ledger["warnings"],
                        "found_units_offset": ledger["found_units_offset"]}

    return {
        "ok": True,
        "delimiter": reimb["delimiter"],
        "summary": summary,
        "reversals": reversals,
        "short_pay": {"checked_lines": checked, "lines": short,
                      "total_shortfall": round(sum(s["shortfall"] for s in short), 2),
                      "units_basis": "quantity-reimbursed-cash" if has_cash_col else "quantity-reimbursed-total"}
        if (unit_cost or sku_costs) else None,
        "ledger_match": ledger_match,
    }


def _lines(n):
    return "%d line%s" % (n, "" if n == 1 else "s")


def render_markdown(out, names):
    s = out["summary"]
    cur = s["currency"] or "USD"
    m = lambda n: core.fmt_money(n, cur)  # noqa: E731
    md = ["# FBA reimbursements check", ""]
    md.append("Reimbursements: `%s` (%s-separated, %d lines, approval dates %s to %s%s)" % (
        names.get("reimbursements", "reimbursements"), out["delimiter"], s["row_count"], s["date_from"] or "?", s["date_to"] or "?",
        (", currencies: " + ", ".join(s["currencies"])) if len(s["currencies"]) > 1 else ""))
    if out["ledger_match"] is not None:
        md.append("")
        md.append("Inventory Ledger: `%s`" % names.get("ledger", "ledger"))
    md.append("")
    md.append("## Totals (every figure summed from your file)")
    md.append("")
    md.append("- Net reimbursed, reversals included: **%s**" % m(s["total_amount"]))
    md.append("- Reimbursements: %s over %s · Reversals: %s over %s" % (
        m(s["reimbursed_amount"]), _lines(s["row_count"] - s["reversal_count"]), m(s["reversal_amount"]), _lines(s["reversal_count"])))
    md.append("- Units reimbursed, reversals netted: %d (cash %d · as inventory %d)" % (s["units"], s["cash_units"], s["inventory_units"]))
    md.append("")
    md.append("## By reason (reversals netted against the reason on their line)")
    md.append("")
    md.append(core.md_table(["Reason", "Lines", "Units", "Amount", "Offsets a warehouse loss in ledger-audit?"],
                            [[x["reason"], x["count"], x["units"], m(x["amount"]),
                              "Yes" if core.is_warehouse_loss_reason(x["reason"]) else
                              ("Only if it reverses a warehouse line" if "revers" in x["reason"].lower() else "No")]
                             for x in s["by_reason"]]))
    md.append("")
    md.append("## By SKU")
    md.append("")
    md.append(core.md_table(["SKU", "ASIN", "Product", "Lines", "Units", "Amount"],
                            [[x["sku"], x["asin"], x["product_name"], x["count"], x["units"], m(x["amount"])] for x in s["by_sku"]]))
    md.append("")
    if out["reversals"]:
        md.append("## Reversals (Amazon taking an earlier reimbursement back)")
        md.append("")
        md.append(core.md_table(["Reversal ID", "Date", "SKU", "Amount", "Units", "Reverses", "Original in this file?", "Original reason"],
                                [[x["reimbursement_id"], x["approval_date"], x["sku"], m(x["amount"]), x["units"],
                                  x["original_reimbursement_id"] or "(not given)", "Yes" if x["original_in_file"] else "No",
                                  x["original_reason"]] for x in out["reversals"]]))
        md.append("")
    sp = out["short_pay"]
    if sp is not None:
        md.append("## Lines reimbursed below your unit cost")
        md.append("")
        md.append("Per-unit amount = amount-total ÷ %s, compared with the cost you gave. %d line%s checked." % (
            sp["units_basis"], sp["checked_lines"], "" if sp["checked_lines"] == 1 else "s"))
        md.append("")
        if not sp["lines"]:
            md.append("None: every checked line was reimbursed at or above the cost you gave.")
        else:
            md.append(core.md_table(["Reimbursement ID", "Date", "SKU", "Reason", "Units", "Per unit", "Your cost", "Gap", "Note"],
                                    [[x["reimbursement_id"], x["approval_date"], x["sku"], x["reason"], x["units"], m(x["per_unit"]),
                                      m(x["your_cost"]), m(x["shortfall"]),
                                      "; ".join(n for n in [
                                          "reversed in part or in full (see Reversals)" if x["later_reversed"] else "",
                                          "inventory not tied to an order" if x["inventory_reason"] else "order-related or other reason — valuation may differ",
                                      ] if n)] for x in sp["lines"]]))
            md.append("")
            md.append("Total gap against your cost: **%s**. This compares Amazon's amount with *your* number; it does not mean "
                      "Amazon owes the difference. Check the manufacturing cost Amazon has on file for each SKU before "
                      "raising anything." % m(sp["total_shortfall"]))
        md.append("")
    lm = out["ledger_match"]
    if lm is not None:
        md.append("## Warehouse reimbursements vs Inventory Ledger losses")
        md.append("")
        md.append("Ledger losses are lost (M/5) net of found (F/N) plus warehouse-damaged (E). Only Lost_Warehouse / "
                  "Damaged_Warehouse lines (net of their reversals) are matched to them.")
        md.append("")
        md.append(core.md_table(["SKU", "Ledger lost", "Ledger damaged", "Ledger dates", "Warehouse units reimbursed",
                                 "Reimbursement IDs", "Not reimbursed", "Reimbursed beyond this ledger"],
                                [[x["sku"], x["ledger_lost"], x["ledger_damaged"],
                                  (x["ledger_first"] if x["ledger_first"] == x["ledger_last"]
                                   else "%s to %s" % (x["ledger_first"], x["ledger_last"])) if x["ledger_first"] else "—",
                                  x["warehouse_units_reimbursed"], ", ".join(x["reimbursement_ids"]) or "—",
                                  x["not_reimbursed"], x["reimbursed_beyond_ledger"]] for x in lm["rows"]]))
        md.append("")
        md.append("\"Reimbursed beyond this ledger\" usually means the loss happened before the ledger's date range. For "
                  "claim-window dates per unit, run the ledger-audit skill.")
        md.append("")
    warnings = list(s["warnings"]) + (lm["warnings"] if lm else [])
    if warnings:
        md.append("## Warnings")
        md.append("")
        md += ["- %s" % w for w in warnings]
        md.append("")
    md.append("## Read this before acting")
    md.append("")
    md.append("- This report lists reimbursements Amazon has already made. It cannot show what is still missing on its own; "
              "that needs the Inventory Ledger (ledger-audit) or settlement + returns reports (returns-not-received).")
    md.append("- Dated facts (as of %s; sources in `references/reimbursement-reasons.md` and `references/valuation.md`): since "
              "31 Mar 2025 reimbursements for inventory not tied to a customer order are based on the item's manufacturing "
              "cost; if Amazon has no cost on file it uses its own estimate. Reimbursements can take up to 5 days to appear "
              "in the report. Not affiliated with Amazon. Not legal or tax advice." % FACTS_AS_OF)
    return "\n".join(md)


def _parse_sku_costs(items):
    out = {}
    for it in items or []:
        if "=" not in it:
            raise ValueError("--sku-cost must look like SKU=COST, got %r" % it)
        sku, cost = it.rsplit("=", 1)
        out[sku.strip()] = float(cost)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description="FBA reimbursements: totals, reversals, below-cost lines, ledger match.")
    p.add_argument("reimbursements", help="Reimbursements report (CSV/TSV/TXT)")
    p.add_argument("--ledger", help="Inventory Ledger, Detailed view (optional)")
    p.add_argument("--unit-cost", type=float, help="Your cost per unit for every SKU (optional)")
    p.add_argument("--sku-cost", action="append", metavar="SKU=COST", help="Cost for one SKU; repeat as needed (optional)")
    p.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    a = p.parse_args(argv)
    try:
        sku_costs = _parse_sku_costs(a.sku_cost)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    try:
        reimb_text = core.read_text(a.reimbursements)
        ledger_text = core.read_text(a.ledger) if a.ledger else None
    except OSError as e:
        print("Could not open a file: %s" % e, file=sys.stderr)
        return 2
    out = run(reimb_text, ledger_text, unit_cost=a.unit_cost, sku_costs=sku_costs)
    if not out["ok"]:
        msg = "%s file: %s" % (out["file"], out["message"])
        if out["found_columns"]:
            msg += " Columns found: %s." % ", ".join(out["found_columns"])
        print(msg, file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        names = {"reimbursements": os.path.basename(a.reimbursements)}
        if a.ledger:
            names["ledger"] = os.path.basename(a.ledger)
        print(render_markdown(out, names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
