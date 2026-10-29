# CLAUDE.md — CML CCNP Lab Library

Guidance for Claude Code sessions working in this repo. Read it fully before building or touching any lab.

## What this repo is

A library of Cisco Modeling Labs (CML) labs for **CCNP Enterprise: ENCOR 350-401 v1.2 + ENARSI 300-410 v1.1**
(CCNA foundations only where a CCNP lab needs them). Every topic gets:

- **Learning lab** (`learn-<name>/`) — guided build: objectives, tasks, verification with real show output and the *why*.
- **Troubleshooting lab** (`ts-<name>/`) — pre-broken topology, symptom-based ticket, hints; solution kept in `solution/`.

Labs are built **on demand**. `blueprint/` is the backlog; the user picks what gets built next.

The user understands much of CCNP conceptually but has seen little of it run. Labs teach by doing: concrete
topologies, the exact output to look for, and short explanations of why the device behaves that way.

## Safety rules (shared work server — non-negotiable)

- Only create/modify/start/stop/wipe/delete labs whose title starts with **`[LAB] `**. Never touch any other lab,
  even to read-and-tidy. (At setup the server held three untagged admin labs; leave them alone.)
- **Ask before any stop / wipe / delete**, even on our own labs, unless the user explicitly said to clean up that lab.
- Never change server settings, users, groups, licensing, or images.
- Never commit credentials. `.env` is git-ignored; only `.env.example` (placeholders) is committed. Don't put the CML
  hostname/URL or SSH details in the repo.

## Server facts (queried 2026-10-29)

| Item | Value |
|---|---|
| CML version | 2.10.1 (cml-mcp needs ≥ 2.9 ✔) |
| License | Reports "CML Personal, 20 nodes", but status EVAL / not registered (eval expires 2027-01-27) and the server **enforces 5 nodes**: starting a 6th licensed node fails with `5 of 5 node licenses are in use` |
| Hardware | 8 vCPU, ~8 GB RAM (IOL-XE allocates 1 GB each, Alpine 512 MB) |
| Health | all compute/controller checks valid |
| Lab repositories | supported (2.9+): admin can link a git repo, default branch, optional folder → set folder to `labs` |

This dev server is not the final target: the user will run the labs on an **external work CML server** that pulls
this repo as a CML Lab Repository. Labs are designed to the **20-node** target; `validate.py` enforces 20.

**Licensed node counting (verified 2026-10-29):** `unmanaged_switch` does **not** count — 5 IOL routers + 1 unmanaged
switch ran with 5/5 licenses used. `external_connector` is assumed not to count (unverified). Hosts (alpine etc.) do count.

### Node definitions with images (the only ones labs may use)

See `tools/server-inventory.json` (source of truth for `validate.py`). Summary:

| Role | node_definition | image |
|---|---|---|
| Router (default) | `iol-xe` | `iol-xe-17-18-02` |
| Router w/ serial | `iol-xe-serial-4eth` | `iol-xe-serial-4eth-17-18-02` |
| Router (classic IOS) | `iosv` | `iosv-159-3-m12` |
| L2/L3 switch (default) | `ioll2-xe` | `ioll2-xe-17-18-02` |
| L2 switch (classic) | `iosvl2` | `iosvl2-2020` |
| Firewall | `asav` | `asav-9-24-1` |
| Hosts | `alpine`, `server` (TinyCore), `desktop` | `alpine-base-3-23-3`, `server-tcl-17-0`, `alpine-desktop-3-23-3` |
| Servers (TACACS+/RADIUS/syslog/SNMP/NETCONF client) | `ubuntu` | `ubuntu-24-04-20260307` |
| Wireless | `wireless-ap`, `wireless-client` | (images present) |
| Built-ins | `unmanaged_switch`, `external_connector` | none needed |

**Not available** (defined but no image): cat8000v, csr1000v, XRd, XRv9000, Nexus 9000v, Cat9000v, Cat9800 WLC,
all SD-WAN, ISE, FTDv/FMCv, Meraki vMX, and every Docker node (FRR, net-tools, nginx, radius, tacplus, syslog,
dnsmasq, chrome, firefox, splunk, thousandeyes). Topics that need these are marked *N/A here* in the blueprint.

## Tooling

- CML access is through the **cml-mcp** server (github.com/xorrkaz/cml-mcp) running on an Ubuntu VM over SSH, with the
  `[pyats]` extra for device CLI. Today it is provided by the **Claude desktop app** (tools `mcp__Cisco_Modeling_Labs__CML___*`);
  it is *not* registered with the terminal `claude` CLI. If CLI use is needed, register at **user scope** by copying
  the desktop entry — never into a project `.mcp.json`.
- pyATS device login uses `PYATS_USERNAME` / `PYATS_PASSWORD` / `PYATS_AUTH_PASS` set on the VM side; every lab's
  base config must match them (see Device credentials below).
- Repo scripts are PEP 723 single-file scripts run with `uv run tools/<script>.py`. They read CML creds from `.env`.

## Conventions

Full detail and the base config live in [`templates/addressing.md`](templates/addressing.md). Short form:

- **Lab title:** `[LAB] <EXAM> <blueprint id> <Topic> – <learn|ts>-<name>`, e.g. `[LAB] ENARSI 1.10 OSPF – learn-multiarea`.
- **Paths:** `labs/<exam>/<domain-number>-<domain-slug>/<topic-slug>/<learn|ts>-<name>/`
  (exam ∈ `encor`, `enarsi`, `ccna`; e.g. `labs/encor/3-infrastructure/ospf/learn-multiarea/`).
- **Topology file name:** `<exam>-<id>-<topic>-<learn|ts>-<name>.yaml`, e.g. `encor-3.2.b-ospf-learn-multiarea.yaml`.
  Never `topology.yaml`: CML's Sample Labs browser flattens the repo, so names must be unique repo-wide. No other
  `.yaml` files anywhere under `labs/` (solutions use `.cfg` / `.md`) — CML would list them as labs.
- **Lab notes:** the topology's `lab.notes` holds the lab README (Markdown) so learners see the tasks/ticket inside
  CML; `lab.description` is a one-line summary for the Sample Labs list. Never put solutions in notes.
- **Each lab folder:** the topology file (CML export, configs embedded, importable as-is), `README.md`, `solution/`.
  - learn: `solution/verification.md` (real captured output) + `solution/configs/<node>.cfg` (final configs).
  - ts: `solution/root-cause.md` (faults, fix, how to verify) + `solution/configs/<node>.cfg` (fixed configs).
    The ts README must not reveal the fault.
- **Platforms:** `iol-xe` routers + `ioll2-xe` switches by default; `iosv`/`iosvl2` only where IOL lacks a feature
  (say why in the README). `alpine`/`server` for test hosts, `ubuntu` for service hosts.
- **Names:** `R1..Rn`, `SW1..n`, `PC1..n`, `SRV1..n`, `ISP1..n`, `FW1..n`. Node number drives addressing.
- **Addressing:** Lo0 `10.255.255.N/32` + `2001:db8:ffff::N/128`; link Ra–Rb (a<b) `10.a.b.0/24` + `2001:db8:a:b::/64`,
  host part = router number; LANs `192.168.<vlan>.0/24` (gateway/VIP .1, physical .2/.3, hosts .10+);
  BGP ASNs 650xx enterprise, 6451x ISP. No mgmt network by default (console + pyATS).
- **≤ 20 licensed nodes** per lab, enforced by `tools/validate.py`.

### Device credentials

`username cisco privilege 15 secret cisco`, `enable secret cisco` (confirmed by user). Lab-only, committed inside the
topology files; the `PYATS_*` values on the VM must match. Alpine hosts: cisco / cisco (image default).

## Lab build workflow

1. User names a topic. Design topology + write the README first; show the user a brief plan.
2. Build on the server via the MCP (title prefixed `[LAB] `), start it, verify with real device output (pyATS).
3. Troubleshooting labs: build working → verify → inject fault(s) → confirm the symptoms appear → record in `solution/`.
4. Export to `<exam>-<id>-<topic>-<lab>.yaml` (`download_lab_topology`), put the README into `lab.notes`, run `uv run tools/validate.py`, update `blueprint/*.md` status
   and the README index, commit (`<exam> <id>: add learn-/ts-<name>`).
5. Ask before stopping/wiping/deleting the lab on the server.

## Open items

- [x] Licensed-node counting: unmanaged_switch verified free (see above).
- [ ] **pyATS not available**: `send_cli_command` returns "PyATS and Genie are required". The desktop MCP entry
      must launch `cml-mcp[pyats]` (pyATS does not run on native Windows — it must run on the Ubuntu VM).
- [ ] **5-node enforcement** on the dev server blocks building labs > 5 licensed nodes here.
- [x] Device credentials confirmed: cisco / cisco, enable cisco.
- [ ] GitHub remote: private repo exists under `xevnan-git`; `gh` not installed. CML lab repositories may not
      sync private repos — test on the work server, or make the repo public.
- [x] Git identity set repo-locally (xevnan-git).
- [ ] `tools/cml_teardown_lab.py` — user will drop it in; restrict its lab list to `[LAB] ` titles and load `.env`.
- [ ] ENARSI: official v1.1 used; a v1.2 PDF URL returned 403 — recheck Cisco Learning Network occasionally.
