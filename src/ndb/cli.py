from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import os

from . import __version__
from . import db as dbmod
from . import discover as discovermod


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
    ls.add_argument("--json", action="store_true", help="output JSON instead of a table")

    # ndb query: filter devices by field=value pairs
    query = sub.add_parser("query", help="query devices by example")
    query.add_argument(
        "pairs", nargs="+", help="field=value filters (e.g., ip_address=1.2.3.4)"
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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "db":
        if args.db_cmd == "init":
            path = dbmod.init_db(args.path)
            print(f"Initialized database at {path}")
            return 0
        if args.db_cmd == "status":
            rep = dbmod.db_status(
                db_path=args.path,
                include_orphans=(args.show_orphans or args.verbose),
                include_device_hashes=args.verbose,
            )
            if getattr(args, "json", False):
                import json as _json
                print(_json.dumps(rep, indent=2))
                return 0
            # Text output
            print(f"Database: {args.path}")
            print(f"Devices:  {rep['devices']}")
            print(f"CAS:      {rep['cas']}")
            print(f"Orphans:  {rep['orphans_count']}")
            if args.verbose and rep.get("device_hashes"):
                print("Device hashes:")
                for h in rep["device_hashes"]:  # type: ignore[index]
                    print(f"- {h}")
            if (args.show_orphans or args.verbose) and rep.get("orphans"):
                print("Orphan hashes:")
                for h in rep["orphans"]:  # type: ignore[index]
                    print(f"- {h}")
            return 0

    # ndb cas ...
    if args.cmd == "cas":
        if args.cas_cmd == "put":
            text: str | None = None
            if args.text is not None:
                text = args.text
            elif args.file is not None:
                text = args.file.read_text(encoding="utf-8")
            else:
                import sys
                text = sys.stdin.read()

            h = dbmod.cas_put(text, db_path=args.path)
            print(h)
            return 0

        if args.cas_cmd == "get":
            matches = dbmod.cas_get(args.key, db_path=args.path)
            if not matches:
                print(f"Not found: {args.key}")
                return 1
            show_hash = args.show_hash
            for i, (h, content) in enumerate(matches):
                if show_hash:
                    print(f"@{h}")
                print(content, end="" if content.endswith("\n") else "\n")
                if i < len(matches) - 1 and show_hash:
                    print("---")
            return 0

    if args.cmd == "put":
        if args.text is not None:
            content = args.text
        else:
            content = args.file.read_text(encoding="utf-8")
        cas_hash = dbmod.cas_put(content, db_path=args.path)
        dbmod.upsert_device(
            uid=args.uid,
            hostname=args.hostname,
            ip_address=args.ip_address,
            device_category=args.device_category,
            cas_hash=cas_hash,
            db_path=args.path,
        )
        print(cas_hash)
        return 0

    if args.cmd == "ls":
        rows = dbmod.list_devices(db_path=args.path)
        if args.json:
            import json as _json
            out = [
                {
                    "uid": uid,
                    "hostname": hostname,
                    "ip_address": ip,
                    "device_category": cat,
                    "cas_hash": cas_hash,
                    "last_seen": last_seen,
                }
                for (uid, hostname, ip, cat, cas_hash, last_seen) in rows
            ]
            print(_json.dumps(out, indent=2))
            return 0

        # Compact table output
        def clip(s: str | None, width: int) -> str:
            s2 = (s or "-")
            return (s2[: width - 1] + "…") if len(s2) > width else s2

        # Column widths
        W_UID, W_HOST, W_IP, W_CAT, W_SEEN = 12, 24, 15, 8, 19
        header = f"{ 'UID'.ljust(W_UID) }  { 'Hostname'.ljust(W_HOST) }  { 'IP'.ljust(W_IP) }  { 'Cat'.ljust(W_CAT) }  Last Seen"
        print(header)
        for uid, hostname, ip, cat, cas_hash, last_seen in rows:
            line = (
                f"{clip(uid, W_UID).ljust(W_UID)}  "
                f"{clip(hostname, W_HOST).ljust(W_HOST)}  "
                f"{clip(ip, W_IP).ljust(W_IP)}  "
                f"{clip(cat, W_CAT).ljust(W_CAT)}  "
                f"{(last_seen or '-'): >{W_SEEN}}"
            )
            print(line)
        return 0

    if args.cmd == "query":
        filters: dict[str, str] = {}
        for pair in args.pairs:
            if "=" not in pair:
                print(f"Invalid filter: {pair}")
                return 2
            k, v = pair.split("=", 1)
            if k == "category":
                k = "device_category"
            filters[k] = v
        try:
            rows = dbmod.query_devices(filters, db_path=args.path)
        except ValueError as e:
            print(str(e))
            return 2
        if args.json:
            import json as _json
            out = [
                {
                    "uid": uid,
                    "hostname": hostname,
                    "ip_address": ip,
                    "device_category": cat,
                    "cas_hash": cas_hash,
                    "last_seen": last_seen,
                }
                for (uid, hostname, ip, cat, cas_hash, last_seen) in rows
            ]
            print(_json.dumps(out, indent=2))
            return 0

        def clip(s: str | None, width: int) -> str:
            s2 = (s or "-")
            return (s2[: width - 1] + "…") if len(s2) > width else s2

        W_UID, W_HOST, W_IP, W_CAT, W_SEEN = 12, 24, 15, 8, 19
        header = f"{ 'UID'.ljust(W_UID) }  { 'Hostname'.ljust(W_HOST) }  { 'IP'.ljust(W_IP) }  { 'Cat'.ljust(W_CAT) }  Last Seen"
        print(header)
        for uid, hostname, ip, cat, cas_hash, last_seen in rows:
            line = (
                f"{clip(uid, W_UID).ljust(W_UID)}  "
                f"{clip(hostname, W_HOST).ljust(W_HOST)}  "
                f"{clip(ip, W_IP).ljust(W_IP)}  "
                f"{clip(cat, W_CAT).ljust(W_CAT)}  "
                f"{(last_seen or '-'): >{W_SEEN}}"
            )
            print(line)
        return 0

    if args.cmd == "get":
        res = dbmod.get_device_cas(args.uid, db_path=args.path)
        if not res:
            print(f"Not found: {args.uid}")
            return 1
        _hash, content = res
        print(content, end="" if content.endswith("\n") else "\n")
        return 0

    if args.cmd == "discover":
        password = args.password
        if password is None:
            import os as _os
            password = _os.environ.get("CIRCUITPY_WEB_API_PASSWORD")

        # mDNS mode: scan and process all devices found
        if args.mdns:
            try:
                found = discovermod.mdns_scan(duration=args.mdns_duration)
            except RuntimeError as e:
                print(str(e))
                return 2
            any_saved = False
            for ip, port, name in found:
                host = f"{ip}:{port}"
                info = discovermod.fetch_device_info(host, timeout=args.timeout, retries=args.retries, password=password)
                if not info:
                    if args.debug:
                        print(f"Failed to parse version.json from {host} ({name})")
                    continue
                record = info.to_record(seed=host, label=args.label)
                import json as _json
                content = _json.dumps(record, indent=2, ensure_ascii=False)
                if args.dry_run:
                    print(content)
                    continue
                cas_hash = dbmod.cas_put(content, db_path=args.path)
                dbmod.upsert_device(
                    uid=info.uid,
                    hostname=info.hostname,
                    ip_address=info.ip_address,
                    device_category=args.category,
                    cas_hash=cas_hash,
                    db_path=args.path,
                )
                print(f"{info.uid} {cas_hash} {host}")
                any_saved = True
            return 0 if (any_saved or args.dry_run) else 2

        # Seed mode: single host
        info = discovermod.fetch_device_info(
            args.seed, timeout=args.timeout, retries=args.retries, password=password
        )
        if not info:
            url, body = discovermod.fetch_raw(
                args.seed, timeout=args.timeout, retries=args.retries, password=password
            )
            if args.debug and url:
                print(f"Fetched {url} but parsing failed")
            if args.raw and body:
                print(body)
            if not url:
                print(f"Failed to fetch device info from {args.seed}")
            return 2
        record = info.to_record(seed=args.seed, label=args.label)
        import json as _json
        content = _json.dumps(record, indent=2, ensure_ascii=False)
        if args.raw:
            url, body = discovermod.fetch_raw(
                args.seed, timeout=args.timeout, retries=args.retries, password=password
            )
            if url and body:
                print(f"# Raw from {url}")
                print(body)
        if args.dry_run:
            print(content)
            return 0
        cas_hash = dbmod.cas_put(content, db_path=args.path)
        dbmod.upsert_device(
            uid=info.uid,
            hostname=info.hostname,
            ip_address=info.ip_address,
            device_category=args.category,
            cas_hash=cas_hash,
            db_path=args.path,
        )
        print(f"{info.uid} {cas_hash}")
        return 0

    if args.cmd == "status":
        # Prefer explicit path; environment override allowed via NDB_STATUS_BIN
        status_bin = os.environ.get("NDB_STATUS_BIN", "/home/rsbohn/.codex/bin/status")
        try:
            r = subprocess.run([status_bin])
            return r.returncode
        except FileNotFoundError:
            print("status helper not found:", status_bin)
            return 1

    # Default behavior for now
    print("Hello from ndb!")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
