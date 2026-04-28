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

from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv

from traffic_study.parsers import parse_date, parse_int, parse_numeric, parse_timestamp

load_dotenv()

BASE_URL_DEFAULT = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
PACKAGE_ID = "private-transportation-companies-summary-and-trip-data"


def table_name_for_year(year: int) -> str:
    return f"pts_trips_yearly_{year}"


EXPECTED_COLUMNS = frozenset(
    {
        "dt",
        "pickup_hr",
        "pickup_municipality",
        "pickup_community_council",
        "pickup_ward",
        "dropoff_municipality",
        "dropoff_community_council",
        "dropoff_ward",
        "trips_total",
        "fare_avg",
        "distance_avg",
        "waittime_avg",
        "duration_avg",
    }
)


def ddl_year_table(table: str) -> str:
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
"""


def ddl_indexes(table: str) -> list[str]:
    safe = table.replace(".", "_")
    return [
        f"CREATE INDEX IF NOT EXISTS idx_{safe}_dt ON {table} (dt)",
        f"CREATE INDEX IF NOT EXISTS idx_{safe}_pickup_hr ON {table} (pickup_hr)",
    ]


COPY_COLUMN_LIST = """
    dt, pickup_hr,
    pickup_municipality, pickup_community_council, pickup_ward,
    dropoff_municipality, dropoff_community_council, dropoff_ward,
    trips_total, fare_avg, waittime_avg, distance_avg, duration_avg
""".replace(
    "\n", " "
).strip()


def copy_sql(table: str) -> str:
    return f"COPY {table} ({COPY_COLUMN_LIST}) FROM STDIN"


def zip_row_flat(rec: dict[str, Any]) -> tuple[Any, ...]:
    ph = parse_timestamp(rec.get("pickup_hr"))
    if ph is None:
        raise ValueError("missing or invalid pickup_hr")
    return (
        parse_date(rec.get("dt")),
        ph,
        rec.get("pickup_municipality"),
        rec.get("pickup_community_council"),
        rec.get("pickup_ward"),
        rec.get("dropoff_municipality"),
        rec.get("dropoff_community_council"),
        rec.get("dropoff_ward"),
        parse_int(rec.get("trips_total")),
        parse_numeric(rec.get("fare_avg")),
        parse_numeric(rec.get("waittime_avg")),
        parse_numeric(rec.get("distance_avg")),
        parse_numeric(rec.get("duration_avg")),
    )


def get_zip_download_url(base_url: str, session: Any, year: int) -> str:
    import requests

    url = f"{base_url.rstrip('/')}/api/3/action/package_show"
    r = session.get(url, params={"id": PACKAGE_ID}, timeout=120)
    r.raise_for_status()
    payload = r.json()
    if not payload.get("success"):
        raise RuntimeError(f"package_show failed: {payload}")
    want = f"trips_{year}.zip"
    for res in payload["result"]["resources"]:
        if res.get("name") == want:
            u = res.get("url")
            if not u:
                raise RuntimeError(f"No url for resource {want!r}")
            return u
    raise RuntimeError(f"Resource {want!r} not found in package {PACKAGE_ID!r}.")


def download_zip(url: str, dest: Path, session: Any) -> None:
    r = session.get(url, stream=True, timeout=600)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 512):
            if chunk:
                f.write(chunk)


def iter_csv_rows(zf: zipfile.ZipFile) -> Iterator[tuple[Any, ...]]:
    names = sorted(n for n in zf.namelist() if n.lower().endswith(".csv"))
    if not names:
        raise RuntimeError("ZIP contains no .csv files")
    for member in names:
        with zf.open(member, "r") as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
            reader = csv.DictReader(text)
            if reader.fieldnames is None:
                raise RuntimeError(f"No header row in {member!r}")
            cols = {c.strip() for c in reader.fieldnames if c}
            if cols != EXPECTED_COLUMNS:
                raise RuntimeError(
                    f"{member!r}: unexpected columns.\n"
                    f"  got:      {sorted(cols)}\n"
                    f"  expected: {sorted(EXPECTED_COLUMNS)}"
                )
            n = 0
            for rec in reader:
                yield zip_row_flat(rec)
                n += 1
            print(f"  {member}: {n:,} rows", flush=True)


def main() -> None:
    import requests

    parser = argparse.ArgumentParser(
        description="Load trips_YYYY.zip monthly CSVs into per-year tables pts_trips_yearly_{year}.",
    )
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=[2024, 2025],
        help="Calendar years to load (default: 2024 2025)",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("CKAN_BASE_URL", BASE_URL_DEFAULT),
        help="CKAN API base URL (used to resolve ZIP download URLs)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Download and count rows only; no database writes",
    )
    parser.add_argument(
        "--keep-zip",
        action="store_true",
        help="Leave downloaded ZIP on disk and print path (dry-run or debug)",
    )
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url and not args.dry_run:
        print("Missing DATABASE_URL.", file=sys.stderr)
        sys.exit(1)

    for y in args.years:
        if y < 2000 or y > 2100:
            print(f"Year out of range: {y}", file=sys.stderr)
            sys.exit(1)

    session = requests.Session()
    total_copied = 0

    if args.dry_run:
        for year in args.years:
            zip_url = get_zip_download_url(args.base_url, session, year)
            print(f"{year}: {zip_url} -> table {table_name_for_year(year)}")
            tmp: Path | None = None
            try:
                fd, tmp_str = tempfile.mkstemp(suffix=f"_{year}.zip")
                os.close(fd)
                tmp = Path(tmp_str)
                download_zip(zip_url, tmp, session)
                if args.keep_zip:
                    print(f"  saved: {tmp}")
                with zipfile.ZipFile(tmp, "r") as zf:
                    count = sum(1 for _ in iter_csv_rows(zf))
                print(f"{year}: total rows {count:,}")
                total_copied += count
            finally:
                if tmp is not None and tmp.exists() and not args.keep_zip:
                    tmp.unlink(missing_ok=True)
        print(f"Dry-run total rows across years: {total_copied:,}")
        return

    import psycopg

    with psycopg.connect(db_url) as conn:
        for year in args.years:
            tname = table_name_for_year(year)
            with conn.cursor() as cur:
                cur.execute(ddl_year_table(tname))
                for stmt in ddl_indexes(tname):
                    cur.execute(stmt)
                cur.execute(f"TRUNCATE TABLE {tname}")
            conn.commit()

        for year in args.years:
            tname = table_name_for_year(year)
            zip_url = get_zip_download_url(args.base_url, session, year)
            print(f"Loading {year} into {tname} from {zip_url}")
            tmp: Path | None = None
            try:
                fd, tmp_str = tempfile.mkstemp(suffix=f"_{year}.zip")
                os.close(fd)
                tmp = Path(tmp_str)
                download_zip(zip_url, tmp, session)
                if args.keep_zip:
                    print(f"  kept ZIP at {tmp}")
                year_rows = 0
                with zipfile.ZipFile(tmp, "r") as zf:
                    with conn.cursor() as cur:
                        with cur.copy(copy_sql(tname)) as copy:
                            for tup in iter_csv_rows(zf):
                                copy.write_row(tup)
                                year_rows += 1
                conn.commit()
                print(f"  {year}: copied {year_rows:,} rows into {tname}")
                total_copied += year_rows
            finally:
                if tmp is not None and tmp.exists() and not args.keep_zip:
                    tmp.unlink(missing_ok=True)

    print(f"Done. Total rows inserted: {total_copied:,}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
