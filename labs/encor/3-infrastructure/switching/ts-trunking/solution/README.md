# 802.1Q Trunking and DTP — Solution (ts-trunking)

> Spoilers below. Try the hints first, one at a time.

## Hints

<details><summary>Hint 1 — where to look</summary>

Work one PC at a time and follow its VLAN hop by hop: access port → uplink trunk → SW1 → R1's subinterface. On
every switch, `show interfaces trunk` has four sections. Read all four for every trunk port, not just the first.
`show logging` on SW1 and SW2 is worth a look too.
</details>

<details><summary>Hint 2 — what to compare</summary>

- One of SW1's trunks allows a different VLAN list from the others.
- A VLAN can be allowed on a trunk and still not be carried. Which VLAN is missing from "allowed and active in
  management domain" on SW1, and why?
- Is SW3's uplink actually trunking? `show interfaces Ethernet0/0 switchport` and `show dtp interface Ethernet0/0`
  on SW3.
- Compare the native VLAN on both ends of every trunk.
- The switches can be perfect and the router still wrong: `show vlans` on R1.
</details>

<details><summary>Hint 3 — almost there</summary>

- `dynamic auto` only becomes a trunk if the far end *sends* DTP. `switchport nonegotiate` stops sending it.
- A switch only forwards a VLAN that exists in its own VLAN database, even as a transit switch with no ports in it.
- With mismatched native VLANs, untagged frames from one side land in a different VLAN on the other. A switch whose
  native VLAN is its management VLAN sends management traffic untagged.
- A router subinterface only accepts frames whose 802.1Q tag matches its `encapsulation dot1Q` number.
</details>

## Faults

| # | Device | Fault | Breaks |
|---|---|---|---|
| 1 | R1 | e0/0.20 `encapsulation dot1Q 200` | PC2 (hidden behind fault 5) |
| 2 | SW2 | e0/0 native VLAN 99 | SW2 management |
| 3 | SW1 | e0/2 `switchport nonegotiate` | PC3, PC4, SW3 management (SW3 stays an access port) |
| 4 | SW1 | VLAN 30 not in the VLAN database | PC3 (hidden behind fault 3) |
| 5 | SW1 | e0/1 allowed VLANs `10,30,99` | PC2 |

### Fault 5: VLAN 20 missing from SW1's trunk to SW2
- **Where:** SW1, Ethernet0/1.
- **Injected config:** `switchport trunk allowed vlan 10,30,99` (designed: `10,20,30,99`).
- **Why it breaks:** SW1 drops every VLAN 20 frame on that trunk, in both directions, so PC2 never reaches R1.
- **Evidence (Captured):**
  ```
  SW1# show interfaces trunk
  Port           Mode             Encapsulation  Status        Native vlan
  Et0/0          on               802.1q         trunking      999
  Et0/1          desirable        802.1q         trunking      999
  Et0/2          on               802.1q         trunking      999

  Port           Vlans allowed on trunk
  Et0/0          10,20,30,99
  Et0/1          10,30,99
  Et0/2          10,20,30,99

  Port           Vlans allowed and active in management domain
  Et0/0          10,20,99
  Et0/1          10,99
  Et0/2          10,20,99

  Port           Vlans in spanning tree forwarding state and not pruned
  Et0/0          10,20,99
  Et0/1          10
  Et0/2          10,20,99

  PC2:~$ ping -c 3 192.168.20.1
  3 packets transmitted, 0 packets received, 100% packet loss
  ```
  That one output holds two faults. Et0/1's allowed list is short (fault 5), and VLAN 30 is allowed everywhere but
  active nowhere (fault 4). (This was captured about a minute after boot; a few seconds later Et0/1 was forwarding
  10 and 99.)
- **Fix:**
  ```
  SW1(config)# interface Ethernet0/1
  SW1(config-if)# switchport trunk allowed vlan add 20
  ```
  Use `add`. A bare `switchport trunk allowed vlan 20` replaces the whole list.
  **PC2 still fails after this.** See fault 1.

### Fault 1: wrong 802.1Q tag on R1's VLAN 20 subinterface
- **Where:** R1, Ethernet0/0.20.
- **Injected config:** `encapsulation dot1Q 200` (designed: `encapsulation dot1Q 20`).
- **Why it breaks:** the subinterface has the right IP, so `show ip interface brief` looks perfect. But it only
  accepts frames tagged 200 and tags its replies 200. VLAN 20 frames from SW1 match no subinterface and are dropped,
  so PC2's ARP for 192.168.20.1 never gets a reply. The switches are fine at this point: SW1 learns PC2's MAC in
  VLAN 20.
- **Evidence (Captured, after fixing fault 5):**
  ```
  PC2:~$ ping -c 3 192.168.20.1; arp -n
  3 packets transmitted, 0 packets received, 100% packet loss
  ? (192.168.20.1) at <incomplete>  on eth0

  SW1# show mac address-table vlan 20
  Vlan    Mac Address       Type        Ports
    20    5254.003f.ca72    DYNAMIC     Et0/1
    20    aabb.cc00.1100    DYNAMIC     Et0/1

  R1# show vlans
  VLAN ID: 200 (IEEE 802.1Q Encapsulation)
  VLAN trunk interfaces for VLAN ID 200:
  Ethernet0/0.20
  Ethernet0/0.20 (200)
                       IP: 192.168.20.1

  R1# show interfaces Ethernet0/0.20 | include Encapsulation|Vlan
    Encapsulation 802.1Q Virtual LAN, Vlan ID  200.
  ```
  `show vlans` on R1 lists VLAN IDs 1, 10, 30, 99, 200 and 999. There's no VLAN 20, and the `.20` subinterface is
  under 200.
- **Fix:**
  ```
  R1(config)# interface Ethernet0/0.20
  R1(config-subif)# encapsulation dot1Q 20
  ```
  The IP address stays configured through the change.

### Fault 2: native VLAN mismatch on the SW1–SW2 trunk
- **Where:** SW2, Ethernet0/0.
- **Injected config:** `switchport trunk native vlan 99` (designed: `999`).
- **Why it breaks:** SW2 now sends VLAN 99, its management VLAN, **untagged**. SW1 puts untagged frames on that
  trunk into *its* native VLAN, 999, so SW2's management traffic ends up in the wrong VLAN and never reaches R1.
  User VLANs are unaffected: PC1 works throughout. CDP spots the mismatch on both ends, but nothing goes down.
  Rapid-PVST doesn't block anything here either: SW1 doesn't run spanning tree for VLAN 999, since it isn't allowed
  on any trunk.
- **Evidence (Captured):**
  ```
  SW1# show logging | include CDP
  %CDP-4-NATIVE_VLAN_MISMATCH: Native VLAN mismatch discovered on Ethernet0/1 (999), with SW2.lab.local Ethernet0/0 (99).

  SW2# show interfaces trunk
  Port           Mode             Encapsulation  Status        Native vlan
  Et0/0          auto             802.1q         trunking      99

  SW1# ping 192.168.99.202
  .....
  Success rate is 0 percent (0/5)

  PC1:~$ ping -c 3 192.168.10.1        3 packets transmitted, 3 packets received, 0% packet loss
  PC1:~$ ping -c 3 192.168.99.202      3 packets transmitted, 0 packets received, 100% packet loss
  ```
  `show interfaces trunk` on SW1 looks clean for VLAN 99. The only places the mismatch shows are the native VLAN
  column on SW2 and the CDP log.
- **Fix:**
  ```
  SW2(config)# interface Ethernet0/0
  SW2(config-if)# switchport trunk native vlan 999
  ```

### Fault 3: SW1 stopped sending DTP to SW3
- **Where:** SW1, Ethernet0/2.
- **Injected config:** `switchport nonegotiate` added (designed: `switchport mode trunk` with DTP on).
- **Why it breaks:** SW1's end is still a static trunk, so SW1 *looks* healthy: `show interfaces trunk` lists
  Et0/2 as trunking. But SW3's end is `dynamic auto`, which only turns into a trunk when it receives a DTP request.
  With `nonegotiate`, SW1 sends none, so SW3 stays a plain **access port in VLAN 1**. Everything SW1 sends tagged is
  dropped, and SW3's VLAN 10, 30 and 99 traffic never leaves the switch. PC3, PC4 and SW3 management all fail.
- **Evidence (Captured):**
  ```
  SW3# show interfaces trunk
  (empty)

  SW3# show interfaces Ethernet0/0 switchport | include Mode|Negotiation|Access Mode
  Administrative Mode: dynamic auto
  Operational Mode: static access
  Negotiation of Trunking: On
  Access Mode VLAN: 1 (default)
  Trunking Native Mode VLAN: 999 (NATIVE-UNUSED)

  SW3# show dtp interface Ethernet0/0 | include TOS|FSM|received|nonegotiate
    TOS/TAS/TNS:                              ACCESS/AUTO/ACCESS
    FSM state:                                S2:ACCESS
    0 packets received (0 good)

  PC4:~$ ping -c 3 192.168.10.1        3 packets transmitted, 0 packets received, 100% packet loss
  PC3:~$ ping -c 3 192.168.30.1        3 packets transmitted, 0 packets received, 100% packet loss
  ```
  `0 packets received` is the giveaway: SW3 has never heard a DTP frame on its uplink.
- **Fix:**
  ```
  SW1(config)# interface Ethernet0/2
  SW1(config-if)# no switchport nonegotiate
  ```
  Changing SW3 to `switchport mode trunk` would also work, but it isn't the design.
  **PC4 recovers. PC3 doesn't.** See fault 4.

### Fault 4: VLAN 30 doesn't exist on SW1
- **Where:** SW1, VLAN database.
- **Injected config:** `vlan 30` / `name FINANCE` missing (every other switch has it).
- **Why it breaks:** SW1 has no Finance ports, but it's the transit switch between SW3 and R1, and a switch only
  forwards VLANs that exist in its own database. VLAN 30 is in every allowed list, yet SW1 drops it on every trunk.
  In VTP transparent mode nothing creates it for you. This one hides behind fault 3: until SW3 is trunking, nothing
  in VLAN 30 can even reach SW1.
- **Evidence (Captured, after fixing fault 3):**
  ```
  SW1# show vlan brief
  VLAN Name                             Status    Ports
  1    default                          active    Et0/3, Et1/0, Et1/1, Et1/2, Et1/3
  10   SALES                            active
  20   ENGINEERING                      active
  99   MGMT                             active
  999  NATIVE-UNUSED                    active

  SW3# show interfaces trunk
  Port           Mode             Encapsulation  Status        Native vlan
  Et0/0          auto             802.1q         trunking      999
  ...
  Port           Vlans in spanning tree forwarding state and not pruned
  Et0/0          10,20,99

  PC4:~$ ping -c 3 192.168.10.1        3 packets transmitted, 3 packets received, 0% packet loss
  PC3:~$ ping -c 3 192.168.30.1        3 packets transmitted, 0 packets received, 100% packet loss
  ```
  SW3 itself is fine: VLAN 30 is allowed and active on its uplink. The VLAN dies at SW1, and `show vlan brief` there
  shows why.
- **Fix:**
  ```
  SW1(config)# vlan 30
  SW1(config-vlan)# name FINANCE
  ```

## Why the ticket looked the way it did
- **PC1** (VLAN 10 on SW2) works: no fault touches VLAN 10 on that path.
- **PC2** needs two fixes: VLAN 20 allowed on SW1 e0/1 (fault 5) *and* the right tag on R1 (fault 1). Fixing either
  one alone changes nothing visible.
- **PC4** is down only because SW3's uplink isn't trunking (fault 3).
- **PC3** has the same cause plus a second one (fault 4) that only appears once fault 3 is fixed. PC4 coming back
  while PC3 stays down is the clue.
- **SW2 management** is the native VLAN mismatch (fault 2). **SW3 management** is fault 3.

## Final configs
[`configs/`](configs/): the fixed, intended configuration of every node.

## Verifying the fix (Captured)
Tested in two passes (5-node license): R1, SW1, SW2, PC1, PC2, then R1, SW1, SW3, PC3, PC4 with SW2 stopped.
```
SW2# show interfaces trunk
Port           Mode             Encapsulation  Status        Native vlan
Et0/0          auto             802.1q         trunking      999
Port           Vlans in spanning tree forwarding state and not pruned
Et0/0          10,20,30,99

SW2# ping 192.168.99.1                !!!!!   Success rate is 100 percent (5/5)

PC2:~$ ping -c 3 192.168.20.1         3 packets transmitted, 3 packets received, 0% packet loss
PC2:~$ ping -c 3 192.168.10.10        3 packets transmitted, 3 packets received, 0% packet loss
PC2:~$ ping -c 3 192.168.99.202       3 packets transmitted, 1 packets received   (first pings lost to ARP)

SW1# show interfaces trunk                       (pass 2, SW2 stopped)
Port           Mode             Encapsulation  Status        Native vlan
Et0/0          on               802.1q         trunking      999
Et0/1          desirable        802.1q         trunking      999
Et0/2          on               802.1q         trunking      999
Port           Vlans allowed on trunk
Et0/0          10,20,30,99
Et0/1          10,20,30,99
Et0/2          10,20,30,99
Port           Vlans allowed and active in management domain
Et0/0          10,20,30,99
Et0/1          10,20,30,99
Et0/2          10,20,30,99
Port           Vlans in spanning tree forwarding state and not pruned
Et0/0          10,20,99
Et0/1          10,20,99
Et0/2          10,20,30,99

SW1# ping 192.168.99.203             .!!!!   Success rate is 80 percent (4/5)

PC3:~$ ping -c 3 192.168.30.1         3 packets transmitted, 3 packets received, 0% packet loss
PC3:~$ ping -c 3 192.168.10.11        3 packets transmitted, 3 packets received, 0% packet loss
PC3:~$ ping -c 3 192.168.20.1         3 packets transmitted, 3 packets received, 0% packet loss
```
In pass 2, Et0/0 and Et0/1 don't forward VLAN 30 because nothing beyond them uses it yet (R1 runs no STP and SW2 was
stopped). With every node running, Et0/0 and Et0/1 forward 10, 20, 30, 99 as well.

**Expected (not run with every node up):** `PC3:~$ ping -c 3 192.168.10.10` and `R1# ping 192.168.99.202` /
`192.168.99.203` succeed. Each path was proven in one of the two passes.

## Testing notes
- On IOL-L2-XE 17.18 the native VLAN mismatch doesn't put either port into a PVID-inconsistent state; CDP logs it
  every minute and traffic just leaks between VLANs.
- `switchport mode trunk` shows Mode **on** in `show interfaces trunk` whether or not `nonegotiate` is set. Only
  `show dtp interface` tells you whether DTP is going out.
- About 60 s after boot the PnP agent ("Config Wizard") adds `no logging console` to IOL routers and switches. Use
  `show logging` instead of waiting for messages on the console, or re-enable with `logging console`.
