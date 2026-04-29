"""
Load full-year trip ZIPs from Toronto Open Data (Private Transportation Companies –
Summary and Trip Data) into PostgreSQL.

Each calendar year is stored in its own table: pts_trips_yearly_{year}
(e.g. pts_trips_yearly_2024, pts_trips_yearly_2025). There is no source_year column.

Each year is published as trips_YYYY.zip containing monthly trips_YYYYMM.csv files.
Schema matches the datastore trips_sample resource (no CKAN _id).

Flow:
  1. package_show → direct download URL for trips_{year}.zip
  2. Download ZIP to a temp file, stream each CSV inside
  3. COPY rows into pts_trips_yearly_{year} (truncates those tables for requested years)

If you previously used the unified table pts_trips_yearly, run once:
  traffic-migrate-yearly-split

CKAN API: https://docs.ckan.org/en/latest/api/
"""

from __future__ import annotations  # Postpone annotation evaluation so forward refs work without quotes

import argparse  # CLI argument parsing for years, URLs, dry-run, etc.
import csv  # Parse CSV rows inside the ZIP archives
import io  # Text wrapper over zip member bytes for DictReader
import os  # Env vars (DATABASE_URL, CKAN_BASE_URL) and temp file fd cleanup
import sys  # stderr messages and exit codes
import tempfile  # Secure temp path for downloaded ZIP files
import zipfile  # Open trips_YYYY.zip and iterate monthly CSV members
from pathlib import Path  # Type-safe filesystem paths for temp ZIP locations
from typing import Any, Iterator  # Row dict typing and CSV row iterator

from dotenv import load_dotenv  # Load .env so DATABASE_URL / CKAN_BASE_URL are available

from traffic_study.parsers import parse_date, parse_int, parse_numeric, parse_timestamp  # Normalize CSV cell types

load_dotenv()  # Populate os.environ from .env if present

BASE_URL_DEFAULT = "https://ckan0.cf.opendata.inter.prod-toronto.ca"  # Toronto CKAN when env not set
PACKAGE_ID = "private-transportation-companies-summary-and-trip-data"  # CKAN dataset id for package_show


def table_name_for_year(year: int) -> str:  # Build PostgreSQL table name for a calendar year
    return f"pts_trips_yearly_{year}"  # Convention: one physical table per year


EXPECTED_COLUMNS = frozenset(  # Set of CSV header names we require (order-independent)
    {
        "dt",  # Trip date column
        "pickup_hr",  # Pickup timestamp
        "pickup_municipality",  # Origin municipality label
        "pickup_community_council",  # Origin community council
        "pickup_ward",  # Origin ward
        "dropoff_municipality",  # Destination municipality
        "dropoff_community_council",  # Destination community council
        "dropoff_ward",  # Destination ward
        "trips_total",  # Trip count aggregate
        "fare_avg",  # Average fare
        "distance_avg",  # Average distance
        "waittime_avg",  # Average wait time
        "duration_avg",  # Average trip duration
    }
)


def ddl_year_table(table: str) -> str:  # SQL to create the per-year table if missing
    return f"""
CREATE TABLE IF NOT EXISTS {table} (
    id BIGSERIAL PRIMARY KEY,
    dt DATE,
    pickup_hr TIMESTAMPTZ NOT NULL,
    pickup_municipality TEXT,
    pickup_community_council TEXT,
    pickup_ward TEXT,
    dropoff_municipality TEXT,
    dropoff_community_council TEXT,
    dropoff_ward TEXT,
    trips_total INTEGER,
    fare_avg NUMERIC(16, 4),
    waittime_avg NUMERIC(16, 4),
    distance_avg NUMERIC(16, 4),
    duration_avg NUMERIC(16, 4),
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""  # loaded_at set at insert time; waittime/duration column order matches COPY list below


def ddl_indexes(table: str) -> list[str]:  # Indexes for typical date/time filters
    safe = table.replace(".", "_")  # Sanitize table name for index identifier (no dots)
    return [  # One index on calendar date, one on pickup hour timestamp
        f"CREATE INDEX IF NOT EXISTS idx_{safe}_dt ON {table} (dt)",
        f"CREATE INDEX IF NOT EXISTS idx_{safe}_pickup_hr ON {table} (pickup_hr)",
    ]


COPY_COLUMN_LIST = """
    dt, pickup_hr,
    pickup_municipality, pickup_community_council, pickup_ward,
    dropoff_municipality, dropoff_community_council, dropoff_ward,
    trips_total, fare_avg, waittime_avg, distance_avg, duration_avg
""".replace(
    "\n", " "  # Flatten to single line for COPY (...) clause
).strip()  # Trim leading/trailing whitespace from the column list string


def copy_sql(table: str) -> str:  # COPY statement matching COPY_COLUMN_LIST order
    return f"COPY {table} ({COPY_COLUMN_LIST}) FROM STDIN"  # psycopg copy manager streams rows to STDIN


def zip_row_flat(rec: dict[str, Any]) -> tuple[Any, ...]:  # Map one CSV dict row to DB tuple for COPY
    ph = parse_timestamp(rec.get("pickup_hr"))  # Parse required pickup timestamp
    if ph is None:  # Reject rows we cannot place in time
        raise ValueError("missing or invalid pickup_hr")
    return (  # Order must match COPY_COLUMN_LIST
        parse_date(rec.get("dt")),  # Calendar date
        ph,  # Pickup timestamptz
        rec.get("pickup_municipality"),  # Pass through text fields
        rec.get("pickup_community_council"),
        rec.get("pickup_ward"),
        rec.get("dropoff_municipality"),
        rec.get("dropoff_community_council"),
        rec.get("dropoff_ward"),
        parse_int(rec.get("trips_total")),  # Integer metric
        parse_numeric(rec.get("fare_avg")),  # Numeric metrics with shared parser
        parse_numeric(rec.get("waittime_avg")),
        parse_numeric(rec.get("distance_avg")),
        parse_numeric(rec.get("duration_avg")),
    )


def get_zip_download_url(base_url: str, session: Any, year: int) -> str:  # Resolve direct ZIP URL from CKAN API
    import requests  # Local import: only needed when this function runs

    url = f"{base_url.rstrip('/')}/api/3/action/package_show"  # CKAN action URL for dataset metadata
    r = session.get(url, params={"id": PACKAGE_ID}, timeout=120)  # Fetch package JSON by id
    r.raise_for_status()  # Convert HTTP errors to exceptions
    payload = r.json()  # Parse JSON body
    if not payload.get("success"):  # CKAN wraps result and success flag
        raise RuntimeError(f"package_show failed: {payload}")
    want = f"trips_{year}.zip"  # Published resource name for that year’s archive
    for res in payload["result"]["resources"]:  # Scan attached files / datastore links
        if res.get("name") == want:  # Match exact resource name
            u = res.get("url")  # Direct download URL for the ZIP
            if not u:  # Guard missing link
                raise RuntimeError(f"No url for resource {want!r}")
            return u  # First matching resource wins
    raise RuntimeError(f"Resource {want!r} not found in package {PACKAGE_ID!r}.")  # Year not published


def download_zip(url: str, dest: Path, session: Any) -> None:  # Stream HTTP body to disk without loading whole file
    r = session.get(url, stream=True, timeout=600)  # Long timeout for large archives
    r.raise_for_status()  # Fail fast on 4xx/5xx
    with open(dest, "wb") as f:  # Binary write to temp path
        for chunk in r.iter_content(chunk_size=1024 * 512):  # Half-megabyte chunks
            if chunk:  # Skip keep-alive empty chunks
                f.write(chunk)  # Append to file


def iter_csv_rows(zf: zipfile.ZipFile) -> Iterator[tuple[Any, ...]]:  # Yield typed tuples for every CSV row in ZIP
    names = sorted(n for n in zf.namelist() if n.lower().endswith(".csv"))  # Sorted monthly files inside archive
    if not names:  # Empty ZIP is invalid for this loader
        raise RuntimeError("ZIP contains no .csv files")
    for member in names:  # Process each CSV in deterministic order
        with zf.open(member, "r") as raw:  # Raw bytes from zip member
            text = io.TextIOWrapper(raw, encoding="utf-8", newline="")  # Decode as UTF-8 for csv module
            reader = csv.DictReader(text)  # Header-driven dict rows
            if reader.fieldnames is None:  # Missing header row
                raise RuntimeError(f"No header row in {member!r}")
            cols = {c.strip() for c in reader.fieldnames if c}  # Normalize header names, ignore empty
            if cols != EXPECTED_COLUMNS:  # Schema drift vs sample resource
                raise RuntimeError(
                    f"{member!r}: unexpected columns.\n"
                    f"  got:      {sorted(cols)}\n"
                    f"  expected: {sorted(EXPECTED_COLUMNS)}"
                )
            n = 0  # Row counter for logging per file
            for rec in reader:  # Iterate data rows
                yield zip_row_flat(rec)  # Emit tuple for COPY
                n += 1  # Increment after yield so count includes yielded rows
            print(f"  {member}: {n:,} rows", flush=True)  # Progress line after finishing member


def main() -> None:  # CLI entry: download ZIPs, optionally load into Postgres
    import requests  # HTTP client for CKAN and file download

    parser = argparse.ArgumentParser(  # Describe script purpose in --help
        description="Load trips_YYYY.zip monthly CSVs into per-year tables pts_trips_yearly_{year}.",
    )
    parser.add_argument(
        "--years",
        type=int,  # Each positional year argument parsed as int
        nargs="+",  # One or more years required when flag is used
        default=[2024, 2025],  # Default load targets if --years omitted
        help="Calendar years to load (default: 2024 2025)",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("CKAN_BASE_URL", BASE_URL_DEFAULT),  # Env overrides embedded default
        help="CKAN API base URL (used to resolve ZIP download URLs)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",  # Sets args.dry_run True when flag present
        help="Download and count rows only; no database writes",
    )
    parser.add_argument(
        "--keep-zip",
        action="store_true",  # Retain temp ZIP path for inspection
        help="Leave downloaded ZIP on disk and print path (dry-run or debug)",
    )
    args = parser.parse_args()  # Populate namespace from argv

    db_url = os.environ.get("DATABASE_URL")  # Postgres connection string from env
    if not db_url and not args.dry_run:  # Real load requires database
        print("Missing DATABASE_URL.", file=sys.stderr)
        sys.exit(1)

    for y in args.years:  # Validate every requested year
        if y < 2000 or y > 2100:  # Reject obvious mistakes
            print(f"Year out of range: {y}", file=sys.stderr)
            sys.exit(1)

    session = requests.Session()  # Reuse connections across downloads
    total_copied = 0  # Accumulate row counts across years (dry-run or insert)

    if args.dry_run:  # Count-only path
        for year in args.years:  # Each year independently
            zip_url = get_zip_download_url(args.base_url, session, year)  # Lookup CKAN resource URL
            print(f"{year}: {zip_url} -> table {table_name_for_year(year)}")  # Show target mapping
            tmp: Path | None = None  # Temp file path holder for cleanup
            try:  # Ensure temp file removed unless --keep-zip
                fd, tmp_str = tempfile.mkstemp(suffix=f"_{year}.zip")  # Create empty temp file, get path
                os.close(fd)  # We only need the path; open again in download_zip
                tmp = Path(tmp_str)  # pathlib for consistent API
                download_zip(zip_url, tmp, session)  # Fill temp file from HTTP
                if args.keep_zip:  # User wants path preserved
                    print(f"  saved: {tmp}")
                with zipfile.ZipFile(tmp, "r") as zf:  # Open archive read-only
                    count = sum(1 for _ in iter_csv_rows(zf))  # Exhaust iterator and count tuples
                print(f"{year}: total rows {count:,}")  # Per-year total
                total_copied += count  # Add to running sum
            finally:  # Always run cleanup
                if tmp is not None and tmp.exists() and not args.keep_zip:  # Delete unless user kept file
                    tmp.unlink(missing_ok=True)  # Remove temp ZIP
        print(f"Dry-run total rows across years: {total_copied:,}")  # Final aggregate
        return  # Skip database branch

    import psycopg  # Deferred import: only needed for non-dry-run

    with psycopg.connect(db_url) as conn:  # Context-managed connection
        for year in args.years:  # Prepare each target table before any COPY
            tname = table_name_for_year(year)  # Table for this year
            with conn.cursor() as cur:  # One transaction block per year setup
                cur.execute(ddl_year_table(tname))  # Ensure table exists
                for stmt in ddl_indexes(tname):  # Create indexes if missing
                    cur.execute(stmt)
                cur.execute(f"TRUNCATE TABLE {tname}")  # Full reload: empty before COPY
            conn.commit()  # Commit DDL + truncate before loading data

        for year in args.years:  # Load loop: one ZIP per year after all truncates
            tname = table_name_for_year(year)  # Destination table name
            zip_url = get_zip_download_url(args.base_url, session, year)  # Resolve download link
            print(f"Loading {year} into {tname} from {zip_url}")  # User-visible progress
            tmp: Path | None = None  # Temp ZIP path
            try:
                fd, tmp_str = tempfile.mkstemp(suffix=f"_{year}.zip")  # Create temp file for ZIP bytes
                os.close(fd)  # Close fd from mkstemp; download opens by path
                tmp = Path(tmp_str)  # Use pathlib
                download_zip(zip_url, tmp, session)  # Stream download
                if args.keep_zip:  # Optional retention for debugging
                    print(f"  kept ZIP at {tmp}")
                year_rows = 0  # Rows copied for this year only
                with zipfile.ZipFile(tmp, "r") as zf:  # Read monthly CSVs
                    with conn.cursor() as cur:  # Cursor hosts COPY
                        with cur.copy(copy_sql(tname)) as copy:  # Binary COPY protocol
                            for tup in iter_csv_rows(zf):  # Stream rows from all CSV members
                                copy.write_row(tup)  # Send one tuple
                                year_rows += 1  # Count successful writes
                conn.commit()  # Commit this year’s bulk load
                print(f"  {year}: copied {year_rows:,} rows into {tname}")  # Per-year summary
                total_copied += year_rows  # Add to global total
            finally:
                if tmp is not None and tmp.exists() and not args.keep_zip:  # Cleanup temp file
                    tmp.unlink(missing_ok=True)

    print(f"Done. Total rows inserted: {total_copied:,}")  # Final line after all years


if __name__ == "__main__":  # Script executed directly
    try:
        main()  # Run CLI
    except Exception as e:  # Print error without traceback for cleaner CLI output
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
