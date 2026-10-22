# Governance Pack, Nabd, AI Marketing Automation for Tawreed

Session 1 mini project · Ismail Mohamed · 2026-10-22

**System.** Nabd is the marketing automation system inside Tawreed, a B2B wholesale
marketplace where Egyptian retailers reorder stock from distributors. A nightly job scores each
retailer (segment, churn risk) and picks the best offer for them. An agent orchestrator then
plans each message, retrieves the approved offer and past campaigns from pgvector, asks the LLM
for a draft through `LLMClient`, and passes the draft to an Offer Validator before a marketer
approves it. Simple rules cover the few cases that can't wait for the night, like an abandoned
cart. The mobile app
and the dashboard sit outside Nabd.

**Goals.** G1 repeat orders +15% · G2 CSAT from 60% to 80%, opt-out under 1% · G3 cost per
incremental order down 25% · G4 no unapproved prices, PDPL compliant

**Diagram.** [`01-governance-architecture.drawio`](../diagrams/src/01-governance-architecture.drawio)
([PNG](../diagrams/src/export/01-governance-architecture.png))

---

## 1 · Principles

| # | Principle | Business goal | Forces in the design |
| --- | --- | --- | --- |
| **P1** | **Only approved offers.** Every price, discount and stock claim in a message comes from the approved offer catalog. The LLM writes the wording and never the numbers | G4, G2. One wrong price costs the distributor money and the retailer's trust | Retrieval reads approved offers only; numbers are template slots filled from the DB; the Offer Validator rejects any draft whose numbers don't match its offer |
| **P2** | **A person approves anything sent at scale.** A campaign to more than 500 retailers, or to a new segment, needs a marketer's approval. Single template reminders go out on their own | G2, G4 | Approval Console between the Offer Validator and the Send Service; kill switch per campaign; weekly sample review |
| **P3** | **Retailer data stays minimal and in-country (PDPL).** No personal data (phone, owner name, shop location) reaches the LLM vendor, and nothing is sent without consent for that channel | G4, legal compliance | `LLMClient` tokenizes PII before any call; agent sees segment features and placeholders; Send Service checks consent per channel |
| **P4** | **Every send is measured against a holdout.** Each message is traced and costed, and its effect is compared with a 10% control group | G1, G3. Without a holdout we can't tell new orders from orders that would have happened anyway | Trace per stage (tokens, push sends); 10% holdout per campaign; cost per incremental order on a dashboard |

**Why P4 uses a holdout.** Counting orders placed after a message always looks good, because most
retailers would have reordered anyway. P4 only counts the difference between retailers who got the
message and the 10% who didn't. If that difference is zero, the campaign is costing money.

## 2 · ADRs

Full records in [`/adr`](../adr/).

| ADR | Options | Key trade-off | Decision · revisit when |
| --- | --- | --- | --- |
| [**0001** LLM hosting](../adr/0001-llm-hosting.md) · Accepted | A) LLM API called directly · B) self-hosted open model in-country · C) LLM API behind an `LLMClient` adapter with PII tokenization and model tiering | A/C: strong Egyptian-Arabic copy, no GPU ops · B: data stays inside, but GPU ops and weaker dialect copy | **C.** P1 + P3 mean the vendor only sees de-identified copy requests; the adapter owns redaction, cost logging, and failover. *Revisit:* monthly LLM spend > a GPU node **and** an open model is within 5 pts on our copy eval set |
| [**0002** NBA: batch vs real-time](../adr/0002-nba-batch-vs-realtime.md) · Accepted | A) nightly batch · B) real-time model per event · C) nightly batch + near-real-time rules for named triggers | A: cheap, up to 24 h stale · B: fresh, but a model in the hot path for every event · C: batch cost with fast reaction where it pays | **C.** Batch ranking nightly; template nudges for abandoned cart (2 h) and usual-SKU back in stock. *Revisit:* a trigger's uplift over holdout justifies a real-time model |
| [**0003** Vector store](../adr/0003-vector-store.md) · Accepted | A) pgvector in our Postgres · B) managed Pinecone · C) no vectors, SQL/keyword retrieval | A: no new vendor or PDPL flow, enough for ~50k SKUs · B: ops-free, but a cross-border processor · C: misses Arabic/English product synonyms | **A**, behind a `VectorStore` interface. *Revisit:* > 5M vectors or p95 retrieval > 200 ms |

## 3 · ARB, Architecture Review Board

**Who.** Architect (chair), growth/marketing lead, platform engineer, privacy owner.
**When.** Any change that adds a vendor, a channel or an agent tool, a review every two weeks,
and a required pass before each production release. **Passing.** Every check is Yes, No or N/A
with a link to evidence. A No needs a written exception with an owner and a date. Two open
exceptions in the same area block the release.

| Area | Checks |
| --- | --- |
| **Security** | ☐ Threat model covers prompt injection through product names and distributor-entered offer text ☐ Agent tools least-privilege (read catalog and segments; write drafts only) ☐ Secrets in a vault; outbound allow-list to listed vendors ☐ Dashboard behind SSO with roles (distributor, marketer) |
| **Privacy (PDPL)** | ☐ Data classified: phone, owner name, shop location, order history ☐ Consent recorded per channel before any send (P3) ☐ No PII in prompts, traces, or eval sets, weekly scan ☐ DPA and processing region confirmed for the LLM vendor and FCM ☐ Opt-out honoured within 24 h |
| **Evals** | ☐ Copy eval set (≥ 200 offers) passes: 100% number match (P1), tone ≥ 4/5 by Arabic reviewers ☐ Ranking beats the rules baseline on last month's holdout ☐ Injection test set (≥ 50 cases) passes before release |
| **Cost** | ☐ Cost per incremental order on a dashboard (P4) ☐ Token and push spend per campaign ☐ Budget alert per vendor |
| **Human oversight** | ☐ Approval required above 500 recipients or for a new segment (P2) ☐ Named owner per campaign ☐ Kill switch tested each release ☐ Audit log of approvals and sends |

**PDPL.** Egypt's Personal Data Protection Law (Law No. 151 of 2020) requires a permit to transfer
personal data outside the country. P3 keeps personal data away from the LLM vendor. Firebase Cloud
Messaging still receives a device token with each message, so it needs a data processing agreement. Confirm the current
procedure with a lawyer.

**Runtime triggers.**

| Signal | Threshold | Action | Owner |
| --- | --- | --- | --- |
| Number-mismatch validator rejects | any in production | Pause the campaign; root-cause before resuming (P1) | Architect |
| Opt-out rate | > 1% on a campaign | Pause the campaign; marketer review (G2) | Growth lead |
| Uplift vs holdout | ≤ 0 for 2 weeks | Retire or redesign the campaign (P4) | Growth lead |
| Cost per incremental order | over target 3 days running | Cost review; model-tier audit (G3) | Platform engineer |

## 4 · Automated guardrails (optional)

Three checks run in GitHub Actions on every push:

- [`tools/arch_lint.py`](../tools/arch_lint.py) fails the build if an ADR is missing a required section or cites no principle, if a principle in this pack doesn't appear in the diagram, or if this page grows past two pages.
- The diagram's PNG is exported from the `.drawio` file automatically, so the picture can't drift from the source.
- Every link in the markdown files is checked.
