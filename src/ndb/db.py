from __future__ import annotations

import sqlite3
from pathlib import Path
import hashlib
from typing import Iterable, List, Tuple


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
