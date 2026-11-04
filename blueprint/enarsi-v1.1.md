# ENARSI 300-410 v1.1 — backlog

Source: Cisco, *Implementing Cisco Enterprise Advanced Routing and Services v1.1 (300-410)* exam topics (2023).
Legend: see [README](README.md).

## 1.0 Layer 3 Technologies (35%) — `labs/enarsi/1-layer3/`

| ID | Topic | Plan | Status | Lab(s) | Notes |
|---|---|---|---|---|---|
| 1.1 | Administrative distance (all routing protocols) | learn + ts | backlog | | |
| 1.2 | Route maps (attributes, tagging, filtering) | learn + ts | backlog | | |
| 1.3 | Loop prevention (filtering, tagging, split horizon, route poisoning) | ts | backlog | | Pairs with 1.4 redistribution loops |
| 1.4 | Redistribution between any protocols or sources | learn + ts | backlog | | Two-point mutual redistribution |
| 1.5 | Manual and auto summarization (any protocol) | learn + ts | backlog | | |
| 1.6 | Policy-based routing | learn + ts | backlog | | Also covers ENCOR 3.2.d |
| 1.7 | VRF-Lite | learn + ts | backlog | | Builds on ENCOR 2.2.a |
| 1.8 | Bidirectional Forwarding Detection | learn | backlog | | With OSPF/BGP failover timing |
| 1.9.a | EIGRP address families (IPv4/IPv6), classic and named mode, VRF and global | learn | backlog | | |
| 1.9.b | EIGRP neighbor relationships and authentication | ts | backlog | | |
| 1.9.c | EIGRP loop-free paths: RD, FD, FC, successor, FS, stuck in active | learn + ts | backlog | | |
| 1.9.d | EIGRP stubs | learn + ts | backlog | | Hub-and-spoke, SIA avoidance |
| 1.9.e | EIGRP load balancing (equal and unequal cost / variance) | learn | backlog | | |
| 1.9.f | EIGRP metrics (classic vs wide) | learn | backlog | | Folded into 1.9.c/e |
| 1.10.a | OSPF address families (OSPFv2, OSPFv3 IPv4/IPv6 AF) | learn | backlog | | |
| 1.10.b | OSPF neighbor relationships and authentication | ts | backlog | | Area/MTU/passive faults covered by ENCOR 3.2.b ts-multiarea-adjacency; still needs auth, timers, network-type faults |
| 1.10.c.i | OSPF network types: point-to-point, multipoint, broadcast, NBMA | learn + ts | backlog | | |
| 1.10.c.ii | OSPF area types: backbone, normal, transit, stub, NSSA, totally stubby | learn + ts | backlog | | |
| 1.10.c.iii | OSPF router types: internal, backbone, ABR, ASBR | → 1.10.c.ii | backlog | | |
| 1.10.c.iv | OSPF virtual link | learn + ts | backlog | | |
| 1.10.d | OSPF path preference (intra > inter > E1 > E2, cost) | learn + ts | backlog | | |
| 1.11.a | BGP address families (IPv4, IPv6) | learn | backlog | | |
| 1.11.b | BGP neighbors: next-hop, multihop, 4-byte AS, private AS, route refresh, peer groups, states, timers | ts | backlog | | |
| 1.11.c | BGP path preference (attributes and best path) | learn + ts | backlog | | |
| 1.11.d | BGP route reflector (single RR) | learn + ts | backlog | | |
| 1.11.e | BGP policies (in/out filtering, path manipulation) | learn + ts | backlog | | |

## 2.0 VPN Technologies (20%) — `labs/enarsi/2-vpn/`

| ID | Topic | Plan | Status | Lab(s) | Notes |
|---|---|---|---|---|---|
| 2.1 | MPLS operations (LSR, LDP, label switching, LSP) | learn | backlog | | IOL-XE; walk the label stack hop by hop |
| 2.2 | MPLS Layer 3 VPN | learn | backlog | | PE/P/CE with VRFs and MP-BGP VPNv4 |
| 2.3 | DMVPN single hub: GRE/mGRE, NHRP, IPsec, dynamic neighbors, spoke-to-spoke | learn + ts | backlog | | Phase 2 and 3 |

## 3.0 Infrastructure Security (20%) — `labs/enarsi/3-infra-security/`

| ID | Topic | Plan | Status | Lab(s) | Notes |
|---|---|---|---|---|---|
| 3.1 | IOS AAA (TACACS+, RADIUS, local) | learn + ts | backlog | | Ubuntu SRV running tac_plus + FreeRADIUS (no Docker images); also ENCOR 5.1.b |
| 3.2.a | IPv4 ACLs (standard, extended, time-based) | learn + ts | done (dev-tested) | [learn-acl](../labs/encor/5-security/infra-security/learn-acl/), [ts-acl](../labs/encor/5-security/infra-security/ts-acl/) | Shared with ENCOR 5.2.a |
| 3.2.b | IPv6 traffic filter | learn + ts | backlog | | |
| 3.2.c | Unicast RPF | learn + ts | backlog | | |
| 3.3 | CoPP (Telnet, SSH, HTTP(S), SNMP, EIGRP, OSPF, BGP) | learn + ts | done (dev-tested) | [learn-copp](../labs/encor/5-security/infra-security/learn-copp/), [ts-copp](../labs/encor/5-security/infra-security/ts-copp/) | Shared with ENCOR 5.2.b; SNMP/HTTP classified but not exercised (no client / IOL HTTP refuses) |
| 3.4 | IPv6 First Hop Security (RA guard, DHCP guard, binding table, ND inspection, source guard) | learn | backlog | | verify on IOL-L2-XE |

## 4.0 Infrastructure Services (25%) — `labs/enarsi/4-infra-services/`

| ID | Topic | Plan | Status | Lab(s) | Notes |
|---|---|---|---|---|---|
| 4.1 | Device management: console, VTY, Telnet, HTTP(S), SSH, SCP, (T)FTP | ts | backlog | | |
| 4.2 | SNMP v2c and v3 | learn + ts | backlog | | Ubuntu SRV with net-snmp tools |
| 4.3 | Logging: local, syslog, debugs, conditional debugs, timestamps | learn + ts | backlog | | Also ENCOR 4.1 |
| 4.4 | IPv4/IPv6 DHCP: client, IOS server, relay, options | learn + ts | backlog | | |
| 4.5 | IP SLA: jitter, tracking objects, delay, connectivity | learn + ts | backlog | | Also ENCOR 4.4 |
| 4.6 | NetFlow v5, v9, Flexible NetFlow | learn + ts | backlog | | Also ENCOR 4.2; collector on Ubuntu SRV; verify FNF on IOL-XE |
| 4.7 | Catalyst Center assurance | N/A here | — | | No Catalyst Center |
