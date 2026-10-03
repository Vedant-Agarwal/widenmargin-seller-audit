#!/usr/bin/env python3
"""
returns-not-received: FBA orders refunded to a customer where the unit never came back to a
fulfillment center and Amazon has not reimbursed the seller, dated against the day-60-to-120
claim window.

Usage:
  python3 returns_not_received.py --settlement S1.txt [S2.txt ...] --returns RETURNS.txt
                                  [--reimbursements REIMB.txt] [--today YYYY-MM-DD] [--json]

Reads only the files named on the command line; sends nothing anywhere. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wm_audit_core as core  # noqa: E402

FACTS_AS_OF = "2026-10-03"
STATUS_LABEL = {"claim-now": "Claim now (day 60–120)", "wait": "Wait", "too-late": "Past day 120"}


def run(settlement_texts, returns_text, reimb_text=None, today=None, claim_from_days=60, claim_until_days=120):
    """Pure entry point. settlement_texts is a list of (name, text): several settlement files are
    parsed one by one and their rows combined (each covers ~2 weeks)."""
    rows = []
    files = []
    for name, text in settlement_texts:
        res = core.parse_settlement_report(text)
        if not res["ok"]:
            return {"ok": False, "file": "settlement report %s" % name, "message": res["message"], "found_columns": res["found_columns"]}
        rows.extend(res["rows"])
        files.append({"name": name, "delimiter": res["delimiter"], "rows": len(res["rows"]),
                      "settlement_ids": res["settlement_ids"], "currencies": res["currencies"],
                      "marketplace": res["marketplace"],
                      "warnings": [w["message"] for w in res["warnings"] if w["code"] != "unparsable-amount"]})
    ret = core.parse_customer_returns(returns_text)
    if not ret["ok"]:
        return {"ok": False, "file": "customer returns", "message": ret["message"], "found_columns": ret["found_columns"]}
    reimb_rows = []
    reimb = None
    if reimb_text is not None:
        reimb = core.parse_reimbursements(reimb_text)
        if not reimb["ok"]:
            return {"ok": False, "file": "reimbursements", "message": reimb["message"], "found_columns": reimb["found_columns"]}
        reimb_rows = reimb["rows"]
    result = core.find_unreturned_refunds(rows, ret["rows"], reimb_rows, today=today,
                                          claim_from_days=claim_from_days, claim_until_days=claim_until_days)
    refund_dates = sorted(set(core.to_iso_date(r["posted_date"], r["posted_date"][:10]) for r in rows
                              if core._RE_REFUND.search(r["transaction_type"]) and r["posted_date"]))
    return {
        "ok": True,
        "settlement_files": files,
        "refund_date_range": [refund_dates[0], refund_dates[-1]] if refund_dates else None,
        "returns": {"rows": len(ret["rows"]), "warnings": ret["warnings"]},
        "reimbursements": None if reimb is None else {"rows": reimb["summary"]["row_count"],
                                                     "date_from": reimb["summary"]["date_from"],
                                                     "date_to": reimb["summary"]["date_to"],
                                                     "warnings": reimb["summary"]["warnings"]},
        "result": result,
        "claim_now_principal": round(sum(c["refunded_principal"] for c in result["cases"] if c["status"] == "claim-now"), 2),
    }


def draft_message(case, have_reimb):
    L = []
    L.append("Subject: Refunded FBA order %s — item not returned and not reimbursed" % case["order_id"])
    L.append("")
    L.append("Hello,")
    L.append("")
    tail = (", and our Reimbursements report shows no CustomerReturn or CustomerServiceIssue reimbursement for it."
            if have_reimb else ".")
    L.append("Order %s (SKU %s) was refunded to the customer on %s, %d days ago. Our FBA Customer Returns report shows "
             "no return received at a fulfillment center for this order and SKU%s Could you please check whether the "
             "item was returned and, if it was not, review the order for reimbursement?"
             % (case["order_id"], case["sku"], case["refund_date"], case["days_since_refund"], tail))
    L.append("")
    L.append("- Order ID: %s" % case["order_id"])
    L.append("- SKU: %s" % case["sku"])
    ids = []
    if case["settlement_ids"]:
        ids.append("settlement ID %s" % ", ".join(case["settlement_ids"]))
    if case["adjustment_ids"]:
        ids.append("adjustment ID %s" % ", ".join(case["adjustment_ids"]))
    L.append("- Refund posted: %s%s" % (case["refund_date"], (" (" + "; ".join(ids) + ")") if ids else ""))
    L.append("- Units refunded: %d · units returned: %d · units reimbursed: %d" % (
        case["refunded_units"], case["returned_units"], case["reimbursed_units"]))
    if case["refunded_principal"]:
        L.append("- Principal refunded to the customer: %s" % core.fmt_money(case["refunded_principal"]))
    L.append("")
    L.append("Thank you.")
    return "\n".join(L)


def _rows(n):
    return "%d row%s" % (n, "" if n == 1 else "s")


def render_markdown(out, names):
    r = out["result"]
    cases = r["cases"]
    have_reimb = out["reimbursements"] is not None
    md = ["# Refunded but not returned (FBA)", ""]
    s_desc = ", ".join("`%s` (%s)" % (f["name"], _rows(f["rows"])) for f in out["settlement_files"])
    md.append("Settlement file%s: %s" % ("" if len(out["settlement_files"]) == 1 else "s", s_desc))
    md.append("")
    md.append("Customer returns: `%s` (%s) · Reimbursements: %s" % (
        names.get("returns", "returns"), _rows(out["returns"]["rows"]),
        ("`%s` (%s)" % (names.get("reimbursements", "reimbursements"), _rows(out["reimbursements"]["rows"]))) if have_reimb
        else "**not provided** — Amazon reimburses many of these on its own, so this list is an upper bound"))
    md.append("")
    if out["refund_date_range"]:
        md.append("Refunds in these files run from %s to %s. Checked as of **%s**." % (
            out["refund_date_range"][0], out["refund_date_range"][1], r["today"]))
    else:
        md.append("No refund lines were found in the settlement file(s). Checked as of **%s**." % r["today"])
    md.append("")
    md.append("## Summary")
    md.append("")
    md.append("- FBA refunds checked (order + SKU): **%d** · returned: %d · reimbursed: %d" % (
        r["refunded_lines"], r["returned_lines"], r["reimbursed_lines"]))
    md.append("- **Claim now** (day %d–%d after the refund): **%d** order line%s%s" % (
        r["claim_from_days"], r["claim_until_days"], r["claim_now"], "" if r["claim_now"] == 1 else "s",
        (" · %s principal refunded to customers" % core.fmt_money(out["claim_now_principal"])) if out["claim_now_principal"] else ""))
    md.append("- Wait (under day %d — Amazon may still reimburse on its own): %d" % (r["claim_from_days"], r["waiting"]))
    md.append("- Past day %d (too late to claim): %d" % (r["claim_until_days"], r["too_late"]))
    if r["mfn_skipped"]:
        md.append("- Seller-fulfilled (MFN) refunds skipped: %d — returns you ship yourself are not Amazon's to reimburse" % r["mfn_skipped"])
    md.append("")
    md.append("## Orders worth checking")
    md.append("")
    if not cases:
        md.append("Nothing missing: every FBA refund in these files was returned or reimbursed.")
    else:
        rows = []
        for c in cases:
            label = STATUS_LABEL[c["status"]]
            if c["status"] == "wait":
                label = "Wait — claimable from %s" % c["claimable_from"]
            elif c["status"] == "claim-now":
                label = "Claim now — until %s" % c["claimable_until"]
            rows.append([c["order_id"], c["sku"], c["refund_date"], c["days_since_refund"],
                         core.fmt_money(c["refunded_principal"]) if c["refunded_principal"] else "—",
                         c["refunded_units"], c["returned_units"], c["reimbursed_units"], c["missing_units"], label])
        md.append(core.md_table(["Order", "SKU", "Refunded on", "Days", "Principal refunded", "Refunded", "Returned",
                                 "Reimbursed", "Missing", "Status"], rows))
    md.append("")
    now = [c for c in cases if c["status"] == "claim-now"]
    if now:
        md.append("## Draft case messages (drafts — verify each order in Seller Central before sending)")
        md.append("")
        for c in now:
            md.append("### %s · %s" % (c["order_id"], c["sku"]))
            md.append("")
            md.append("```")
            md.append(draft_message(c, have_reimb))
            md.append("```")
            md.append("")
    warnings = []
    for f in out["settlement_files"]:
        warnings += ["%s: %s" % (f["name"], w) for w in f["warnings"]]
    warnings += out["returns"]["warnings"]
    if have_reimb:
        warnings += out["reimbursements"]["warnings"]
    if warnings:
        md.append("## Warnings")
        md.append("")
        md += ["- %s" % w for w in warnings]
        md.append("")
    md.append("## Read this before acting")
    md.append("")
    md.append("- These are orders **worth checking**, not money Amazon owes. A return can arrive late or under a different "
              "order line, and Amazon sometimes refunds without asking for the item back.")
    md.append("- A row in the returns report counts as returned whatever its disposition; for DAMAGED or CARRIER_DAMAGED "
              "returns, look for the compensation in the Reimbursements report separately.")
    md.append("- The refunded amount is what the customer got back; Amazon reimburses at its own valuation.")
    md.append("- Dated facts (as of %s; sources in `references/returns-rules.md`): Amazon normally reimburses a refund with no "
              "return at around day 45; if it does not, a claim can be filed from day 60 to day 120 after the refund. "
              "Not affiliated with Amazon. Not legal or tax advice." % FACTS_AS_OF)
    return "\n".join(md)


def main(argv=None):
    p = argparse.ArgumentParser(description="FBA refunds where the item never came back and was not reimbursed.")
    p.add_argument("--settlement", nargs="+", required=True, help="Settlement report flat file(s) V2 — several allowed")
    p.add_argument("--returns", required=True, help="FBA Customer Returns report")
    p.add_argument("--reimbursements", help="Reimbursements report (optional, recommended)")
    p.add_argument("--today", help="Date to measure from, YYYY-MM-DD (default: today, UTC)")
    p.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    a = p.parse_args(argv)
    try:
        settlements = [(os.path.basename(path), core.read_text(path)) for path in a.settlement]
        returns_text = core.read_text(a.returns)
        reimb_text = core.read_text(a.reimbursements) if a.reimbursements else None
    except OSError as e:
        print("Could not open a file: %s" % e, file=sys.stderr)
        return 2
    out = run(settlements, returns_text, reimb_text, today=a.today)
    if not out["ok"]:
        msg = "%s: %s" % (out["file"], out["message"])
        if out["found_columns"]:
            msg += " Columns found: %s." % ", ".join(out["found_columns"])
        print(msg, file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        names = {"returns": os.path.basename(a.returns)}
        if a.reimbursements:
            names["reimbursements"] = os.path.basename(a.reimbursements)
        print(render_markdown(out, names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
