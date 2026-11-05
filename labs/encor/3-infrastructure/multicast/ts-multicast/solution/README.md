# Multicast (PIM-SM, IGMP, SSM) — Solution (ts-multicast)

> Spoilers below. Try the hints first, one at a time.

## Hints

<details><summary>Hint 1 — where to look</summary>

Work from the receiver toward the source. On R3: `show ip igmp groups` (does R3 know what PC1 wants?),
`show ip pim interface`, `show ip pim neighbor`, `show ip pim rp mapping`, `show ip mroute <group>`,
`show ip rpf <address>`. On R1 and R2: `show ip mroute <group>` right after SRV1 pings, and
`show ip pim rp mapping`. On PC1: `show ip igmp interface Ethernet0/0 | include version`. Compare the three
routers' `show running-config | include ^ip pim|access-list|permit`.
</details>

<details><summary>Hint 2 — what to compare</summary>

- R3 lists no groups at all from PC1. What turns IGMP on for an interface?
- R3's (\*,G) for 239.1.1.1 has a Null incoming interface. Which RP does R3 think it is using?
- After that, R1 creates nothing for 239.1.1.1 when SRV1 sends. Does R1 have an RP for 239.1.1.1?
- R3's join toward the RP goes out Ethernet0/2. How many PIM neighbors does R3 have on that interface?
- PC1 is configured for IGMPv3, yet its host version says 2. Who decides that?
</details>

<details><summary>Hint 3 — almost there</summary>

- No `ip pim sparse-mode` on an interface means no IGMP there either.
- A static RP must be the same address on every router.
- An ACL on `ip pim rp-address` limits which groups use that RP. `0.0.255.255` covers a /16.
- The RPF neighbor has to be a PIM neighbor; PIM must run on *both* ends of a link.
- A host falls back to the oldest IGMP version it hears from the querier. SSM needs v3 on the router's LAN
  interface; the host recovers on its own within a couple of minutes.
</details>

## Faults
Two on R3's LAN interface, one more on R3, one on R1 and one on R2. In the order a learner usually meets them:

| # | Router | Fault | Breaks |
|---|---|---|---|
| 1 | R3 | no `ip pim sparse-mode` on Ethernet0/0 (LAN20) | everything (no IGMP) |
| 2 | R3 | RP is 10.255.255.3 (its own loopback) | 239.1.1.1 |
| 3 | R1 | RP 10.255.255.2 limited to an ACL covering 239.0.0.0/16 only | 239.1.1.1 |
| 4 | R2 | no `ip pim sparse-mode` on Ethernet0/1 (to R3) | 239.1.1.1 |
| 5 | R3 | `ip igmp version 2` on Ethernet0/0 | 232.1.1.1 |

### Fault 1: no PIM (so no IGMP) on R3's LAN
- **Where:** R3, Ethernet0/0.
- **Injected config:** the interface lacks `ip pim sparse-mode` (it still has `ip igmp version 2`, Fault 5).
- **Why it breaks:** `ip pim sparse-mode` is what turns on IGMP on an interface. Without it R3 ignores PC1's
  membership reports, so no group has a receiver on LAN20 and no join is ever sent. All three streams fail.
- **Evidence (Captured, at boot):**
  ```
  SRV1# ping 192.168.20.10 repeat 2
  !!
  SRV1# ping 239.1.1.1 repeat 2
  ..
  SRV1# ping 239.2.2.2 repeat 2
  ..
  SRV1# ping 232.1.1.1 repeat 2
  ..

  R3# show ip igmp groups
  Group Address    Interface                Uptime    Expires   Last Reporter   Group Accounted
  224.0.1.40       Loopback0                00:01:16  00:02:46  10.255.255.3
  R3# show ip pim interface
  Address          Interface                Ver/   Nbr    Query  DR         DR
                                            Mode   Count  Intvl  Prior
  10.255.255.3     Loopback0                v2/S   0      30     1          10.255.255.3
  10.1.3.3         Ethernet0/1              v2/S   1      30     1          10.1.3.3
  10.2.3.3         Ethernet0/2              v2/S   0      30     1          10.2.3.3
  ```
  Ethernet0/0 is missing from the list. (Ethernet0/2 with 0 neighbors is Fault 4.)
- **Fix:**
  ```
  R3(config)# interface Ethernet0/0
  R3(config-if)# ip pim sparse-mode
  ```
  Within seconds R3 learns 239.1.1.1 and 239.2.2.2 from PC1, and **239.2.2.2 starts working** (bidir uses R1 as
  RP, which every router agrees on). 232.1.1.1 is still missing (Fault 5):
  ```
  R3# show ip igmp groups
  239.1.1.1        Ethernet0/0              00:00:17  00:02:42  192.168.20.10
  239.2.2.2        Ethernet0/0              00:00:17  00:02:42  192.168.20.10
  224.0.1.40       Loopback0                00:01:53  00:02:09  10.255.255.3
  SRV1# ping 239.2.2.2 repeat 2
  Reply to request 0 from 192.168.20.10, 2 ms
  Reply to request 1 from 192.168.20.10, 2 ms
  ```

### Fault 2: R3 uses itself as the RP
- **Where:** R3, global config.
- **Injected config:** `ip pim rp-address 10.255.255.3` (designed: `10.255.255.2`).
- **Why it breaks:** R3 believes it is the RP for 239.1.1.1, so it roots PC1's shared tree at itself and sends no
  join anywhere. R1 registers SRV1 with the real RP, R2, which has no receivers. The receiver side and the source
  side never meet.
- **Evidence (Captured, after Fault 1's fix):**
  ```
  R3# show ip pim rp mapping
  Group(s): 224.0.0.0/4, Static
      RP: 10.255.255.3 (?)
  Acl: BIDIR-GROUPS, Static, Bidir Mode
      RP: 10.255.255.1 (?)
  R3# show ip mroute | include \(|Incoming
  (*, 239.1.1.1), 00:00:17/00:02:42, RP 10.255.255.3, flags: SJC
    Incoming interface: Null, RPF nbr 0.0.0.0
  ```
- **Fix:**
  ```
  R3(config)# no ip pim rp-address 10.255.255.3
  R3(config)# ip pim rp-address 10.255.255.2
  ```
  R3's (\*,G) now points out Ethernet0/2 toward R2, but SRV1's pings to 239.1.1.1 still fail (Faults 3 and 4):
  ```
  R3# show ip mroute 239.1.1.1 | begin \(
  (*, 239.1.1.1), 00:02:44/00:02:23, RP 10.255.255.2, flags: SJC
    Incoming interface: Ethernet0/2, RPF nbr 10.2.3.2
  ```

### Fault 3: R1's RP covers only 239.0.0.0/16
- **Where:** R1, global config.
- **Injected config:**
  ```
  ip access-list standard ASM-GROUPS
   permit 239.0.0.0 0.0.255.255
  ip pim rp-address 10.255.255.2 ASM-GROUPS
  ```
  (designed: `ip pim rp-address 10.255.255.2`, no ACL). The wildcard was meant to be `0.255.255.255`, but the
  design has no ACL at all.
- **Why it breaks:** R1 has no RP for 239.1.1.1, so as the first-hop router it has nobody to register SRV1 with and
  drops the packets without creating any state.
- **Evidence (Captured, after Fault 2's fix, right after `ping 239.1.1.1` on SRV1):**
  ```
  R1# show ip pim rp mapping
  Acl: ASM-GROUPS, Static
      RP: 10.255.255.2 (?)
  Acl: BIDIR-GROUPS, Static, Bidir Mode
      RP: 10.255.255.1 (?)
  R1# show ip mroute 239.1.1.1 | begin \(
  (empty)
  R2# show ip mroute 239.1.1.1 | begin \(
  (empty)
  ```
  R1's mapping has no 224.0.0.0/4 line, unlike R2's.
- **Fix:**
  ```
  R1(config)# no ip pim rp-address 10.255.255.2 ASM-GROUPS
  R1(config)# ip pim rp-address 10.255.255.2
  R1(config)# no ip access-list standard ASM-GROUPS
  ```
  Now R1 registers SRV1 with R2, R2 learns the source (and announces it over MSDP: flag **A**), but R2 has no
  receivers to send it to:
  ```
  R2# show ip mroute 239.1.1.1 | begin \(
  (*, 239.1.1.1), 00:00:21/stopped, RP 10.255.255.2, flags: SP
    Incoming interface: Null, RPF nbr 0.0.0.0
    Outgoing interface list: Null

  (192.168.10.10, 239.1.1.1), 00:00:21/00:02:38, flags: PA
    Incoming interface: Ethernet0/0, RPF nbr 10.1.2.1
    Outgoing interface list: Null
  ```

### Fault 4: no PIM on R2's link to R3
- **Where:** R2, Ethernet0/1.
- **Injected config:** the interface lacks `ip pim sparse-mode`.
- **Why it breaks:** R3's RPF interface toward the RP is Ethernet0/2 (OSPF's best path to 10.255.255.2), so R3 sends
  its (\*,G) join to 10.2.3.2. R2 doesn't run PIM on that interface and ignores it: the shared tree never reaches
  R2, and R2's (\*,G) outgoing list stays Null. R3 never sees the first packets, so it never learns the source and
  never switches to the shortest path either. This is an **RPF failure toward the RP**: the RPF neighbor isn't a
  PIM neighbor. (Unicast is fine: OSPF doesn't need PIM.)
- **Evidence (Captured, after Fault 2's fix; the pings after Fault 3's fix):**
  ```
  R3# show ip rpf 10.255.255.2
    RPF interface: Ethernet0/2
    RPF neighbor: ? (10.2.3.2)
    RPF type: unicast (ospf 1)
  R3# show ip pim neighbor | begin Address
  10.1.3.1          Ethernet0/1              00:03:50/00:01:20 v2    1 / B S P G
  R2# show ip pim interface
  Address          Interface                Ver/   Nbr    Query  DR         DR
                                            Mode   Count  Intvl  Prior
  10.255.255.2     Loopback0                v2/S   0      30     1          10.255.255.2
  10.1.2.2         Ethernet0/0              v2/S   1      30     1          10.1.2.2
  SRV1# ping 239.1.1.1 repeat 3
  ...
  ```
  R3's RPF neighbor 10.2.3.2 is missing from its PIM neighbor table, and R2 doesn't list Ethernet0/1.
- **Fix:**
  ```
  R2(config)# interface Ethernet0/1
  R2(config-if)# ip pim sparse-mode
  ```
  R3 sees 10.2.3.2 as a neighbor at once, and 239.1.1.1 works. The duplicate reply is normal while the tree
  switches from the register path to native forwarding:
  ```
  SRV1# ping 239.1.1.1 repeat 3
  Reply to request 0 from 192.168.20.10, 26 ms
  Reply to request 1 from 192.168.20.10, 3 ms
  Reply to request 1 from 192.168.20.10, 12 ms
  Reply to request 2 from 192.168.20.10, 3 ms
  ```
  A static mroute on R3 (`ip mroute 10.255.255.2 255.255.255.255 10.1.3.1`) would also make it work, via R1, but
  the design says every link runs PIM.

### Fault 5: IGMPv2 on R3's LAN
- **Where:** R3, Ethernet0/0.
- **Injected config:** `ip igmp version 2` (designed: `ip igmp version 3`).
- **Why it breaks:** an IGMPv3 host that hears a v2 querier falls back to v2 (`Current IGMP host version is 2` on
  PC1, although PC1 is configured for 3). An IGMPv2 report can't carry a source, so PC1's (S,G) join for
  232.1.1.1 is never reported. In the SSM range there's no RP, so without a source-specific join nothing builds
  a tree and R1 drops SRV1's packets.
- **Evidence (Captured, after Fault 1's fix):**
  ```
  R3# show ip igmp interface Ethernet0/0 | include version|querying
    Current IGMP host version is 2
    Current IGMP router version is 2
    IGMP querying router is 192.168.20.1 (this system)
  PC1# show ip igmp interface Ethernet0/0 | include version
    Current IGMP host version is 2
    Current IGMP router version is 3
  SRV1# ping 232.1.1.1 repeat 2
  ..
  ```
  R3's `show ip igmp groups` has no 232.1.1.1 line.
- **Fix:**
  ```
  R3(config)# interface Ethernet0/0
  R3(config-if)# ip igmp version 3
  ```
  PC1 stays in v2 compatibility mode until its "older querier present" timer runs out: it went back to host
  version 3 and reported 232.1.1.1 about 90 seconds after the fix. Then:
  ```
  R3# show ip mroute 232.1.1.1 | begin \(
  (192.168.10.10, 232.1.1.1), 00:01:18/00:02:48, flags: sTI
    Incoming interface: Ethernet0/1, RPF nbr 10.1.3.1
    Outgoing interface list:
      Ethernet0/0, Forward/Sparse, 00:01:18/00:02:48, flags:
  ```

## Verification after all fixes (Captured)
```
SRV1# ping 239.1.1.1 repeat 3
Reply to request 0 from 192.168.20.10, 23 ms
Reply to request 1 from 192.168.20.10, 2 ms
Reply to request 1 from 192.168.20.10, 18 ms
Reply to request 1 from 192.168.20.10, 6 ms
Reply to request 2 from 192.168.20.10, 2 ms
SRV1# ping 232.1.1.1 repeat 3
Reply to request 0 from 192.168.20.10, 3 ms
Reply to request 1 from 192.168.20.10, 2 ms
Reply to request 2 from 192.168.20.10, 4 ms
SRV1# ping 239.2.2.2 repeat 3
Reply to request 0 from 192.168.20.10, 2 ms
Reply to request 1 from 192.168.20.10, 2 ms
Reply to request 2 from 192.168.20.10, 3 ms

R3# show ip igmp groups
239.1.1.1        Ethernet0/0              00:09:41  00:02:48  192.168.20.10
239.2.2.2        Ethernet0/0              00:09:40  00:02:48  192.168.20.10
232.1.1.1        Ethernet0/0              00:01:18  stopped   192.168.20.10
224.0.1.40       Loopback0                00:11:17  00:02:50  10.255.255.3
R3# show ip pim rp mapping
Acl: BIDIR-GROUPS, Static, Bidir Mode
    RP: 10.255.255.1 (?)
Group(s): 224.0.0.0/4, Static
    RP: 10.255.255.2 (?)
R3# show ip mroute | include \(|Incoming|Upstream
(*,239.2.0.0/16), 00:11:32/-, RP 10.255.255.1, flags: B
  Bidir-Upstream: Ethernet0/1, RPF nbr: 10.1.3.1
(*, 239.1.1.1), 00:10:38/stopped, RP 10.255.255.2, flags: SJC
  Incoming interface: Ethernet0/2, RPF nbr 10.2.3.2
(192.168.10.10, 239.1.1.1), 00:00:33/00:02:26, flags: JT
  Incoming interface: Ethernet0/1, RPF nbr 10.1.3.1
(*, 239.2.2.2), 00:10:38/00:02:47, RP 10.255.255.1, flags: BC
  Bidir-Upstream: Ethernet0/1, RPF nbr 10.1.3.1
(192.168.10.10, 232.1.1.1), 00:02:15/00:02:47, flags: sTI
  Incoming interface: Ethernet0/1, RPF nbr 10.1.3.1
(*, 224.0.1.40), 00:08:57/00:02:48, RP 10.255.255.2, flags: SJCL
  Incoming interface: Ethernet0/2, RPF nbr 10.2.3.2

R1# show ip msdp summary
10.255.255.2     ?           Up       00:11:33 0     1     ?
R1# show ip msdp sa-cache
MSDP Source-Active Cache - 1 entries
(192.168.10.10, 239.1.1.1), RP 10.255.255.2, AS ?,00:06:34/00:05:33, Peer 10.255.255.2
```
The final configs are in [`configs/`](configs/).

## How this was tested
On the dev server, CML 2.10.1, IOL-XE 17.18.2, whole lab (5 licensed nodes), booted with the faulted configs. Each
symptom was confirmed live, then fixed in the order above. Notes:
- All faulted lines were accepted at boot (no `% Invalid input` in any boot log).
- MSDP between R1 and R2 took about a minute to come up after boot (TCP 639; `Listen`/`Down` until then).
- The repeated `Reply to request 1` lines appear when the first packets of a stream travel both inside a register
  and natively during the switchover; after that each request gets exactly one reply.
