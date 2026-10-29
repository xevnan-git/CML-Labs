# OSPFv2 Multi-Area — Solution (learn-multiarea)

## Final configs
[`configs/`](configs/) holds the complete configuration of every node after Step 7 (R1–R6, PC1, PC2). Paste a
router's file over a clean device to jump straight to the finished state.

## Test record

The dev CML server enforces 5 licensed nodes, so the finished design was booted in chunks and checked with real
commands through pyATS (CML 2.10.1, IOL-XE 17.18.2, 2026-10-29). Each output block is labelled:

- **Captured** — real output from the dev server.
- **Expected** — not captured here; confirm it on the 20-node server.

| Chunk | Nodes | What it proved |
|---|---|---|
| A | R1, R2, R3, R4, R5 + SW0 | DR/BDR election, non-preemption, ABR summary + Null0, LSDB, Step 3 "before" behavior |
| C | R1, R2, R4, R5, R6 + SW0 | R6's view: the /22 summary, the type-3 filter, end-to-end path, passive LAN |
| D | R2, R3, R5, R6, PC2 + SW0 | External E2 route and type-4 LSA at R6, PC2 reachability |
| — | full 8 nodes incl. PC1↔PC2 | **Not run here.** The LAN-to-LAN path was tested router-to-router (R6 → R4 LAN gateway) |

Because each chunk leaves out some routers, a few routes are missing from individual outputs below (e.g. chunk C has
no R3, so no E2 route). Each block says which chunk it came from.

### Bug found in testing (fixed)
When R3 booted with the route-map *above* the interfaces in its startup config, it rejected the match line
*(Captured, boot console)*:
```
 match interface Loopback1
                         ^
% Invalid input detected at '^' marker.
```
`match interface` needs the interface to exist when the line is parsed. The final config now defines the
route-map after the interfaces. In the Guide this can't happen, because Loopback1 is created in Step 1.

---

## Step 2 — the area 0 segment

**Captured (chunk A)** — R1 is DROTHER (priority 0); R3 (255) is DR, R2 (100) is BDR:
```
R1# show ip ospf neighbor
Neighbor ID     Pri   State           Dead Time   Address         Interface
10.255.255.2    100   FULL/BDR        00:00:33    10.0.1.2        Ethernet0/0
10.255.255.3    255   FULL/DR         00:00:35    10.0.1.3        Ethernet0/0
10.255.255.4      0   FULL/  -        00:00:31    10.1.4.4        Ethernet0/1

R1# show ip ospf interface Ethernet0/0
  Process ID 1, Router ID 10.255.255.1, Network Type BROADCAST, Cost: 10
  Transmit Delay is 1 sec, State DROTHER, Priority 0
  Designated Router (ID) 10.255.255.3, Interface address 10.0.1.3
  Backup Designated router (ID) 10.255.255.2, Interface address 10.0.1.2
  Timer intervals configured, Hello 10, Dead 40, Wait 40, Retransmit 5
  Neighbor Count is 2, Adjacent neighbor count is 2
    Adjacent with neighbor 10.255.255.2  (Backup Designated Router)
    Adjacent with neighbor 10.255.255.3  (Designated Router)
```
(trimmed)

**Captured (chunk A)** — from R2's side, R1 shows as `FULL/DROTHER`:
```
R2# show ip ospf neighbor
Neighbor ID     Pri   State           Dead Time   Address         Interface
10.255.255.1      0   FULL/DROTHER    00:00:34    10.0.1.1        Ethernet0/0
10.255.255.3    255   FULL/DR         00:00:31    10.0.1.3        Ethernet0/0
10.255.255.5      0   FULL/  -        00:00:39    10.2.5.5        Ethernet0/1
```
R1 and R2 are FULL here because R2 is the BDR. Two DROTHERs would stop at `2WAY/DROTHER` with each other.

**Captured (chunk A)** — DR election doesn't preempt. Raising R1's priority to 254 on a running segment changes nothing:
```
R1(config)# interface Ethernet0/0
R1(config-if)# ip ospf priority 254
R1# show ip ospf interface brief | include Et0/0
Et0/0        1     0               10.0.1.1/24        10    DROTH 2/2
```

## Step 3 — area 1, before and after point-to-point

**Captured (chunk A, point-to-point temporarily removed on R1 e0/1, R4 e0/0 and R4 Lo1–4)** —
first the 40-second **wait timer** on the new broadcast link:
```
R1# show ip ospf interface brief
Interface    PID   Area            IP Address/Mask    Cost  State Nbrs F/C
Lo0          1     0               10.255.255.1/32    1     LOOP  0/0
Et0/0        1     0               10.0.1.1/24        10    DROTH 2/2
Et0/1        1     1               10.1.4.1/24        10    WAIT  0/1

R1# show ip ospf neighbor
10.255.255.4      1   2WAY/DROTHER    00:00:32    10.1.4.4        Ethernet0/1
```
…then a DR election on a link with only two routers, and the loopbacks advertised as /32 host routes:
```
R1# show ip ospf neighbor
10.255.255.4      1   FULL/DR         00:00:37    10.1.4.4        Ethernet0/1

R1# show ip route ospf | include 172.20
      172.20.0.0/32 is subnetted, 4 subnets
O        172.20.0.1 [110/11] via 10.1.4.4, 00:00:20, Ethernet0/1
O        172.20.1.1 [110/11] via 10.1.4.4, 00:00:20, Ethernet0/1
O        172.20.2.1 [110/11] via 10.1.4.4, 00:00:20, Ethernet0/1
O        172.20.3.1 [110/11] via 10.1.4.4, 00:00:20, Ethernet0/1

R4# show ip ospf interface Loopback1 | include Network Type
  Process ID 1, Router ID 10.255.255.4, Network Type LOOPBACK, Cost: 1
```
**Captured (chunk A)** — with point-to-point restored (the final configs), R4 is `FULL/  -` and the /24s appear.
Here they're shown under the summary, because Step 6 is also applied:
```
O        172.20.0.0/22 is a summary, 00:01:18, Null0
O        172.20.0.0/24 [110/11] via 10.1.4.4, 00:01:18, Ethernet0/1
O        172.20.1.0/24 [110/11] via 10.1.4.4, 00:01:18, Ethernet0/1
O        172.20.2.0/24 [110/11] via 10.1.4.4, 00:01:18, Ethernet0/1
O        172.20.3.0/24 [110/11] via 10.1.4.4, 00:01:18, Ethernet0/1
O     192.168.10.0/24 [110/20] via 10.1.4.4, 00:01:18, Ethernet0/1
```
192.168.10.0/24 is advertised even though Et0/1 is passive.

## Step 4 — area 2

**Captured (chunk C)** — R6's routing table (no R3 in this chunk, so no E2 route):
```
R6# show ip route ospf
      10.0.0.0/8 is variably subnetted, 9 subnets, 2 masks
O IA     10.0.1.0/24 [110/30] via 10.5.6.5, 00:00:34, Ethernet0/0
O IA     10.1.4.0/24 [110/40] via 10.5.6.5, 00:00:05, Ethernet0/0
O        10.2.5.0/24 [110/20] via 10.5.6.5, 00:00:34, Ethernet0/0
O IA     10.255.255.1/32 [110/31] via 10.5.6.5, 00:00:05, Ethernet0/0
O IA     10.255.255.2/32 [110/21] via 10.5.6.5, 00:00:34, Ethernet0/0
O        10.255.255.5/32 [110/11] via 10.5.6.5, 00:00:34, Ethernet0/0
      172.20.0.0/22 is subnetted, 1 subnets
O IA     172.20.0.0 [110/41] via 10.5.6.5, 00:00:05, Ethernet0/0
O IA  192.168.10.0/24 [110/50] via 10.5.6.5, 00:00:05, Ethernet0/0

R6# show ip ospf border-routers
i 10.255.255.2 [20] via 10.5.6.5, Ethernet0/0, ABR, Area 2, SPF 5

R6# show ip ospf interface Ethernet0/1 | include Passive
    No Hellos (Passive interface)
```
Note `10.255.255.2/32` is `O IA`, not `O`: R2's Loopback0 is in area 0, so even R2's own loopback reaches area 2
as a type-3 summary.

**Captured (chunk C)** — Site B LAN to Site A LAN, sourced from the LAN gateways:
```
R6# ping 192.168.10.1 source 192.168.20.1
!!!!!
Success rate is 100 percent (5/5), round-trip min/avg/max = 2/2/5 ms

R6# traceroute 192.168.10.1 source 192.168.20.1 numeric
  1 10.5.6.5 2 msec 2 msec 3 msec
  2 10.2.5.2 4 msec 3 msec 2 msec
  3 10.0.1.1 3 msec 3 msec 3 msec
  4 10.1.4.4 3 msec *  4 msec
```
Area 2 → R2 → area 0 → R1 → area 1, exactly as the Guide describes.

## Step 5 — the ASBR

**Captured (chunk A)**:
```
R3# show ip ospf | include boundary
 It is an autonomous system boundary router

R3# show ip ospf database external
  LS Type: AS External Link
  Link State ID: 203.0.113.0 (External Network Number )
  Advertising Router: 10.255.255.3
  Network Mask: /24
	Metric Type: 2 (Larger than any link state path)
	Metric: 20

R5# show ip ospf database asbr-summary
		Summary ASB Link States (Area 2)
  LS Type: Summary Links(AS Boundary Router)
  Link State ID: 10.255.255.3 (AS Boundary Router address)
  Advertising Router: 10.255.255.2
	MTID: 0 	Metric: 10
```
(trimmed)

**Captured (chunk D)** — at R6 the external route keeps metric 20. `forward metric 30` is R6's internal cost to reach
the ASBR, which R6 learns through the type-4 LSA:
```
R6# show ip route 203.0.113.0
Routing entry for 203.0.113.0/24
  Known via "ospf 1", distance 110, metric 20, type extern 2, forward metric 30
  * 10.5.6.5, from 10.255.255.3, 00:00:16 ago, via Ethernet0/0

R6# show ip ospf border-routers
I 10.255.255.3 [30] via 10.5.6.5, Ethernet0/0, ASBR, Area 2, SPF 5
i 10.255.255.2 [20] via 10.5.6.5, Ethernet0/0, ABR, Area 2, SPF 5
```
For E2 routes, OSPF uses the forward metric only as a tie-breaker between two exits with the same E2 metric.

**Captured (chunk D)** — PC2 reaches the external network and R3's loopback:
```
PC2:~$ ping -c 3 203.0.113.1
3 packets transmitted, 3 packets received, 0% packet loss
PC2:~$ traceroute -n 10.255.255.3
 1  192.168.20.1   2  10.5.6.5   3  10.2.5.2   4  10.0.1.3
```

## Step 6 — summarization

**Captured (chunk A)** — the discard route on R1:
```
R1# show ip route 172.20.0.0 255.255.252.0
Routing entry for 172.20.0.0/22
  Known via "ospf 1", distance 110, metric 0, type intra area
  Routing Descriptor Blocks:
  * directly connected, via Null0
```
**Captured (chunk C)** — R6 sees one prefix instead of four:
```
R6# show ip route 172.20.0.0 255.255.0.0 longer-prefixes
      172.20.0.0/22 is subnetted, 1 subnets
O IA     172.20.0.0 [110/41] via 10.5.6.5, 00:00:05, Ethernet0/0
```

## Step 7 — the filter

**Captured (chunk C)**:
```
R6# show ip route 10.255.255.4
% Subnet not in table
R6# ping 10.255.255.4
.....
Success rate is 0 percent (0/5)
```
**Captured (chunk A)** — R1 still has the route (`O 10.255.255.4/32 [110/11] via 10.1.4.4`). In R5's LSDB the type-3
for 10.255.255.4 is simply absent, while 172.20.0.0 and 192.168.10.0 are there.

## Step 8 — the LSDB

**Captured (chunk A)** — R1, an ABR, holds one database per area:
```
R1# show ip ospf database
		Router Link States (Area 0)
10.255.255.1    10.255.255.1    35          0x80000007 0x0007CF 2
10.255.255.2    10.255.255.2    41          0x80000007 0x001BB7 2
10.255.255.3    10.255.255.3    36          0x80000006 0x00349A 2
		Net Link States (Area 0)
10.0.1.3        10.255.255.3    50          0x80000001 0x002BCB
		Summary Net Link States (Area 0)
10.1.4.0        10.255.255.1    ...
10.2.5.0        10.255.255.2    ...
10.5.6.0        10.255.255.2    ...
10.255.255.4    10.255.255.1    ...
10.255.255.5    10.255.255.2    ...
172.20.0.0      10.255.255.1    ...
192.168.10.0    10.255.255.1    ...
		Router Link States (Area 1)
10.255.255.1    10.255.255.1    78          0x80000002 0x008249 2
10.255.255.4    10.255.255.4    47          0x80000004 0x00DFEA 8
		Summary Net Link States (Area 1)
		(area 0 and area 2 prefixes, all advertised by 10.255.255.1)
		Summary ASB Link States (Area 1)
10.255.255.3    10.255.255.1    49          0x80000001 0x00DE3B
		Type-5 AS External Link States
203.0.113.0     10.255.255.3    91          0x80000001 0x004214 0

R1# show ip ospf | include border
 It is an area border router
```
The single Net LSA (type 2) is originated by R3, the DR. Area 1 has no Net LSAs, because both of its links are point-to-point.

**Captured (chunk A)** — R5, an internal router, has no ABR/ASBR line in `show ip ospf`, and its database has only
area 2 plus the externals:
```
R5# show ip ospf database
		Router Link States (Area 2)
10.255.255.2    10.255.255.2    ...
10.255.255.5    10.255.255.5    ...
		Summary Net Link States (Area 2)
10.0.1.0 / 10.1.4.0 / 10.255.255.1 / 10.255.255.2 / 10.255.255.3 / 172.20.0.0 / 192.168.10.0   (all from 10.255.255.2)
		Summary ASB Link States (Area 2)
10.255.255.3    10.255.255.2    ...
		Type-5 AS External Link States
203.0.113.0     10.255.255.3    ...
```
(R6 wasn't in chunk A; on the full lab there's also a Router LSA for 10.255.255.6.)

## Final check — Expected (needs the full lab)
```
PC2:~$ ping -c 3 192.168.10.10
3 packets transmitted, 3 packets received, 0% packet loss
PC2:~$ traceroute -n 192.168.10.10
 1  192.168.20.1   2  10.5.6.5   3  10.2.5.2   4  10.0.1.1   5  10.1.4.4   6  192.168.10.10
```
Every hop in this path was captured separately (chunks C and D), but not PC1 ↔ PC2 end to end.

## Check-yourself answers
- R1 is DROTHER because its priority is 0. R3, as DR, originates the segment's **type-2 network LSA**. That's the
  single `Net Link States (Area 0)` entry, advertised by 10.255.255.3.
- With Loopback4 down, the /22 is still advertised, because other component prefixes exist. Traffic for 172.20.3.50
  reaches R1 and is dropped by the **Null0 discard route** there, so it doesn't loop.
- `area 2 filter-list` only acts on **type-3** LSAs. 203.0.113.0/24 is a type-5 external, which floods unchanged.
- R1 = ABR (`It is an area border router`), R3 = ASBR (`It is an autonomous system boundary router`), R5 = internal
  router: `show ip ospf` prints neither line, and its LSDB has only area 2.
