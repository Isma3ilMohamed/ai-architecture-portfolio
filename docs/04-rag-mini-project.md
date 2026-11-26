# Session 4 mini project: Nabd Assist, end-to-end RAG

**Ismail Mohamed · 2026-11-26** · Diagram:
[`04-rag-chatbot.drawio`](../diagrams/src/04-rag-chatbot.drawio) · Full design:
[04-rag-chatbot.md](04-rag-chatbot.md) · [ADR-0006](../adr/0006-rag-chatbot.md)

**Scenario: E-Commerce Policy & Refund Assistant.** A retailer in the Tawreed app taps a push
about an offer and asks before ordering: does this distributor deliver to Tanta on Thursdays,
what is the minimum order, can I return a damaged carton. Answers come from Tawreed's policies,
distributor terms and help center; order status and prices come from read-only lookups.

## 1. Parsing, chunking and sync

- **Fixed 500-character windows vs section-based chunks.** Section-based for policies (about 400
  tokens, 50 overlap), one chunk per distributor and topic for terms, one per help article.
  *Accuracy:* a refund rule and its exception stay in one chunk instead of being cut mid-sentence,
  at almost the same embedding *cost*. Fixed windows only for files with no headings.
- **Sync.** Every chunk carries `doc_id`, `version`, `owner`, `audience`. A new version is
  inserted before the old one's chunks are deleted, so answers never disappear mid-update.
- **Hard formats.** Arabic OCR is unreliable, so distributor terms come through a dashboard form;
  a scanned PDF is a fallback and the distributor confirms the extracted text before indexing.
  No crawler: Tawreed owns its help center, so articles are read from its database on publish.

## 2. Embedding compute and retrieval

- **Single CPU vs multi-worker CPU vs GPU.** About 1,500 chunks in total (estimate) and tens of
  changes a day. One CPU worker (~6 chunks/s) re-indexes everything in about 4 minutes; four do it
  in about 1. A GPU would sit idle all day (*cost*). Choice: one worker behind a batch manager,
  four for a full re-index.
- **Consistency.** Model name and version are stored on every vector; the query path refuses an
  index built with another version. A new model gets a second index, then a switch.
- **Top-K.** K = 5 misses answers ranked sixth; K = 50 sent to the LLM buries the answer and costs
  tokens and latency. Choice: retrieve 20 (filtered to the retailer's audience inside the query),
  re-rank, keep 5, fall back below a score threshold. Both values get tuned on the eval set.

## 3. Cost control and the harness

- **Short-circuit first.** A small intent classifier sends small talk to a fixed reply, orders and
  prices to a lookup, complaints to a person. Only document questions reach the vector DB and LLM.
- **Bidirectional safeguard vs prompt-only rules.** Prompt rules alone fail against injection.
  Choice: both, plus a separate guard model on input and output
  ([ADR-0005](../adr/0005-guardrail-scanning.md)). About 1 s of *latency*, inside the 6 s budget;
  the output scan blocks phone numbers, names and card details (*PDPL*).
- **Tool breach.** Lookups are read-only and take the retailer id from the session token, never
  from the model, so a retailer can only ever see their own orders.

## 4. Feasibility and over-engineering check

- **MVP.** One Assist service, modular inside (ingestion worker, RAG module, lookups), on the
  Postgres and pgvector Nabd already runs. Extracted first: ingestion, since OCR and re-index
  bursts need memory while questions need steady low latency. Not in the MVP: Qdrant, GPUs, write
  tools.
- **Pushback.** "Instant answers, streamed like ChatGPT." Generation plus an output scan can't be
  sub-second, and streaming would show text before it is scanned. Instead: small talk and lookups
  answer in under a second; document answers arrive whole behind a typing indicator, p95 under 6 s.

## Bonus: admin guardrail config

```yaml
tone: "Egyptian Arabic, friendly, short; formal for legal and payment topics"
grounding: "Answer only from the retrieved chunks and cite the document title"
fallback: "If the chunks don't answer it, say you don't know and offer support"
forbidden: [competitors, politics, religion, delivery promises beyond the terms]
tools: {allowed: [order_status, offer_price, stock], mode: read_only, scope: session_retailer}
```
