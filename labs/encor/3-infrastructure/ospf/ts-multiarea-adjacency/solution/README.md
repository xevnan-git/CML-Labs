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
- **Evidence — Captured** (R2 console, dev server):
  ```
  %OSPF-4-ERRRCV: Received invalid packet: mismatched area ID from backbone area from 10.2.5.5, Ethernet0/1
  ```
  Also: `R5# show ip ospf interface brief` lists Et0/0 in area 0 while the other interfaces are in area 2.
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
- **Evidence:** R5 and R6 never log an ADJCHG for each other (*Captured*: no adjacency in the R6 console log; with the
  intended config R6 logged FULL to 10.255.255.5 about 10 s after boot). `show ip ospf neighbor` is empty on R6.
  `R6# show ip ospf interface Ethernet0/0` says `No Hellos (Passive interface)` *(Expected)*.
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
- **Evidence:** *Captured:* no ADJCHG to FULL between R1 and R4 (with the intended config they reached FULL about
  10 s after boot). *Expected:*
  ```
  R1# show ip ospf neighbor
  Neighbor ID     Pri   State           Dead Time   Address         Interface
  10.255.255.4      0   EXSTART/  -     00:00:36    10.1.4.4        Ethernet0/1
  ```
  After a few minutes, the logs may show the neighbor dropping with *"Too many retransmissions"* and starting over.
  Compare `show ip interface Ethernet0/0 | include MTU` on both ends.
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

## Test record
Tested on the dev server (5-node limit) as chunk C: R1, R2, R4, R5, R6 + SW0 with these faults injected.
Faults 1–3 produced the symptoms above (Captured items). The full 8-node lab, the PC tests and the *Expected* show
output still need checking on the 20-node server.
