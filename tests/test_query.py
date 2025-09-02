from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path


# Ensure the package in ./src is importable when running tests without install
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ndb import cli  # type: ignore
from ndb import db as dbmod  # type: ignore


DB_PATH = ROOT / "test" / "local.db"


def run_cli(args: list[str]) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        # cli.main returns int exit code; we assert success in callers as needed
        cli.main(args)
    return buf.getvalue()


def ensure_db():
    if DB_PATH.exists():
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Initialize and populate the database using ndb key=value CAS entries
    cli.main(["db", "init", "--path", str(DB_PATH)])
    # Device CAS lines start with 'sys=' and include id/ip/category where available
    records = [
        "sys=feather-a id=cp-001 ip=192.168.0.10 category=cp",
        "sys=feather-b id=cp-002 ip=192.168.0.11 category=cp",
        "sys=esp-cam id=esp-003 ip=10.0.0.5 category=esp",
        "sys=printer id=misc-004 ip=192.168.0.200 category=other",
        "sys=unlabeled id=unlabeled-005",
    ]
    for line in records:
        cli.main(["cas", "put", "--path", str(DB_PATH), "--text", line])
    # Build devices table from CAS
    cli.main(["db", "refresh", "--path", str(DB_PATH)])


def test_list_devices_json_has_expected_count():
    ensure_db()
    out = run_cli(["ls", "--path", str(DB_PATH), "--json"])
    data = json.loads(out)
    # We expect exactly 5 inserted sample devices
    assert isinstance(data, list)
    assert len(data) == 5


def test_query_by_category_cp_returns_two_devices():
    ensure_db()
    out = run_cli(["query", "category=cp", "--path", str(DB_PATH), "--json"])
    data = json.loads(out)
    uids = {row["uid"] for row in data}
    assert uids == {"cp-001", "cp-002"}


def test_query_by_ip_returns_single_match():
    ensure_db()
    out = run_cli(["query", "ip=10.0.0.5", "--path", str(DB_PATH), "--json"])
    # we get a better error message if we assert the output first
    assert "esp-003" in out
    data = json.loads(out)
    assert len(data) == 1
    assert data[0]["uid"] == "esp-003"


def test_get_device_cas_returns_content():
    ensure_db()
    res = dbmod.get_device_cas("cp-001", db_path=str(DB_PATH))
    assert res is not None
    _h, content = res
    assert "sys=feather-a" in content
