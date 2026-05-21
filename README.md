# traffic-study

Python tooling to load **City of Toronto Open Data** ([CKAN](https://open.toronto.ca/)) ride-hailing and vehicle datasets into **PostgreSQL**. The installable package lives under `src/traffic_study` and exposes console commands for connection checks, CKAN datastore samples, yearly trip ZIP imports, and a one-time migration from a legacy unified yearly trips table.

## What this repository contains

- **Operating hours** — sample import of vehicle operating hours from the CKAN datastore.
- **Summary trip data** — trip sample plus summary statistics from CKAN.
- **Yearly trip ZIPs** — full-year `trips_YYYY.zip` style payloads into per-year tables (`pts_trips_yearly_{year}`).
- **Migration helper** — split legacy unified `pts_trips_yearly` into per-year tables when upgrading an older database.

For table names, environment variables, troubleshooting, and a full module map, see **[doc/walkthrough.md](doc/walkthrough.md)**.

## Prerequisites

- **Python** 3.10 or newer (see [pyproject.toml](pyproject.toml)).
- **PostgreSQL** reachable from your machine; loaders expect `DATABASE_URL`.
- **Network access** to Toronto’s CKAN / datastore endpoints when running imports (not required for `traffic-connect` alone).

## Setup

```bash
git clone https://github.com/zizhenggaoleadercircle-maker/traffic-study.git
cd traffic-study   # or your clone folder name, e.g. traffic
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Runtime dependencies are declared in [pyproject.toml](pyproject.toml) and mirrored in [dep/requirements.txt](dep/requirements.txt). The root [requirements.txt](requirements.txt) includes `dep/requirements.txt` so you can also run:

```bash
pip install -r requirements.txt
```

## Configuration

Copy [.env.example](.env.example) to `.env` in the project root and set **`DATABASE_URL`**. The example file documents URL shape, percent-encoding passwords with special characters, and optional `sslmode`. Never commit `.env` (it is listed in [.gitignore](.gitignore)).

## Repository layout

| Directory | Purpose |
|-----------|---------|
| [src/traffic_study/](src/traffic_study/) | Installable Python package: loaders, [parsers](src/traffic_study/parsers.py), [datastore](src/traffic_study/datastore.py) helpers |
| [doc/](doc/) | Documentation: [walkthrough](doc/walkthrough.md), [Vision Zero landscape](doc/vision-zero-landscape.md), reference PDF [RidehailingEmptyTrips.pdf](doc/RidehailingEmptyTrips.pdf) |
| [analysis/](analysis/) | Jupyter notebooks and ad hoc analysis (e.g. [trips_yearly.ipynb](analysis/trips_yearly.ipynb)) |
| [dep/](dep/) | Dependency listings (`requirements.txt` mirror of [pyproject.toml](pyproject.toml)) |
| [tests/](tests/) | Unit tests |
| [samples/](samples/) | Optional examples (placeholder) |
| [res/](res/) | Static resources / assets (placeholder) |
| [tools/](tools/) | Helper scripts not part of the package |
| [.config/](.config/) | Versioned configuration notes (no secrets) |
| `build/` | Local build output (gitignored) |

Root files: [pyproject.toml](pyproject.toml), [README.md](README.md), [.env.example](.env.example).

## Commands (after `pip install -e .`)

| Command | Role |
|---------|------|
| `traffic-connect` | Test Postgres connection |
| `traffic-import-operating-hours` | CKAN operating hours sample |
| `traffic-import-summary-trip-data` | CKAN trips sample + summary stats |
| `traffic-import-trips-yearly-zip` | Yearly `trips_YYYY.zip` into `pts_trips_yearly_{year}` |
| `traffic-migrate-yearly-split` | One-time migration from legacy unified `pts_trips_yearly` |

Each module is also runnable as `python -m traffic_study.<module>` (for example `python -m traffic_study.connect`). Use `--help` on each command where supported for flags such as `--dry-run`.

## Notebooks

The [analysis/](analysis/) folder holds notebooks that assume you have set up the environment above and have access to the same database or exported data. Install Jupyter in your venv if needed: `pip install jupyter`.

## Tests

```bash
pip install -e .
python -m unittest discover -s tests -t .
```

## Data and upstream

Datasets are provided by the **City of Toronto** under their [Open Data terms](https://open.toronto.ca/open-data-licence/). This project is an independent loader; refer to Toronto Open Data for dataset definitions and updates.

## Repository

[https://github.com/zizhenggaoleadercircle-maker/traffic-study](https://github.com/zizhenggaoleadercircle-maker/traffic-study)
