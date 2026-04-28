# Traffic project walkthrough

Living document: update this file when you add scripts, tables, env vars, or change how PostgreSQL / CKAN integration works.

## Git repository

Remote: [https://github.com/zizhenggaoleadercircle-maker/traffic-study](https://github.com/zizhenggaoleadercircle-maker/traffic-study)

`.env` and `.venv` are not committed; copy `.env.example` to `.env` after cloning.

## Repository layout

Top-level layout follows a standard open-source template: **source** in `src/`, **documentation** in `doc/`, **dependencies** listed under `dep/`, **tests** in `test/`, **resources** in `res/`, **samples** in `samples/`, **tools** in `tools/`, optional **config** in `.config/`, and build output in `build/` (gitignored).

| Path | Purpose |
|------|---------|
| [pyproject.toml](../pyproject.toml) | Package `traffic-study`, dependencies, console entry points |
| [dep/requirements.txt](../dep/requirements.txt) | Runtime deps (mirror of `pyproject.toml`); use with `pip install -r dep/requirements.txt` |
| [requirements.txt](../requirements.txt) | Includes `dep/requirements.txt` for one-line `pip install -r requirements.txt` |
| [src/traffic_study/](../src/traffic_study/) | Installable package: loaders, shared `parsers`, `datastore` helpers |
| [doc/walkthrough.md](walkthrough.md) | This document |
| [tests/](../tests/) | Unit tests (`python -m unittest discover -s tests -t .`; plural avoids clashing with stdlib `test`) |
| [samples/](../samples/) | Optional usage examples (empty placeholder) |
| [res/](../res/) | Static resources / assets (placeholder) |
| [tools/](../tools/) | Helper scripts not shipped as the package |
| [.config/](../.config/) | Versioned non-secret configuration notes |
| `build/` | Local build artifacts (ignored by git) |

**Module map**

| Module | Role |
|--------|------|
| [traffic_study/parsers.py](../src/traffic_study/parsers.py) | Shared CKAN/CSV value parsing (timestamps, numerics, booleans) |
| [traffic_study/datastore.py](../src/traffic_study/datastore.py) | `datastore_search` pagination |
| [traffic_study/connect.py](../src/traffic_study/connect.py) | DB smoke test |
| [traffic_study/operating_hours.py](../src/traffic_study/operating_hours.py) | CKAN vehicle operating hours sample |
| [traffic_study/summary_trip_data.py](../src/traffic_study/summary_trip_data.py) | CKAN trips sample + summary stats |
| [traffic_study/trips_yearly_zip.py](../src/traffic_study/trips_yearly_zip.py) | Yearly `trips_YYYY.zip` into `pts_trips_yearly_{year}` |
| [traffic_study/migrate_yearly_split.py](../src/traffic_study/migrate_yearly_split.py) | One-time split of legacy `pts_trips_yearly` |

## Quick setup and commands

```bash
cd /path/to/traffic
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Test database
traffic-connect

# CKAN datastore samples (Toronto Open Data)
traffic-import-operating-hours
traffic-import-operating-hours --dry-run

traffic-import-summary-trip-data
traffic-import-summary-trip-data --dry-run

# Full-year trip ZIPs (one table per year: pts_trips_yearly_2024, pts_trips_yearly_2025, ...)
traffic-import-trips-yearly-zip
traffic-import-trips-yearly-zip --dry-run

# One-time: migrate legacy unified pts_trips_yearly -> pts_trips_yearly_{year} (if upgrading)
traffic-migrate-yearly-split
```

Same entry points as `python -m traffic_study.connect`, `python -m traffic_study.operating_hours`, and so on.

## Dependencies

Declared in [pyproject.toml](../pyproject.toml) and mirrored in [dep/requirements.txt](../dep/requirements.txt):

- **psycopg[binary]** — PostgreSQL driver.
- **python-dotenv** — Load `.env` into the process environment.
- **requests** — HTTP client for CKAN API calls.

## Environment variables

### `DATABASE_URL`

- Set in **`.env`** (copy from **`.env.example`**).
- Format: `postgresql://USER:PASSWORD@HOST:PORT/DATABASE`
- Match the same host, port, database, user, and password you use in DBeaver (Main tab).
- If the password contains `@ : / # ? &` or spaces, percent-encode it in the URL.
- Local Postgres usually does not need TLS; add `?sslmode=require` only if the server requires SSL.

### `CKAN_BASE_URL` (optional)

- Default: `https://ckan0.cf.opendata.inter.prod-toronto.ca`
- When set, overrides the default Toronto CKAN API base for loaders that call `package_show` / `datastore_search` (`traffic-import-operating-hours`, `traffic-import-summary-trip-data`, and `traffic-import-trips-yearly-zip` for URL resolution).
- Same as passing `--base-url` on those CLIs.

## `traffic-connect` ([connect.py](../src/traffic_study/connect.py))

**Goal:** Verify Python can connect using `DATABASE_URL`.

1. `load_dotenv()` loads `.env`.
2. Read `DATABASE_URL`; exit with a message if missing.
3. Import `psycopg` (helpful error if dependencies are not installed).
4. `SELECT version();` and print the result.

## `traffic-import-operating-hours` ([operating_hours.py](../src/traffic_study/operating_hours.py))

**Goal:** Load Toronto Open Data CKAN package *Private Transportation Companies – Vehicle Operating Data* into PostgreSQL.

**Data source:** CKAN **datastore** resource `operating_hours_sample` (on the order of ~9k rows). Yearly ZIP releases are multi-gigabyte; they are not loaded by this script (same column layout as the sample if you add a ZIP pipeline later).

**CKAN API reference:** [https://docs.ckan.org/en/latest/api/](https://docs.ckan.org/en/latest/api/)

**Flow:**

1. `package_show` with package id `private-transportation-companies-vehicle-operating-data` to find the resource UUID where `datastore_active` is true and `name` is `operating_hours_sample`.
2. `datastore_search` with `resource_id`, `limit`, and `offset` until all rows are read.
3. `CREATE TABLE IF NOT EXISTS vehicle_operating_hours` plus indexes on `hour` and `vehid`.
4. By default, `TRUNCATE vehicle_operating_hours` then batch `INSERT` (parameterized). Use `--no-truncate` only if you avoid duplicate `ckan_id` values.

**CLI:**

| Flag | Effect |
|------|--------|
| `--base-url` | CKAN API base URL (default from env or Toronto prod URL) |
| `--batch-size` | Page size for `datastore_search` (default 5000) |
| `--no-truncate` | Skip truncate before insert (duplicates will error) |
| `--dry-run` | Fetch from CKAN only; no database writes |

**Destination table:** `vehicle_operating_hours` — primary key `ckan_id` (CKAN field `_id`).

Implementation details (parsing `hr` timestamps, `t`/`f` booleans, etc.) live in [parsers.py](../src/traffic_study/parsers.py) and script comments.

## `traffic-import-summary-trip-data` ([summary_trip_data.py](../src/traffic_study/summary_trip_data.py))

**Goal:** Load CKAN package *Private Transportation Companies – Summary and Trip Data* (`private-transportation-companies-summary-and-trip-data`).

**Data source:** Two **datastore** resources: `trips_sample` and `summary_stats` (paged with `datastore_search`).

**Flow:** `package_show` to resolve resource ids, `datastore_search` with offset paging, `CREATE TABLE IF NOT EXISTS`, default `TRUNCATE` per table, batch `INSERT`.

**CLI:** `--base-url`, `--batch-size`, `--no-truncate`, `--dry-run`, and `--resource all|trips_sample|summary_stats`.

**Destination tables:** `pts_trips_sample`, `pts_summary_stats` (primary key `ckan_id` from CKAN `_id`).

## `traffic-import-trips-yearly-zip` ([trips_yearly_zip.py](../src/traffic_study/trips_yearly_zip.py))

**Goal:** Load full-year **ZIP** releases (`trips_YYYY.zip` on `opendata.toronto.ca`) into **one table per calendar year** (no `source_year` column; the year is in the table name).

**Data source:** Resource URL from CKAN `package_show` (same package as summary/trip loader); each ZIP contains monthly `trips_YYYYMM.csv` files with the same columns as the CKAN `trips_sample` datastore (no `_id`).

**Flow:** Download ZIP to a temp file, stream each CSV, validate headers, `COPY` into `pts_trips_yearly_{year}`. For each requested year, the script `TRUNCATE`s that year’s table before loading.

**CLI:** `--years` (default `2024 2025`), `--base-url`, `--dry-run` (download and row counts only), `--keep-zip`.

**Destination tables:** `pts_trips_yearly_2024`, `pts_trips_yearly_2025`, etc. (primary key `id` / `BIGSERIAL`).

## `traffic-migrate-yearly-split` ([migrate_yearly_split.py](../src/traffic_study/migrate_yearly_split.py))

**Goal:** One-time migration if you still have a legacy unified table `pts_trips_yearly` with a `source_year` column: create `pts_trips_yearly_{year}` using the same layout as the current importer, `INSERT ... SELECT` by `source_year`, then `DROP` the old table. If `pts_trips_yearly` is missing, the script exits with no changes.

## PostgreSQL tables (summary)

| Table | Loader | Notes |
|------|--------|--------|
| `vehicle_operating_hours` | `traffic-import-operating-hours` | CKAN `_id` as `ckan_id` |
| `pts_trips_sample` | `traffic-import-summary-trip-data` | Small CKAN trips sample |
| `pts_summary_stats` | `traffic-import-summary-trip-data` | Daily summary metrics |
| `pts_trips_yearly_YYYY` | `traffic-import-trips-yearly-zip` | Full-year ZIP data; one table per year |

All live in the database named in `DATABASE_URL` (usually schema `public`).

## Troubleshooting

- **Connection refused / wrong port:** Compare DBeaver host and port with `DATABASE_URL`.
- **Password authentication failed:** Align user and password with DBeaver; encode special characters in the password portion of the URL.
- **Database does not exist:** The database name in the URL must exist on the server (e.g. `postgres`).

## Changelog

| Date | Change |
|------|--------|
| 2026-04-17 | Initial walkthrough: `connect_db.py`, `import_operating_hours.py`, `.env.example`, CKAN sample load. |
| 2026-04-17 | Pushed to GitHub `traffic-study`; merged remote `README.md`; documented repo URL here. |
| 2026-04-28 | Documented `import_summary_trip_data.py`, `import_trips_yearly_zip.py`, `migrate_pts_trips_yearly_split.py`, per-year `pts_trips_yearly_YYYY` tables, and `CKAN_BASE_URL` for all CKAN-related scripts. |
| 2026-04-28 | Restructured as `src/traffic_study` package, `pyproject.toml`, console commands (`traffic-connect`, etc.). |
| 2026-04-28 | Repository layout aligned with template: `doc/`, `dep/`, `tests/`, `res/`, `samples/`, `tools/`, `.config/`. |
