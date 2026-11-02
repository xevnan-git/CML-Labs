# Handoff — CML CCNP Lab Library

Paste this into a new chat to continue the project. (It supersedes `claude-code-handoff-prompt.md`, the original setup brief.)

## Goal
Build a GitHub repo of Cisco Modeling Labs (CML) labs for **CCNP Enterprise: ENCOR 350-401 v1.2 + ENARSI 300-410 v1.1**.
Every exam topic gets two labs:
- **Learning lab**: routers boot clean, and a step-by-step Guide builds the topic, showing the exact commands, what to look for in the output, and *why*.
- **Troubleshooting lab**: the network boots with injected faults. The Guide has a ticket, logins, addressing, intended design and expected behavior, with **no hints**. Hints and the solution live only in the repo's `solution/README.md`.

The user understands CCNP concepts but has seen little of it running, so labs teach by doing. Labs are built **on demand**: the user names the next topic.

## Current status (2026-11-02, updated after 3.2.c)
- **Repo:** https://github.com/xevnan-git/CML-Labs, branch `main`, everything pushed. Local checkout: `C:\Claude\CML-Labs`.
- **Built (all dev-tested in 5-node chunks; none yet run in full on the 20-node server):**

  | Blueprint | Lab | Folder |
  |---|---|---|
  | ENCOR 3.2.b | `[LEARN] ENCOR 3.2.b OSPF Multi-Area` | `labs/encor/3-infrastructure/ospf/learn-multiarea` |
  | ENCOR 3.2.b | `[TSHOOT] ENCOR 3.2.b OSPF Multi-Area Adjacency` | `…/ospf/ts-multiarea-adjacency` |
  | ENCOR 3.1.a+b | `[TSHOOT] ENCOR 3.1.a-b Trunking and EtherChannel` (4 faults) | `…/switching/ts-trunk-etherchannel` |
  | ENCOR 3.1.a | `[TSHOOT] ENCOR 3.1.a 802.1Q Trunking and DTP` (5 faults) | `…/switching/ts-trunking` |
  | ENCOR 3.1.b | `[TSHOOT] ENCOR 3.1.b EtherChannel (LACP, PAgP, L3)` (5 faults) | `…/switching/ts-etherchannel` |
  | ENCOR 3.1.c | `[LEARN] ENCOR 3.1.c Spanning Tree (RSTP, MST, Guards)` | `…/switching/learn-stp` |
  | ENCOR 3.1.c | `[TSHOOT] ENCOR 3.1.c MST and STP Guards` (4 faults) | `…/switching/ts-mst-guards` |
  | ENCOR 3.2.c | `[LEARN] ENCOR 3.2.c eBGP Dual-Homed Edge` | `…/bgp/learn-ebgp` |
  | ENCOR 3.2.c | `[TSHOOT] ENCOR 3.2.c eBGP Peering and Best Path` (5 faults, all on R1) | `…/bgp/ts-ebgp` |

  Each solution lists the few end-to-end checks that couldn't run under the 5-node limit, marked **Expected**.
- **Backlog:** `blueprint/encor-v1.2.md` and `blueprint/enarsi-v1.1.md` list every exam topic with plan and status.
- **Tooling works:**
  - CML MCP (cml-mcp with pyATS) runs on an Ubuntu VM over SSH, so `send_cli_command` works on IOL-XE, IOL-L2-XE and Alpine nodes.
  - Scripts: `tools/validate.py`, `tools/sync_notes.py`, `tools/import_lab.py`, and one builder per lab (pair) in `tools/builders/`.

## User preferences (from feedback)
- **Guide layout, scenario first:** Ticket / objectives → Done when → Rules → Intended design → Expected behavior,
  then `---` and a `# Reference` section (lab access, topology, addressing) at the bottom. The templates follow this.
  The OSPF guides predate it and were deliberately left alone.
- **Troubleshooting difficulty:** about 4 faults for a combined topic, **5 for a single topic**, with some faults
  layered so that fixing one reveals the next. Larger topologies (6–8 nodes) are fine.
- A TS Guide's Rules must not hint (e.g. no "re-check PC1 after every change").
- Learn labs can be skipped when the user says so (3.1.a/b were TS-only by request).

## Environment
- **Dev CML server:** CML 2.10.1 on VMware, unregistered eval license (expires 2027-01-27). It **enforces 5 running licensed nodes** (unmanaged switches don't count).
- **Target:** the user's 20-node work server. Design every lab for ≤ 20 nodes; test here in ≤ 5-node chunks.
- **Images:** IOL-XE 17.18.2 routers, IOL-L2-XE switches, IOSv, IOSv-L2, ASAv, Alpine, TinyCore, Ubuntu 24.04. No Cat8000v/CSR/XR/Nexus/Cat9kv/WLC/SD-WAN/ISE/Docker nodes, so those topics are marked "N/A here" in the backlog.
- **MCP:** runs from the Claude desktop app via SSH to the Ubuntu VM (user `justin`, lowercase). Credentials live only in a 600-mode env file on the VM. Hyper-V must stay **off** (it breaks VMware), so there's no WSL or Docker.
- **CML pulls the repo** as a Lab Repository (Folder = `labs`). CML can't authenticate, so the user makes the repo **public while working, private otherwise**. A refresh error `could not read Username for 'https://github.com'` just means it's private: ask the user to switch it.

## Key decisions (all detailed in `CLAUDE.md`)
- **Titles:** `[LEARN] <EXAM> <id> <Topic>` / `[TSHOOT] <EXAM> <id> <Topic>`. Temporary test chunks use `[TEST] …`.
- **Paths:** `labs/<exam>/<n>-<domain>/<topic>/<learn|ts>-<name>/` containing `<exam>-<id>-<topic>-<learn|ts>-<name>.yaml` (unique name, never `topology.yaml`), `README.md` (the Guide, also copied into the lab's CML notes), `solution/README.md` and `solution/configs/*.cfg`.
- **Every licensed node has a canvas label** with its login and addresses.
- **Logins:** routers `cisco` / `cisco`, enable `cisco`; Alpine hosts `cisco` / `cisco`.
- **Addressing:** Lo0 `10.255.255.N/32`; link Ra–Rb `10.a.b.0/24` with host = router number; LANs `192.168.<vlan>.0/24` (gateway .1); summarizable blocks `172.(16+N).x.0/24`. Full plan in `templates/addressing.md`.
- **Solution output** is labelled **Captured** (real pyATS output) or **Expected** (not yet run).
- **Git identity:** `xevnan-git <348862922+xevnan-git@users.noreply.github.com>`. GitHub rejects the Gmail address.

## Workflow per lab
1. The user names a topic. Design the topology and Guide; show a brief plan.
2. Write a builder in `tools/builders/` that generates the clean, final and faulted configs plus both YAMLs.
3. Test in ≤ 5-node `[TEST]` chunks with pyATS: build working → verify → inject faults → confirm the symptoms → apply the fixes → re-verify.
4. Run `uv run tools/sync_notes.py` and `uv run tools/validate.py`. Import-check each YAML via CML `POST /api/v0/import` from the VM.
5. Update the backlog and README index, commit, push, and refresh the CML repo (`PUT /api/v0/lab_repos/refresh`).

## Avoid
- **Shared-server safety:**
  - Never touch CML labs without a project tag (`[LEARN]`/`[TSHOOT]`/`[TEST]`/legacy `[LAB]`). Three untagged admin labs on the server belong to the user.
  - Ask before stopping, wiping or deleting any lab, except `[TEST]` labs you created, which have a standing OK.
  - Never change CML server settings, users, licensing or images.
- **Secrets:** never commit credentials, IPs or SSH details (`.env` is git-ignored). Don't put the CML password in command lines.
- **Annotation format:** in committed YAML, annotation `border_style` must be `''`, `'2,2'` or `'4,2'`. The MCP tool wants `solid`/`dotted`/`dashed` instead, and the wrong form makes CML silently drop the lab ("Invalid topology file").
- **IOL config order:** in IOL startup configs, anything that references an interface (e.g. `route-map … match interface`) must come *after* that interface.
- **Hints in CML:** don't put hints or solutions in a troubleshooting Guide or the CML notes.
- **Timeouts:** the first pyATS command to a freshly booted node can time out. Retry once.
- **Platform traps (detail in `CLAUDE.md`):** IOL-L2 has `ip routing` on by default (L2-only switches need
  `no ip routing` or `ip default-gateway` is ignored); IOL-XE routers can't do EtherChannel; IOL-L2 has no
  `min-links` and drops `lacp max-bundle`; pyATS turns off console logging when it connects (labs are fine).
- **BGP traps (found building 3.2.c):** `network 192.168.10.0 mask 255.255.0.0` is *rejected* (host bits set);
  use a valid-but-unmatched prefix for a "not advertised" fault. After boot, BGP holds paths without `>` for up to
  ~2 min while a neighbor never comes up (read-only mode). `show ip bgp <pfx> best-path-reason` works on IOL-XE
  17.18. Policy changes need `clear ip bgp … soft in|out`, and the result lags the command by a few seconds.
- **pyATS on Alpine:** run `traceroute -n -q 1 -w 1` (and `ping -W 1`); default timeouts can exceed the tool call's.
- **Unverified claims:** test every fault's symptom live before writing it up. If a fault behaves
  non-deterministically (e.g. LACP picking a link by race), replace it.

## Open items
- Full runs of every lab on the 20-node server. As of 2026-11-01 the user hasn't run any yet ("the briefs look
  good"); they'll give feedback on the Guide format once they do. No need to ask every session.
- 3.2.c YAMLs: CML import check (`POST /api/v0/import` from the VM) and Lab Repository refresh not yet run. The
  local Windows checkout has no `.env`, so do it from the VM or ask the user.
- `tools/cml_teardown_lab.py`: the user will add it. Restrict it to project-tagged labs and `.env`.
- Unverified: whether `external_connector` counts against the license. Recheck now and then whether an ENARSI v1.2 blueprint exists.

## Very next step
Build **ENCOR 5.2 infrastructure security: ACLs and CoPP**, the user's pick (2026-11-01). It jumps ahead of
3.2.a / 4.x / 5.1. It's **three topics, each with a learn lab and a ts lab, so 6 labs**, split the way 3.1.a / 3.1.b /
3.1.a-b were (but this time with learn labs too):

| Topic | Learn | TS (faults) | Folder |
|---|---|---|---|
| 5.2.a ACLs | `[LEARN] ENCOR 5.2.a ACLs` | `[TSHOOT] ENCOR 5.2.a ACLs` (5) | `labs/encor/5-security/infra-security/learn-acl`, `ts-acl` |
| 5.2.b CoPP | `[LEARN] ENCOR 5.2.b CoPP` | `[TSHOOT] ENCOR 5.2.b CoPP` (5) | `…/infra-security/learn-copp`, `ts-copp` |
| 5.2.a-b combined | `[LEARN] ENCOR 5.2.a-b ACLs and CoPP` | `[TSHOOT] ENCOR 5.2.a-b ACLs and CoPP` (4) | `…/infra-security/learn-acl-copp`, `ts-acl-copp` |

Titles and folder names are a proposal. Confirm them with the user along with the plan. File names follow the
convention, e.g. `encor-5.2.a-infra-security-learn-acl.yaml` and `encor-5.2.ab-infra-security-ts-acl-copp.yaml`
(matching `encor-3.1.ab-…`). Probably one builder per topic, or one shared builder like
`encor_3_1_ab_trunk_etherchannel.py`.

Scope:
- **Exam depth:** the backlog maps ENCOR 5.2.a → **ENARSI 3.2.a** (standard, extended, named, *time-based* ACLs)
  and 5.2.b → **ENARSI 3.3** (CoPP for Telnet, SSH, HTTP(S), SNMP, EIGRP, OSPF, BGP). Build to ENARSI depth so the
  labs cover both exams, then update both blueprint rows.
- **ACL ideas:** standard vs extended placement, wildcard masks, implicit deny (and the routing protocol it kills),
  named ACL sequence-number edits, `access-class` on vty, `established`, time-range, hit counters / `log`.
- **CoPP ideas:** class-maps by ACL for management (SSH/Telnet), routing (OSPF/BGP) and ICMP;
  `police` per class; `class-default`; verify with `show policy-map control-plane` counters; show a routing
  protocol dying when its class is policed too hard or left out of a permit.
- **Combined:** an edge router with interface ACLs *and* CoPP, where an ACL change and a CoPP class interact, for
  example traffic permitted by the interface ACL but dropped by CoPP.
- **Platform checks first:**
  - Confirm on IOL-XE 17.18 that `control-plane` / `service-policy input` is accepted and that the CoPP counters
    actually increment. If it doesn't work, try `iosv` and say why in the README.
  - Check what the Alpine image has for test traffic (ssh/telnet/curl clients). Use `ubuntu` SRV nodes for
    SNMP/HTTP servers only if needed.
  - IOL-XE time-range needs a clock. Check that `show clock` and `periodic` behave without NTP.
- **Size:** keep each topology at 5 or fewer licensed nodes if possible, so it tests in one pass.

Follow the workflow above: show the user the plan (topologies, Guide steps, fault lists) before building.
