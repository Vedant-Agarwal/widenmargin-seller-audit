# Report columns the ledger-audit script reads

**As of 2026-10-03.** Column names are matched case-insensitively; spaces, underscores and hyphens
are treated the same ("Event Type" = "event-type" = "event_type"). Extra columns are ignored.
Tab-, comma-, semicolon- and pipe-separated files, a UTF-8 BOM, a preamble above the header,
quoted fields, "(1.00)" accounting negatives and repeated header rows from concatenated files are
all handled.

## Inventory Ledger — Detailed view

Seller Central download / SP-API `GET_LEDGER_DETAIL_VIEW_DATA`. Columns: Date, Date and Time, FNSKU,
ASIN, MSKU, Title, Event Type, Reference ID, Quantity, Fulfillment Center, Disposition, Reason,
Country, Reconciled Quantity, Unreconciled Quantity.

- Required: **Event Type**, **Quantity**. Without **Reason** the file is read from event types alone
  (a warning says so).
- Date is MM/DD/YYYY; Date and Time is ISO 8601 and wins when present. Both become YYYY-MM-DD.
- SKU = MSKU (or sku / merchant-sku), else FNSKU, else ASIN.
- Reference ID and Fulfillment Center are carried into the draft case messages.

Sources: Amazon SP-API report type values (FBA),
https://developer-docs.amazon.com/sp-api/docs/report-type-values-fba ; Amazon, "Inventory Ledger
report", https://sellercentral.amazon.com/help/hub/reference/external/G4FKT5KQWFFJ7LDN?locale=en-US

## Reimbursements report

SP-API `GET_FBA_REIMBURSEMENTS_DATA`, in Amazon's order: approval-date, reimbursement-id, case-id,
amazon-order-id, reason, sku, fnsku, asin, product-name, condition, currency-unit, amount-per-unit,
amount-total, quantity-reimbursed-cash, quantity-reimbursed-inventory, quantity-reimbursed-total,
original-reimbursement-id, original-reimbursement-type.

- Required: **reimbursement-id**, **amount-total**.
- Only `Lost_Warehouse` / `Damaged_Warehouse` lines (any separator or case, e.g. `Lost:Warehouse`),
  net of reversals of those, offset ledger losses. Units = quantity-reimbursed-total.
- A reversal (a line with original-reimbursement-id, or a negative amount) counts only when the
  reimbursement it takes back is a warehouse one — found by its id in the same file, or by the
  reversal line's own reason. A reversal whose original is not in the file is left out.

Sources: WidenMargin, "Amazon FBA reimbursement report reasons explained" (updated 2026-10-02),
https://widenmargin.com/resources/amazon-us/fba-reimbursement-report-reasons ; Amazon SP-API report
type values (FBA), https://developer-docs.amazon.com/sp-api/docs/report-type-values-fba
