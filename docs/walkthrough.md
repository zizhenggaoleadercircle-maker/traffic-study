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
python import_operating_hours.py
python import_operating_hours.py --dry-run
```

## Project layout

| Path | Purpose |
|------|---------|
| [requirements.txt](../requirements.txt) | Python dependencies |
| [.env.example](../.env.example) | Template for `DATABASE_URL` (safe to commit) |
| [.env](../.env) | Real secrets; gitignored |
| [.gitignore](../.gitignore) | Ignores `.env`, `.venv`, `__pycache__` |
| [connect_db.py](../connect_db.py) | Smoke test: PostgreSQL connectivity |
| [import_operating_hours.py](../import_operating_hours.py) | CKAN datastore sample to `vehicle_operating_hours` |
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

- Overrides the default Toronto CKAN API base URL in `import_operating_hours.py` when set.
- Same effect as `python import_operating_hours.py --base-url ...`.

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

## Troubleshooting

- **Connection refused / wrong port:** Compare DBeaver host and port with `DATABASE_URL`.
- **Password authentication failed:** Align user and password with DBeaver; encode special characters in the password portion of the URL.
- **Database does not exist:** The database name in the URL must exist on the server (e.g. `postgres`).

## Changelog

| Date | Change |
|------|--------|
| 2026-04-17 | Initial walkthrough: `connect_db.py`, `import_operating_hours.py`, `.env.example`, CKAN sample load. |
| 2026-04-17 | Pushed to GitHub `traffic-study`; merged remote `README.md`; documented repo URL here. |
