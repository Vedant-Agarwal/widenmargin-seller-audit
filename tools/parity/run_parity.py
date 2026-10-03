#!/usr/bin/env python3
"""
Differential parity check: the Python port (src/wm_audit_core.py) vs the original TypeScript.

  python3 tools/parity/run_parity.py /path/to/shelfstack [--fuzz 300] [--seed 7]

1. Copies the seven TS lib files from <shelfstack>/agent-core/apps/web/src/lib into _parity_tmp/,
   rewriting "@/lib/..." imports to relative ".ts" paths, plus tools/parity/harness.ts.
2. Builds a plan: every fixture scenario ported from the TS vitest files, the TS settlement
   samples, and N randomly generated ledgers / reimbursements / settlement+returns sets.
3. Runs the plan through Node (`node --experimental-strip-types`, Node >= 22.6, TZ=UTC) and Python.
4. Compares every field the TypeScript returns (snake_case <-> camelCase). Extra Python-only
   fields (reference IDs, FCs, source lines...) are additive and ignored.
Exit status 0 only if every compared value is identical.
"""

import json
import os
import random
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "src"))
import wm_audit_core as core  # noqa: E402

FX = os.path.join(ROOT, "tests", "fixtures")
TMP = os.path.join(ROOT, "_parity_tmp")
LIBS = ["settlement-report/parse.ts", "settlement-report/sample.ts", "fba-inventory-ledger/parse.ts",
        "fba-recovery/reconcile.ts", "fba-recovery/from-reimbursements.ts", "fba-reimbursements/parse.ts",
        "fba-returns/parse.ts", "fba-returns/reconcile.ts"]


def copy_ts(shelfstack):
    src = os.path.join(shelfstack, "agent-core", "apps", "web", "src", "lib")
    if os.path.isdir(TMP):
        shutil.rmtree(TMP)
    for rel in LIBS:
        dst = os.path.join(TMP, "lib", rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        text = open(os.path.join(src, rel), encoding="utf-8").read()
        # every lib file sits at lib/<dir>/<file>.ts, so "@/lib/a/b" is "../a/b.ts" from any of them
        text = re.sub(r'from "@/lib/([^"]+)"', r'from "../\1.ts"', text)
        text = re.sub(r'from "\./([^".]+)"', r'from "./\1.ts"', text)
        open(dst, "w", encoding="utf-8").write(text)
    shutil.copyfile(os.path.join(HERE, "harness.ts"), os.path.join(TMP, "harness.ts"))


# ------------------------------------------------------------------ fixture scenarios
def fixture_plan():
    f = lambda n: os.path.join(FX, n)  # noqa: E731
    sc = []
    for n in ["ledger_real.tsv", "ledger_freetext.tsv", "not_a_report.csv", "demo_ledger.csv"]:
        sc.append({"id": "ledger:" + n, "kind": "ledger", "file": f(n)})
    for n in ["reimb_full.tsv", "reimb_full.csv", "not_a_report.csv", "reimb_recovery_mixed.tsv", "demo_reimbursements.tsv", "reimb_returns.tsv"]:
        sc.append({"id": "reimb:" + n, "kind": "reimbursements", "file": f(n)})
    for n in ["reimb_recovery_mixed.tsv", "reimb_recovery_outbound.tsv", "reimb_recovery_reversals.tsv", "demo_reimbursements.tsv", "reimb_full.tsv"]:
        sc.append({"id": "units:" + n, "kind": "recovery-units", "file": f(n)})
    for n in ["settlement_in_awkward.tsv", "settlement_us_quoted.csv", "settlement_v1.tsv", "settlement_unparsable.tsv",
              "settlement_concatenated.tsv", "settlement_returns.tsv", "settlement_part1.tsv", "not_a_report.csv"]:
        sc.append({"id": "settle:" + n, "kind": "settlement", "file": f(n)})
    sc.append({"id": "settle:empty", "kind": "settlement", "text": ""})
    sc.append({"id": "settle:blank", "kind": "settlement", "text": "   \n\n "})
    sc.append({"id": "settle:header-only", "kind": "settlement", "text": "settlement-id\tamount-type\tamount-description\tamount\n"})
    for n in ["returns.tsv", "returns_empty.tsv", "not_a_report.csv"]:
        sc.append({"id": "returns:" + n, "kind": "returns", "file": f(n)})
    cases = json.load(open(f("reconcile_cases.json")))
    for k, v in cases.items():
        sc.append({"id": "reconcile:" + k, "kind": "reconcile", **v})
    sc.append({"id": "audit:ledger_real+B1", "kind": "ledger-audit", "ledger": f("ledger_real.tsv"), "reimbursed": [{"sku": "B", "units": 1, "amount": 9}],
               "today": "2026-03-01", "unit_cost": 0})
    sc.append({"id": "audit:ledger_real+file", "kind": "ledger-audit", "ledger": f("ledger_real.tsv"), "reimbursements": f("reimb_ledger_b.tsv"),
               "today": "2026-03-01", "unit_cost": 7.25})
    sc.append({"id": "audit:demo", "kind": "ledger-audit", "ledger": f("demo_ledger.csv"), "reimbursements": f("demo_reimbursements.tsv"),
               "today": "2026-10-03", "unit_cost": 6.5})
    sc.append({"id": "returns-audit:main", "kind": "returns-audit", "settlements": [f("settlement_returns.tsv")], "returns": f("returns.tsv"),
               "reimbursements": f("reimb_returns.tsv"), "today": "2026-09-24"})
    sc.append({"id": "returns-audit:multi-file", "kind": "returns-audit", "settlements": [f("settlement_part1.tsv"), f("settlement_part2.tsv")],
               "returns": f("returns.tsv"), "reimbursements": f("reimb_returns.tsv"), "today": "2026-09-24"})
    for n in ["reimb_o9_fee.tsv", "reimb_o9_customer.tsv", "reimb_o9_reversed.tsv"]:
        sc.append({"id": "returns-audit:" + n, "kind": "returns-audit", "settlements": [f("settlement_o9.tsv")], "returns": f("returns_empty.tsv"),
                   "reimbursements": f(n), "today": "2026-09-24"})
    sc.append({"id": "returns-audit:no-reimb", "kind": "returns-audit", "settlements": [f("settlement_returns.tsv")], "returns": f("returns.tsv"),
               "today": "2026-09-24"})
    return sc


# ------------------------------------------------------------------ random generators
def _q(v, delim, rng):
    if delim == "," and (("," in v) or ('"' in v) or rng.random() < 0.1):
        return '"' + v.replace('"', '""') + '"'
    return v


def _date(rng, fmt):
    y = rng.choice([2025, 2026])
    m = rng.randint(1, 13) if rng.random() < 0.03 else rng.randint(1, 12)
    d = rng.randint(1, 31)  # includes V8's ISO day roll-over (2026-02-30 -> 2 March) and invalid dates
    if fmt == "us":
        return "%02d/%02d/%d" % (m, d, y)
    if fmt == "us-short":
        return "%d/%d/%02d" % (m, d, y % 100)
    if fmt == "iso-dt":
        return "%d-%02d-%02dT%02d:15:00-07:00" % (y, m, d, rng.randint(0, 23))
    return "%d-%02d-%02d" % (y, m, d)


def gen_ledger(rng):
    delim = rng.choice(["\t", ","])
    with_dt = rng.random() < 0.4
    hdr = ["Date"] + (["Date and Time"] if with_dt else []) + ["FNSKU", "ASIN", "MSKU", "Title", "Event Type", "Reference ID", "Quantity",
                                                              "Fulfillment Center", "Disposition", "Reason", "Country", "Reconciled Quantity", "Unreconciled Quantity"]
    if rng.random() < 0.2:
        hdr = [h.lower().replace(" ", rng.choice(["-", "_", " "])) for h in hdr]
    reasons = list(core.REASON_CODES.keys()) + ["m", "e", "", "", "Z", "Lost", "Damaged:Warehouse", "Damaged:Customer", "Found", "Disposal", "misplaced unit"]
    events = ["Adjustments", "Adjustments", "Adjustments", "Receipts", "Shipments", "CustomerReturns", "VendorReturns", "Found", "Disposed"]
    lines = []
    if rng.random() < 0.2:
        lines.append("Inventory ledger export")
    lines.append(delim.join(hdr))
    for _ in range(rng.randint(0, 40)):
        sku = rng.choice(["A", "B", "C", "D", ""])
        fmt = rng.choice(["us", "us", "iso", "us-short"])
        qty = rng.choice([str(rng.randint(-6, 6)), "", "(2)", "-1.5", "2.5", "n/a"])
        title = rng.choice(["Widget", 'Mug, 12oz "Blue"', "Mat", ""])
        row = [_date(rng, fmt)] + ([_date(rng, "iso-dt")] if with_dt else []) + [
            ("X-" + sku) if sku or rng.random() < 0.5 else "", "B-" + sku, sku, title, rng.choice(events), "R%d" % rng.randint(1, 99),
            qty, rng.choice(["PHX6", "ONT8", ""]), rng.choice(["SELLABLE", "WAREHOUSE_DAMAGED", ""]), rng.choice(reasons), "US", "0",
            rng.choice(["0", "1", "", "3"])]
        lines.append(delim.join(_q(v, delim, rng) for v in row))
        if rng.random() < 0.03:
            lines.append(delim.join(hdr))  # concatenated files
        if rng.random() < 0.03:
            lines.append("")
    text = ("﻿" if rng.random() < 0.2 else "") + (("\r\n" if rng.random() < 0.3 else "\n").join(lines))
    return text


def gen_reimb(rng, order_ids=None, skus=("A", "B", "C", "D")):
    delim = rng.choice(["\t", ","])
    hdr = ["approval-date", "reimbursement-id", "case-id", "amazon-order-id", "reason", "sku", "fnsku", "asin", "product-name", "condition",
           "currency-unit", "amount-per-unit", "amount-total", "quantity-reimbursed-cash", "quantity-reimbursed-inventory",
           "quantity-reimbursed-total", "original-reimbursement-id", "original-reimbursement-type"]
    reasons = ["Lost_Warehouse", "Damaged_Warehouse", "Lost:Warehouse", "damaged warehouse", "Lost_Outbound", "Damaged_Inbound", "CustomerReturn",
               "CustomerServiceIssue", "FeeCorrection", "UnplannedServiceFee", "Reimbursement_Reversal", ""]
    ids = []
    lines = [delim.join(hdr)]
    for i in range(rng.randint(0, 25)):
        rid = "R%d" % (i + 1)
        reason = rng.choice(reasons)
        reversal = reason == "Reimbursement_Reversal" or rng.random() < 0.1
        orig = (rng.choice(ids) if ids and rng.random() < 0.7 else "R-missing") if reversal else ""
        q = rng.randint(1, 3)
        amt = round(rng.uniform(1, 30), 2)
        amount = ("-%.2f" % amt) if reversal and rng.random() < 0.8 else rng.choice(["%.2f" % amt, "$%s" % format(amt, ",.2f"), "(%.2f)" % amt])
        qty = str(-q if reversal else q)
        sku = rng.choice(list(skus) + [""])
        oid = rng.choice(order_ids) if order_ids and rng.random() < 0.7 else ""
        row = [_date(rng, rng.choice(["iso", "iso-dt", "us"])), rid, "", oid, reason, sku, "X-" + sku if sku else rng.choice(["", "XF"]), "B-" + sku,
               "Item, %s" % sku, "New", "USD", "%.2f" % amt, amount, qty, "0", rng.choice([qty, qty, "", "2.5"]), orig, ""]
        lines.append(delim.join(_q(v, delim, rng) for v in row))
        if not reversal:
            ids.append(rid)
    return "\n".join(lines)


def gen_settlement(rng, order_ids, skus):
    delim = rng.choice(["\t", ","])
    hdr = ["settlement-id", "settlement-start-date", "settlement-end-date", "deposit-date", "total-amount", "currency", "transaction-type", "order-id",
           "adjustment-id", "marketplace-name", "amount-type", "amount-description", "amount", "fulfillment-id", "posted-date", "sku", "quantity-purchased"]
    if rng.random() < 0.3:
        hdr = [h for h in hdr if h != "fulfillment-id"]
    lines = [delim.join(hdr)]
    lines.append(delim.join(["S%d" % rng.randint(1, 9), "2026-01-01", "2026-09-30", "2026-10-02", "123.45", "USD"] + [""] * (len(hdr) - 6)))
    for _ in range(rng.randint(0, 30)):
        oid = rng.choice(order_ids)
        sku = rng.choice(skus + [""])
        ttype = rng.choice(["Refund", "Refund", "Refund", "Order", "Chargeback Refund", "other-transaction"])
        desc = rng.choice(["Principal", "Principal", "Commission", "Tax", "RefundCommission"])
        amt = rng.choice(["-%.2f" % rng.uniform(1, 40), "%.2f" % rng.uniform(1, 5), "", "(3.00)"])
        posted = rng.choice([_date(rng, "iso"), _date(rng, "iso-dt"), _date(rng, "us"), ""])
        vals = {"settlement-id": rng.choice(["", "S1"]), "transaction-type": ttype, "order-id": oid, "adjustment-id": "A%d" % rng.randint(1, 50),
                "marketplace-name": "Amazon.com", "amount-type": "ItemPrice", "amount-description": desc, "amount": amt,
                "fulfillment-id": rng.choice(["AFN", "AFN", "afn", "MFN", ""]), "posted-date": posted, "sku": sku,
                "quantity-purchased": rng.choice(["", "1", "2", "0", "-1"]), "currency": rng.choice(["", "USD"])}
        lines.append(delim.join(_q(vals.get(h, ""), delim, rng) for h in hdr))
    return "\n".join(lines)


def gen_returns(rng, order_ids, skus):
    hdr = ["return-date", "order-id", "sku", "asin", "fnsku", "product-name", "quantity", "fulfillment-center-id", "detailed-disposition",
           "reason", "status", "license-plate-number", "customer-comments"]
    lines = ["\t".join(hdr)]
    for _ in range(rng.randint(0, 10)):
        lines.append("\t".join([_date(rng, "iso-dt"), rng.choice(order_ids + [""]), rng.choice(skus), "B", "X", "Item", rng.choice(["1", "2", "", "-1", "1.5"]),
                                "PHX6", rng.choice(["SELLABLE", "DAMAGED", "CUSTOMER_DAMAGED"]), "UNWANTED_ITEM", "Unit returned to inventory", "LPN", ""]))
    return "\n".join(lines)


def fuzz_plan(n, seed):
    rng = random.Random(seed)
    d = os.path.join(TMP, "fuzz")
    os.makedirs(d, exist_ok=True)
    sc = []
    for i in range(n):
        lp = os.path.join(d, "ledger_%d.txt" % i)
        rp = os.path.join(d, "reimb_%d.txt" % i)
        open(lp, "w", encoding="utf-8", newline="").write(gen_ledger(rng))
        open(rp, "w", encoding="utf-8", newline="").write(gen_reimb(rng))
        today = "2026-%02d-%02d" % (rng.randint(1, 12), rng.randint(1, 28))
        sc.append({"id": "fuzz-ledger:%d" % i, "kind": "ledger", "file": lp})
        sc.append({"id": "fuzz-reimb:%d" % i, "kind": "reimbursements", "file": rp})
        sc.append({"id": "fuzz-units:%d" % i, "kind": "recovery-units", "file": rp})
        sc.append({"id": "fuzz-audit:%d" % i, "kind": "ledger-audit", "ledger": lp, "reimbursements": rp, "today": today,
                   "unit_cost": rng.choice([0, 0, 4.2, 10])})
        orders = ["O-%d" % k for k in range(1, rng.randint(2, 12))]
        skus = ["MUG", "MAT", "BOT"]
        sps = []
        for j in range(rng.randint(1, 3)):
            sp = os.path.join(d, "settle_%d_%d.txt" % (i, j))
            open(sp, "w", encoding="utf-8", newline="").write(gen_settlement(rng, orders, skus))
            sps.append(sp)
        tp = os.path.join(d, "returns_%d.txt" % i)
        open(tp, "w", encoding="utf-8", newline="").write(gen_returns(rng, orders, skus))
        mp = os.path.join(d, "reimb_orders_%d.txt" % i)
        open(mp, "w", encoding="utf-8", newline="").write(gen_reimb(rng, order_ids=orders, skus=skus))
        sc.append({"id": "fuzz-returns-audit:%d" % i, "kind": "returns-audit", "settlements": sps, "returns": tp,
                   "reimbursements": mp if rng.random() < 0.8 else None, "today": today})
    return sc


# ------------------------------------------------------------------ python side
def run_python(sc, samples):
    k = sc["kind"]
    rd = core.read_text
    if k == "ledger":
        return core.parse_inventory_ledger(rd(sc["file"]))
    if k == "reimbursements":
        return core.parse_reimbursements(rd(sc["file"]))
    if k == "settlement":
        text = sc["text"] if "text" in sc else (samples[sc["sample"]] if "sample" in sc else rd(sc["file"]))
        return core.parse_settlement_report(text)
    if k == "returns":
        return core.parse_customer_returns(rd(sc["file"]))
    if k == "recovery-units":
        r = core.parse_reimbursements(rd(sc["file"]))
        return core.reimbursed_units_for_recovery(r["rows"]) if r["ok"] else r
    if k == "reconcile":
        return core.reconcile(sc["losses"], sc["reimbursed"], unit_costs=sc["unit_costs"], today=sc["today"])
    if k == "ledger-audit":
        l = core.parse_inventory_ledger(rd(sc["ledger"]))
        if not l["ok"]:
            return l
        reimbursed = sc.get("reimbursed") or []
        if sc.get("reimbursements"):
            r = core.parse_reimbursements(rd(sc["reimbursements"]))
            if not r["ok"]:
                return r
            reimbursed = core.reimbursed_units_for_recovery(r["rows"])
        costs = {x["sku"]: sc["unit_cost"] for x in l["losses"]} if sc["unit_cost"] > 0 else {}
        return core.reconcile(l["losses"], reimbursed, unit_costs=costs, today=sc["today"])
    if k == "returns-audit":
        rows = []
        for p in sc["settlements"]:
            s = core.parse_settlement_report(rd(p))
            if not s["ok"]:
                return s
            rows.extend(s["rows"])
        ret = core.parse_customer_returns(rd(sc["returns"]))
        if not ret["ok"]:
            return ret
        reimb = []
        if sc.get("reimbursements"):
            m = core.parse_reimbursements(rd(sc["reimbursements"]))
            if not m["ok"]:
                return m
            reimb = m["rows"]
        return core.find_unreturned_refunds(rows, ret["rows"], reimb, today=sc["today"])
    raise ValueError(k)


def camel(s):
    parts = s.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def to_camel(o):
    if isinstance(o, dict):
        return {camel(k): to_camel(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [to_camel(v) for v in o]
    return o


def compare(ts, py, path, diffs):
    if isinstance(ts, dict):
        if not isinstance(py, dict):
            diffs.append("%s: TS object, Python %r" % (path, type(py).__name__))
            return
        for k, v in ts.items():
            if k not in py:
                diffs.append("%s.%s: missing in Python" % (path, k))
                continue
            compare(v, py[k], path + "." + k, diffs)
    elif isinstance(ts, list):
        if not isinstance(py, list) or len(py) != len(ts):
            diffs.append("%s: list length TS %d vs Python %s" % (path, len(ts), len(py) if isinstance(py, list) else type(py).__name__))
            return
        for i, (a, b) in enumerate(zip(ts, py)):
            compare(a, b, "%s[%d]" % (path, i), diffs)
    elif isinstance(ts, bool) or ts is None or isinstance(ts, str):
        if ts != py or type(ts) != type(py):
            diffs.append("%s: TS %r vs Python %r" % (path, ts, py))
    elif isinstance(ts, (int, float)):
        if isinstance(py, bool) or not isinstance(py, (int, float)) or ts != py:
            diffs.append("%s: TS %r vs Python %r" % (path, ts, py))
    else:
        diffs.append("%s: unhandled %r" % (path, ts))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    shelfstack = sys.argv[1]
    n = int(sys.argv[sys.argv.index("--fuzz") + 1]) if "--fuzz" in sys.argv else 300
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 7
    copy_ts(shelfstack)
    plan = fixture_plan()
    plan += [{"id": "settle:SAMPLE_IN_TSV", "kind": "settlement", "sample": "SAMPLE_IN_TSV"},
             {"id": "settle:SAMPLE_US_CSV", "kind": "settlement", "sample": "SAMPLE_US_CSV"}]
    plan += fuzz_plan(n, seed)
    plan_path = os.path.join(TMP, "plan.json")
    ts_plan = [dict(s) for s in plan]
    proc0 = subprocess.run(["node", "--experimental-strip-types", "--no-warnings", "-e",
                            "import('./lib/settlement-report/sample.ts').then(m=>process.stdout.write(JSON.stringify({SAMPLE_IN_TSV:m.SAMPLE_IN_TSV,SAMPLE_US_CSV:m.SAMPLE_US_CSV})))"],
                           cwd=TMP, capture_output=True, text=True)
    if proc0.returncode != 0:
        print(proc0.stderr)
        return 2
    samples = json.loads(proc0.stdout)
    for s in ts_plan:
        if "sample" in s:
            s["text"] = samples[s["sample"]]
    json.dump({"scenarios": ts_plan}, open(plan_path, "w"))
    # TZ=UTC: Claude's sandbox runs in UTC, and V8 reads "MM/DD/YYYY" approval dates in local time.
    env = dict(os.environ, TZ="UTC")
    proc = subprocess.run(["node", "--experimental-strip-types", "--no-warnings", "harness.ts", plan_path], cwd=TMP, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        print(proc.stderr)
        return 2
    ts_out = json.loads(proc.stdout)
    total_fields = [0]
    failures = 0
    by_kind = {}
    for sc in plan:
        ts = ts_out.get(sc["id"])
        if isinstance(ts, dict) and "__error" in ts:
            print("TS error in", sc["id"], ts["__error"])
            failures += 1
            continue
        py = to_camel(run_python(sc, samples))
        diffs = []
        compare(ts, py, sc["id"], diffs)
        kind = sc["kind"] + (" (fuzz)" if sc["id"].startswith("fuzz") else "")
        st = by_kind.setdefault(kind, [0, 0])
        st[0] += 1
        if diffs:
            failures += 1
            st[1] += 1
            print("MISMATCH", sc["id"])
            for d in diffs[:10]:
                print("   ", d)
        total_fields[0] += json.dumps(ts).count(":")
    print("\nParity summary (scenarios compared / mismatched):")
    for k in sorted(by_kind):
        print("  %-28s %4d / %d" % (k, by_kind[k][0], by_kind[k][1]))
    print("  values compared (approx.): %d" % total_fields[0])
    print("RESULT:", "IDENTICAL" if failures == 0 else "%d scenario(s) differ" % failures)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
