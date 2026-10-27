# ADR-0003: Vector store

```
Status:  Accepted (amended by ADR-0004, 2026-10-26)
Session: 1 (governance pack)
Date:    2026-10-22
```

## Context

The agent's Retrieval step pulls approved offers, product descriptions, and past high-performing
campaigns to ground its copy. Retailers and distributors name products in Arabic, English, and
brand shorthand (for example "Pepsi cans" vs "Pepsi 330ml"), so keyword search alone misses matches. The corpus
is small: ~50k SKUs and a few thousand campaigns. The data already lives in Tawreed's Postgres.

## Options

**A. pgvector in our existing Postgres.** No new vendor, data stays where it is, and
transactional data and vectors can be joined in one query.

**B. Managed Pinecone.** Ops-free and fast at scale, but a new cross-border processor and a
second copy of catalog data to keep in sync.

**C. No vectors; SQL and keyword retrieval.** Simplest, but misses synonyms across Arabic,
English, and shorthand.

## Trade-offs

| | Arabic/English matching | Ops | PDPL / vendors | Fit for ~50k SKUs |
| --- | --- | --- | --- | --- |
| A | Good | Low: existing DB | No new flow | Comfortable |
| B | Good | None | New processor + DPA | Oversized |
| C | Poor | None | None | Fits, but low recall |

## Decision

**Option A**, behind a `VectorStore` interface so a later move to B is one component's change.
Only catalog and campaign text is embedded, never retailer PII (P3).

## Consequences

- Index tuning and vacuum become the platform team's job.
- Embeddings are computed through `LLMClient` (ADR-0001), so they are costed (P4).
- Approved-offer filtering happens in the same SQL query as the similarity search, which supports P1.

## Revisit when

The index grows beyond ~5M vectors, or p95 retrieval exceeds 200 ms.

## Amendments

**2026-10-26 (Session 2): where the store lives, and Qdrant.**

- The store is now Nabd's own Postgres, fed by change data capture ([ADR-0004](0004-own-analytical-store.md)),
  not Tawreed's operational database. The decision above still holds: the catalog and campaign
  text arrive through CDC and are embedded in our store.
- We also considered **Qdrant**, a dedicated vector database that the course instructor
  recommends for production because each data store then has one job. At ~50k SKUs it would add
  a second store and a second sync path without a gain we can measure yet. pgvector stays, and
  the `VectorStore` interface keeps a move to Qdrant a one-component change. Qdrant is the target
  if the revisit trigger below fires.

## Related

P1, P3, P4 · [ADR-0001](0001-llm-hosting.md)
