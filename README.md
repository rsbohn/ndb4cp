ndb - a network database

Quickstart

- Run the CLI: `uv run ndb`
- Show version: `uv run ndb -- --version`

Query

- Search devices by field value:
  - `uv run -- ndb query ip_address=192.168.0.49`
  - `uv run -- ndb query category=cp --json`

Discovery

- Single device (via /cp/version.json):
  - `uv run -- ndb discover --from 192.168.0.191:80`
  - Add `--raw --debug` to print the fetched JSON and URL.
  - If needed, pass the Web API password with `--password` or env `CIRCUITPY_WEB_API_PASSWORD`.
- mDNS sweep (requires zeroconf):
  - Install once: `uv add zeroconf`
  - Scan and save: `uv run -- ndb discover --mdns --mdns-duration 3`
  - Preview without saving: add `--dry-run`

Notes

- Uses a `src/` layout with the package at `src/ndb`.
- Entry point is defined under `[project.scripts]` as `ndb = "ndb.cli:main"` in `pyproject.toml`.
