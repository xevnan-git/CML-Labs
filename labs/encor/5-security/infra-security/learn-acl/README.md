# ACLs: Standard, Extended, Named and Time-Based — Learning Lab

> **Blueprint:** ENCOR 5.2.a — Configure and verify infrastructure security features: ACLs
> (also ENARSI 3.2.a — Troubleshoot IPv4 ACLs: standard, extended, time-based)
> **Mode:** Learning (guided build) · **Nodes:** 5 licensed (2 routers, 3 hosts) · **Time:** ~60 min

<!--
This README is copied verbatim into the lab's CML Notes (tools/sync_notes.py), so it must read well inside CML:
plain Markdown, ASCII diagrams (no Mermaid), no links to solution files.
Order: objectives and steps first; lab access, topology and addressing in the Reference section at the bottom.
-->

## What you'll learn
- Explain why a **standard** ACL belongs near the destination by placing one at the wrong end first and watching
  it block too much.
- Write a named **extended** ACL near the source, and read its per-line hit counters.
- See that a new line goes to the **end** of an ACL, and use sequence numbers to insert it where it belongs.
- Break OSPF with the **implicit deny**, recognize it in the log, and fix it.
- Use `established` to let return traffic in without letting new connections in.
- Lock router logins down with `access-class` on the vty lines.
- Make a line apply only during business hours with a **time-range**.
- Read wildcard masks: `0.0.0.255` is one /24, and `0.0.1.255` covers two adjacent ones.

## Starting point
Logins, the topology diagram and the addressing table are in **Reference** at the end of this guide.

This lab is about ACLs, not routing, so the network already works: every address is configured and OSPF area 0
runs between R1 and R2. **There are no ACLs anywhere.** The hosts are preconfigured, and SRV1 runs a web server
(port 80) and SSH (port 22).

You're the network engineer for a small company:

| Network | Who | Policy you'll build |
|---|---|---|
| VLAN 10, 192.168.10.0/24 (PC1) | Staff | Go anywhere. Only staff may log in to the routers. |
| VLAN 11, 192.168.11.0/24 (PC2) | Contractors | On the server LAN: web on SRV1 (business hours only) and ping SRV1. Nothing else there. Elsewhere: allowed. |
| VLAN 50, 192.168.50.0/24 (SRV1) | Servers at HQ | Must not be able to open connections *into* the branch. |

Wait about a minute after starting the lab, until the routers finish booting, before you test.

## Step 1 — Baseline: everything is open
Before filtering anything, prove what works, so you can tell later whether an ACL broke something or it never
worked.

**PC2**
```
ping -c 2 192.168.50.10
ping -c 2 172.18.0.1
wget -q -O - http://192.168.50.10/
nc -zv -w 3 192.168.50.10 22
```
**Output (captured)**
```
64 bytes from 192.168.50.10: seq=0 ttl=42 time=4.145 ms
64 bytes from 172.18.0.1: seq=0 ttl=42 time=0.989 ms
<h1>SRV1 intranet</h1>
192.168.50.10 (192.168.50.10:22) open
```
Look for: the contractor PC reaches the server (ping, web **and** SSH) and the HQ users network 172.18.0.0/24.

## Step 2 — Standard ACL: first at the wrong end
First requirement: *contractors must not reach the server LAN.* A **standard** ACL matches only the **source**
address, so it can say "contractors" but not "going to the servers". Put it on R1, right next to the
contractors, and see what happens.

**R1**
```
configure terminal
access-list 10 deny 192.168.11.0 0.0.0.255
access-list 10 permit any
interface Ethernet0/2
 ip access-group 10 in
end
```
**PC2**
```
ping -c 2 192.168.50.10
ping -c 2 172.18.0.1
ping -c 1 192.168.11.1
```
**Output (captured)**
```
2 packets transmitted, 0 packets received, 100% packet loss
2 packets transmitted, 0 packets received, 100% packet loss
1 packets transmitted, 0 packets received, 100% packet loss
```
```
R1# show access-lists 10
Standard IP access list 10
    10 deny   192.168.11.0, wildcard bits 0.0.0.255 (10 matches)
    20 permit any (10 matches)
```
Look for: the contractors lost **everything**, not just the servers. Even their own gateway doesn't answer.

> **Why:** Applied inbound on e0/2, the ACL sees every packet the contractors send, whatever its destination.
> Because a standard ACL can't look at the destination, it drops it all. That's the rule: put a **standard ACL as
> close to the destination as possible**, where only traffic for that destination passes through it.
>
> **Wildcard masks:** `0.0.0.255` means "the first three octets must match, the last can be anything", which is
> 192.168.11.0/24. A 0 bit means *must match* and a 1 bit means *don't care*. It's the inverse of a subnet mask.

Move it to R2, outbound toward the servers:

**R1**
```
configure terminal
interface Ethernet0/2
 no ip access-group 10 in
exit
no access-list 10
end
```
**R2**
```
configure terminal
access-list 10 deny 192.168.11.0 0.0.0.255
access-list 10 permit any
interface Ethernet0/1
 ip access-group 10 out
end
```
**PC2**
```
ping -c 2 192.168.50.10
ping -c 2 172.18.0.1
ping -c 2 192.168.50.1
```
**Output (captured)**
```
2 packets transmitted, 0 packets received, 100% packet loss
2 packets transmitted, 2 packets received, 0% packet loss
2 packets transmitted, 2 packets received, 0% packet loss
```
Look for: SRV1 is blocked, while HQ users (172.18.0.1) work again. Notice that **192.168.50.1**, R2's own
address on the server LAN, still answers.

> **Why:** An outbound ACL filters packets that are *routed out* of that interface. A ping to 192.168.50.1 is
> addressed to R2 itself, so it never goes out of e0/1, and the ACL never sees it. To protect a router's own
> addresses you need something else: `access-class` on the vty lines (Step 7) or Control Plane Policing (CoPP).

## Step 3 — Extended named ACL near the source
The requirement changes: *contractors may use the web server on SRV1, but nothing else on the server LAN.* That
needs protocol and destination, so it's an **extended** ACL. An extended ACL can be precise, so put it **near the
source** and drop unwanted traffic before it crosses the WAN.

Remove the standard ACL from R2 first:

**R2**
```
configure terminal
interface Ethernet0/1
 no ip access-group 10 out
exit
no access-list 10
end
```
**R1**
```
configure terminal
ip access-list extended CONTRACTORS-IN
 permit tcp 192.168.11.0 0.0.0.255 host 192.168.50.10 eq www
 deny ip 192.168.11.0 0.0.0.255 192.168.50.0 0.0.0.255 log
 permit ip 192.168.11.0 0.0.0.255 any
exit
interface Ethernet0/2
 ip access-group CONTRACTORS-IN in
end
```
**PC2**
```
wget -q -O - http://192.168.50.10/
nc -zv -w 3 192.168.50.10 22
ping -c 2 172.18.0.1
```
**Output (captured)**
```
<h1>SRV1 intranet</h1>
nc: 192.168.50.10 (192.168.50.10:22): Host is unreachable
2 packets transmitted, 2 packets received, 0% packet loss
```
```
R1# show access-lists CONTRACTORS-IN
Extended IP access list CONTRACTORS-IN
    10 permit tcp 192.168.11.0 0.0.0.255 host 192.168.50.10 eq www (5 matches)
    20 deny ip 192.168.11.0 0.0.0.255 192.168.50.0 0.0.0.255 log (3 matches)
    30 permit ip 192.168.11.0 0.0.0.255 any (2 matches)

R1# show logging | include SEC-6
%SEC-6-IPACCESSLOGP: list CONTRACTORS-IN denied tcp 192.168.11.10(38953) -> 192.168.50.10(22), 1 packet
```
Look for: web works, SSH is refused with *Host is unreachable* (R1 sends back an ICMP "administratively
prohibited"), and the log names the ACL, the protocol, both addresses and both ports.

> **Why:** An ACL is checked **top down, and the first match wins**. Nothing after it is evaluated. The web line
> must come before the broad deny. The last line, `permit ip … any`, is needed because every ACL ends with an
> invisible **`deny ip any any`**: without it, contractors could reach *only* SRV1's web server and nothing else.
>
> The hit counters are your best troubleshooting tool. `clear ip access-list counters` resets them, then you
> generate one test and see which line it hits.

## Step 4 — Sequence numbers: inserting a line
New requirement: *contractors may also ping SRV1.* Add the obvious line:

**R1**
```
configure terminal
ip access-list extended CONTRACTORS-IN
 permit icmp 192.168.11.0 0.0.0.255 host 192.168.50.10 echo
end
```
**PC2**
```
ping -c 2 192.168.50.10
```
**Output (captured)**
```
2 packets transmitted, 0 packets received, 100% packet loss
```
```
R1# show access-lists CONTRACTORS-IN
Extended IP access list CONTRACTORS-IN
    10 permit tcp 192.168.11.0 0.0.0.255 host 192.168.50.10 eq www (5 matches)
    20 deny ip 192.168.11.0 0.0.0.255 192.168.50.0 0.0.0.255 log (5 matches)
    30 permit ip 192.168.11.0 0.0.0.255 any (2 matches)
    40 permit icmp 192.168.11.0 0.0.0.255 host 192.168.50.10 echo
```
Look for: the new line got sequence **40**, at the end, with no matches. The pings hit line 20 first.

Move it. With a named ACL (or numbered ACLs on modern IOS) you can delete one line by number and insert a line by
giving it a number:

**R1**
```
configure terminal
ip access-list extended CONTRACTORS-IN
 no 40
 15 permit icmp 192.168.11.0 0.0.0.255 host 192.168.50.10 echo
end
```
**PC2**: `ping -c 2 192.168.50.10` now gets 2 replies.

Squeezing lines in between leaves odd numbers like 15. Renumber the ACL to make room again:

**R1**
```
configure terminal
ip access-list resequence CONTRACTORS-IN 10 10
end
show access-lists CONTRACTORS-IN
```
**Output (captured)**
```
Extended IP access list CONTRACTORS-IN
    10 permit tcp 192.168.11.0 0.0.0.255 host 192.168.50.10 eq www (5 matches)
    20 permit icmp 192.168.11.0 0.0.0.255 host 192.168.50.10 echo (2 matches)
    30 deny ip 192.168.11.0 0.0.0.255 192.168.50.0 0.0.0.255 log (5 matches)
    40 permit ip 192.168.11.0 0.0.0.255 any (2 matches)
```
> **Why:** Before sequence numbers, the only way to put a line in the middle of a numbered ACL was to delete the
> whole ACL and type it again (with the ACL still applied, often locking yourself out halfway). `resequence <start>
> <step>` renumbers the lines without changing their order or their counters.

## Step 5 — The implicit deny kills OSPF
Requirement: *HQ servers must not open connections into the branch.* Filter what comes **into** R1 from HQ.
Branch users still need their replies, so allow TCP replies (`established`) and ICMP:

**R1**
```
configure terminal
ip access-list extended BRANCH-IN
 permit tcp any 192.168.10.0 0.0.1.255 established
 permit icmp any any
 deny ip any any log
exit
interface Ethernet0/0
 ip access-group BRANCH-IN in
end
```
Everything still works for about 40 seconds. Then:

**PC1**
```
wget -q -O - http://192.168.50.10/
```
**Output (captured, about 45 s later)**
```
wget: can't connect to remote host (192.168.50.10): Host is unreachable
```
```
R1# show logging | include OSPF|BRANCH-IN
%SEC-6-IPACCESSLOGRP: list BRANCH-IN denied ospf 10.1.2.2 -> 224.0.0.5, 1 packet
%OSPF-5-ADJCHG: Process 1, Nbr 10.255.255.2 on Ethernet0/0 from FULL to DOWN, Neighbor Down: Dead timer expired
%SEC-6-IPACCESSLOGRP: list BRANCH-IN denied ospf 10.1.2.2 -> 10.1.2.1, 1 packet

R1# show ip ospf neighbor
(empty)
R1# show ip route 192.168.50.0
% Network not in table
```
Look for: R2's OSPF hellos (to 224.0.0.5) denied by your ACL, then the dead timer expiring 40 seconds later and
every HQ route disappearing.

> **Why:** An inbound ACL filters **everything** that arrives on the interface, including the routing protocol
> packets addressed to the router itself. OSPF (IP protocol 89) matches none of your permits, so it hits the deny.
> It's the implicit deny's favorite victim. Your explicit `deny ip any any log` is a deliberate copy of the
> implicit deny: it works the same way but gives you counters and log messages.

Insert the fix **above** everything else, then tidy up the numbers:

**R1**
```
configure terminal
ip access-list extended BRANCH-IN
 5 permit ospf any any
exit
ip access-list resequence BRANCH-IN 10 10
end
```
Within a few seconds, `show ip ospf neighbor` shows R2 **FULL** again.

## Step 6 — `established`: replies in, new connections out
Test both directions now that routing is back.

**PC1** (branch → HQ)
```
nc -zv -w 3 192.168.50.10 22
wget -q -O - http://192.168.50.10/
```
**SRV1** (HQ → branch; PC1 also runs SSH)
```
nc -zv -w 3 192.168.10.10 22
ping -c 2 192.168.10.10
```
**Output (captured)**
```
PC1:  192.168.50.10 (192.168.50.10:22) open
PC1:  <h1>SRV1 intranet</h1>
SRV1: nc: 192.168.10.10 (192.168.10.10:22): Host is unreachable
SRV1: 2 packets transmitted, 2 packets received, 0% packet loss
```
```
R1# show access-lists BRANCH-IN
Extended IP access list BRANCH-IN
    10 permit ospf any any (13 matches)
    20 permit tcp any 192.168.10.0 0.0.1.255 established (14 matches)
    30 permit icmp any any (2 matches)
    40 deny ip any any log (13 matches)

%SEC-6-IPACCESSLOGP: list BRANCH-IN denied tcp 192.168.50.10(37691) -> 192.168.10.10(22), 1 packet
```
Look for: PC1's connections work and SRV1's don't, and the denied packet is SRV1's opening SYN.

> **Why:** `established` matches TCP segments with the **ACK or RST** flag set. Every segment of a TCP conversation
> has ACK set except the very first one, the SYN that opens it. So replies to connections the branch opened are
> permitted, and a SYN from HQ falls through to the deny. It's a stateless check of a header bit, not a real state
> table: it only works for TCP (UDP has no flags), and a crafted packet with ACK set gets through. Stateful
> firewalls and reflexive ACLs do it properly.
>
> **Wildcard check:** `192.168.10.0 0.0.1.255` matches 192.168.**10**.x *and* 192.168.**11**.x, because the
> last bit of the third octet is "don't care". That's why the contractors' web replies get through too.

## Step 7 — Protect the routers' own logins: `access-class`
Requirement: *only staff may log in to the routers.* An interface ACL is the wrong tool: there are many paths to
a router's many addresses. Filter on the **vty lines** instead, so it applies to Telnet and SSH on every address.

**R1** and **R2** (same commands on both)
```
configure terminal
ip access-list standard VTY-ADMIN
 permit 192.168.10.0 0.0.0.255
exit
line vty 0 4
 access-class VTY-ADMIN in
end
```
**PC2**
```
telnet 10.255.255.2
telnet 192.168.11.1
```
**PC1**
```
telnet 10.255.255.2
```
**Output (captured)**
```
PC2: telnet: can't connect to remote host (10.255.255.2): Connection refused
PC2: telnet: can't connect to remote host (192.168.11.1): Connection refused
PC1: Connected to 10.255.255.2   (log in with cisco / cisco, then exit)
```
```
R2# show access-lists VTY-ADMIN
Standard IP access list VTY-ADMIN
    10 permit 192.168.10.0, wildcard bits 0.0.0.255 (4 matches)
```
Look for: *Connection refused* (the router rejects the session) rather than a timeout.

> **Why:** `access-class … in` checks the **source** address of incoming Telnet/SSH sessions, so a standard ACL is
> enough. It covers every interface and every address on the router at once. Apply it to **all** vty lines:
> these routers have exactly vty 0–4 (`show line`), but many platforms have 0–15, and one unprotected line is
> enough to get in. Denied attempts don't show up as matches; only the permit line counts.

## Step 8 — Time-based ACL: web only during business hours
Last requirement: *contractors get web access to SRV1 on weekdays from 08:00 to 17:00 only.*

**R1**
```
configure terminal
time-range BUSINESS-HOURS
 periodic weekdays 8:00 to 17:00
exit
ip access-list extended CONTRACTORS-IN
 no 10
 10 permit tcp 192.168.11.0 0.0.0.255 host 192.168.50.10 eq www time-range BUSINESS-HOURS
end
show clock
show time-range
```
The routers have no NTP server, so they boot with the CML host's clock in **UTC**. Make it *outside* business
hours first (pick a Monday; any weekday works):

**R1**
```
clock set 04:00:00 2 Nov 2026
show access-lists CONTRACTORS-IN
```
**PC2**: `wget -q -T 3 -O - http://192.168.50.10/`

**Output (captured)**
```
time-range entry: BUSINESS-HOURS (inactive)
   periodic weekdays 8:00 to 17:00
   used in: IP ACL entry

Extended IP access list CONTRACTORS-IN
    10 permit tcp 192.168.11.0 0.0.0.255 host 192.168.50.10 eq www time-range BUSINESS-HOURS (inactive)
    20 permit icmp 192.168.11.0 0.0.0.255 host 192.168.50.10 echo (2 matches)
    30 deny ip 192.168.11.0 0.0.0.255 192.168.50.0 0.0.0.255 log (5 matches)
    40 permit ip 192.168.11.0 0.0.0.255 any (5 matches)

PC2: wget: can't connect to remote host (192.168.50.10): Host is unreachable
```
Now move into business hours:

**R1**
```
clock set 10:00:00 2 Nov 2026
show access-lists CONTRACTORS-IN | include www
```
**Output (captured)**
```
    10 permit tcp 192.168.11.0 0.0.0.255 host 192.168.50.10 eq www time-range BUSINESS-HOURS (active)

PC2: <h1>SRV1 intranet</h1>
```
> **Why:** An inactive line is skipped as if it weren't there, so the web traffic falls to line 30 and is denied.
> The router's own clock decides, so in production a time-based ACL always goes together with NTP. A wrong clock
> or time zone silently opens or closes the window. `periodic` repeats every week; `absolute start … end …`
> defines a one-off window.

## Final check
Your R1 should now contain these ACLs (`show running-config | section ip access-list`):

```
ip access-list standard VTY-ADMIN
 10 permit 192.168.10.0 0.0.0.255
ip access-list extended BRANCH-IN
 10 permit ospf any any
 20 permit tcp any 192.168.10.0 0.0.1.255 established
 30 permit icmp any any
 40 deny ip any any log
ip access-list extended CONTRACTORS-IN
 10 permit tcp 192.168.11.0 0.0.0.255 host 192.168.50.10 eq www time-range BUSINESS-HOURS
 20 permit icmp 192.168.11.0 0.0.0.255 host 192.168.50.10 echo
 30 deny ip 192.168.11.0 0.0.0.255 192.168.50.0 0.0.0.255 log
 40 permit ip 192.168.11.0 0.0.0.255 any
```
And the whole policy holds (inside business hours):

| From | Test | Result |
|---|---|---|
| PC1 | `wget -q -O - http://192.168.50.10/`, `nc -zv 192.168.50.10 22` | both work |
| PC1 | `telnet 10.255.255.2` | login prompt |
| PC2 | `wget -q -O - http://192.168.50.10/`, `ping -c 2 192.168.50.10` | both work |
| PC2 | `nc -zv -w 3 192.168.50.10 22` | Host is unreachable |
| PC2 | `ping -c 2 172.18.0.1` | works |
| PC2 | `telnet 10.255.255.1` | Connection refused |
| SRV1 | `nc -zv -w 3 192.168.10.10 22` | Host is unreachable |
| R1 | `show ip ospf neighbor` | R2 FULL |

## Check yourself
- In Step 2, why did the contractors lose their own gateway (192.168.11.1) but, with the ACL on R2, still reach
  192.168.50.1?
- Which wildcard mask matches only the *odd* hosts of 192.168.11.0/24?
- You append `permit tcp any any eq 22` to CONTRACTORS-IN without a sequence number. Can contractors now SSH to
  SRV1? Why not?
- BRANCH-IN lost OSPF. If R1 and R2 ran BGP instead, what line would you need? And for EIGRP?
- Can SRV1 send a DNS query (UDP) to a server in the branch through BRANCH-IN? Could `established` help?
- Why is `access-class` a better way to protect router logins than an interface ACL?
- The CML server's clock is wrong by 5 hours. What happens to the contractors' web access?

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1, R2 | IOL-XE router | cisco | cisco | cisco |
| PC1, PC2, SRV1 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → Console). Routers start in privileged EXEC.
Each node also has a label in the CML canvas with its login and addresses.

## Topology

```
 PC1 (Staff)
 192.168.10.10 ── e0/1 ┐
                       R1 e0/0 ── 10.1.2.0/24 ── e0/0 R2 e0/1 ── SRV1 (web :80, ssh :22)
 192.168.11.10 ── e0/2 ┘  branch                  HQ  Lo1         192.168.50.10
 PC2 (Contractor)                                     172.18.0.1/24 (HQ users)

                   OSPF area 0 on every router interface
```

## Addressing

| Node | Interface | IPv4 | Connects to |
|---|---|---|---|
| R1 | Loopback0 | 10.255.255.1/32 | — |
| R1 | Ethernet0/0 | 10.1.2.1/24 | R2 e0/0 |
| R1 | Ethernet0/1 | 192.168.10.1/24 | PC1 (VLAN 10 Staff) |
| R1 | Ethernet0/2 | 192.168.11.1/24 | PC2 (VLAN 11 Contractors) |
| R2 | Loopback0 | 10.255.255.2/32 | — |
| R2 | Loopback1 | 172.18.0.1/24 | HQ users (simulated) |
| R2 | Ethernet0/0 | 10.1.2.2/24 | R1 e0/0 |
| R2 | Ethernet0/1 | 192.168.50.1/24 | SRV1 (VLAN 50 Servers) |
| PC1 | eth0 | 192.168.10.10/24, gw .1 | R1 e0/1 |
| PC2 | eth0 | 192.168.11.10/24, gw .1 | R1 e0/2 |
| SRV1 | eth0 | 192.168.50.10/24, gw .1 | R2 e0/1 |

OSPF process 1, area 0, router IDs 10.255.255.N. The LAN interfaces and R2 Lo1 are passive.
