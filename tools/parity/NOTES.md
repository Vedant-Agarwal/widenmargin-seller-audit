# Parity: Python port vs the original TypeScript

`run_parity.py` runs the ORIGINAL TypeScript from github.com/Vedant-Agarwal/shelfstack
(`agent-core/apps/web/src/lib`, checked at commit c88af9c, 2026-10-02) and `src/wm_audit_core.py`
over the same inputs and compares every field the TypeScript returns.

Inputs: every scenario in the TS vitest files (ported to `tests/fixtures/`), the TS settlement
samples (`settlement-report/sample.ts`), the demo fixtures, and N random cases per seed of each
kind: ledger parse, reimbursements parse, warehouse units for recovery, ledger + reimbursements
reconcile ("ledger-audit"), and settlement(s) + returns + reimbursements ("returns-audit"). The
generator mixes tab/comma files, BOMs, CRLF, preambles, repeated headers, quoted fields with
commas and quotes, accounting negatives, "$1,234.50", blank and fractional quantities, lowercase
and unknown reason codes, free-text reasons, reversals of present/absent originals, MFN/AFN/blank
fulfillment, ISO / ISO date-time / MM/DD/YYYY / M/D/YY dates, day 29-31 in short months and
invalid months.

Result on 2026-10-03 (Node v25.2.1, Python 3.9.6): seeds 7, 11, 23 and 42 with `--fuzz 500` —
4 × 2,500 random scenarios plus 46 fixture scenarios — **identical** on every compared value
(about 270,000 per run). A negative control (breaking F-netting and using banker's rounding)
was caught as 97 differing scenarios.

## Known, documented differences (none affects a count, total or status on real exports)

1. **Time zone of non-ISO dates.** V8 reads "MM/DD/YYYY" (and ISO date-times without an offset)
   in the browser's local time; Python reads them as UTC, which is what Claude's sandbox uses.
   This can only change which raw approval-date string the reimbursements summary shows as
   "from"/"to" when one file mixes formats for the same day. The harness runs Node with `TZ=UTC`;
   in a US-time-zone browser, seed 23 shows 2 such display-only differences.
2. **Free-text dates the parsers leave as-is** (e.g. "Jun 26, 2026", "2026/01/10"). V8's
   `new Date()` accepts some of these; Python treats them as unparseable (age 0 — the same path the
   TypeScript takes for an Invalid Date). Ledger, settlement, returns and reimbursements exports use
   ISO or MM/DD/YYYY, which both sides handle identically (including V8's day roll-over:
   "2026-02-30" is 2 March).
3. **File decoding.** The browser decodes files as UTF-8; Python tries UTF-8, then UTF-16 (with
   BOM), then Windows-1252. Only the display of non-UTF-8 product titles can differ.
4. **Additive fields.** Python results also carry reference IDs, fulfillment centers, source
   lines, per-unit window detail, settlement/adjustment IDs and amount-per-unit for the draft
   messages and the extra checks. They are never used in a count, total or status.
