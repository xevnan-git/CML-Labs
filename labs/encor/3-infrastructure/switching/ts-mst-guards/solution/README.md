# MST and STP Guards — Solution (ts-mst-guards)

> Spoilers below. Try the hints first, one at a time.

## Hints

<details><summary>Hint 1 — where to look</summary>

PC2's problem is on SW4, but there are two separate reasons it's cut off. Start with `show logging`,
`show interfaces status err-disabled` and `show spanning-tree inconsistentports` on SW4. Then compare
`show spanning-tree mst configuration` on all four switches. The ticket says Sales works, but "working" isn't the
same as "matches the design".
</details>

<details><summary>Hint 2 — what to compare</summary>

- One SW4 uplink is err-disabled. Which feature did that, and does the design put that feature on uplinks?
- The other SW4 uplink is blocked by a guard. Which side of the link is the guard on, and which direction is the
  root?
- One switch's MST region config is *almost* identical to the others. Read the name character by character.
- After the region is fixed, look at SW1's and SW2's logs again.
</details>

<details><summary>Hint 3 — almost there</summary>

- BPDU guard err-disables a port on *any* BPDU. A trunk to a distribution switch receives BPDUs constantly.
- Root guard blocks a port that receives a *superior* BPDU. On an access switch's root port, every BPDU from the
  root direction is superior.
- MST region names are case-sensitive.
- Across a region boundary, only instance 0 is exchanged, so another region's per-instance priorities are hidden.
  Inside one region they aren't.
</details>

## Faults

### Fault 1: BPDU guard + PortFast on SW4's uplink to SW2
- **Where:** SW4, Ethernet0/1 (trunk to SW2 e0/2).
- **Injected config:** `spanning-tree portfast trunk` and `spanning-tree bpduguard enable` (designed: neither).
- **Why it breaks:** BPDU guard err-disables a port on the first BPDU it receives, and SW2 sends BPDUs on that trunk
  every 2 seconds. The port died within seconds of boot. PortFast on a trunk is legitimate toward servers or
  hypervisors, never toward another switch.
- **Evidence (Captured):**
  ```
  SW4# show logging | include BPDUGUARD|ERR_DISABLE
  %SPANTREE-2-BLOCK_BPDUGUARD: Received BPDU from bridge aabb.cc00.0600 on port Et0/1 with BPDU Guard enabled. Disabling port.
  %PM-4-ERR_DISABLE: bpduguard error detected on Et0/1, putting Et0/1 in err-disable state

  SW4# show interfaces status err-disabled
  Port         Name         Status       Reason               Err-disabled Vlans
  Et0/1        to SW2 e0/2  err-disabled bpduguard
  ```
  (The bridge in the message is the CIST root carried in the BPDU, SW1, even though the BPDU arrived from SW2.)
- **Fix:**
  ```
  SW4(config)# interface Ethernet0/1
  SW4(config-if)# no spanning-tree portfast trunk
  SW4(config-if)# no spanning-tree bpduguard enable
  SW4(config-if)# shutdown
  SW4(config-if)# no shutdown
  ```
  The `shutdown` / `no shutdown` clears the err-disable. Auto-recovery for `bpduguard` is off by default.

### Fault 2: root guard on SW4's root port
- **Where:** SW4, Ethernet0/0 (trunk to SW1 e0/2).
- **Injected config:** `spanning-tree guard root` (designed: none on the access side; root guard belongs on SW1's
  end of this link, where it's already configured).
- **Why it breaks:** root guard blocks a port that receives a BPDU superior to the switch's own root information.
  SW4's best path to the root (SW1) is *through this port*, so every BPDU from SW1 is superior. The port goes
  root-inconsistent in every MST instance. With fault 1 killing the other uplink, SW4 has no way out, so PC2 is
  isolated. Root guard on an *access* switch's uplink is always wrong: it guards against the very root you want.
- **Evidence (Captured):**
  ```
  SW4# show logging | include ROOTGUARD
  %SPANTREE-2-ROOTGUARD_BLOCK: Received a superior STP BPDU from bridge aabb.cc00.0600. Root guard blocking port Ethernet0/0 on MST1.

  SW4# show spanning-tree inconsistentports
  Name                 Interface                      Inconsistency
  MST0                 Ethernet0/0                    Root Inconsistent
  MST1                 Ethernet0/0                    Root Inconsistent
  MST2                 Ethernet0/0                    Root Inconsistent

  SW4# show spanning-tree summary | include Root
  Root bridge for: MST0-MST2

  SW4# show spanning-tree mst 2
  ##### MST2    vlans mapped:   20
  Bridge        address aabb.cc00.0900  priority      32770 (32768 sysid 2)
  Root          this switch for MST2
  Et0/0                            Desg BKN*2000000   128.1    P2p *ROOT_Inc
  Et1/0                            Desg FWD 2000000   128.5    P2p Edge

  PC2:~$ ping -c 3 192.168.20.1
  3 packets transmitted, 0 packets received, 100% packet loss
  ```
- **Fix:**
  ```
  SW4(config)# interface Ethernet0/0
  SW4(config-if)# no spanning-tree guard root
  ```
  Root-inconsistent clears by itself. No bounce needed.

### Fault 3: MST region name case mismatch on SW3
- **Where:** SW3, `spanning-tree mst configuration`.
- **Injected config:** `name Lab` (designed: `name LAB`).
- **Why it breaks:** the region name is case-sensitive, so SW3 forms a region of its own. Across the boundary only
  the CIST (instance 0) is negotiated, and SW3's instances follow the CIST port roles. VLAN 20 on SW3 leaves via
  SW1 instead of SW2. Nothing goes down, which is why the ticket says Sales "works". But the design is broken, and
  this fault also **hides fault 4**.
- **Evidence (Captured):**
  ```
  SW3# show spanning-tree mst configuration
  Name      [Lab]
  Revision  1     Instances configured 3

  SW3# show spanning-tree mst 0 | include Root|Regional|Et0
  Root          address aabb.cc00.0600  priority      4096  (4096 sysid 0)
  Regional Root this switch
  Et0/0                            Root FWD 2000000   128.1    P2p Bound(RSTP)
  Et0/1                            Altn BLK 2000000   128.2    P2p Bound(RSTP)

  SW3# show spanning-tree mst 2
  ##### MST2    vlans mapped:   20
  Root          this switch for MST2
  Et0/0                            Mstr FWD 2000000   128.1    P2p Bound(RSTP)
  Et0/1                            Altn BLK 2000000   128.2    P2p Bound(RSTP)
  ```
  Design says MST2's root port on SW3 is e0/1 (to SW2). Here e0/0 is forwarding as the *master* port (the CIST root
  port), and SW3 believes it's root of MST1 and MST2. Note that **only SW3** shows the `Bound` flags; SW1 and SW2 show
  nothing unusual in `show spanning-tree mst`.
- **Fix:**
  ```
  SW3(config)# spanning-tree mst configuration
  SW3(config-mst)# name LAB
  SW3(config-mst)# exit
  ```
  **Fixing this breaks PC1.** See fault 4.

### Fault 4: SW3 claims root of MST 1 (priority 0)
- **Where:** SW3, global config.
- **Injected config:** `spanning-tree mst 1 priority 0` (designed: default).
- **Why it breaks:** while SW3 was in its own region (fault 3), its MST1 priority stayed inside that region. Once
  the names match, SW3's MST1 information (priority 0) flows to SW1 and SW2, where it's superior. **Root guard does
  its job** on both distribution downlinks to SW3 and blocks them, for **MST1 only**. VLAN 10 on SW3 is cut off, so
  PC1 can't reach its gateway. VLANs 20 and 99 keep working, so SW3 is still manageable.
- **Evidence (Captured, after fixing fault 3 only):**
  ```
  SW1# show logging | include ROOTGUARD
  %SPANTREE-2-ROOTGUARD_BLOCK: Received a superior STP BPDU from bridge aabb.cc00.0600. Root guard blocking port Ethernet0/1 on MST1.

  SW1# show spanning-tree inconsistentports
  Name                 Interface                      Inconsistency
  MST1                 Ethernet0/1                    Root Inconsistent

  SW1# show spanning-tree mst 1 | begin Interface
  Et0/0                            Desg FWD 2000000   128.1    P2p
  Et0/1                            Desg BKN*2000000   128.2    P2p *ROOT_Inc
  Et0/2                            Desg FWD 2000000   128.3    P2p

  SW2# show spanning-tree inconsistentports
  MST1                 Ethernet0/1                    Root Inconsistent

  SW3# show spanning-tree mst 1
  Bridge        address aabb.cc00.0800  priority      1     (0 sysid 1)
  Root          this switch for MST1

  PC1:~$ ping -c 3 192.168.10.1
  3 packets transmitted, 0 packets received, 100% packet loss
  ```
  Don't be misled by the log: `from bridge aabb.cc00.0600` is SW1's own MAC (the CIST root carried in the BPDU),
  not the switch claiming MST1. `show spanning-tree mst 1` on the neighbor tells you who's really claiming it.
- **Fix:** remove the priority. Don't remove root guard; it caught a real problem.
  ```
  SW3(config)# no spanning-tree mst 1 priority
  ```

## Why the ticket looked the way it did
SW4 needed both of its faults (1 and 2) to lose PC2, and fixing either one brings PC2 back. SW3's two faults
cancelled each other out: the region mismatch kept SW3's rogue MST1 priority from ever reaching root guard, so Sales
"worked". Fixing the mismatch, which is the right thing to do, then knocks PC1 off. That's correct root-guard
behavior and points straight at fault 4.

## Final configs
[`configs/`](configs/): the fixed, intended configuration of every node.

## Verifying the fix (Captured)
After all four fixes (SW1–SW4 + PC1 running):
```
SW1# show spanning-tree root
MST Instance           Root ID          Cost    Time  Age Dly  Root Port
MST0              4096 aabb.cc00.0600         0    2   20  15
MST1              4097 aabb.cc00.0600         0    2   20  15
MST2              4098 aabb.cc00.0700   2000000    2   20  15  Et0/0

SW1# show spanning-tree inconsistentports
Number of inconsistent ports (segments) in the system : 0

SW3# show spanning-tree mst configuration digest
Name      [LAB]
Revision  1     Instances configured 3
Digest          0x9357EBB7A8D74DD5FEF4F2BAB50531AA

SW3# show spanning-tree mst 1
Bridge        address aabb.cc00.0800  priority      32769 (32768 sysid 1)
Root          address aabb.cc00.0600  priority      4097  (4096 sysid 1)
Et0/0                            Root FWD 2000000   128.1    P2p
Et0/1                            Altn BLK 2000000   128.2    P2p
Et1/0                            Desg FWD 2000000   128.5    P2p Edge

SW3# show spanning-tree mst 2 | begin Interface
Et0/0                            Altn BLK 2000000   128.1    P2p
Et0/1                            Root FWD 2000000   128.2    P2p

SW4# show spanning-tree mst 2 | begin Interface
Et0/0                            Altn BLK 2000000   128.1    P2p
Et0/1                            Root FWD 2000000   128.2    P2p
Et1/0                            Desg FWD 2000000   128.5    P2p Edge

SW4# show interfaces status err-disabled
(empty)

PC1:~$ ping -c 3 192.168.10.1        3 packets transmitted, 3 packets received, 0% packet loss
PC1:~$ ping -c 3 192.168.20.1        3 packets transmitted, 3 packets received, 0% packet loss
```
**Expected (not run):** `PC2:~$ ping -c 3 192.168.20.1` and PC1 ↔ PC2 succeed. PC2 was stopped (5-node license)
by the time SW4 was fixed. SW4's healthy MST2 port roles above were captured, and the same topology carried PC1 ↔ PC2
traffic in the learning lab's test run.

## Testing notes
- Region mismatch with PC1 working was confirmed by re-injecting fault 3 after the fix: PC1's ping to
  192.168.10.1 recovered within about 10 seconds and root guard logged `ROOTGUARD_UNBLOCK`.
- `spanning-tree portfast trunk` is accepted as-is on IOL-L2-XE 17.18 and stays in the running config with that
  spelling.
