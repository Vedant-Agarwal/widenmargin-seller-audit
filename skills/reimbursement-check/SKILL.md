---
name: reimbursement-check
description: Summarises an Amazon US FBA Reimbursements report - totals by reason and by SKU with reversals netted, every Reimbursement_Reversal and whether the reimbursement it takes back is in the file, lines reimbursed below the seller's own unit cost, and (with an Inventory Ledger) which Lost_Warehouse / Damaged_Warehouse reimbursements line up with which ledger losses. Use when a seller asks what Amazon has reimbursed, to analyse or explain their reimbursements report or its reasons, whether reimbursements were too low or below cost, what a reversal or clawback is, or which reimbursements match their lost and damaged inventory, or uploads a Reimbursements report.
license: MIT
compatibility: Runs a bundled Python 3.8+ script (standard library only) on the uploaded files. Needs code execution; no network access or packages required.
metadata:
  author: Vedant Agarwal
  version: "0.1.0"
  facts-as-of: "2026-10-03"
---

# FBA reimbursements check

Summarise what Amazon has already reimbursed, flag lines reimbursed below the seller's own cost,
and match warehouse reimbursements to Inventory Ledger losses.

All figures come from `scripts/reimbursement_check.py`, a port of the WidenMargin reimbursements
analyser plus two additive checks. **Never compute, estimate or round these numbers yourself, and
never invent a number the script did not print.** If the script fails, say so and show its message.

## Step 1 — Get the files

Required: the **Reimbursements report**. Optional: the **Inventory Ledger (Detailed view)** for the
same dates, and the seller's **unit cost** — one figure for all SKUs and/or per SKU. Ask for their
*manufacturing (sourcing) cost*, which is what Amazon values non-order inventory at since 31 Mar 2025.

If a file is missing, ask for it with these steps (Seller Central menus as of 2026-10-03; labels can
change):

- **Reimbursements**: Seller Central → Reports → Fulfillment → Reimbursements → choose dates →
  download.
- **Inventory Ledger**: Seller Central → Reports → Fulfillment → Inventory Ledger → **Detailed
  view** → same dates → download.

## Step 2 — Run the script

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/reimbursement_check.py "REIMBURSEMENTS_FILE" --ledger "LEDGER_FILE" --unit-cost 6.50 --sku-cost "SKU-1=8.20" --sku-cost "SKU-2=3.10"
```

In claude.ai chat this skill's folder is copied into the sandbox, so the same script is at
`scripts/reimbursement_check.py` relative to this SKILL.md. Every option is optional; a per-SKU
cost overrides `--unit-cost` for that SKU. `--json` prints the same result as JSON.

If the script says the file "does not look like an Amazon FBA reimbursements report", show the
message and the "Columns found" list and ask for the right download.

## Step 3 — Present the result

Use the script's Markdown output; keep its numbers exactly:

1. **Totals** — net reimbursed (reversals included), reimbursements vs reversals, units.
2. **By reason** and **By SKU**. For what a reason means, use `references/reimbursement-reasons.md`;
   where it says Amazon publishes no definition, say exactly that rather than guessing.
3. **Reversals** — say whether each reversal's original is in the file.
4. **Below your unit cost** (only when a cost was given): present it as "reimbursed below the cost
   you gave", note any line that was later reversed, and that order-related or other reasons may be
   valued differently. Suggest checking the manufacturing cost Amazon has on file for those SKUs.
5. **Ledger match** (only with a ledger): SKUs with ledger losses not matched by warehouse
   reimbursements, and reimbursements beyond the ledger's dates. For claim-window dates per unit,
   suggest the `ledger-audit` skill; for refunds that were never returned, `returns-not-received`.

## Rules for wording

- This report shows what Amazon **has** reimbursed. It cannot show what is missing on its own.
- A gap against the seller's cost is "worth checking", never "Amazon owes you the difference".
- Dated facts with sources are in `references/valuation.md` and `references/reimbursement-reasons.md`:
  manufacturing-cost valuation since 31 Mar 2025 (Amazon uses its own estimate when it has no cost
  on file); reimbursements can take up to 5 days to appear; same-day reimbursements for one issue
  may be combined. Say they are as of 2026-10-03 and to confirm in Seller Central Help.
- Files are processed only inside this conversation's sandbox; the script makes no network calls.
- Not affiliated with Amazon. Not legal, tax or accounting advice.

## Example (bundled test fixtures, with `--unit-cost 6.5 --sku-cost MAT-GREY=8` and a ledger)

```
- Net reimbursed, reversals included: $23.50
- Reimbursements: $26.90 over 4 lines · Reversals: -$3.40 over 1 line
| 5550001 | MAT-GREY | Damaged_Warehouse | 1 unit | $7.10 per unit | your cost $8.00 | gap $0.90 |
| 5550002 | MUG-BLUE | Lost_Warehouse    | 2 units | $3.40 per unit | your cost $6.50 | gap $6.20 | reversed in part or in full |
| MUG-BLUE | ledger lost 4 | warehouse units reimbursed 1 (5550002, 5550005) | not reimbursed 3 |
```
