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
