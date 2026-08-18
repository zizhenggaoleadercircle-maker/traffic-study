# Project plan: Why Ride-Hail Here? Ward-to-Ward Mobility Gaps in Toronto

Recruiting brief and working plan for a Toronto open-data project. Share this document with people who might want to join.

**Status:** Proposed  
**Target submission:** [Toronto Open Data Awards 2026](https://open.toronto.ca/toronto-open-data-awards-2026-call-for-submissions/) (deadline Dec. 4, 2026)  
**Likely award category:** Open Data Analysis (upgrade to Open Data Applications if we ship a public interactive tool)  
**Related repo:** [traffic-study](https://github.com/zizhenggaoleadercircle-maker/traffic-study)

---

## One-sentence pitch

We use Toronto’s ride-hail open data with TTC schedules and ward boundaries to show where people rely on Uber/Lyft between wards — and whether that looks like a transit connection gap, not just preference.

---

## Civic problem

Residents and councillors often debate traffic, parking, and ride-hail growth ward by ward, but public tools rarely connect:

1. **Where ride-hail trips actually flow** (origin ward → destination ward), and
2. **How hard the same trip is by transit** (time, transfers, late-night frequency).

Without that link, high ride-hail corridors get treated as “preference” or “congestion” when they may reflect **limited public transit or bad connections**.

This project makes that comparison visible, evidence-based, and shareable.

---

## What we will build

### Core deliverable (required for the award)

A **public analysis product** (report + interactive map/dashboard) that:

- Builds a **ward-to-ward origin–destination (OD) matrix** from City of Toronto Private Transportation Company (PTC) trip data
- Scores the same ward pairs for **transit friction** using TTC GTFS (travel time, transfers, off-peak/night service)
- Adds context from neighbourhood / census profiles (and optionally TTS mode share and TTC delay data)
- Publishes **5–8 short corridor stories** (e.g. Willowdale ↔ downtown at night) that non-technical readers can understand
- Optionally overlays resident proposals from local engagement (e.g. Willowdale “Let’s Talk Traffic”) as qualitative corroboration

### Stretch deliverable

A simple public web app: pick two wards → see ride-hail volume vs transit alternatives → share a linkable brief.

### What already exists in this repo

- Python package and CLIs to load Toronto CKAN PTC data into PostgreSQL
- Yearly trip tables with `pickup_ward`, `dropoff_ward`, and `pickup_hr`
- Analysis notebook starter and documentation under `doc/`

The award entry is **not** “we loaded data into Postgres.” The award entry is the **public insight product** built on top of that pipeline.

---

## Research questions

1. Which ward pairs have the highest ride-hail OD volumes (within-ward and between-ward)?
2. Do high ride-hail OD pairs also have high transit friction (long trips, many transfers, weak night service)?
3. When transit looks strong but ride-hail remains high, what other factors show up (income, car ownership, nightlife hours, reliability)?
4. Can we produce ward-level briefs that are useful to residents, civic groups, and councillor offices?

---

## Datasets (Toronto open data and related)

| Dataset | Role |
|--------|------|
| PTC Summary and Trip Data / yearly trip ZIPs | Ride-hail OD by ward and time |
| City Wards | Official geography for mapping and joins |
| TTC Routes and Schedules (GTFS) | Transit time, transfers, frequency |
| Neighbourhood Profiles | Demand-side context (car ownership, income, age, employment) |
| TTC delay datasets (optional) | Reliability story |
| Transportation Tomorrow Survey / TTS (optional) | Mode-share baseline between areas |
| Local engagement proposals (optional) | Qualitative resident signals |

Primary eligibility requirement: use at least one dataset from [open.toronto.ca](https://open.toronto.ca/).

---

## Who we need (roles)

You do not need to fill every role. Small teams can cover multiple hats.

| Role | Responsibilities | Skills |
|------|------------------|--------|
| Project lead | Scope, timeline, award submission, stakeholder outreach | Organization, writing |
| Data / backend | PTC loads, ward OD tables, Postgres, data quality | Python, SQL, pandas |
| Transit analyst | GTFS processing, transit friction scores per ward pair | GTFS, routing or network analysis |
| Analysis / research | Stats, corridor case studies, careful interpretation | Urban / transport analysis |
| Frontend / viz | Public map, charts, accessible UI | Web map (e.g. MapLibre/Leaflet), dashboard |
| Design / comms | Plain-language stories, visuals, outreach materials | Writing, design |
| Community liaison | Feedback from residents, civic tech, councillor staff | Facilitation, outreach |

**Time expectation (working estimate):** 3–6 hours/week per person through late 2026, with heavier weeks before the Dec. 4 submission.

---

## Timeline (working plan)

| Phase | Window | Outcomes |
|-------|--------|----------|
| 1. Foundations | Now → +3 weeks | Confirm team; materialize `ward_od_daily` from existing PTC tables; join City Wards; publish a short public README for the award project |
| 2. Transit layer | Weeks 4–7 | GTFS-based transit scores for top OD pairs; draft methodology note |
| 3. Insights | Weeks 8–10 | First 3 corridor case studies; draft maps/charts; internal review |
| 4. Public product | Weeks 11–14 | Public dashboard or illustrated report live on the web; open GitHub docs |
| 5. Engagement | Ongoing after public launch | Collect feedback (civic meetup, councillor office, resident groups); iterate |
| 6. Award packaging | Nov–Dec 4, 2026 | Submission write-up: problem, users, impact evidence, open code/docs |

Adjust dates as the team forms. Keep a public URL live well before the deadline.

---

## Success metrics (for recruitment and for the award)

- Public URL with clear research question and methods
- Reproducible open code in this (or a linked) repository
- At least 3 corridor stories with evidence, not anecdotes alone
- Documented feedback from at least one external audience (residents, civic tech, or City/councillor staff)
- Measurable reach if possible (visits, shares, mentions, workshop attendance)
- Award submission completed by Dec. 4, 2026

---

## Principles

- **Public and free:** no paywall (award eligibility)
- **Careful claims:** correlation is not proof; distinguish transit gaps from preference, nightlife, luggage, accessibility needs, and parking costs
- **Open by default:** code, methods, and caveats documented
- **Privacy-aware:** use ward-level aggregates from published open data; do not attempt to re-identify individuals
- **Useful to non-experts:** every chart should answer “so what?” for a resident or councillor

---

## How this differs from existing work

Projects such as the School of Cities Toronto ridehailing charts and City VFH studies already describe citywide ride-hail trends. This project’s niche is joining **ward OD ride-hail** with **transit connection quality** into an explanation layer that residents and local decision-makers can use.

---

## How to join

1. Read this plan and the repo [README](../README.md) / [walkthrough](walkthrough.md).
2. Tell the project lead which role(s) you want and roughly how many hours/week you can give.
3. Pick a first task from Phase 1 (OD table, wards join, methodology draft, or recruitment outreach).

**Contact:** add maintainer contact / chat link here before sharing widely.

---

## Open questions for the founding team

- Grassroots vs funded track for judging — confirm how we will describe ourselves
- Hosting for the public site (GitHub Pages, static host, etc.)
- Whether TTS access is in scope for v1 or deferred
- Geographic focus for v1: citywide vs a pilot set of wards (e.g. North York / Willowdale stories first)

---

## Changelog

| Date | Change |
|------|--------|
| 2026-08-17 | Initial recruiting / award project plan drafted from traffic-study discussion |
