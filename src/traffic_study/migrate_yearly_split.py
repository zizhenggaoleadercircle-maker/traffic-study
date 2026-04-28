"""
One-time migration: copy rows from unified pts_trips_yearly (source_year column)
into pts_trips_yearly_{year}, then drop the old table.

If pts_trips_yearly does not exist, exits with a short message (nothing to do).

Requires DATABASE_URL (see .env.example).
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

from traffic_study.trips_yearly_zip import ddl_indexes, ddl_year_table, table_name_for_year

load_dotenv()


def main() -> None:
    import psycopg

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Missing DATABASE_URL.", file=sys.stderr)
        sys.exit(1)

    old = "pts_trips_yearly"

    with psycopg.connect(db_url) as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                  SELECT 1 FROM information_schema.tables
                  WHERE table_schema = 'public' AND table_name = %s
                )
                """,
                (old,),
            )
            if not cur.fetchone()[0]:
                print(f"Table {old!r} not found; no migration needed.")
                return

            cur.execute(f"SELECT DISTINCT source_year FROM {old} ORDER BY 1")
            years = [r[0] for r in cur.fetchall()]
            if not years:
                print(f"{old} has no rows; dropping empty unified table.")
                cur.execute(f"DROP TABLE {old}")
                conn.commit()
                print("Done.")
                return

            print(f"Migrating years from {old}: {years}")

            cols = """
                dt, pickup_hr,
                pickup_municipality, pickup_community_council, pickup_ward,
                dropoff_municipality, dropoff_community_council, dropoff_ward,
                trips_total, fare_avg, waittime_avg, distance_avg, duration_avg,
                loaded_at
            """

            for y in years:
                tname = table_name_for_year(int(y))
                cur.execute(ddl_year_table(tname))
                for stmt in ddl_indexes(tname):
                    cur.execute(stmt)
                cur.execute(f"TRUNCATE TABLE {tname}")
                cur.execute(
                    f"""
                    INSERT INTO {tname} ({cols})
                    SELECT {cols}
                    FROM {old}
                    WHERE source_year = %s
                    """,
                    (y,),
                )
                cur.execute(f"SELECT COUNT(*) FROM {tname}")
                n = cur.fetchone()[0]
                print(f"  {tname}: {n:,} rows")

            cur.execute(f"DROP TABLE {old}")
        conn.commit()

    print(f"Dropped unified table {old!r}. Use traffic-import-trips-yearly-zip for reloads.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
