# Report columns the returns-not-received script reads

**As of 2026-10-03.** Names are matched case-insensitively; spaces, underscores and hyphens are the
same. Extra columns are ignored. Tab/comma/semicolon/pipe, BOM, preamble, quoting, "(1.00)"
negatives and repeated headers are handled.

## Settlement report — Flat File V2

Seller Central → Reports → Payments → All Statements → "Download Flat File V2" (tab-separated
.txt). Columns read: settlement-id, settlement-start-date, settlement-end-date, deposit-date,
total-amount, currency, transaction-type, order-id, adjustment-id, marketplace-name, amount-type,
amount-description, amount, fulfillment-id, posted-date (or posted-date-time), sku,
quantity-purchased. Typical files also carry merchant-order-id, shipment-id, order-item-code,
merchant-order-item-id, merchant-adjustment-item-id and promotion-id (ignored).

- Required: **settlement-id, amount-type, amount-description, amount**.
- The older Flat File V1 layout (item-related-fee-type, shipment-fee-amount …) is recognised and
  refused with a message to download V2 instead.
- A blank settlement-id, currency or date on a line inherits the last non-blank value above it.
- Several files (each settlement covers about two weeks) are parsed one by one and their lines
  combined. Cover at least the last 4 months so day 60 to 120 is inside the files.

Sources: Amazon Seller Central, "How do I read my Payments report?",
https://sellercentral.amazon.com/gp/help/external/14921 and "Payments Summary",
https://sellercentral.amazon.com/gp/help/external/G200913190 (sign-in may be needed), as cited on
https://widenmargin.com/resources/amazon-us/settlement-report-analyser (updated 2026-09-23).

## Customer Returns report

SP-API `GET_FBA_FULFILLMENT_CUSTOMER_RETURNS_DATA`, in Amazon's order: return-date, order-id, sku,
asin, fnsku, product-name, quantity, fulfillment-center-id, detailed-disposition, reason, status,
license-plate-number, customer-comments. Required: **order-id, sku**. A row with no order-id is
skipped; a blank quantity counts as 1.

Source: https://widenmargin.com/resources/amazon-us/fba-customer-returns-dispositions (updated
2026-10-02), citing https://developer-docs.amazon.com/sp-api/docs/report-type-values-fba

## Reimbursements report

SP-API `GET_FBA_REIMBURSEMENTS_DATA`: approval-date, reimbursement-id, case-id, amazon-order-id,
reason, sku, fnsku, asin, product-name, condition, currency-unit, amount-per-unit, amount-total,
quantity-reimbursed-cash, quantity-reimbursed-inventory, quantity-reimbursed-total,
original-reimbursement-id, original-reimbursement-type. Required: **reimbursement-id,
amount-total**; this check also needs **amazon-order-id** and **reason** to match orders.

Source: https://widenmargin.com/resources/amazon-us/fba-reimbursement-report-reasons (updated
2026-10-02), citing https://developer-docs.amazon.com/sp-api/docs/report-type-values-fba
