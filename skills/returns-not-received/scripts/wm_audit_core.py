"""
WidenMargin Seller Audit - shared core (stdlib only, Python 3.8+).

A faithful Python port of the parsing and reconciliation logic in the WidenMargin web tools
(github.com/Vedant-Agarwal/shelfstack, agent-core/apps/web/src/lib/):

  settlement-report/parse.ts        -> normalise_column, parse_amount, split_records, parse_settlement_report
  fba-inventory-ledger/parse.ts     -> REASON_CODES, classify, to_iso_date, parse_inventory_ledger
  fba-recovery/reconcile.ts         -> reconcile
  fba-recovery/from-reimbursements.ts -> is_warehouse_loss_reason, reimbursed_units_for_recovery
  fba-reimbursements/parse.ts       -> parse_reimbursements
  fba-returns/parse.ts              -> parse_customer_returns
  fba-returns/reconcile.ts          -> find_unreturned_refunds

Same rules, same edge cases. Where this port carries extra detail (reference IDs, fulfilment
centres, source lines, settlement/adjustment IDs, amount-per-unit), it is additive: it never
changes a count, a total or a status that the TypeScript computes.

Pure functions: no network, no file writes. Reading a file from disk is done only by read_text().

THIS FILE IS COPIED INTO EVERY SKILL'S scripts/ FOLDER (each skill must be self-contained).
Edit src/wm_audit_core.py and run tools/sync_core.py; a test fails if the copies drift.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone

CORE_VERSION = "0.1.0"

# --------------------------------------------------------------------------------------------
# JavaScript-compatible primitives
# --------------------------------------------------------------------------------------------

# JavaScript's \s and String.prototype.trim() whitespace set (includes NBSP and the BOM).
JS_WS = "\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
_JS_S = "[\t\n\v\f\r \u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]"


def js_trim(s: str) -> str:
    return s.strip(JS_WS)


def js_round(x: float) -> int:
    """Math.round: halves round toward +infinity (Math.round(-2.5) == -2)."""
    return int(math.floor(x + 0.5))


DAY_SECONDS = 86400


def parse_iso_day(value: str):
    """Date for an ISO 'YYYY-MM-DD' (optionally followed by a time) as UTC midnight, else None.

    Mirrors `new Date("YYYY-MM-DD")` in JavaScript for the date strings the parsers produce.
    Anything that is not ISO is treated as unparseable (the TypeScript treats an invalid date as
    age 0; see tools/parity/NOTES.md for the one divergence on non-ISO free-text dates).
    """
    if not value:
        return None
    m = re.match(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})\Z", value)
    if not m:
        return None
    # V8 accepts day 29-31 in any month and rolls over ("2026-02-30" is 2 March), so do the same.
    return _rollover(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def days_between(a: datetime, b: datetime) -> int:
    """Math.floor((b - a) / DAY)."""
    delta = b - a
    return int(math.floor(delta.total_seconds() / DAY_SECONDS))


def today_utc(today=None) -> datetime:
    """`today` may be None (now), a 'YYYY-MM-DD' string, a date or a datetime."""
    if today is None:
        return datetime.now(timezone.utc)
    if isinstance(today, str):
        d = parse_iso_day(today)
        if d is None:
            raise ValueError("today must be YYYY-MM-DD, got %r" % today)
        return d
    if isinstance(today, datetime):
        return today if today.tzinfo else today.replace(tzinfo=timezone.utc)
    return datetime(today.year, today.month, today.day, tzinfo=timezone.utc)


def _rollover(year, month, day, hh=0, mm=0, ss=0):
    """V8-style calendar date: month 1-12 and day 1-31 accepted, day overflow rolls into the next
    month ("2026-02-30" is 2 March). Returns a UTC datetime or None."""
    if not (1 <= month <= 12 and 1 <= day <= 31) or year < 1 or hh > 24 or mm > 59 or ss > 59:
        return None
    return datetime(year, month, 1, tzinfo=timezone.utc) + timedelta(days=day - 1, hours=hh, minutes=mm, seconds=ss)


def js_date_parse(raw: str):
    """A small subset of Date.parse for report dates: ISO date / date-time, and M/D/YYYY.

    Returns a POSIX timestamp (float) or None. Used only to find the earliest/latest
    approval-date in a reimbursements report.
    """
    s = js_trim(raw)
    if not s:
        return None
    m = re.match(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})(?:[T ]([0-9]{2}):([0-9]{2})(?::([0-9]{2})(?:\.[0-9]+)?)?)?\s*(Z|UTC|[+-][0-9]{2}:?[0-9]{2})?\Z", s)
    if m:
        dt = _rollover(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0))
        if dt is None:
            return None
        tz = m.group(7)
        if tz and tz not in ("Z", "UTC"):
            sign = 1 if tz[0] == "+" else -1
            digits = tz[1:].replace(":", "")
            dt = dt - sign * timedelta(hours=int(digits[:2]), minutes=int(digits[2:]))
        return dt.timestamp()
    m = re.match(r"^([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})(?:\s+([0-9]{1,2}):([0-9]{2})(?::([0-9]{2}))?)?", s)
    if m:
        dt = _rollover(int(m.group(3)), int(m.group(1)), int(m.group(2)), int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0))
        return None if dt is None else dt.timestamp()
    return None


# --------------------------------------------------------------------------------------------
# Reading files
# --------------------------------------------------------------------------------------------


def read_text(path: str) -> str:
    """Read a report file as text. UTF-8 (BOM kept, the parsers strip it), UTF-16 with a BOM,
    or Windows-1252 as a last resort (some Seller Central exports with product titles)."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


# --------------------------------------------------------------------------------------------
# settlement-report/parse.ts - CSV primitives
# --------------------------------------------------------------------------------------------

_RE_WRAPPING_QUOTES = re.compile(r'^"([\s\S]*)"\Z')
_RE_SPACES_UNDERSCORES = re.compile("(?:" + _JS_S + "|_)+")
_RE_HYPHENS = re.compile(r"-+")


def normalise_column(raw: str) -> str:
    """Lower-case, strip quotes/BOM, and treat spaces and underscores as hyphens."""
    s = raw[1:] if raw.startswith("\ufeff") else raw
    s = js_trim(s)
    s = _RE_WRAPPING_QUOTES.sub(r"\1", s)
    s = js_trim(s).lower()
    s = _RE_SPACES_UNDERSCORES.sub("-", s)
    return _RE_HYPHENS.sub("-", s)


_RE_PAREN = re.compile(r"^\((.*)\)\Z")
_RE_CURRENCY_SYMBOLS = re.compile("[\u20b9$\u00a3\u20ac\u00a5]")
_RE_CURRENCY_CODES = re.compile(r"\b(?:INR|USD|GBP|EUR|CAD|AUD|JPY|AED|SGD)\b", re.IGNORECASE | re.ASCII)
_RE_ANY_JS_SPACE = re.compile(_JS_S)
_RE_NUMBER = re.compile(r"[0-9]*\.?[0-9]*")


def parse_amount(raw):
    """Amounts as Amazon and spreadsheets write them: "-1234.56", "-1,234.56", "(1,234.56)",
    "1 234.56", "$1,234.56", "". Returns None when there is no number (never 0 for 'missing')."""
    if raw is None:
        return None
    s = js_trim(raw)
    s = js_trim(_RE_WRAPPING_QUOTES.sub(r"\1", s))
    if not s:
        return None
    negative = False
    m = _RE_PAREN.match(s)
    if m:
        negative = True
        s = js_trim(m.group(1))
    s = _RE_CURRENCY_SYMBOLS.sub("", s)
    s = _RE_CURRENCY_CODES.sub("", s)
    s = _RE_ANY_JS_SPACE.sub("", s)
    if s.startswith("+"):
        s = s[1:]
    if s.startswith("-"):
        negative = not negative
        s = s[1:]
    s = s.replace(",", "")
    if not s or not _RE_NUMBER.fullmatch(s) or s == ".":
        return None
    n = float(s)
    if not math.isfinite(n):
        return None
    return -n if negative else n


def split_records(text: str, delimiter: str, limit=None):
    """Split delimited text into records honouring RFC 4180 quoting (a quoted field may hold the
    delimiter, a newline or a doubled quote). Handles CRLF and a leading BOM; drops blank lines.

    Returns a list of (fields, line) with 1-based source line numbers. `limit` stops after that
    many records (same records, same order as the full split - used to score headers fast).
    """
    src = text[1:] if text.startswith("\ufeff") else text
    records = []
    fields = []
    field_parts = []
    in_quotes = False
    line = 1
    record_line = 1
    started = False
    n = len(src)
    i = 0
    stop_unquoted = re.compile("[" + re.escape(delimiter) + '"\r\n]')

    def field_value():
        return "".join(field_parts)

    def end_record():
        nonlocal fields, field_parts, started
        fields.append(field_value())
        field_parts = []
        if not (len(fields) == 1 and js_trim(fields[0]) == ""):
            records.append((fields, record_line))
        fields = []
        started = False

    while i < n:
        if not started:
            record_line = line
            started = True
        if in_quotes:
            j = src.find('"', i)
            if j < 0:
                chunk = src[i:]
                line += chunk.count("\n")
                field_parts.append(chunk)
                i = n
                break
            chunk = src[i:j]
            line += chunk.count("\n")
            field_parts.append(chunk)
            if j + 1 < n and src[j + 1] == '"':
                field_parts.append('"')
                i = j + 2
            else:
                in_quotes = False
                i = j + 1
            continue
        m = stop_unquoted.search(src, i)
        if m is None:
            field_parts.append(src[i:])
            i = n
            break
        j = m.start()
        if j > i:
            field_parts.append(src[i:j])
            i = j
            continue
        c = src[i]
        if c == '"' and js_trim(field_value()) == "":
            field_parts = []
            in_quotes = True
        elif c == delimiter:
            fields.append(field_value())
            field_parts = []
        elif c == "\r":
            pass
        elif c == "\n":
            end_record()
            line += 1
            if limit is not None and len(records) >= limit:
                return records
        else:  # a quote in the middle of an unquoted field is literal
            field_parts.append(c)
        i += 1
    if started or field_value() != "" or fields:
        end_record()
    if limit is not None:
        return records[:limit]
    return records


DELIMITERS = [("\t", "tab"), (",", "comma"), (";", "semicolon"), ("|", "pipe")]


def detect_header(text: str, score_fn):
    """Try each delimiter over the first 40 records, keep the most recognisable header row.
    Returns (delimiter_name, delimiter_char, records, header_index, score) or None."""
    best = None
    for char, name in DELIMITERS:
        head = split_records(text, char, limit=40)
        if not head:
            continue
        for i in range(min(len(head), 40)):
            score = score_fn(head[i][0])
            if score > (best[4] if best else 0):
                best = (name, char, None, i, score)
    if best is None:
        return None
    name, char, _, idx, score = best
    return (name, char, split_records(text, char), idx, score)


def _make_index(normalised):
    index = {}
    for i, name in enumerate(normalised):
        if name not in index:
            index[name] = i
    return index


def _cell(index, fields, name):
    i = index.get(name)
    if i is None or i >= len(fields):
        return ""
    return js_trim(fields[i] or "")


def _clean_headers(fields):
    return [js_trim(h)[1:] if js_trim(h).startswith("\ufeff") else js_trim(h) for h in fields]


# --------------------------------------------------------------------------------------------
# settlement-report/parse.ts - Flat File V2
# --------------------------------------------------------------------------------------------

SETTLEMENT_KNOWN_COLUMNS = [
    "settlement-id", "settlement-start-date", "settlement-end-date", "deposit-date", "total-amount",
    "currency", "transaction-type", "order-id", "adjustment-id", "marketplace-name", "amount-type",
    "amount-description", "amount", "posted-date", "posted-date-time", "sku", "quantity-purchased",
    "fulfillment-id",
]
SETTLEMENT_REQUIRED_COLUMNS = ["settlement-id", "amount-type", "amount-description", "amount"]
SETTLEMENT_RECOMMENDED_COLUMNS = ["total-amount", "currency", "transaction-type", "sku", "quantity-purchased"]
SETTLEMENT_V1_ONLY_COLUMNS = ["item-related-fee-type", "item-related-fee-amount", "shipment-fee-type",
                              "shipment-fee-amount", "order-fee-type"]


def _settlement_score(fields):
    names = set(normalise_column(f) for f in fields)
    return sum(1 for c in SETTLEMENT_KNOWN_COLUMNS if c in names) + sum(1 for c in SETTLEMENT_V1_ONLY_COLUMNS if c in names)


def settlement_expected_columns_message():
    return ("This does not look like an Amazon settlement report. It needs a header row with at least these columns: "
            + ", ".join(SETTLEMENT_REQUIRED_COLUMNS)
            + " \u2014 the \"Flat File V2\" download from Seller Central (Reports \u2192 Payments \u2192 All Statements) has them.")


def _fail(message, missing, found):
    return {"ok": False, "message": message, "missing_columns": list(missing), "found_columns": list(found)}


def _detect_marketplace(rows, currencies):
    codes = [c.upper() for c in currencies]
    if "INR" in codes:
        return "in"
    if "USD" in codes:
        return "us"
    names = []
    for r in rows:
        n = r["marketplace_name"].lower()
        if n and n not in names:
            names.append(n)
    for n in names:
        if "amazon.in" in n or "india" in n:
            return "in"
        if "amazon.com" in n or "us" in n:
            return "us"
    return "unknown"


def parse_settlement_report(text: str):
    """Parse a settlement report (Flat File V2). Pure: same input, same output."""
    if not text or not js_trim(text):
        return _fail("That file is empty.", SETTLEMENT_REQUIRED_COLUMNS, [])
    detected = detect_header(text, _settlement_score)
    if not detected or detected[4] == 0:
        return _fail(settlement_expected_columns_message(), SETTLEMENT_REQUIRED_COLUMNS, [])
    delimiter, _, records, header_index, _ = detected
    headers = _clean_headers(records[header_index][0])
    normalised = [normalise_column(h) for h in headers]
    present = set(normalised)
    missing = [c for c in SETTLEMENT_REQUIRED_COLUMNS if c not in present]
    if missing:
        looks_v1 = any(c in present for c in SETTLEMENT_V1_ONLY_COLUMNS)
        if looks_v1:
            message = ("This looks like the older \"Flat File V1\" settlement report, which splits every figure across its own columns. "
                       "Download \"Flat File V2\" for the same settlement period instead \u2014 it has the columns this tool needs: "
                       + ", ".join(SETTLEMENT_REQUIRED_COLUMNS) + ".")
        else:
            message = settlement_expected_columns_message() + " Missing: " + ", ".join(missing) + "."
        return _fail(message, missing, [h for h in headers if h])

    index = _make_index(normalised)
    warnings = []
    for c in SETTLEMENT_RECOMMENDED_COLUMNS:
        if c not in present:
            warnings.append({"code": "missing-optional-column",
                             "message": 'The column "%s" is not in this file, so anything that depends on it is left out.' % c})

    rows = []
    last_settlement = last_currency = last_start = last_end = last_deposit = ""
    unparsable = 0
    for fields, line in records[header_index + 1:]:
        if all(js_trim(f) == "" for f in fields):
            continue
        if _settlement_score(fields) >= 3:
            continue
        cell = lambda name: _cell(index, fields, name)  # noqa: E731
        settlement_id = cell("settlement-id") or last_settlement
        if settlement_id:
            last_settlement = settlement_id
        currency = cell("currency") or last_currency
        if currency:
            last_currency = currency
        start = cell("settlement-start-date") or last_start
        if start:
            last_start = start
        end = cell("settlement-end-date") or last_end
        if end:
            last_end = end
        deposit = cell("deposit-date") or last_deposit
        if deposit:
            last_deposit = deposit
        raw_amount = cell("amount")
        amount = parse_amount(raw_amount)
        if raw_amount and amount is None:
            unparsable += 1
            warnings.append({"code": "unparsable-amount",
                             "message": 'Line %d: could not read the amount "%s", so that line is left out of the totals.' % (line, raw_amount)})
        qty = parse_amount(cell("quantity-purchased"))
        rows.append({
            "settlement_id": settlement_id,
            "settlement_start_date": start,
            "settlement_end_date": end,
            "deposit_date": deposit,
            "total_amount": parse_amount(cell("total-amount")),
            "currency": currency,
            "transaction_type": cell("transaction-type"),
            "order_id": cell("order-id"),
            "adjustment_id": cell("adjustment-id"),
            "marketplace_name": cell("marketplace-name"),
            "amount_type": cell("amount-type"),
            "amount_description": cell("amount-description"),
            "amount": amount,
            "posted_date": cell("posted-date") or cell("posted-date-time"),
            "sku": cell("sku"),
            "quantity_purchased": None if qty is None else js_round(qty),
            "fulfillment_id": cell("fulfillment-id"),
            "source_line": line,
        })
    if not rows:
        return _fail("The header row was found, but the file has no transaction lines under it.", [], [h for h in headers if h])
    if unparsable > 3:
        warnings.append({"code": "row-skipped",
                         "message": "%d lines had an amount that could not be read as a number. Check the file was saved as text and not reformatted." % unparsable})
    currencies = _unique([r["currency"] for r in rows])
    settlement_ids = _unique([r["settlement_id"] for r in rows])
    if not any(r["total_amount"] is not None for r in rows):
        warnings.append({"code": "no-summary-row",
                         "message": "This file has no total-amount line, so the payout Amazon reports cannot be compared with the sum of the lines."})
    return {
        "ok": True,
        "rows": rows,
        "headers": [h for h in headers if h],
        "delimiter": delimiter,
        "marketplace": _detect_marketplace(rows, currencies),
        "currencies": currencies,
        "settlement_ids": settlement_ids,
        "warnings": warnings,
    }


def _unique(values):
    out = []
    seen = set()
    for v in values:
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


# --------------------------------------------------------------------------------------------
# fba-inventory-ledger/parse.ts
# --------------------------------------------------------------------------------------------

LEDGER_KNOWN_COLUMNS = [
    "date", "date-and-time", "fnsku", "asin", "msku", "sku", "merchant-sku", "title", "product-name",
    "event-type", "reference-id", "reason", "disposition", "quantity", "fulfillment-center",
    "fulfillment-center-id", "country", "reconciled-quantity", "unreconciled-quantity",
]
LEDGER_REQUIRED_COLUMNS = ["event-type", "quantity"]

# Amazon's inventory-adjustment reason codes (Seller Central definitions), as in the TypeScript.
REASON_CODES = {
    "M": {"meaning": "Missing from a bin location (lost)", "treatment": "lost"},
    "5": {"meaning": "Missing from a bin location (lost)", "treatment": "lost"},
    "F": {"meaning": "Missing inventory found", "treatment": "found"},
    "N": {"meaning": "Transferred in from an incorrectly assigned FNSKU", "treatment": "found"},
    "E": {"meaning": "Damaged at an Amazon fulfilment centre", "treatment": "damaged"},
    "6": {"meaning": "Carrier-damaged", "treatment": "check"},
    "D": {"meaning": "Disposed of", "treatment": "check"},
    "H": {"meaning": "Customer-damaged", "treatment": "ignored"},
    "K": {"meaning": "Defective", "treatment": "ignored"},
    "U": {"meaning": "Distributor-damaged", "treatment": "ignored"},
    "7": {"meaning": "Expired", "treatment": "ignored"},
    "Q": {"meaning": "Disposition change (removed)", "treatment": "ignored"},
    "P": {"meaning": "Disposition change (re-added)", "treatment": "ignored"},
    "3": {"meaning": "Product redefinition \u2014 transfer in", "treatment": "ignored"},
    "4": {"meaning": "Product redefinition \u2014 transfer out", "treatment": "ignored"},
    "O": {"meaning": "Transferred out (mis-received or already reimbursed)", "treatment": "ignored"},
}

TREATMENT_LABEL = {
    "lost": "Counted as lost",
    "damaged": "Counted as damaged",
    "found": "Subtracted (found)",
    "check": "Shown, not counted",
    "ignored": "Not counted",
}

_RE_NOT_AMAZON = re.compile(r"customer|carrier|distributor|defect|expir")
_RE_FOUND = re.compile(r"\bfound\b", re.ASCII)
_RE_DAMAG = re.compile(r"\bdamag", re.ASCII)
_RE_LOST = re.compile(r"\blost\b|misplac|missing", re.ASCII)
_RE_DISPOSED = re.compile(r"dispos|destroy")


def classify(event_type: str, reason: str, qty):
    """How a ledger row is treated. A recognised reason code always wins; otherwise a conservative
    keyword fallback on event-type + reason (decreases only for losses, increases only for found)."""
    code = js_trim(reason).upper()
    if code and code in REASON_CODES:
        return dict(REASON_CODES[code])
    t = ("%s %s" % (event_type, reason)).lower()
    if _RE_NOT_AMAZON.search(t):
        return {"treatment": "ignored", "meaning": "Not Amazon's fault"}
    if qty is not None and qty > 0 and _RE_FOUND.search(t):
        return {"treatment": "found", "meaning": "Found"}
    if qty is not None and qty < 0:
        if _RE_DAMAG.search(t):
            return {"treatment": "damaged", "meaning": "Damaged (warehouse)"}
        if _RE_LOST.search(t):
            return {"treatment": "lost", "meaning": "Lost / misplaced"}
        if _RE_DISPOSED.search(t):
            return {"treatment": "check", "meaning": "Disposed"}
    return {"treatment": "ignored", "meaning": "Unrecognised reason" if code else "No reason given"}


_RE_ISO_PREFIX = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})")
_RE_US_DATE = re.compile(r"^([0-9]{1,2})/([0-9]{1,2})/([0-9]{2}|[0-9]{4})\Z")


def to_iso_date(date_time: str, date: str) -> str:
    """The ledger's Date column is MM/DD/YYYY and "Date and Time" is ISO 8601. Normalise to
    YYYY-MM-DD so dates sort and compare correctly as strings."""
    m = _RE_ISO_PREFIX.match(date_time) or _RE_ISO_PREFIX.match(date)
    if m:
        return "%s-%s-%s" % (m.group(1), m.group(2), m.group(3))
    us = _RE_US_DATE.match(date or date_time)
    if us:
        year = "20" + us.group(3) if len(us.group(3)) == 2 else us.group(3)
        return "%s-%s-%s" % (year, us.group(1).rjust(2, "0"), us.group(2).rjust(2, "0"))
    return date or date_time


def _ledger_score(fields):
    names = set(normalise_column(f) for f in fields)
    return sum(1 for c in LEDGER_KNOWN_COLUMNS if c in names)


def ledger_expected_columns_message():
    return ("This does not look like an Amazon FBA inventory ledger. It needs a header row with at least: "
            + ", ".join(LEDGER_REQUIRED_COLUMNS)
            + " \u2014 the \"Inventory Ledger \u2192 Detailed view\" download from Seller Central (Reports \u2192 Fulfilment \u2192 Inventory) has them.")


def parse_inventory_ledger(text: str):
    """Parse an FBA Inventory Ledger (Detailed view). Pure.

    Returns losses (lost net of found, plus warehouse-damaged) ready for reconcile(), and a full
    breakdown of every event type and reason code seen, with how each was treated.
    """
    if not text or not js_trim(text):
        return _fail("That file is empty.", LEDGER_REQUIRED_COLUMNS, [])
    detected = detect_header(text, _ledger_score)
    if not detected or detected[4] == 0:
        return _fail(ledger_expected_columns_message(), LEDGER_REQUIRED_COLUMNS, [])
    delimiter, _, records, header_index, _ = detected
    headers = _clean_headers(records[header_index][0])
    normalised = [normalise_column(h) for h in headers]
    present = set(normalised)
    missing = [c for c in LEDGER_REQUIRED_COLUMNS if c not in present]
    if missing:
        return _fail(ledger_expected_columns_message() + " Missing: " + ", ".join(missing) + ".", missing, [h for h in headers if h])

    index = _make_index(normalised)
    warnings = []
    if "reason" not in present:
        warnings.append('No "Reason" column, so events are categorised from the event type alone \u2014 check the breakdown.')
    has_unreconciled = "unreconciled-quantity" in present

    loss_rows = []
    found_by_sku = {}
    by_event = {}
    by_reason = {}
    check_units = 0
    unreconciled = 0
    data_rows = 0

    for fields, line in records[header_index + 1:]:
        if all(js_trim(f) == "" for f in fields):
            continue
        if _ledger_score(fields) >= 3:
            continue  # a repeated header from concatenated files
        data_rows += 1
        cell = lambda name: _cell(index, fields, name)  # noqa: E731
        event_type = cell("event-type") or "(blank)"
        reason = cell("reason")
        qty = parse_amount(cell("quantity"))
        units = 0 if qty is None else abs(js_round(qty))
        c = classify(event_type, reason, qty)
        treatment, meaning = c["treatment"], c["meaning"]
        sku = cell("msku") or cell("sku") or cell("merchant-sku")
        sku_key = sku or cell("fnsku") or cell("asin") or "(no SKU)"

        ev = by_event.setdefault(event_type, {"type": event_type, "rows": 0, "units": 0})
        ev["rows"] += 1
        ev["units"] += units

        r_key = reason or "(blank)"
        rb = by_reason.setdefault(r_key, {"reason": r_key, "meaning": meaning, "treatment": treatment, "rows": 0, "units": 0})
        rb["rows"] += 1
        rb["units"] += units

        if has_unreconciled:
            u = parse_amount(cell("unreconciled-quantity"))
            if u is not None:
                unreconciled += abs(js_round(u))

        if units <= 0:
            continue
        if treatment == "found":
            found_by_sku[sku_key] = found_by_sku.get(sku_key, 0) + units
        elif treatment == "check":
            check_units += units
        elif treatment in ("lost", "damaged"):
            loss_rows.append({
                "date": to_iso_date(cell("date-and-time"), cell("date")),
                "sku": sku_key,
                "asin": cell("asin"),
                "fnsku": cell("fnsku"),
                "product_name": cell("title") or cell("product-name"),
                "category": treatment,
                "units": units,
                "reason": ("%s \u2014 %s" % (reason, meaning)) if reason else meaning,
                # additive detail for draft case messages
                "reason_code": reason,
                "event_type": event_type,
                "reference_id": cell("reference-id"),
                "fulfillment_center": cell("fulfillment-center") or cell("fulfillment-center-id"),
                "source_line": line,
            })

    # Found units cancel lost units of the same SKU, oldest loss first. Damaged units are not offset.
    found_offset = 0
    losses = []
    for e in sorted(loss_rows, key=lambda x: x["date"]):
        if e["category"] == "lost":
            avail = found_by_sku.get(e["sku"], 0)
            take = min(avail, e["units"])
            if take > 0:
                found_by_sku[e["sku"]] = avail - take
                found_offset += take
                if e["units"] - take <= 0:
                    continue
                e2 = dict(e)
                e2["units"] = e["units"] - take
                e2["found_offset_units"] = take
                losses.append(e2)
                continue
        losses.append(e)

    event_types = sorted(by_event.values(), key=lambda v: -v["units"])
    reasons = sorted(by_reason.values(), key=lambda v: -v["units"])

    if not losses:
        warnings.append("No unresolved lost or warehouse-damaged units were found. Either there are none in this period, or the reason labels differ \u2014 check the reason breakdown.")
    if any(r["meaning"] == "Unrecognised reason" for r in reasons):
        warnings.append("Some reasons were not recognised and were left out \u2014 check the reason breakdown.")

    dates = sorted(set(e["date"] for e in loss_rows if e["date"]))
    return {
        "ok": True,
        "losses": losses,
        "event_types": event_types,
        "reasons": reasons,
        "found_units_offset": found_offset,
        "check_units": check_units,
        "unreconciled_units": unreconciled if has_unreconciled else None,
        "headers": [h for h in headers if h],
        "delimiter": delimiter,
        "warnings": warnings,
        "data_rows": data_rows,
        "loss_date_range": [dates[0], dates[-1]] if dates else None,
    }


# --------------------------------------------------------------------------------------------
# fba-reimbursements/parse.ts
# --------------------------------------------------------------------------------------------

REIMB_KNOWN_COLUMNS = [
    "approval-date", "reimbursement-id", "case-id", "amazon-order-id", "reason", "sku", "merchant-sku",
    "fnsku", "asin", "product-name", "condition", "currency-unit", "currency", "amount-total",
    "amount-per-unit", "quantity-reimbursed-total", "quantity-reimbursed-cash",
    "quantity-reimbursed-inventory", "original-reimbursement-id", "original-reimbursement-type",
]
REIMB_REQUIRED_COLUMNS = ["reimbursement-id", "amount-total"]
REIMB_RECOMMENDED_COLUMNS = ["reason", "currency-unit", "sku", "quantity-reimbursed-total"]


def _reimb_score(fields):
    names = set(normalise_column(f) for f in fields)
    return sum(1 for c in REIMB_KNOWN_COLUMNS if c in names)


def reimb_expected_columns_message():
    return ("This does not look like an Amazon FBA reimbursements report. It needs a header row with at least these columns: "
            + ", ".join(REIMB_REQUIRED_COLUMNS)
            + " \u2014 the \"Reimbursements\" download from Seller Central (Reports \u2192 Fulfilment \u2192 Reimbursements) has them.")


def _int_or_none(raw):
    n = parse_amount(raw)
    return None if n is None else js_round(n)


def _reimb_date_range(rows):
    from_t = math.inf
    to_t = -math.inf
    frm = ""
    to = ""
    for r in rows:
        raw = js_trim(r["approval_date"])
        if not raw:
            continue
        t = js_date_parse(raw)
        shown = raw[:10]
        if t is not None:
            if t < from_t:
                from_t = t
                frm = shown
            if t > to_t:
                to_t = t
                to = shown
        else:
            if not frm:
                frm = shown
            to = shown
    return frm, to


def summarise_reimbursements(rows, warnings):
    currencies = _unique([r["currency"] for r in rows])
    reason_map = {}
    sku_map = {}
    total = reimbursed = reversal = 0.0
    reversal_count = 0
    units = cash_units = inventory_units = 0
    for r in rows:
        amt = r["amount_total"] if r["amount_total"] is not None else 0
        total += amt
        if r["is_reversal"] or amt < 0:
            reversal += amt
            reversal_count += 1
        else:
            reimbursed += amt
        units += r["quantity_total"] or 0
        cash_units += r["quantity_cash"] or 0
        inventory_units += r["quantity_inventory"] or 0
        rk = r["reason"] or "(reason not in file)"
        ra = reason_map.setdefault(rk, {"reason": rk, "count": 0, "units": 0, "amount": 0})
        ra["count"] += 1
        ra["units"] += r["quantity_total"] or 0
        ra["amount"] += amt
        sk = r["sku"] or r["asin"] or r["fnsku"] or "(no SKU on line)"
        sa = sku_map.setdefault(sk, {"sku": sk, "asin": r["asin"], "product_name": r["product_name"], "count": 0, "units": 0, "amount": 0})
        sa["count"] += 1
        sa["units"] += r["quantity_total"] or 0
        sa["amount"] += amt
        if not sa["asin"] and r["asin"]:
            sa["asin"] = r["asin"]
        if not sa["product_name"] and r["product_name"]:
            sa["product_name"] = r["product_name"]
    frm, to = _reimb_date_range(rows)
    return {
        "row_count": len(rows),
        "currency": currencies[0] if currencies else "",
        "currencies": currencies,
        "date_from": frm,
        "date_to": to,
        "total_amount": total,
        "reimbursed_amount": reimbursed,
        "reversal_amount": reversal,
        "reversal_count": reversal_count,
        "units": units,
        "cash_units": cash_units,
        "inventory_units": inventory_units,
        "by_reason": sorted(reason_map.values(), key=lambda v: -v["amount"]),
        "by_sku": sorted(sku_map.values(), key=lambda v: -v["amount"]),
        "warnings": warnings,
    }


def parse_reimbursements(text: str):
    """Parse an FBA Reimbursements report. Pure."""
    if not text or not js_trim(text):
        return _fail("That file is empty.", REIMB_REQUIRED_COLUMNS, [])
    detected = detect_header(text, _reimb_score)
    if not detected or detected[4] == 0:
        return _fail(reimb_expected_columns_message(), REIMB_REQUIRED_COLUMNS, [])
    delimiter, _, records, header_index, _ = detected
    headers = _clean_headers(records[header_index][0])
    normalised = [normalise_column(h) for h in headers]
    present = set(normalised)
    missing = [c for c in REIMB_REQUIRED_COLUMNS if c not in present]
    if missing:
        return _fail(reimb_expected_columns_message() + " Missing: " + ", ".join(missing) + ".", missing, [h for h in headers if h])
    index = _make_index(normalised)
    warnings = []
    for c in REIMB_RECOMMENDED_COLUMNS:
        if c not in present:
            warnings.append('The column "%s" is not in this file, so anything that depends on it is left out.' % c)
    rows = []
    unparsable = 0
    for fields, line in records[header_index + 1:]:
        if all(js_trim(f) == "" for f in fields):
            continue
        if _reimb_score(fields) >= 3:
            continue
        cell = lambda name: _cell(index, fields, name)  # noqa: E731
        raw_amount = cell("amount-total")
        amount_total = parse_amount(raw_amount)
        if raw_amount and amount_total is None:
            unparsable += 1
        original = cell("original-reimbursement-id")
        rows.append({
            "approval_date": cell("approval-date"),
            "reimbursement_id": cell("reimbursement-id"),
            "case_id": cell("case-id"),
            "amazon_order_id": cell("amazon-order-id"),
            "reason": cell("reason"),
            "sku": cell("sku") or cell("merchant-sku"),
            "fnsku": cell("fnsku"),
            "asin": cell("asin"),
            "product_name": cell("product-name"),
            "condition": cell("condition"),
            "currency": cell("currency-unit") or cell("currency"),
            "amount_total": amount_total,
            "quantity_total": _int_or_none(cell("quantity-reimbursed-total")),
            "quantity_cash": _int_or_none(cell("quantity-reimbursed-cash")),
            "quantity_inventory": _int_or_none(cell("quantity-reimbursed-inventory")),
            "original_reimbursement_id": original,
            "is_reversal": bool(original) or (amount_total is not None and amount_total < 0),
            "source_line": line,
            # additive: read but not used by any total
            "amount_per_unit": parse_amount(cell("amount-per-unit")),
            "original_reimbursement_type": cell("original-reimbursement-type"),
        })
    if not rows:
        return _fail("The header row was found, but the file has no reimbursement lines under it.", [], [h for h in headers if h])
    if unparsable > 3:
        warnings.append("%d lines had an amount that could not be read as a number, so they are left out of the totals." % unparsable)
    return {
        "ok": True,
        "rows": rows,
        "headers": [h for h in headers if h],
        "delimiter": delimiter,
        "has_columns": sorted(present),
        "summary": summarise_reimbursements(rows, warnings),
    }


# --------------------------------------------------------------------------------------------
# fba-recovery/from-reimbursements.ts
# --------------------------------------------------------------------------------------------


def is_warehouse_loss_reason(reason: str) -> bool:
    """Lost_Warehouse / Damaged_Warehouse (any separator, any case)."""
    r = (reason or "").lower()
    return "warehouse" in r and ("lost" in r or "damag" in r)


def is_warehouse_loss_reimbursement(row, original_reason=None) -> bool:
    if row["is_reversal"]:
        return is_warehouse_loss_reason(row["reason"]) or is_warehouse_loss_reason(original_reason or "")
    return is_warehouse_loss_reason(row["reason"])


def _reason_by_id(rows):
    out = {}
    for r in rows:
        if not r["is_reversal"] and r["reimbursement_id"]:
            out[r["reimbursement_id"]] = r["reason"]
    return out


def reimbursed_units_for_recovery(rows):
    """Per-SKU units Amazon already reimbursed for WAREHOUSE losses (Lost_Warehouse /
    Damaged_Warehouse), net of reversals of those. Outbound, inbound, customer-return and fee lines
    never offset a warehouse loss; a reversal counts only when it takes back a warehouse line."""
    reason_by_id = _reason_by_id(rows)
    by_sku = {}
    for r in rows:
        original = reason_by_id.get(r["original_reimbursement_id"]) if r["is_reversal"] else None
        if not is_warehouse_loss_reimbursement(r, original):
            continue
        key = r["sku"] or r["fnsku"] or r["asin"]
        if not key:
            continue
        agg = by_sku.setdefault(key, {"sku": key, "units": 0, "amount": 0, "reimbursement_ids": []})
        agg["units"] += r["quantity_total"] or 0
        agg["amount"] += r["amount_total"] or 0
        agg["reimbursement_ids"].append(r["reimbursement_id"])
    out = []
    for a in by_sku.values():
        b = dict(a)
        b["units"] = max(0, a["units"])
        out.append(b)
    return out


def classify_reimbursement_rows_for_recovery(rows):
    """Additive transparency: for each reimbursement reason, whether its rows were counted against
    warehouse losses (same rule as reimbursed_units_for_recovery)."""
    reason_by_id = _reason_by_id(rows)
    by = {}
    for r in rows:
        original = reason_by_id.get(r["original_reimbursement_id"]) if r["is_reversal"] else None
        counted = is_warehouse_loss_reimbursement(r, original)
        label = r["reason"] or "(reason not in file)"
        if r["is_reversal"]:
            label = "%s (reversal of %s)" % (label, original if original is not None else "a reimbursement not in this file")
        k = (label, counted)
        b = by.setdefault(k, {"reason": label, "counted": counted, "rows": 0, "units": 0, "amount": 0})
        b["rows"] += 1
        b["units"] += r["quantity_total"] or 0
        b["amount"] += r["amount_total"] or 0
    return list(by.values())


# --------------------------------------------------------------------------------------------
# fba-recovery/reconcile.ts
# --------------------------------------------------------------------------------------------


def reconcile(losses, reimbursed, unit_costs=None, today=None, closing_days=45, expired_days=60):
    """Reconcile ledger losses against warehouse reimbursements into a per-SKU list.

    Recoverable units = removed - reimbursed (floored at 0). Reimbursed units cover the OLDEST
    events first; each remaining unit keeps its own date and is checked against the claim window:
    'expired' = no remaining unit inside `expired_days`; 'closing' = some are, but at least one
    of those is `closing_days` old or more; else 'open'. Guidance, not law.
    """
    now = today_utc(today)
    unit_costs = unit_costs or {}
    reimb_by_sku = {}
    for r in reimbursed:
        reimb_by_sku[r["sku"]] = reimb_by_sku.get(r["sku"], 0) + (r.get("units") or 0)

    by_sku = {}
    for e in losses:
        if not e.get("units") or e["units"] <= 0:
            continue
        key = e.get("sku") or e.get("asin") or e.get("fnsku") or "(no SKU)"
        a = by_sku.get(key)
        if a is None:
            a = {"sku": key, "asin": e.get("asin", ""), "fnsku": e.get("fnsku", ""), "product_name": e.get("product_name", ""),
                 "lost": 0, "damaged": 0, "other": 0, "oldest": e["date"], "newest": e["date"], "events": []}
            by_sku[key] = a
        cat = e.get("category")
        if cat == "lost":
            a["lost"] += e["units"]
        elif cat == "damaged":
            a["damaged"] += e["units"]
        else:
            a["other"] += e["units"]
        a["events"].append(e)
        if not a["asin"] and e.get("asin"):
            a["asin"] = e["asin"]
        if not a["fnsku"] and e.get("fnsku"):
            a["fnsku"] = e["fnsku"]
        if not a["product_name"] and e.get("product_name"):
            a["product_name"] = e["product_name"]
        if e["date"] and (not a["oldest"] or e["date"] < a["oldest"]):
            a["oldest"] = e["date"]
        if e["date"] and (not a["newest"] or e["date"] > a["newest"]):
            a["newest"] = e["date"]

    cases = []
    total_removed = total_reimbursed = total_recoverable = 0
    total_value = 0.0
    saw_cost = False
    open_count = closing_count = expired_count = 0

    for a in by_sku.values():
        removed = a["lost"] + a["damaged"] + a["other"]
        reimbursed_units = reimb_by_sku.get(a["sku"], 0)
        recoverable = max(0, removed - reimbursed_units)
        total_removed += removed
        total_reimbursed += reimbursed_units
        if recoverable <= 0:
            continue
        total_recoverable += recoverable

        to_cover = reimbursed_units
        claimable = 0
        near_deadline = False
        oldest_remaining = ""
        remaining = []
        for ev in sorted(a["events"], key=lambda x: x["date"]):
            covered = min(to_cover, ev["units"])
            to_cover -= covered
            left = ev["units"] - covered
            if left <= 0:
                continue
            if not oldest_remaining:
                oldest_remaining = ev["date"]
            d = parse_iso_day(ev["date"]) if ev["date"] else None
            age = days_between(d, now) if d is not None else 0
            inside = age < expired_days
            if inside:
                claimable += left
                if age >= closing_days:
                    near_deadline = True
            remaining.append({
                "date": ev["date"], "units": left, "covered_by_reimbursement": covered, "age_days": age,
                "inside_window": inside, "days_left": (expired_days - age) if inside else 0,
                "category": ev.get("category"), "reason": ev.get("reason", ""), "reason_code": ev.get("reason_code", ""),
                "reference_id": ev.get("reference_id", ""), "fulfillment_center": ev.get("fulfillment_center", ""),
                "event_type": ev.get("event_type", ""), "source_line": ev.get("source_line"),
            })
        if claimable == 0:
            status = "expired"
        elif near_deadline:
            status = "closing"
        else:
            status = "open"
        if status == "open":
            open_count += 1
        elif status == "closing":
            closing_count += 1
        else:
            expired_count += 1

        cost = unit_costs.get(a["sku"])
        est_value = None
        if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost > 0:
            saw_cost = True
            est_value = recoverable * cost
            total_value += est_value

        cases.append({
            "sku": a["sku"], "asin": a["asin"], "fnsku": a["fnsku"], "product_name": a["product_name"],
            "lost_units": a["lost"], "damaged_units": a["damaged"], "other_units": a["other"],
            "removed_units": removed, "reimbursed_units": reimbursed_units, "recoverable_units": recoverable,
            "est_value": est_value, "claimable_units": claimable,
            "oldest_event": oldest_remaining or a["oldest"], "newest_event": a["newest"],
            "window_status": status, "remaining_events": remaining,
        })

    cases = sorted(cases, key=lambda c: -(c["est_value"] if c["est_value"] is not None else c["recoverable_units"]))
    return {
        "cases": cases,
        "total_removed_units": total_removed,
        "total_reimbursed_units": total_reimbursed,
        "total_recoverable_units": total_recoverable,
        "total_est_value": total_value if saw_cost else None,
        "open_count": open_count,
        "closing_count": closing_count,
        "expired_count": expired_count,
        "today": now.strftime("%Y-%m-%d"),
        "closing_days": closing_days,
        "expired_days": expired_days,
    }


# --------------------------------------------------------------------------------------------
# fba-returns/parse.ts
# --------------------------------------------------------------------------------------------

RETURNS_KNOWN = [
    "return-date", "order-id", "sku", "asin", "fnsku", "product-name", "quantity", "fulfillment-center-id",
    "detailed-disposition", "reason", "status", "license-plate-number", "customer-comments",
]
RETURNS_REQUIRED_COLUMNS = ["order-id", "sku"]


def _returns_score(fields):
    names = set(normalise_column(f) for f in fields)
    return sum(1 for k in RETURNS_KNOWN if k in names)


def parse_customer_returns(text: str):
    """Parse the FBA Customer Returns report. Pure."""
    msg = ("This does not look like an Amazon FBA customer returns report. It needs at least: "
           + ", ".join(RETURNS_REQUIRED_COLUMNS)
           + " \u2014 download it from Reports \u2192 Fulfillment \u2192 Customer Returns.")
    if not text or not js_trim(text):
        return _fail("That file is empty.", RETURNS_REQUIRED_COLUMNS, [])
    detected = detect_header(text, _returns_score)
    if not detected:
        return _fail(msg, RETURNS_REQUIRED_COLUMNS, [])
    _, _, records, header_index, _ = detected
    headers = _clean_headers(records[header_index][0])
    norm = [normalise_column(h) for h in headers]
    missing = [c for c in RETURNS_REQUIRED_COLUMNS if c not in norm]
    if missing:
        return _fail(msg + " Missing: " + ", ".join(missing) + ".", missing, [h for h in headers if h])
    index = _make_index(norm)
    rows = []
    for fields, line in records[header_index + 1:]:
        if all(js_trim(x) == "" for x in fields) or _returns_score(fields) >= 3:
            continue
        cell = lambda name: _cell(index, fields, name)  # noqa: E731
        order_id = cell("order-id")
        if not order_id:
            continue
        q = parse_amount(cell("quantity"))
        rows.append({
            "return_date": cell("return-date"),
            "order_id": order_id,
            "sku": cell("sku"),
            "asin": cell("asin"),
            "fnsku": cell("fnsku"),
            "product_name": cell("product-name"),
            "quantity": 1 if q is None else max(0, abs(js_round(q))),
            "disposition": cell("detailed-disposition"),
            "reason": cell("reason"),
            "status": cell("status"),
            "source_line": line,
        })
    warnings = [] if rows else ["No returns in this file. Check the date range covers the refunds you are checking."]
    return {"ok": True, "rows": rows, "headers": [h for h in headers if h], "warnings": warnings}


# --------------------------------------------------------------------------------------------
# fba-returns/reconcile.ts
# --------------------------------------------------------------------------------------------

_RE_REFUND = re.compile(r"refund", re.IGNORECASE)
_RE_PRINCIPAL = re.compile(r"principal", re.IGNORECASE)
_RE_CUSTOMER = re.compile(r"customer", re.IGNORECASE)


def _is_customer(reason):
    return bool(_RE_CUSTOMER.search(reason or ""))


def find_unreturned_refunds(settlement_rows, returns_rows, reimbursement_rows, today=None, claim_from_days=60, claim_until_days=120):
    """FBA orders refunded to a customer where the unit never came back and Amazon has not
    reimbursed the seller. refunds <- settlement (transaction-type Refund, AFN only);
    returned <- customer returns by order-id + sku; reimbursed <- CustomerReturn /
    CustomerServiceIssue reimbursements on that amazon-order-id (a reversal counts only when it
    takes one of those back). Status: wait (<60d), claim-now (60-120d), too-late (>120d)."""
    now = today_utc(today)
    refunds = {}
    mfn_skipped = 0
    seen_mfn = set()
    for r in settlement_rows:
        if not _RE_REFUND.search(r["transaction_type"]) or not r["order_id"] or not r["sku"]:
            continue
        k = (r["order_id"], r["sku"])
        if r.get("fulfillment_id") and r["fulfillment_id"].upper() != "AFN":
            if k not in seen_mfn:
                mfn_skipped += 1
            seen_mfn.add(k)
            continue
        raw = r["posted_date"]
        date = to_iso_date(raw, raw[:10])
        cur = refunds.get(k)
        if cur is None:
            cur = {"order_id": r["order_id"], "sku": r["sku"], "date": date, "units": 0, "principal": 0,
                   "settlement_ids": [], "adjustment_ids": []}
            refunds[k] = cur
        if date and (not cur["date"] or date < cur["date"]):
            cur["date"] = date
        if r["quantity_purchased"]:
            cur["units"] = max(cur["units"], abs(r["quantity_purchased"]))
        if _RE_PRINCIPAL.search(r["amount_description"]) and r["amount"] is not None:
            cur["principal"] += -r["amount"]
        if r.get("settlement_id") and r["settlement_id"] not in cur["settlement_ids"]:
            cur["settlement_ids"].append(r["settlement_id"])
        if r.get("adjustment_id") and r["adjustment_id"] not in cur["adjustment_ids"]:
            cur["adjustment_ids"].append(r["adjustment_id"])

    returned = {}
    for r in returns_rows:
        k = (r["order_id"], r["sku"])
        returned[k] = returned.get(k, 0) + r["quantity"]

    reason_by_id = _reason_by_id(reimbursement_rows)
    reimbursed = {}
    for r in reimbursement_rows:
        if not r["amazon_order_id"]:
            continue
        if r["is_reversal"]:
            counts = _is_customer(r["reason"]) or _is_customer(reason_by_id.get(r["original_reimbursement_id"], ""))
        else:
            counts = _is_customer(r["reason"])
        if not counts:
            continue
        k = (r["amazon_order_id"], r["sku"])
        reimbursed[k] = reimbursed.get(k, 0) + (r["quantity_total"] or 0)

    cases = []
    returned_lines = reimbursed_lines = 0
    for k, rf in refunds.items():
        units = rf["units"] or 1
        back = returned.get(k, 0)
        got = max(0, reimbursed.get(k, 0))
        if back > 0:
            returned_lines += 1
        if got > 0:
            reimbursed_lines += 1
        missing = max(0, units - back - got)
        if not missing:
            continue
        d = parse_iso_day(rf["date"]) if rf["date"] else None
        age = days_between(d, now) if d is not None else 0
        if age > claim_until_days:
            status = "too-late"
        elif age >= claim_from_days:
            status = "claim-now"
        else:
            status = "wait"
        claimable_from = (d + timedelta(days=claim_from_days)).strftime("%Y-%m-%d") if d is not None else ""
        claimable_until = (d + timedelta(days=claim_until_days)).strftime("%Y-%m-%d") if d is not None else ""
        cases.append({
            "order_id": rf["order_id"], "sku": rf["sku"], "refund_date": rf["date"], "days_since_refund": age,
            "refunded_units": units, "returned_units": back, "reimbursed_units": got, "missing_units": missing,
            "refunded_principal": js_round(rf["principal"] * 100) / 100, "status": status,
            "claimable_from": claimable_from,
            # additive detail
            "claimable_until": claimable_until,
            "settlement_ids": rf["settlement_ids"], "adjustment_ids": rf["adjustment_ids"],
        })
    order = {"claim-now": 0, "wait": 1, "too-late": 2}
    cases = sorted(cases, key=lambda c: (order[c["status"]], c["refund_date"]))
    return {
        "cases": cases,
        "refunded_lines": len(refunds),
        "returned_lines": returned_lines,
        "reimbursed_lines": reimbursed_lines,
        "mfn_skipped": mfn_skipped,
        "claim_now": sum(1 for c in cases if c["status"] == "claim-now"),
        "waiting": sum(1 for c in cases if c["status"] == "wait"),
        "too_late": sum(1 for c in cases if c["status"] == "too-late"),
        "today": now.strftime("%Y-%m-%d"),
        "claim_from_days": claim_from_days,
        "claim_until_days": claim_until_days,
    }


# --------------------------------------------------------------------------------------------
# Small formatting helpers shared by the skill scripts
# --------------------------------------------------------------------------------------------


def fmt_money(n, currency="USD"):
    if n is None:
        return "\u2014"
    sign = "-" if n < 0 else ""
    sym = "$" if currency in ("USD", "", None) else currency + " "
    return "%s%s%s" % (sign, sym, format(abs(n), ",.2f"))


def md_table(headers, rows):
    def esc(v):
        s = "" if v is None else str(v)
        return s.replace("|", "\\|").replace("\n", " ")
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(esc(v) for v in r) + " |")
    return "\n".join(out)
