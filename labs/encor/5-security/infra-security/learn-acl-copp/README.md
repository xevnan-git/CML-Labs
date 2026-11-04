# ACLs and CoPP, Layered on the Edge — Learning Lab

> **Blueprint:** ENCOR 5.2.a + 5.2.b — Configure and verify infrastructure security features: ACLs, CoPP
> (also ENARSI 3.2.a and 3.3)
> **Mode:** Learning (guided build) · **Nodes:** 5 licensed (3 routers, 2 hosts) · **Time:** ~60 min

<!--
This README is copied verbatim into the lab's CML Notes (tools/sync_notes.py), so it must read well inside CML:
plain Markdown, ASCII diagrams (no Mermaid), no links to solution files.
Order: objectives and steps first; lab access, topology and addressing in the Reference section at the bottom.
-->

## What you'll learn
- Write an **infrastructure ACL** (iACL) for an internet edge: permit the ISP peer, drop spoofed sources, protect
  the router's own addresses, let transit through.
- Put three layers in front of the router's CPU: iACL on the interface, CoPP on the control plane, and a vty
  `access-class` on the login lines. Then work out which layer stopped a packet, using only counters.
- See which order the router checks them in, and why `no ip unreachables` belongs on an internet interface.
- See traffic the iACL permits but CoPP drops, and logins that CoPP permits but the vty ACL refuses.

This lab assumes the basics from the two single-topic labs: ACL syntax and wildcards (5.2.a ACLs) and how CoPP
classes and policers work (5.2.b CoPP). It doesn't explain them again.

## Starting point
Logins, the topology diagram and the addressing table are in **Reference** at the end of this guide.

The network already works, with no protection at all:
- **R1** is your internet edge. It runs OSPF area 0 with **R2** (inside) and eBGP with **ISP1** (AS 64511).
  It originates a default route into OSPF and advertises the management LAN 192.168.10.0/24 and its Loopback0 to
  ISP1. **R1 is the only router you change.**
- **PC1** (192.168.10.10) is the admins' workstation, behind R2. **PC2** is "somebody on the internet", behind
  ISP1. ISP1 is the provider's router: you may run `show`, `ping` and `traceroute` there, but don't change it.
- ISP1 is the *passive* side of the BGP session, so R1 always opens the TCP connection, and BGP timers are 10/30.
- The R1–ISP1 peering subnet, 10.1.101.0/24, is a **private** range. Keep that in mind for Step 2.

Wait about a minute after starting the lab, until the routers finish booting, before you test.

## Step 1 — Baseline: what the internet can reach today
**PC2** (internet)
```
telnet 10.1.101.1            (you get a login prompt; press Ctrl+] then type quit)
telnet 10.255.255.1          (same)
ping -c 2 192.168.10.10
```
**ISP1** (an internet router sending from a private address)
```
ping 192.168.10.10 source Loopback0 repeat 2
```
**Output (captured)**
```
PC2: Connected to 10.1.101.1
PC2: Connected to 10.255.255.1
PC2: 2 packets transmitted, 2 packets received, 0% packet loss

ISP1: Packet sent with a source address of 10.255.255.101
ISP1: !!
ISP1: Success rate is 100 percent (2/2)
```
Look for: anyone on the internet gets a login prompt on two of R1's addresses, and a packet whose **source** is a
private 10.x address walks straight in to the management LAN. On the real internet no legitimate packet comes from
10.0.0.0/8, so it's spoofed or misrouted. ISP1's Loopback0 plays that role here.

## Step 2 — Layer 1: the infrastructure ACL
An iACL sits inbound on the internet-facing interface and filters everything arriving there, transit and
router-bound alike. It's built in four sections, in this order:

**R1**
```
configure terminal
ip access-list extended IACL-IN
 10 permit tcp host 10.1.101.101 host 10.1.101.1 eq bgp
 20 permit tcp host 10.1.101.101 eq bgp host 10.1.101.1
 30 permit icmp host 10.1.101.101 host 10.1.101.1
 40 deny ip 10.0.0.0 0.255.255.255 any
 50 deny ip 172.16.0.0 0.15.255.255 any
 60 deny ip 192.168.0.0 0.0.255.255 any
 70 deny ip 127.0.0.0 0.255.255.255 any
 80 permit icmp any host 10.1.101.1 echo
 90 permit icmp any host 10.1.101.1 echo-reply
 100 permit icmp any host 10.1.101.1 unreachable
 110 permit icmp any host 10.1.101.1 time-exceeded
 120 deny ip any host 10.1.101.1
 130 deny ip any host 10.255.255.1
 140 deny ip any 10.1.2.0 0.0.0.255
 150 permit ip any any
end
```
> **Why each section:**
> - **10–30, the ISP peer, first.** BGP to and from port 179 (R1 opens the session, so ISP1's packets come
>   *from* 179, line 20), and ICMP from the peer so you can ping and traceroute across the link. These must come
>   **before** anti-spoofing: the peer's address 10.1.101.101 is inside 10.0.0.0/8, and line 40 would drop it.
>   First match wins, so a too-broad deny above a permit silently wins.
> - **40–70, anti-spoofing.** Private and loopback **sources** can't legitimately arrive from the internet. A real
>   edge also lists its own public prefix (nobody outside should be using your addresses as a source) and other
>   bogons; here the "public" range we advertise, 192.168.10.0/24, is already covered by line 60.
> - **80–140, protect R1 itself.** Allow just enough ICMP to R1's internet address: `echo` so people can ping it,
>   and `echo-reply`, `unreachable` and `time-exceeded` so that **R1's own** pings and traceroutes outward get
>   their answers back. Then deny everything else to R1's addresses and to the inside link 10.1.2.0/24. An iACL
>   can't tell "a reply to R1" from "a new packet to R1", so if you forget the reply types, R1 can't ping or
>   traceroute to the internet even though transit works fine.
> - **150, transit.** Everything else is traffic for the inside network, which this ACL isn't meant to police.
>   Without this line, the implicit deny at the end drops every reply coming back to the office.

Apply it inbound on the internet interface:

**R1**
```
configure terminal
interface Ethernet0/1
 ip access-group IACL-IN in
end
```

## Step 3 — Verify the iACL
**PC2**
```
telnet 10.1.101.1
telnet 10.255.255.1
ping -c 2 10.1.101.1
ping -c 2 192.168.10.10
```
**ISP1**
```
ping 192.168.10.10 source Loopback0 repeat 2
```
**R1**
```
ping 198.51.100.10 repeat 2
traceroute 198.51.100.10 timeout 1 probe 1 ttl 1 3
show access-lists IACL-IN
```
**Output (captured, trimmed)**
```
PC2: telnet: can't connect to remote host (10.1.101.1): Host is unreachable
PC2: telnet: can't connect to remote host (10.255.255.1): Host is unreachable
PC2: 2 packets transmitted, 2 packets received, 0% packet loss       (ping R1's internet address)
PC2: 2 packets transmitted, 2 packets received, 0% packet loss       (ping PC1: transit)

ISP1: U.
ISP1: Success rate is 0 percent (0/2)

R1: Success rate is 100 percent (2/2)
R1:   1 10.1.101.101 1 msec
R1:   2 198.51.100.10 [AS 64511] 1 msec

Extended IP access list IACL-IN
    20 permit tcp host 10.1.101.101 eq bgp host 10.1.101.1 (12 matches)
    30 permit icmp host 10.1.101.101 host 10.1.101.1 (6 matches)
    40 deny ip 10.0.0.0 0.255.255.255 any (2 matches)
    80 permit icmp any host 10.1.101.1 echo (4 matches)
    90 permit icmp any host 10.1.101.1 echo-reply (4 matches)
    100 permit icmp any host 10.1.101.1 unreachable (2 matches)
    120 deny ip any host 10.1.101.1 (1 match)
    130 deny ip any host 10.255.255.1 (2 matches)
    150 permit ip any any (2 matches)
```
Look for:
- Logins from the internet now fail with *Host is unreachable*: R1 denied the SYN and sent back an ICMP
  unreachable (the same thing ISP1 shows as `U`). Pings to R1's internet address still work.
- ISP1's private-source ping hits line 40. BGP is still up: line 20 is counting keepalives.
- R1's own ping and traceroute work, thanks to lines 90 and 100. Line 100 counts PC2's "port unreachable", the
  answer that ends a traceroute.

## Step 4 — Layer 2: CoPP behind the iACL
Add the CoPP policy from the 5.2.b lab, unchanged. It covers traffic arriving on *every* interface, including from
the inside, which the iACL never sees.

**R1**
```
configure terminal
ip access-list extended COPP-ROUTING
 10 permit ospf any any
 20 permit tcp any any eq bgp
 30 permit tcp any eq bgp any
 40 permit eigrp any any
ip access-list extended COPP-MGMT
 10 permit tcp 192.168.10.0 0.0.0.255 any eq 22
 20 permit tcp 192.168.10.0 0.0.0.255 any eq telnet
 30 permit tcp 192.168.10.0 0.0.0.255 any eq www
 40 permit tcp 192.168.10.0 0.0.0.255 any eq 443
ip access-list extended COPP-SNMP
 10 permit udp 192.168.10.0 0.0.0.255 any eq snmp
ip access-list extended COPP-ICMP
 10 permit icmp any any
ip access-list extended COPP-CATCHALL
 10 permit ip any any
class-map match-all CM-ROUTING
 match access-group name COPP-ROUTING
class-map match-all CM-MGMT
 match access-group name COPP-MGMT
class-map match-any CM-MONITOR
 match access-group name COPP-SNMP
 match access-group name COPP-ICMP
class-map match-all CM-CATCHALL
 match access-group name COPP-CATCHALL
policy-map PM-COPP
 class CM-ROUTING
  police 256000 conform-action transmit exceed-action transmit
 class CM-MGMT
  police 256000 conform-action transmit exceed-action drop
 class CM-MONITOR
  police 16000 conform-action transmit exceed-action drop
 class CM-CATCHALL
  police 8000 conform-action drop exceed-action drop
 class class-default
  police 64000 conform-action transmit exceed-action drop
control-plane
 service-policy input PM-COPP
end
clear access-list counters IACL-IN
clear control-plane *
```
Now send something the iACL **permits** but CoPP limits, and something the iACL **denies**:

**PC2**
```
ping -c 20 -i 0.2 -s 1400 10.1.101.1
telnet 10.1.101.1            (wait; press Ctrl+C after about 10 seconds)
```
**R1**
```
show access-lists IACL-IN
show policy-map control-plane
```
**Output (captured, trimmed)**
```
PC2: 20 packets transmitted, 5 packets received, 75% packet loss
PC2: (telnet hangs; no "Host is unreachable" this time)

Extended IP access list IACL-IN
    80 permit icmp any host 10.1.101.1 echo (25 matches)
    120 deny ip any host 10.1.101.1

    Class-map: CM-MONITOR (match-any)
        conformed 5 packets, 7210 bytes; actions:
        exceeded 15 packets, 21630 bytes; actions:
    Class-map: CM-CATCHALL (match-all)
        conformed 7 packets, 518 bytes; actions:
```
Look for:
- **Permitted by the iACL, dropped by CoPP:** every big ping matched line 80, but CM-MONITOR's 16 kbps policer
  dropped 15 of the 20. The iACL decides *whether* a kind of traffic may reach R1; CoPP decides *how much*.
- **Something odd about telnet:** it now hangs instead of failing fast, line 120 didn't count it, and CM-CATCHALL
  did. That looks as though CoPP saw the packet *before* the iACL. Step 5 shows what's really going on.

## Step 5 — Which layer runs first? (`no ip unreachables`)
Test with a packet both layers have an opinion on. ISP1's private-source ping is denied by iACL line 40, but CoPP
would happily transmit it (CM-MONITOR matches all ICMP).

**R1**
```
clear access-list counters IACL-IN
clear control-plane *
```
**ISP1**
```
ping 10.1.101.1 source Loopback0 repeat 5 timeout 1
```
**R1**
```
show access-lists IACL-IN | include 40 deny
show policy-map control-plane input class CM-MONITOR | include Match|packets
```
**Output (captured)**
```
ISP1: U.U.U
ISP1: Success rate is 0 percent (0/5)

    40 deny ip 10.0.0.0 0.255.255.255 any (5 matches)
      Match: access-group name COPP-ICMP
        3 packets, 342 bytes
```
The iACL denied all five. If CoPP ran first, CM-MONITOR would show five packets; it shows **three**, exactly the
number of `U` replies ISP1 got. So the interface ACL checks the packet first. When it denies a packet on an
interface that sends unreachables, the packet goes to R1's CPU so it can build the ICMP "unreachable" reply, and
**that** trip to the CPU passes through CoPP. (IOS rate-limits unreachables, which is why only every other packet
got one.) Telnet in Step 4 went the same way: the denied SYN went to the CPU to generate an unreachable, CoPP put
it in CM-CATCHALL and dropped it, and no reply was sent. On this platform the iACL's deny counter didn't count
that SYN either.

Generating unreachables for the internet just tells scanners which addresses exist, and costs CPU. Turn it off on
the internet interface:

**R1**
```
configure terminal
interface Ethernet0/1
 no ip unreachables
end
clear access-list counters IACL-IN
clear control-plane *
```
Repeat the ISP1 ping, and on **PC2** run `nc -w 3 10.1.101.1 23` (a one-shot telnet attempt). Then on **R1**:
```
show access-lists IACL-IN | include 40 deny|120
show policy-map control-plane | include Class-map|conformed [0-9]
```
**Output (captured)**
```
ISP1: .....

    40 deny ip 10.0.0.0 0.255.255.255 any (5 matches)
    120 deny ip any host 10.1.101.1 (3 matches)

    Class-map: CM-ROUTING (match-all)
        conformed 17 packets, 1368 bytes; actions:
    Class-map: CM-MGMT (match-all)
        conformed 0 packets, 0 bytes; actions:
    Class-map: CM-MONITOR (match-any)
        conformed 0 packets, 0 bytes; actions:
    Class-map: CM-CATCHALL (match-all)
        conformed 0 packets, 0 bytes; actions:
```
Now the counters tell a clean story: everything the iACL denies is counted on its deny line, and CoPP never sees
it. CoPP only counts what the iACL let through (here, just routing).

> **Why it matters for troubleshooting:** the layers run in order: **interface ACL → CoPP → the service itself**
> (vty `access-class`, next). When something can't reach R1, check them in that order and stop at the first
> counter that moves. Unreachables blur that picture, so leave them off on internet-facing interfaces.

## Step 6 — Inside traffic never meets the iACL
The iACL is only on e0/1. From the inside, CoPP is the first layer.

**R2**
```
telnet 10.1.2.1 /source-interface Loopback0
```
**Output (captured)**
```
Trying 10.1.2.1 ...
% Connection timed out; remote host not responding
```
R2's Loopback0 (10.255.255.2) isn't in the management LAN, so COPP-MGMT doesn't match it; the SYN lands in
CM-CATCHALL and is dropped. Same address, different direction, different layer.

## Step 7 — Layer 3: the vty access-class
CoPP's management class allows the **whole** management LAN, at a rate. Who may actually log in is a decision for
the login lines. Here only the admin workstation PC1 may:

First try it without: from **R2**, `telnet 10.1.2.1 /source-interface Ethernet0/1` (source 192.168.10.1, in the
management LAN). You get R1's `Username:` prompt. Press Ctrl+Shift+6 then x, and type `disconnect`.

**R1**
```
configure terminal
ip access-list standard VTY-MGMT
 10 permit 192.168.10.10
 20 deny any log
line vty 0 4
 access-class VTY-MGMT in
end
```
**R2**
```
telnet 10.1.2.1 /source-interface Ethernet0/1
```
**PC1**
```
telnet 10.255.255.1          (log in, then exit)
ssh cisco@10.255.255.1       (log in, then exit)
ping -c 2 198.51.100.10
```
**R1**
```
show access-lists VTY-MGMT
show logging | include SEC-6
show policy-map control-plane input class CM-MGMT | include conformed [0-9]
```
**Output (captured)**
```
R2: % Connection refused by remote host
PC1: Connected to 10.255.255.1        (and SSH reaches the login stage)
PC1: 2 packets transmitted, 2 packets received, 0% packet loss

Standard IP access list VTY-MGMT
    10 permit 192.168.10.10 (4 matches)
    20 deny   any log (1 match)
%SEC-6-IPACCESSLOGS: list VTY-MGMT denied 192.168.10.1 1 packet
        conformed 42 packets, 4278 bytes; actions:
```
Look for: R2's SYN passed CoPP (it's from the management LAN, so CM-MGMT conformed) and was refused by the vty
ACL with a TCP reset: *Connection refused*, an immediate answer. Compare the other two layers: the iACL
(silent with `no ip unreachables`) and CoPP (silent) just let the client time out.

> **Why three layers:** each one covers something the others can't. The iACL is the only one that filters
> **transit** (anti-spoofing). CoPP is the only one that **rate-limits**, and the only one that sees traffic from
> every interface. `access-class` is the only one that applies to the login service itself, whatever the path,
> and it logs who tried.

## Final check
| From | Test | Result | Layer that decides |
|---|---|---|---|
| R1 | `show ip ospf neighbor`, `show ip bgp summary` | R2 FULL; ISP1 with 2 prefixes | iACL 10–20 + CM-ROUTING |
| PC1 | `ping -c 2 198.51.100.10` | works | iACL 150 (transit) |
| R1 | `ping 198.51.100.10`, `traceroute 198.51.100.10` | both complete | iACL 90–110 |
| PC2 | `ping -c 3 10.1.101.1` | works | iACL 80 + CM-MONITOR |
| PC2 | `ping -c 20 -i 0.2 -s 1400 10.1.101.1` | heavy loss | CM-MONITOR policer |
| PC2 | `telnet 10.1.101.1`, `ping 10.255.255.1` | no answer | iACL 120, 130 |
| ISP1 | `ping 192.168.10.10 source Loopback0` | fails | iACL 40 (anti-spoofing) |
| R2 | `telnet 10.1.2.1 /source-interface Loopback0` | times out | CM-CATCHALL |
| R2 | `telnet 10.1.2.1 /source-interface Ethernet0/1` | refused | VTY-MGMT |
| PC1 | `telnet` / `ssh` to 10.255.255.1 | login prompt | all three permit |

## Check yourself
- You move lines 10–30 below line 70. What happens to BGP, and which counter shows it?
- You delete lines 90–110. Which still works: PC1 pinging PC2, or R1 pinging PC2? Why?
- Why did PC2's telnet fail fast in Step 3 but hang in Step 4, when the iACL hadn't changed?
- A packet is denied by the iACL. Can CoPP's counters ever show it? Under what condition?
- An admin on 192.168.10.20 can ping R1 but can't log in, and gets "Connection refused". Which layer, and which
  line?
- Why can't CoPP or `access-class` do the iACL's anti-spoofing job?

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1 | IOL-XE router (your edge, the only one you change) | cisco | cisco | cisco |
| R2 | IOL-XE router (inside) | cisco | cisco | cisco |
| ISP1 | IOL-XE router (provider; show/ping/traceroute only) | cisco | cisco | cisco |
| PC1, PC2 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → Console). Routers start in privileged EXEC.
Each node also has a label in the CML canvas with its login and addresses.

## Topology

```
                 OSPF area 0                 eBGP 65001 <-> 64511
 PC1 ── e0/1 R2 e0/0 ── 10.1.2.0/24 ── e0/0 R1 e0/1 ── 10.1.101.0/24 ── e0/0 ISP1 e0/1 ── PC2
 192.168.10.10   inside               edge: CoPP,  iACL in             provider        198.51.100.10
 (admin, mgmt LAN)                    vty ACL      on e0/1                             (internet host)
```

## Addressing

| Node | Interface | IPv4 | Connects to |
|---|---|---|---|
| R1 | Loopback0 | 10.255.255.1/32 | — |
| R1 | Ethernet0/0 | 10.1.2.1/24 | R2 e0/0 |
| R1 | Ethernet0/1 | 10.1.101.1/24 | ISP1 e0/0 |
| R2 | Loopback0 | 10.255.255.2/32 | — |
| R2 | Ethernet0/0 | 10.1.2.2/24 | R1 e0/0 |
| R2 | Ethernet0/1 | 192.168.10.1/24 | PC1 (management LAN) |
| ISP1 | Loopback0 | 10.255.255.101/32 | — |
| ISP1 | Ethernet0/0 | 10.1.101.101/24 | R1 e0/1 |
| ISP1 | Ethernet0/1 | 198.51.100.1/24 | PC2 |
| PC1 | eth0 | 192.168.10.10/24, gw .1 | R2 e0/1 |
| PC2 | eth0 | 198.51.100.10/24, gw .1 | ISP1 e0/1 |

| Router | Routing |
|---|---|
| R1 | OSPF 1 area 0 (Lo0, e0/0), `default-information originate always`; BGP 65001, neighbor 10.1.101.101, advertises 192.168.10.0/24 and 10.255.255.1/32 |
| R2 | OSPF 1 area 0 (Lo0, e0/0, e0/1 passive) |
| ISP1 | BGP 64511, neighbor 10.1.101.1 (passive), advertises 198.51.100.0/24 and 10.255.255.101/32 |
