from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable


PRIVATE_IP = re.compile(
    r"\b(?:10|192\.168|172\.(?:1[6-9]|2[0-9]|3[0-1]))\.(?:\d{1,3}\.){2}\d{1,3}\b"
)

# Match real hostnames ending in .local (service types like _http._tcp.local. are excluded)
LOCAL_HOST = re.compile(r"\b[a-z0-9-]+\.local\b", re.IGNORECASE)


def staged_files() -> list[Path]:
    try:
        out = subprocess.check_output(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            text=True,
        )
    except Exception:
        return []
    files = [Path(p.strip()) for p in out.splitlines() if p.strip()]
    return files


def pick_targets(paths: Iterable[Path]) -> list[Path]:
    targets: list[Path] = []
    for p in paths:
        if p.is_dir():
            continue
        # Only check devlog markdown files
        if not (str(p).startswith("devlog/") and p.suffix.lower() in {".md", ".markdown"}):
            continue
        targets.append(p)
    return targets


def scan_file(path: Path) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return findings
    for i, line in enumerate(text.splitlines(), start=1):
        # Allow masked IPs with xxx; the regex only matches digit octets
        hit_ip = PRIVATE_IP.search(line)
        hit_local = LOCAL_HOST.search(line)
        if hit_ip or hit_local:
            findings.append((i, line.rstrip()))
    return findings


def main(argv: list[str]) -> int:
    args = set(argv)
    if "--help" in args or "-h" in args:
        print("Usage: check_privacy.py [--staged]")
        return 0
    files: list[Path]
    if "--staged" in args:
        files = pick_targets(staged_files())
        # If none staged under devlog/, fall back to all devlog files
        if not files:
            files = pick_targets(Path("devlog").glob("*.md"))
    else:
        files = pick_targets(Path("devlog").glob("*.md"))

    any_fail = False
    for p in files:
        findings = scan_file(p)
        if findings:
            any_fail = True
            print(f"Privacy check: potential leak in {p}")
            for ln, content in findings:
                print(f"  L{ln}: {content}")

    if any_fail:
        print("\nERROR: Private network info detected in devlog. Mask or remove before commit.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

