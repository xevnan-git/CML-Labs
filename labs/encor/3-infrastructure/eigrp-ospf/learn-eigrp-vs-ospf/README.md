# EIGRP vs OSPF, Side by Side — Learning Lab

> **Blueprint:** ENCOR 3.2.a — Compare routing concepts of EIGRP and OSPF (advanced distance vector vs link
> state, load balancing, path selection, path operations, metrics, and area types)
> **Mode:** Learning (guided build) · **Nodes:** 5 licensed (4 routers, 1 host) · **Time:** ~60 min

<!--
This README is copied verbatim into the lab's CML Notes (tools/sync_notes.py), so it must read well inside CML:
plain Markdown, ASCII diagrams (no Mermaid), no links to solution files.
Order: objectives and steps first; lab access, topology and addressing in the Reference section at the bottom.
-->

## What you'll learn
- Run OSPF and EIGRP on the **same** four routers and compare what each one knows and how it decides.
- Link state vs advanced distance vector: OSPF's LSDB (every router's links) vs EIGRP's topology table (what each
  neighbor reports).
- Metrics: OSPF cost from bandwidth only, EIGRP's composite of bandwidth and delay.
- Why EIGRP wins the routing table when both run (administrative distance), and the one rule that beats AD.
- EIGRP's feasible successor: a pre-computed backup that takes over without asking anyone.
- Load balancing: equal-cost in both, unequal-cost (`variance`) only in EIGRP.
- Summarization: anywhere in EIGRP, only at area borders in OSPF.

## Starting point
Logins, the topology diagram and the addressing table are in **Reference** at the end of this guide.

Every interface already has its address, and nothing is routed yet. The four routers form a square: R1 can reach
R4 via R2 or via R3. R4's Loopback1–4 (172.20.0.0/24 – 172.20.3.0/24) stand in for a remote site's LANs. PC1 is
on R1's LAN for end-to-end tests.

Wait about a minute after starting the lab, until the routers finish booting.

## Step 1 — Baseline: no routing
**R1**
```
show ip interface brief | exclude unassigned
show ip route | begin Gateway
ping 172.20.0.1 repeat 2
```
**Output (captured, trimmed)**
```
Interface              IP-Address      OK? Method Status                Protocol
Ethernet0/0            10.1.2.1        YES TFTP   up                    up
Ethernet0/1            10.1.3.1        YES TFTP   up                    up
Ethernet0/2            192.168.10.1    YES TFTP   up                    up
Loopback0              10.255.255.1    YES TFTP   up                    up

Gateway of last resort is not set
C        10.1.2.0/24 is directly connected, Ethernet0/0
C        10.1.3.0/24 is directly connected, Ethernet0/1
C        10.255.255.1/32 is directly connected, Loopback0
C        192.168.10.0/24 is directly connected, Ethernet0/2

Success rate is 0 percent (0/2)
```
Only connected routes. (*TFTP* is how CML delivered the startup config; it means "from the config file".)

## Step 2 — OSPF: every router gets the whole map
Enable OSPF area 0 on every interface, router by router. This lab uses the per-interface style
(`ip ospf 1 area 0`); EIGRP will use `network` statements, so you see both.

**R1**
```
configure terminal
router ospf 1
 router-id 10.255.255.1
 passive-interface Ethernet0/2
interface Loopback0
 ip ospf 1 area 0
interface Ethernet0/0
 ip ospf 1 area 0
interface Ethernet0/1
 ip ospf 1 area 0
interface Ethernet0/2
 ip ospf 1 area 0
end
```
**R2** and **R3** (use router-id 10.255.255.2 on R2 and 10.255.255.3 on R3)
```
configure terminal
router ospf 1
 router-id 10.255.255.2
interface Loopback0
 ip ospf 1 area 0
interface Ethernet0/0
 ip ospf 1 area 0
interface Ethernet0/1
 ip ospf 1 area 0
end
```
**R4**
```
configure terminal
router ospf 1
 router-id 10.255.255.4
interface Loopback0
 ip ospf 1 area 0
interface range Loopback1 - 4
 ip ospf network point-to-point
 ip ospf 1 area 0
interface Ethernet0/0
 ip ospf 1 area 0
interface Ethernet0/1
 ip ospf 1 area 0
end
```
> `ip ospf network point-to-point` on the loopbacks makes OSPF advertise them as /24s. By default OSPF advertises
> any loopback as a /32 host route.

Wait about 45 seconds (on Ethernet, OSPF waits up to the 40-second dead interval before electing a DR), then:

**R1**
```
show ip ospf neighbor
show ip route ospf | begin Gateway
show ip ospf database router 10.255.255.4
```
**Output (captured, trimmed)**
```
Neighbor ID     Pri   State           Dead Time   Address         Interface
10.255.255.3      1   FULL/DR         00:00:30    10.1.3.3        Ethernet0/1
10.255.255.2      1   FULL/DR         00:00:32    10.1.2.2        Ethernet0/0

O        10.255.255.4/32 [110/21] via 10.1.3.3, 00:00:34, Ethernet0/1
                         [110/21] via 10.1.2.2, 00:00:39, Ethernet0/0
O        172.20.1.0 [110/21] via 10.1.3.3, 00:00:34, Ethernet0/1
                    [110/21] via 10.1.2.2, 00:00:39, Ethernet0/0

  LS Type: Router Links
  Advertising Router: 10.255.255.4
  Number of Links: 7
    Link connected to: a Stub Network
     (Link ID) Network/subnet number: 172.20.1.0
      TOS 0 Metrics: 1
    Link connected to: a Transit Network
     (Link ID) Designated Router address: 10.2.4.4
      TOS 0 Metrics: 10
    ...
```
Look for:
- **Link state:** R1 holds R4's own router LSA, R4's description of every link it has and what each costs. Every
  router in the area has an identical copy and runs SPF (Dijkstra) on it to build its own shortest-path tree.
- **Cost** 21 = 10 (R1's link) + 10 (R2 or R3's link to R4) + 1 (R4's loopback). OSPF cost is
  `reference bandwidth / interface bandwidth`, 100 Mbps / 10 Mbps = 10 for IOL's Ethernet.
- **Equal-cost load balancing:** both paths cost 21, so both are installed (OSPF and EIGRP both default to up to
  4 equal paths, `maximum-paths`).

## Step 3 — Make one path slower
Tell both ends of the R1–R3 link it's a 5 Mbps circuit. `bandwidth` doesn't change the real speed; it's the
number routing protocols (and QoS) use.

**R1**
```
configure terminal
interface Ethernet0/1
 bandwidth 5000
end
```
**R3**
```
configure terminal
interface Ethernet0/0
 bandwidth 5000
end
```
**R1**
```
show ip ospf interface brief
show ip route 172.20.1.0
```
**Output (captured)**
```
Interface    PID   Area            IP Address/Mask    Cost  State Nbrs F/C
Lo0          1     0               10.255.255.1/32    1     LOOP  0/0
Et0/2        1     0               192.168.10.1/24    10    DR    0/0
Et0/1        1     0               10.1.3.1/24        20    BDR   1/1
Et0/0        1     0               10.1.2.1/24        10    BDR   1/1

Routing entry for 172.20.1.0/24
  Known via "ospf 1", distance 110, metric 21, type intra area
  Routing Descriptor Blocks:
  * 10.1.2.2, from 10.255.255.4, 00:01:35 ago, via Ethernet0/0
      Route metric is 21, traffic share count is 1
```
Look for: Et0/1 now costs 20, the R3 path totals 31, and OSPF uses only the R2 path. OSPF can't use a worse path
alongside a better one. It's equal cost or nothing.

> A real network sets `auto-cost reference-bandwidth` (same value on every router) above its fastest link: with
> the default 100 Mbps, a 1 Gbps and a 10 Gbps link both cost 1.

## Step 4 — Add EIGRP on the same routers
EIGRP named mode: one `router eigrp <name>` block holds the address family, per-interface settings
(`af-interface`) and topology settings (`topology base`).

**R1**
```
configure terminal
router eigrp LAB
 address-family ipv4 unicast autonomous-system 100
  eigrp router-id 10.255.255.1
  network 10.0.0.0
  network 192.168.10.0
  af-interface Ethernet0/2
   passive-interface
  exit-af-interface
end
```
**R2** and **R3** (router-id 10.255.255.2 / 10.255.255.3)
```
configure terminal
router eigrp LAB
 address-family ipv4 unicast autonomous-system 100
  eigrp router-id 10.255.255.2
  network 10.0.0.0
end
```
**R4**
```
configure terminal
router eigrp LAB
 address-family ipv4 unicast autonomous-system 100
  eigrp router-id 10.255.255.4
  network 10.0.0.0
  network 172.20.0.0
end
```
EIGRP neighbors come up in seconds (no DR election). Then on **R1**:
```
show eigrp address-family ipv4 neighbors
show ip route | begin Gateway
show ip route 172.20.1.0
show ip ospf rib 172.20.1.0
```
**Output (captured, trimmed)**
```
H   Address                 Interface              Hold Uptime   SRTT   RTO  Q  Seq
1   10.1.3.3                Et0/1                    14 00:00:54    1   100  0  9
0   10.1.2.2                Et0/0                    13 00:01:10    1   100  0  10

D        10.255.255.4/32 [90/1536640] via 10.1.2.2, 00:00:39, Ethernet0/0
D        172.20.1.0 [90/1536640] via 10.1.2.2, 00:00:39, Ethernet0/0
(no O routes left)

Routing entry for 172.20.1.0/24
  Known via "eigrp 100", distance 90, metric 1536640, precedence routine (0), type internal
      Total delay is 2001 microseconds, minimum bandwidth is 10000 Kbit

OSPF local RIB
Codes: * - Best, > - Installed in global RIB
*   172.20.1.0/24, Intra, cost 21, area 0
```
Look for:
- Every OSPF route is gone from the routing table, replaced by `D` (EIGRP). Same prefix, two sources: the lower
  **administrative distance** wins, internal EIGRP 90 vs OSPF 110.
- OSPF hasn't stopped: its local RIB still has the route marked `*` (best) but not `>` (installed). If EIGRP lost
  the route, OSPF's would be installed at once.
- EIGRP's metric is built from the path's **minimum bandwidth** and **total delay**. OSPF only looks at bandwidth.

## Step 5 — The topology table: successor and feasible successor
**R1**
```
show eigrp address-family ipv4 topology 172.20.1.0/24
show ip eigrp topology | section 10.255.255.4
```
**Output (captured, trimmed)**
```
EIGRP-IPv4 VR(LAB) Topology Entry for AS(100)/ID(10.255.255.1) for 172.20.1.0/24
  State is Passive, Query origin flag is 1, 1 Successor(s), FD is 196689920, RIB is 1536640
  Descriptor Blocks:
  10.1.2.2 (Ethernet0/0), from 10.1.2.2, Send flag is 0x0
      Composite metric is (196689920/131153920), route is Internal
        Minimum bandwidth is 10000 Kbit
        Total delay is 2001250000 picoseconds
  10.1.3.3 (Ethernet0/1), from 10.1.3.3, Send flag is 0x0
      Composite metric is (262225920/131153920), route is Internal
        Minimum bandwidth is 5000 Kbit
        Total delay is 2001250000 picoseconds

P 10.255.255.4/32, 1 successors, FD is 196689920
        via 10.1.2.2 (196689920/131153920), Ethernet0/0
        via 10.1.3.3 (262225920/131153920), Ethernet0/1
```
How to read `(196689920/131153920)`: the first number is R1's total metric through that neighbor; the second is
the **reported distance** (RD), the neighbor's own metric to the destination.
- **Successor:** the best path, via R2. Its metric is the **feasible distance** (FD), 196689920.
- **Feasible successor:** a backup whose RD is lower than the FD. R3 reports 131153920 < 196689920, so R3 is
  closer to the destination than R1 is, which proves R3's path can't loop back through R1. EIGRP keeps it ready.
- Named mode uses 64-bit **wide metrics** (delay in picoseconds) so that fast links aren't all equal. The routing
  table can't hold 64-bit numbers, so it shows the metric divided by 128 (`RIB is 1536640`).
- Unlike OSPF, R1 knows nothing about the links *behind* R2 and R3, only the distances they report. That's
  "distance vector": distance plus direction.

## Step 6 — Lose the best path: DUAL in action
Watch EIGRP's decision process (DUAL) while you cut the R2 link.

**R1**
```
debug eigrp fsm
configure terminal
interface Ethernet0/0
 shutdown
end
undebug all
show logging | begin Find FS
show eigrp address-family ipv4 traffic | include Queries|Replies
```
**Output (captured, trimmed)**
```
EIGRP-IPv4(100): Find FS for dest 10.255.255.4/32. FD is 196689920, RD is 196689920 on tid 0
EIGRP-IPv4(100):        10.1.2.2 metric 72057594037927935/72057594037927935
EIGRP-IPv4(100):        10.1.3.3 metric 262225920/131153920 found Dmin is 262225920
DUAL: AS(100) Removing dest 10.255.255.4/32, nexthop 10.1.2.2
DUAL: AS(100) RT installed 10.255.255.4/32 via 10.1.3.3
...
EIGRP-IPv4(100): dest(10.1.2.0/24) active
EIGRP-IPv4(100): rcvreply: 10.1.2.0/24 via 10.1.3.3 metric 393216000/262144000 for tid 0
EIGRP-IPv4(100): reply count is 1
DUAL: AS(100) RT installed 10.1.2.0/24 via 10.1.3.3

  Queries sent/received: 1/0
  Replies sent/received: 0/1
```
Look for two different outcomes in the same second:
- **10.255.255.4/32 had a feasible successor:** *found*, installed via R3 straight away. No packet was sent to
  anyone. (`72057594037927935` is EIGRP's "infinity", the dead path.) The 172.20.x routes also had a feasible
  successor and moved to R3 the same way: `show ip route 172.20.1.0` now shows only 10.1.3.3.
- **10.1.2.0/24** (the R1–R2 link itself) had **no** feasible successor. The route went **active** and R1 sent a
  **query** to its remaining neighbor, waited for the **reply**, then installed the new path. Queries are where
  EIGRP slows down in big networks (and "stuck in active" comes from).

> **Compare OSPF:** an OSPF router floods an LSA about the change, and every router in the area reruns SPF over
> the whole map (`show ip ospf statistics` on R1 shows the run count growing). OSPF doesn't keep backups. It
> recalculates fast enough that it doesn't need them.

Bring the link back:

**R1**
```
configure terminal
interface Ethernet0/0
 no shutdown
end
```

## Step 7 — Unequal-cost load balancing
Use both paths, in proportion to their metrics. `variance 2` installs any feasible successor whose metric is less
than 2 × FD (262225920 < 2 × 196689920).

**R1**
```
configure terminal
router eigrp LAB
 address-family ipv4 unicast autonomous-system 100
  topology base
   variance 2
end
show ip route 172.20.1.0
```
**Output (captured, trimmed)**
```
Routing entry for 172.20.1.0/24
  Known via "eigrp 100", distance 90, metric 1536640, precedence routine (0), type internal
  Routing Descriptor Blocks:
    10.1.3.3, from 10.1.3.3, 00:00:16 ago, via Ethernet0/1
      Route metric is 2048640, traffic share count is 3
      Total delay is 2001 microseconds, minimum bandwidth is 5000 Kbit
  * 10.1.2.2, from 10.1.2.2, 00:00:16 ago, via Ethernet0/0
      Route metric is 1536640, traffic share count is 4
      Total delay is 2001 microseconds, minimum bandwidth is 10000 Kbit
```
Look for: two paths with different metrics, shared **4 : 3** (inversely to their metrics). OSPF can't do this.
Only a feasible successor qualifies, however large the variance, so the loop-free guarantee still holds.

## Step 8 — Summarization, and the rule that beats AD
EIGRP can summarize on **any** interface of **any** router. Summarize R4's four site LANs toward R2 and R3:

**R4**
```
configure terminal
router eigrp LAB
 address-family ipv4 unicast autonomous-system 100
  af-interface Ethernet0/0
   summary-address 172.20.0.0 255.255.252.0
  exit-af-interface
  af-interface Ethernet0/1
   summary-address 172.20.0.0 255.255.252.0
  exit-af-interface
end
show ip route 172.20.0.0 255.255.252.0
```
**R1**
```
show ip route 172.20.0.0 255.255.0.0 longer-prefixes | begin Gateway
show ip route 172.20.1.1 | include Known|Routing entry
```
**Output (captured)**
```
R4: Routing entry for 172.20.0.0/22
R4:   Known via "eigrp 100", distance 5, metric 1280, precedence routine (0), type internal
R4:   * directly connected, via Null0

      172.20.0.0/16 is variably subnetted, 5 subnets, 2 masks
D        172.20.0.0/22 [90/2048640] via 10.1.3.3, 00:00:16, Ethernet0/1
                       [90/1536640] via 10.1.2.2, 00:00:16, Ethernet0/0
O        172.20.0.0/24 [110/21] via 10.1.2.2, 00:00:16, Ethernet0/0
O        172.20.1.0/24 [110/21] via 10.1.2.2, 00:00:16, Ethernet0/0
O        172.20.2.0/24 [110/21] via 10.1.2.2, 00:00:16, Ethernet0/0
O        172.20.3.0/24 [110/21] via 10.1.2.2, 00:00:16, Ethernet0/0

Routing entry for 172.20.1.0/24
  Known via "ospf 1", distance 110, metric 21, type intra area
```
Look for:
- R1 gets one EIGRP /22 instead of four /24s, and R4 installs a **discard route** to Null0 (AD 5) for the
  summary, so packets for an unused part of the /22 are dropped at R4 instead of looping.
- The OSPF /24s are **back** in R1's table. AD only breaks ties between routes for the **same prefix**. A /22 and
  a /24 are different prefixes, so both are installed, and forwarding uses the **longest match**: traffic to
  172.20.1.1 now follows OSPF.
- OSPF couldn't have summarized here. It summarizes only at an **ABR** (`area range`, between areas) or an
  **ASBR** (`summary-address`, for redistributed routes). Inside one area every router must have the same,
  unsummarized LSDB. That's also why OSPF needs **areas** to scale, and EIGRP has none.

## Final check
| From | Test | Result |
|---|---|---|
| R1 | `show ip ospf neighbor`, `show eigrp address-family ipv4 neighbors` | R2 and R3 in both |
| R1 | `show ip route 172.20.0.0 255.255.0.0 longer-prefixes` | EIGRP /22 over two paths, OSPF /24s |
| R1 | `show ip ospf rib 172.20.1.0` | OSPF route best and installed again |
| PC1 | `ping -c 2 172.20.1.1` | works |
| PC1 | `traceroute -n 172.20.1.1` | 192.168.10.1, 10.1.2.2, 10.2.4.4 |

## Side by side
| | OSPF | EIGRP |
|---|---|---|
| Type | Link state: every router has the full map (LSDB) and runs SPF | Advanced distance vector: each router knows only what neighbors report, and runs DUAL |
| Metric | Cost = reference bandwidth / bandwidth, summed per link | Composite: minimum bandwidth + total delay (wide metrics in named mode) |
| AD | 110 | 90 internal, 170 external, 5 summary |
| Backup path | None stored; recalculates SPF | Feasible successor, pre-checked loop-free (RD < FD) |
| Load balancing | Equal cost only | Equal cost, and unequal cost with `variance` |
| Hierarchy | Areas (backbone area 0, plus stub, NSSA… types) | None; flat, scaled with summarization and stubs |
| Summarization | Only at ABRs and ASBRs | On any interface |
| Hellos | 224.0.0.5 (DR/BDR: 224.0.0.6), 10/40 s on Ethernet | 224.0.0.10, 5/15 s |
| Updates | LSAs flooded through the area | Partial, bounded updates to neighbors |
| Standard | Open (RFC 2328 / 5340) | Cisco, published as informational RFC 7868 |

## Check yourself
- In Step 3, why didn't OSPF keep the R3 path as a backup in the routing table?
- Suppose R3's reported distance to 172.20.1.0 were higher than R1's FD. What would change in Step 6 and Step 7?
- You set `variance 10`. Can a path whose neighbor's RD is higher than the FD ever be installed? Why not?
- After Step 8, you shut R4's Loopback2. Which routing protocol notices on R1, and what happens to R1's /22?
- Both protocols are configured, but you want OSPF to win. Name two ways (one AD, one not).
- Why does OSPF need DR/BDR election on Ethernet, and EIGRP doesn't?

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1–R4 | IOL-XE router | cisco | cisco | cisco |
| PC1 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → Console). Routers start in privileged EXEC.
Each node also has a label in the CML canvas with its login and addresses.

## Topology

```
                         10.1.2.0/24        10.2.4.0/24
                e0/0 ─────────────── R2 ─────────────── e0/0
 PC1 ── e0/2 R1                                           R4   Lo1-4 172.20.0.0/24 - 172.20.3.0/24
 192.168.10.10  e0/1 ─────────────── R3 ─────────────── e0/1
                     10.1.3.0/24 (slow)   10.3.4.0/24
```

## Addressing

| Node | Interface | IPv4 | Connects to |
|---|---|---|---|
| R1 | Loopback0 | 10.255.255.1/32 | — |
| R1 | Ethernet0/0 | 10.1.2.1/24 | R2 e0/0 |
| R1 | Ethernet0/1 | 10.1.3.1/24 | R3 e0/0 (set to 5 Mbps in Step 3) |
| R1 | Ethernet0/2 | 192.168.10.1/24 | PC1 |
| R2 | Loopback0 | 10.255.255.2/32 | — |
| R2 | Ethernet0/0 | 10.1.2.2/24 | R1 e0/0 |
| R2 | Ethernet0/1 | 10.2.4.2/24 | R4 e0/0 |
| R3 | Loopback0 | 10.255.255.3/32 | — |
| R3 | Ethernet0/0 | 10.1.3.3/24 | R1 e0/1 (set to 5 Mbps in Step 3) |
| R3 | Ethernet0/1 | 10.3.4.3/24 | R4 e0/1 |
| R4 | Loopback0 | 10.255.255.4/32 | — |
| R4 | Loopback1–4 | 172.20.0.1/24 – 172.20.3.1/24 | simulated site LANs |
| R4 | Ethernet0/0 | 10.2.4.4/24 | R2 e0/1 |
| R4 | Ethernet0/1 | 10.3.4.4/24 | R3 e0/1 |
| PC1 | eth0 | 192.168.10.10/24, gw .1 | R1 e0/2 |
