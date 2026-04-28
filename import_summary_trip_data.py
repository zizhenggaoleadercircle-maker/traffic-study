#!/usr/bin/env python3
"""
Load Toronto Open Data CKAN package "Private Transportation Companies - Summary and Trip Data"
into PostgreSQL.

Datastore resources (paged via datastore_search):
  - trips_sample (~8k rows): trip aggregates by pickup hour / area.
  - summary_stats (~3k rows): daily fleet / trip summary metrics.

ZIPs and static files in the package are not loaded here; use datastore resources or download URLs.

CKAN API: https://docs.ckan.org/en/latest/api/
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterator, List

from dotenv import load_dotenv

load_dotenv()

BASE_URL_DEFAULT = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
PACKAGE_ID = "private-transportation-companies-summary-and-trip-data"

TABLE_TRIPS = "pts_trips_sample"
TABLE_SUMMARY = "pts_summary_stats"


def parse_timestamp(val: Any) -> datetime | None:
    if val is None or val == "":
        return None
    s = str(val).strip()
    m = re.match(r"^(.+?)([+-]\d{2})$", s)
    if m and not re.search(r"[+-]\d{2}:\d{2}$", s):
        s = m.group(1) + m.group(2) + ":00"
    return datetime.fromisoformat(s)


def parse_date(val: Any) -> date | None:
    if val is None or val == "":
        return None
    s = str(val).strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return date.fromisoformat(s[:10])
    d = datetime.fromisoformat(s)
    return d.date()


def parse_int(val: Any) -> int | None:
    if val is None or val == "":
        return None
    return int(str(val).strip())


def parse_numeric(val: Any) -> Decimal | None:
    if val is None or val == "":
        return None
    try:
        return Decimal(str(val).strip())
    except InvalidOperation:
        return None


def row_trips(rec: dict[str, Any]) -> tuple[Any, ...]:
    return (
        rec["_id"],
        parse_date(rec["dt"]),
        parse_timestamp(rec["pickup_hr"]),
        rec.get("pickup_municipality"),
        rec.get("pickup_community_council"),
        rec.get("pickup_ward"),
        rec.get("dropoff_municipality"),
        rec.get("dropoff_community_council"),
        rec.get("dropoff_ward"),
        parse_int(rec["trips_total"]),
        parse_numeric(rec["fare_avg"]),
        parse_numeric(rec["waittime_avg"]),
        parse_numeric(rec["distance_avg"]),
        parse_numeric(rec["duration_avg"]),
    )


def row_summary(rec: dict[str, Any]) -> tuple[Any, ...]:
    return (
        rec["_id"],
        parse_date(rec["dt"]),
        parse_int(rec["reported_trips_started"]),
        parse_int(rec["trips_started_wav"]),
        parse_int(rec["trips_started_nonwav"]),
        parse_int(rec["trips_started_pooled"]),
        parse_int(rec["trips_cancelled_driver_wav"]),
        parse_int(rec["trips_cancelled_driver_nonwav"]),
        parse_int(rec["trips_cancelled_passenger_wav"]),
        parse_int(rec["trips_cancelled_passenger_nonwav"]),
        parse_numeric(rec["dist_avg"]),
        parse_numeric(rec["fare_avg"]),
        parse_numeric(rec["waittime_wav_avg"]),
        parse_numeric(rec["waittime_nonwav_avg"]),
        parse_int(rec["active_vehicles"]),
        parse_numeric(rec["time_available"]),
        parse_numeric(rec["time_enroute"]),
        parse_numeric(rec["time_waiting"]),
        parse_numeric(rec["time_ontrip"]),
        parse_numeric(rec["dist_available_routed"]),
        parse_numeric(rec["dist_enroute_routed"]),
        parse_numeric(rec["dist_ontrip_routed"]),
        parse_numeric(rec["dist_ontrip_reported"]),
        parse_numeric(rec["percent_time_available"]),
        parse_numeric(rec["percent_time_enroute"]),
        parse_numeric(rec["percent_time_waiting"]),
        parse_numeric(rec["percent_time_ontrip"]),
        parse_numeric(rec["percent_dist_available_routed"]),
        parse_numeric(rec["percent_dist_enroute_routed"]),
        parse_numeric(rec["percent_dist_ontrip_routed"]),
    )


def get_datastore_resource_ids(base_url: str, session: Any) -> dict[str, str]:
    url = f"{base_url.rstrip('/')}/api/3/action/package_show"
    r = session.get(url, params={"id": PACKAGE_ID}, timeout=120)
    r.raise_for_status()
    payload = r.json()
    if not payload.get("success"):
        raise RuntimeError(f"package_show failed: {payload}")
    out: dict[str, str] = {}
    for res in payload["result"]["resources"]:
        if res.get("datastore_active") and res.get("name") in ("trips_sample", "summary_stats"):
            out[res["name"]] = res["id"]
    for name in ("trips_sample", "summary_stats"):
        if name not in out:
            raise RuntimeError(f"Datastore resource {name!r} not found in package.")
    return out


def iter_datastore_batches(
    base_url: str,
    resource_id: str,
    session: Any,
    batch_size: int,
) -> Iterator[List[dict[str, Any]]]:
    offset = 0
    while True:
        r = session.get(
            f"{base_url.rstrip('/')}/api/3/action/datastore_search",
            params={
                "resource_id": resource_id,
                "limit": batch_size,
                "offset": offset,
            },
            timeout=120,
        )
        r.raise_for_status()
        payload = r.json()
        if not payload.get("success"):
            raise RuntimeError(f"datastore_search failed: {payload}")
        records: List[dict[str, Any]] = payload["result"]["records"]
        if not records:
            break
        yield records
        offset += len(records)
        if len(records) < batch_size:
            break


DDL_TRIPS = f"""
CREATE TABLE IF NOT EXISTS {TABLE_TRIPS} (
    ckan_id INTEGER PRIMARY KEY,
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

DDL_SUMMARY = f"""
CREATE TABLE IF NOT EXISTS {TABLE_SUMMARY} (
    ckan_id INTEGER PRIMARY KEY,
    dt DATE,
    reported_trips_started INTEGER,
    trips_started_wav INTEGER,
    trips_started_nonwav INTEGER,
    trips_started_pooled INTEGER,
    trips_cancelled_driver_wav INTEGER,
    trips_cancelled_driver_nonwav INTEGER,
    trips_cancelled_passenger_wav INTEGER,
    trips_cancelled_passenger_nonwav INTEGER,
    dist_avg NUMERIC(16, 4),
    fare_avg NUMERIC(16, 4),
    waittime_wav_avg NUMERIC(16, 4),
    waittime_nonwav_avg NUMERIC(16, 4),
    active_vehicles INTEGER,
    time_available NUMERIC(16, 4),
    time_enroute NUMERIC(16, 4),
    time_waiting NUMERIC(16, 4),
    time_ontrip NUMERIC(16, 4),
    dist_available_routed NUMERIC(16, 4),
    dist_enroute_routed NUMERIC(16, 4),
    dist_ontrip_routed NUMERIC(16, 4),
    dist_ontrip_reported NUMERIC(16, 4),
    percent_time_available NUMERIC(16, 4),
    percent_time_enroute NUMERIC(16, 4),
    percent_time_waiting NUMERIC(16, 4),
    percent_time_ontrip NUMERIC(16, 4),
    percent_dist_available_routed NUMERIC(16, 4),
    percent_dist_enroute_routed NUMERIC(16, 4),
    percent_dist_ontrip_routed NUMERIC(16, 4),
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

IDX_TRIPS_PICKUP = f"CREATE INDEX IF NOT EXISTS idx_{TABLE_TRIPS}_pickup_hr ON {TABLE_TRIPS} (pickup_hr)"
IDX_TRIPS_DT = f"CREATE INDEX IF NOT EXISTS idx_{TABLE_TRIPS}_dt ON {TABLE_TRIPS} (dt)"
IDX_SUMMARY_DT = f"CREATE INDEX IF NOT EXISTS idx_{TABLE_SUMMARY}_dt ON {TABLE_SUMMARY} (dt)"

INSERT_TRIPS = f"""
INSERT INTO {TABLE_TRIPS} (
    ckan_id, dt, pickup_hr,
    pickup_municipality, pickup_community_council, pickup_ward,
    dropoff_municipality, dropoff_community_council, dropoff_ward,
    trips_total, fare_avg, waittime_avg, distance_avg, duration_avg
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
)
"""

INSERT_SUMMARY = f"""
INSERT INTO {TABLE_SUMMARY} (
    ckan_id, dt,
    reported_trips_started, trips_started_wav, trips_started_nonwav, trips_started_pooled,
    trips_cancelled_driver_wav, trips_cancelled_driver_nonwav,
    trips_cancelled_passenger_wav, trips_cancelled_passenger_nonwav,
    dist_avg, fare_avg, waittime_wav_avg, waittime_nonwav_avg, active_vehicles,
    time_available, time_enroute, time_waiting, time_ontrip,
    dist_available_routed, dist_enroute_routed, dist_ontrip_routed, dist_ontrip_reported,
    percent_time_available, percent_time_enroute, percent_time_waiting, percent_time_ontrip,
    percent_dist_available_routed, percent_dist_enroute_routed, percent_dist_ontrip_routed
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
)
"""


def main() -> None:
    import requests

    parser = argparse.ArgumentParser(
        description="Load Summary and Trip Data CKAN datastore tables into PostgreSQL.",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("CKAN_BASE_URL", BASE_URL_DEFAULT),
        help="CKAN API base URL",
    )
    parser.add_argument("--batch-size", type=int, default=5000, help="datastore_search page size")
    parser.add_argument(
        "--resource",
        choices=("all", "trips_sample", "summary_stats"),
        default="all",
        help="Which datastore resource to load",
    )
    parser.add_argument(
        "--no-truncate",
        action="store_true",
        help="Do not truncate tables before load",
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
    ids = get_datastore_resource_ids(args.base_url, session)
    print(f"Datastore resource ids: trips_sample={ids['trips_sample']}, summary_stats={ids['summary_stats']}")

    load_trips = args.resource in ("all", "trips_sample")
    load_summary = args.resource in ("all", "summary_stats")

    if args.dry_run:
        for name, flag in (("trips_sample", load_trips), ("summary_stats", load_summary)):
            if not flag:
                continue
            rid = ids[name]
            total = 0
            first: List[dict[str, Any]] | None = None
            for batch in iter_datastore_batches(args.base_url, rid, session, args.batch_size):
                if first is None and batch:
                    first = batch
                total += len(batch)
            print(f"Would load {total} rows into {name} (resource {rid}).")
            if first:
                print(f"  Sample keys ({name}):", sorted(first[0].keys()))
        return

    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            if load_trips:
                cur.execute(DDL_TRIPS)
                cur.execute(IDX_TRIPS_PICKUP)
                cur.execute(IDX_TRIPS_DT)
            if load_summary:
                cur.execute(DDL_SUMMARY)
                cur.execute(IDX_SUMMARY_DT)

        if load_trips and not args.no_truncate:
            with conn.cursor() as cur:
                cur.execute(f"TRUNCATE TABLE {TABLE_TRIPS}")
        if load_summary and not args.no_truncate:
            with conn.cursor() as cur:
                cur.execute(f"TRUNCATE TABLE {TABLE_SUMMARY}")

        inserted_trips = 0
        inserted_summary = 0
        if load_trips:
            for batch in iter_datastore_batches(
                args.base_url, ids["trips_sample"], session, args.batch_size
            ):
                with conn.cursor() as cur:
                    cur.executemany(INSERT_TRIPS, [row_trips(rec) for rec in batch])
                    inserted_trips += len(batch)
        if load_summary:
            for batch in iter_datastore_batches(
                args.base_url, ids["summary_stats"], session, args.batch_size
            ):
                with conn.cursor() as cur:
                    cur.executemany(INSERT_SUMMARY, [row_summary(rec) for rec in batch])
                    inserted_summary += len(batch)
        conn.commit()

    if load_trips:
        print(f"Inserted {inserted_trips} rows into {TABLE_TRIPS}.")
    if load_summary:
        print(f"Inserted {inserted_summary} rows into {TABLE_SUMMARY}.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
