# Use-case flow view: cold start

**Session 2 mini project · Ismail Mohamed · 2026-11-01** ·
Diagram: [`02-cold-start-flow.drawio`](../diagrams/src/02-cold-start-flow.drawio)

**Use case.** A kiosk owner signs up today. Nabd has nothing personal to go on: no orders, no
features, no vector. Within a minute they get one welcome push with three offers from
distributors that deliver to their area, picked for their shop type. Until they have four weeks
of orders, the nightly ranking keeps using those defaults.

**Two paths.** Real-time (A, steps 1–16): sign-up → CDC → Kafka → recommendation engine → push →
the retailer opens an offer. Background (B): Airflow rebuilds the defaults every night, moves
retailers with enough history to personal ranking, and measures the welcome push against a
holdout (P4).

**Why the real-time path starts with an event.** Nabd doesn't render screens (the home page is a
non-goal in the SDD), so no request waits on a recommendation. The real-time path runs from the
sign-up event to the push. The only synchronous part is the retailer opening the offer (steps
13–16), and that call never waits on Nabd.

**Choosing the three offers (step 7)**

| | A · Precomputed segment defaults (chosen) | B · Real-time vector DB query |
| --- | --- | --- |
| Latency | ≈ 10 ms read | ≈ 60 ms embed + query |
| Cost | ~160 small lists a night (shop type × governorate) | One embedding call per sign-up |
| Quality | Ranked by what similar new retailers actually ordered first | A vector built from two fields is a lookup with extra steps |
| Operational DB load | None: reads Nabd's store | None |

**Decision: A.** A new retailer has no behaviour to embed, so B would only re-encode two
categories a SQL key already handles. Staleness is handled at send time: step 9 drops any offer
that changed since last night, because offer changes arrive through CDC
([ADR-0004](../adr/0004-own-analytical-store.md)). If a segment has no defaults yet (a governorate
with no retailers so far), step 7 falls back to the national list for the same shop type. No LLM
writes the message: it is a pre-approved template with offer slots (P1, P2).

**Over-engineering check**

- **Needed:** app + gateway (sign-up, opening the offer), Tawreed backend + operational DB (source
  of truth), CDC → Kafka (the sign-up event, no polling), Airflow + CDP (nightly defaults),
  recommendation engine, push in place of WhatsApp.
- **Not needed here:** Flink (no timer or window; a plain consumer reads one event), feature store
  (nothing to store yet), vector DB (no user vector), the agent and the LLM.
- **Missing from the high-level view:** a small serving table for the defaults (the CDP isn't meant
  for request-time reads), a consent service (push opt-in at sign-up, PDPL), a first-week
  frequency cap, and the rule that moves a retailer to personal ranking.

**Latency budget (P95)**

| Path | Hops | Total | Target |
| --- | --- | --- | --- |
| Sign-up → welcome push | CDC 1,000 · Kafka → engine 50 · defaults 10 · checks 20 · FCM 1,000 | ≈ 2.1 s | ≤ 60 s |
| Retailer opens the offer | gateway 60 · offer read 40 · render 40 | ≈ 140 ms | ≤ 500 ms |

Figures are illustrative until load-tested on pre-prod.
