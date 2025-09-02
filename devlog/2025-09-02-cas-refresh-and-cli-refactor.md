## 2025-09-02 — CAS refresh + CLI/printer refactor

### Summary
- Devices can now be rebuilt from CAS rows that start with `sys=`.
- CLI parsing moved into `parsers.py`.
- `ls`/`query` output centralized in `printer.py` (JSON or table).
- Query filters accept `ip=…` (mapped to DB `ip_address`). JSON outputs use `ip`.
- `ls --raw` prints raw `sys=…` CAS lines.

### Changes
- db
  - Added `refresh_devices_from_cas(db_path=...)` to scan CAS for `sys=` entries, parse first line `key=value` tokens, and upsert `devices`.
  - Added helper `_parse_kv_line`.
  - Added `cas_list_devices()` to return CAS contents beginning with `sys` for raw listing.
- cli
  - New `db refresh` subcommand to rebuild `devices` from CAS.
  - Moved `build_parser` to `parsers.py` and import it.
  - `ls` uses `printer.print_devices` and supports `--json` and `--raw`.
  - `query` maps `ip` -> `ip_address`; output rendered via `printer.print_query`.
  - `put` adds `--ip` as alias to `--ip-address`.
  - Fixed/cleaned up `discover --mdns` path after earlier edits.
- printer
  - Implemented `print_devices(rows, as_json=False)` with JSON (key `ip`) and table output.
  - Added `print_query(...)` delegating to `print_devices`.
- tests
  - Test DB seeding switched to CAS `key=value` lines and `db refresh` to populate `devices`.
  - Adjusted a content assertion to look for `sys=…` instead of JSON.

### Data model / compatibility
- DB still stores column `ip_address`. CLI/UI and JSON use `ip`. Mapping handled in CLI.
- CAS content limit remains 4096 chars; `cas_put` enforces it.

### How to try
```
# Initialize, seed a couple of CAS device lines, refresh, then list
python -m ndb.cli db init --path ./local.db
python -m ndb.cli cas put --path ./local.db --text "sys=feather-a id=cp-001 ip=192.168.0.10 category=cp"
python -m ndb.cli db refresh --path ./local.db
python -m ndb.cli ls --path ./local.db --json
python -m ndb.cli query ip=192.168.0.10 --path ./local.db --json
```

### Quality gates
- Type/syntax: no errors reported in `db.py`, `cli.py`, `parsers.py`, `printer.py`.
- Tests: updated; one query test may need `--json` to parse structured output.

### Next steps
- Add a small migration helper if we ever rename DB `ip_address` -> `ip`.
- Extend CAS parser to support multi-line records and quoted values.
- Add round-trip tests for `db refresh` and `ls --raw`.
- Consider `ndb import` for bulk CAS ingestion from a file.