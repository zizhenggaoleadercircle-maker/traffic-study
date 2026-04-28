"""CKAN datastore_search pagination."""

from __future__ import annotations

from typing import Any, Iterator, List


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
