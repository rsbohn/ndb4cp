from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import os

from . import __version__
from . import db as dbmod
from . import discover as discovermod
from .parsers import build_parser
from . import printer



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
        if args.db_cmd == "refresh":
            updated = dbmod.refresh_devices_from_cas(db_path=args.path)
            if not updated:
                print("No CAS entries starting with 'sys=' found.")
                return 0
            for uid, h in updated:
                print(f"{uid} {h}")
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
        if args.raw:
            rows = dbmod.cas_list_devices(db_path=args.path)
            for row in rows:
                print(row)
            return 0
        rows = dbmod.list_devices(db_path=args.path)
        printer.print_devices(rows, as_json=bool(args.json))
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
            elif k == "ip":
                k = "ip_address"
            filters[k] = v
        try:
            rows = dbmod.query_devices(filters, db_path=args.path)
        except ValueError as e:
            print(str(e))
            return 2
        printer.print_query(rows, as_json=bool(args.json))
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
