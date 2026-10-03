---
name: returns-not-received
description: Finds Amazon US FBA orders where the customer was refunded but the item never came back to a fulfillment center and Amazon has not reimbursed the seller, by matching settlement report refunds (Flat File V2, several files allowed) against the Customer Returns report and the Reimbursements report. Dates each order against the day-60-to-120 claim window (wait, claim now, too late) and drafts a case message for each claim-now order. Use when a seller asks which refunds were not returned, about refunded-but-not-returned or missing returns, customer returns that never arrived, unreturned FBA refunds, return reimbursements Amazon missed, or uploads settlement and customer returns reports.
license: MIT
compatibility: Runs a bundled Python 3.8+ script (standard library only) on the uploaded files. Needs code execution; no network access or packages required.
metadata:
  author: Vedant Agarwal
  version: "0.1.0"
  facts-as-of: "2026-10-03"
---

# Refunded but not returned (FBA)

Find FBA orders Amazon refunded to a customer where the unit never came back to a fulfillment
center and Amazon has not reimbursed the seller, and say which are inside the day-60-to-120 claim
window.

The matching is done by `scripts/returns_not_received.py`, a faithful port of the WidenMargin web
tool. **Never compute, estimate or round these numbers yourself, and never invent a number the
script did not print.** If the script fails, say so and show its message.

## Step 1 — Get the files

Required: **settlement report(s), Flat File V2** and the **Customer Returns report**. Strongly
recommended: the **Reimbursements report** (Amazon reimburses many of these on its own; without it
the list is an upper bound).

If a file is missing, ask for it with these steps (Seller Central menus as of 2026-10-03; labels can
change):

- **Settlement reports**: Seller Central → Reports → Payments → All Statements → for each
  settlement period, **Download Flat File V2** (not V1). Each covers about two weeks, so ask for
  several covering at least the last **4 months** — the claim window runs to day 120.
- **Customer Returns**: Seller Central → Reports → Fulfillment → Customer Returns (under Customer
  Concessions) → same dates through today → download.
- **Reimbursements**: Seller Central → Reports → Fulfillment → Reimbursements → same dates through
  today → download.

Files as downloaded (TXT/TSV/CSV) are fine; do not ask the seller to reformat them.

## Step 2 — Run the script

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/returns_not_received.py --settlement "S1.txt" "S2.txt" "S3.txt" --returns "RETURNS.txt" --reimbursements "REIMB.txt"
```

In claude.ai chat this skill's folder is copied into the sandbox, so the same script is at
`scripts/returns_not_received.py` relative to this SKILL.md. Pass every settlement file after
`--settlement`. Leave out `--reimbursements` only if the seller cannot provide it. `--today
YYYY-MM-DD` checks as of another date; `--json` prints the same result as JSON.

If a settlement file is the older V1 layout the script says so — ask for Flat File V2. For any
other "does not look like" message, show it with the "Columns found" list and ask for the right
download.

## Step 3 — Present the result

Use the script's Markdown output; keep its numbers exactly:

1. **Summary** — FBA refunds checked, returned, reimbursed; how many are **claim now** (day 60 to
   120), **wait** (under day 60, with the date claims open), and **too late** (past day 120);
   seller-fulfilled (MFN) refunds skipped.
2. **Orders worth checking** table.
3. **Draft case messages** for claim-now orders, exactly as printed, labelled as drafts to verify
   in Seller Central first (check the order's return status and that no reimbursement posted in
   the last few days).
4. If the reimbursements file was not given, say the list is an upper bound and ask for it.
5. If nothing is missing, say so plainly.

## Rules for wording

- Say "worth checking". Never say Amazon "owes" the seller and never promise a payout. A return
  can arrive late or under a different order line; Amazon sometimes refunds without asking for the
  item back.
- The "principal refunded" is what the customer got back, not what Amazon will reimburse.
- A row in the returns report counts as returned whatever its disposition; for DAMAGED or
  CARRIER_DAMAGED returns, the compensation shows up in the Reimbursements report separately.
- Dated facts, with their sources in `references/returns-rules.md`: Amazon normally reimburses a
  refund with no return at around day 45; if it does not, a claim can be filed from day 60 to day
  120 after the refund. Say these are as of 2026-10-03 and to confirm in Seller Central Help.
- For dispositions, statuses and column questions use `references/returns-rules.md` and
  `references/report-columns.md`.
- Files are processed only inside this conversation's sandbox; the script makes no network calls.
- Not affiliated with Amazon. Not legal, tax or accounting advice.

## Example (from the bundled test fixtures, two settlement files, checked as of 2026-09-24)

```
- FBA refunds checked (order + SKU): 5 · returned: 1 · reimbursed: 1
- Claim now (day 60–120 after the refund): 1 order line · $20.00 principal refunded to customers
- Wait (under day 60): 1   - Past day 120: 1   - Seller-fulfilled (MFN) refunds skipped: 1
| O-1 | MUG | 2026-06-26 | 90 days | $20.00 | Claim now — until 2026-10-24 |
| O-4 | BOT | 2026-09-04 | 20 days | $9.00  | Wait — claimable from 2026-11-03 |
| O-5 | BOT | 2026-03-08 | 200 days | $9.00 | Past day 120 |
```

A CustomerReturn reimbursement on the same order clears it; a fee line (e.g. UnplannedServiceFee)
does not; a reversal of that CustomerReturn reimbursement reopens it.
