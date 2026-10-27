# ADR-0001: LLM hosting

```
Status:  Accepted (amended 2026-10-26)
Session: 1 (governance pack)
Date:    2026-10-22
```

## Context

The agent orchestrator drafts Egyptian-Arabic copy for push notifications. Copy quality
drives G2 (CSAT, opt-outs), and the LLM is the largest variable line in cost per incremental
order (G3). Two things frame the choice:

- **Dialect quality matters.** Retailers read colloquial Egyptian Arabic. Stiff Modern Standard
  Arabic reads like spam and makes people turn notifications off.
- **What the model sees is already limited.** Under P1 the model never produces numbers, and
  under P3 it never receives PII. A copy request holds a segment, an offer type, and placeholders.

## Options

**A. LLM API called directly** from each service that needs it. Strong Arabic, no GPU ops,
pay per token. Redaction, retries, and cost logging get re-implemented in every caller.

**B. Self-hosted open-weight model in-country.** No data leaves our region and cost is flat.
We take on GPU capacity, upgrades, and dialect quality we would have to fine-tune for.

**C. LLM API behind an `LLMClient` adapter.** One component owns PII tokenization, a
cheap/strong model tier per task, cost logging, retries, and failover to a second provider.

## Trade-offs

| | Dialect copy | Ops burden | Cost shape | Data exposure |
| --- | --- | --- | --- | --- |
| A | Strong | None | Per token, untracked per caller | Depends on every caller redacting correctly |
| B | Weaker until fine-tuned | High (GPUs) | Flat, high floor | None |
| C | Strong | Low | Per token, attributed per campaign | De-identified requests only, enforced in one place |

## Decision

**Option C.** Because of P1 and P3, the vendor only ever sees de-identified copy requests, so
the residency benefit of B is small at our volume while its ops cost is real. The adapter turns
P3 (tokenize before any call) and P4 (cost per call) into one component's job.

## Consequences

- No service holds an LLM API key; only `LLMClient` does.
- A redaction bug is a single-component bug with a single-component fix.
- The adapter is on the agent's path, but the agent runs in batch (ADR-0002), so its latency is not user-facing.
- We still need a DPA with the vendor, even for de-identified data (P3).

## Revisit when

Monthly LLM spend exceeds the cost of a dedicated GPU node **and** an open-weight model scores
within 5 points of the current model on our copy eval set.

## Amendments

**2026-10-26 (Session 2): fallback and evaluation.**

- **Fallback provider.** `LLMClient` wraps the primary provider in a circuit breaker. When it
  opens, requests go to the *same model* served by a second provider, not to a smaller model,
  so copy quality and eval results carry over. A smaller model would pass the outage and fail
  the eval set.
- **Provider SLA.** Each provider's SLA has to be at least as strong as the one we promise for
  the send path. A provider at 98% under a 99.9% target breaks the target by design.
- **Dead-letter queue.** Drafts that still fail go to a dead-letter queue and are replayed before
  the 09:00 approval window. A draft is never silently dropped.
- **Judge model.** The copy eval uses LLM-as-judge with a different, stronger model than the one
  writing drafts, plus a weekly sample read by Arabic reviewers. A model grading its own output
  tends to defend it.

## Related

P1, P3, P4 · [ADR-0002](0002-nba-batch-vs-realtime.md) keeps the agent off the hot path.
