# ADR-0006: Retailer questions are answered by RAG, not by a fine-tuned model

```
Status:  Accepted
Session: 4 (RAG chatbot)
Date:    2026-11-26
```

## Context

When a retailer opens a push about an offer, the next step is often a question, not an order:
does this distributor deliver to my area on Thursdays, what is the minimum order, can I return
a damaged carton. Today those questions go to Tawreed's support line, and most of them repeat.

The answers live in documents that change: Tawreed's return, refund and delivery policies, each
distributor's terms, and the help-center articles. Distributors update their terms when they
change routes or prices, often more than once a month. Some answers are not documents at all:
the status of an order or the price of an offer lives in Tawreed's database.

This is Nabd's first synchronous LLM path. Until now every model call ran in the nightly batch
([ADR-0002](0002-nba-batch-vs-realtime.md)); here a retailer waits for the answer.

## Options

**A. Fine-tune a model on the policies.** Answers sound natural, but every policy change means
building a new training set and retraining, and a fine-tuned model cannot say which document an
answer came from.

**B. Search only.** Return the best-matching help article, no generated answer. Cheap and
predictable, but the retailer still reads a long policy to find one line.

**C. RAG behind intent routing.** Route each message first: small talk gets a fixed reply, order
status and prices go to a read-only lookup, document questions go to retrieval and a model that
answers only from what was retrieved. Below a confidence threshold, fall back to B and offer a
person.

**D. Put every document in a long context window.** No index to run, but the cost grows with
every document and distributor, and a long context is where models lose the one line that matters.

## Trade-offs

| | Keeps up with changing terms | Cites its source | Cost per question | Prices and order data |
| --- | --- | --- | --- | --- |
| A | Retrain per change | No | Low | From training data, possibly stale |
| B | Re-index per change | Yes, it is the source | Lowest | Not answered |
| C | Re-index per change | Yes | Medium | From the database, live |
| D | Immediately | Weakly | High, grows with content | From the documents, possibly stale |

## Decision

**Option C, with B as its fallback.** The knowledge changes faster than any retraining cycle,
and nobody can list in advance what retailers will ask about a forty-page policy. Prices,
discounts and order status never come from the model: they come from a lookup and fill a slot,
the same rule as campaign copy (P1). Retailer PII is not sent to the model; the lookup uses the
retailer id from the session token, never from the message text (P3).

The design is in [04-rag-chatbot.md](../docs/04-rag-chatbot.md).

## Consequences

- A user-facing latency budget: p95 under 6 seconds for a full answer (section 7 of the design).
- Both guard scans from [ADR-0005](0005-guardrail-scanning.md) run on every document question.
  Because the answer is scanned before it is shown, it is not streamed token by token.
- The index lives in Nabd's Postgres with pgvector ([ADR-0003](0003-vector-store.md)). It holds a
  few thousand chunks, well inside that ADR's revisit trigger.
- Indexing and questions use the same embedding model and version. Changing the model means
  building a second index and switching to it, never mixing the two.
- Retrieval is filtered by who is asking: a retailer only retrieves Tawreed-wide documents and
  the terms of distributors that serve their area.
- Rollout keeps 10% of retailers on the current support path, so the drop in support calls and
  the change in CSAT are measured against a control (P4).
- Support gets a handoff queue with the transcript, and a weekly review of unanswered questions
  becomes the list of documents to fix.

## Revisit when

The fallback rate stays above 30% after the first month (the documents, not the model, are the
problem), or the same questions repeat with stable answers long enough that a fine-tuned small
model would be cheaper than retrieval.

## Related

P1, P3, P4 · [ADR-0001](0001-llm-hosting.md) owns `LLMClient` · [ADR-0003](0003-vector-store.md) ·
[ADR-0005](0005-guardrail-scanning.md)
