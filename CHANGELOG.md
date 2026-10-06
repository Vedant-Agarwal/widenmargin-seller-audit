# Changelog

All notable changes to this plugin are listed here. Versions follow `version` in
`.claude-plugin/plugin.json`; policy facts in each skill's `references/` carry their own as-of date.

## 0.1.1 — 2026-10-05

- Added a privacy policy (`PRIVACY.md`), linked from the README. No code changes.

## 0.1.0 — 2026-10-03

First release.

- `ledger-audit`: Inventory Ledger (Detailed view) vs Reimbursements report. Reason codes M/5
  (lost), F/N (found, netted oldest-first), E (warehouse-damaged), 6/D (review only), H/K/U/7/Q/P/3/4/O
  (not counted), free-text fallback; only Lost_Warehouse/Damaged_Warehouse reimbursements (net of
  their reversals) offset losses; per-unit 60-day window with open/closing (45+ days)/expired;
  reason-code breakdown; draft case message per SKU with FNSKU, dates, fulfillment centers and
  ledger reference IDs.
- `returns-not-received`: settlement Flat File V2 refunds (AFN only, several files combined) vs
  Customer Returns (order-id + sku) vs CustomerReturn/CustomerServiceIssue reimbursements; wait
  (under day 60) / claim now (day 60–120) / too late; draft case message per claim-now order.
- `reimbursement-check`: totals by reason and SKU with reversals netted, reversal list, lines
  reimbursed below the seller's own unit cost, and warehouse reimbursements matched to ledger losses.
- Python port of the WidenMargin TypeScript (shelfstack `agent-core/apps/web/src/lib`, commit
  c88af9c) with identical results on all ported fixtures and 10,000 fuzzed scenarios (tools/parity).
- Dated (2026-10-03), cited reference files for every policy fact.
