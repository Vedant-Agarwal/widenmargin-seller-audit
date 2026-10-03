# Claim windows and automatic reimbursement — dated facts

**As of 2026-10-03.** Amazon changes these policies; check the current FBA inventory reimbursement
policy in Seller Central Help before relying on a date. Not legal advice.

| Fact | Date it took effect | Source |
|---|---|---|
| Claims for units lost or damaged in a fulfilment centre must be filed within **60 days** of the loss or damage being reported in Amazon's systems (the date on the Inventory Ledger row). Before this the window was **18 months**. | 23 October 2024 | [1], corroborated by [3] (thread title), [4], [5] |
| Amazon reimburses **most** units it loses or damages in its fulfilment centres **automatically**, without a claim. Sellers still report units that were never reimbursed, which is what this check looks for. | 1 November 2024 | [1], [2], corroborated by [4] |
| Reimbursements for inventory **not tied to a customer order** are based on the item's **manufacturing (sourcing) cost**, not what the item sells for. If Amazon has no cost on file for the product it uses its own estimate. | 31 March 2025 | [1], corroborated by [5] (which adds that manufacturing cost excludes shipping, handling and customs duties) |
| Inbound shipments and removal orders have their own windows under the same policy; this skill does not check them. | — | [1] |

How the `ledger-audit` script applies the 60-day rule (configurable guidance, not law): each
unit is dated from its own ledger event; reimbursed units cover the oldest events first; a unit
is "inside the window" while it is under 60 days old; a SKU is **closing** when any of its
remaining in-window units is 45+ days old, **expired** when none is under 60 days.

## Sources

1. WidenMargin, "Amazon FBA reimbursement claim deadlines" (updated 2026-09-29),
   https://widenmargin.com/resources/amazon-us/fba-reimbursement-claim-deadlines — the live guide
   this skill was built from. It states these dates without linking a primary Amazon page.
2. WidenMargin, "FBA lost & damaged inventory finder" FAQ (updated 2026-09-26),
   https://widenmargin.com/resources/amazon-us/fba-lost-damaged-inventory-finder
3. Amazon Seller Forums, "FBA inventory reimbursement policy changes from 23th of october",
   https://sellercentral.amazon.com/seller-forums/discussions/t/2de1ef2f-e299-486c-9466-48a885c3faef
   (Seller Central sign-in may be needed).
4. Helium 10, "Amazon FBA Inventory Reimbursement Policy Update",
   https://www.helium10.com/blog/amazon-fba-inventory-reimbursement-policy-update/ (modified 2024-10-01)
5. eComEngine, "Amazon FBA Reimbursement Policy Updates for 2025",
   https://www.ecomengine.com/blog/fba-reimbursement-policy (updated 2025-03-07)

Sources 3–5 are third-party corroboration checked on 2026-10-03; they are not cited on the live
WidenMargin guides. The primary source is Amazon's "FBA inventory reimbursement policy" page in
Seller Central Help (sign-in required).
