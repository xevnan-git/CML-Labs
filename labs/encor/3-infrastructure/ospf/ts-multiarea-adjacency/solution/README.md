# OSPFv2 Multi-Area — Solution (ts-multiarea-adjacency)

> Spoilers below. Try the hints first, one at a time.

## Hints

<details><summary>Hint 1 — where to look</summary>

The core is fine, as the ticket says. Walk the path from PC2 toward PC1 one hop at a time with
`show ip ospf neighbor`, and note every link where a neighbor you'd expect is missing or isn't FULL.
</details>

<details><summary>Hint 2 — what to compare</summary>

There are three broken links, and each one breaks differently:
- On one link, one side is complaining in its **log**. Check `show logging`.
- On one link, one router doesn't list the other at all, and `show ip ospf interface` on that router is missing
  something you'd normally see (hellos).
- On one link, both routers see each other, but the neighbor state never reaches FULL.
</details>

<details><summary>Hint 3 — almost there</summary>

Before two OSPF routers can become neighbors, these must match: area ID, hello/dead timers, authentication,
subnet/mask, and stub flags. Passive interfaces don't send hellos. And the DBD exchange checks one more
interface parameter.
</details>

## Faults

### Fault 1: area mismatch on R5 Ethernet0/0
- **Where:** R5, Ethernet0/0 (link to R2)
- **Injected config:** `ip ospf 1 area 0` (designed: `ip ospf 1 area 2`)
- **Why it breaks:** the area ID is carried in every hello. R2's Et0/1 is in area 2 and R5's Et0/0 says area 0, so
  each side discards the other's hellos and no adjacency forms. Area 2 is cut off from the backbone.
- **Evidence — Captured.** R2's log repeats this every hello interval (10 s):
  ```
  R2# show logging | include OSPF
  %OSPF-4-ERRRCV: Received invalid packet: mismatched area ID from backbone area from 10.2.5.5, Ethernet0/1
  %OSPF-4-ERRRCV: Received invalid packet: mismatched area ID from backbone area from 10.2.5.5, Ethernet0/1
  ...
  ```
  R5 has no neighbors at all, and its interface list gives the fault away:
  ```
  R5# show ip ospf interface brief
  Interface    PID   Area            IP Address/Mask    Cost  State Nbrs F/C
  Et0/0        1     0               10.2.5.5/24        10    P2P   0/0
  Lo0          1     2               10.255.255.5/32    1     LOOP  0/0
  Et0/1        1     2               10.5.6.5/24        10    P2P   0/0
  ```
  Notice that only R2 logs the error. R5 receives hellos saying "area 2" on an interface it believes is in area 0,
  but it logs nothing. The router that complains isn't necessarily the misconfigured one.
- **Fix:**
  ```
  R5(config)# interface Ethernet0/0
  R5(config-if)# ip ospf 1 area 2
  ```

### Fault 2: passive-interface on the wrong interface on R6
- **Where:** R6, `router ospf 1`
- **Injected config:** `passive-interface Ethernet0/0` (designed: `passive-interface Ethernet0/1`)
- **Why it breaks:** a passive interface still advertises its subnet but sends and processes no hellos. With the
  uplink to R5 passive, R6 never forms an adjacency. Meanwhile the PC2 LAN interface, which was meant to be passive,
  is now sending hellos toward PC2 (a security issue, not the outage).
- **Evidence — Captured.** R6 has no neighbors and no OSPF routes. The uplink's interface detail says why:
  ```
  R6# show ip ospf neighbor
  (empty)
  R6# show ip ospf interface Ethernet0/0 | include State|Passive
    Transmit Delay is 1 sec, State POINT_TO_POINT
      No Hellos (Passive interface)
  R6# show ip route ospf | begin Gateway
  Gateway of last resort is not set
  ```
  Unlike fault 1, neither side logs anything. R5 simply never hears a hello from R6.
- **Fix:**
  ```
  R6(config)# router ospf 1
  R6(config-router)# no passive-interface Ethernet0/0
  R6(config-router)# passive-interface Ethernet0/1
  ```

### Fault 3: IP MTU mismatch on R4 Ethernet0/0
- **Where:** R4, Ethernet0/0 (link to R1)
- **Injected config:** `ip mtu 1400` (designed: default 1500)
- **Why it breaks:** hellos don't carry the MTU, so R1 and R4 see each other and move past 2-WAY. Database
  Description (DBD) packets do carry the interface MTU, and a router rejects a DBD advertising a larger MTU than its
  own. R4 (1400) rejects R1's DBDs (1500), so the pair loops in **EXSTART/EXCHANGE** and never reaches FULL. Area 1,
  including Site A's LANs, is cut off.
- **Evidence — Captured.** The two ends get stuck in *different* states, which is the giveaway for an MTU mismatch:
  ```
  R1# show ip ospf neighbor
  Neighbor ID     Pri   State           Dead Time   Address         Interface
  10.255.255.4      0   EXCHANGE/  -    00:00:38    10.1.4.4        Ethernet0/1

  R4# show ip ospf neighbor
  Neighbor ID     Pri   State           Dead Time   Address         Interface
  10.255.255.1      0   EXSTART/  -     00:00:38    10.1.4.1        Ethernet0/0

  R4# show ip interface Ethernet0/0 | include MTU
    MTU is 1400 bytes
  ```
  R1 (MTU 1500) accepted R4's DBD and moved on to EXCHANGE. R4 (MTU 1400) keeps rejecting R1's DBD, which advertises
  1500, so it never leaves EXSTART. On IOS-XE 17.18 neither side logged an MTU message during the test. You have to
  find this one with `show ip ospf neighbor` and then compare MTUs. Left long enough, the adjacency may reset with
  "Too many retransmissions" *(Expected, not seen in the short test)*.
- **Fix:**
  ```
  R4(config)# interface Ethernet0/0
  R4(config-if)# no ip mtu
  ```
  (`ip ospf mtu-ignore` would also bring the adjacency up, but it hides the mismatch instead of fixing it. That's
  not the intended design.)

## Why the ticket looked the way it did
Faults 1 and 2 each isolate Site B, and fault 3 isolates Site A. Fixing any one or two of them still leaves PC2 unable
to reach PC1, which is why "fixing one may reveal the next".

## Final configs
[`configs/`](configs/) — the fixed, intended configuration of every node. It's identical to the learning lab's final state.

## Verifying the fix — Captured
After the three fixes above, on the same test chunk:
```
R1# show ip ospf neighbor
10.255.255.2    100   FULL/DR         00:00:31    10.0.1.2        Ethernet0/0
10.255.255.4      0   FULL/  -        00:00:32    10.1.4.4        Ethernet0/1

R6# show ip ospf neighbor
10.255.255.5      0   FULL/  -        00:00:31    10.5.6.5        Ethernet0/0

R6# show ip route ospf | include 172.20|192.168.10|10.255.255.4
      172.20.0.0/22 is subnetted, 1 subnets
O IA     172.20.0.0 [110/41] via 10.5.6.5, 00:00:38, Ethernet0/0
O IA  192.168.10.0/24 [110/50] via 10.5.6.5, 00:00:38, Ethernet0/0

R6# ping 172.20.3.1
!!!!!
R6# ping 192.168.10.1 source 192.168.20.1
!!!!!
R6# show ip route 10.255.255.4
% Subnet not in table

R4# show ip route ospf | include 192.168.20
O IA  192.168.20.0/24 [110/50] via 10.1.4.1, 00:00:54, Ethernet0/0
```
The filter on R2 still hides 10.255.255.4 from area 2, as intended. (R2 is DR here only because R3 wasn't in the
test chunk. On the full lab R3 is DR and R2 is BDR.)

## Test record
Tested on the dev server (5-node limit) with pyATS on 2026-10-29. The chunk was R1, R2, R4, R5, R6 + SW0 with all
three faults injected: each fault's evidence was captured, the fixes were applied, and the result was re-checked.
Not covered here: R3/external routes (they aren't affected by the faults) and the PC1 ↔ PC2 test. The LAN-to-LAN path
was proven router-to-router. Run the full 8-node lab once on the 20-node server.
