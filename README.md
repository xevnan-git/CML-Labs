# CML CCNP Lab Library

Hands-on Cisco Modeling Labs (CML 2.9+) topologies for **CCNP Enterprise — ENCOR 350-401 v1.2 and ENARSI 300-410 v1.1**.

Each exam topic gets two kinds of labs:

- **Learning labs** (`learn-*`) — build it yourself: objectives, step-by-step tasks, and the exact show output that
  proves it works, with a short explanation of *why*.
- **Troubleshooting labs** (`ts-*`) — a pre-broken network, a ticket describing the symptoms, and hints. The answer is
  in that lab's `solution/` folder — don't peek until you've tried.

Every lab fits within a **20-node** CML license and uses only IOL-XE, IOL-L2-XE, IOSv, IOSv-L2, ASAv and Linux nodes.

## Lab index

| Exam | Blueprint | Topic | Learning lab | Troubleshooting lab |
|---|---|---|---|---|
| — | — | *No labs built yet — see [`blueprint/`](blueprint/) for the backlog* | | |

Backlog and status: [ENCOR v1.2](blueprint/encor-v1.2.md) · [ENARSI v1.1](blueprint/enarsi-v1.1.md)

## Getting a lab into CML

### Option A — CML Lab Repository (whole library, admin once)
CML 2.9+ can sync labs from a git repo. A CML admin adds it under **Tools → Lab Repositories → Add**:
URL = this repo, **Folder = `labs`**. CML syncs the default branch; press **Refresh All** after new labs are pushed.
Labs then appear under **Tools → Sample Labs**.

### Option B — Web UI import (one lab)
1. Download the lab's `.yaml` file (e.g. `encor-3.2.b-ospf-learn-multiarea.yaml`).
2. In CML: **Dashboard → Import** → choose the file → **Import**.
3. Open the lab and **Start**.

### Option C — Script (file or URL)
```bash
cp .env.example .env   # fill in CML_URL / CML_USERNAME / CML_PASSWORD
uv run tools/import_lab.py labs/encor/3-infrastructure/ospf/learn-multiarea/encor-3.2.b-ospf-learn-multiarea.yaml --start
```
Raw GitHub URLs work too. Lab titles must start with `[LAB] ` (the script checks).

### Removing a lab
`uv run tools/cml_teardown_lab.py` — lists `[LAB] ` labs, asks you to type the title, then stop → wipe → delete
(`--dry-run`, `--insecure` available).

## Device logins

All lab devices use **cisco / cisco**, enable **cisco**. Consoles open straight to the prompt.

## Conventions

Naming and addressing are the same in every lab so topologies feel familiar — see
[`templates/addressing.md`](templates/addressing.md). Quick version: routers `R1..Rn` with Loopback0
`10.255.255.N`, and the link between R*a* and R*b* is `10.a.b.0/24`, where each router's address ends in its own number.

## Repo layout

```
blueprint/   exam topic backlog with build status
labs/        <exam>/<domain>/<topic>/{learn-*,ts-*}/{<unique-name>.yaml, README.md, solution/}
templates/   README templates, addressing & base-config conventions
tools/       validate.py, import_lab.py, cml_teardown_lab.py, server-inventory.json
```

## Contributing / validating

```bash
uv run tools/validate.py
```
Checks every lab's topology file is uniquely named (CML's Sample Labs browser flattens folders), parses, has the `[LAB] ` title prefix, stays within 20 licensed nodes, uses only node
types/images present on the server, and that each lab has a README and a solution.
