# Spanning Tree: RSTP, MST, Root Guard and BPDU Guard — Learning Lab

> **Blueprint:** ENCOR 3.1.c — Configure and verify common Spanning Tree Protocols (RSTP, MST) and Spanning Tree
> enhancements such as root guard and BPDU guard
> **Mode:** Learning (guided build) · **Nodes:** 7 licensed (5 switches, 2 PCs) · **Time:** ~60 min

<!--
This README is copied verbatim into the lab's CML Notes (tools/sync_notes.py), so it must read well inside CML:
plain Markdown, ASCII diagrams (no Mermaid), no links to solution files.
Order: objectives and steps first; lab access, topology and addressing in the Reference section at the bottom.
-->

## What you'll learn
- Read `show spanning-tree`: who the root is and why, and each port's role (Root / Designated / Alternate).
- Put the root where *you* want it, per VLAN, and see two VLANs block different uplinks (load sharing).
- Watch RSTP fail over in an instant, and see why access ports still stall without PortFast.
- Watch BPDU guard err-disable a port the moment a switch is plugged into it.
- Watch a rogue switch take over as root, then stop it with root guard.
- Migrate to MST: build a region, map VLANs to instances, and see what happens when one switch's region config
  doesn't match.

## Starting point
Logins, the topology diagram and the addressing table are in **Reference** at the end of this guide.

Unlike most learning labs, these switches don't boot completely blank, because trunking is a separate topic (3.1.a).
Already configured:
- VLANs 10 (SALES), 20 (ENGINEERING), 99 (MGMT) and 999 (unused native) on every switch.
- 802.1Q trunks on all five inter-switch links (allowed 10, 20, 99, native 999).
- Access ports for PC1 (SW3 e1/0, VLAN 10), PC2 (SW4 e1/0, VLAN 20), and two spare ports (SW3 e1/2 and SW4 e1/2,
  VLAN 10) that SW5 connects to.
- SW1 is the gateway (SVIs for VLANs 10, 20, 99). SW2–SW4 have a VLAN 99 management address.
- **Spanning tree is left at defaults** on SW1–SW4.
- **SW5** is a "rogue" switch, for example someone's desk switch. It runs Rapid PVST+ with priority **0** for every
  VLAN, so it beats everything. Its two ports are **shut down** until Step 4.

PCs: wait for the switches to finish booting (about a minute) before testing from PC1 or PC2.

## Step 1 — Read the default spanning tree
Look before you touch. Spanning tree is already running, and an election has already happened.

**SW1**
```
show spanning-tree summary | include mode
show spanning-tree root
```
**Output (captured)**
```
Switch is in rapid-pvst mode

Vlan                   Root ID          Cost    Time  Age Dly  Root Port
---------------- -------------------- --------- ----- --- ---  ------------
VLAN0010         32778 aabb.cc00.0a00         0    2   20  15
VLAN0020         32788 aabb.cc00.0a00         0    2   20  15
VLAN0099         32867 aabb.cc00.0a00         0    2   20  15
```
Look for:
- **Mode.** IOS-XE switches default to **Rapid PVST+**: one RSTP (802.1w) instance per VLAN. Older IOS defaulted
  to classic PVST+ (802.1D).
- **Root ID priority 32778 for VLAN 10.** That's the default 32768 plus the VLAN number. This *extended system ID*
  is why every VLAN gets a slightly different priority.
- **Who's root.** All priorities are equal, so the lowest MAC address wins. In the capture SW1 happened to win.
  Your MACs may differ: IOL derives them from the node's ID in CML. Whichever switch it is, it won by accident.

Now look at an access switch:

**SW3**
```
show spanning-tree vlan 10
```
**Output (captured, trimmed)**
```
  Root ID    Priority    32778
             Address     aabb.cc00.0a00
             Cost        100
             Port        1 (Ethernet0/0)
  Bridge ID  Priority    32778  (priority 32768 sys-id-ext 10)
             Address     aabb.cc00.0c00

Interface           Role Sts Cost      Prio.Nbr Type
------------------- ---- --- --------- -------- --------------------------------
Et0/0               Root FWD 100       128.1    P2p
Et0/1               Altn BLK 100       128.2    P2p
Et1/0               Desg FWD 100       128.5    P2p
Et1/2               Desg FWD 100       128.7    P2p
```
Look for: one **Root** port (best path to the root), one **Altn BLK** uplink (the loop-breaker, and also the
standby), and **Desg** ports facing the edge. Cost 100 is the short-mode cost of a 10 Mb/s link, which is what IOL
reports for its Ethernet ports.

> **Why:** every switch picks one root port (lowest total cost to the root, then lowest neighbor bridge ID,
> then lowest neighbor port ID). Every segment gets one designated port. Whatever's left is *alternate*, and it
> discards. RSTP renamed 802.1D's "blocking" role to *alternate* because it's a pre-computed backup root port, not
> just a dead port.

## Step 2 — Put the roots where you want them, per VLAN
The root should be a well-connected distribution switch, chosen deliberately. Make SW1 the root for VLANs 10
and 99 and SW2 the root for VLAN 20, each backing up the other. That way the two VLANs use different uplinks.

**SW1**
```
configure terminal
 spanning-tree vlan 10,99 root primary
 spanning-tree vlan 20 root secondary
end
```
**SW2**
```
configure terminal
 spanning-tree vlan 20 root primary
 spanning-tree vlan 10,99 root secondary
end
```

**Verify**
```
SW2# show running-config | include spanning-tree vlan
spanning-tree vlan 10,99 priority 28672
spanning-tree vlan 20 priority 24576

SW2# show spanning-tree root
VLAN0010         24586 aabb.cc00.0a00       100    2   20  15  Et0/0
VLAN0020         24596 aabb.cc00.0b00         0    2   20  15
VLAN0099         24675 aabb.cc00.0a00       100    2   20  15  Et0/0
```
(Captured.) `root primary` and `root secondary` are **macros**: they write a plain `priority` line (24576 and
28672 here) and don't keep watching. If someone later adds a switch with priority 4096, it wins. For a fixed design,
set `spanning-tree vlan X priority N` explicitly.

Now compare the two VLANs on an access switch:
```
SW3# show spanning-tree vlan 10 | begin Interface
Et0/0               Root FWD 100       128.1    P2p          <- to SW1
Et0/1               Altn BLK 100       128.2    P2p
SW3# show spanning-tree vlan 20 | begin Interface
Et0/0               Altn BLK 100       128.1    P2p
Et0/1               Root FWD 100       128.2    P2p          <- to SW2
```
(Captured.) Same links, opposite choices. Both uplinks now carry traffic, one per VLAN. That's the payoff of a
*per-VLAN* spanning tree.

## Step 3 — RSTP failover, and the problem with access ports
Fail SW3's VLAN 10 root port and look right away:

**SW3**
```
configure terminal
 interface Ethernet0/0
  shutdown
  do show spanning-tree vlan 10 | begin Interface
  no shutdown
end
```
**Output (captured)**
```
Et0/1               Root FWD 100       128.2    P2p
Et1/0               Desg BLK 100       128.5    P2p
Et1/2               Desg BLK 100       128.7    P2p
```
Two things to notice:
- **The uplink failed over instantly.** Et0/1 went from Alternate straight to Root **FWD**, with no 30-second
  listening/learning wait. Under 802.1D this would have taken up to 50 seconds.
- **The PC port went to BLK.** When a switch gets a new root port, RSTP's *sync* step puts all its non-edge
  designated ports into discarding until each one is either confirmed safe by a downstream switch (proposal/agreement)
  or ages through the timers. PC1 doesn't speak RSTP, so it can't agree, and Et1/0 waits out the full forward delay.
  The uplink recovered in milliseconds, but PC1 was still cut off for about 30 seconds.

The fix is to tell the switch which ports are **edge** ports. That's the next step.

## Step 4 — PortFast and BPDU guard on edge ports
`spanning-tree portfast` marks a port as an edge port. It forwards immediately and is left out of the sync.
The danger is that if someone plugs a switch into an edge port, you've let a possible loop in with no protection.
**BPDU guard** closes that hole: if a BPDU ever arrives on the port, the port is err-disabled.

**SW3**
```
configure terminal
 interface range Ethernet1/0 , Ethernet1/2
  spanning-tree portfast
  spanning-tree bpduguard enable
end
```
**SW4**
```
configure terminal
 interface Ethernet1/0
  spanning-tree portfast
  spanning-tree bpduguard enable
end
```
IOS warns that PortFast is only safe on single-host ports. That warning is the reason BPDU guard exists.

**Verify:** repeat the Step 3 failover test. This time the PC ports stay forwarding and are marked **Edge** (Captured):
```
Et0/1               Root FWD 100       128.2    P2p
Et1/0               Desg FWD 100       128.5    P2p Edge
Et1/2               Desg FWD 100       128.7    P2p Edge
```

Now "plug in" the rogue switch on SW3's spare desk port:

**SW5**
```
configure terminal
 interface Ethernet0/0
  no shutdown
end
```
**SW3: what happens (captured)**
```
%SPANTREE-2-BLOCK_BPDUGUARD: Received BPDU from bridge aabb.cc00.0e00 on port Et1/2 with BPDU Guard enabled. Disabling port.
%PM-4-ERR_DISABLE: bpduguard error detected on Et1/2, putting Et1/2 in err-disable state

SW3# show interfaces status err-disabled
Port         Name         Status       Reason               Err-disabled Vlans
Et1/2        spare desk p err-disabled bpduguard

SW3# show errdisable recovery | include bpduguard|Timer
bpduguard                    Disabled
Timer interval: 300 seconds
```
The first BPDU from SW5 killed the port. SW5's priority 0 never got a chance to matter: `show spanning-tree root`
on SW1 still shows SW1 as root for VLAN 10. Auto-recovery is **off** by default, so the port stays down until
someone fixes the cause and bounces it (`shutdown` / `no shutdown`), or until you enable
`errdisable recovery cause bpduguard`.

> **Why:** BPDU guard doesn't care whether the BPDU is superior or inferior. On an edge port, *any* BPDU means a
> switch is there, and that's a policy violation.

## Step 5 — Root guard: when a switch is allowed, but not as root
Sometimes a port legitimately connects to another switch, such as a lab bench or a customer's switch, so BPDU guard
would be wrong. But that switch must never become root. That's what **root guard** is for. First, see what
happens *without* it.

**SW5**
```
configure terminal
 interface Ethernet0/1
  no shutdown
end
```
**SW1 (captured)**
```
SW1# show spanning-tree root
VLAN0010            10 aabb.cc00.0e00       200    2   20  15  Et0/2
VLAN0020         24596 aabb.cc00.0b00       100    2   20  15  Et0/0
VLAN0099         24675 aabb.cc00.0a00         0    2   20  15
```
SW5 (priority 0 + VLAN 10 = **10**) is now root for VLAN 10. Your distribution switch SW1 now has a *root port*
pointing down through an access switch to a desk switch. All VLAN 10 traffic between the distribution switches
now converges toward SW5. This is the outage root guard prevents.

Turn root guard on where SW5 connects:

**SW4**
```
configure terminal
 interface Ethernet1/2
  spanning-tree guard root
end
```
**Verify (captured)**
```
%SPANTREE-2-ROOTGUARD_BLOCK: Received a superior STP BPDU from bridge aabb.cc00.0e00. Root guard blocking port Ethernet1/2 on VLAN0010.

SW4# show spanning-tree inconsistentports
Name                 Interface                      Inconsistency
VLAN0010             Ethernet1/2                    Root Inconsistent

SW4# show spanning-tree vlan 10 | begin Interface
Et0/0               Root FWD 100       128.1    P2p
Et0/1               Altn BLK 100       128.2    P2p
Et1/2               Desg BKN*100       128.7    P2p *ROOT_Inc

SW1# show spanning-tree root
VLAN0010         24586 aabb.cc00.0a00         0    2   20  15
```
SW1 is root again. The port isn't err-disabled. It sits in **root-inconsistent** (`BKN*`) only while superior
BPDUs keep arriving, and only for the affected VLAN.

Unplug the rogue and watch both guards recover differently:

**SW5**
```
configure terminal
 interface range Ethernet0/0 - 1
  shutdown
end
```
```
SW4# show logging | include ROOTGUARD_UNBLOCK
%SPANTREE-2-ROOTGUARD_UNBLOCK: Root guard unblocking port Ethernet1/2 on VLAN0010.
```
(Captured.) Root guard recovers **by itself**. BPDU guard doesn't: SW3 Et1/2 is still err-disabled. Recover it by hand:

**SW3**
```
configure terminal
 interface Ethernet1/2
  shutdown
  no shutdown
end
```

> **Why the difference:** BPDU guard says "no switch may ever be here", so it shuts the port. Root guard says
> "a switch may be here, but it may not win", so it only refuses the superior information and forwards again
> once that information stops.

## Step 6 — Migrate to MST
Rapid PVST+ runs one spanning-tree instance per VLAN. With 500 VLANs that's 500 instances, each sending BPDUs every
2 seconds on every trunk, even though you only want two different topologies. **MST (802.1s)** maps many VLANs onto
a few instances. Here, instance 1 carries VLAN 10 (rooted at SW1) and instance 2 carries VLAN 20 (rooted at SW2).
Everything else, including VLAN 99, stays in instance 0, the IST.

Switches only share MST instances if they're in the **same region**. A region is defined by three values that
must match exactly: the **name**, the **revision number**, and the **VLAN-to-instance mapping**.

**SW1**
```
configure terminal
 spanning-tree mst configuration
  name LAB
  revision 1
  instance 1 vlan 10
  instance 2 vlan 20
  show pending
  exit
 spanning-tree mode mst
 spanning-tree mst 0-1 priority 4096
 spanning-tree mst 2 priority 8192
 no spanning-tree vlan 10,99 priority
 no spanning-tree vlan 20 priority
end
```
`show pending` displays the region config you're about to apply. It only takes effect when you leave the
sub-mode. The last two lines remove the Rapid PVST+ priorities, which MST ignores.

Before you configure the others, look at SW1 as the only MST switch among Rapid PVST+ neighbors (Captured):
```
SW1# show spanning-tree mst 0 | begin Interface
Et0/0                            Desg LRN 2000000   128.1    P2p Bound(PVST)
Et0/1                            Desg LRN 2000000   128.2    P2p Bound(PVST)
Et0/2                            Desg LRN 2000000   128.3    P2p Bound(PVST)
```
- **Bound(PVST)**: each port is a region boundary facing a PVST+ switch. MST interoperates through *PVST
  simulation*, so the network keeps working during a migration, one switch at a time.
- **Cost 2000000**: MST uses *long* path costs (10 Mb/s = 2,000,000), not the short-mode 100 you saw earlier.

**SW2** (mirror priorities)
```
configure terminal
 spanning-tree mst configuration
  name LAB
  revision 1
  instance 1 vlan 10
  instance 2 vlan 20
  exit
 spanning-tree mode mst
 spanning-tree mst 0-1 priority 8192
 spanning-tree mst 2 priority 4096
 no spanning-tree vlan 10,99 priority
 no spanning-tree vlan 20 priority
end
```
**SW3** and **SW4** (region only, default priority)
```
configure terminal
 spanning-tree mst configuration
  name LAB
  revision 1
  instance 1 vlan 10
  instance 2 vlan 20
  exit
 spanning-tree mode mst
end
```

**Verify (captured)**
```
SW4# show spanning-tree mst configuration digest
Name      [LAB]
Revision  1     Instances configured 3
Digest          0x9357EBB7A8D74DD5FEF4F2BAB50531AA

SW1# show spanning-tree root
MST Instance           Root ID          Cost    Time  Age Dly  Root Port
MST0              4096 aabb.cc00.0a00         0    2   20  15
MST1              4097 aabb.cc00.0a00         0    2   20  15
MST2              4098 aabb.cc00.0b00   2000000    2   20  15  Et0/0

SW4# show spanning-tree mst 2 | begin Interface
Et0/0                            Altn BLK 2000000   128.1    P2p
Et0/1                            Root FWD 2000000   128.2    P2p
Et1/0                            Desg FWD 2000000   128.5    P2p Edge
```
The **digest** is a hash of the VLAN-to-instance table. Switches compare the name, the revision and this digest,
not the table itself. Run the digest command on all four switches: the numbers must be identical. There's no
`Bound` flag anywhere now, because it's one region. And per-VLAN load sharing is back, now with only three
instances. PortFast, BPDU guard and root guard all carried over: they're per-port features, independent of the
STP mode.

## Step 7 — Break the region (on purpose)
Change one value on one switch:

**SW4**
```
configure terminal
 spanning-tree mst configuration
  revision 2
end
```
**SW4 (captured)**
```
SW4# show spanning-tree mst 0 | include Root|Regional|Et0
Root          address aabb.cc00.0a00  priority      4096  (4096 sysid 0)
Regional Root this switch
Et0/0                            Root FWD 2000000   128.1    P2p Bound(RSTP)
Et0/1                            Altn BLK 2000000   128.2    P2p Bound(RSTP)

SW4# show spanning-tree mst 2
##### MST2    vlans mapped:   20
Root          this switch for MST2
Et0/0                            Mstr FWD 2000000   128.1    P2p Bound(RSTP)
Et0/1                            Altn BLK 2000000   128.2    P2p Bound(RSTP)
Et1/0                            Desg FWD 2000000   128.5    P2p Edge
```
SW4 is now a region of one. It's its own *regional root*, it thinks it's root for MST2, and both uplinks are
**Bound**. Across a boundary only the CIST (instance 0) is negotiated, so every instance on SW4 follows the CIST
port roles. VLAN 20 now leaves via SW1 (`Mstr` = master port, the CIST root port) instead of SW2. Nothing is
down, so nobody would file a ticket, but the design is quietly broken. That's why region mismatches are a favorite
troubleshooting topic.

Put it back:

**SW4**
```
configure terminal
 spanning-tree mst configuration
  revision 1
end
```
`show spanning-tree mst 2` on SW4 again shows Et0/1 (to SW2) as the root port.

## Final check
- `show spanning-tree root` on SW1: MST0 and MST1 rooted at SW1, MST2 at SW2.
- `show spanning-tree mst configuration digest` is identical on SW1–SW4.
- From PC1: `ping -c 3 192.168.10.1`, `ping -c 3 192.168.20.10` (PC2), `ping -c 3 192.168.99.204` (SW4) all succeed.
- SW5's ports are shut down, and no port is err-disabled (`show interfaces status err-disabled` is empty on SW3).

## Check yourself
1. Two switches with priority 32768 compete for root in VLAN 20. What decides it, and why does VLAN 20's root
   priority show as 32788?
2. In Step 3 the uplink recovered instantly, but PC1 still lost connectivity. Why, and which command fixed it?
3. BPDU guard and root guard both react to BPDUs. Which one would you put on a port facing a customer's switch,
   and which on a port facing a user's desk? Which one recovers by itself?
4. `spanning-tree vlan 10 root primary` set priority 24576. What happens if a new switch with priority 16384 is
   added later?
5. Name the three values that must match for two MST switches to be in the same region. What did SW4 do with VLAN
   20's traffic when its revision didn't match, and why?

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| SW1–SW5 | IOL-L2-XE switch | cisco | cisco | cisco |
| PC1, PC2 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → **Console**). Switches drop you straight into privileged EXEC.
Each node also has a label on the canvas with its login and addresses.

## Topology

```
                    e0/0              e0/0
              SW1 -------------------------- SW2
       distribution, gateway            distribution
          e0/1 |    e0/2 `.          .' e0/1   | e0/2
               |           `.      .'          |
               |             `.  .'            |
               |               ><              |
               |             .'  `.            |
               |           .'      `.          |
          e0/0 |    e0/1 .'          `. e0/0   | e0/1
              SW3                            SW4
          e1/0 |  e1/2 \                  / e1/2 | e1/0
               |        \                /       |
              PC1        e0/0  SW5  e0/1        PC2
           VLAN 10        rogue switch        VLAN 20
                       (ports shut at boot)

  Uplinks: SW1 e0/1-SW3 e0/0, SW1 e0/2-SW4 e0/0, SW2 e0/1-SW3 e0/1, SW2 e0/2-SW4 e0/1, SW1 e0/0-SW2 e0/0
  All five are 802.1Q trunks (VLANs 10, 20, 99; native 999).
```

## Addressing

| Node | Interface | IPv4 | Notes |
|---|---|---|---|
| SW1 | Vlan10 / Vlan20 / Vlan99 | 192.168.10.1 / 192.168.20.1 / 192.168.99.1 | gateway for all VLANs |
| SW2 | Vlan99 | 192.168.99.202/24 | |
| SW3 | Vlan99 | 192.168.99.203/24 | |
| SW4 | Vlan99 | 192.168.99.204/24 | |
| SW5 | Vlan10 | 192.168.10.205/24 | rogue switch |
| PC1 | eth0 | 192.168.10.10/24, gw .1 | SW3 e1/0, VLAN 10 |
| PC2 | eth0 | 192.168.20.10/24, gw .1 | SW4 e1/0, VLAN 20 |
