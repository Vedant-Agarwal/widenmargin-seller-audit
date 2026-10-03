---
name: ledger-audit
description: Checks an Amazon US FBA Inventory Ledger (Detailed view) for units lost or damaged in Amazon's fulfillment centers that show no matching warehouse reimbursement, dates every remaining unit against the 60-day claim window (open, closing, expired), explains how each reason code (M, 5, F, N, E, P, 6, D, H, Q...) in the file was read, and drafts a case message per SKU still inside the window. Use when a seller asks to check or audit their inventory ledger, find lost or damaged FBA inventory that was not reimbursed, reconcile the ledger against the Reimbursements report, see which losses are still claimable or inside 60 days, or uploads an Inventory Ledger CSV/TSV.
license: MIT
compatibility: Runs a bundled Python 3.8+ script (standard library only) on the uploaded files. Needs code execution; no network access or packages required.
metadata:
  author: Vedant Agarwal
  version: "0.1.0"
  facts-as-of: "2026-10-03"
---

# FBA lost & damaged inventory check (Inventory Ledger)

Find FBA units the seller's own Inventory Ledger records as lost (M, 5) or damaged in a
fulfillment center (E), net of units found again (F, N), that have no matching Lost_Warehouse /
Damaged_Warehouse reimbursement — and say which are still inside the 60-day claim window.

The arithmetic is done by `scripts/ledger_audit.py`, a faithful port of the WidenMargin web tool.
**Never compute, estimate or round these numbers yourself, and never invent a number the script
did not print.** If the script fails, say so and show its message.

## Step 1 — Get the files

Required: the **Inventory Ledger, Detailed view**. Recommended: the **Reimbursements report** for
the same dates (without it nothing is subtracted as already reimbursed, so results are an upper
bound). Optional: the seller's **average cost per unit**, only for a rough value.

If a file is missing, ask for it with these steps (Seller Central menus as of 2026-10-03; labels can
change):

- **Inventory Ledger**: Seller Central → Reports → Fulfillment → Inventory Ledger → **Detailed
  view** → choose a date range covering at least the last 60 days (90 is better) → generate →
  download. The Summary view has no reason codes and will not work.
- **Reimbursements**: Seller Central → Reports → Fulfillment → Reimbursements → same dates →
  download.

CSV, TSV or TXT as downloaded are all fine; do not ask the seller to reformat them.

## Step 2 — Run the script

Run it on the uploaded file paths (quote paths with spaces):

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/ledger_audit.py "LEDGER_FILE" --reimbursements "REIMBURSEMENTS_FILE" --unit-cost 6.50
```

In claude.ai chat this skill's folder is copied into the sandbox, so the same script is at
`scripts/ledger_audit.py` relative to this SKILL.md. Leave out `--reimbursements` or `--unit-cost`
if not provided. Add `--today YYYY-MM-DD` only if the seller asks to check as of another date.
`--json` prints the same result as JSON if you need a specific field.

If the script exits with "does not look like an Amazon FBA inventory ledger" (or reimbursements
report), show the message and the "Columns found" list, and ask for the right download.

## Step 3 — Present the result

Use the script's Markdown output; keep its numbers exactly. In this order:

1. **Summary** — units without a matching warehouse reimbursement, units still inside the 60-day
   window, SKU counts by status (open / closing / past 60 days). If the seller gave a unit cost,
   the rough value, labelled as their cost × units, not what Amazon will reimburse.
2. **How your file was read** — always show the reason-code table (and the reimbursements reason
   table when that file was given) and ask the seller to confirm it matches their file. Point out
   any "Unrecognised reason" or warning lines.
3. **SKUs worth checking** and the per-unit window table. "Closing soon" means at least one unit
   inside the window is 45+ days old — mention its days left.
4. **Draft case messages** for SKUs with units inside the window, exactly as printed, clearly
   labelled as drafts to verify in Seller Central before sending. Do not draft for expired SKUs.
5. If nothing is found, say that is the expected outcome now that Amazon reimburses most warehouse
   losses automatically.

## Rules for wording

- Say "worth checking" / "not matched to a reimbursement". Never say Amazon "owes" the seller, and
  never promise a payout. Amazon may have found the units, reimbursed them under another SKU/FNSKU,
  or reimbursed them outside the reimbursements file's dates.
- Mention that since 1 Nov 2024 Amazon reimburses most fulfillment-center losses automatically,
  so this is a check that those reimbursements happened.
- Every policy fact is dated. State it with its date and source from
  `references/claim-rules.md` (60-day window since 23 Oct 2024, was 18 months; automatic
  reimbursement since 1 Nov 2024; manufacturing-cost valuation since 31 Mar 2025), and say the
  seller should confirm the current policy in Seller Central Help.
- For what a code means, use `references/reason-codes.md`; for column questions,
  `references/report-columns.md`. Do not guess a meaning for a code that is not listed.
- Carrier-damaged (6) and disposed (D) units are shown for review only; customer-damaged (H),
  defective (K), distributor-damaged (U), expired (7) and disposition changes (Q/P) are never
  claimable here.
- Files are processed only inside this conversation's sandbox; the script makes no network calls.
- Not affiliated with Amazon. Not legal, tax or accounting advice.

## Example (from the bundled test fixture)

Ledger with 11 rows + reimbursements with 5 rows, checked as of 2026-10-03:

```
- Lost/damaged units without a matching warehouse reimbursement: 9 units across 4 SKUs
- Of those, still inside the 60-day window: 8 units
- SKUs by window status: open 2 · closing 1 · past 60 days 1
| BOT-500  | 4 lost | 0 reimbursed | 4 inside window | Open |
| MUG-BLUE | 4 lost (after 1 found) | 1 reimbursed (2 − 1 reversed) | 3 inside window | Open |
| MAT-GREY | 2 damaged | 1 reimbursed | 1 inside window, 6 days left | Closing soon |
| LAMP-01  | 1 lost | 0 reimbursed | 0 inside window | Past 60 days |
```

A Lost_Outbound reimbursement on BOT-500 is not subtracted (outbound is a different event), and a
CustomerReturn reimbursement on MUG-BLUE is not subtracted either.
