# ADR-0002: Next-best-action, batch vs real-time

```
Status:  Accepted
Session: 1 (governance pack)
Date:    2026-10-22
```

## Context

Nabd decides which offer each retailer should see next. Most Tawreed orders are weekly or
biweekly reorders, so a decision made last night is usually still right this morning. A few
moments do lose value by the hour: an abandoned cart, or a retailer's usual SKU coming back in
stock. The choice affects cost (G3), relevance (G2), and how much runs in the hot path.

## Options

**A. Nightly batch.** One run ranks offers for every retailer. Cheap and simple; reactions can
be up to 24 h stale.

**B. Real-time model per event.** Every app event re-scores the retailer. Freshest, but a model
call in the hot path for every event, and much more to monitor.

**C. Nightly batch + near-real-time rules.** The nightly run does the ranking. A small set of
named triggers (cart abandoned for 2 h, usual SKU back in stock) sends a pre-approved template
within minutes, with no model and no LLM in that path.

## Trade-offs

| | Freshness | Cost | Hot-path risk | Governance |
| --- | --- | --- | --- | --- |
| A | Up to 24 h | Lowest | None | Simple: one run to review |
| B | Seconds | Highest (a run per event) | High | Every event can produce a message |
| C | Minutes for named triggers, 24 h otherwise | Near A | Low: rules only | Triggers are templates, so P1 and P2 hold without review per send |

## Decision

**Option C.** It gets the speed where it pays (abandoned carts) at close to batch cost. Because
trigger messages are pre-approved templates, P1 holds by construction and P2 needs approval once
per template, not once per send.

## Consequences

- Two paths to maintain: the nightly ranking job and the event rules.
- New triggers go through the ARB like any other change.
- Every trigger has its own holdout, so its value is measured (P4).

## Revisit when

A trigger shows uplift over its holdout large enough to justify a real-time model, or retailers
start ordering daily rather than weekly.

## Related

P1, P2, P4 · [ADR-0001](0001-llm-hosting.md)
