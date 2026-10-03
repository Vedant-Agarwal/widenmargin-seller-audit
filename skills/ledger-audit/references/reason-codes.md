# Inventory Ledger reason codes

**As of 2026-10-03.** This is the same table the `ledger-audit` script uses (`REASON_CODES` in
`scripts/wm_audit_core.py`), so the explanation and the arithmetic cannot disagree.

Source: WidenMargin, "Amazon Inventory Ledger reason codes explained" (updated 2026-09-29),
https://widenmargin.com/resources/amazon-us/inventory-ledger-reason-codes — built from Amazon's
published inventory-adjustment code definitions. About the report itself: Amazon, "Inventory Ledger
report", https://sellercentral.amazon.com/help/hub/reference/external/G4FKT5KQWFFJ7LDN?locale=en-US
and "How to find the information you need",
https://sellercentral.amazon.com/help/hub/reference/external/GCRWH2T93NYDHBXU?locale=en-US (Seller
Central sign-in may be needed). The codes have not been validated against a large set of real
sellers' files, which is why every run prints how each code in *your* file was treated.

| Code | What it means | Amazon's fault? | How the check treats it |
|---|---|---|---|
| M | Missing from a bin location (lost) | Yes | Counted as lost |
| 5 | Missing from a bin location (lost) | Yes | Counted as lost |
| F | Missing inventory found | Cancels an earlier loss | Subtracted from that SKU's lost units, oldest loss first |
| N | Transferred in from an incorrectly assigned FNSKU | Cancels an earlier loss | Subtracted, as F |
| E | Damaged at an Amazon fulfilment centre | Yes | Counted as damaged |
| 6 | Carrier-damaged | Sometimes | Shown for review, never counted |
| D | Disposed of | Sometimes | Shown for review, never counted |
| H | Customer-damaged | No | Not counted |
| K | Defective | No | Not counted |
| U | Distributor-damaged | No | Not counted |
| 7 | Expired | No | Not counted |
| Q | Disposition change (removed) | No | Not counted |
| P | Disposition change (re-added) | No | Not counted (the removal side is the event) |
| 3 | Product redefinition — transfer in | No | Not counted |
| 4 | Product redefinition — transfer out | No | Not counted |
| O | Transferred out (mis-received or already reimbursed) | No | Not counted |

## Codes that come in pairs

A change of condition is two rows: a removal (Q, E, 6, 7, H, K or U) and a matching **P** that adds
the same unit back under its new condition. Only the removal is counted, never both. An **M** or
**5** followed later by an **F** or **N** for the same SKU means the unit was found: nothing is
claimable for it. Found units are netted against the SKU's oldest lost units first; damaged (E)
units are never offset by found units.

## Codes the table does not know

A code not listed above (for example `Z`) is reported as "Unrecognised reason" and left out. Where the
Reason column holds free text instead of a code (older exports), a conservative keyword fallback is
used on decreases only (lost/misplaced/missing → lost, damag… → damaged, dispos/destroy → review),
never for customer, carrier, distributor, defective or expired wording. Lowercase codes (`m`, `e`)
are read as their uppercase code.
