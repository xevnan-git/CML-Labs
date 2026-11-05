# Multicast (PIM-SM, IGMP, SSM) — Learning Lab

> **Blueprint:** ENCOR 3.3.d — Describe multicast protocols, such as RPF check, PIM SM, IGMP v2/v3, SSM, bidir,
> and MSDP
> **Mode:** Learning (guided build) · **Nodes:** 5 licensed (3 routers, 2 IOL hosts) · **Time:** ~75 min

<!--
This README is copied verbatim into the lab's CML Notes (tools/sync_notes.py), so it must read well inside CML:
plain Markdown, ASCII diagrams (no Mermaid), no links to solution files.
Order: objectives and steps first; lab access, topology and addressing in the Reference section at the bottom.
-->

## What you'll learn
- Turn on **multicast routing** and **PIM sparse mode**, and read `show ip pim neighbor` / `interface`.
- See how a receiver asks for a group with **IGMP**, and how the last-hop router turns that into PIM state.
- Why sparse mode needs a **rendezvous point (RP)**, and what happens without one.
- Watch the **shared tree** (rooted at the RP) switch to the **shortest-path tree** (rooted at the source), and read
  the `S`, `J`, `T`, `P`, `F` flags in `show ip mroute`.
- Watch the **RPF check** drop a duplicate packet, break a tree, and get fixed with a **static mroute**.
- Use **IGMPv3** and **SSM** (232.0.0.0/8): no RP at all.
- See **bidirectional PIM** (one shared tree, no source state) and **MSDP** (RPs telling each other about sources).

## Starting point
Logins, the topology diagram and the addressing table are in **Reference** at the end of this guide.

- **R1**, **R2** and **R3** form a triangle and run OSPF. **R2** will be the RP, and it's deliberately *not* on the
  shortest path between the source and the receiver.
- **SRV1** (behind R1) is the multicast source and **PC1** (behind R3) the receiver. Both are IOL-XE routers acting
  as hosts: a router answers a ping to a group it has joined, so `ping 239.1.1.1` on SRV1 shows exactly which
  receivers got each packet. (A Linux host ignores pings to multicast addresses by default.)
- Unicast works end to end. No multicast is configured anywhere.
- **You configure R1, R2, R3 and PC1's IGMP joins.** SRV1 only runs pings.

**The goal:** SRV1's pings to **239.1.1.1** (any-source multicast), **232.1.1.1** (source-specific) and
**239.2.2.2** (bidir) all get a reply from PC1.

Wait about a minute after starting the lab, until the routers finish booting, before you test.

> **Tip:** multicast state is created by the first packets and by periodic messages, so the first ping after a change
> can be lost. If a ping fails right after a change, give it a few seconds and send it again before you debug.

## Step 1 — Baseline: unicast works, multicast doesn't
**SRV1**
```
ping 192.168.20.10
ping 239.1.1.1 repeat 2
```
**R3**
```
show ip multicast
show ip mroute
```
**Output (captured)**
```
SRV1# ping 192.168.20.10
!!!!!
Success rate is 100 percent (5/5), round-trip min/avg/max = 1/1/2 ms
SRV1# ping 239.1.1.1 repeat 2
Sending 2, 100-byte ICMP Echos to 239.1.1.1, timeout is 2 seconds:
..

R3# show ip multicast
  Multicast Routing: disabled
R3# show ip mroute
IP Multicast Routing Table
Flags: D - Dense, S - Sparse, B - Bidir Group, s - SSM Group, C - Connected,
       L - Local, P - Pruned, R - RP-bit set, F - Register flag,
       T - SPT-bit set, J - Join SPT, M - MSDP created entry, E - Extranet,
       ...
IP Multicast Forwarding is not enabled.
```
A router doesn't forward multicast unless told to. The legend at the top of `show ip mroute` lists every flag; the
ones that matter here are **S** sparse, **C** connected receiver, **J** join SPT, **T** on the SPT, **P** pruned,
**F** register (the source is directly connected), **s** SSM, **B** bidir. Later steps filter the output with
`| begin \(` to skip the legend.

## Step 2 — Multicast routing and PIM sparse mode
On **R1, R2 and R3**, enable multicast routing and PIM sparse mode on **every** interface, including Loopback0:
**R1** (R2 and R3: the same, with their own interfaces; R2 has only Ethernet0/0 and Ethernet0/1)
```
configure terminal
ip multicast-routing
interface Loopback0
 ip pim sparse-mode
interface Ethernet0/0
 ip pim sparse-mode
interface Ethernet0/1
 ip pim sparse-mode
interface Ethernet0/2
 ip pim sparse-mode
end
```
**R3**
```
show ip pim neighbor
show ip pim interface
show ip igmp interface Ethernet0/0
```
**Output (captured)**
```
R3# show ip pim neighbor
Neighbor          Interface                Uptime/Expires    Ver   DR
Address                                                            Prio/Mode
10.1.3.1          Ethernet0/1              00:00:18/00:01:25 v2    1 / S P G
10.2.3.2          Ethernet0/2              00:00:18/00:01:26 v2    1 / S P G

R3# show ip pim interface
Address          Interface                Ver/   Nbr    Query  DR         DR
                                          Mode   Count  Intvl  Prior
10.255.255.3     Loopback0                v2/S   0      30     1          10.255.255.3
192.168.20.1     Ethernet0/0              v2/S   0      30     1          192.168.20.1
10.1.3.3         Ethernet0/1              v2/S   1      30     1          10.1.3.3
10.2.3.3         Ethernet0/2              v2/S   1      30     1          10.2.3.3

R3# show ip igmp interface Ethernet0/0
Ethernet0/0 is up, line protocol is up
  IGMP is enabled on interface
  Current IGMP host version is 2
  Current IGMP router version is 2
  IGMP query interval is 60 seconds
  ...
  Multicast designated router (DR) is 192.168.20.1 (this system)
  IGMP querying router is 192.168.20.1 (this system)
```
> **Why each piece:** `ip multicast-routing` turns on the multicast forwarding table. `ip pim sparse-mode` on an
> interface does two things: it sends **PIM hellos** (224.0.0.13, every 30 s) to find PIM neighbors, and it turns
> on **IGMP** there, so the router listens for hosts. That's why R3's LAN interface, with no PIM neighbor, still
> needs it: it's where IGMP runs. **IGMPv2 is the default.** The **DR** on a LAN is the router that sends joins
> for the hosts (and registers sources); the **IGMP querier** asks the hosts which groups they want, every 60 s.
> Sparse mode means nothing is forwarded until someone explicitly **joins**. (Dense mode, the opposite, floods
> everywhere and prunes back; nobody designs with it any more.)

## Step 3 — A receiver joins, but there's no RP
**PC1** joins 239.1.1.1. `ip igmp join-group` makes the router behave like a host that wants the group:
```
configure terminal
interface Ethernet0/0
 ip igmp join-group 239.1.1.1
end
```
**R3**
```
show ip igmp groups
show ip mroute 239.1.1.1 | begin \(
```
Then **SRV1** `ping 239.1.1.1 repeat 3`, and on **R1** `show ip mroute | begin \(`.

**Output (captured)**
```
R3# show ip igmp groups
IGMP Connected Group Membership
Group Address    Interface                Uptime    Expires   Last Reporter   Group Accounted
239.1.1.1        Ethernet0/0              00:00:20  00:02:39  192.168.20.10
224.0.1.40       Loopback0                00:00:58  00:02:01  10.255.255.3

R3# show ip mroute 239.1.1.1 | begin \(
(*, 239.1.1.1), 00:00:20/00:02:39, RP 0.0.0.0, flags: SJC
  Incoming interface: Null, RPF nbr 0.0.0.0
  Outgoing interface list:
    Ethernet0/0, Forward/Sparse, 00:00:20/00:02:39, flags:

SRV1# ping 239.1.1.1 repeat 3
...

R1# show ip mroute | begin \(
(*, 224.0.1.40), 00:04:00/00:02:00, RP 0.0.0.0, flags: DCL
  Incoming interface: Null, RPF nbr 0.0.0.0
  Outgoing interface list:
    Loopback0, Forward/Sparse, 00:03:58/00:02:00, flags:
```
> **What happened:** PC1 sent an **IGMP membership report** for 239.1.1.1 and R3 recorded it (Last Reporter
> 192.168.20.10). R3 created a **(\*,G)** entry, "any source, group 239.1.1.1", with its LAN in the outgoing list
> (**C**: connected receiver). But the incoming interface is **Null**, because in sparse mode a router joins
> *toward the RP* and there isn't one (RP 0.0.0.0). On the source side, R1 receives SRV1's packets, has no RP to
> tell, and drops them without creating any state for 239.1.1.1. (224.0.1.40 is a group every Cisco PIM router
> joins on its own, for Auto-RP. Ignore it.)
>
> The RP is the meeting point: receivers' routers join toward it, sources' routers register with it, so neither
> side needs to know where the other is.

## Step 4 — A static RP: the shared tree
Tell **R1, R2 and R3** that R2's Loopback0 is the RP for all groups:
```
configure terminal
ip pim rp-address 10.255.255.2
end
```
**R3**
```
show ip pim rp mapping
show ip rpf 10.255.255.2
show ip mroute 239.1.1.1 | begin \(
```
**R2**
```
show ip mroute 239.1.1.1 | begin \(
```
**Output (captured)**
```
R3# show ip pim rp mapping
PIM Group-to-RP Mappings

Group(s): 224.0.0.0/4, Static
    RP: 10.255.255.2 (?)

R3# show ip rpf 10.255.255.2
RPF information for ? (10.255.255.2)
  RPF interface: Ethernet0/2
  RPF neighbor: ? (10.2.3.2)
  RPF route/mask: 10.255.255.2/32
  RPF type: unicast (ospf 1)

R3# show ip mroute 239.1.1.1 | begin \(
(*, 239.1.1.1), 00:04:00/00:02:24, RP 10.255.255.2, flags: SJC
  Incoming interface: Ethernet0/2, RPF nbr 10.2.3.2
  Outgoing interface list:
    Ethernet0/0, Forward/Sparse, 00:04:00/00:02:24, flags:

R2# show ip mroute 239.1.1.1 | begin \(
(*, 239.1.1.1), 00:00:34/00:03:10, RP 10.255.255.2, flags: S
  Incoming interface: Null, RPF nbr 0.0.0.0
  Outgoing interface list:
    Ethernet0/1, Forward/Sparse, 00:00:34/00:03:10, flags:
```
> **The shared tree (RPT):** R3 looked up the RP's address in the unicast routing table (`show ip rpf`: out
> Ethernet0/2, neighbor R2) and sent a **PIM (\*,G) join** that way. R2 is the RP, so the tree ends there: its
> incoming interface is Null, and Ethernet0/1 (toward R3) is now in its outgoing list. The path from the RP down
> to the receivers is the **shared tree**, the same for every source of the group. Every router must agree on the
> RP: a static RP has to be configured identically everywhere. (Auto-RP and BSR distribute it automatically.)
>
> **RPF** (reverse path forwarding) shows up for the first time here: multicast trees are built *backwards*, from
> the receiver toward the root, along the unicast route to the root. `show ip rpf <root>` is the question
> "which interface leads back to it?".

## Step 5 — The source sends: register, then the shortest-path tree
**SRV1**
```
ping 239.1.1.1 repeat 5
```
Then look at all three routers: `show ip mroute 239.1.1.1 | begin \(`.

**Output (captured)**
```
SRV1# ping 239.1.1.1 repeat 5
Sending 5, 100-byte ICMP Echos to 239.1.1.1, timeout is 2 seconds:
Reply to request 0 from 192.168.20.10, 2 ms
Reply to request 1 from 192.168.20.10, 2 ms
Reply to request 2 from 192.168.20.10, 3 ms
Reply to request 3 from 192.168.20.10, 2 ms
Reply to request 4 from 192.168.20.10, 2 ms

R1# show ip mroute 239.1.1.1 | begin \(
(*, 239.1.1.1), 00:02:09/stopped, RP 10.255.255.2, flags: SPF
  Incoming interface: Ethernet0/1, RPF nbr 10.1.2.2
  Outgoing interface list: Null

(192.168.10.10, 239.1.1.1), 00:02:09/00:01:22, flags: FT
  Incoming interface: Ethernet0/0, RPF nbr 0.0.0.0
  Outgoing interface list:
    Ethernet0/2, Forward/Sparse, 00:02:09/00:03:18, flags:

R2# show ip mroute 239.1.1.1 | begin \(
(*, 239.1.1.1), 00:03:28/00:03:14, RP 10.255.255.2, flags: S
  Incoming interface: Null, RPF nbr 0.0.0.0
  Outgoing interface list:
    Ethernet0/1, Forward/Sparse, 00:03:28/00:03:14, flags:

(192.168.10.10, 239.1.1.1), 00:01:53/00:01:10, flags: PT
  Incoming interface: Ethernet0/0, RPF nbr 10.1.2.1
  Outgoing interface list: Null

R3# show ip mroute 239.1.1.1 | begin \(
(*, 239.1.1.1), 00:06:13/stopped, RP 10.255.255.2, flags: SJC
  Incoming interface: Ethernet0/2, RPF nbr 10.2.3.2
  Outgoing interface list:
    Ethernet0/0, Forward/Sparse, 00:06:13/00:02:16, flags:

(192.168.10.10, 239.1.1.1), 00:00:58/00:02:01, flags: JT
  Incoming interface: Ethernet0/1, RPF nbr 10.1.3.1
  Outgoing interface list:
    Ethernet0/0, Forward/Sparse, 00:00:58/00:02:16, flags:
```
Read it as a story, in order:
1. **Register:** R1 is the DR for SRV1's LAN (**F**: register flag, the source is directly connected). It wrapped
   the first packets in unicast **PIM register** messages to the RP.
2. **Down the shared tree:** R2 unwrapped them and sent them down the shared tree (R2 → R3 → PC1), then joined
   toward the source itself with an **(S,G)** join, so R1 started sending natively and R2 told R1 to stop
   registering (**register-stop**).
3. **SPT switchover:** as soon as R3 saw traffic from 192.168.10.10, it joined the **shortest-path tree** for that
   source: an (S,G) join toward SRV1 by RPF, out Ethernet0/1 straight to R1 (**J**, then **T** once traffic
   arrived that way). R1 added Ethernet0/2 to its (S,G) outgoing list.
4. **Prune:** R3 then pruned the source off the shared tree, so R2's (S,G) is now **P**runed with a Null
   outgoing list. The traffic flows R1 → R3 directly and the RP isn't on the path any more.

> **Why switch?** The shared tree is the same for all sources, so it's often a detour through the RP (R1 → R2 → R3
> here, against R1 → R3). Cisco routers switch to the SPT on the first packet by default (**SPT threshold 0**).
> The RP is only needed to *introduce* sources to receivers.

## Step 6 — Stay on the shared tree, and meet the RPF check
On **R3**, keep the traffic on the shared tree, then clear the state to start over:
```
configure terminal
ip pim spt-threshold infinity
end
clear ip mroute *
```
`clear ip mroute *` removes R3's (\*,G) too; it comes back with PC1's next IGMP report (within a minute: watch
`show ip mroute 239.1.1.1` on R3). Then **SRV1** `ping 239.1.1.1 repeat 5` and on **R3**:
```
show ip mroute 239.1.1.1 | begin \(
show ip mroute count | begin 239
```
**Output (captured)**
```
R3# show ip mroute 239.1.1.1 | begin \(
(*, 239.1.1.1), 00:00:48/00:02:11, RP 10.255.255.2, flags: SC
  Incoming interface: Ethernet0/2, RPF nbr 10.2.3.2
  Outgoing interface list:
    Ethernet0/0, Forward/Sparse, 00:00:48/00:02:11, flags:

R3# show ip mroute count | begin 239
Group: 239.1.1.1, Source count: 0, Packets forwarded: 5, Packets received: 10
  RP-tree: Forwarding: 5/0/100/0, Other: 10/5/0

R2# show ip mroute 239.1.1.1 | begin \(
(192.168.10.10, 239.1.1.1), 00:04:17/00:01:31, flags: T
  Incoming interface: Ethernet0/0, RPF nbr 10.1.2.1
  Outgoing interface list:
    Ethernet0/1, Forward/Sparse, 00:01:03/00:03:25, flags:

R1# show ip mroute 239.1.1.1 | begin \(
(192.168.10.10, 239.1.1.1), 00:04:37/00:01:42, flags: FT
  Incoming interface: Ethernet0/0, RPF nbr 0.0.0.0
  Outgoing interface list:
    Ethernet0/1, Forward/Sparse, 00:01:23/00:02:51, flags:
    Ethernet0/2, Forward/Sparse, 00:04:37/00:00:50, flags:
```
R3 now has only the (\*,G): no **J** flag, no (S,G), and the traffic comes R1 → R2 → R3.

**The RPF check at work.** R3 *received* 10 packets but forwarded 5, and the "Other" counters say
**10 total / 5 RPF failed / 0 other drops**. Why 10? R1 still had its old SPT branch toward R3 (Ethernet0/2,
expiring in 50 s, because only R3's state was cleared), so every ping reached R3 twice: once via R2 and once
directly from R1. For a (\*,G) the **RPF interface is the one toward the RP** (Ethernet0/2). The copy from R1
arrived on Ethernet0/1, failed the RPF check and was dropped. Your counts may differ, depending on how long after
the clear you ping. Once R1's branch expires, the RPF failures stop.

> **The RPF check** is multicast's loop prevention: a router accepts a multicast packet only on the interface it
> would use to reach the packet's *source* (for an (S,G)) or the *RP* (for a (\*,G)), and drops it on any other
> interface. Unicast forwarding looks at where a packet is going; multicast looks at where it came from.

Undo the threshold before the next step (**R3**: `no ip pim spt-threshold infinity` in global config).

## Step 7 — An RPF failure and the static mroute
Pretend the **R2–R3 link can't run multicast** (some provider links can't). On **R2** Ethernet0/1 and **R3**
Ethernet0/2: `no ip pim sparse-mode`. Then on **R3**:
```
show ip rpf 10.255.255.2
show ip mroute 239.1.1.1 | begin \(
```
and **SRV1** `ping 239.1.1.1 repeat 5`.

**Output (captured)**
```
R3# show ip rpf 10.255.255.2
 failed, no route exists
R3# show ip mroute 239.1.1.1 | begin \(
(*, 239.1.1.1), 00:06:56/00:02:01, RP 10.255.255.2, flags: SJC
  Incoming interface: Null, RPF nbr 0.0.0.0
  Outgoing interface list:
    Ethernet0/0, Forward/Sparse, 00:06:56/00:02:01, flags:

SRV1# ping 239.1.1.1 repeat 5
.....
```
Unicast to the RP still goes over that link (OSPF doesn't care about PIM), but the RPF lookup only accepts an
interface that runs PIM, so R3 has **no RPF path to the RP**. Its (\*,G) has a Null incoming interface, no join
reaches R2, and the source and receiver never meet. This is the classic **incongruent topology**: the unicast and
multicast topologies differ.

The fix is a **static mroute**: an entry in a separate *multicast* RPF table that overrides the unicast route for
the RPF check only. On **R3**, use R1 (which has PIM toward R2) to reach the RP:
```
configure terminal
ip mroute 10.255.255.2 255.255.255.255 10.1.3.1
end
show ip rpf 10.255.255.2
show ip mroute 239.1.1.1 | begin \(
```
**Output (captured)**
```
R3# show ip rpf 10.255.255.2
RPF information for ? (10.255.255.2)
  RPF interface: Ethernet0/1
  RPF neighbor: ? (10.1.3.1)
  RPF route/mask: 10.255.255.2/32
  RPF type: multicast (static)

R3# show ip mroute 239.1.1.1 | begin \(
(*, 239.1.1.1), 00:08:03/00:02:51, RP 10.255.255.2, flags: SJC
  Incoming interface: Ethernet0/1, RPF nbr 10.1.3.1, Mroute
  Outgoing interface list:
    Ethernet0/0, Forward/Sparse, 00:08:03/00:02:51, flags:

SRV1# ping 239.1.1.1 repeat 5
Reply to request 0 from 192.168.20.10, 19 ms
Reply to request 1 from 192.168.20.10, 2 ms
...
```
"RPF type: multicast (static)" and "Mroute" on the incoming interface show that the static entry won. Unicast
traffic to 10.255.255.2 still uses the R2–R3 link; only the RPF check changed. (The other common fix is a
multicast-only route from BGP, MP-BGP's IPv4 multicast address family, which does the same thing dynamically.)

**Put the design back** before the next step: on **R3** `no ip mroute 10.255.255.2 255.255.255.255 10.1.3.1`, and
`ip pim sparse-mode` again on R2 Ethernet0/1 and R3 Ethernet0/2.

> **One-sided PIM is different.** If only R1's end of the R1–R3 link loses PIM, R3's RPF toward SRV1 still points
> at R1 (R3's side runs PIM), its SPT join goes unanswered, and IOS-XE simply keeps the traffic on the shared tree
> via R2: no loss, only a detour. A link without PIM where the *RP* is involved, like the one above, does break
> things.

## Step 8 — IGMPv3 and SSM: no RP at all
**Source-specific multicast** lets the receiver name the source as well as the group, so the last-hop router can
join the SPT immediately and no RP is needed. It uses the **232.0.0.0/8** range and needs **IGMPv3**, the only
IGMP version whose reports carry sources.

On **R1, R2 and R3**: `ip pim ssm default` (global config: treat 232/8 as SSM). On **R3**:
```
interface Ethernet0/0
 ip igmp version 3
```
On **PC1**, first try joining an (S,G) while PC1 still runs IGMPv2:
```
configure terminal
interface Ethernet0/0
 ip igmp join-group 232.1.1.1 source 192.168.10.10
end
show ip igmp interface Ethernet0/0 | include version
```
and **R3** `show ip igmp groups`, **SRV1** `ping 232.1.1.1 repeat 3`.

**Output (captured)**
```
PC1# show ip igmp interface Ethernet0/0 | include version
  Current IGMP host version is 2
  Current IGMP router version is 2

R3# show ip igmp groups
Group Address    Interface                Uptime    Expires   Last Reporter   Group Accounted
239.1.1.1        Ethernet0/0              00:19:45  00:01:57  192.168.20.10
224.0.1.40       Loopback0                00:20:24  00:02:37  10.255.255.3

SRV1# ping 232.1.1.1 repeat 3
...
```
IOS accepts the command, but an IGMPv2 host has no way to send a source, so nothing reaches R3, and R1 drops
SRV1's 232.1.1.1 packets without creating any state (in the SSM range there's no RP to register with). Now
**PC1** `ip igmp version 3` on Ethernet0/0, and look again:
```
R3# show ip igmp groups 232.1.1.1 detail
Interface:      Ethernet0/0
Group:          232.1.1.1
Flags:          SSM
Group mode:     INCLUDE
Last reporter:  192.168.20.10
  Source Address   Uptime    v3 Exp   CSR Exp   Fwd  Flags
  192.168.10.10    00:00:18  00:02:42  stopped   Yes  R

R3# show ip mroute 232.1.1.1 | begin \(
(192.168.10.10, 232.1.1.1), 00:00:18/00:02:41, flags: sTI
  Incoming interface: Ethernet0/1, RPF nbr 10.1.3.1
  Outgoing interface list:
    Ethernet0/0, Forward/Sparse, 00:00:18/00:02:41, flags:

SRV1# ping 232.1.1.1 repeat 3
Reply to request 0 from 192.168.20.10, 2 ms
Reply to request 1 from 192.168.20.10, 3 ms
Reply to request 2 from 192.168.20.10, 2 ms

R1# show ip mroute 232.1.1.1 | begin \(
(192.168.10.10, 232.1.1.1), 00:01:14/00:03:13, flags: sT
  Incoming interface: Ethernet0/0, RPF nbr 0.0.0.0
  Outgoing interface list:
    Ethernet0/2, Forward/Sparse, 00:01:14/00:03:13, flags:
```
R3 built the (S,G) **before any packet was sent** (**s**: SSM, **I**: from a source-specific host report), joined
straight toward R1, and there's no (\*,G) and no RP anywhere: `show ip mroute 232.1.1.1` on R2 is empty.

| | IGMPv2 | IGMPv3 |
|---|---|---|
| Report says | "I want group G" | "I want G **from** sources S1, S2" (INCLUDE) or "from anyone except…" (EXCLUDE) |
| Leave | explicit Leave message, router sends group-specific queries | state change report |
| SSM | no | yes |
| Router-side default on IOS | yes | `ip igmp version 3` |

A v3 host on a LAN whose querier runs v2 falls back to v2 (that's why PC1's host version followed R3's), so the
**router's** IGMP version decides whether SSM can work on that LAN.

## Step 9 — Bidirectional PIM
In bidir PIM, traffic flows *up* the shared tree to the RP and *down* to the receivers on the same tree, with no
registers and no (S,G) state: ideal for many-to-many applications where every host is also a source. Use R1 as the
bidir RP for 239.2.0.0/16. On **R1, R2 and R3**:
```
configure terminal
ip pim bidir-enable
ip access-list standard BIDIR-GROUPS
 permit 239.2.0.0 0.0.255.255
exit
ip pim rp-address 10.255.255.1 BIDIR-GROUPS bidir
end
```
**PC1**: `ip igmp join-group 239.2.2.2` on Ethernet0/0. Then **R3**:
```
show ip pim rp mapping
show ip pim interface df
show ip mroute 239.2.2.2 | begin \(
```
**Output (captured)**
```
R3# show ip pim rp mapping
Group(s): 224.0.0.0/4, Static
    RP: 10.255.255.2 (?)
Acl: BIDIR-GROUPS, Static, Bidir Mode
    RP: 10.255.255.1 (?)

R3# show ip pim interface df
* implies this system is the DF
Interface                RP               DF Winner        Metric     Uptime
Loopback0                10.255.255.1     *10.255.255.3     11         00:00:35
Ethernet0/0              10.255.255.1     *192.168.20.1     11         00:00:35
Ethernet0/1              10.255.255.1      10.1.3.1         0          00:00:23
Ethernet0/2              10.255.255.1     *10.2.3.3         11         00:00:32

R3# show ip mroute 239.2.2.2 | begin \(
(*, 239.2.2.2), 00:00:15/00:02:55, RP 10.255.255.1, flags: BC
  Bidir-Upstream: Ethernet0/1, RPF nbr 10.1.3.1
  Outgoing interface list:
    Ethernet0/0, Forward/Sparse, 00:00:15/00:02:55, flags:
    Ethernet0/1, Bidir-Upstream/Sparse, 00:00:15/stopped, flags:

SRV1# ping 239.2.2.2 repeat 3
Reply to request 0 from 192.168.20.10, 2 ms
...
R1# show ip mroute 239.2.2.2 | begin \(
(*, 239.2.2.2), 00:00:56/00:02:33, RP 10.255.255.1, flags: B
  Bidir-Upstream: Null, RPF nbr 0.0.0.0
  Outgoing interface list:
    Ethernet0/2, Forward/Sparse, 00:00:56/00:02:33, flags:
```
The group-specific RP (the ACL) wins over the catch-all 224.0.0.0/4, so 239.1.1.1 still uses R2 while 239.2.x
uses R1. Bidir can't use the RPF check (traffic legitimately arrives from both directions), so instead every link
elects a **designated forwarder (DF)**: the router with the best route to the RP, the only one allowed to forward
toward the RP on that link. Even after SRV1 sent, there is no (S,G) anywhere: one (\*,G) per group, however many
sources.

## Step 10 — MSDP: RPs talking about sources
**MSDP** connects RPs: when a source registers with one RP, that RP sends a **Source-Active (SA)** message to its
MSDP peers, so receivers in another PIM domain (or behind another RP of the same domain) can join the source.
Peer R2 (the RP for 239.1.1.1) with R1 over their loopbacks:

**R1**: `ip msdp peer 10.255.255.2 connect-source Loopback0`
**R2**: `ip msdp peer 10.255.255.1 connect-source Loopback0`

MSDP runs over TCP 639, so give it about a minute. Then **SRV1** `ping 239.1.1.1 repeat 3` and look:
```
R2# show ip msdp summary
Peer Address     AS          State    Uptime/  Reset SA    Peer Name
                                      Downtime Count Count
10.255.255.1     ?           Up       00:01:19 0     0     ?

R1# show ip msdp sa-cache
MSDP Source-Active Cache - 1 entries
(192.168.10.10, 239.1.1.1), RP 10.255.255.2, AS ?,00:00:21/00:05:53, Peer 10.255.255.2
```
R2 announced the active source (SRV1, 239.1.1.1) to R1. The main use inside one domain is **Anycast RP**: two or
more RPs share one RP address (a loopback configured on each), every router uses the nearest one, and MSDP between
them makes sure each RP knows about the sources registered with the others. If one RP fails, unicast routing
simply moves everyone to the next.

> You may see a reply twice (`Reply to request 1` two times) right after a pause: the first packets travel both
> inside a register to the RP and natively on the new tree for a moment. That's normal during the switchover.

## Final check
| From | Test | Result |
|---|---|---|
| R1–R3 | `show ip pim neighbor` | R1: R2 and R3; R2: R1 and R3; R3: R1 and R2 |
| R3 | `show ip igmp groups` | 239.1.1.1, 239.2.2.2 and 232.1.1.1 on Ethernet0/0, reporter 192.168.20.10 |
| R3 | `show ip pim rp mapping` | 224.0.0.0/4 → 10.255.255.2; BIDIR-GROUPS → 10.255.255.1 (bidir) |
| SRV1 | `ping 239.1.1.1` / `232.1.1.1` / `239.2.2.2` | replies from 192.168.20.10 |
| R3 | `show ip mroute 239.1.1.1` | (S,G) with **T**, incoming Ethernet0/1 (SPT, straight from R1) |
| R3 | `show ip mroute 232.1.1.1` | (S,G) with **sTI**, no (\*,G) |
| R1 | `show ip msdp sa-cache` | (192.168.10.10, 239.1.1.1) from peer 10.255.255.2 |

## Check yourself
- Why does R3's LAN interface need `ip pim sparse-mode` although no PIM neighbor will ever appear there?
- In Step 3 R3 had a (\*,G) for 239.1.1.1 but SRV1's pings failed. Name the missing piece and where it's missing.
- One router has `ip pim rp-address 10.255.255.3` and the rest `10.255.255.2`. What happens to receivers behind it?
- What do the flags **F**, **J**, **T** and **P** mean, and on which router did you see each in Step 5?
- Which interface does the RPF check use for a (\*,G) entry? And for an (S,G) entry?
- Why did the ping to 232.1.1.1 fail while PC1 ran IGMPv2, and why did it need no RP afterwards?
- R1 has `ip pim rp-address 10.255.255.2 ASM` with an ACL ASM that permits `239.0.0.0 0.0.255.255`. Will SRV1's
  239.1.1.1 traffic be registered?
- What replaces the RPF check in bidir PIM?

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1, R2, R3 | IOL-XE routers | cisco | cisco | cisco |
| SRV1 | IOL-XE acting as the multicast source (pings only) | cisco | cisco | cisco |
| PC1 | IOL-XE acting as the receiver (IGMP joins) | cisco | cisco | cisco |

Open a console from the node in CML (right-click → Console). Routers start in privileged EXEC.
Each node also has a label in the CML canvas with its login and addresses.

## Topology

```
                         R2  (RP for ASM groups)
                         Lo0 10.255.255.2
               e0/0 /                    \ e0/1
         10.1.2.0/24                      10.2.3.0/24
             e0/1 /                          \ e0/2
          R1  ---------------------------------  R3
   Lo0 10.255.255.1  e0/2   10.1.3.0/24    e0/1  Lo0 10.255.255.3
   (first hop)                                   (last hop)
         | e0/0 192.168.10.1                      | e0/0 192.168.20.1
         |  LAN10 192.168.10.0/24                 |  LAN20 192.168.20.0/24
         | e0/0 192.168.10.10                     | e0/0 192.168.20.10
        SRV1 (source)                            PC1 (receiver)
```

## Addressing

| Node | Interface | IPv4 | Connects to |
|---|---|---|---|
| R1 | Loopback0 | 10.255.255.1/32 | — |
| R1 | Ethernet0/0 | 192.168.10.1/24 | SRV1 (LAN10) |
| R1 | Ethernet0/1 | 10.1.2.1/24 | R2 e0/0 |
| R1 | Ethernet0/2 | 10.1.3.1/24 | R3 e0/1 |
| R2 | Loopback0 | 10.255.255.2/32 | — (RP) |
| R2 | Ethernet0/0 | 10.1.2.2/24 | R1 e0/1 |
| R2 | Ethernet0/1 | 10.2.3.2/24 | R3 e0/2 |
| R3 | Loopback0 | 10.255.255.3/32 | — |
| R3 | Ethernet0/0 | 192.168.20.1/24 | PC1 (LAN20) |
| R3 | Ethernet0/1 | 10.1.3.3/24 | R1 e0/2 |
| R3 | Ethernet0/2 | 10.2.3.3/24 | R2 e0/1 |
| SRV1 | Ethernet0/0 | 192.168.10.10/24, default route → .1 | R1 |
| PC1 | Ethernet0/0 | 192.168.20.10/24, default route → .1 | R3 |

| Group | Mode | RP |
|---|---|---|
| 239.1.1.1 | ASM (PIM sparse mode) | R2, 10.255.255.2 |
| 232.1.1.1, source 192.168.10.10 | SSM | none |
| 239.2.2.2 (239.2.0.0/16) | bidir | R1, 10.255.255.1 |

**Routing:** OSPF area 0 on every interface of R1, R2 and R3; the LAN interfaces are passive. Every link has OSPF
cost 10, so R3 reaches LAN10 directly through R1 and R2's loopback directly through R2.
