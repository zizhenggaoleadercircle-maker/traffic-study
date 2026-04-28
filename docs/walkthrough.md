# Traffic project walkthrough

Living document: update this file when you add scripts, tables, env vars, or change how PostgreSQL / CKAN integration works.

## Git repository

Remote: [https://github.com/zizhenggaoleadercircle-maker/traffic-study](https://github.com/zizhenggaoleadercircle-maker/traffic-study)

`.env` and `.venv` are not committed; copy `.env.example` to `.env` after cloning.

## Quick commands

```bash
cd /path/to/traffic
source .venv/bin/activate
pip install -r requirements.txt

python connect_db.py

# CKAN datastore samples (Toronto Open Data)
python import_operating_hours.py
python import_operating_hours.py --dry-run

python import_summary_trip_data.py
python import_summary_trip_data.py --dry-run

# Full-year trip ZIPs (one table per year: pts_trips_yearly_2024, pts_trips_yearly_2025, ...)
python import_trips_yearly_zip.py
python import_trips_yearly_zip.py --dry-run

# One-time: migrate legacy unified pts_trips_yearly -> pts_trips_yearly_{year} (if upgrading)
python migrate_pts_trips_yearly_split.py
```

## Project layout

| Path | Purpose |
|------|---------|
| [requirements.txt](../requirements.txt) | Python dependencies |
| [.env.example](../.env.example) | Template for `DATABASE_URL` (safe to commit) |
| [.env](../.env) | Real secrets; gitignored |
| [.gitignore](../.gitignore) | Ignores `.env`, `.venv`, `__pycache__` |
| [connect_db.py](../connect_db.py) | Smoke test: PostgreSQL connectivity |
| [import_operating_hours.py](../import_operating_hours.py) | CKAN datastore: vehicle operating hours sample to `vehicle_operating_hours` |
| [import_summary_trip_data.py](../import_summary_trip_data.py) | CKAN datastore: trips sample + summary stats to `pts_trips_sample`, `pts_summary_stats` |
| [import_trips_yearly_zip.py](../import_trips_yearly_zip.py) | Download yearly `trips_YYYY.zip`, load into `pts_trips_yearly_{year}` |
| [migrate_pts_trips_yearly_split.py](../migrate_pts_trips_yearly_split.py) | One-time: split old `pts_trips_yearly` (with `source_year`) into per-year tables, drop legacy table |
| [docs/walkthrough.md](walkthrough.md) | This document |

## Dependencies ([requirements.txt](../requirements.txt))

- **psycopg[binary]** — PostgreSQL driver.
- **python-dotenv** — Load `.env` into the process environment.
- **requests** — HTTP client for CKAN API calls.

## Virtual environment

Create once per machine:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment variables

### `DATABASE_URL`

- Set in **`.env`** (copy from **`.env.example`**).
- Format: `postgresql://USER:PASSWORD@HOST:PORT/DATABASE`
- Match the same host, port, database, user, and password you use in DBeaver (Main tab).
- If the password contains `@ : / # ? &` or spaces, percent-encode it in the URL.
- Local Postgres usually does not need TLS; add `?sslmode=require` only if the server requires SSL.

### `CKAN_BASE_URL` (optional)

- Default: `https://ckan0.cf.opendata.inter.prod-toronto.ca`
- When set, overrides the default Toronto CKAN API base for scripts that call `package_show` / `datastore_search` (`import_operating_hours.py`, `import_summary_trip_data.py`, and `import_trips_yearly_zip.py` for URL resolution).
- Same as passing `--base-url` on those CLIs.

## [connect_db.py](../connect_db.py)

**Goal:** Verify Python can connect using `DATABASE_URL`.

1. `load_dotenv()` loads `.env`.
2. Read `DATABASE_URL`; exit with a message if missing.
3. Import `psycopg` (helpful error if dependencies are not installed).
4. `SELECT version();` and print the result.

## [import_operating_hours.py](../import_operating_hours.py)

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

Implementation details (parsing `hr` timestamps, `t`/`f` booleans, etc.) are documented in comments inside the script.

## [import_summary_trip_data.py](../import_summary_trip_data.py)

**Goal:** Load CKAN package *Private Transportation Companies – Summary and Trip Data* (`private-transportation-companies-summary-and-trip-data`).

**Data source:** Two **datastore** resources: `trips_sample` and `summary_stats` (paged with `datastore_search`).

**Flow:** `package_show` to resolve resource ids, `datastore_search` with offset paging, `CREATE TABLE IF NOT EXISTS`, default `TRUNCATE` per table, batch `INSERT`.

**CLI:** `--base-url`, `--batch-size`, `--no-truncate`, `--dry-run`, and `--resource all|trips_sample|summary_stats`.

**Destination tables:** `pts_trips_sample`, `pts_summary_stats` (primary key `ckan_id` from CKAN `_id`).

## [import_trips_yearly_zip.py](../import_trips_yearly_zip.py)

**Goal:** Load full-year **ZIP** releases (`trips_YYYY.zip` on `opendata.toronto.ca`) into **one table per calendar year** (no `source_year` column; the year is in the table name).

**Data source:** Resource URL from CKAN `package_show` (same package as `import_summary_trip_data.py`); each ZIP contains monthly `trips_YYYYMM.csv` files with the same columns as the CKAN `trips_sample` datastore (no `_id`).

**Flow:** Download ZIP to a temp file, stream each CSV, validate headers, `COPY` into `pts_trips_yearly_{year}`. For each requested year, the script `TRUNCATE`s that year’s table before loading.

**CLI:** `--years` (default `2024 2025`), `--base-url`, `--dry-run` (download and row counts only), `--keep-zip`.

**Destination tables:** `pts_trips_yearly_2024`, `pts_trips_yearly_2025`, etc. (primary key `id` / `BIGSERIAL`).

## [migrate_pts_trips_yearly_split.py](../migrate_pts_trips_yearly_split.py)

**Goal:** One-time migration if you still have a legacy unified table `pts_trips_yearly` with a `source_year` column: create `pts_trips_yearly_{year}` using the same layout as the current importer, `INSERT ... SELECT` by `source_year`, then `DROP` the old table. If `pts_trips_yearly` is missing, the script exits with no changes.

## PostgreSQL tables (summary)

| Table | Loader | Notes |
|------|--------|--------|
| `vehicle_operating_hours` | `import_operating_hours.py` | CKAN `_id` as `ckan_id` |
| `pts_trips_sample` | `import_summary_trip_data.py` | Small CKAN trips sample |
| `pts_summary_stats` | `import_summary_trip_data.py` | Daily summary metrics |
| `pts_trips_yearly_YYYY` | `import_trips_yearly_zip.py` | Full-year ZIP data; one table per year |

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
