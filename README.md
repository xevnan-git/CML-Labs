# CML CCNP Lab Library

Hands-on Cisco Modeling Labs (CML 2.9+) topologies for **CCNP Enterprise — ENCOR 350-401 v1.2 and ENARSI 300-410 v1.1**.

Each exam topic gets two kinds of labs:

- **Learning labs** (`learn-*`) — routers boot clean, and the Guide walks you step by step to the finished topic:
  exact commands, what to look for in the output, and *why* it behaves that way.
- **Troubleshooting labs** (`ts-*`) — the network boots fully configured with faults injected. The Guide gives the
  ticket, logins, addressing, intended design and expected behavior. Hints and the answer are only in the lab's
  `solution/README.md` here in the repo, not inside CML.

Each lab's Guide is also in the lab's **Notes** inside CML, and every node has a canvas label with its login and
addresses.

Every lab fits within a **20-node** CML license and uses only IOL-XE, IOL-L2-XE, IOSv, IOSv-L2, ASAv and Linux nodes.

## Lab index

| Exam | Blueprint | Topic | Learning lab | Troubleshooting lab |
|---|---|---|---|---|
| ENCOR | 3.1.a, 3.1.b | 802.1Q trunking (DTP, VTP domain) + EtherChannel (LACP, PAgP, misconfig guard) | — | [ts-trunk-etherchannel](labs/encor/3-infrastructure/switching/ts-trunk-etherchannel/) |
| ENCOR | 3.1.a | 802.1Q trunking: router-on-a-stick, DTP modes, native VLAN, transit VLANs | — | [ts-trunking](labs/encor/3-infrastructure/switching/ts-trunking/) |
| ENCOR | 3.1.b | EtherChannel: LACP, PAgP, `mode on`, member consistency, L3 port-channel | — | [ts-etherchannel](labs/encor/3-infrastructure/switching/ts-etherchannel/) |
| ENCOR | 3.1.c | Spanning tree: Rapid PVST+, MST regions, PortFast, BPDU guard, root guard | [learn-stp](labs/encor/3-infrastructure/switching/learn-stp/) | [ts-mst-guards](labs/encor/3-infrastructure/switching/ts-mst-guards/) |
| ENCOR | 3.2.a | EIGRP vs OSPF on one topology: LSDB vs topology table, cost vs composite metric, AD, feasible successor and DUAL queries, `variance`, summarization vs longest match | [learn-eigrp-vs-ospf](labs/encor/3-infrastructure/eigrp-ospf/learn-eigrp-vs-ospf/) | — |
| ENCOR | 3.2.b | OSPFv2 multi-area (DR/BDR, p2p, passive, summarization, filtering, ASBR) | [learn-multiarea](labs/encor/3-infrastructure/ospf/learn-multiarea/) | [ts-multiarea-adjacency](labs/encor/3-infrastructure/ospf/ts-multiarea-adjacency/) |
| ENCOR | 3.2.c | eBGP dual-homed edge: neighbor states, MD5, `network`, best path (weight, local-pref, prepend), no-transit | [learn-ebgp](labs/encor/3-infrastructure/bgp/learn-ebgp/) | [ts-ebgp](labs/encor/3-infrastructure/bgp/ts-ebgp/) |
| ENCOR | 5.2.a | ACLs (also ENARSI 3.2.a): standard vs extended placement, wildcards, named ACL sequence numbers, implicit deny vs OSPF, `established`, vty `access-class`, time-range | [learn-acl](labs/encor/5-security/infra-security/learn-acl/) | [ts-acl](labs/encor/5-security/infra-security/ts-acl/) |
| ENCOR | 5.2.b | CoPP (also ENARSI 3.3): classify routing/management/monitoring, police per class, BGP source vs destination port, OSPF EXSTART, SSH vs policer burst, class-default and ARP | [learn-copp](labs/encor/5-security/infra-security/learn-copp/) | [ts-copp](labs/encor/5-security/infra-security/ts-copp/) |
| ENCOR | 5.2.a-b | ACLs + CoPP layered on an internet edge (also ENARSI 3.2.a, 3.3): infrastructure ACL (peer, anti-spoofing, protect the router, transit), layer order iACL → CoPP → vty `access-class`, `no ip unreachables`, router-originated replies | [learn-acl-copp](labs/encor/5-security/infra-security/learn-acl-copp/) | [ts-acl-copp](labs/encor/5-security/infra-security/ts-acl-copp/) |

Labs marked *dev-tested* in the backlog were tested in 5-node chunks; they still need a full run on a 20-node server.

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
Raw GitHub URLs work too. Lab titles must start with `[LEARN] `, `[TSHOOT] ` or `[TEST] ` (the script checks).

### Removing a lab
`uv run tools/cml_teardown_lab.py` — lists this project's labs (`[LEARN]`, `[TSHOOT]`, `[TEST]`), asks you to type the title, then stop → wipe → delete
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
Checks every lab's topology file is uniquely named (CML's Sample Labs browser flattens folders), parses, has the right title tag (`[LEARN] ` or `[TSHOOT] `), stays within 20 licensed nodes, uses only node
types/images present on the server, and that each lab has a README and a solution.
