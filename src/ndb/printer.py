"""Output helpers for ndb CLI."""

from __future__ import annotations

import json
from typing import Iterable, Tuple


Row = Tuple[str, str | None, str | None, str | None, str, str]


def print_devices(rows: Iterable[Row], as_json: bool = False) -> None:
    """Print device rows as JSON or a simple table.

    rows are tuples: (uid, hostname, ip, category, cas_hash, last_seen)
    """
    rows_list = list(rows)
    if as_json:
        out = [
            {
                "uid": uid,
                "hostname": hostname,
                "ip": ip,
                "device_category": cat,
                "cas_hash": cas_hash,
                "last_seen": last_seen,
            }
            for (uid, hostname, ip, cat, cas_hash, last_seen) in rows_list
        ]
        print(json.dumps(out, indent=2))
        return

    def clip(s: str | None, width: int) -> str:
        s2 = (s or "-")
        return (s2[: width - 1] + "…") if len(s2) > width else s2

    W_UID, W_HOST, W_IP, W_CAT, W_SEEN = 12, 24, 15, 8, 19
    header = f"{ 'UID'.ljust(W_UID) }  { 'Hostname'.ljust(W_HOST) }  { 'IP'.ljust(W_IP) }  { 'Cat'.ljust(W_CAT) }  Last Seen"
    print(header)
    for uid, hostname, ip, cat, cas_hash, last_seen in rows_list:
        line = (
            f"{clip(uid, W_UID).ljust(W_UID)}  "
            f"{clip(hostname, W_HOST).ljust(W_HOST)}  "
            f"{clip(ip, W_IP).ljust(W_IP)}  "
            f"{clip(cat, W_CAT).ljust(W_CAT)}  "
            f"{(last_seen or '-'): >{W_SEEN}}"
        )
        print(line)


def print_query(rows: Iterable[Row], as_json: bool = False) -> None:
    """Print query results; wrapper over print_devices for clarity."""
    print_devices(rows, as_json=as_json)