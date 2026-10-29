# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Validate every lab in labs/.

A lab folder is a learn-*/ts-* directory holding exactly one topology file named
<exam>-<id>-<topic>-<folder>.yaml (e.g. encor-3.2.b-ospf-learn-multiarea.yaml). CML's Sample Labs browser
flattens repo folders, so file names must be unique repo-wide — never plain topology.yaml.

Checks per lab folder:
  - one topology file, correctly named and unique across the repo
  - it parses and looks like a CML export (lab / nodes / links)
  - lab title starts with the mode tag: "[LEARN] " for learn-* labs, "[TSHOOT] " for ts-* labs
  - licensed node count <= the license limit (unlicensed definitions excluded)
  - every node_definition / image_definition exists in tools/server-inventory.json
  - links reference existing nodes and interfaces
  - every licensed node has a canvas text annotation that names it (login + addresses)
  - README.md exists and lab.notes matches it (run tools/sync_notes.py)
  - solution/README.md exists (hints/solution stay in the repo, never in CML notes)

Usage:  uv run tools/validate.py [lab-dir ...]
Exit code 0 when all labs pass, 1 otherwise.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
LABS = REPO / "labs"
INVENTORY = REPO / "tools" / "server-inventory.json"
TITLE_PREFIX = {"learn": "[LEARN] ", "ts": "[TSHOOT] "}
REQUIRED_SOLUTION_FILES = {
    "learn": ["README.md"],
    "ts": ["README.md"],
}


def load_inventory() -> dict:
    with INVENTORY.open(encoding="utf-8") as f:
        return json.load(f)


def lab_type(lab_dir: Path) -> str | None:
    for prefix in REQUIRED_SOLUTION_FILES:
        if lab_dir.name.startswith(prefix + "-"):
            return prefix
    return None


def topology_files(lab_dir: Path) -> list[Path]:
    return sorted(lab_dir.glob("*.yaml"))


def check_lab(lab_dir: Path, inv: dict) -> list[str]:
    errors: list[str] = []
    files = topology_files(lab_dir)
    if len(files) != 1:
        return [f"expected exactly one .yaml topology file, found {len(files)}"]
    topo_path = files[0]
    exam = lab_dir.relative_to(LABS).parts[0] if lab_dir.is_relative_to(LABS) else None
    if not topo_path.name.endswith(f"-{lab_dir.name}.yaml") or (exam and not topo_path.name.startswith(exam + "-")):
        errors.append(f"{topo_path.name}: name must be <exam>-<id>-<topic>-{lab_dir.name}.yaml")

    try:
        topo = yaml.safe_load(topo_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        return errors + [f"{topo_path.name} does not parse: {e}"]
    if not isinstance(topo, dict) or "nodes" not in topo or "lab" not in topo:
        return errors + [f"{topo_path.name} is not a CML export (missing 'lab' or 'nodes')"]

    title = (topo.get("lab") or {}).get("title", "")
    prefix = TITLE_PREFIX.get(lab_type(lab_dir))
    if prefix and not title.startswith(prefix):
        errors.append(f"lab title {title!r} must start with {prefix!r}")

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

    # CML's importer (and the Lab Repository indexer) only accepts these; anything else marks the whole file invalid.
    for k, a in enumerate(topo.get("annotations") or []):
        if a.get("border_style", "") not in ("", "2,2", "4,2"):
            errors.append(f"annotation {k}: border_style {a.get('border_style')!r} must be '', '2,2' or '4,2'")

    annotation_text = "\n".join(
        a.get("text_content", "") for a in topo.get("annotations") or [] if a.get("type") == "text"
    )
    for node in nodes:
        label = node.get("label", "")
        if node.get("node_definition") not in unlicensed and label not in annotation_text:
            errors.append(f"node {label}: no canvas text annotation with its login/addresses")

    readme = lab_dir / "README.md"
    if not readme.is_file():
        errors.append("missing README.md")
    elif (topo.get("lab") or {}).get("notes") != readme.read_text(encoding="utf-8"):
        errors.append("lab.notes does not match README.md (run: uv run tools/sync_notes.py)")

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
    all_yaml = [p for p in LABS.rglob("*.yaml") if "solution" not in p.parts] if LABS.exists() else []
    if argv:
        lab_dirs = [Path(a).resolve() for a in argv]
    else:
        lab_dirs = sorted({p.parent for p in all_yaml})

    if not lab_dirs:
        print("No labs found.")
        return 0

    name_counts = Counter(p.name for p in all_yaml)
    duplicates = {name for name, n in name_counts.items() if n > 1}

    failed = 0
    for lab_dir in lab_dirs:
        rel = lab_dir.relative_to(REPO) if lab_dir.is_relative_to(REPO) else lab_dir
        errors = check_lab(lab_dir, inv)
        errors += [f"{f.name}: file name is not unique in the repo" for f in topology_files(lab_dir) if f.name in duplicates]
        if errors:
            failed += 1
            print(f"FAIL {rel}")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"ok   {rel}")

    print(f"\n{len(lab_dirs) - failed}/{len(lab_dirs)} labs passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
