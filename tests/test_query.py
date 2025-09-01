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
    # Initialize and populate the database to mirror the manual setup
    cli.main(["db", "init", "--path", str(DB_PATH)])
    cli.main([
        "put", "--path", str(DB_PATH),
        "--uid", "cp-001", "--hostname", "feather-a", "--ip-address", "192.168.0.10", "--category", "cp",
        "--text", '{"note":"cp feather a"}',
    ])
    cli.main([
        "put", "--path", str(DB_PATH),
        "--uid", "cp-002", "--hostname", "feather-b", "--ip-address", "192.168.0.11", "--category", "cp",
        "--text", '{"note":"cp feather b"}',
    ])
    cli.main([
        "put", "--path", str(DB_PATH),
        "--uid", "esp-003", "--hostname", "esp-cam", "--ip-address", "10.0.0.5", "--category", "esp",
        "--text", '{"note":"esp32-cam"}',
    ])
    cli.main([
        "put", "--path", str(DB_PATH),
        "--uid", "misc-004", "--hostname", "printer", "--ip-address", "192.168.0.200", "--category", "other",
        "--text", '{"note":"network printer"}',
    ])
    cli.main([
        "put", "--path", str(DB_PATH),
        "--uid", "unlabeled-005",
        "--text", '{"note":"no host or ip"}',
    ])


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
    out = run_cli(["query", "ip_address=10.0.0.5", "--path", str(DB_PATH), "--json"])
    data = json.loads(out)
    assert len(data) == 1
    assert data[0]["uid"] == "esp-003"


def test_get_device_cas_returns_content():
    ensure_db()
    res = dbmod.get_device_cas("cp-001", db_path=str(DB_PATH))
    assert res is not None
    _h, content = res
    assert "cp feather a" in content
