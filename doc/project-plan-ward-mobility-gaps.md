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
4. How are those patterns **changing over years** (growth, seasonality, time-of-day mix)?
5. Can we produce ward-level briefs that are useful to residents, civic groups, and councillor offices?

---



## Datasets (Toronto open data and related)


| Dataset                                         | Role                                                         |
| ----------------------------------------------- | ------------------------------------------------------------ |
| PTC Summary and Trip Data / yearly trip ZIPs    | Ride-hail OD by ward and time                                |
| City Wards                                      | Official geography for mapping and joins                     |
| TTC Routes and Schedules (GTFS)                 | Transit time, transfers, frequency                           |
| Neighbourhood Profiles                          | Demand-side context (car ownership, income, age, employment) |
| TTC delay datasets (optional)                   | Reliability story                                            |
| Transportation Tomorrow Survey / TTS (optional) | Mode-share baseline between areas                            |
| Local engagement proposals (optional)           | Qualitative resident signals                                 |


Primary eligibility requirement: use at least one dataset from [open.toronto.ca](https://open.toronto.ca/).

---



## Multi-year / time-series analysis

The repo already loads PTC trips into per-year tables (`pts_trips_yearly_2024`, `pts_trips_yearly_2025`, …) with `dt`, `pickup_hr`, `pickup_ward`, `dropoff_ward`, and `trips_total`. Multi-year data lets us ask not only where gaps are, but whether they are **worsening**.

### Panel table (required foundation)

Union years into one OD time series (example grain: daily):

- Keys: `dt`, `origin_ward`, `dest_ward` (plus derived `year`, week, month)
- Metrics: `SUM(trips_total)`, optional averages for wait / duration / distance
- Filter out non-Toronto / placeholder wards consistently across years

Suggested materialized object: `ward_od_daily` (then roll up to weekly / monthly as needed).

| Grain | Use for |
|-------|---------|
| Daily | Shocks, events, weather |
| Weekly | Smooth noise for corridor charts |
| Monthly | Year-over-year growth and seasonality |
| Hour-of-day x weekday | Night vs peak “gap” stories |
| Year | Rankings and simple before/after |

### Metrics to track per ward pair over time

- Trip volume and share of citywide trips
- Growth: YoY % change, or index a base year to 100
- Within-ward vs between-ward mix
- Time-of-day mix (% night / AM peak / PM peak)
- PTC service proxies: wait, duration, distance averages when present

Core time-series question: do **high transit-friction** corridors **grow faster** than well-served ones?

### Analysis patterns for the public product

1. Rank stability — top OD pairs by year; who entered or left the top set
2. Growth leaders — fastest-growing edges (absolute and %)
3. Seasonality — same month across years
4. Diurnal shift — is growth mostly late-night (weaker transit) or all-day
5. Optional association checks — growth vs transit friction (labeled carefully; not causation)
6. Policy/context windows — note major construction or VFH policy periods without overclaiming

### Transit friction caveat

PTC OD is a true multi-year series. GTFS-based transit scores are **not**, unless we version schedule snapshots (feeds change often).

- **v1:** one GTFS snapshot (static friction) + moving PTC volumes over years
- **v2 (stretch):** yearly or seasonal GTFS archives so friction also becomes a time series

### Narrative value

| Cross-section (one year) | Time series (multiple years) |
|--------------------------|------------------------------|
| Where are the gaps? | Are gaps worsening? |
| Which corridors are hot? | Which are accelerating? |
| Link to 2030 ZEV | Show demand growth electrification alone will not absorb |

### Methods (keep lightweight for v1)

Line charts and small multiples for selected corridors; month x hour heatmaps; simple indexes and YoY tables. Heavy forecasting models are optional stretch, not required for the award entry.

---



## Who we need (roles)

You do not need to fill every role. Small teams can cover multiple hats.


| Role                | Responsibilities                                        | Skills                                     |
| ------------------- | ------------------------------------------------------- | ------------------------------------------ |
| Project lead        | Scope, timeline, award submission, stakeholder outreach | Organization, writing                      |
| Data / backend      | PTC loads, multi-year `ward_od_*` panels, Postgres      | Python, SQL, pandas                        |
| Transit analyst     | GTFS processing, transit friction scores per ward pair  | GTFS, routing or network analysis          |
| Analysis / research | Stats, time series, corridor case studies               | Urban / transport analysis                 |
| Frontend / viz      | Public map, charts, accessible UI                       | Web map (e.g. MapLibre/Leaflet), dashboard |
| Design / comms      | Plain-language stories, visuals, outreach materials     | Writing, design                            |
| Community liaison   | Feedback from residents, civic tech, councillor staff   | Facilitation, outreach                     |


**Time expectation (working estimate):** 3–6 hours/week per person through late 2026, with heavier weeks before the Dec. 4 submission.

---



## Timeline (working plan)


| Phase              | Window                      | Outcomes                                                                                                                                 |
| ------------------ | --------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Foundations     | Now → +3 weeks              | Confirm team; materialize multi-year `ward_od_daily` from PTC yearly tables; join City Wards; publish a short public README for the award project |
| 2. Transit layer   | Weeks 4–7                   | GTFS-based transit scores for top OD pairs; draft methodology note                                                                       |
| 3. Insights        | Weeks 8–10                  | First 3 corridor case studies; draft maps/charts; internal review                                                                        |
| 4. Public product  | Weeks 11–14                 | Public dashboard or illustrated report live on the web; open GitHub docs                                                                 |
| 5. Engagement      | Ongoing after public launch | Collect feedback (civic meetup, councillor office, resident groups); iterate                                                             |
| 6. Award packaging | Nov–Dec 4, 2026             | Submission write-up: problem, users, impact evidence, open code/docs                                                                     |


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

Projects such as the School of Cities Toronto ridehailing charts and City VFH studies already describe citywide ride-hail trends (congestion share downtown, deadheading, licensing caps). This project’s niche is joining **ward OD ride-hail** with **transit connection quality** into an explanation layer that residents and local decision-makers can use. See **Required reading** below for the main Toronto debates and evidence base.

---



## Link to Toronto’s 2030 VFH zero-emission goal

Toronto is moving the vehicle-for-hire (VFH) sector toward **zero-emission vehicles by 2030** (Council direction on net-zero VFH, related grant programs, and ZEV-related licence rules). Electrifying Uber/Lyft fleets cuts **tailpipe emissions per kilometre**. It does **not** by itself reduce congestion, empty driving (deadheading), or the need for ride-hail where transit connections are weak.

**How this project helps that goal:**

1. **Reduce avoidable VFH kilometres** — Ward OD pairs with high ride-hail and high transit friction point to places where better transit can displace trips, so fewer kilometres need to be electrified, charged, and regulated.
2. **Site charging and operations** — OD and peak-hour maps show where PTC demand concentrates, informing where VFH charging, curb, and depot policy matter most for an all-EV fleet.
3. **Separate necessary mobility from inefficient circulation** — Corridor stories can flag trips that are hard to replace (night service, accessibility, last-mile) versus corridors that look like poor connections or oversupply.
4. **Support equity in the transition** — City debates already note impacts in areas without higher-order transit; ward-level evidence makes that concrete for caps, ZEV rules, and transit investment together.

**One-line framing:** Electrifying ride-hail by 2030 cuts emissions per kilometre; this project shows **which ward-to-ward trips are transit gaps vs preference**, so the City can cut avoidable VFH kilometres and put charging and transit investment where the remaining EV fleet will actually be needed.

Relevant background is in the 2024 VFH by-law review and supplemental reports listed under **Required reading** (net-zero VFH, caps, ZEV exemptions).

---



## Required reading

New contributors should skim these before picking a workstream. They cover congestion, empty driving (deadheading), policy debates, and public open-data work already online.

### City of Toronto (policy + evidence)

| Resource | Why read it |
|----------|-------------|
| [2024 Review of the Vehicle-for-Hire By-law and Industry](https://www.toronto.ca/legdocs/mmis/2024/ex/bgrd/backgroundfile-251312.pdf) | Staff framing of PTC growth, downtown share (~14% of downtown traffic), efficiency decline, and driver-cap recommendations |
| [Executive Summary: 2024 Transportation Impact Study](https://www.toronto.ca/legdocs/mmis/2024/ex/bgrd/backgroundfile-251317.pdf) | Short version of congestion vs construction context; citywide vs downtown PTC share |
| [The Transportation Impacts of Vehicle-for-Hire in the City of Toronto (full study)](https://www.toronto.ca/legdocs/mmis/2024/ex/bgrd/backgroundfile-251488.pdf) | Deep dive: VKT, user survey (HDR), U of T Mobility Network modelling |
| [Supplemental report wrapping the 2024 impact study](https://www.toronto.ca/legdocs/mmis/2024/ex/bgrd/backgroundfile-251487.pdf) | Council decision history (caps, net-zero VFH, litigation context) |
| [2019 VFH bylaw review / transportation impacts report](https://www.toronto.ca/wp-content/uploads/2019/06/96c7-Report_v1.0_2019-06-21.pdf) | Earlier baseline: OD patterns, equity, relationship to transit |

### Research and open-data analysis

| Resource | Why read it |
|----------|-------------|
| [How Much Ridehail Travel Is Deadheading? (Findings, School of Cities)](https://findingspress.org/article/164827-how-much-ridehail-travel-is-deadheading-estimating-its-share-and-evolution-in-toronto) | Peer-reviewed estimate of empty VKT and unpaid in-app time using City open data |
| [Toronto ridehailing charts](https://schoolofcities.github.io/ridehailing/toronto-trends) + [GitHub](https://github.com/schoolofcities/ridehailing) | Public viz of trips, drivers, VKT, fares; closest existing open project |
| [City of Toronto bdit_triplinker](https://github.com/CityofToronto/bdit_triplinker) | City tooling for linking VFH OD trips into driver shifts |

### Advocacy, media, and public debate

| Resource | Why read it |
|----------|-------------|
| [RideFair — How Low Can Ridehail Driver Pay Go?](https://ridefair.ca/wp-content/uploads/2026/05/Ridefair-Report_May_2026_final.pdf) | Advocacy analysis of deadheading, wages, and downtown congestion |
| [Globe and Mail: drivers spend half their time without a passenger](https://www.theglobeandmail.com/business/article-toronto-rideshare-drivers-spend-half-of-their-time-on-the-road-without/) | Plain-language summary of deadheading and pay implications |
| [CBC: ride-share driver cap debate at Executive Committee](https://www.cbc.ca/news/canada/toronto/ride-share-cap-debate-1.7406508) | Political / stakeholder arguments (drivers, Uber, congestion) |
| [Star: staff recommend limiting Uber/Lyft drivers for congestion](https://www.thestar.com/news/gta/limit-the-number-of-uber-lyft-drivers-to-help-with-toronto-congestion-staff-report-recommends/article_cc434222-b102-11ef-8b6d-5b56d13e70ae.html) | How City findings entered the public licence-cap debate |

**Takeaway for this project:** most existing discussion is citywide or downtown (share of traffic, empty kilometres, caps). Our gap is **ward-to-ward OD + transit friction**, not redoing the deadheading or cap debate from scratch.

---



## How to join

1. Read this plan, the **Required reading** section above, and the repo [README](../README.md) / [walkthrough](walkthrough.md).
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


| Date       | Change                                                                        |
| ---------- | ----------------------------------------------------------------------------- |
| 2026-08-17 | Initial recruiting / award project plan drafted from traffic-study discussion |
| 2026-08-17 | Added Required reading: City VFH studies, deadheading research, advocacy/media |
| 2026-08-17 | Added section linking the project to Toronto’s 2030 VFH zero-emission goal |
| 2026-08-18 | Added multi-year / time-series analysis section; updated research questions and Phase 1 |


