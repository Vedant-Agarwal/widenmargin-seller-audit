# WidenMargin Seller Audit

Free, open-source Agent Skills for **Amazon US FBA sellers**, packaged as a Claude plugin. Upload
your own Seller Central reports to Claude and it checks them for money worth looking into: units
Amazon lost or damaged in its warehouses with no matching reimbursement, customer refunds where the
item never came back, and a clear breakdown of what Amazon has already reimbursed.

Every number comes from a small Python script (standard library only) that runs on your files
inside Claude. The logic is a line-for-line port of the free browser tools at
[widenmargin.com](https://widenmargin.com/resources/amazon-us/fba-lost-damaged-inventory-finder),
checked against the original TypeScript on every ported test fixture and on 10,000 randomly generated report scenarios.

## What it does

| Skill | You give it | You get back |
|---|---|---|
| `ledger-audit` | Inventory Ledger (Detailed view); optional Reimbursements report and average unit cost | Per-SKU lost/damaged units not matched to a warehouse reimbursement, each unit dated against the 60-day claim window (open / closing / expired), how every reason code in your file was read, and a draft case message per SKU still inside the window |
| `returns-not-received` | Settlement report(s) Flat File V2 (several allowed), Customer Returns report; optional Reimbursements report | FBA refunds that were neither returned nor reimbursed, each dated against the day-60-to-120 window (wait / claim now / too late), and a draft case message per claim-now order |
| `reimbursement-check` | Reimbursements report; optional Inventory Ledger and your unit costs | Totals by reason and SKU with reversals netted, every reversal and whether its original is in the file, lines reimbursed below your own cost, and which warehouse reimbursements match which ledger losses |

Try asking Claude: *"Check my inventory ledger for unreimbursed losses"*, *"Which refunds weren't
returned?"*, or *"Break down my FBA reimbursements report"*. If a report is missing, Claude tells
you exactly where to download it in Seller Central.

Results are framed as **worth checking**, never as money Amazon owes you. Since 1 November 2024
Amazon reimburses most fulfillment-center losses automatically, so most months the right answer
is "nothing missing" — this is a check that those reimbursements happened.

### Example (from the bundled test fixtures)

```
FBA lost & damaged inventory check — checked as of 2026-10-03
- Lost/damaged units without a matching warehouse reimbursement: 9 units across 4 SKUs
- Of those, still inside the 60-day window: 8 units
- SKUs by window status: open 2 · closing 1 · past 60 days 1
| SKU      | Lost | Damaged | Reimbursed | Not reimbursed | Inside window | Status       |
| BOT-500  | 4    | 0       | 0          | 4              | 4             | Open         |
| MUG-BLUE | 4    | 0       | 1          | 3              | 3             | Open         |
| LAMP-01  | 1    | 0       | 0          | 1              | 0             | Past 60 days |
| MAT-GREY | 0    | 2       | 1          | 1              | 1             | Closing soon |
```

## Privacy: what this plugin runs, sends and fetches

- **Files are processed inside Claude; nothing is sent to WidenMargin** or to anyone else.
- **Runs:** three Python scripts (`skills/*/scripts/*.py`) on the files you upload, in Claude's
  code-execution sandbox (claude.ai, Cowork) or on your machine (Claude Code, which asks before
  running them).
- **Sends:** nothing. The scripts make no network requests, write no files, and collect no
  analytics. **Fetches:** nothing. There are no MCP servers, hooks, or external dependencies.
- The scripts are plain, readable Python: `skills/<skill>/scripts/`. The shared parser
  `wm_audit_core.py` is identical in all three skills so that each skill also works on its own.

## Install

### From the Claude directory (once listed)

In claude.ai or the Claude desktop app: **Customize → Plugins → Discover**, search for
**WidenMargin Seller Audit**, and add it. A plugin added there also reaches Claude Code as a
synced plugin. In Claude Code you can also run `/plugin directory`.

### Upload the ZIP yourself (claude.ai / Claude desktop)

1. Make sure code execution is on (Settings → Capabilities, or ask your Owner on Team/Enterprise).
2. Download `widenmargin-seller-audit-plugin-<version>.zip` from the GitHub releases page.
3. **Customize → Plugins → Add → Upload plugin**, and choose the ZIP.

Or upload a single skill: **Customize → Skills → + → Create skill → Upload a skill** with
`ledger-audit.zip`, `returns-not-received.zip` or `reimbursement-check.zip` (each holds one skill
folder with its `SKILL.md`).

### Claude Code

```bash
# from GitHub (this repository is also a one-plugin marketplace)
/plugin marketplace add Vedant-Agarwal/widenmargin-seller-audit
/plugin install widenmargin-seller-audit@widenmargin

# or try a local checkout for one session
claude --plugin-dir ./widenmargin-seller-audit
```

You can also run any script directly, for example:

```bash
python3 skills/ledger-audit/scripts/ledger_audit.py InventoryLedger.csv --reimbursements Reimbursements.txt --unit-cost 6.50
python3 skills/returns-not-received/scripts/returns_not_received.py --settlement s1.txt s2.txt s3.txt --returns returns.txt --reimbursements reimb.txt
python3 skills/reimbursement-check/scripts/reimbursement_check.py Reimbursements.txt --ledger InventoryLedger.csv --unit-cost 6.50
```

## Dated facts and sources

Policy facts are dated **2026-10-03** and cited in each skill's `references/` folder: the 60-day
window for fulfillment-center losses (since 23 Oct 2024, previously 18 months), automatic
reimbursement of most such losses (since 1 Nov 2024), manufacturing-cost valuation (since 31 Mar
2025), the day-60-to-120 window for refunds that were not returned, Inventory Ledger reason codes,
reimbursement reasons, return dispositions, and the report columns from Amazon's SP-API report
documentation. Amazon changes these policies; always confirm in Seller Central Help.

## Disclaimers

- **Free and open source** under the MIT License.
- **Not affiliated with, endorsed by, or sponsored by Amazon.** Amazon, Seller Central and FBA are
  trademarks of Amazon.com, Inc. or its affiliates.
- **Not tax, legal or accounting advice.**
- **No guarantee of any reimbursement.** Results are units and orders worth checking. Amazon decides
  every claim and its value; it may have found units, reimbursed them under another SKU, or
  reimbursed them outside your files' dates. Draft case messages are drafts — verify every event
  in Seller Central before sending anything.
- Reason codes and report formats come from Amazon's public definitions and have not been tested
  against a large set of real sellers' files. That is why every run shows how your file was read.

## Development

```bash
python3 tools/sync_core.py                     # copy src/wm_audit_core.py into each skill
python3 -m pytest                              # unit tests (pytest; Python 3.8+)
python3 tools/parity/run_parity.py <shelfstack-checkout> --fuzz 500   # TS vs Python parity (needs Node 22.6+)
python3 tools/validate.py                      # structure, frontmatter, sizes, wording
python3 tools/build_zips.py                    # dist/ ZIPs for upload
```

Issues and pull requests are welcome. See [CHANGELOG.md](CHANGELOG.md).
