# Nabd · Software Design Document

**Sessions 2–3 · building blocks and use-case flows · Ismail Mohamed · v2 · 2026-11-04**

This document follows the course SDD template: intro and facts, then one section per viewpoint.
The principles (P1–P4), goals (G1–G4) and the ARB checklist from Session 1 still apply; see the
[governance pack](01-governance-pack.md). Decisions are recorded in [`/adr`](../adr/).

**Diagrams.** Context view: [`01-governance-architecture.drawio`](../diagrams/src/01-governance-architecture.drawio).
Data and deployment view: [`02-data-deployment.drawio`](../diagrams/src/02-data-deployment.drawio)
(its PNG is exported by CI on merge).

**v2 (Session 3).** Section 7 now gives every use case two flows, ingestion or training and
inference, the way the course SDD does. Also new: guardrail scanning
([ADR-0005](../adr/0005-guardrail-scanning.md)), the training factory decision (8.1), and the
tunable values (section 11). After the mini-project feedback: storage tiers for historical data
(9.4) and supply-chain checks in CI (section 11).

---

## 1. Problem and pain points

- **Every retailer gets the same offers.** Distributors publish offers and marketing pushes them
  to everyone. Relevance is low, and so is trust (G2).
- **Next best action.** Retailers who abandon a cart or slow down before churning get nothing,
  or a generic blast days later.
- **New retailers (cold start).** A retailer who signed up yesterday has no orders, so nothing
  personal can be said about them yet.
- **Campaign drafting by hand.** Marketing writes every push in Egyptian Arabic by hand. An agent
  can draft it, as long as a person still approves what goes out at scale (P2).

## 2. Goals and non-goals

Goals are G1–G4 in the [README](../README.md): repeat orders +15% against a holdout,
CSAT 60% → 80% with opt-outs under 1%, cost per incremental order −25%, and zero unapproved
prices under PDPL.

Non-goals for v1:

- WhatsApp or SMS. Push only.
- A real-time ML model per event ([ADR-0002](../adr/0002-nba-batch-vs-realtime.md)).
- One LLM draft per retailer. Drafts are per segment × offer; names and prices go into template
  slots.
- Ranking the home page inside the Tawreed app. Nabd decides what to push, not what the app shows.

## 3. As-is

Tawreed today: the mobile app and the dashboard talk to the Tawreed backend, which writes to one
operational Postgres database. Distributors publish offers in the dashboard. Marketing sends
push notifications from the same dashboard, to everyone or to a hand-picked list. There is no
segmentation, no holdout, and no record of which push led to which order.

## 4. Assumptions

Not verified yet. Each one has a question for the next round with Tawreed.

| Assumption | Value | Why it matters |
| --- | --- | --- |
| Active retailers | ~20,000 | Size of the nightly scoring run |
| Distributors | ~150 | Offers per night, approval load |
| Concurrent dashboard users (Nabd screens) | ~30 normal, ~80 at Ramadan and Eid peaks | Sizing the Approval Console |
| Cart and order events | ~400k per day, peaks of ~50 per second in the evening | Kafka and Event Rules sizing |
| Nightly window | 00:00–06:00, approvals open at 09:00 | The pipeline has to finish inside it |
| Push opt-in | ~70% of retailers | Reach of every campaign |

## 5. Principles and key decisions

P1–P4 from Session 1 still lead. Session 2 adds three platform rules:

- **Data stays in-country, at rest and in transit.** The only exceptions are vendors under a DPA
  that never receive PII (P3): the LLM API and FCM.
- **Internal services sit behind the VPN.** The only public entry is Tawreed's API gateway, over
  HTTPS with a JWT. Inside the VPN, services may talk plain HTTP.
- **Nabd never queries Tawreed's operational database.** It reads changes through CDC.

| ADR | Decision |
| --- | --- |
| [0001](../adr/0001-llm-hosting.md) | LLM API behind `LLMClient`; amended with a same-model fallback provider and a different judge model, and a revisit of self-hosting in Session 3 |
| [0002](../adr/0002-nba-batch-vs-realtime.md) | Nightly batch plus near-real-time rules |
| [0003](../adr/0003-vector-store.md) | pgvector behind `VectorStore`; amended: lives in Nabd's own store, Qdrant considered |
| [0004](../adr/0004-own-analytical-store.md) | Own analytical store fed by CDC (Debezium → Kafka) |
| [0005](../adr/0005-guardrail-scanning.md) | Filters plus a separate guard model scan every prompt and draft; fail closed to a fixed template |
| [0006](../adr/0006-rag-chatbot.md) | Retailer questions answered by RAG behind intent routing (Session 4) |

## 6. Context viewpoint

Unchanged from Session 1: retailers, distributors and marketers use Tawreed's app and dashboard;
Nabd sits behind them and talks to two vendors, the LLM API and FCM. What Session 2 adds is
inside the box, in the next sections.

## 7. Components viewpoint

| Component | Job | Inside |
| --- | --- | --- |
| Debezium + Kafka | Moves order, cart, offer, consent and sign-up changes out of Tawreed's database | One topic per table, one data contract per topic |
| Nabd store (Postgres) | Everything Nabd knows about a retailer, plus features and vectors | CDP tables, feature tables (partitioned by month), pgvector |
| Archive (object storage, in-country) | Cold tier for history the nightly jobs no longer read | Parquet files by month, lifecycle rules (9.4) |
| Segment defaults table | Serves cold-start offers at request time, so nothing reads the CDP tables live | ~160 small lists plus a national list per shop type, rebuilt nightly |
| Airflow | Runs the nightly pipeline in order, with retries, and stops it when a step fails | One DAG, six tasks (section 9.2), plus the weekly training DAG |
| Event Rules | Reacts to sign-up, cart and stock events within minutes | Kafka consumer, one timer per cart, pre-approved templates |
| Agent Orchestrator | Drafts copy for each segment × offer | Planner, retrieval, prompt builder, guard calls, validator gate |
| Guardrail Scanner | Reads every prompt and every draft before anything moves on | Filters first, then a separate guard model ([ADR-0005](../adr/0005-guardrail-scanning.md)) |
| `LLMClient` | The only component that calls an LLM | PII tokenization, cost logging, circuit breaker, fallback, one tier per model |
| Offer Validator | Rejects any draft whose numbers don't match its offer (P1) | Deterministic code, no model |
| Approval Console | Marketer approval above 500 retailers, kill switch (P2) | Web API behind the gateway |
| Send Service | Consent check, holdout assignment, frequency cap, push (P3, P4) | FCM client, outbox table; consent comes from the sign-up screen through CDC |
| MLflow | Keeps every churn model version and its metrics | Registry; the scoring task loads the promoted version |
| Assist service (Session 4) | Answers retailer questions in the app, the only synchronous LLM path | Intent routing, read-only lookups, retrieval and re-ranking; design in [04-rag-chatbot.md](04-rag-chatbot.md) |

Each use case below has two flows. The first builds what the second reads: ingestion, nightly
jobs or training. The second is what happens when it runs for a retailer.

### 7.1 Cold start: a retailer's first day

A retailer who signs up today has no orders, so no features and no churn score. Nabd falls back to
what the sign-up tells it: shop type and governorate. There is no model here; the nightly job is a
popularity count. The full flow view, with the options and a latency budget, is in
[02-cold-start-flow.md](02-cold-start-flow.md).

**Nightly: build the defaults.**

```mermaid
sequenceDiagram
  participant K as Kafka
  participant Store as Nabd store
  participant Air as Airflow
  participant D as Segment defaults
  K->>Store: sink: retailers, orders, offers, consent
  Air->>Store: first orders of retailers who joined in the last 90 days
  Store-->>Air: orders by shop type and governorate
  Air->>Air: rank live offers per segment
  Air->>D: write one list per shop type and governorate, plus a national list per shop type
```

**On sign-up: the welcome push.**

```mermaid
sequenceDiagram
  participant DB as Tawreed DB
  participant CDC as Debezium
  participant K as Kafka
  participant R as Event Rules
  participant D as Segment defaults
  participant S as Send Service
  participant F as FCM
  DB->>CDC: retailer created (WAL)
  CDC->>K: retailer_created
  K->>R: consume
  R->>D: defaults for kiosk in Gharbia
  D-->>R: 3 offers, or the national list if the segment is empty
  R->>S: welcome template with offer slots
  S->>S: offers still live, consent, holdout, first-week cap
  S->>F: push
```

After four weeks of orders the retailer gets real features and moves to the nightly campaign
path (7.2).

### 7.2 Nightly campaign

**Nightly: features, scores and segments.**

```mermaid
sequenceDiagram
  participant Air as Airflow
  participant Store as Nabd store
  participant ML as MLflow
  participant Rank as Ranking task
  Air->>Store: data checks on yesterday's sink
  Air->>Store: build features (days since last order, basket size, push open rate)
  Air->>ML: load the promoted churn model
  Air->>Store: churn score, RFM and segment per retailer
  Air->>Rank: rank the next-best offer per retailer
  Rank->>Store: tonight's segment × offer list
```

**Nightly to 09:00: draft, check, approve, send.**

```mermaid
sequenceDiagram
  participant Air as Airflow
  participant Ag as Agent
  participant G as Guardrail Scanner
  participant L as LLMClient
  participant V as Offer Validator
  participant A as Approval Console
  participant S as Send Service
  Air->>Ag: draft per segment x offer
  Ag->>G: scan prompt (PII, injection in offer text)
  G-->>Ag: pass
  Ag->>L: prompt, no PII (P3)
  L-->>Ag: draft
  Ag->>G: scan draft (tone, policy, invented claims)
  G-->>Ag: pass, or blocked (retry up to 2, then fixed template)
  Ag->>V: check numbers and slots (P1)
  V-->>Ag: pass or reject
  Ag->>A: over 500 retailers: queue for approval (P2)
  A->>S: approved at 09:00
  S->>S: fill slots, consent, holdout, frequency cap
```

Below 500 retailers a campaign goes out without a person reading it, which is why the scanner runs
on every draft.

### 7.3 Abandoned cart

**Ingestion.** Cart changes arrive through CDC on the `cart` topic. No model trains on this path
([ADR-0002](../adr/0002-nba-batch-vs-realtime.md)). Once a week Airflow reports the
nudge-to-order rate per template against the holdout (P4), and marketing retires templates that
don't beat it.

**On a quiet cart.**

```mermaid
sequenceDiagram
  participant App as Tawreed App
  participant DB as Tawreed DB
  participant CDC as Debezium
  participant K as Kafka
  participant R as Event Rules
  participant S as Send Service
  participant F as FCM
  App->>DB: cart saved
  DB->>CDC: WAL change
  CDC->>K: cart_updated
  K->>R: subscribed to cart
  R->>R: 2 h, no checkout
  R->>S: template nudge with offer slots
  S->>S: consent, holdout, frequency cap (P3, P4)
  S->>F: push
```

The course design uses Flink for this timer. One rule at about 50 events a second fits in a plain
Kafka consumer. Flink comes in if we add rules over windows, such as "three abandoned carts in a
week".

### 7.4 Churn model

**Weekly: training.**

```mermaid
sequenceDiagram
  participant Air as Airflow
  participant W as Airflow worker (CPU)
  participant Store as Nabd store
  participant ML as MLflow
  Air->>W: weekly: train the churn model
  W->>Store: features, last 12 months
  W->>Store: labels: no order in the next 30 days
  W->>W: train gradient boosting
  W->>W: compare with the current model on last month's holdout (AUC, recall in the top 10%)
  W->>ML: register vN, only if it is better
```

**Nightly: scoring.** Part of the 00:30 task in 9.2.

```mermaid
sequenceDiagram
  participant Air as Airflow
  participant W as Scoring task
  participant ML as MLflow
  participant Store as Nabd store
  participant Rank as Ranking task
  Air->>W: score churn
  W->>ML: load the promoted version
  W->>Store: features of active retailers
  W->>Store: churn score per retailer
  Rank->>Store: retailers above the churn threshold
  Rank->>Rank: their retention offer ranks first
```

Retailers above the threshold get their retention offer through the nightly campaign (7.2). The
threshold is set with marketing, not by the model (section 11).

## 8. Deployment viewpoint

Everything runs on Kubernetes in an in-country region. The first sizing below is a starting
point for the load test, not a promise.

| Service | Pods | Request → limit | Scaling |
| --- | --- | --- | --- |
| Approval Console API | 2 | 1 vCPU / 2 GiB → 2 vCPU / 4 GiB | HPA at 70% CPU |
| Send Service | 2 | 0.5 vCPU / 1 GiB → 1 vCPU / 2 GiB | HPA on outbox length |
| Event Rules | 2 | 0.5 vCPU / 1 GiB → 1 vCPU / 2 GiB | One pod per Kafka partition, up to 6 |
| Airflow workers | per task | 1 vCPU / 2 GiB → 4 vCPU / 8 GiB | Parallel tasks, rate-limited for the LLM |
| Nabd store (Postgres) | primary + replica | sized by load test | Vertical; the replica serves the console |
| Kafka | 3 brokers (managed if in-country) | vendor sizing | Partitions |

- **No GPUs.** The models are classical and run on CPU; the LLM and embeddings come from an API
  ([ADR-0001](../adr/0001-llm-hosting.md)). GPUs come back into the plan only if we self-host.
- **Two pods minimum** for anything on the send path, so one crash doesn't stop delivery.
- **Peaks.** Ramadan and Eid move the evening peak later and higher. HPA covers the API and the
  rules; the nightly window is checked against peak-season data before Ramadan.
- **Disaster recovery.** This is Tawreed's call, not Nabd's. If Tawreed runs a second region,
  Nabd goes active-passive there: the store replicates, services stay scaled to zero until
  failover. If not, pods spread across zones in one region.

### 8.1 Training factory

Only one model trains in v1: the churn model, once a week, on tabular features. It is classical
and trains in minutes on CPU. The LLM and the embeddings come from an API.

| | A. Task on the Airflow workers (chosen) | B. Kubernetes Job per run | C. Shared training pod, always on |
| --- | --- | --- | --- |
| Fits | Small CPU jobs that finish in minutes | GPU or long jobs | Near-continuous training, or GPUs already paid for |
| Cost | Nothing new: the workers exist for the nightly DAG | Pay per run, plus node start-up | The pod is paid for 24/7 |
| Isolation | Shares the worker image, dependencies pinned | Clean image every run | Libraries drift between runs |
| Ops | None new | Job templates, quotas, autoscaling | Manual upkeep |

**Decision: A.** A dedicated pod per run would be over-engineering for a weekly CPU job. MLflow
keeps every version, and a version is promoted only if it beats the current one. The day a GPU job
appears (a self-hosted model, see the Session 3 amendment to
[ADR-0001](../adr/0001-llm-hosting.md)), it moves to B with GPU nodes that scale to zero.

## 9. Data viewpoint

### 9.1 Ingestion

Tawreed's database → Debezium (reads the write-ahead log) → Kafka → sink into Nabd's store.
The same topics feed Event Rules ([ADR-0004](../adr/0004-own-analytical-store.md)).

| Topic | Producer | Consumers | Notes |
| --- | --- | --- | --- |
| `order` | Debezium | store sink | No owner name or phone; retailer id only |
| `cart` | Debezium | store sink, Event Rules | Drives the 2-hour abandoned-cart rule |
| `offer` | Debezium | store sink, embedding task | Approved offers only reach the agent (P1) |
| `consent` | Debezium | store sink, Send Service | Opt-outs applied within minutes, not nightly |

### 9.2 Nightly pipeline

One Airflow DAG. Each task starts when the previous one succeeds. A task that fails after two
retries stops the run and pages on-call; no campaign goes out on partial data (fail closed).

| Time | Task | Runs on |
| --- | --- | --- |
| 00:00 | Data checks on yesterday's sink (row counts, nulls, late partitions) | CPU |
| 00:10 | Build features (days since last order, basket size, push open rate) | CPU, SQL |
| 00:30 | Score churn and assign segments | CPU, classical models |
| 00:45 | Rank next-best offer per retailer | CPU |
| 01:00 | Draft copy per segment × offer; scan and validate every draft | Workers + `LLMClient` |
| 06:00 | Queue for approval; small template nudges are queued to send | — |

Weekly: retrain the churn model and register the new version in MLflow (7.4). It is promoted only
if it beats the current one on last month's holdout.

### 9.3 Connections

| Source | Destination | Protocol | Port | Auth | Exposure |
| --- | --- | --- | --- | --- | --- |
| Tawreed Dashboard | API Gateway | HTTPS | 443 | JWT, TLS 1.2+ | Public, via gateway |
| API Gateway | Approval Console API | HTTP | 8080 | Internal service token | Private (VPN) |
| Tawreed orders DB | Debezium | Postgres logical replication | 5432 | Read-only replication role | Private (VPN) |
| Debezium, sink, Event Rules | Kafka | Kafka | 9092 | SASL/SCRAM | Private (VPN) |
| Airflow workers | Nabd store | Postgres | 5432 | Service account, least privilege | Private (VPN) |
| `LLMClient` | LLM API, primary and fallback | HTTPS | 443 | API keys from the vault | Outbound, allow-listed |
| Send Service | FCM | HTTPS | 443 | OAuth2 service account | Outbound, allow-listed |
| All services | Langfuse, Loki | HTTPS | 443, 3100 | Project keys | Private (VPN) |
| Prometheus | All services | HTTP | metrics port | Network policy | Private (VPN) |
| Airflow workers | Archive (object storage) | HTTPS | 443 | Service account, write only to its bucket | Private (VPN), in-country |

### 9.4 Data policy

The course SDD asks for customer data to be kept at least five years. PDPL also says not to keep
personal data longer than needed. Both hold if retention is set per class of data:

| Data | Retention | Reason |
| --- | --- | --- |
| Orders and sends (retailer id, no names) | 5 years | Accounting, and the holdout history behind P4 |
| Retailer PII (owner name, phone, location) | While active; deleted or anonymised 30 days after opt-out or account closure | PDPL minimisation |
| Features and scores | 13 months | Year-over-year seasonality for retraining |
| LLM traces | 90 days, no PII | Debugging and evals |

**Storage tiers.** Historical tables grow every night, but the nightly jobs only read recent
months. Keeping all of it in Postgres makes every backup, vacuum and restore slower for data that is
read once a week at most.

| Tier | Where | Holds | Read by |
| --- | --- | --- | --- |
| Hot | Nabd store (Postgres), one partition per month | Features and scores of the last 3 months; orders and sends of the last 13 months | Nightly pipeline, Event Rules, Approval Console |
| Cold | In-country object storage, Parquet by month | Features and scores from 3 to 13 months; orders and sends up to 5 years | Weekly churn training, audits, holdout reports |
| Deleted | None | Features and scores after 13 months; PII 30 days after opt-out | Retention job |

A monthly Airflow DAG moves partitions older than the hot window: it writes the Parquet files,
checks row counts and checksums against the partition, and only then drops it. The weekly churn
training reads hot and cold together, so 12 months of history (7.4) costs no Postgres space. Cold
files hold retailer ids only, never names or phones, so a PII deletion never has to rewrite
them. Object storage lifecycle rules delete files when they pass their retention.

Backups: daily snapshot of the store, 30 days, same region. Restore is tested each quarter. The
cold tier is versioned object storage in the same region, so it needs no snapshot of its own.

### 9.5 API and data contracts

Kept out of this document because they change more often than the design. The Approval Console
API will be described in an OpenAPI file, and each Kafka topic gets a contract (schema, owner,
version, column mapping) agreed with Tawreed's team and checked in their CI. Both will live in
`contracts/` once agreed.

## 10. Concurrency viewpoint

- **Sync and async.** Only the Approval Console is synchronous (dashboard → gateway → API).
  Everything else is async: CDC and rules run on Kafka, and the pipeline runs on Airflow.
- **Workers.** Drafting runs on a pool of workers sized to the LLM provider's rate limit, not to
  the number of drafts. ~300 drafts a night fit in well under an hour.
- **Failures.** Each LLM call has a timeout and two retries with backoff for transient errors.
  After five failures in a row the circuit breaker opens and calls go to the fallback provider
  (same model). Drafts that still fail go to a dead-letter queue and are replayed before 09:00.
- **Guardrail scans.** Two per draft, each with a 10-second timeout. A timeout counts as a block:
  after two retries the segment × offer gets its fixed template
  ([ADR-0005](../adr/0005-guardrail-scanning.md)).
- **Shared state.** Holdout assignment is decided once per retailer per campaign and stored, so a
  retried send cannot move a retailer between groups. The agent checkpoints its run state, so a
  restart resumes instead of drafting twice.
- **Sending.** The Send Service writes to an outbox table before calling FCM, so a crash between
  "approved" and "sent" is retried, not lost or sent twice.

## 11. Operation viewpoint

### Service level objectives

Load-tested on pre-prod, which mirrors production (same network rules, same gateway, same
security). Numbers are first targets.

| Path | Availability | Latency | Throughput |
| --- | --- | --- | --- |
| Approval Console API | 99.5% | p50 < 100 ms, p95 < 500 ms | 50 RPS |
| Abandoned-cart nudge | 99.9% of triggers sent | p95 < 5 min from the 2-hour mark | 50 events/s peak |
| Nightly pipeline | Done by 06:00 on 29 of 30 nights | — | 20,000 retailers |

### Observability

| Tool | What we watch | Alert |
| --- | --- | --- |
| Prometheus + Grafana | p95 per API, Kafka lag, replication slot size, DAG task status | p95 over target 15 min (S1); DAG failed (S1) |
| Loki | Logs from every service, no PII | — |
| Langfuse (self-hosted) | One trace per draft: tokens, cost, guard result, validator result, judge score | Guard block rate over 5% in a night (S1); cost per incremental order over target 3 days (S2) |
| MLflow | Churn model versions and metrics | — |

Severity: **S0** pages on-call now (send path sending to opted-out retailers, validator down).
**S1** goes to the team channel with a ticket. **S2** goes in the daily digest.

### Tunable values

None of these is hard-coded. They live in a `nabd_config` table in the Nabd store, every change
is logged with who made it and why, and jobs read them when they start. Changing one doesn't need
a deployment.

| Value | Starting point | Owner | Used in |
| --- | --- | --- | --- |
| Cold-start window (first orders of recent sign-ups) | 90 days | Data | 7.1 |
| Move to personal ranking after | 4 weeks of orders | Marketing | 7.1, 7.2 |
| Churn label | No order in the next 30 days | Data | 7.4 |
| Churn threshold for a retention offer | Score 0.6, reviewed monthly | Marketing | 7.4 |
| Abandoned-cart delay | 2 hours | Marketing | 7.3 |
| Approval required above | 500 retailers | Marketing | 7.2 (P2) |
| Pushes in a retailer's first week | 2 | Marketing | 7.1, Send Service |
| Circuit breaker opens after | 5 failures in a row | Platform | `LLMClient` |
| Hot window for features and scores | 3 months | Data | 9.4 |

### Security clearance

Before each release: the security survey and the ARB security checks from Session 1, run on
pre-prod, with sign-off from the security owner.

Every service ships as a container image, so the CI pipeline checks what goes into each image,
not only the code:

| Check | When | Fails the build when |
| --- | --- | --- |
| Image scan (Trivy) | Every build | A critical or high CVE has a fix available |
| Dependency scan and SBOM | Every build | A dependency has a known critical CVE; the SBOM is kept with the release |
| Secrets scan (gitleaks) | Every pull request | A key, token or password is committed |
| Image signing (cosign) | On release | Not signed; the cluster only runs signed images from the in-country registry |

Images already running are rescanned every night in the registry. A new critical CVE in a running
image opens a ticket (S1) and is patched by rebuilding on the fixed base image.

## 12. Open questions for the next round

1. Does Tawreed run a second region? That decides DR.
2. Can Debezium get a replication role on the orders database, and who owns the contracts?
3. Is there an in-country managed Kafka, or do we run our own?
4. Which second LLM provider serves the same model, and what SLA does it sign?
5. Which model serves as the guard, and who in marketing signs off the scan policy?
6. What churn threshold can marketing act on: how many retention offers a week can distributors fund?
