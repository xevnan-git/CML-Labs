# 802.1Q Trunking and EtherChannel — Solution (ts-trunk-etherchannel)

> Spoilers below. Try the hints first, one at a time.

## Hints

<details><summary>Hint 1 — where to look</summary>

Both access switches are cut off, but for different reasons. Each one has two uplinks, so each needs **two** broken
uplinks before its users notice. Start on SW1 and SW2 (they're reachable) and run `show etherchannel summary` and
`show interfaces trunk`. Compare what you see with the uplink table in the Guide. Then do the same on SW3 and SW4
from their consoles.
</details>

<details><summary>Hint 2 — what to compare</summary>

- One bundle has **suspended** members on both ends. Read the log on either switch.
- One bundle is up on one end and **stand-alone** on the other, until spanning tree notices.
- One DTP link should have negotiated a trunk but is an access port. `show dtp interface` has a counter that explains why.
- One static trunk is up, but compare its *allowed* VLAN list with the design.
</details>

<details><summary>Hint 3 — almost there</summary>

- LACP needs at least one **active** end; passive only answers.
- `mode on` doesn't speak PAgP or LACP, so the far end never sees a partner. STP's EtherChannel misconfig guard
  shuts the `on` side down.
- DTP messages carry the **VTP domain name**, and a switch ignores DTP from a different domain, even in transparent mode.
- `switchport trunk allowed vlan` *replaces* the list; `... allowed vlan add` appends to it.
</details>

## Faults

### Fault 1: VTP domain mismatch on SW3 breaks DTP (3.1.a)
- **Where:** SW3, global config.
- **Injected config:** `vtp domain LAB-SW3` (designed: `vtp domain LAB`).
- **Why it breaks:** DTP frames carry the sender's VTP domain name. When the names differ, the receiver drops the
  frame and won't negotiate a trunk, even though VTP itself is in transparent mode. SW2 e0/2 (`dynamic desirable`)
  and SW3 e0/2 (`dynamic auto`) both fall back to **access** mode in VLAN 1. SW3 loses its backup uplink.
- **Evidence (Captured).** Both switches log it once at boot, and `show dtp` counts the drops:
  ```
  SW2# show logging | include DTP
  %DTP-5-DOMAINMISMATCH: Unable to perform trunk negotiation on port Et0/2 because of VTP domain mismatch.

  SW2# show dtp interface Ethernet0/2
    TOS/TAS/TNS:                              ACCESS/DESIRABLE/ACCESS
    FSM state:                                S2:ACCESS
    ...
    2 packets received (0 good)
    2 packets dropped
        0 nonegotiate, 0 bad version, 2 domain mismatches,

  SW3# show interfaces Ethernet0/2 switchport | include Mode
  Administrative Mode: dynamic auto
  Operational Mode: static access
  Access Mode VLAN: 1 (default)

  SW3# show vtp status | include Domain
  VTP Domain Name                 : LAB-SW3
  ```
- **Fix:**
  ```
  SW3(config)# vtp domain LAB
  ```
  DTP renegotiates within a few seconds. `show dtp interface Ethernet0/2` on SW2 then shows `TRUNK/DESIRABLE/TRUNK`
  and `S6:TRUNK`.

### Fault 2: LACP passive on both ends of Po2 (3.1.b)
- **Where:** SW1, Ethernet0/2 and Ethernet0/3.
- **Injected config:** `channel-group 2 mode passive` (designed: `active`). SW3 is passive by design.
- **Why it breaks:** a passive LACP port only replies to LACPDUs; it never starts the exchange. With passive on both
  ends, nobody speaks first, so no bundle forms. On IOS-XE, ports that get no LACPDUs are **suspended** rather than
  left to forward as stand-alone links, so SW3 loses its primary uplink completely. With fault 1 also in place, SW3
  has no working uplink, and PC1 and PC2 are isolated.
- **Evidence (Captured):**
  ```
  SW1# show etherchannel summary | begin Group
  1      Po1(SU)         LACP        Et0/0(P)        Et0/1(P)
  2      Po2(SD)         LACP        Et0/2(s)        Et0/3(s)

  SW1# show logging | include ETC
  %ETC-5-L3DONTBNDL2: Et0/3 suspended: LACP currently not enabled on the remote port.
  %ETC-5-L3DONTBNDL2: Et0/2 suspended: LACP currently not enabled on the remote port.

  SW1# show interfaces Ethernet0/2 etherchannel | include state|Mode
  Port state    = Up Cnt-bndl-rmt Suspend Mstr Rmt-LACP_Dsbl Not-in-Bndl
  Channel group = 2           Mode = Passive         Gcchange = -

  SW1# show lacp neighbor        (only group 1 has neighbors; group 2 has none)
  ```
  SW3 logs the same `L3DONTBNDL2` messages, so both ends blame each other. The fix belongs on SW1, because the
  design says SW1 is the active end.
- **Fix:**
  ```
  SW1(config)# interface range Ethernet0/2 - 3
  SW1(config-if-range)# channel-group 2 mode active
  ```
  (No need to remove the channel-group first, because passive to active stays within LACP.)

### Fault 3: `mode on` facing PAgP on Po3 (3.1.b)
- **Where:** SW4, Ethernet0/0 and Ethernet0/1.
- **Injected config:** `channel-group 3 mode on` (designed: `channel-group 3 mode auto`).
- **Why it breaks:** `mode on` forces a bundle without any negotiation protocol. SW2 runs PAgP `desirable`, hears no
  PAgP from SW4, and leaves its two ports **stand-alone (I)**, forwarding as two separate trunks. SW4 treats the same
  two links as one logical port. That's a loop waiting to happen. STP's **EtherChannel misconfig guard** spots BPDUs
  from two different SW2 ports arriving on one port-channel and err-disables SW4's Po3 and both members. That took
  about 90 seconds after boot in testing.
- **Evidence (Captured):**
  ```
  SW2# show etherchannel summary | begin Group
  1      Po1(SU)         LACP        Et0/0(P)        Et0/1(P)
  3      Po3(SD)         PAgP        Et1/0(I)        Et1/1(I)

  SW4# show logging | include PM-
  %PM-4-ERR_DISABLE: channel-misconfig error detected on Po3, putting Et0/0 in err-disable state
  %PM-4-ERR_DISABLE: channel-misconfig error detected on Po3, putting Et0/1 in err-disable state
  %PM-4-ERR_DISABLE: channel-misconfig error detected on Po3, putting Po3 in err-disable state

  SW4# show etherchannel 3 detail | include Mode
  Channel group = 3           Mode = On              Gcchange = -
  ```
  Before the guard fires, `show etherchannel summary` on SW4 shows `Po3(SU)  -  Et0/0(P) Et0/1(P)`. The protocol
  column is `-` because no protocol is running. If you look early, it seems fine.
  (IOL-L2 has no `show pagp` command; use `show etherchannel <n> detail` instead.)
- **Fix:** you can't change `on` to a PAgP mode in place. IOS rejects it with
  `Command rejected: ... already part of a channel with a different type of protocol enabled`. Remove the
  channel-group, add it back with the right mode, then bounce the port-channel to clear the err-disable:
  ```
  SW4(config)# interface range Ethernet0/0 - 1
  SW4(config-if-range)# shutdown
  SW4(config-if-range)# no channel-group
  SW4(config-if-range)# channel-group 3 mode auto
  SW4(config-if-range)# no shutdown
  SW4(config-if-range)# interface Port-channel3
  SW4(config-if)# shutdown
  SW4(config-if)# no shutdown
  ```
  `no channel-group` leaves `interface Port-channel3` and its trunk config in place, so the members rejoin it.

### Fault 4: VLAN 10 missing from the SW1–SW4 trunk's allowed list (3.1.a)
- **Where:** SW1, Ethernet1/0 (static trunk to SW4).
- **Injected config:** `switchport trunk allowed vlan 20,99` (designed: `10,20,99`).
- **Why it breaks:** the trunk is up and SW4's side allows 10, but SW1 won't send or accept VLAN 10 frames on it.
  For VLAN 10, SW4's only other path is Po3, and fault 3 has err-disabled it. SW4 becomes its own root bridge for
  VLAN 10 and PC3 is isolated. VLANs 20 and 99 still cross this link, so SW4 itself stays manageable, which hides
  the problem.
- **Evidence (Captured):**
  ```
  SW1# show interfaces trunk
  Port           Mode             Encapsulation  Status        Native vlan
  Et1/0          on               802.1q         trunking      999
  Po1            on               802.1q         trunking      999

  Port           Vlans allowed on trunk
  Et1/0          20,99
  Po1            10,20,99

  SW4# show spanning-tree summary | include Root
  Root bridge for: VLAN0010
  ```
  Notice that Po2 is missing from SW1's list entirely, which is fault 2.
- **Fix:**
  ```
  SW1(config)# interface Ethernet1/0
  SW1(config-if)# switchport trunk allowed vlan add 10
  ```
  Use `add`. `switchport trunk allowed vlan 10` without it would *replace* the list and drop VLANs 20 and 99.

## Why the ticket looked the way it did
Each access switch has two uplinks, and the cleanup broke both on each. SW3 lost Po2 (fault 2) and its DTP backup
(fault 1). SW4 lost Po3 (fault 3) and VLAN 10 on its direct trunk (fault 4). Fixing only one fault per switch brings
its users back. PC1/PC2 recover after fault 1 *or* 2; PC3 recovers after fault 3 *or* 4. The ticket is closed only when
all four are fixed and every bundle and trunk matches the design. "Link lights green" was true throughout: every
fault here is above the physical layer.

## Final configs
[`configs/`](configs/): the fixed, intended configuration of every node.

## Verifying the fix (Captured)
After the four fixes, tested in two passes: SW1–SW4 + PC3, then SW1–SW3 + PC1/PC2. The dev server allows 5 nodes.
```
SW1# show etherchannel summary | begin Group
1      Po1(SU)         LACP        Et0/0(P)        Et0/1(P)
2      Po2(SU)         LACP        Et0/2(P)        Et0/3(P)

SW1# show interfaces trunk | begin allowed on
Port           Vlans allowed on trunk
Et1/0          10,20,99
Po1            10,20,99
Po2            10,20,99

SW1# show lacp neighbor | begin group 2
Channel group 2 neighbors
Port          Flags  Priority  Dev ID          Age  key    Key    Number  State
Et0/2         SP     32768     aabb.cc80.0400  14s  0x0    0x2    0x1     0x3C
Et0/3         SP     32768     aabb.cc80.0400  17s  0x0    0x2    0x2     0x3C
        (flag P = SW3 is the passive end, as designed)

SW2# show etherchannel summary | begin Group
1      Po1(SU)         LACP        Et0/0(P)        Et0/1(P)
3      Po3(SU)         PAgP        Et1/0(P)        Et1/1(P)

SW2# show interfaces trunk
Port           Mode             Encapsulation  Status        Native vlan
Et0/2          desirable        802.1q         trunking      999
Po1            on               802.1q         trunking      999
Po3            on               802.1q         trunking      999

SW3# show interfaces trunk
Port           Mode             Encapsulation  Status        Native vlan
Et0/2          auto             802.1q         trunking      999
Po2            on               802.1q         trunking      999

SW3# show spanning-tree vlan 10 | begin Interface
Et0/2               Altn BLK 100       128.3    P2p
Et1/0               Desg FWD 100       128.5    P2p Edge
Po2                 Root FWD 56        128.65   P2p

SW4# show spanning-tree vlan 10 | begin Interface
Et0/2               Root FWD 100       128.3    P2p
Et1/0               Desg FWD 100       128.5    P2p Edge
Po3                 Altn BLK 56        128.65   P2p

PC3:~$ ping -c 3 192.168.10.1        3 packets transmitted, 3 packets received, 0% packet loss
PC3:~$ ping -c 3 192.168.20.1        3 packets transmitted, 3 packets received, 0% packet loss
PC1:~$ ping -c 3 192.168.10.1        3 packets transmitted, 3 packets received, 0% packet loss
PC1:~$ ping -c 3 192.168.20.10       3 packets transmitted, 3 packets received, 0% packet loss
```
Why SW4 blocks Po3 instead of its single link: its cost to the root through Po3 is 56 (Po3) + 56 (SW2's Po1) = 112.
The direct link to SW1 costs 100. A port-channel lowers the cost of *its* link, but it can still lose to a shorter path.

**Symptom check (Captured):** with faults 1 and 2 in place, `PC1:~$ ping -c 3 192.168.10.1` and
`PC2:~$ ping -c 3 192.168.20.1` both get 100% loss. With faults 3 and 4 in place, so does `PC3:~$ ping -c 5 192.168.10.1`.
