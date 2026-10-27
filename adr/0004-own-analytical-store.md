# ADR-0004: Nabd keeps its own analytical store, fed by CDC

```
Status:  Accepted
Session: 2 (building blocks)
Date:    2026-10-26
```

## Context

The Session 1 README assumed Nabd would reuse Tawreed's PostgreSQL. That database is Tawreed's
operational database: it serves carts, checkout and orders, and its latency budget assumes the
app is the only thing talking to it.

Nabd's workload looks nothing like the app's. The nightly jobs scan months of orders per
retailer, build features, score 20,000 retailers, and run vector search over the catalog. Run
against the operational database, those queries take locks on the same tables checkout writes
to, and a slow campaign night becomes a slow checkout. The data also changes owner: once Nabd
derives segments and churn scores, someone has to own that data, and it shouldn't be Tawreed's
order team.

Nabd also needs events, not only tables. The abandoned-cart rule in ADR-0002 has to react within
minutes, which a nightly copy can't do.

## Options

**A. Query Tawreed's operational database directly**, in a separate schema. No new
infrastructure. Every Nabd job competes with checkout.

**B. Read replica of the operational database.** Analytics no longer locks the primary, but the
replica carries Tawreed's full schema and PII, has no events, and its lag is out of our hands.

**C. Own Postgres store fed by change data capture.** Debezium reads the database's write-ahead
log and publishes row changes to Kafka. A sink writes only the tables and columns Nabd needs
into Nabd's own Postgres (CDP tables, features, pgvector). Event Rules subscribe to the same
topics.

**D. Nightly bulk export.** A job copies the tables we need once a night. Simple, but up to a
day stale and no events.

## Trade-offs

| | Load on checkout | Freshness | Events for rules | Data we hold | Ops |
| --- | --- | --- | --- | --- | --- |
| A | High | Live | No | Everything, shared | None new |
| B | None on primary | Seconds, not ours to control | No | Full copy, incl. PII | Low |
| C | None (reads the log) | Seconds | Yes, same pipeline | Only the columns we choose | Debezium + Kafka |
| D | A nightly spike | Up to 24 h | No | Only what we choose | Low |

## Decision

**Option C.** It is the only option that keeps Nabd's load off checkout and also gives the
event rules their events, from one pipeline. Choosing columns at the sink lets us leave out PII
we don't need, which is P3 applied at ingestion rather than only at the LLM boundary. Keeping a
full history of orders and sends in our own store is also what makes the holdout comparison in
P4 possible without asking Tawreed for reports.

Each topic gets a written data contract with Tawreed's team: schema, owner, version, and the
column mapping into Nabd's tables.

## Consequences

- Two new components to run: Debezium and Kafka (a managed Kafka is fine if it is in-country).
- A replication slot that nobody reads makes the database's write-ahead log grow. Lag and slot
  size get alerts on day one.
- A schema change on Tawreed's side can break the sink. The data contract is checked in their CI,
  so a breaking change fails their build instead of filling our tables with nulls.
- Nabd now stores retailer data itself, so the PDPL retention rules in `docs/02-sdd.md` apply to
  our store.
- The vector store from ADR-0003 lives in this store, not in Tawreed's database.

## Revisit when

Tawreed builds a company data platform that already publishes these events and tables, or the
event rules are dropped and a nightly export (D) would be enough.

## Related

P3, P4 · [ADR-0002](0002-nba-batch-vs-realtime.md) needs the events ·
[ADR-0003](0003-vector-store.md) moves into this store
