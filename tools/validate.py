# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Validate every lab in labs/.

Checks per lab folder (any directory containing topology.yaml):
  - topology.yaml parses and looks like a CML export (lab / nodes / links)
  - lab title starts with the project tag "[LAB] "
  - licensed node count <= the license limit (unlicensed definitions excluded)
  - every node_definition / image_definition exists in tools/server-inventory.json
  - links reference existing nodes and interfaces
  - README.md exists; solution/ exists and has the files its lab type requires

Usage:  uv run tools/validate.py [lab-dir ...]
Exit code 0 when all labs pass, 1 otherwise.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
LABS = REPO / "labs"
INVENTORY = REPO / "tools" / "server-inventory.json"
TITLE_PREFIX = "[LAB] "
REQUIRED_SOLUTION_FILES = {
    "learn": ["verification.md"],
    "ts": ["root-cause.md"],
}


def load_inventory() -> dict:
    with INVENTORY.open(encoding="utf-8") as f:
        return json.load(f)


def lab_type(lab_dir: Path) -> str | None:
    for prefix in REQUIRED_SOLUTION_FILES:
        if lab_dir.name.startswith(prefix + "-"):
            return prefix
    return None


def check_lab(lab_dir: Path, inv: dict) -> list[str]:
    errors: list[str] = []
    topo_path = lab_dir / "topology.yaml"

    try:
        topo = yaml.safe_load(topo_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        return [f"topology.yaml does not parse: {e}"]
    if not isinstance(topo, dict) or "nodes" not in topo or "lab" not in topo:
        return ["topology.yaml is not a CML export (missing 'lab' or 'nodes')"]

    title = (topo.get("lab") or {}).get("title", "")
    if not title.startswith(TITLE_PREFIX):
        errors.append(f"lab title {title!r} must start with {TITLE_PREFIX!r}")

    nodes = topo.get("nodes") or []
    defs = inv["node_definitions"]
    unlicensed = set(inv["unlicensed_node_definitions"])
    licensed = 0
    interfaces: dict[str, set[str]] = {}
    for node in nodes:
        label = node.get("label", node.get("id", "?"))
        nd = node.get("node_definition")
        if nd not in defs:
            errors.append(f"node {label}: node_definition {nd!r} is not available on the server")
        else:
            img = node.get("image_definition")
            if img and img not in defs[nd]:
                errors.append(f"node {label}: image_definition {img!r} not installed for {nd}")
        if nd not in unlicensed:
            licensed += 1
        interfaces[node.get("id")] = {i.get("id") for i in node.get("interfaces") or []}

    limit = inv["license_node_limit"]
    if licensed > limit:
        errors.append(f"{licensed} licensed nodes exceeds the {limit}-node license")

    for link in topo.get("links") or []:
        for n_key, i_key in (("n1", "i1"), ("n2", "i2")):
            n, i = link.get(n_key), link.get(i_key)
            if n not in interfaces:
                errors.append(f"link {link.get('id')}: unknown node {n!r}")
            elif i not in interfaces[n]:
                errors.append(f"link {link.get('id')}: node {n!r} has no interface {i!r}")

    if not (lab_dir / "README.md").is_file():
        errors.append("missing README.md")

    kind = lab_type(lab_dir)
    solution = lab_dir / "solution"
    if kind is None:
        errors.append("folder name must start with 'learn-' or 'ts-'")
    elif not solution.is_dir():
        errors.append("missing solution/ directory")
    else:
        for name in REQUIRED_SOLUTION_FILES[kind]:
            if not (solution / name).is_file():
                errors.append(f"missing solution/{name}")

    return errors


def main(argv: list[str]) -> int:
    inv = load_inventory()
    if argv:
        lab_dirs = [Path(a).resolve() for a in argv]
    else:
        lab_dirs = sorted(p.parent for p in LABS.rglob("topology.yaml")) if LABS.exists() else []

    if not lab_dirs:
        print("No labs found.")
        return 0

    failed = 0
    for lab_dir in lab_dirs:
        rel = lab_dir.relative_to(REPO) if lab_dir.is_relative_to(REPO) else lab_dir
        if not (lab_dir / "topology.yaml").is_file():
            print(f"FAIL {rel}\n  - no topology.yaml")
            failed += 1
            continue
        errors = check_lab(lab_dir, inv)
        if errors:
            failed += 1
            print(f"FAIL {rel}")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"ok   {rel}")

    if not inv.get("unlicensed_verified"):
        print("note: unlicensed node counting is unverified (see CLAUDE.md)")
    print(f"\n{len(lab_dirs) - failed}/{len(lab_dirs)} labs passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
