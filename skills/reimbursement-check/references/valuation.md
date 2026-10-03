# How Amazon values a reimbursement — dated facts

**As of 2026-10-03.** Not legal or tax advice; check Amazon's current FBA inventory reimbursement
policy in Seller Central Help.

| Fact | Date | Source |
|---|---|---|
| Reimbursements for inventory **not tied to a customer order** (for example, units lost or damaged in a fulfilment centre) are based on the item's **manufacturing (sourcing) cost**, not what the item sells for. | 31 March 2025 | [1], corroborated by [3] |
| If Amazon has no cost on file for the product it uses its own estimate, so keeping unit costs up to date in Seller Central matters. | 31 March 2025 | [1] |
| Manufacturing cost is the amount needed to source or produce the item; it excludes shipping, handling, customs duties and other costs. | — | [3] |
| Since 1 November 2024 Amazon reimburses most fulfilment-centre losses automatically; since 23 October 2024 claims for the ones it misses must be filed within 60 days. | — | [1], [2] |

How the `reimbursement-check` script uses this: when you give a cost, it divides each line's
amount-total by quantity-reimbursed-cash (or quantity-reimbursed-total when the cash column is
absent) and lists lines whose per-unit amount is below **your** cost. Give your manufacturing
(sourcing) cost — not landed cost or what the item sells for — for a like-for-like comparison. The
script treats Lost/Damaged _Warehouse and _Inbound reasons as inventory not tied to an order (its
own reading, not an Amazon statement); every other reason is marked "order-related or other reason —
valuation may differ". A gap is something to check, not an amount owed.

## Sources

1. WidenMargin, "Amazon FBA reimbursement claim deadlines" (updated 2026-09-29),
   https://widenmargin.com/resources/amazon-us/fba-reimbursement-claim-deadlines
2. WidenMargin, "FBA lost & damaged inventory finder" (updated 2026-09-26),
   https://widenmargin.com/resources/amazon-us/fba-lost-damaged-inventory-finder
3. eComEngine, "Amazon FBA Reimbursement Policy Updates for 2025" (updated 2025-03-07),
   https://www.ecomengine.com/blog/fba-reimbursement-policy — third-party, checked 2026-10-03; not
   cited on the live WidenMargin guides.
