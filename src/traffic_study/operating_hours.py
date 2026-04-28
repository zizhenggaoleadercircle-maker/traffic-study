"""
Load Toronto Open Data CKAN package "Private Transportation Companies – Vehicle Operating Data"
into PostgreSQL.

Uses the datastore-backed resource operating_hours_sample (~9k rows). Full yearly releases
are multi-GB ZIPs; load those separately if needed (same column layout as the sample).

CKAN API: https://docs.ckan.org/en/latest/api/

High-level steps:
  1. Call package_show to find the resource id for "operating_hours_sample" (datastore).
  2. Page through datastore_search until all rows are retrieved.
  3. CREATE TABLE + indexes if missing; TRUNCATE (unless --no-truncate); INSERT batches.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, List

from dotenv import load_dotenv

from traffic_study.datastore import iter_datastore_batches
from traffic_study.parsers import parse_bool_tf, parse_int, parse_numeric, parse_timestamp

load_dotenv()

BASE_URL_DEFAULT = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
PACKAGE_ID = "private-transportation-companies-vehicle-operating-data"
TABLE_NAME = "vehicle_operating_hours"


def row_tuple(rec: dict[str, Any]) -> tuple[Any, ...]:
    return (
        rec["_id"],
        rec["vehid"],
        parse_timestamp(rec["hr"]),
        parse_int(rec["reported_trips_started"]),
        parse_numeric(rec["reported_trip_fractions"]),
        parse_int(rec["pooled_trips_started"]),
        parse_numeric(rec["pooled_trip_fractions"]),
        parse_int(rec["routed_trips_started"]),
        parse_int(rec["driver_cancelled_trips"]),
        parse_int(rec["passenger_cancelled_trips"]),
        parse_bool_tf(rec["toronto_boundary_crossed"]),
        parse_numeric(rec["fares"]),
        parse_numeric(rec["time_available"]),
        parse_numeric(rec["time_enroute"]),
        parse_numeric(rec["time_waiting"]),
        parse_numeric(rec["time_ontrip"]),
        parse_numeric(rec["dist_available_routed"]),
        parse_numeric(rec["dist_enroute_routed"]),
        parse_numeric(rec["dist_ontrip_routed"]),
        parse_numeric(rec["dist_ontrip_reported"]),
    )


def get_datastore_resource_id(base_url: str, session: Any) -> str:
    url = f"{base_url.rstrip('/')}/api/3/action/package_show"
    r = session.get(url, params={"id": PACKAGE_ID}, timeout=120)
    r.raise_for_status()
    payload = r.json()
    if not payload.get("success"):
        raise RuntimeError(f"package_show failed: {payload}")
    for res in payload["result"]["resources"]:
        if res.get("datastore_active") and res.get("name") == "operating_hours_sample":
            return res["id"]
    raise RuntimeError("No datastore resource operating_hours_sample found in package.")


DDL_TABLE = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    ckan_id INTEGER PRIMARY KEY,
    vehid TEXT NOT NULL,
    hour TIMESTAMPTZ NOT NULL,
    reported_trips_started INTEGER,
    reported_trip_fractions NUMERIC(14, 4),
    pooled_trips_started INTEGER,
    pooled_trip_fractions NUMERIC(14, 4),
    routed_trips_started INTEGER,
    driver_cancelled_trips INTEGER,
    passenger_cancelled_trips INTEGER,
    toronto_boundary_crossed BOOLEAN,
    fares NUMERIC(16, 4),
    time_available NUMERIC(14, 4),
    time_enroute NUMERIC(14, 4),
    time_waiting NUMERIC(14, 4),
    time_ontrip NUMERIC(14, 4),
    dist_available_routed NUMERIC(14, 4),
    dist_enroute_routed NUMERIC(14, 4),
    dist_ontrip_routed NUMERIC(14, 4),
    dist_ontrip_reported NUMERIC(14, 4),
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

DDL_INDEX_HOUR = f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_hour ON {TABLE_NAME} (hour)"
DDL_INDEX_VEHID = f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_vehid ON {TABLE_NAME} (vehid)"

INSERT_SQL = f"""
INSERT INTO {TABLE_NAME} (
    ckan_id, vehid, hour,
    reported_trips_started, reported_trip_fractions,
    pooled_trips_started, pooled_trip_fractions,
    routed_trips_started, driver_cancelled_trips, passenger_cancelled_trips,
    toronto_boundary_crossed,
    fares, time_available, time_enroute, time_waiting, time_ontrip,
    dist_available_routed, dist_enroute_routed, dist_ontrip_routed, dist_ontrip_reported
) VALUES (
    %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s,
    %s, %s, %s, %s
)
"""


def main() -> None:
    import requests

    parser = argparse.ArgumentParser(description="Load CKAN operating hours sample into PostgreSQL.")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("CKAN_BASE_URL", BASE_URL_DEFAULT),
        help="CKAN API base URL",
    )
    parser.add_argument("--batch-size", type=int, default=5000, help="datastore_search page size")
    parser.add_argument(
        "--no-truncate",
        action="store_true",
        help="Do not truncate table before load (will fail on duplicate ckan_id)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch from API only; do not write to the database",
    )
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url and not args.dry_run:
        print("Missing DATABASE_URL.", file=sys.stderr)
        sys.exit(1)

    import psycopg

    session = requests.Session()
    resource_id = get_datastore_resource_id(args.base_url, session)
    print(f"Datastore resource id: {resource_id}")

    if args.dry_run:
        first: List[dict[str, Any]] | None = None
        total = 0
        for batch in iter_datastore_batches(args.base_url, resource_id, session, args.batch_size):
            if first is None and batch:
                first = batch
            total += len(batch)
        print(f"Would load {total} records from CKAN.")
        if first:
            print("Sample keys:", sorted(first[0].keys()))
        return

    inserted = 0
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(DDL_TABLE)
            cur.execute(DDL_INDEX_HOUR)
            cur.execute(DDL_INDEX_VEHID)
        if not args.no_truncate:
            with conn.cursor() as cur:
                cur.execute(f"TRUNCATE TABLE {TABLE_NAME}")
        for batch in iter_datastore_batches(args.base_url, resource_id, session, args.batch_size):
            with conn.cursor() as cur:
                cur.executemany(INSERT_SQL, [row_tuple(rec) for rec in batch])
                inserted += len(batch)
        conn.commit()
    print(f"Inserted {inserted} rows into {TABLE_NAME}.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
