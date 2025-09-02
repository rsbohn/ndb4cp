from __future__ import annotations

import sqlite3
from pathlib import Path
import hashlib
from typing import Iterable, List, Tuple
from typing import Dict


DEFAULT_DB_PATH = Path("local.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS cas (
    hash TEXT PRIMARY KEY,
    content TEXT NOT NULL CHECK (length(content) <= 4096)
);

CREATE TABLE IF NOT EXISTS devices (
    uid TEXT PRIMARY KEY,
    hostname TEXT,
    ip_address TEXT,
    device_category TEXT,
    cas_hash TEXT NOT NULL,
    last_seen TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_devices_hostname ON devices(hostname);
CREATE INDEX IF NOT EXISTS idx_devices_ip ON devices(ip_address);
CREATE INDEX IF NOT EXISTS idx_devices_category ON devices(device_category);
"""


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    # Ensure better defaults
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(db_path: Path | str = DEFAULT_DB_PATH) -> Path:
    path = Path(db_path)
    with connect(path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.executescript(SCHEMA)
        conn.commit()
    return path


def hash_content(content: str) -> str:
    """Return a chelle-compatible SHA-256 hex digest for content.

    chelle computes `hashlib.sha256(content.encode('utf-8')).hexdigest()`.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def cas_put(content: str, db_path: Path | str = DEFAULT_DB_PATH) -> str:
    """Store content in CAS if absent and return its hash.

    Enforces the 4K character limit consistent with the DB schema.
    """
    if not isinstance(content, str):
        raise TypeError("content must be a string")
    if len(content) > 4096:
        raise ValueError("content too large (>4096 characters)")

    h = hash_content(content)
    with connect(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO cas(hash, content) VALUES(?, ?)",
            (h, content),
        )
        conn.commit()
    return h


def cas_get(key: str, db_path: Path | str = DEFAULT_DB_PATH) -> List[Tuple[str, str]]:
    """Retrieve content(s) by exact hash or prefix.

    Returns a list of (hash, content) tuples.
    Accepts keys starting with '@' and strips it (chelle-compatible UX).
    """
    if key.startswith("@"):
        key = key[1:]
    like = f"{key}%"
    with connect(db_path) as conn:
        cur = conn.execute(
            "SELECT hash, content FROM cas WHERE hash LIKE ? ORDER BY hash",
            (like,),
        )
        return list(cur.fetchall())


def upsert_device(
    *,
    uid: str,
    cas_hash: str,
    hostname: str | None = None,
    ip_address: str | None = None,
    device_category: str | None = None,
    db_path: Path | str = DEFAULT_DB_PATH,
) -> None:
    """Insert or update a device row by uid.

    Updates hostname/ip/category/cas_hash when provided, and refreshes timestamps.
    """
    now = "CURRENT_TIMESTAMP"
    with connect(db_path) as conn:
        # Try update first to avoid overriding fields with NULLs unnecessarily
        cur = conn.execute(
            """
            UPDATE devices
            SET
                hostname = COALESCE(?, hostname),
                ip_address = COALESCE(?, ip_address),
                device_category = COALESCE(?, device_category),
                cas_hash = COALESCE(?, cas_hash),
                last_seen = {now},
                updated_at = {now}
            WHERE uid = ?
            """.format(now=now),
            (hostname, ip_address, device_category, cas_hash, uid),
        )
        if cur.rowcount == 0:
            conn.execute(
                """
                INSERT INTO devices(uid, hostname, ip_address, device_category, cas_hash)
                VALUES(?, ?, ?, ?, ?)
                """,
                (uid, hostname, ip_address, device_category, cas_hash),
            )
        conn.commit()


def list_devices(
    *, db_path: Path | str = DEFAULT_DB_PATH
) -> List[Tuple[str, str | None, str | None, str | None, str, str]]:
    """Return devices as list of tuples: (uid, hostname, ip, category, cas_hash, last_seen)."""
    with connect(db_path) as conn:
        cur = conn.execute(
            "SELECT uid, hostname, ip_address, device_category, cas_hash, last_seen FROM devices WHERE deleted_at IS NULL ORDER BY hostname, uid"
        )
        return list(cur.fetchall())

def cas_list_devices(db_path: Path | str = DEFAULT_DB_PATH) -> list[str]:
    """Return a list of all CAS device hashes."""
    with connect(db_path) as conn:
        cur = conn.execute("SELECT DISTINCT content FROM cas WHERE content LIKE 'sys%'")
        return [row[0] for row in cur.fetchall()]


def _parse_kv_line(line: str) -> Dict[str, str]:
    """Parse a simple space-separated key=value line into a dict.

    Later values override earlier ones on duplicate keys.
    """
    out: Dict[str, str] = {}
    for tok in line.strip().split():
        if "=" not in tok:
            continue
        k, v = tok.split("=", 1)
        if k:
            out[k] = v
    return out


def refresh_devices_from_cas(*, db_path: Path | str = DEFAULT_DB_PATH) -> List[Tuple[str, str]]:
    """Refresh the devices table from CAS entries that start with 'sys='.

    Interprets CAS content as space-separated key=value pairs. Expected keys:
    - sys: a human name; used as hostname fallback and as uid if no id/uid
    - id or uid: preferred stable device identifier
    - ip: IP address (mapped to ip_address)
    - category: device category

    Returns a list of (uid, cas_hash) that were inserted or updated.
    """
    updated: List[Tuple[str, str]] = []
    with connect(db_path) as conn:
        cur = conn.execute(
            "SELECT hash, content FROM cas WHERE content LIKE 'sys%' ORDER BY hash"
        )
        rows = list(cur.fetchall())
        for cas_hash, content in rows:
            first_line = content.splitlines()[0] if content else ""
            kv = _parse_kv_line(first_line)
            uid = kv.get("id") or kv.get("uid") or kv.get("sys")
            if not uid:
                # Skip rows that don't specify any usable identifier
                continue
            hostname = kv.get("hostname") or kv.get("sys")
            ip_address = kv.get("ip") or kv.get("ip_address")
            category = kv.get("category") or kv.get("device_category")

            # Upsert within the same transaction for efficiency
            now = "CURRENT_TIMESTAMP"
            cur2 = conn.execute(
                f"""
                UPDATE devices
                SET
                    hostname = COALESCE(?, hostname),
                    ip_address = COALESCE(?, ip_address),
                    device_category = COALESCE(?, device_category),
                    cas_hash = COALESCE(?, cas_hash),
                    last_seen = {now},
                    updated_at = {now}
                WHERE uid = ? AND deleted_at IS NULL
                """,
                (hostname, ip_address, category, cas_hash, uid),
            )
            if cur2.rowcount == 0:
                conn.execute(
                    """
                    INSERT INTO devices(uid, hostname, ip_address, device_category, cas_hash)
                    VALUES(?, ?, ?, ?, ?)
                    """,
                    (uid, hostname, ip_address, category, cas_hash),
                )
            updated.append((uid, cas_hash))
        conn.commit()
    return updated


def query_devices(
    filters: dict[str, str], *, db_path: Path | str = DEFAULT_DB_PATH
) -> List[Tuple[str, str | None, str | None, str | None, str, str]]:
    """Return devices matching all field filters."""
    allowed = {"uid", "hostname", "ip_address", "device_category"}
    clauses: list[str] = []
    params: list[str] = []
    for key, value in filters.items():
        if key not in allowed:
            raise ValueError(f"Unknown field: {key}")
        clauses.append(f"{key} = ?")
        params.append(value)
    where = " AND ".join(clauses) if clauses else "1"
    query = (
        "SELECT uid, hostname, ip_address, device_category, cas_hash, last_seen "
        "FROM devices WHERE deleted_at IS NULL AND "
        + where
        + " ORDER BY hostname, uid"
    )
    with connect(db_path) as conn:
        cur = conn.execute(query, params)
        return list(cur.fetchall())


def get_device_cas(uid: str, *, db_path: Path | str = DEFAULT_DB_PATH) -> Tuple[str, str] | None:
    """Return (cas_hash, content) for a device uid, or None if not found."""
    with connect(db_path) as conn:
        cur = conn.execute(
            "SELECT cas_hash FROM devices WHERE uid = ? AND deleted_at IS NULL",
            (uid,),
        )
        row = cur.fetchone()
        if not row:
            return None
        cas_hash = row[0]
        cur2 = conn.execute(
            "SELECT hash, content FROM cas WHERE hash = ?",
            (cas_hash,),
        )
        row2 = cur2.fetchone()
        if not row2:
            return (cas_hash, "")
        return (row2[0], row2[1])


def db_status(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    include_orphans: bool = False,
    include_device_hashes: bool = False,
) -> Dict[str, object]:
    """Return a health report for the database.

    Keys:
    - cas: total CAS rows
    - devices: total non-deleted devices
    - orphans_count: CAS rows not referenced by any active device
    - orphans: list of orphan hashes (only when include_orphans=True)
    """
    with connect(db_path) as conn:
        cur = conn.execute("SELECT COUNT(*) FROM cas")
        cas_count = int(cur.fetchone()[0])
        cur = conn.execute("SELECT COUNT(*) FROM devices WHERE deleted_at IS NULL")
        dev_count = int(cur.fetchone()[0])
        cur = conn.execute(
            """
            SELECT hash FROM cas
            WHERE hash NOT IN (
                SELECT cas_hash FROM devices WHERE deleted_at IS NULL
            )
            ORDER BY hash
            """
        )
        orphans = [h for (h,) in cur.fetchall()]
        dev_hashes: list[str] = []
        if include_device_hashes:
            cur = conn.execute(
                "SELECT DISTINCT cas_hash FROM devices WHERE deleted_at IS NULL ORDER BY cas_hash"
            )
            dev_hashes = [h for (h,) in cur.fetchall()]
    report: Dict[str, object] = {
        "cas": cas_count,
        "devices": dev_count,
        "orphans_count": len(orphans),
    }
    if include_orphans:
        report["orphans"] = orphans
    if include_device_hashes:
        report["device_hashes"] = dev_hashes
    return report
