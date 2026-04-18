#!/usr/bin/env python3
"""
Smoke test: verify that Python can connect to PostgreSQL using DATABASE_URL.

Flow:
  1. Load environment variables from a file named .env in the project (via python-dotenv).
  2. Read DATABASE_URL (same format as libpq / DBeaver JDBC string, but URL form).
  3. Open one connection, run SELECT version(), print the result, exit 0.

Run:  source .venv/bin/activate && python connect_db.py
"""

import os
import sys

from dotenv import load_dotenv

# Load key=value pairs from .env into os.environ so DATABASE_URL is available.
load_dotenv()

url = os.environ.get("DATABASE_URL")
if not url:
    print("Missing DATABASE_URL. Copy .env.example to .env and set it.", file=sys.stderr)
    sys.exit(1)

# psycopg is the PostgreSQL driver; import here so we can print a helpful hint if venv is wrong.
try:
    import psycopg
except ImportError:
    print("Install dependencies: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    # Context managers close the connection and cursor when the block ends.
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            # version() returns one row, one column (string like "PostgreSQL 18.2 ...").
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
