# Privacy policy — WidenMargin Seller Audit (Claude plugin)

Last updated: 5 October 2026

**Short version: this plugin collects nothing, stores nothing and sends nothing.**

- **What it reads:** only the Amazon report files you choose to upload in your Claude conversation
  (Inventory Ledger, Reimbursements, settlement and Customer Returns reports). Those reports can contain
  order IDs and, in some report types, other order details.
- **Where it runs:** three Python scripts run on those files inside Claude's code-execution sandbox
  (claude.ai, Cowork) or on your own machine (Claude Code). The results appear in your conversation.
- **What it sends:** nothing. The scripts make no network requests, call no APIs, use no MCP servers or
  hooks, and collect no analytics. Nothing is sent to WidenMargin, to the author, or to anyone else.
- **What it keeps:** nothing. The scripts write no files and keep no data after they finish. Your
  conversation and uploaded files are handled by Anthropic under Claude's own privacy policy.
- **Under 18:** the plugin is meant for Amazon sellers and is not directed at children.

The code is open source (MIT) and readable: [`skills/*/scripts/`](skills/).

Questions: open an issue at https://github.com/Vedant-Agarwal/widenmargin-seller-audit/issues
