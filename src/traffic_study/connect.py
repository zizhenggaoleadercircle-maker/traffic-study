"""
Smoke test: verify that Python can connect to PostgreSQL using DATABASE_URL.

Run:  traffic-connect
      python -m traffic_study.connect
"""

import os
import sys

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("Missing DATABASE_URL. Copy .env.example to .env and set it.", file=sys.stderr)
        sys.exit(1)
    try:
        import psycopg
    except ImportError:
        print("Install dependencies: pip install -e .", file=sys.stderr)
        sys.exit(1)
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
    print("Connected successfully.")
    print(version)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Connection failed: {e}", file=sys.stderr)
        sys.exit(1)
