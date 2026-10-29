# OSPFv2 Multi-Area — Troubleshooting Lab

> **Blueprint:** ENCOR 3.2.b — Configure simple OSPFv2/v3 environments (neighbor adjacency, point-to-point and
> broadcast network types, passive-interface); also ENARSI 1.10.b — Troubleshoot OSPF neighbor relationships
> **Mode:** Troubleshooting · **Nodes:** 8 licensed + 1 unmanaged switch · **Faults:** 3 · **Difficulty:** 2 of 3

## Ticket

> **#4417 — Site B can't reach Site A after last night's change**
> "Last night's change window 'standardized the OSPF configs' on several routers. Since then, users at Site B
> (PC2, 192.168.20.10) can't reach anything at Site A (PC1, 192.168.10.10), not even the Site A server LANs
> (172.20.x.x). The change engineer says every router 'has OSPF configured and the interfaces are up'.
> The core (R1/R2/R3 segment) looks fine."

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1–R6 | IOL-XE router | cisco | cisco | cisco |
| PC1, PC2 | Alpine Linux | cisco | cisco | `sudo -i` |
| SW0 | Unmanaged switch | — | — | — |

Open a console from the node in CML (right-click → **Console**). Routers drop you straight into privileged EXEC.
Each node also has a label on the CML canvas with its login and addresses.

## Topology

```
                         203.0.113.0/24 (R3 Lo1, "external")
                                    |
                                   R3  ASBR
                                    | e0/0 .3
                             +------+------+
     AREA 1                  |     SW0     |   10.0.1.0/24  AREA 0          AREA 2
                             +--+-------+--+
                          .1 |  e0/0    e0/0 | .2
 PC1 ---- R4 ------------- R1               R2 ------------- R5 ------------- R6 ---- PC2
   .10  e0/1  e0/0      e0/1  ABR         ABR  e0/1      e0/0  e0/1      e0/0  e0/1    .10
  192.168.10.0/24  10.1.4.0/24                      10.2.5.0/24      10.5.6.0/24   192.168.20.0/24
     R4 Lo1-Lo4: 172.20.0.0/24 - 172.20.3.0/24
          SITE A                                                                 SITE B
```

## Addressing (as designed)

| Node | Interface | IPv4 | Connects to | OSPF area |
|---|---|---|---|---|
| R1 | Loopback0 | 10.255.255.1/32 | — | 0 |
| R1 | Ethernet0/0 | 10.0.1.1/24 | SW0 (R2, R3) | 0 |
| R1 | Ethernet0/1 | 10.1.4.1/24 | R4 e0/0 | 1 |
| R2 | Loopback0 | 10.255.255.2/32 | — | 0 |
| R2 | Ethernet0/0 | 10.0.1.2/24 | SW0 (R1, R3) | 0 |
| R2 | Ethernet0/1 | 10.2.5.2/24 | R5 e0/0 | 2 |
| R3 | Loopback0 | 10.255.255.3/32 | — | 0 |
| R3 | Loopback1 | 203.0.113.1/24 | — (redistributed) | — |
| R3 | Ethernet0/0 | 10.0.1.3/24 | SW0 (R1, R2) | 0 |
| R4 | Loopback0 | 10.255.255.4/32 | — | 1 |
| R4 | Loopback1–4 | 172.20.0.1/24 … 172.20.3.1/24 | — (Site A server LANs) | 1 |
| R4 | Ethernet0/0 | 10.1.4.4/24 | R1 e0/1 | 1 |
| R4 | Ethernet0/1 | 192.168.10.1/24 | PC1 | 1 (passive) |
| R5 | Loopback0 | 10.255.255.5/32 | — | 2 |
| R5 | Ethernet0/0 | 10.2.5.5/24 | R2 e0/1 | 2 |
| R5 | Ethernet0/1 | 10.5.6.5/24 | R6 e0/0 | 2 |
| R6 | Loopback0 | 10.255.255.6/32 | — | 2 |
| R6 | Ethernet0/0 | 10.5.6.6/24 | R5 e0/1 | 2 |
| R6 | Ethernet0/1 | 192.168.20.1/24 | PC2 | 2 (passive) |
| PC1 | eth0 | 192.168.10.10/24, gw .1 | R4 e0/1 | — |
| PC2 | eth0 | 192.168.20.10/24, gw .1 | R6 e0/1 | — |

## Intended design
- OSPF process 1 everywhere, enabled per interface (`ip ospf 1 area N`). Router IDs = Loopback0.
- **Area 0:** the SW0 broadcast segment plus R1/R2/R3 loopbacks. R3 is the DR (priority 255), R2 the BDR (priority 100),
  and R1 never takes either role (priority 0).
- **Area 1:** R1–R4 link, R4 loopbacks, PC1 LAN. **Area 2:** R2–R5 and R5–R6 links, R5/R6 loopbacks, PC2 LAN.
- All router-to-router Ethernet links use OSPF network type **point-to-point**.
- The PC LANs (R4 e0/1, R6 e0/1) are **passive**: advertised, but no hellos sent.
- R1 summarizes area 1's server LANs as **172.20.0.0/22**. R2 filters R4's loopback (10.255.255.4/32) out of area 2.
- R3 redistributes 203.0.113.0/24 as an external (E2) route.

## Expected behavior (healthy network)
- `show ip ospf neighbor` shows **FULL** on every router-to-router link:
  R1↔R4, R2↔R5, R5↔R6 as `FULL/  -`, and on the segment R3 = `FULL/DR`, R2 = `FULL/BDR`, R1 = `DROTHER`.
- R6's routing table contains `O IA 172.20.0.0/22`, `O IA 192.168.10.0/24` and `O E2 203.0.113.0/24`, and
  **does not** contain 10.255.255.4/32.
- R4's routing table contains `O IA 192.168.20.0/24` and `O E2 203.0.113.0/24`.

## Done when
- `PC2:~$ ping -c 3 192.168.10.10` succeeds, and `PC1:~$ ping -c 3 192.168.20.10` succeeds.
- `R6# ping 172.20.3.1` succeeds.
- Every router-to-router adjacency listed above is FULL.
- R6 still has **no** route to 10.255.255.4/32 (the filter is intended — don't remove it).

## Rules
- Fix with the smallest change that restores the intended design; don't redesign.
- There's more than one fault, and fixing one may reveal the next.
- Hints and the full solution are in the lab repository (`solution/README.md` in this lab's folder), not in CML.
