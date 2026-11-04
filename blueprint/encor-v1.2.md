# ENCOR 350-401 v1.2 — backlog

Source: Cisco, *Implementing Cisco Enterprise Network Core Technologies v1.2 (350-401)* exam topics (2025).
Legend: see [README](README.md).

## 1.0 Architecture (15%) — `labs/encor/1-architecture/`

| ID | Topic | Plan | Status | Lab(s) | Notes |
|---|---|---|---|---|---|
| 1.1.a | Enterprise design: 2-tier, 3-tier, fabric, cloud | concept | backlog | | |
| 1.1.b | High availability: redundancy, FHRP, SSO | → 3.3.c | backlog | | SSO is concept-only (no dual-RP platform) |
| 1.2.a | Catalyst SD-WAN control and data plane elements | N/A here | — | | No SD-WAN images |
| 1.2.b | Catalyst SD-WAN benefits and limitations | concept | backlog | | |
| 1.3.a | SD-Access control and data plane elements | concept | backlog | | LISP/VXLAN pieces via 2.3 |
| 1.3.b | Traditional campus interoperating with SD-Access | concept | backlog | | |
| 1.4 | Interpret QoS configurations (MQC classify/mark/police/shape/queue) | learn + ts | backlog | | verify MQC on IOL-XE |

## 2.0 Virtualization (10%) — `labs/encor/2-virtualization/`

| ID | Topic | Plan | Status | Lab(s) | Notes |
|---|---|---|---|---|---|
| 2.1.a–c | Hypervisor type 1/2, VMs, virtual switching | concept | backlog | | CML itself is a good worked example |
| 2.2.a | VRF | learn + ts | backlog | | Pairs with ENARSI 1.7 VRF-Lite |
| 2.2.b | GRE and IPsec tunneling | learn + ts | backlog | | GRE, GRE over IPsec, VTI |
| 2.3.a | LISP | learn | backlog | | verify LISP on IOL-XE |
| 2.3.b | VXLAN | learn | backlog | | verify; static flood-and-learn VXLAN on IOL-XE, else concept |

## 3.0 Infrastructure (30%) — `labs/encor/3-infrastructure/`

| ID | Topic | Plan | Status | Lab(s) | Notes |
|---|---|---|---|---|---|
| 3.1.a | Static and dynamic 802.1Q trunking (DTP) | ts + ts (combined with 3.1.b) | done (dev-tested) | [ts-trunking](../labs/encor/3-infrastructure/switching/ts-trunking/), [ts-trunk-etherchannel](../labs/encor/3-infrastructure/switching/ts-trunk-etherchannel/) | IOL-L2-XE. Learn lab skipped at user's request |
| 3.1.b | Static and dynamic EtherChannels (LACP, PAgP) | ts + ts (combined with 3.1.a) | done (dev-tested) | [ts-etherchannel](../labs/encor/3-infrastructure/switching/ts-etherchannel/), [ts-trunk-etherchannel](../labs/encor/3-infrastructure/switching/ts-trunk-etherchannel/) | PAgP works on IOL-L2 (no `show pagp`; use `show etherchannel`). No `min-links`; `lacp max-bundle` silently ignored. IOL-XE routers can't bundle, so the L3 Po uses an L3 switch. Learn lab skipped |
| 3.1.c | RSTP, MST, root guard, BPDU guard | learn + ts | done (dev-tested) | [learn-stp](../labs/encor/3-infrastructure/switching/learn-stp/), [ts-mst-guards](../labs/encor/3-infrastructure/switching/ts-mst-guards/) | IOL-L2 defaults to rapid-pvst. TS: PC1↔PC2 end to end needs 6 nodes |
| 3.2.a | EIGRP vs OSPF concepts (DV vs LS, LB, path selection, metrics, areas) | learn | done (dev-tested) | [learn-eigrp-vs-ospf](../labs/encor/3-infrastructure/eigrp-ospf/learn-eigrp-vs-ospf/) | 5 nodes, tested whole; both protocols on one square topology. No TS lab (describe-level topic) |
| 3.2.b | OSPFv2/v3 multi-area, summarization, filtering, network types, passive | learn + ts | done (dev-tested) | [learn-multiarea](../labs/encor/3-infrastructure/ospf/learn-multiarea/), [ts-multiarea-adjacency](../labs/encor/3-infrastructure/ospf/ts-multiarea-adjacency/) | OSPFv2 only; OSPFv3 → ENARSI 1.10.a. Needs full 8-node run on 20-node server |
| 3.2.c | eBGP between directly connected neighbors, best path, neighbor states | learn + ts | done (dev-tested) | [learn-ebgp](../labs/encor/3-infrastructure/bgp/learn-ebgp/), [ts-ebgp](../labs/encor/3-infrastructure/bgp/ts-ebgp/) | 6 nodes; PC1↔PC2 end-to-end needs the 20-node server |
| 3.2.d | Policy-based routing | → ENARSI 1.6 | backlog | | |
| 3.3.a | NTP and PTP configurations | learn + ts | backlog | | PTP concept-only |
| 3.3.b | NAT/PAT | learn + ts | backlog | | |
| 3.3.c | FHRP: HSRP, VRRP | learn + ts | backlog | | Also covers 1.1.b |
| 3.3.d | Multicast: RPF, PIM-SM, IGMPv2/v3, SSM, bidir, MSDP | learn | backlog | | verify bidir/MSDP on IOL-XE |

## 4.0 Network Assurance (10%) — `labs/encor/4-network-assurance/`

| ID | Topic | Plan | Status | Lab(s) | Notes |
|---|---|---|---|---|---|
| 4.1 | Diagnose with debugs, conditional debugs, traceroute, ping, SNMP, syslog | ts | backlog | | Ubuntu SRV as syslog/SNMP manager; pairs with ENARSI 4.2/4.3 |
| 4.2 | Flexible NetFlow | → ENARSI 4.6 | backlog | | |
| 4.3 | SPAN, RSPAN, ERSPAN | learn | backlog | | verify RSPAN on IOL-L2, ERSPAN on IOL-XE |
| 4.4 | IP SLA | → ENARSI 4.5 | backlog | | |
| 4.5 | Catalyst Center configuration, monitoring, AI workflows | N/A here | — | | No Catalyst Center |
| 4.6 | NETCONF and RESTCONF | learn + ts | backlog | | verify netconf-yang/restconf on IOL-XE; Ubuntu SRV as client |

## 5.0 Security (20%) — `labs/encor/5-security/`

| ID | Topic | Plan | Status | Lab(s) | Notes |
|---|---|---|---|---|---|
| 5.1.a | Lines and local user authentication | learn + ts | backlog | | |
| 5.1.b | Authentication and authorization using AAA | → ENARSI 3.1 | backlog | | |
| 5.2.a | ACLs | learn + ts (+ combined 5.2.a-b) | done (dev-tested), combined pair done | [learn-acl](../labs/encor/5-security/infra-security/learn-acl/), [ts-acl](../labs/encor/5-security/infra-security/ts-acl/), combined [learn-acl-copp](../labs/encor/5-security/infra-security/learn-acl-copp/), [ts-acl-copp](../labs/encor/5-security/infra-security/ts-acl-copp/) | 5 nodes, tested whole; built to ENARSI 3.2.a depth (standard, extended, named, time-based) |
| 5.2.b | CoPP | learn + ts (+ combined 5.2.a-b) | done (dev-tested), combined pair done | [learn-copp](../labs/encor/5-security/infra-security/learn-copp/), [ts-copp](../labs/encor/5-security/infra-security/ts-copp/), combined [learn-acl-copp](../labs/encor/5-security/infra-security/learn-acl-copp/), [ts-acl-copp](../labs/encor/5-security/infra-security/ts-acl-copp/) | 5 nodes, tested whole; built to ENARSI 3.3 depth (SNMP classified, not exercised: no client) |
| 5.3 | REST API security | concept | backlog | | Demo on the 4.6 lab (HTTPS, auth headers) |
| 5.4.a–d | Threat defense, endpoint security, NGFW, TrustSec/MACsec | concept | backlog | | |

## 6.0 Automation and AI (15%) — `labs/encor/6-automation/`

| ID | Topic | Plan | Status | Lab(s) | Notes |
|---|---|---|---|---|---|
| 6.1 | Interpret basic Python components and scripts | learn | backlog | | Python on Ubuntu SRV against lab routers |
| 6.2 | Construct valid JSON-encoded files | learn | backlog | | Folded into the 6.1 or 4.6 lab |
| 6.3 | Data modeling language principles (YANG) | → 4.6 | backlog | | |
| 6.4 | Catalyst Center and SD-WAN Manager APIs | N/A here | — | | Concept note only |
| 6.5 | REST API response codes and payloads (RESTCONF) | → 4.6 | backlog | | |
| 6.6 | EEM applets | learn + ts | backlog | | |
| 6.7 | Agent vs agentless orchestration tools | concept | backlog | | |
