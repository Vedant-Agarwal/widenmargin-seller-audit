// Parity harness: runs the ORIGINAL shelfstack TypeScript over a plan of scenarios and prints JSON.
// run_parity.py copies the TS libs next to this file (imports rewritten to relative .ts paths) and
// runs it with `node --experimental-strip-types`. Nothing here is shipped in the plugin.
import { readFileSync } from "node:fs";
import { parseInventoryLedger } from "./lib/fba-inventory-ledger/parse.ts";
import { reconcile } from "./lib/fba-recovery/reconcile.ts";
import { reimbursedUnitsForRecovery } from "./lib/fba-recovery/from-reimbursements.ts";
import { parseReimbursements } from "./lib/fba-reimbursements/parse.ts";
import { parseSettlementReport } from "./lib/settlement-report/parse.ts";
import { SAMPLE_IN_TSV, SAMPLE_US_CSV } from "./lib/settlement-report/sample.ts";
import { parseCustomerReturns } from "./lib/fba-returns/parse.ts";
import { findUnreturnedRefunds } from "./lib/fba-returns/reconcile.ts";

const plan = JSON.parse(readFileSync(process.argv[2], "utf8"));
const read = (p: string) => readFileSync(p, "utf8");
const day = (s: string) => new Date(`${s}T00:00:00Z`);
const out: Record<string, unknown> = { __samples: { SAMPLE_IN_TSV, SAMPLE_US_CSV } };

for (const sc of plan.scenarios) {
  try {
    if (sc.kind === "ledger") out[sc.id] = parseInventoryLedger(read(sc.file));
    else if (sc.kind === "reimbursements") out[sc.id] = parseReimbursements(read(sc.file));
    else if (sc.kind === "settlement") out[sc.id] = parseSettlementReport(sc.text ?? read(sc.file));
    else if (sc.kind === "returns") out[sc.id] = parseCustomerReturns(read(sc.file));
    else if (sc.kind === "recovery-units") {
      const r = parseReimbursements(read(sc.file));
      out[sc.id] = r.ok ? reimbursedUnitsForRecovery(r.rows) : r;
    } else if (sc.kind === "reconcile") {
      out[sc.id] = reconcile(sc.losses, sc.reimbursed, { today: day(sc.today), unitCosts: sc.unit_costs });
    } else if (sc.kind === "ledger-audit") {
      const l = parseInventoryLedger(read(sc.ledger));
      if (!l.ok) { out[sc.id] = l; continue; }
      let reimbursed: { sku: string; units: number; amount: number }[] = sc.reimbursed ?? [];
      if (sc.reimbursements) {
        const r = parseReimbursements(read(sc.reimbursements));
        if (!r.ok) { out[sc.id] = r; continue; }
        reimbursed = reimbursedUnitsForRecovery(r.rows);
      }
      const unitCosts: Record<string, number> = {};
      if (sc.unit_cost > 0) for (const x of l.losses) unitCosts[x.sku] = sc.unit_cost; // as recovery-tool.tsx
      out[sc.id] = reconcile(l.losses, reimbursed, { today: day(sc.today), unitCosts });
    } else if (sc.kind === "returns-audit") {
      const rows = [];
      let bad = null;
      for (const f of sc.settlements) {
        const s = parseSettlementReport(read(f));
        if (!s.ok) { bad = s; break; }
        rows.push(...s.rows); // as returns-finder.tsx: several settlement files, rows combined
      }
      if (bad) { out[sc.id] = bad; continue; }
      const ret = parseCustomerReturns(read(sc.returns));
      if (!ret.ok) { out[sc.id] = ret; continue; }
      let reimb = [];
      if (sc.reimbursements) {
        const m = parseReimbursements(read(sc.reimbursements));
        if (!m.ok) { out[sc.id] = m; continue; }
        reimb = m.rows;
      }
      out[sc.id] = findUnreturnedRefunds(rows, ret.rows, reimb, { today: day(sc.today) });
    }
  } catch (e) {
    out[sc.id] = { __error: String(e) };
  }
}
process.stdout.write(JSON.stringify(out));
