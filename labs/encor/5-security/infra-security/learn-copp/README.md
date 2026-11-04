# Control Plane Policing (CoPP) — Learning Lab

> **Blueprint:** ENCOR 5.2.b — Configure and verify infrastructure security features: CoPP
> (also ENARSI 3.3 — Troubleshoot CoPP: Telnet, SSH, HTTP(S), SNMP, EIGRP, OSPF, BGP)
> **Mode:** Learning (guided build) · **Nodes:** 5 licensed (3 routers, 2 hosts) · **Time:** ~60 min

<!--
This README is copied verbatim into the lab's CML Notes (tools/sync_notes.py), so it must read well inside CML:
plain Markdown, ASCII diagrams (no Mermaid), no links to solution files.
Order: objectives and steps first; lab access, topology and addressing in the Reference section at the bottom.
-->

## What you'll learn
- Sort the traffic a router *receives for itself* into classes: routing, management, monitoring, everything
  else.
- Build CoPP the MQC way: ACLs → class-maps → policy-map → `control-plane` / `service-policy input`.
- Read `show policy-map control-plane`: which class a packet landed in, and whether it conformed or was dropped.
- Explain why the BGP class must match TCP port 179 as a source *and* as a destination.
- See four classic CoPP mistakes break things, and recognize each one from its symptoms:
  OSPF left out, OSPF matched too narrowly (stuck in EXSTART), SSH policed too low, and a class-default that
  drops ARP.

## Starting point
Logins, the topology diagram and the addressing table are in **Reference** at the end of this guide.

The network already works. This lab is about protecting a router, not building one:
- **R1** is your internet edge. It runs OSPF area 0 with **R2** (inside) and eBGP with **ISP1** (AS 64511).
  It originates a default route into OSPF and advertises the management LAN 192.168.10.0/24 and its Loopback0 to
  ISP1. **R1 is the only router you change.**
- **PC1** is the admins' workstation on the management LAN, 192.168.10.0/24, behind R2.
- **PC2** is "somebody on the internet", behind ISP1.
- ISP1 belongs to the provider. It's configured as the *passive* side of the BGP session
  (`transport connection-mode passive`), so R1 always opens the TCP connection. Both sides use BGP timers
  10/30 (keepalive/hold) instead of 60/180, so failures show up in 30 seconds instead of 3 minutes.

Wait about a minute after starting the lab, until the routers finish booting, before you test.

## Step 1 — Baseline: what reaches R1 today
CoPP filters the **control plane**: packets the router has to process itself (routing updates, logins, pings to
its addresses, ARP). Transit traffic forwarded *through* the router isn't affected. Right now nothing limits it.

**PC1** (admin)
```
ping -c 2 198.51.100.10
telnet 10.255.255.1          (log in with cisco / cisco, then exit)
ssh cisco@10.255.255.1       (answer yes to the host key, log in, exit)
```
**PC2** (internet)
```
telnet 10.1.101.1            (press Ctrl+] then type quit)
ping -c 20 -i 0.2 -s 1400 10.1.101.1
```
**Output (captured)**
```
PC1: 2 packets transmitted, 2 packets received, 0% packet loss
PC1: Connected to 10.255.255.1
PC2: Connected to 10.1.101.1
PC2: 20 packets transmitted, 20 packets received, 0% packet loss
```
Look for: anyone on the internet gets a **login prompt** on your edge router, and can make it answer a stream of
large pings as fast as they like. In real life that's a brute-force target and a CPU you don't control.

Now look at the BGP session's TCP ports:

**R1**
```
show tcp brief
```
**Output (captured)**
```
TCB       Local Address               Foreign Address             (state)
71B269E2AC48  10.1.101.1.38541           10.1.101.101.179            ESTAB
------------  0.0.0.0.23                 *.*                         LISTEN
------------  0.0.0.0.22                 *.*                         LISTEN
```
Look for: R1 uses a random port (38541) and ISP1 uses **179**. So every BGP packet R1 *receives* has **source**
port 179, not destination port 179. Remember that for Step 2.

## Step 2 — Classify: one ACL per kind of traffic
In CoPP an ACL doesn't permit or deny anything. It **selects** packets for a class. `permit` means "this packet
belongs to the class".

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
end
```
> **Why each line:**
> - **Routing:** OSPF to *any* destination: hellos go to the multicast 224.0.0.5, but the database exchange
>   (DBD, LSR) is sent unicast to R1's interface address. BGP **both ways**: line 20 catches a session ISP1
>   opens to R1 (destination 179), line 30 catches the session R1 opened (source 179, Step 1). EIGRP isn't
>   running here, but a template usually lists every routing protocol the router could run.
> - **Management:** SSH, Telnet, HTTP and HTTPS, **only from the management LAN** as source. Anyone else trying
>   to log in falls through to the catch-all. (IOL-XE runs the HTTP and HTTPS servers by default; they're in the
>   class so they're covered, but they won't serve you a page in this lab.)
> - **Monitoring:** SNMP from the management LAN, and ICMP from anywhere. ICMP stays open so ping and traceroute
>   keep working, but it gets a small rate. (The PCs have no SNMP client, so this lab classifies SNMP without
>   testing it.)
> - **Catch-all:** every other IP packet addressed to R1. Non-IP traffic such as ARP never matches an IP ACL, so
>   it ends up in `class-default`.

## Step 3 — Class-maps: name the classes
**R1**
```
configure terminal
class-map match-all CM-ROUTING
 match access-group name COPP-ROUTING
class-map match-all CM-MGMT
 match access-group name COPP-MGMT
class-map match-any CM-MONITOR
 match access-group name COPP-SNMP
 match access-group name COPP-ICMP
class-map match-all CM-CATCHALL
 match access-group name COPP-CATCHALL
end
```
> **Why `match-any` for CM-MONITOR:** with two `match` lines, `match-all` means a packet must match **both**
> ACLs: be SNMP *and* ICMP at the same time, which is impossible, so the class would never match anything.
> `match-any` means either one. With a single `match` line the keyword makes no difference.

## Step 4 — Policy-map: a rate for each class
**R1**
```
configure terminal
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
end
```
> **Why these numbers:** `police <bps>` is a token bucket: traffic up to the rate (plus a burst, `bc`) *conforms*,
> the rest *exceeds*. Each class says what to do with each.
> - **Routing** is never dropped (exceed → transmit). The policer just counts, so you can see how much routing
>   traffic there is. Losing OSPF or BGP hurts far more than a busy CPU.
> - **Management** gets plenty for a few admins (256 kbps), and a brute-force flood is capped.
> - **Monitoring** is deliberately small: 16 kbps is about 20 normal pings a second.
> - **Catch-all** is dropped whatever the rate (conform → drop). IOS rejects a plain `drop` in a control-plane
>   class, so this is how you write "drop everything".
> - **class-default** gets a modest rate, and must **not** drop. You'll see why in Step 9.
>
> Classes are checked top down and the first match wins, like ACL lines. Order matters: put CM-CATCHALL above
> CM-ROUTING and it would swallow OSPF and BGP.

## Step 5 — Apply it, and read the counters
**R1**
```
configure terminal
control-plane
 service-policy input PM-COPP
end
```
**PC2**
```
telnet 10.1.101.1
ping -c 20 -i 0.2 -s 1400 10.1.101.1
ping -c 3 10.1.101.1
```
**PC1**
```
telnet 10.255.255.1
ping -c 2 198.51.100.10
```
**Output (captured)**
```
PC2: (telnet hangs; no prompt. Press Ctrl+C)
PC2: 20 packets transmitted, 5 packets received, 75% packet loss
PC2: 3 packets transmitted, 3 packets received, 0% packet loss
PC1: Connected to 10.255.255.1
PC1: 2 packets transmitted, 2 packets received, 0% packet loss
```
**R1**
```
show policy-map control-plane
```
**Output (captured, trimmed)**
```
    Class-map: CM-ROUTING (match-all)
      police:
          cir 256000 bps, bc 8000 bytes
        conformed 18 packets, 1482 bytes; actions:
          transmit
    Class-map: CM-MGMT (match-all)
          cir 256000 bps, bc 8000 bytes
        conformed 20 packets, 2908 bytes; actions:
    Class-map: CM-MONITOR (match-any)
      Match: access-group name COPP-SNMP
        0 packets, 0 bytes
      Match: access-group name COPP-ICMP
        25 packets, 29330 bytes
          cir 16000 bps, bc 1500 bytes
        conformed 10 packets, 7700 bytes; actions:
          transmit
        exceeded 15 packets, 21630 bytes; actions:
          drop
    Class-map: CM-CATCHALL (match-all)
          cir 8000 bps, bc 1500 bytes
        conformed 5 packets, 370 bytes; actions:
          drop
    Class-map: class-default (match-any)
          cir 64000 bps, bc 2000 bytes
        conformed 2 packets, 812 bytes; actions:
          transmit
```
Look for:
- PC2's telnet SYNs counted in **CM-CATCHALL** and dropped. The connection just times out. CoPP drops silently;
  unlike an interface ACL, it sends no ICMP "unreachable".
- The 1400-byte ping flood mostly **exceeded** CM-MONITOR, while a normal ping still gets through.
- The admin from PC1 still gets in, and transit traffic (PC1 → PC2) isn't affected at all.

> **Why:** the policy is attached to the *control plane*, a virtual interface in front of the route processor.
> Only packets punted to the CPU pass through it. `bc` is the burst the policer allows: IOS picks it from the
> rate unless you set it (8000 bytes at 256 kbps, but only 1500 at 16 kbps). Keep that in mind for Step 8.

## Step 6 — Break it: BGP replies unclassified
Remove the line that matches **source** port 179:

**R1**
```
configure terminal
ip access-list extended COPP-ROUTING
 no 30
end
```
Wait 30 seconds (the hold time), then:

**R1**
```
show ip bgp summary | begin Neighbor
show logging | include BGP
show tcp brief
```
**Output (captured)**
```
Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
10.1.101.101    4        64511       0       0        1    0    0 00:01:03 Active

%BGP-3-NOTIFICATION: sent to neighbor 10.1.101.101 4/0 (hold time expired) 0 bytes
%BGP-5-ADJCHANGE: neighbor 10.1.101.101 Down BGP Notification sent

TCB       Local Address               Foreign Address             (state)
71B26C2805F8  10.1.101.1.34657           10.1.101.101.179            SYNSENT
```
Look for: *hold time expired* (R1 stopped hearing ISP1's keepalives), then **SYNSENT** forever: R1's new SYN goes
out, but ISP1's SYN-ACK comes back from port 179 to a random port, falls into CM-CATCHALL and is dropped.

> **Why:** CoPP sees only what R1 *receives*. Which side opens a TCP session decides which port the received
> packets use, and a router may be either side. Matching only `eq bgp` as destination works by luck when the
> neighbor happens to open the session.

Put it back:

**R1**
```
configure terminal
ip access-list extended COPP-ROUTING
 30 permit tcp any eq bgp any
end
```
BGP is Established again within about a minute (R1 retries the connection on a timer).

## Step 7 — Break it: OSPF left out, then matched too narrowly
First, take OSPF out of the routing class completely:

**R1**
```
configure terminal
ip access-list extended COPP-ROUTING
 no 10
end
```
Wait about 40 seconds:

**Output (captured)**
```
R1# show logging | include OSPF
%OSPF-5-ADJCHG: Process 1, Nbr 10.255.255.2 on Ethernet0/0 from FULL to DOWN, Neighbor Down: Dead timer expired
```
The hellos land in CM-CATCHALL and are dropped, so the neighbor dies after the 40-second dead timer.

A subtler version: match only the hello address.

**R1**
```
configure terminal
ip access-list extended COPP-ROUTING
 10 permit ospf any host 224.0.0.5
end
```
Wait about 40 seconds, then on **R1** and **R2**: `show ip ospf neighbor`

**Output (captured)**
```
R1: 10.255.255.2      1   EXSTART/DR      00:00:39    10.1.2.2        Ethernet0/0
R2: 10.255.255.1      1   EXSTART/BDR     00:00:39    10.1.2.1        Ethernet0/0
```
Look for: hellos get through (the dead timer keeps resetting, so the neighbor never goes down), but the adjacency is
stuck in **EXSTART**. The DBD packets that negotiate the exchange are unicast to 10.1.2.1, and they're dropped.

> **Why:** EXSTART that never ends usually points to an MTU mismatch. Here the cause is that the unicast half of
> OSPF is filtered somewhere, which looks exactly the same. When an adjacency hangs in EXSTART or EXCHANGE and
> the MTUs match, check what filters the router's own traffic.

Restore the designed line:

**R1**
```
configure terminal
ip access-list extended COPP-ROUTING
 no 10
 10 permit ospf any any
end
```

## Step 8 — Break it: SSH policed too low
**R1**
```
configure terminal
policy-map PM-COPP
 class CM-MGMT
  police 32000 conform-action transmit exceed-action drop
end
```
**PC1**
```
ssh cisco@10.255.255.1
telnet 10.255.255.1
```
**Output (captured)**
```
PC1: ssh hangs without a password prompt (2 of 2 tries; Ctrl+C)
PC1: Connected to 10.255.255.1

R1# show policy-map control-plane input class CM-MGMT
      police:
          cir 32000 bps, bc 1500 bytes
        conformed 41 packets, 4404 bytes; actions:
          transmit
        exceeded 18 packets, 27252 bytes; actions:
          drop
```
Look for: Telnet works and SSH doesn't, in the same class. The exceeded packets average **1514 bytes**.

> **Why:** at 32 kbps IOS sets the burst to 1500 bytes. A policer can't pass a packet bigger than its bucket, so a
> full-size 1514-byte frame **always exceeds**, however idle the class is. Telnet sends tiny packets. The SSH
> handshake includes full-size packets (the key exchange, where both sides list every algorithm they support),
> and when they're dropped every time, the handshake never finishes. When a policer breaks one protocol and not
> another, compare packet sizes with `bc`, not just average rates.

Restore 256 kbps:

**R1**
```
configure terminal
policy-map PM-COPP
 class CM-MGMT
  police 256000 conform-action transmit exceed-action drop
end
```

## Step 9 — Break it: a class-default that drops
"Drop everything not listed" sounds safe. Try it:

**R1**
```
configure terminal
policy-map PM-COPP
 class class-default
  police 8000 conform-action drop exceed-action drop
end
```
ARP entries last for hours, so make R2 ask again:

**R2**
```
clear ip arp 10.1.2.1
ping 10.1.2.1
show ip arp 10.1.2.1
show ip ospf neighbor
```
**PC1**
```
ping -c 2 198.51.100.10
```
**Output (captured)**
```
R2: Success rate is 0 percent (0/3)
R2: Internet  10.1.2.1                0   Incomplete      ARPA
R2: 10.255.255.1      1   FULL/BDR        00:00:35    10.1.2.1        Ethernet0/0
PC1: 2 packets transmitted, 0 packets received, 100% packet loss
```
Look for: OSPF is still **FULL**, and routing tables look perfect, but nothing is forwarded to R1, because R2
can't resolve R1's MAC address.

> **Why:** ARP isn't IP, so no IP ACL can match it, and it ends up in class-default. Drop class-default and you
> drop ARP (and on real networks also CDP, LLDP, keepalives and more). OSPF stays up because hellos are
> multicast and need no ARP, which makes the failure confusing. This is why a "deny everything else" class is
> written as an **IP** catch-all (CM-CATCHALL) and class-default stays permissive.

Restore it:

**R1**
```
configure terminal
policy-map PM-COPP
 class class-default
  police 64000 conform-action transmit exceed-action drop
end
```
PC1's ping to 198.51.100.10 works again within a few seconds.

## Final check
| From | Test | Result |
|---|---|---|
| R1 | `show ip ospf neighbor` | R2 FULL |
| R1 | `show ip bgp summary` | 10.1.101.101 with 2 prefixes |
| PC1 | `ping -c 2 198.51.100.10` | works (transit) |
| PC1 | `telnet 10.255.255.1`, `ssh cisco@10.255.255.1` | login prompts |
| PC2 | `telnet 10.1.101.1` | times out |
| PC2 | `ping -c 3 10.1.101.1` | works |
| PC2 | `ping -c 20 -i 0.2 -s 1400 10.1.101.1` | heavy loss |
| R1 | `show policy-map control-plane` | every class except CM-MONITOR's SNMP match has counters |

## Check yourself
- Which class does a ping from PC1 *through* R1 to PC2 hit? (Trick question.)
- ISP1 is reconfigured to open the BGP session itself. Which line of COPP-ROUTING does the traffic match now?
- Why is CM-ROUTING's exceed action `transmit` instead of `drop`?
- You add `match access-group name COPP-MGMT` to CM-MONITOR and leave it `match-all`. What happens to pings?
- An admin on 192.168.20.0/24 can't SSH to R1 but can ping it. Which class did their SSH land in?
- Why did PC2's blocked telnet *time out*, when a blocked telnet in an interface ACL lab says *Host is
  unreachable*?
- What would you check first if an OSPF neighbor sat in EXSTART on a router with CoPP?

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1 | IOL-XE router (your edge, the only one you change) | cisco | cisco | cisco |
| R2 | IOL-XE router (inside) | cisco | cisco | cisco |
| ISP1 | IOL-XE router (provider; look, don't change) | cisco | cisco | cisco |
| PC1, PC2 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → Console). Routers start in privileged EXEC.
Each node also has a label in the CML canvas with its login and addresses.

## Topology

```
                 OSPF area 0                 eBGP 65001 <-> 64511
 PC1 ── e0/1 R2 e0/0 ── 10.1.2.0/24 ── e0/0 R1 e0/1 ── 10.1.101.0/24 ── e0/0 ISP1 e0/1 ── PC2
 192.168.10.10   inside                 edge (CoPP)                     provider        198.51.100.10
 (admin, mgmt LAN)                                                                      (internet host)
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
