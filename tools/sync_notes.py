# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Copy each lab's README.md into its topology's lab.notes so the guide shows inside CML.

Usage:  uv run tools/sync_notes.py [lab-dir ...]     (default: every lab under labs/)
validate.py fails any lab whose notes don't match its README, so run this after editing a README.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
LABS = REPO / "labs"


class _Dumper(yaml.SafeDumper):
    pass


def _str_representer(dumper: yaml.SafeDumper, data: str) -> yaml.ScalarNode:
    # Multi-line strings (configs, notes) as literal blocks so the YAML stays readable and diffable.
    # PyYAML falls back to a quoted scalar if the text can't be a literal block (e.g. trailing spaces).
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_Dumper.add_representer(str, _str_representer)


def dump_topology(topo: dict) -> str:
    return yaml.dump(topo, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=1000)


def sync(lab_dir: Path) -> bool:
    files = sorted(lab_dir.glob("*.yaml"))
    readme = lab_dir / "README.md"
    if len(files) != 1 or not readme.is_file():
        print(f"skip {lab_dir}: need exactly one .yaml and a README.md")
        return False
    topo = yaml.safe_load(files[0].read_text(encoding="utf-8"))
    notes = readme.read_text(encoding="utf-8")
    if topo["lab"].get("notes") == notes:
        print(f"same {files[0].name}")
        return True
    topo["lab"]["notes"] = notes
    files[0].write_text(dump_topology(topo), encoding="utf-8", newline="\n")
    print(f"sync {files[0].name}")
    return True


def main(argv: list[str]) -> int:
    dirs = [Path(a).resolve() for a in argv] or sorted(
        {p.parent for p in LABS.rglob("*.yaml") if "solution" not in p.parts}
    )
    ok = all([sync(d) for d in dirs])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
