# traffic-study

Toronto Open Data (CKAN) loaders for PostgreSQL: vehicle operating hours, summary/trip samples, and full-year trip ZIPs.

## Setup

```bash
cd traffic-study
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Copy [.env.example](.env.example) to `.env` and set `DATABASE_URL`.

## Repository layout

| Directory | Purpose |
|-----------|---------|
| [src/traffic_study/](src/traffic_study/) | Installable Python package |
| [doc/](doc/) | Documentation ([walkthrough](doc/walkthrough.md)) |
| [dep/](dep/) | Dependency listings (`requirements.txt` mirror of [pyproject.toml](pyproject.toml)) |
| [tests/](tests/) | Unit tests |
| [samples/](samples/) | Optional examples |
| [res/](res/) | Static resources / assets |
| [tools/](tools/) | Helper scripts not part of the package |
| [.config/](.config/) | Versioned configuration notes (no secrets) |
| `build/` | Local build output (gitignored) |

Root files: [pyproject.toml](pyproject.toml), [README.md](README.md), [.env.example](.env.example). Root [requirements.txt](requirements.txt) includes `dep/requirements.txt`.

## Commands (after `pip install -e .`)

| Command | Role |
|---------|------|
| `traffic-connect` | Test Postgres connection |
| `traffic-import-operating-hours` | CKAN operating hours sample |
| `traffic-import-summary-trip-data` | CKAN trips sample + summary stats |
| `traffic-import-trips-yearly-zip` | Yearly `trips_YYYY.zip` into `pts_trips_yearly_{year}` |
| `traffic-migrate-yearly-split` | One-time migration from legacy unified `pts_trips_yearly` |

Equivalent: `python -m traffic_study.connect`, `python -m traffic_study.operating_hours`, etc.

## Tests

```bash
pip install -e .
python -m unittest discover -s tests -t .
```

## Repository

[https://github.com/zizhenggaoleadercircle-maker/traffic-study](https://github.com/zizhenggaoleadercircle-maker/traffic-study)
