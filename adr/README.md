# ADRs

One file per architecture decision, named `NNNN-short-title.md`. Numbering is global across the
course, not per session. Each record opens with a `Status` / `Session` / `Date` block and cites
the principles (P1–P4) it serves; `tools/arch_lint.py` checks both in CI. An accepted ADR is
not rewritten: later changes go in an `## Amendments` section or a new ADR.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-llm-hosting.md) | LLM hosting | Accepted, amended in Session 2 |
| [0002](0002-nba-batch-vs-realtime.md) | Next-best-action: batch vs real-time | Accepted |
| [0003](0003-vector-store.md) | Vector store | Accepted, amended by 0004 |
| [0004](0004-own-analytical-store.md) | Own analytical store, fed by CDC | Accepted |
