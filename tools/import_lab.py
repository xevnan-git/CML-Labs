# /// script
# requires-python = ">=3.10"
# dependencies = ["virl2-client>=2.10,<2.11", "pyyaml>=6"]
# ///
"""Import a lab topology into CML from a local file or a URL (e.g. a raw GitHub link).

Reads CML_URL / CML_USERNAME / CML_PASSWORD / CML_VERIFY_SSL from the environment or a .env file at the repo root.
Refuses topologies whose title doesn't start with "[LAB] " so only project labs land on the shared server.

Usage:
  uv run tools/import_lab.py <path-or-url> [--start] [--insecure] [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
TITLE_PREFIX = "[LAB] "


def load_env(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines; existing environment variables win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def read_source(src: str) -> str:
    if src.startswith(("http://", "https://")):
        with urllib.request.urlopen(src, timeout=30) as r:
            return r.read().decode("utf-8")
    return Path(src).read_text(encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="topology.yaml path or URL")
    ap.add_argument("--start", action="store_true", help="start the lab after import")
    ap.add_argument("--insecure", action="store_true", help="skip TLS verification (self-signed cert)")
    ap.add_argument("--dry-run", action="store_true", help="parse and check only; don't contact CML")
    args = ap.parse_args()

    text = read_source(args.source)
    topo = yaml.safe_load(text)
    title = ((topo or {}).get("lab") or {}).get("title", "")
    if not title.startswith(TITLE_PREFIX):
        print(f"Refusing: lab title {title!r} does not start with {TITLE_PREFIX!r}", file=sys.stderr)
        return 2
    print(f"Topology: {title} ({len(topo.get('nodes') or [])} nodes)")
    if args.dry_run:
        print("Dry run — not importing.")
        return 0

    load_env(REPO / ".env")
    missing = [k for k in ("CML_URL", "CML_USERNAME", "CML_PASSWORD") if not os.environ.get(k)]
    if missing:
        print(f"Missing {', '.join(missing)} (set them in .env)", file=sys.stderr)
        return 2
    verify = not args.insecure and os.environ.get("CML_VERIFY_SSL", "true").lower() not in ("0", "false", "no")

    from virl2_client import ClientLibrary

    client = ClientLibrary(
        os.environ["CML_URL"], os.environ["CML_USERNAME"], os.environ["CML_PASSWORD"], ssl_verify=verify
    )
    existing = [lab for lab in client.all_labs(show_all=True) if lab.title == title]
    if existing:
        print(f"Note: {len(existing)} lab(s) titled {title!r} already exist; importing another copy.")

    lab = client.import_lab(text, title=title)
    print(f"Imported: {lab.title} (id {lab.id})")
    if args.start:
        print("Starting...")
        lab.start(wait=False)
        print("Start requested.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
