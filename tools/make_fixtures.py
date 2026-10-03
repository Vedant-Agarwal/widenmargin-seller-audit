#!/usr/bin/env python3
"""Write tests/fixtures/*. Most fixtures are ported 1:1 from the TypeScript vitest files in
shelfstack (agent-core/apps/web/src/lib/**.test.ts) so the parity check can run the same
scenarios through both implementations. A few extra realistic files are added (comma CSV with a
BOM and quoting, multiple settlement files, a demo set used for the README examples)."""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FX = os.path.join(ROOT, "tests", "fixtures")
os.makedirs(FX, exist_ok=True)


def tsv(rows):
    return "\n".join("\t".join(r) for r in rows)


def write(name, text):
    with open(os.path.join(FX, name), "w", encoding="utf-8", newline="") as f:
        f.write(text)


# ---------------------------------------------------------------- inventory ledger (parse.test.ts)
LEDGER_HEADER = ["Date", "FNSKU", "ASIN", "MSKU", "Title", "Event Type", "Reference ID", "Quantity",
                 "Fulfillment Center", "Disposition", "Reason", "Country", "Reconciled Quantity", "Unreconciled Quantity"]


def lrow(date, sku, ev, qty, disp, reason, unrec="0"):
    return [date, "X-" + sku, "B-" + sku, sku, "Widget " + sku, ev, "R1", qty, "PHX6", disp, reason, "US", "0", unrec]


write("ledger_real.tsv", tsv([
    LEDGER_HEADER,
    lrow("11/02/2025", "A", "Receipts", "100", "SELLABLE", ""),
    lrow("11/20/2025", "A", "Shipments", "-5", "SELLABLE", ""),
    lrow("12/15/2025", "A", "Adjustments", "-2", "SELLABLE", "M", "0"),
    lrow("01/10/2026", "A", "Adjustments", "-3", "SELLABLE", "M", "3"),
    lrow("02/01/2026", "A", "Adjustments", "2", "SELLABLE", "F"),
    lrow("02/03/2026", "A", "Adjustments", "-1", "SELLABLE", "E"),
    lrow("02/03/2026", "A", "Adjustments", "1", "WAREHOUSE_DAMAGED", "P"),
    lrow("02/05/2026", "B", "Adjustments", "-1", "SELLABLE", "H"),
    lrow("02/05/2026", "B", "Adjustments", "1", "CUSTOMER_DAMAGED", "P"),
    lrow("02/07/2026", "B", "Adjustments", "-2", "SELLABLE", "6"),
    lrow("02/08/2026", "B", "Adjustments", "-1", "UNSELLABLE", "D"),
    lrow("02/09/2026", "B", "Adjustments", "-1", "SELLABLE", "Q"),
    lrow("02/09/2026", "B", "Adjustments", "1", "DEFECTIVE", "P"),
    lrow("02/10/2026", "B", "Adjustments", "-4", "SELLABLE", "5"),
    lrow("02/11/2026", "B", "Adjustments", "-1", "SELLABLE", "Z"),
    lrow("02/12/2026", "B", "CustomerReturns", "1", "CUSTOMER_DAMAGED", ""),
]))

write("ledger_freetext.tsv", tsv([
    ["date", "fnsku", "asin", "msku", "title", "event-type", "quantity", "disposition", "reason"],
    ["2026-03-08", "X1", "B1", "SKU-A", "Widget A", "Adjustments", "-3", "SELLABLE", "Lost"],
    ["2026-03-10", "X2", "B2", "SKU-B", "Widget B", "Adjustments", "-2", "SELLABLE", "Damaged:Warehouse"],
    ["2026-03-11", "X2", "B2", "SKU-B", "Widget B", "Adjustments", "-1", "SELLABLE", "Damaged:Customer"],
    ["2026-03-12", "X2", "B2", "SKU-B", "Widget B", "Disposed", "-1", "UNSELLABLE", "Disposal"],
    ["2026-03-15", "X1", "B1", "SKU-A", "Widget A", "Found", "1", "SELLABLE", ""],
    ["2026-03-16", "X2", "B2", "SKU-B", "Widget B", "Adjustments", "1", "WAREHOUSE_DAMAGED", "Damaged:Warehouse"],
]))

write("not_a_report.csv", "name,value\nfoo,1\nbar,2\n")

# ---------------------------------------------------------------- reimbursements (parse.test.ts)
R_HEADER = ["approval-date", "reimbursement-id", "case-id", "amount-per-unit", "amount-total", "quantity-reimbursed-cash",
            "quantity-reimbursed-inventory", "quantity-reimbursed-total", "original-reimbursement-id",
            "original-reimbursement-type", "currency-unit", "sku", "fnsku", "asin", "product-name", "condition", "reason"]
R_ROWS = [
    ["2026-03-02", "R1", "C1", "12.50", "12.50", "1", "0", "1", "", "", "USD", "SKU-LOST", "X001", "B001", "Blue Widget", "Sellable", "Lost:Warehouse"],
    ["2026-03-05", "R2", "C2", "12.50", "25.00", "2", "0", "2", "", "", "USD", "SKU-DMG", "X002", "B002", "Red Gadget", "Sellable", "Damaged:Warehouse"],
    ["2026-03-09", "R3", "C3", "9.00", "9.00", "1", "0", "1", "", "", "USD", "SKU-LOST", "X001", "B001", "Blue Widget", "Sellable", "CustomerReturn"],
    ["2026-03-11", "R4", "C4", "3.20", "3.20", "0", "0", "0", "", "", "USD", "SKU-DMG", "X002", "B002", "Red Gadget", "Sellable", "FeeCorrection"],
    ["2026-03-14", "R5", "C1", "-12.50", "-12.50", "-1", "0", "-1", "R1", "REVERSAL_REIMBURSEMENT", "USD", "SKU-LOST", "X001", "B001", "Blue Widget", "Sellable", "Lost:Warehouse"],
]
write("reimb_full.tsv", tsv([R_HEADER] + R_ROWS))
write("reimb_full.csv", "\n".join(",".join(r) for r in [R_HEADER] + R_ROWS))

# ---------------------------------------------------------------- from-reimbursements.test.ts
FR_HEAD = ["approval-date", "reimbursement-id", "amount-total", "quantity-reimbursed-total", "original-reimbursement-id", "currency-unit", "sku", "reason"]
write("reimb_recovery_mixed.tsv", tsv([FR_HEAD,
    ["2026-03-02", "R1", "12.50", "2", "", "USD", "A", "Lost_Warehouse"],
    ["2026-03-03", "R2", "8.00", "1", "", "USD", "A", "Damaged_Warehouse"],
    ["2026-03-04", "R3", "9.00", "1", "", "USD", "A", "CustomerReturn"],
    ["2026-03-05", "R4", "5.00", "3", "", "USD", "A", "Lost_Inbound"],
    ["2026-03-06", "R5", "-6.25", "-1", "R1", "USD", "A", "Reimbursement_Reversal"],
    ["2026-03-07", "R6", "4.00", "1", "", "USD", "B", "Lost:Warehouse"],
]))
write("reimb_recovery_outbound.tsv", tsv([FR_HEAD,
    ["2026-03-02", "R1", "10.00", "2", "", "USD", "A", "Lost_Outbound"],
    ["2026-03-03", "R2", "10.00", "1", "", "USD", "A", "Damaged_Outbound"],
    ["2026-03-04", "R3", "10.00", "1", "", "USD", "A", "Lost_Warehouse"],
]))
write("reimb_recovery_reversals.tsv", tsv([FR_HEAD,
    ["2026-03-02", "R1", "10.00", "2", "", "USD", "A", "Lost_Warehouse"],
    ["2026-03-03", "R2", "9.00", "1", "", "USD", "A", "CustomerReturn"],
    ["2026-03-04", "R3", "-9.00", "-1", "R2", "USD", "A", "Reimbursement_Reversal"],
    ["2026-03-05", "R4", "-5.00", "-1", "R-not-in-file", "USD", "A", "Reimbursement_Reversal"],
]))
# The ledger test's end-to-end step: one unit reimbursed for SKU B.
write("reimb_ledger_b.tsv", tsv([FR_HEAD, ["2026-02-20", "RB1", "9.00", "1", "", "USD", "B", "Lost_Warehouse"]]))

# ---------------------------------------------------------------- recovery reconcile (reconcile.test.ts)
reconcile_cases = {
    "main": {
        "today": "2026-09-24",
        "unit_costs": {"SKU-A": 8, "SKU-C": 5},
        "losses": [
            {"date": "2026-09-01", "sku": "SKU-A", "asin": "B00A", "fnsku": "XA", "product_name": "Widget A", "category": "lost", "units": 5},
            {"date": "2026-09-01", "sku": "SKU-A", "asin": "B00A", "fnsku": "XA", "product_name": "Widget A", "category": "lost", "units": 3},
            {"date": "2026-09-10", "sku": "SKU-A", "asin": "B00A", "fnsku": "XA", "product_name": "Widget A", "category": "damaged", "units": 2},
            {"date": "2026-09-10", "sku": "SKU-B", "asin": "B00B", "fnsku": "XB", "product_name": "Widget B", "category": "damaged", "units": 4},
            {"date": "2026-07-31", "sku": "SKU-C", "asin": "B00C", "fnsku": "XC", "product_name": "Widget C", "category": "lost", "units": 2},
            {"date": "2024-06-01", "sku": "SKU-D", "asin": "B00D", "fnsku": "XD", "product_name": "Widget D", "category": "lost", "units": 1},
        ],
        "reimbursed": [{"sku": "SKU-A", "units": 4, "amount": 40}, {"sku": "SKU-B", "units": 4, "amount": 50}],
    },
    "old_hides_recent": {"today": "2026-09-24", "unit_costs": {}, "reimbursed": [],
                         "losses": [{"date": "2026-03-01", "sku": "S", "asin": "", "fnsku": "", "product_name": "", "category": "lost", "units": 2},
                                    {"date": "2026-09-10", "sku": "S", "asin": "", "fnsku": "", "product_name": "", "category": "lost", "units": 1}]},
    "fifo": {"today": "2026-09-24", "unit_costs": {}, "reimbursed": [{"sku": "S", "units": 1, "amount": 5}],
             "losses": [{"date": "2026-09-01", "sku": "S", "asin": "", "fnsku": "", "product_name": "", "category": "lost", "units": 1},
                        {"date": "2026-08-05", "sku": "S", "asin": "", "fnsku": "", "product_name": "", "category": "lost", "units": 1}]},
    "closing": {"today": "2026-09-24", "unit_costs": {}, "reimbursed": [],
                "losses": [{"date": "2026-08-05", "sku": "S", "asin": "", "fnsku": "", "product_name": "", "category": "lost", "units": 1}]},
    "expired": {"today": "2026-09-24", "unit_costs": {}, "reimbursed": [],
                "losses": [{"date": "2026-07-01", "sku": "S", "asin": "", "fnsku": "", "product_name": "", "category": "lost", "units": 1}]},
    "boundary_day_45_and_60": {"today": "2026-09-24", "unit_costs": {}, "reimbursed": [],
                               "losses": [{"date": "2026-08-10", "sku": "D45", "asin": "", "fnsku": "", "product_name": "", "category": "lost", "units": 1},
                                          {"date": "2026-08-11", "sku": "D44", "asin": "", "fnsku": "", "product_name": "", "category": "lost", "units": 1},
                                          {"date": "2026-07-26", "sku": "D60", "asin": "", "fnsku": "", "product_name": "", "category": "lost", "units": 1},
                                          {"date": "2026-07-27", "sku": "D59", "asin": "", "fnsku": "", "product_name": "", "category": "lost", "units": 1}]},
}
write("reconcile_cases.json", json.dumps(reconcile_cases, indent=2) + "\n")

# ---------------------------------------------------------------- returns (fba-returns/reconcile.test.ts)
S_HEAD = ["settlement-id", "settlement-start-date", "settlement-end-date", "deposit-date", "total-amount", "currency", "transaction-type",
          "order-id", "merchant-order-id", "adjustment-id", "shipment-id", "marketplace-name", "amount-type", "amount-description", "amount",
          "fulfillment-id", "posted-date", "order-item-code", "merchant-order-item-id", "merchant-adjustment-item-id", "sku",
          "quantity-purchased", "promotion-id"]
S_SUMMARY = ["S1", "2026-05-01", "2026-09-20", "2026-09-22", "100.00", "USD"] + [""] * 17
S_LINES = [
    ["S1", "", "", "", "", "USD", "Refund", "O-1", "", "A1", "", "Amazon.com", "ItemPrice", "Principal", "-20.00", "AFN", "2026-06-26", "", "", "", "MUG", "", ""],
    ["S1", "", "", "", "", "USD", "Refund", "O-1", "", "A1", "", "Amazon.com", "ItemFees", "Commission", "2.40", "AFN", "2026-06-26", "", "", "", "MUG", "", ""],
    ["S1", "", "", "", "", "USD", "Refund", "O-2", "", "A2", "", "Amazon.com", "ItemPrice", "Principal", "-15.00", "AFN", "2026-06-20", "", "", "", "MAT", "", ""],
    ["S1", "", "", "", "", "USD", "Refund", "O-3", "", "A3", "", "Amazon.com", "ItemPrice", "Principal", "-12.00", "AFN", "2026-06-15", "", "", "", "BOT", "", ""],
    ["S1", "", "", "", "", "USD", "Refund", "O-4", "", "A4", "", "Amazon.com", "ItemPrice", "Principal", "-9.00", "AFN", "2026-09-04", "", "", "", "BOT", "", ""],
    ["S1", "", "", "", "", "USD", "Refund", "O-5", "", "A5", "", "Amazon.com", "ItemPrice", "Principal", "-9.00", "AFN", "2026-03-08", "", "", "", "BOT", "", ""],
    ["S1", "", "", "", "", "USD", "Refund", "O-6", "", "A6", "", "Amazon.com", "ItemPrice", "Principal", "-30.00", "MFN", "2026-06-26", "", "", "", "MUG", "", ""],
    ["S1", "", "", "", "", "USD", "Order", "O-7", "", "", "", "Amazon.com", "ItemPrice", "Principal", "25.00", "AFN", "2026-06-01", "", "", "", "MUG", "1", ""],
]
write("settlement_returns.tsv", tsv([S_HEAD, S_SUMMARY] + S_LINES))
# The same lines split across two settlement files (multiple-file input).
write("settlement_part1.tsv", tsv([S_HEAD, ["S1", "2026-05-01", "2026-06-30", "2026-07-02", "60.00", "USD"] + [""] * 17] + [l for l in S_LINES if l[16] < "2026-07-01"]))
write("settlement_part2.tsv", tsv([S_HEAD, ["S2", "2026-07-01", "2026-09-20", "2026-09-22", "40.00", "USD"] + [""] * 17]
                                  + [["S2"] + l[1:] for l in S_LINES if l[16] >= "2026-07-01"]))

write("returns.tsv", tsv([
    ["return-date", "order-id", "sku", "asin", "fnsku", "product-name", "quantity", "fulfillment-center-id", "detailed-disposition",
     "reason", "status", "license-plate-number", "customer-comments"],
    ["2026-07-01T10:00:00+00:00", "O-2", "MAT", "B2", "X2", "Mat", "1", "PHX6", "SELLABLE", "NOT_AS_DESCRIBED", "Unit returned to inventory", "LPN1", ""],
]))
write("returns_empty.tsv", "return-date\torder-id\tsku\tasin\tfnsku\tproduct-name\tquantity\n")

RM_HEAD = ["approval-date", "reimbursement-id", "case-id", "amazon-order-id", "reason", "sku", "fnsku", "asin", "product-name", "condition",
           "currency-unit", "amount-per-unit", "amount-total", "quantity-reimbursed-cash", "quantity-reimbursed-inventory",
           "quantity-reimbursed-total", "original-reimbursement-id", "original-reimbursement-type"]
write("reimb_returns.tsv", tsv([RM_HEAD,
    ["2026-08-01", "R1", "", "O-3", "CustomerReturn", "BOT", "X3", "B3", "Bottle", "", "USD", "6.00", "6.00", "1", "0", "1", "", ""]]))

write("settlement_o9.tsv", tsv([S_HEAD,
    ["S1", "2026-05-01", "2026-09-20", "2026-09-22", "1.00", "USD"] + [""] * 17,
    ["S1", "", "", "", "", "USD", "Refund", "O-9", "", "A9", "", "Amazon.com", "ItemPrice", "Principal", "-20.00", "AFN", "2026-06-26", "", "", "", "MUG", "", ""]]))
write("reimb_o9_fee.tsv", tsv([RM_HEAD,
    ["2026-08-01", "R1", "", "O-9", "UnplannedServiceFee", "MUG", "X", "B", "Mug", "", "USD", "1.00", "1.00", "1", "0", "1", "", ""]]))
write("reimb_o9_customer.tsv", tsv([RM_HEAD,
    ["2026-08-01", "R1", "", "O-9", "CustomerReturn", "MUG", "X", "B", "Mug", "", "USD", "6.00", "6.00", "1", "0", "1", "", ""]]))
write("reimb_o9_reversed.tsv", tsv([RM_HEAD,
    ["2026-08-01", "R1", "", "O-9", "CustomerReturn", "MUG", "X", "B", "Mug", "", "USD", "6.00", "6.00", "1", "0", "1", "", ""],
    ["2026-08-09", "R2", "", "O-9", "Reimbursement_Reversal", "MUG", "X", "B", "Mug", "", "USD", "-6.00", "-6.00", "-1", "0", "-1", "R1", ""]]))

# ---------------------------------------------------------------- settlement parser (parse.test.ts)
write("settlement_in_awkward.tsv",
      "﻿"
      "Settlement report for seller A1SAMPLE\n"
      "Generated 2026-09-01\n"
      "\n"
      "settlement-id\tsettlement-start-date\tsettlement-end-date\tdeposit-date\ttotal-amount\tcurrency\ttransaction-type\torder-id\tamount-type\tamount-description\tamount\tposted-date\tsku\tquantity-purchased\n"
      "9001\t2026-08-04\t2026-08-17\t2026-08-19\t660.00\tINR\t\t\t\t\t\t\t\t\n"
      "\n"
      "\tX\tX\tX\t\t\tOrder\t403-1\tItemPrice\tPrincipal\t1,000.00\t2026-08-05\tMAT-1\t1\n"
      "\t\t\t\t\t\tOrder\t403-1\tItemFees\tCommission\t(90.00)\t2026-08-05\tMAT-1\t1\n"
      "\t\t\t\t\t\tOrder\t403-1\tItemFees\tFBAPerUnitFulfillmentFee\t-250.00\t2026-08-05\tMAT-1\t1\n")
write("settlement_us_quoted.csv",
      'settlement-id,settlement-start-date,settlement-end-date,deposit-date,total-amount,currency,transaction-type,order-id,amount-type,amount-description,amount,posted-date,sku,quantity-purchased\r\n'
      '"7001","2026-08-04","2026-08-17","2026-08-19","31.50","USD","","","","","","","",""\r\n'
      '"7001","","","","","USD","Order","112-1","ItemPrice","Principal","49.99","2026-08-05","BOTTLE, 750ml","1"\r\n'
      '"7001","","","","","USD","Order","112-1","ItemFees","Commission","-7.49","2026-08-05","BOTTLE, 750ml","1"\r\n'
      '"7001","","","","","USD","other-transaction","","other-transaction","Storage Fee ""August""","-11.00","2026-08-17","",""\r\n')
write("settlement_v1.tsv",
      "settlement-id\tsettlement-start-date\tcurrency\ttransaction-type\torder-id\titem-related-fee-type\titem-related-fee-amount\tshipment-fee-type\tshipment-fee-amount\torder-fee-type\n"
      "5001\t2026-08-04\tUSD\tOrder\t112-1\tCommission\t-7.49\tShippingHB\t-1.00\t\n")
write("settlement_unparsable.tsv", "settlement-id\tamount-type\tamount-description\tamount\n1\tItemPrice\tPrincipal\t10.00\n1\tItemFees\tCommission\tn/a\n")
one = "settlement-id\tamount-type\tamount-description\tamount\n1\tItemPrice\tPrincipal\t10.00\n"
write("settlement_concatenated.tsv", one + one)

# ---------------------------------------------------------------- extra realistic files (not in the TS tests)
# Comma CSV, BOM, CRLF, a quoted title containing a comma and quotes, "Date and Time" ISO column,
# lowercase reason codes, and a year boundary. Used by the demo/README examples.
write("demo_ledger.csv", "﻿" + "\r\n".join([
    "Date,Date and Time,FNSKU,ASIN,MSKU,Title,Event Type,Reference ID,Quantity,Fulfillment Center,Disposition,Reason,Country,Reconciled Quantity,Unreconciled Quantity",
    '07/01/2026,2026-07-01T09:12:00-07:00,X00MUG01,B0MUG00001,MUG-BLUE,"Blue Mug, 12oz ""Classic""",Receipts,FBA15ABC,200,PHX6,SELLABLE,,US,200,0',
    '07/20/2026,2026-07-20T11:00:00-07:00,X00MUG01,B0MUG00001,MUG-BLUE,"Blue Mug, 12oz ""Classic""",Adjustments,9876543210,-2,PHX6,SELLABLE,M,US,0,2',
    '08/25/2026,2026-08-25T14:30:00-07:00,X00MUG01,B0MUG00001,MUG-BLUE,"Blue Mug, 12oz ""Classic""",Adjustments,9876543311,-3,PHX6,SELLABLE,m,US,0,3',
    '09/05/2026,2026-09-05T08:00:00-07:00,X00MUG01,B0MUG00001,MUG-BLUE,"Blue Mug, 12oz ""Classic""",Adjustments,9876543400,1,PHX6,SELLABLE,F,US,1,0',
    '08/10/2026,2026-08-10T10:00:00-07:00,X00MAT02,B0MAT00002,MAT-GREY,Grey Yoga Mat,Adjustments,9876543500,-2,LGB8,SELLABLE,E,US,0,0',
    '08/10/2026,2026-08-10T10:00:00-07:00,X00MAT02,B0MAT00002,MAT-GREY,Grey Yoga Mat,Adjustments,9876543500,2,LGB8,WAREHOUSE_DAMAGED,P,US,0,0',
    '09/02/2026,2026-09-02T10:00:00-07:00,X00MAT02,B0MAT00002,MAT-GREY,Grey Yoga Mat,Adjustments,9876543600,-1,LGB8,SELLABLE,H,US,0,0',
    '09/02/2026,2026-09-02T10:00:00-07:00,X00MAT02,B0MAT00002,MAT-GREY,Grey Yoga Mat,Adjustments,9876543600,1,LGB8,CUSTOMER_DAMAGED,P,US,0,0',
    '09/24/2026,2026-09-24T16:45:00-07:00,X00BOT03,B0BOT00003,BOT-500,Steel Bottle 500ml,Adjustments,9876543700,-4,ONT8,SELLABLE,5,US,0,4',
    '09/26/2026,2026-09-26T16:45:00-07:00,X00BOT03,B0BOT00003,BOT-500,Steel Bottle 500ml,Adjustments,9876543800,-1,ONT8,SELLABLE,6,US,0,0',
    '06/01/2026,2026-06-01T12:00:00-07:00,X00LMP04,B0LMP00004,LAMP-01,Desk Lamp,Adjustments,9876543900,-1,SBD1,SELLABLE,M,US,0,1',
    "",
]))
write("demo_reimbursements.tsv", tsv([
    ["approval-date", "reimbursement-id", "case-id", "amazon-order-id", "reason", "sku", "fnsku", "asin", "product-name", "condition",
     "currency-unit", "amount-per-unit", "amount-total", "quantity-reimbursed-cash", "quantity-reimbursed-inventory",
     "quantity-reimbursed-total", "original-reimbursement-id", "original-reimbursement-type"],
    ["2026-08-15T07:00:00+00:00", "5550001", "", "", "Damaged_Warehouse", "MAT-GREY", "X00MAT02", "B0MAT00002", "Grey Yoga Mat", "New", "USD", "7.10", "7.10", "1", "0", "1", "", ""],
    ["2026-08-02T07:00:00+00:00", "5550002", "", "", "Lost_Warehouse", "MUG-BLUE", "X00MUG01", "B0MUG00001", "Blue Mug", "New", "USD", "3.40", "6.80", "2", "0", "2", "", ""],
    ["2026-09-12T07:00:00+00:00", "5550003", "", "114-1234567-1234567", "CustomerReturn", "MUG-BLUE", "X00MUG01", "B0MUG00001", "Blue Mug", "New", "USD", "9.00", "9.00", "1", "0", "1", "", ""],
    ["2026-09-01T07:00:00+00:00", "5550004", "", "", "Lost_Outbound", "BOT-500", "X00BOT03", "B0BOT00003", "Steel Bottle", "New", "USD", "4.00", "4.00", "1", "0", "1", "", ""],
    ["2026-09-20T07:00:00+00:00", "5550005", "", "", "Reimbursement_Reversal", "MUG-BLUE", "X00MUG01", "B0MUG00001", "Blue Mug", "New", "USD", "-3.40", "-3.40", "-1", "0", "-1", "5550002", "Lost_Warehouse"],
]))
print("fixtures written to", os.path.relpath(FX, ROOT))
