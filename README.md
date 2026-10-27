# AI Architecture Portfolio

Coursework and capstone for the **AI Architecture Design** course (MLOps MENA Academy, Oct–Dec 2026).

## Scenario

**Tawreed** is a B2B wholesale marketplace in Egypt. Small retailers such as groceries,
kiosks and mini-markets use the mobile app to reorder stock from distributors. Distributors and the marketing team work from a web dashboard.

**Nabd** is the marketing automation system inside Tawreed. Each night it scores every retailer
and picks the offer that fits them best. An agent then writes the push notification for that
offer, and it can only use offers the distributor has approved. A few cases can't wait until
the next night, like an abandoned cart, so simple rules handle those within minutes.

The scenario is made up for this course.

| Goal | Target |
| --- | --- |
| **G1** Repeat orders | Monthly reordering retailers +15% vs a holdout group |
| **G2** Relevance & trust | Retailer CSAT 60% → 80%; opt-out rate ≤ 1% per campaign |
| **G3** Cost | Marketing cost per incremental order −25% (LLM + push) |
| **G4** Compliance | Zero messages with a price or discount the distributor didn't approve; PDPL-compliant |

## Non-goals for v1

- WhatsApp or SMS. Push only
- A real-time ML model per event (see ADR-0002)
- One LLM draft per retailer. Drafts are per segment and offer; names and prices go into template slots
- Ranking the home page inside the Tawreed app. Nabd decides what to push, not what the app shows

## Assumptions (not verified yet)

- ~20,000 active retailers and ~150 distributors
- Nabd keeps its own Postgres, filled by change data capture from Tawreed's orders database. It never
  queries Tawreed's operational database (see ADR-0004)
- ~30 people use Nabd's dashboard screens at once on a normal day, ~80 at Ramadan and Eid peaks
- ~70% of retailers have push notifications turned on
- Most orders are weekly or biweekly reorders of the same SKUs
- Personal data can be processed in an in-country (or counsel-approved) cloud region

## How to read this repo

| Folder | Contents |
| --- | --- |
| [docs/](docs/) | One document per session. Start with the latest one |
| [diagrams/](diagrams/) | draw.io sources and exported PNGs |
| [adr/](adr/) | One file per architecture decision, numbered across the whole course |
| [capstone/](capstone/) | Final architecture document and slides |
| [tools/](tools/) | Checks that run in CI |

## Sessions

| # | Topic | Deliverable |
| --- | --- | --- |
| 01 | Architecture views, steps & process | [Governance pack](docs/01-governance-pack.md) · [diagram](diagrams/src/01-governance-architecture.drawio) · [ADR 0001–0003](adr/) |
| 02 | AI system building blocks | [Software design document](docs/02-sdd.md) · [diagram](diagrams/src/02-data-deployment.drawio) · [ADR 0004](adr/0004-own-analytical-store.md) |
