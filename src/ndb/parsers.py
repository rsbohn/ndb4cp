from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from . import db as dbmod


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(prog="ndb", description="ndb - a network database")
	parser.add_argument("--version", action="version", version=f"ndb {__version__}")

	sub = parser.add_subparsers(dest="cmd")

	# ndb db init
	db = sub.add_parser("db", help="database related commands")
	db_sub = db.add_subparsers(dest="db_cmd")

	init = db_sub.add_parser("init", help="initialize local database")
	init.add_argument(
		"--path",
		type=Path,
		default=dbmod.DEFAULT_DB_PATH,
		help="path to SQLite database (default: local.db)",
	)

	status = db_sub.add_parser("status", help="show database health report")
	status.add_argument(
		"--path",
		type=Path,
		default=dbmod.DEFAULT_DB_PATH,
		help="path to SQLite database (default: local.db)",
	)
	status.add_argument("--json", action="store_true", help="output JSON instead of text")
	status.add_argument(
		"--show-orphans", action="store_true", help="include orphan CAS hashes in report"
	)
	status.add_argument(
		"-v", "--verbose", action="store_true", help="list device CAS hashes and orphan hashes"
	)

	refresh = db_sub.add_parser("refresh", help="rebuild devices table from CAS 'sys=' entries")
	refresh.add_argument(
		"--path",
		type=Path,
		default=dbmod.DEFAULT_DB_PATH,
		help="path to SQLite database (default: local.db)",
	)

	# ndb cas put/get
	cas = sub.add_parser("cas", help="content-addressed storage commands")
	cas.add_argument(
		"--path", type=Path, default=dbmod.DEFAULT_DB_PATH, help="path to database"
	)
	cas_sub = cas.add_subparsers(dest="cas_cmd")

	cas_put = cas_sub.add_parser("put", help="store content and print hash")
	group = cas_put.add_mutually_exclusive_group()
	group.add_argument("--text", type=str, help="content string")
	group.add_argument("--file", type=Path, help="path to file with content")
	cas_put.add_argument(
		"--path", type=Path, default=dbmod.DEFAULT_DB_PATH, help="path to database"
	)

	cas_get = cas_sub.add_parser("get", help="retrieve content by hash or prefix")
	cas_get.add_argument("key", type=str, help="hash or prefix (optionally @-prefixed)")
	cas_get.add_argument(
		"--path", type=Path, default=dbmod.DEFAULT_DB_PATH, help="path to database"
	)
	cas_get.add_argument("--show-hash", action="store_true", help="print @hash before content")

	# ndb put: upsert a device using raw content stored in CAS
	put = sub.add_parser("put", help="upsert a device record")
	put.add_argument("--uid", required=True, help="stable device UID (from CircuitPython)")
	put.add_argument("--hostname", help="device hostname")
	put.add_argument("--ip-address", dest="ip_address", help="IP address")
	put.add_argument("--ip", dest="ip_address", help="IP address (alias)")
	put.add_argument("--category", dest="device_category", help="device category")
	put.add_argument(
		"--path", type=Path, default=dbmod.DEFAULT_DB_PATH, help="path to database"
	)
	src = put.add_mutually_exclusive_group(required=True)
	src.add_argument("--text", help="raw device JSON or text to store in CAS")
	src.add_argument("--file", type=Path, help="file containing raw device JSON/text")

	# ndb ls: list devices
	ls = sub.add_parser("ls", help="list known devices")
	ls.add_argument(
		"--path", type=Path, default=dbmod.DEFAULT_DB_PATH, help="path to database"
	)
	ls.add_argument("--raw", action="store_true", help="output raw ndb rows")
	ls.add_argument("--json", action="store_true", help="output JSON instead of a table")

	# ndb query: filter devices by field=value pairs
	query = sub.add_parser("query", help="query devices by example")
	query.add_argument(
		"pairs", nargs="+", help="field=value filters (e.g., ip=1.2.3.4)"
	)
	query.add_argument(
		"--path", type=Path, default=dbmod.DEFAULT_DB_PATH, help="path to database"
	)
	query.add_argument("--json", action="store_true", help="output JSON instead of a table")

	# ndb get <uid>: show raw content from CAS
	get = sub.add_parser("get", help="show raw device record by UID")
	get.add_argument("uid", help="device UID")
	get.add_argument(
		"--path", type=Path, default=dbmod.DEFAULT_DB_PATH, help="path to database"
	)

	# ndb discover: either --from HOST[:PORT] or --mdns to scan
	disc = sub.add_parser("discover", help="discover device(s)")
	mode = disc.add_mutually_exclusive_group(required=True)
	mode.add_argument("--from", dest="seed", help="seed host[:port]")
	mode.add_argument("--mdns", action="store_true", help="scan via mDNS for CircuitPython devices")
	disc.add_argument("--label", help="optional label like @smetch")
	disc.add_argument(
		"--category", default="cp", help="device category to record (default: cp)"
	)
	disc.add_argument(
		"--path", type=Path, default=dbmod.DEFAULT_DB_PATH, help="path to database"
	)
	disc.add_argument(
		"--dry-run", action="store_true", help="print record without saving"
	)
	disc.add_argument("--timeout", type=float, default=3.0, help="HTTP timeout seconds")
	disc.add_argument("--retries", type=int, default=0, help="number of retry cycles")
	disc.add_argument("--raw", action="store_true", help="print raw fetched page on success or when parsing fails")
	disc.add_argument("--debug", action="store_true", help="print the first reachable URL if any")
	disc.add_argument("--password", help="CircuitPython Web API password (or set CIRCUITPY_WEB_API_PASSWORD)")
	disc.add_argument("--mdns-duration", type=float, default=3.0, help="seconds to browse mDNS (when using --mdns)")

	# ndb status: print status line via external helper
	sub.add_parser("status", help="print a status line")

	return parser
