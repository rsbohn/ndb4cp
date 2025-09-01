# ndb - a network database

Our work is comprised of a series of pitches.
To begin a pitch we create a devlog entry.
The devlog is a collection of markdown files in ./devlog.
At the end of each pitch we will document our work in the devlog.
Then we will commit and push.

## Affordances

Use `~/.codex/bin/status` to provide a status line when appropriate.

## Toolchain

- Python 3.12: Target runtime for the CLI and tooling. Verify with `uv run -- python --version`.
- uv: Project manager and runner for isolated builds and scripts. Common tasks:
  - `uv sync` to prepare `.venv` and install the local package.
  - `uv run -- ndb …` to execute the CLI.
- sqlite-utils: Handy CLI for inspecting/managing `local.db`. Run via uvx:
  - `uvx sqlite-utils tables local.db`
  - `uvx sqlite-utils rows local.db cas --limit 5`

## Devlog Privacy

- Scope: Public devlog entries must not disclose private network details (hostnames, private IPs, MACs, device UIDs, or any data that uniquely identifies local devices).
- Redaction: When needed, redact values (e.g., `192.168.0.xxx`, `host=redacted`) or omit fields entirely.
- Private notes: Store sensitive entries locally outside version control (e.g., under `.vscode/` which is gitignored in this repo). You may also use a `devlog/private/` folder if added to `.gitignore`.
- Public stubs: For sensitive changes, add a brief public stub in `devlog/` describing non-sensitive aspects (purpose, categories, generic roles/labels) and note that full details are kept locally.
- Review before commit: `git grep -n -E "(192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[0-1])\.|\.local\b)"` to catch accidental disclosures.
