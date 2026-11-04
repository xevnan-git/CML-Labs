# Handoff — CML CCNP Lab Library

Paste this into a new chat to continue the project. (It supersedes `claude-code-handoff-prompt.md`, the original setup brief.)
Read `CLAUDE.md` too: it holds the full conventions, safety rules and verified platform facts.

## Goal
Build a GitHub repo of Cisco Modeling Labs (CML) labs for **CCNP Enterprise: ENCOR 350-401 v1.2 + ENARSI 300-410 v1.1**.
Every exam topic gets two labs:
- **Learning lab**: a step-by-step Guide builds the topic, showing the exact commands, what to look for in the output, and *why*.
- **Troubleshooting lab**: the network boots with injected faults. The Guide has a ticket, logins, addressing, intended design and expected behavior, with **no hints**. Hints and the solution live only in the repo's `solution/README.md`.

The user understands CCNP concepts but has seen little of it running, so labs teach by doing. Labs are built **on demand**: the user names the next topic.

## Current status (2026-11-04, ENCOR 3.0 run in progress: 3.2.a done)
- **Repo:** https://github.com/xevnan-git/CML-Labs, branch `main`, everything committed and pushed. Local checkout:
  `C:\Claude\CML-Labs`. `validate.py`: 16/16 labs pass.
- **Built (all dev-tested on the 5-node server; none yet run on the 20-node server):**

  | Blueprint | Lab | Folder |
  |---|---|---|
  | ENCOR 3.2.a | `[LEARN] ENCOR 3.2.a EIGRP vs OSPF` (no TS lab) | `labs/encor/3-infrastructure/eigrp-ospf/learn-eigrp-vs-ospf` |
  | ENCOR 3.2.b | `[LEARN] ENCOR 3.2.b OSPF Multi-Area` | `labs/encor/3-infrastructure/ospf/learn-multiarea` |
  | ENCOR 3.2.b | `[TSHOOT] ENCOR 3.2.b OSPF Multi-Area Adjacency` | `…/ospf/ts-multiarea-adjacency` |
  | ENCOR 3.1.a+b | `[TSHOOT] ENCOR 3.1.a-b Trunking and EtherChannel` (4 faults) | `…/switching/ts-trunk-etherchannel` |
  | ENCOR 3.1.a | `[TSHOOT] ENCOR 3.1.a 802.1Q Trunking and DTP` (5 faults) | `…/switching/ts-trunking` |
  | ENCOR 3.1.b | `[TSHOOT] ENCOR 3.1.b EtherChannel (LACP, PAgP, L3)` (5 faults) | `…/switching/ts-etherchannel` |
  | ENCOR 3.1.c | `[LEARN] ENCOR 3.1.c Spanning Tree (RSTP, MST, Guards)` | `…/switching/learn-stp` |
  | ENCOR 3.1.c | `[TSHOOT] ENCOR 3.1.c MST and STP Guards` (4 faults) | `…/switching/ts-mst-guards` |
  | ENCOR 3.2.c | `[LEARN] ENCOR 3.2.c eBGP Dual-Homed Edge` | `…/bgp/learn-ebgp` |
  | ENCOR 3.2.c | `[TSHOOT] ENCOR 3.2.c eBGP Peering and Best Path` (5 faults, all on R1) | `…/bgp/ts-ebgp` |
  | ENCOR 5.2.a | `[LEARN] ENCOR 5.2.a ACLs` (also ENARSI 3.2.a) | `labs/encor/5-security/infra-security/learn-acl` |
  | ENCOR 5.2.a | `[TSHOOT] ENCOR 5.2.a ACLs` (5 faults, 4 on R1, 1 on R2) | `…/infra-security/ts-acl` |
  | ENCOR 5.2.b | `[LEARN] ENCOR 5.2.b CoPP` (also ENARSI 3.3) | `…/infra-security/learn-copp` |
  | ENCOR 5.2.b | `[TSHOOT] ENCOR 5.2.b CoPP` (5 faults, all on R1) | `…/infra-security/ts-copp` |
  | ENCOR 5.2.a-b | `[LEARN] ENCOR 5.2.a-b ACLs and CoPP` (iACL + CoPP + vty ACL) | `…/infra-security/learn-acl-copp` |
  | ENCOR 5.2.a-b | `[TSHOOT] ENCOR 5.2.a-b ACLs and CoPP` (4 faults, all on R1) | `…/infra-security/ts-acl-copp` |

  Older labs needed > 5 nodes and were tested in chunks; their solutions mark the few untestable end-to-end checks
  **Expected**. The 3.2.a, 5.2.a, 5.2.b and 5.2.a-b labs are 5 nodes each, so they ran whole and every output is **Captured**.
- **Backlog:** `blueprint/encor-v1.2.md` and `blueprint/enarsi-v1.1.md` list every exam topic with plan and status.
- **Tooling:**
  - CML MCP (cml-mcp with pyATS) runs on an Ubuntu VM over SSH, from the Claude desktop app.
  - **Exec commands:** `send_cli_command`. **Config commands:** `send_cli_config_command` (load it with ToolSearch).
    Since 2026-11-04, `send_cli_command` with `config_command=true` runs the lines in exec mode and fails with
    `% Invalid input` on the first line.
  - Scripts: `tools/validate.py`, `tools/sync_notes.py`, `tools/import_lab.py`, and one builder per lab pair in
    `tools/builders/`. The newest, `encor_5_2_a_acl.py` and `encor_5_2_b_copp.py`, are the cleanest pattern;
    `encor_5_2_ab_acl_copp.py` imports the 5.2.b builder and only adds R1's extra layers (a model for combined pairs).

## User preferences (from feedback)
- **Guide layout, scenario first:** Ticket / objectives → Done when → Rules → Intended design → Expected behavior,
  then `---` and a `# Reference` section (lab access, topology, addressing) at the bottom. The templates follow this.
  The OSPF guides predate it and were deliberately left alone.
- **Troubleshooting difficulty:** about 4 faults for a combined topic, **5 for a single topic**, with some faults
  layered so that fixing one reveals the next. Larger topologies (6–8 nodes) are fine.
- A TS Guide's Rules must not hint (e.g. no "re-check PC1 after every change").
- Learn labs can be skipped when the user says so (3.1.a/b were TS-only by request).
- Show the plan (topologies, Guide steps, fault lists) before building a new topic. Once the user approves a
  multi-lab plan, build its labs without re-asking; just confirm "next pair?" between them.

## Decisions awaiting the user's feedback
- **Learn labs with preconfigured routing:** the 5.2.a and 5.2.b learn labs boot with addressing, OSPF and BGP
  already working (no ACLs / no CoPP), because the topic isn't routing. That bends CLAUDE.md's "learn labs boot
  clean" rule. The user was told and hasn't objected; the 5.2.a-b learn lab does the same.
- **Topology changes vs the original plan:** the ACL labs use R1, R2, PC1, PC2 and SRV1 (an Alpine web/SSH server)
  instead of three routers, so there's a real host to protect. The user was told.

## Environment
- **Dev CML server:** CML 2.10.1 on VMware, unregistered eval license (expires 2027-01-27). It **enforces 5 running licensed nodes** (unmanaged switches don't count).
- **Target:** the user's 20-node work server. Design every lab for ≤ 20 nodes; test here in ≤ 5-node chunks.
- **Images:** IOL-XE 17.18.2 routers, IOL-L2-XE switches, IOSv, IOSv-L2, ASAv, Alpine, TinyCore, Ubuntu 24.04. No Cat8000v/CSR/XR/Nexus/Cat9kv/WLC/SD-WAN/ISE/Docker nodes, so those topics are marked "N/A here" in the backlog.
- **MCP:** runs from the Claude desktop app via SSH to the Ubuntu VM (user `justin`, lowercase). Credentials live only in a 600-mode env file on the VM. Hyper-V must stay **off** (it breaks VMware), so there's no WSL or Docker.
- **CML pulls the repo** as a Lab Repository (Folder = `labs`). CML can't authenticate, so the user makes the repo **public while working, private otherwise**. A refresh error `could not read Username for 'https://github.com'` just means it's private: ask the user to switch it.
- The local Windows checkout has **no `.env`**, so the import check and repo refresh can't run from here.

## Key decisions (all detailed in `CLAUDE.md`)
- **Titles:** `[LEARN] <EXAM> <id> <Topic>` / `[TSHOOT] <EXAM> <id> <Topic>`. Temporary test chunks use `[TEST] …`.
- **Paths:** `labs/<exam>/<n>-<domain>/<topic>/<learn|ts>-<name>/` containing `<exam>-<id>-<topic>-<learn|ts>-<name>.yaml` (unique name, never `topology.yaml`), `README.md` (the Guide, also copied into the lab's CML notes), `solution/README.md` and `solution/configs/*.cfg`.
- **Every licensed node has a canvas label** with its login and addresses.
- **Logins:** routers `cisco` / `cisco`, enable `cisco`; Alpine hosts `cisco` / `cisco`.
- **Addressing:** Lo0 `10.255.255.N/32`; link Ra–Rb `10.a.b.0/24` with host = router number; LANs `192.168.<vlan>.0/24` (gateway .1); summarizable blocks `172.(16+N).x.0/24`; ISP routers number from 101. Full plan in `templates/addressing.md`.
- **Solution output** is labelled **Captured** (real pyATS output) or **Expected** (not yet run).
- **Git identity:** `xevnan-git <348862922+xevnan-git@users.noreply.github.com>`. GitHub rejects the Gmail address.

## Workflow per lab
1. The user names a topic. Design the topology and Guide; show a brief plan.
2. Write a builder in `tools/builders/` that generates the clean, final and faulted configs plus both YAMLs
   (`--chunks DIR` writes test topologies as JSON for `create_full_lab_topology`).
3. Test in ≤ 5-node `[TEST]` labs with pyATS. Learn lab: boot the clean variant and run every Guide step as
   written, capturing output for the Guide. TS lab: boot the faulted variant, confirm each symptom, fix in order,
   re-verify the "Done when" list. Delete the `[TEST]` lab afterwards (standing OK).
4. Write the Guides and solutions, then run the builder, `uv run tools/sync_notes.py` and `uv run tools/validate.py`.
5. Update the backlog rows (both exams where a topic is shared), the README index and this file; commit
   (`<exam> <id>: add learn-/ts-<name>`) and push. Import check and repo refresh happen from the VM.

## Avoid
- **Shared-server safety:**
  - Never touch CML labs without a project tag (`[LEARN]`/`[TSHOOT]`/`[TEST]`/legacy `[LAB]`). Three untagged admin labs on the server belong to the user.
  - Ask before stopping, wiping or deleting any lab, except `[TEST]` labs you created, which have a standing OK.
  - Never change CML server settings, users, licensing or images.
- **Secrets:** never commit credentials, IPs or SSH details (`.env` is git-ignored). Don't put the CML password in command lines.
- **Annotation format:** in committed YAML, annotation `border_style` must be `''`, `'2,2'` or `'4,2'`. The MCP tool wants `solid`/`dotted`/`dashed` instead, and the wrong form makes CML silently drop the lab ("Invalid topology file").
- **IOL config order:** in IOL startup configs, anything that references an interface (e.g. `route-map … match interface`) must come *after* that interface.
- **Hints in CML:** don't put hints or solutions in a troubleshooting Guide or the CML notes.
- **Timeouts:** the first pyATS command to a freshly booted node can time out; retry once. A single tool call
  that runs longer than about 45 s (e.g. `sleep 50` on a PC) times out, so wait in ≤ 45 s steps.
- **Platform traps (detail in `CLAUDE.md`):** IOL-L2 has `ip routing` on by default (L2-only switches need
  `no ip routing` or `ip default-gateway` is ignored); IOL-XE routers can't do EtherChannel; IOL-L2 has no
  `min-links` and drops `lacp max-bundle`; pyATS turns off console logging when it connects (labs are fine).
- **Security traps (found building 5.2.a/b, detail in `CLAUDE.md`):**
  - An outbound ACL whose lines never match drops the router's own ARP replies on IOL-XE (`0 packets output`).
  - CoPP: `drop` is rejected under a control-plane class (use `police … conform-action drop exceed-action drop`);
    ARP lands in class-default, so a dropping class-default kills ARP; a class policed at 32 kbps (bc 1500)
    hangs SSH but not Telnet.
  - Layer order (verified building 5.2.a-b): interface ACL first, then CoPP. But with `ip unreachables` on (the
    default), a packet the ACL denies is punted to build the unreachable and CoPP classifies *that*, so CoPP
    counters move for denied traffic and a denied telnet just times out. Use `no ip unreachables` on the
    internet interface for clean counters.
  - IOL-XE's HTTP server is on by default but answers port 80 with a reset; don't use HTTP to a router as a test.
  - Alpine: `ssh`, `telnet`, `nc`, `wget`, and `sshd` running; web server is `/usr/sbin/httpd -p 80 -h <dir>`.
    No curl, nmap or SNMP client.
- **BGP traps (found building 3.2.c):** `network 192.168.10.0 mask 255.255.0.0` is *rejected* (host bits set);
  use a valid-but-unmatched prefix for a "not advertised" fault. After boot, BGP holds paths without `>` for up to
  ~2 min while a neighbor never comes up (read-only mode). `show ip bgp <pfx> best-path-reason` works on IOL-XE
  17.18. Policy changes need `clear ip bgp … soft in|out`, and the result lags the command by a few seconds.
- **pyATS on Alpine:** run `traceroute -n -q 1 -w 1` (and `ping -W 1`); default timeouts can exceed the tool call's.
- **Unverified claims:** test every fault's symptom live before writing it up. If a fault behaves
  non-deterministically (e.g. LACP picking a link by race), replace it. Don't state packet-level causes you
  haven't observed; describe what the counters showed.

## Open items
- Full runs of every lab on the 20-node server. As of 2026-11-04 the user hasn't run any yet; they'll give feedback
  on the Guide format once they do. No need to ask every session.
- 3.2.a, 3.2.c, 5.2.a, 5.2.b and 5.2.a-b YAMLs: CML import check (`POST /api/v0/import` from the VM) and Lab Repository refresh
  not yet run. Do it from the VM or ask the user.
- `tools/cml_teardown_lab.py`: the user will add it. Restrict it to project-tagged labs and `.env`.
- Unverified: whether `external_connector` counts against the license. Recheck now and then whether an ENARSI v1.2 blueprint exists.

## Very next step
**Resume here:** 3.2.a is done; next is the 3.2.d PBR pair. The plan below is approved, so don't re-show it: just
confirm "build 3.2.d next?" in one line (the last session asked but ended before an answer) and then build it.
- Model builder for a learn+ts pair: `tools/builders/encor_5_2_b_copp.py` (self-contained); for a learn-only lab:
  `tools/builders/encor_3_2_a_eigrp_ospf.py`. Folder for PBR: `labs/encor/3-infrastructure/pbr/`, files
  `encor-3.2.d-pbr-learn-<name>.yaml` / `encor-3.2.d-pbr-ts-<name>.yaml`. Update the ENCOR 3.2.d row and the ENARSI
  1.6 row (shared).
- Learn labs in this run boot with addresses (and any non-topic routing) preconfigured, like 3.2.a and 5.2.
- Test hint: `wait_for_convergence=true` on start, then expect the first pyATS command to time out once.

**Approved plan (2026-11-04): finish ENCOR 3.0, topics in blueprint order.** The user approved it as written; build
each pair without re-asking and just confirm "next pair?" between them. Every topology is ≤ 5 licensed nodes.

| # | Topic | Labs | Status |
|---|---|---|---|
| 1 | 3.2.a EIGRP vs OSPF | learn only | **done** |
| 2 | 3.2.d PBR (shared with ENARSI 1.6) | learn + ts (5 faults) | **next** |
| 3 | 3.3.a NTP (PTP concept-only) | learn + ts (5) | |
| 4 | 3.3.b NAT/PAT | learn + ts (5) | |
| 5 | 3.3.c HSRP + VRRP (also 1.1.b) | learn + ts (5) | |
| 6 | 3.3.d Multicast | learn + ts (5) | |

Details as approved:
- **3.2.d PBR:** PC1 (staff LAN) and PC2 (guest LAN) on R1, dual-homed to ISP1 and ISP2; both ISPs carry the same
  "internet server" loopback so traceroute shows the ISP used. Guide: default via ISP1, guests via ISP2 by
  route-map; `set ip next-hop` vs `set ip default next-hop`; `verify-availability` + IP SLA track; `ip local
  policy`; `show route-map` and `debug ip policy`. TS: policy on the wrong interface (PBR is ingress only), ACL
  matches the wrong source, `default next-hop` so the default route always wins, unreachable next hop (silent
  fallback to the RIB), IP SLA probing the wrong target.
- **3.3.a NTP:** NTP1 (`ntp master`) → R1 → R2 and R3 (R2–R3 peers). Guide: clock and time zone, hierarchy and
  stratum, peers, MD5 auth and `trusted-key`, `ntp access-group`, `ntp source`, `show ntp associations/status`.
  TS: key mismatch, missing `trusted-key`, access-group blocks, source interface the server can't reach,
  self-reference or loop. NTP sync takes minutes: plan the test waits.
- **3.3.b NAT/PAT:** PC1 and SRV1 (web) inside, R1 edge, ISP1, PC2 outside. Guide: inside/outside, static NAT +
  port forwarding for SRV1, dynamic pool, PAT overload, translations/statistics, `debug ip nat`, NAT order vs an
  outside ACL. TS: inside/outside swapped, wrong ACL wildcard, 1-address pool without overload, port forward to
  the wrong port, ISP has no route to the pool.
- **3.3.c FHRP:** R1 and R2 gateways for LAN10 (PC1, HSRPv2) and LAN20 (PC2, VRRPv3), R3 upstream as the target.
  Guide: priority, preempt, object tracking, timers, auth, load sharing per LAN, failover/failback with
  continuous pings. TS: group mismatch (two actives), VIP mismatch, missing preempt, track decrement too small,
  auth or version mismatch.
- **3.3.d Multicast:** five routers; `ping 239.x` as the source, `ip igmp join-group` receivers. Guide: IGMPv2 vs
  v3, PIM-SM static RP, shared tree vs SPT, RPF and static mroute fix, SSM; bidir and MSDP/anycast RP only if IOL-XE
  supports them (verify first, say so if not). TS: RPF failure, missing `ip pim`, RP mismatch, IGMPv2 for an SSM
  group, TTL or ACL boundary. The user approved adding a TS lab here (the backlog originally said learn only).
- Not in scope: OSPFv3 under ENCOR (the user didn't take the offer; it stays with ENARSI 1.10.a).
