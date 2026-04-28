"""CKAN / CSV value parsing shared by loaders."""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


def parse_timestamp(val: Any) -> datetime | None:
    """CKAN returns timestamps as text; normalize for datetime.fromisoformat."""
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


def parse_bool_tf(val: Any) -> bool | None:
    """Postgres/CKAN often use 't' / 'f' for booleans in text form."""
    if val is None or val == "":
        return None
    v = str(val).strip().lower()
    if v in ("t", "true", "1", "yes"):
        return True
    if v in ("f", "false", "0", "no"):
        return False
    return None
