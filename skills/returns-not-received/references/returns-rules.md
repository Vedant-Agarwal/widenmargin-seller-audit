# Refunded-but-not-returned: dated facts and how the check reads them

**As of 2026-10-03.** Amazon changes these policies; check the current FBA reimbursement policy in
Seller Central Help before relying on a date. Not legal advice.

## The window

| Fact | Source |
|---|---|
| When a customer is refunded and the item is not returned, Amazon **normally reimburses on its own at around day 45** after the refund. | [1], [2] |
| If it does not, a claim can be filed **from day 60 to day 120 after the refund** — not before day 60, not after day 120. | [1], [2] |
| Amazon sometimes refunds a customer **without asking for the item back**; those refunds never appear in the Customer Returns report. | [2] |
| A return appears in the Customer Returns report only once a fulfilment centre has received and processed it; `return-date` is the processing date, not the day the customer asked. | [2] |

How the `returns-not-received` script applies it (configurable guidance, not law): age = whole days
from the refund's posted date to today. Under 60 days → **wait** (shows the date claims open);
60 to 120 days inclusive → **claim now** (shows the last day, refund + 120); over 120 → **too late**.

## What counts as returned or reimbursed

- **Refunds**: settlement report lines whose transaction-type contains "Refund", with an order-id and
  sku, fulfilled by Amazon (`fulfillment-id` = AFN, or the column absent). Seller-fulfilled (MFN)
  refunds are skipped and counted. One case per order-id + sku; units = the largest
  quantity-purchased on its lines (1 if none); principal refunded = minus the sum of lines whose
  amount-description contains "Principal".
- **Returned**: Customer Returns rows with the same order-id + sku, any disposition. For DAMAGED and
  CARRIER_DAMAGED returns Amazon compensates under its reimbursement policy, so look for that in the
  Reimbursements report separately.
- **Reimbursed**: Reimbursements rows on the same amazon-order-id + sku whose reason contains
  "Customer" (CustomerReturn, CustomerServiceIssue). A fee line such as UnplannedServiceFee does not
  clear a refund. A Reimbursement_Reversal counts (as negative units) only when it takes back one of
  those customer reimbursements.
- **Missing** = refunded − returned − reimbursed, floored at 0. Only missing > 0 is listed.

## Return dispositions (Customer Returns report, `detailed-disposition`)

| Code | Meaning | What happens |
|---|---|---|
| SELLABLE | Returned to stock and available for purchase. | Back in your sellable stock |
| DAMAGED | Amazon takes responsibility for the damage; ownership transfers to Amazon. | Amazon compensates you under its FBA inventory reimbursement policy |
| CUSTOMER_DAMAGED | Returned in unsellable condition (e.g. opened packaging); customer refunded. | Stays in your inventory as unsellable |
| DEFECTIVE | Obviously damaged or reported faulty; customer refunded. | Stays in your inventory as unsellable |
| CARRIER_DAMAGED | Amazon takes responsibility; ownership transfers to Amazon. | Amazon compensates you |
| EXPIRED | Within 50 days of expiry; may be set aside and eventually disposed of. | Stays as unsellable until disposed |

Statuses: "Unit returned to inventory"; "Reimbursed" (allow 5 days for it to post); "Pending
repackaging"; "Repackaged successfully". Some sources write codes with a space ("CUSTOMER DAMAGED").

## Sources

1. WidenMargin, "Amazon FBA reimbursement claim deadlines" (updated 2026-09-29),
   https://widenmargin.com/resources/amazon-us/fba-reimbursement-claim-deadlines
2. WidenMargin, "Amazon FBA customer returns dispositions explained" (updated 2026-10-02),
   https://widenmargin.com/resources/amazon-us/fba-customer-returns-dispositions — which cites:
   Amazon SP-API report type values (FBA), https://developer-docs.amazon.com/sp-api/docs/report-type-values-fba ;
   Openbridge, "FBA Customer Returns Report", https://docs.openbridge.com/en/articles/8135664-fba-customer-returns-report ;
   Sellercloud, "FBA returns and reimbursements", https://sellercloud.com/help/omnichannel-ecommerce/fba-returns-and-reimbursments/ ;
   Gorilla ROI, "Amazon FBA returns condition codes", https://www.gorillaroi.com/blog/amazon-fba-returns
3. WidenMargin, "FBA refunded-but-not-returned finder" (updated 2026-09-26),
   https://widenmargin.com/resources/amazon-us/fba-returns-not-received-finder

The live guides state the day-45 and day-60-to-120 rules without linking a primary Amazon page; the
primary source is Amazon's FBA reimbursement policy in Seller Central Help (sign-in required).
