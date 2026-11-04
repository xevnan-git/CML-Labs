# Policy-Based Routing (PBR) — Learning Lab

> **Blueprint:** ENCOR 3.2.d — Configure and verify policy-based routing
> (also ENARSI 1.6 — Troubleshoot policy-based routing)
> **Mode:** Learning (guided build) · **Nodes:** 5 licensed (3 routers, 2 hosts) · **Time:** ~45 min

<!--
This README is copied verbatim into the lab's CML Notes (tools/sync_notes.py), so it must read well inside CML:
plain Markdown, ASCII diagrams (no Mermaid), no links to solution files.
Order: objectives and steps first; lab access, topology and addressing in the Reference section at the bottom.
-->

## What you'll learn
- Override the routing table for chosen traffic: match it with an ACL in a route-map, then `set ip next-hop`.
- Apply PBR to the interface where the traffic comes **in**, and prove which path a packet took.
- Read `show ip policy`, `show route-map` and `debug ip policy`.
- Tell `set ip next-hop` from `set ip default next-hop`, and see that a default route doesn't count as a route
  for `default next-hop`.
- See an untracked next hop black-hole traffic, then fix it with IP SLA, object tracking and
  `verify-availability`.
- Policy-route the router's **own** traffic with `ip local policy`.

## Starting point
Logins, the topology diagram and the addressing table are in **Reference** at the end of this guide.

The network already works. This lab is about steering traffic, not building routing:
- **R1** is your edge router with two internet providers. **ISP1** is the primary: R1 has a static default route
  to it, and a static route for 203.0.113.0/24 (the company's SaaS provider) that also points to ISP1.
  **ISP2** is a cheaper second link that's connected but carries nothing yet. **R1 is the only router you change**,
  apart from one outage you'll simulate on ISP2 in Step 6.
- **PC1** is on the staff LAN (192.168.10.0/24), **PC2** on the guest LAN (192.168.20.0/24).
- Both ISPs host the same "internet server", **203.0.113.100** (a loopback on each). That lets you see which ISP
  a packet used:
  - `traceroute -n 203.0.113.100`: the last hop is **10.1.101.101 through ISP1** or **10.1.102.102 through ISP2**
    (the ISP answers from its interface toward R1).
  - `telnet 203.0.113.100` shows a banner naming the ISP that answered. Press Ctrl+] and type `quit` to leave.

**The goal:** guest traffic leaves through ISP2, staff traffic stays on ISP1, and guests fall back to ISP1 if ISP2
fails.

Wait about a minute after starting the lab, until the routers finish booting, before you test.

## Step 1 — Baseline: everything uses ISP1
**R1**
```
show ip route static
```
**Output (captured, codes trimmed)**
```
Gateway of last resort is 10.1.101.101 to network 0.0.0.0

S*    0.0.0.0/0 [1/0] via 10.1.101.101
S     203.0.113.0/24 [1/0] via 10.1.101.101
```
**PC1** and **PC2**
```
traceroute -n -q 1 -w 1 203.0.113.100
```
**PC2**
```
telnet 203.0.113.100
```
**Output (captured)**
```
PC1:  1  192.168.10.1  6.413 ms
      2  10.1.101.101  2.183 ms
PC2:  1  192.168.20.1  3.629 ms
      2  10.1.101.101  1.113 ms

PC2: *** internet server 203.0.113.100 -- you reached it through ISP1 ***
```
Look for: both LANs leave through ISP1. Normal routing looks only at the **destination** address, so R1 can't treat
the two LANs differently. PBR can: it chooses the next hop from other fields, here the **source** address.

## Step 2 — Match the guests and pick a next hop
PBR uses a route-map: `match` selects packets, `set` says where they go.

**R1**
```
configure terminal
ip access-list extended GUEST-NET
 10 permit ip 192.168.20.0 0.0.0.255 any
route-map PBR-GUEST permit 10
 match ip address GUEST-NET
 set ip next-hop 10.1.102.102
end
```
> **Why:** like in CoPP, the ACL here doesn't filter. `permit` means "policy-route this packet". A packet that
> doesn't match (ACL `deny`, or no matching route-map entry) isn't dropped. It's routed normally, from the
> routing table. A `route-map … deny` entry also means "route normally". The next hop must be on a **directly
> connected** subnet: PBR doesn't do a recursive lookup.

## Step 3 — Apply it where the traffic comes in
**R1**
```
configure terminal
interface Ethernet0/1
 ip policy route-map PBR-GUEST
end
```
Repeat Step 1's traceroutes on **PC1** and **PC2**, and the telnet on **PC2**.

**Output (captured)**
```
PC2:  1  192.168.20.1  0.844 ms
      2  10.1.102.102  0.858 ms
PC2: *** internet server 203.0.113.100 -- you reached it through ISP2 ***
PC1:  1  192.168.10.1  0.945 ms
      2  10.1.101.101  0.978 ms
```
**R1**
```
show ip policy
show route-map PBR-GUEST
show access-lists GUEST-NET
show ip route 203.0.113.100
```
**Output (captured)**
```
Interface      Route map
Ethernet0/1    PBR-GUEST

route-map PBR-GUEST, permit, sequence 10
  Match clauses:
    ip address (access-lists): GUEST-NET
  Set clauses:
    ip next-hop 10.1.102.102
  Policy routing matches: 11 packets, 658 bytes

Extended IP access list GUEST-NET
    10 permit ip 192.168.20.0 0.0.0.255 any (11 matches)

Routing entry for 203.0.113.0/24
  Known via "static", distance 1, metric 0
  Routing Descriptor Blocks:
  * 10.1.101.101
```
Look for: guests now leave through ISP2 while the routing table still says ISP1. `show ip route` doesn't tell you
where policy-routed traffic goes. `show route-map` does, and its **Policy routing matches** counter is the first
thing to check when PBR seems to do nothing.

> **Why on e0/1:** PBR is checked when a packet is **received** on an interface, before the routing lookup. It
> never looks at packets leaving an interface. Putting the policy on e0/3 (toward ISP2) would do nothing for
> guest traffic, because guest packets *enter* R1 on e0/1.

## Step 4 — Watch the decision with `debug ip policy`
**R1**
```
debug ip policy
```
**PC2**, then **PC1**
```
ping -c 1 203.0.113.100
```
**R1**
```
undebug all
show logging | include IP: s=
```
**Output (captured, trimmed)**
```
IP: s=192.168.20.10 (Ethernet0/1), d=203.0.113.100, len 84, FIB policy match
IP: s=192.168.20.10 (Ethernet0/1), d=203.0.113.100, len 84, PBR Counted
IP: s=192.168.20.10 (Ethernet0/1), d=203.0.113.100, g=10.1.102.102, len 84, FIB policy routed
IP: s=0.0.0.0 (Ethernet0/1), d=255.255.255.255 (nil), len 328, policy rejected -- normal forwarding
```
Look for:
- PC2's ping: **policy match**, then **policy routed** with `g=` (the gateway it chose).
- PC1's ping logs nothing: e0/0 has no policy, so nothing is checked.
- The `s=0.0.0.0` broadcast is PC2 asking for DHCP. It enters e0/1, doesn't match GUEST-NET, so it's
  **policy rejected -- normal forwarding**. "Rejected" means "not policy-routed", not "dropped".

> In the console the debug prints live. Over SSH or Telnet, run `terminal monitor` first. Debugs are fine on a
> lab router; on a busy production router, limit them with an ACL (`debug ip policy <acl>`).

## Step 5 — `set ip next-hop` vs `set ip default next-hop`
**R1**
```
configure terminal
route-map PBR-GUEST permit 10
 no set ip next-hop 10.1.102.102
 set ip default next-hop 10.1.102.102
end
```
**PC2**
```
traceroute -n -q 1 -w 1 203.0.113.100
traceroute -n -q 1 -w 1 10.255.255.102
```
**Output (captured)**
```
traceroute to 203.0.113.100
 1  192.168.20.1  4.449 ms
 2  10.1.101.101  3.340 ms
traceroute to 10.255.255.102
 1  192.168.20.1  0.778 ms
 2  10.1.102.102  1.060 ms
```
Look for: the server went back to **ISP1**, but ISP2's loopback 10.255.255.102 still goes through **ISP2**. The
route-map matches both (`show route-map` keeps counting).

> **Why:**
> - `set ip next-hop`: use this next hop **instead of** the routing table.
> - `set ip default next-hop`: look in the routing table first, and use this next hop **only if there's no
>   explicit route** for the destination.
> - **A default route isn't an explicit route** for this purpose. 203.0.113.100 matches the static
>   203.0.113.0/24, so the routing table wins (ISP1). 10.255.255.102 only matches 0.0.0.0/0, so PBR's default
>   next hop is used (ISP2).
>
> `default next-hop` suits "follow specific routes, but send the rest our way instead of the default". It's the
> wrong tool for "guests always use ISP2". (It also can't use `verify-availability … track`, which you'll need
> in Step 7.)

For comparison, without PBR: **PC1** `traceroute -n -q 1 -w 1 -m 3 10.255.255.102` ends with
`10.1.101.101 !H`. ISP1 has no route to ISP2's loopback.

Put the designed line back:

**R1**
```
configure terminal
route-map PBR-GUEST permit 10
 no set ip default next-hop 10.1.102.102
 set ip next-hop 10.1.102.102
end
```

## Step 6 — Break it: ISP2 fails, and PBR doesn't notice
Simulate an outage inside ISP2's network: its link to R1 goes dead, but R1's port stays up.

**ISP2** (this one change on a provider router is part of the exercise)
```
configure terminal
interface Ethernet0/0
 shutdown
end
```
**PC2**
```
ping -c 3 -W 1 203.0.113.100
traceroute -n -q 1 -w 1 -m 3 203.0.113.100
```
**R1**
```
show ip interface brief | include Ethernet0/3
show route-map PBR-GUEST
show ip arp 10.1.102.102
```
**Output (captured)**
```
PC2: 3 packets transmitted, 0 packets received, 100% packet loss
PC2:  1  192.168.20.1  10.592 ms
      2  *
      3  *

Ethernet0/3            10.1.102.1      YES TFTP   up                    up
    ip next-hop 10.1.102.102
  Policy routing matches: 22 packets, 1470 bytes
Internet  10.1.102.102            7   aabb.cc00.4500  ARPA   Ethernet0/3
```
Look for: guests are cut off even though ISP1 is fine. R1's interface is up, the next hop is still in the ARP
cache, so PBR keeps sending guest traffic to a dead next hop.

> **Why:** a plain `set ip next-hop` is skipped only if the next hop isn't on a connected, up interface (or, once
> the ARP entry expires, can't be resolved). An outage beyond R1's port, the usual case with a provider, is
> invisible to it. PBR needs a way to *test* the next hop.

## Step 7 — Track the next hop with IP SLA
Leave ISP2's link down for now.

**R1**
```
configure terminal
ip sla 1
 icmp-echo 10.1.102.102 source-interface Ethernet0/3
 frequency 5
exit
ip sla schedule 1 life forever start-time now
track 1 ip sla 1 reachability
route-map PBR-GUEST permit 10
 no set ip next-hop 10.1.102.102
 set ip next-hop verify-availability 10.1.102.102 1 track 1
end
```
> **Why each piece:**
> - **IP SLA 1** pings ISP2's address every 5 seconds, out of e0/3.
> - **Track 1** turns the probe's result into an up/down object.
> - **`verify-availability <next-hop> <seq> track <n>`** uses the next hop only while the track is up. The `1`
>   is a sequence number: you can list several next hops, each with its own track, and PBR uses the first one
>   that's up. If none is up, the packet is routed normally.
> - An IP SLA entry can't be edited while it runs. To change the target, `no ip sla 1` and enter it again
>   (and schedule it again).

Wait 10 seconds. **PC2**: `traceroute -n -q 1 -w 1 203.0.113.100`. **R1**: `show track 1` and
`show route-map PBR-GUEST`.

**Output (captured)**
```
PC2:  1  192.168.20.1  0.853 ms
      2  10.1.101.101  1.317 ms

Track 1
  IP SLA 1 reachability
  Reachability is Down
    1 change, last change 00:00:40
  Latest operation return code: Timeout
  Tracked by:
    Route Map 0

    ip next-hop verify-availability 10.1.102.102 1 track 1  [down]
```
Guests now fall back to the routing table (ISP1). Bring ISP2 back:

**ISP2**
```
configure terminal
interface Ethernet0/0
 no shutdown
end
```
Wait 10 seconds, then the traceroute on **PC2** again, and on **R1**:
```
show logging | include TRACK
show ip sla statistics 1
show route-map PBR-GUEST
```
**Output (captured)**
```
PC2:  1  192.168.20.1  0.807 ms
      2  10.1.102.102  2.130 ms

%TRACK-6-STATE: 1 ip sla 1 reachability Down -> Up
Latest operation return code: OK
Number of successes: 7
Number of failures: 7
    ip next-hop verify-availability 10.1.102.102 1 track 1  [up]
```
Look for: `[up]`/`[down]` next to the next hop in `show route-map`, and the TRACK log message. Guests switch back
to ISP2 by themselves.

## Step 8 — Policy-route the router's own traffic
Interface policies only see packets *arriving* on that interface. Packets R1 **creates** itself (pings, Telnet,
SSH, syslog, NTP, IP SLA probes) never arrive on an interface, so they need a separate policy. The design: traffic
R1 sources from **Loopback0** (its management address) uses ISP2.

Before you change anything:

**R1**
```
ping 10.255.255.102 source Loopback0 repeat 2 timeout 1
traceroute 203.0.113.100 source Loopback0 probe 1 timeout 1 ttl 1 3
```
**Output (captured)**
```
U.
Success rate is 0 percent (0/2)
  1 10.1.101.101 2 msec
```
**R1**
```
configure terminal
ip access-list extended R1-LOOPBACK
 10 permit ip host 10.255.255.1 any
route-map PBR-LOCAL permit 10
 match ip address R1-LOOPBACK
 set ip next-hop 10.1.102.102
exit
ip local policy route-map PBR-LOCAL
end
```
Run the two commands again, then the same pair **without** a source, and check the policy:

**R1**
```
ping 10.255.255.102 source Loopback0 repeat 2 timeout 1
traceroute 203.0.113.100 source Loopback0 probe 1 timeout 1 ttl 1 3
ping 10.255.255.102 repeat 2 timeout 1
traceroute 203.0.113.100 probe 1 timeout 1 ttl 1 3
show ip policy
show route-map PBR-LOCAL
```
**Output (captured)**
```
Packet sent with a source address of 10.255.255.1
!!
Success rate is 100 percent (2/2), round-trip min/avg/max = 1/1/1 ms
  1 10.1.102.102 1 msec

U.
Success rate is 0 percent (0/2)
  1 10.1.101.101 2 msec

Interface      Route map
local          PBR-LOCAL
Ethernet0/1    PBR-GUEST

  Policy routing matches: 3 packets, 278 bytes
```
Look for: with `source Loopback0`, R1's traffic leaves through ISP2. Without it, R1 sources from the outgoing
interface (e0/2, 10.1.101.1), the ACL doesn't match, and normal routing sends it to ISP1. `show ip policy` lists
the local policy as **local**.

> **Why match on the source:** the local policy sees *every* packet R1 originates, including the IP SLA probe and
> routing protocol traffic. Matching only Loopback0 keeps everything else on normal routing. A careless
> `permit ip any any` here can send a router's own routing or management traffic somewhere it can't reach.

## Final check
| From | Test | Result |
|---|---|---|
| PC1 | `traceroute -n 203.0.113.100` | last hop 10.1.101.101 (ISP1) |
| PC2 | `traceroute -n 203.0.113.100` | last hop 10.1.102.102 (ISP2) |
| R1 | `show ip policy` | Ethernet0/1 PBR-GUEST, local PBR-LOCAL |
| R1 | `show route-map PBR-GUEST` | `verify-availability 10.1.102.102 1 track 1  [up]`, matches counting |
| R1 | `show track 1 brief` | Up |
| R1 | `ping 10.255.255.102 source Loopback0` | works (only reachable through ISP2) |
| ISP2 | `shutdown` on e0/0, wait 15 s | PC2's traceroute ends at 10.1.101.101; `no shutdown` brings it back to ISP2 |

## Check yourself
- You put `ip policy route-map PBR-GUEST` on Ethernet0/3. Which packets does it check now?
- GUEST-NET is written `permit ip any 192.168.20.0 0.0.0.255`. What happens to guest traffic, and what does
  `show route-map` show?
- With `set ip default next-hop 10.1.102.102`, which guest destinations use ISP2 and which use ISP1?
- The IP SLA probe target has a typo and the track is down. Where does guest traffic go? Would anyone notice?
- Why does `ping 10.255.255.102` from R1 fail while `ping 10.255.255.102 source Loopback0` works?
- `set ip next-hop 10.1.120.102` (a typo: not on any connected subnet). What does PBR do with matching packets?
- Why does the IP SLA probe (sourced from e0/3) not get caught by PBR-LOCAL?

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1 | IOL-XE router (your edge, the only one you configure) | cisco | cisco | cisco |
| ISP1 | IOL-XE router (primary provider; look, don't change) | cisco | cisco | cisco |
| ISP2 | IOL-XE router (second provider; change only in Steps 6–7) | cisco | cisco | cisco |
| PC1, PC2 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → Console). Routers start in privileged EXEC.
Each node also has a label in the CML canvas with its login and addresses.

## Topology

```
  PC1 (staff)                                                   ISP1 (primary)
  192.168.10.10 ── e0/0 ┐                         ┌ e0/2 ── 10.1.101.0/24 ── e0/0 ISP1
                        R1  Lo0 10.255.255.1                                  Lo1 203.0.113.100
  PC2 (guest)           │   edge (PBR)            │                           ("internet server")
  192.168.20.10 ── e0/1 ┘                         └ e0/3 ── 10.1.102.0/24 ── e0/0 ISP2
                                                                              Lo1 203.0.113.100
                                                                ISP2 (guest / backup)
```

## Addressing

| Node | Interface | IPv4 | Connects to |
|---|---|---|---|
| R1 | Loopback0 | 10.255.255.1/32 | — |
| R1 | Ethernet0/0 | 192.168.10.1/24 | PC1 (staff LAN) |
| R1 | Ethernet0/1 | 192.168.20.1/24 | PC2 (guest LAN) |
| R1 | Ethernet0/2 | 10.1.101.1/24 | ISP1 e0/0 |
| R1 | Ethernet0/3 | 10.1.102.1/24 | ISP2 e0/0 |
| ISP1 | Loopback0 | 10.255.255.101/32 | — |
| ISP1 | Loopback1 | 203.0.113.100/32 | internet server (same address as ISP2's) |
| ISP1 | Ethernet0/0 | 10.1.101.101/24 | R1 e0/2 |
| ISP2 | Loopback0 | 10.255.255.102/32 | — |
| ISP2 | Loopback1 | 203.0.113.100/32 | internet server (same address as ISP1's) |
| ISP2 | Ethernet0/0 | 10.1.102.102/24 | R1 e0/3 |
| PC1 | eth0 | 192.168.10.10/24, gw .1 | R1 e0/0 |
| PC2 | eth0 | 192.168.20.10/24, gw .1 | R1 e0/1 |

| Router | Routing (static only) |
|---|---|
| R1 | 0.0.0.0/0 → 10.1.101.101 (ISP1); 203.0.113.0/24 → 10.1.101.101 (ISP1) |
| ISP1 | 192.168.0.0/16 and 10.255.255.1/32 → 10.1.101.1 (R1). No route to ISP2's addresses. |
| ISP2 | 192.168.0.0/16 and 10.255.255.1/32 → 10.1.102.1 (R1). No route to ISP1's addresses. |
