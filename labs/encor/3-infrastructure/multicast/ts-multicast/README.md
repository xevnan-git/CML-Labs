# Multicast (PIM-SM, IGMP, SSM) — Troubleshooting Lab

> **Blueprint:** ENCOR 3.3.d — Describe multicast protocols, such as RPF check, PIM SM, IGMP v2/v3, SSM, bidir,
> and MSDP
> **Mode:** Troubleshooting · **Nodes:** 5 licensed (3 routers, 2 IOL hosts) · **Faults:** 5 · **Difficulty:** 3 of 3

<!--
This README is copied verbatim into the lab's CML Notes. It must NOT reveal the faults: no hints, no root cause.
Hints and the solution live only in solution/README.md in the repo.
Order: scenario first (ticket, goal, design), reference material (access, topology, addressing) at the bottom.
-->

## Ticket

> **#6517 — Receiver gets no multicast at all**
> "The multicast rollout for the LAN20 receivers is 'done', but PC1 gets nothing from the source SRV1: not the
> company feed on 239.1.1.1, not the SSM feed on 232.1.1.1, not the collaboration group on 239.2.2.2. Unicast
> between them works fine. The project notes are below. Please get all three working."

## Done when
1. On **SRV1**, each of these gets replies from **192.168.20.10**:
   `ping 239.1.1.1 repeat 3`, `ping 232.1.1.1 repeat 3`, `ping 239.2.2.2 repeat 3`.
2. **R3** `show ip igmp groups` lists 239.1.1.1, 232.1.1.1 and 239.2.2.2 on Ethernet0/0.
3. **R3** `show ip mroute 232.1.1.1` shows an (S,G) with flags **sTI** and no (\*,G); `show ip mroute 239.1.1.1`
   shows the (S,G) arriving on Ethernet0/1 (from R1) after SRV1 has sent.
4. All of R1, R2 and R3 show the same RP mapping (`show ip pim rp mapping`) and each sees both other routers as
   PIM neighbors.
5. **R1** `show ip msdp sa-cache` lists (192.168.10.10, 239.1.1.1) after SRV1 has sent to 239.1.1.1.

## Rules
- **Change only R1, R2 and R3.** SRV1 and PC1 are configured correctly; run `show` commands and pings on them.
- Keep the design below: same RPs, group ranges, protocols and IGMP version. Don't fix things with static mroutes:
  every link is meant to run PIM.
- There's more than one fault, and fixing one may reveal the next.
- Multicast state builds from traffic and periodic messages: after a change, wait a few seconds and ping again
  before you conclude it didn't help. IGMP changes can take a couple of minutes to settle.
- Hints and the full solution are in the lab repository (`solution/README.md` in this lab's folder), not in CML.

## Intended design
**Unicast (working, unchanged):** OSPF area 0 on every interface of R1, R2 and R3; the LANs are passive.

**On R1, R2 and R3:**
- `ip multicast-routing`, and `ip pim sparse-mode` on **every** interface, Loopback0 included.
- **ASM:** one static RP for every group (224.0.0.0/4) outside the ranges below: **R2, 10.255.255.2**.
- **Bidir:** 239.2.0.0/16 (ACL `BIDIR-GROUPS`) uses **R1, 10.255.255.1** as a bidir RP (`ip pim bidir-enable`).
- **SSM:** the default range 232.0.0.0/8 (`ip pim ssm default`).
- **R3's LAN (Ethernet0/0) runs IGMPv3** so receivers can make source-specific joins.
- **MSDP:** R1 and R2 are peers over their Loopback0 addresses.

**Receiver (PC1, configured correctly):** IGMPv3 on Ethernet0/0, joined to 239.1.1.1, 239.2.2.2 and
232.1.1.1 source 192.168.10.10.

**Source (SRV1):** sends with `ping <group>`; its default route points at R1.

## Expected behavior
- PC1 answers SRV1's pings to all three groups.
- 239.1.1.1 starts on the shared tree through R2 and then switches to the shortest path R1 → R3.
- 232.1.1.1 needs no RP: R3 joins R1 directly as soon as PC1 reports.
- 239.2.2.2 has a single (\*,G) tree rooted at R1 and no (S,G) state.

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1, R2, R3 | IOL-XE routers (the ones you fix) | cisco | cisco | cisco |
| SRV1 | IOL-XE acting as the multicast source (look, don't change) | cisco | cisco | cisco |
| PC1 | IOL-XE acting as the receiver (look, don't change) | cisco | cisco | cisco |

Open a console from the node in CML (right-click → Console). Routers start in privileged EXEC.
Each node also has a label in the CML canvas with its login and addresses.

SRV1 and PC1 are routers acting as hosts: a router answers a ping to a group it has joined, so SRV1's ping output
shows exactly which receivers got each packet.

## Topology

```
                         R2  (RP for ASM groups)
                         Lo0 10.255.255.2
               e0/0 /                    \ e0/1
         10.1.2.0/24                      10.2.3.0/24
             e0/1 /                          \ e0/2
          R1  ---------------------------------  R3
   Lo0 10.255.255.1  e0/2   10.1.3.0/24    e0/1  Lo0 10.255.255.3
   (first hop, bidir RP)                         (last hop)
         | e0/0 192.168.10.1                      | e0/0 192.168.20.1
         |  LAN10 192.168.10.0/24                 |  LAN20 192.168.20.0/24
         | e0/0 192.168.10.10                     | e0/0 192.168.20.10
        SRV1 (source)                            PC1 (receiver)
```

## Addressing (as designed)

| Node | Interface | IPv4 | Connects to |
|---|---|---|---|
| R1 | Loopback0 | 10.255.255.1/32 | — (bidir RP) |
| R1 | Ethernet0/0 | 192.168.10.1/24 | SRV1 (LAN10) |
| R1 | Ethernet0/1 | 10.1.2.1/24 | R2 e0/0 |
| R1 | Ethernet0/2 | 10.1.3.1/24 | R3 e0/1 |
| R2 | Loopback0 | 10.255.255.2/32 | — (ASM RP) |
| R2 | Ethernet0/0 | 10.1.2.2/24 | R1 e0/1 |
| R2 | Ethernet0/1 | 10.2.3.2/24 | R3 e0/2 |
| R3 | Loopback0 | 10.255.255.3/32 | — |
| R3 | Ethernet0/0 | 192.168.20.1/24 | PC1 (LAN20) |
| R3 | Ethernet0/1 | 10.1.3.3/24 | R1 e0/2 |
| R3 | Ethernet0/2 | 10.2.3.3/24 | R2 e0/1 |
| SRV1 | Ethernet0/0 | 192.168.10.10/24, default route → .1 | R1 |
| PC1 | Ethernet0/0 | 192.168.20.10/24, default route → .1 | R3 |

| Group | Mode | RP |
|---|---|---|
| 239.1.1.1 | ASM (PIM sparse mode) | R2, 10.255.255.2 |
| 232.1.1.1, source 192.168.10.10 | SSM | none |
| 239.2.2.2 (239.2.0.0/16) | bidir | R1, 10.255.255.1 |
