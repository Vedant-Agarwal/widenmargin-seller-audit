# Reimbursements report: reasons and columns

**As of 2026-10-03.** Amazon's public report documentation lists the columns but not what each
reason means, so a meaning is given only where a published source states one. If a file shows a
reason that is not listed, treat it as unexplained and look at the reimbursement in Seller Central.

| Reason | Meaning (where a source states one) | Offsets a warehouse loss in ledger-audit? |
|---|---|---|
| Lost_Warehouse | A unit lost while it was stored in an Amazon warehouse. | Yes |
| Damaged_Warehouse | A unit damaged while it was stored in an Amazon warehouse. | Yes |
| Lost_Outbound | A unit lost after it left the Amazon warehouse. | No |
| Damaged_Outbound | Amazon doesn't publish a definition for this one. | No |
| Lost_Inbound | Amazon doesn't publish a definition for this one. | No |
| Damaged_Inbound | Amazon doesn't publish a definition for this one. | No |
| CustomerReturn | A customer was refunded but the item did not come back to the warehouse in the time allowed, so Amazon reimbursed you. If the item arrives later in sellable condition, Amazon may take the reimbursement back. | No (used by returns-not-received) |
| CustomerServiceIssue | Amazon covering a service problem on its side — for example damage in transit or a delivery that didn't arrive on time. | No (used by returns-not-received) |
| FeeCorrection | Amazon doesn't publish a definition for this one. | No |
| Reimbursement_Reversal | Amazon taking back an earlier reimbursement — e.g. a unit reimbursed as lost was later found, or a refunded customer did return the item. original-reimbursement-id and original-reimbursement-type point at the reimbursement being reversed. | Only if it reverses a warehouse line |
| GeneralAdjustment | Amazon doesn't publish a definition for this one. | No |
| Payment_Retraction | Amazon doesn't publish a definition for this one. | No |
| ReturnAdjustment | Amazon doesn't publish a definition for this one. | No |
| UnplannedServiceFee | Amazon doesn't publish a definition for this one. | No |

Older files spell the warehouse reasons `Lost:Warehouse` / `Damaged:Warehouse`; any separator and
any case is accepted.

## Columns (SP-API `GET_FBA_REIMBURSEMENTS_DATA`, Amazon's order)

| Column | What it holds |
|---|---|
| approval-date | The date Amazon approved the reimbursement. |
| reimbursement-id | Amazon's ID for the reimbursement. One reimbursement can have several line items. |
| case-id | The case ID when you asked through a case. Reimbursements Amazon makes on its own have none. |
| amazon-order-id | The customer order it relates to; empty when not order-related. |
| reason | Why Amazon reimbursed you (table above). |
| sku / fnsku / asin / product-name | The item. |
| condition | Condition of the reimbursed inventory. |
| currency-unit | Currency of the amounts on the row. |
| amount-per-unit | The reimbursement for a single unit. |
| amount-total | Total cash reimbursed for all units on the line. |
| quantity-reimbursed-cash | Units reimbursed in cash. |
| quantity-reimbursed-inventory | Units reimbursed as inventory instead of cash. |
| quantity-reimbursed-total | All units on the line — cash plus inventory. |
| original-reimbursement-id | On a reversal, the reimbursement being reversed. |
| original-reimbursement-type | On a reversal, the reason of the reimbursement being reversed. |

How the script totals: net = every amount-total added (reversals included); a line is a reversal
when it has an original-reimbursement-id or a negative amount; by-reason and by-SKU totals net each
reversal against the reason/SKU on its own line; units = quantity-reimbursed-total (whole units).

Also from the same sources: the report is tab-delimited and updated daily; it includes
reimbursements you asked for and ones Amazon made on its own; reimbursements can take up to five
days to appear after approval; several reimbursements processed the same day for the same issue may
be combined into one amount; when more than one unit is tied to a customer refund Amazon does not
give unit-level detail.

## Sources

WidenMargin, "Amazon FBA reimbursement report reasons explained" (updated 2026-10-02),
https://widenmargin.com/resources/amazon-us/fba-reimbursement-report-reasons — which cites:
- Amazon SP-API report type values (FBA), https://developer-docs.amazon.com/sp-api/docs/report-type-values-fba
- SellerLegend, "The Reimbursements Screen", https://docs.sellerlegend.com/knowledgebase/the-reimbursements-screen/
- SellerSpace, "Reimbursement Report", https://www.sellerspace.com/en-US/help/doc/amazon-reimbursements-report-use-guide/
- Revstep, "Amazon reimbursements and reversals", https://revstep.com/us/amazon-reimbursements-and-reversals/
- Gorilla ROI, "FBA Reimbursement Details report", https://www.gorillaroi.com/amazon-seller-central-reports/reimburse-details
