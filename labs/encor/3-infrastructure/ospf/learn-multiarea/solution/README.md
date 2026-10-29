# OSPFv2 Multi-Area — Solution (learn-multiarea)

## Final configs
[`configs/`](configs/) holds the complete configuration of every node after Step 7 (R1–R6, PC1, PC2). Paste a
router's file over a clean device to jump straight to the finished state.

## Test record

The dev CML server enforces 5 licensed nodes and its MCP has no pyATS. So the finished design was tested in chunks
by booting the final configs and reading each router's console log. Every block below is labelled:

- **Captured** — copied from the console log on the dev server (CML 2.10.1, IOL-XE 17.18.2), 2026-10-29.
- **Expected** — written from the design, not captured here. Confirm it on the 20-node server.

| Chunk | Nodes | Result |
|---|---|---|
| A | R1, R2, R3, R4, R5 + SW0 | All five adjacencies FULL. Found and fixed one config-order bug (below) |
| B | R4, R5, R6, PC1, PC2 | R5–R6 FULL; Alpine hosts boot with hostnames applied |
| — | full 8-node lab | **Not run here** — needs the 20-node server |

### Bug found in testing (fixed)
When R3 booted from a config file with the route-map *above* the interfaces, it rejected the match line:
```
 match interface Loopback1
                         ^
% Invalid input detected at '^' marker.
```
*(Captured.)* `match interface` needs the interface to exist when the line is parsed. The final config now
defines the route-map after the interfaces. In the Guide this can't happen, because Loopback1 is created in Step 1.

## Verification

### Point-to-point adjacencies form immediately — Captured
```
R1: %OSPF-5-ADJCHG: Process 1, Nbr 10.255.255.4 on Ethernet0/1 from LOADING to FULL, Loading Done
R2: %OSPF-5-ADJCHG: Process 1, Nbr 10.255.255.5 on Ethernet0/1 from LOADING to FULL, Loading Done
R6: %OSPF-5-ADJCHG: Process 1, Nbr 10.255.255.5 on Ethernet0/0 from LOADING to FULL, Loading Done
```
Each reached FULL within roughly 10–20 s of both ends being up. There's no wait timer on point-to-point links.

### Broadcast segment waits ~40 s, then elects R3 — Captured
```
R3 (Ethernet0/0 came up at 18:13:31; adjacencies logged at 18:14:11, about 40 s later):
%OSPF-5-ADJCHG: Process 1, Nbr 10.255.255.2 on Ethernet0/0 from LOADING to FULL, Loading Done
%OSPF-5-ADJCHG: Process 1, Nbr 10.255.255.1 on Ethernet0/0 from LOADING to FULL, Loading Done
```
The ~40 s gap is the OSPF **wait timer** on a broadcast network: hellos have to be heard for a full dead interval
before the DR election. R3 (priority 255) forms FULL with both R1 and R2. R1 and R2 never log a FULL with each other,
because they are DROTHER/BDR, which stop at 2WAY between themselves.

### Neighbor table on the segment — Expected
```
R2# show ip ospf neighbor
Neighbor ID     Pri   State           Dead Time   Address         Interface
10.255.255.3    255   FULL/DR         00:00:38    10.0.1.3        Ethernet0/0
10.255.255.1      0   FULL/DROTHER    00:00:33    10.0.1.1        Ethernet0/0
10.255.255.5      0   FULL/  -        00:00:35    10.2.5.5        Ethernet0/1
```

### Routing on R6 after Steps 5–7 — Expected
```
R6# show ip route ospf
      10.0.0.0/8 is variably subnetted, ...
O IA     10.0.1.0/24 [110/30] via 10.5.6.5, Ethernet0/0
O IA     10.1.4.0/24 [110/40] via 10.5.6.5, Ethernet0/0
O        10.2.5.0/24 [110/20] via 10.5.6.5, Ethernet0/0
O IA     10.255.255.1/32 [110/31] via 10.5.6.5, Ethernet0/0
O IA     10.255.255.2/32 [110/21] via 10.5.6.5, Ethernet0/0
O IA     10.255.255.3/32 [110/31] via 10.5.6.5, Ethernet0/0
O        10.255.255.5/32 [110/11] via 10.5.6.5, Ethernet0/0
      172.20.0.0/22 is subnetted, 1 subnets
O IA     172.20.0.0 [110/41] via 10.5.6.5, Ethernet0/0
O IA  192.168.10.0/24 [110/50] via 10.5.6.5, Ethernet0/0
O E2  203.0.113.0/24 [110/20] via 10.5.6.5, Ethernet0/0
```
Key points: **no** `10.255.255.4/32` (filtered on R2), a single `172.20.0.0/22` (summarized on R1), and
`O E2 203.0.113.0/24` with metric 20. The exact costs depend on the IOL interface bandwidth; check the `[110/x]` values.

### Summary discard route on R1 — Expected
```
R1# show ip route 172.20.0.0 255.255.252.0
Routing entry for 172.20.0.0/22
  Known via "ospf 1", distance 110, metric 1, type intra area
  Routing Descriptor Blocks:
  * directly connected, via Null0
```

### End to end — Expected
```
PC2:~$ ping -c 3 192.168.10.10
3 packets transmitted, 3 packets received, 0% packet loss
PC2:~$ traceroute 192.168.10.10
 1  192.168.20.1   2  10.5.6.5   3  10.2.5.2   4  10.0.1.1   5  10.1.4.4   6  192.168.10.10
```

## Check-yourself answers
- R1 is DROTHER because its priority is 0. R3, as DR, originates the segment's **type-2 network LSA**.
- With Loopback4 down, the /22 is still advertised (other components exist). Traffic for 172.20.3.50 reaches R1 and
  is dropped by the **Null0 discard route** there; it doesn't loop.
- `area 2 filter-list` only acts on **type-3** LSAs. 203.0.113.0/24 is a type-5 external, which floods unchanged.
- R1 = ABR (`show ip ospf`: "area border router"), R3 = ASBR ("autonomous system boundary router"), R5 = internal
  router: all its interfaces are in area 2, and it's listed as neither ABR nor ASBR.
