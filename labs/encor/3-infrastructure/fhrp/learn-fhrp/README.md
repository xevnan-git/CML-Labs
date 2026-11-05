# FHRP (HSRP and VRRP) — Learning Lab

> **Blueprint:** ENCOR 3.3.c — Configure first hop redundancy protocols, such as HSRP, VRRP
> (also ENCOR 1.1.b — high availability techniques such as redundancy, FHRP)
> **Mode:** Learning (guided build) · **Nodes:** 5 licensed (3 routers, 2 hosts) + 2 unmanaged switches · **Time:** ~60 min

<!--
This README is copied verbatim into the lab's CML Notes (tools/sync_notes.py), so it must read well inside CML:
plain Markdown, ASCII diagrams (no Mermaid), no links to solution files.
Order: objectives and steps first; lab access, topology and addressing in the Reference section at the bottom.
-->

## What you'll learn
- Give a LAN a **virtual default gateway** shared by two routers, with HSRPv2 and with VRRPv3.
- Read `show standby` and `show vrrp`: active/standby (HSRP), master/backup (VRRP), virtual IP and virtual MAC.
- Control who forwards with **priority** and **preempt**, and see that priority alone doesn't take over.
- Speed up failover with **timers**, and measure it with a continuous ping.
- Hand over when the **uplink** fails, using **object tracking**.
- Protect HSRP with **MD5 authentication**, and see what a key mismatch does.
- Share the load: one router forwards for LAN10, the other for LAN20.
- See what FHRP doesn't fix: the **return path** is up to routing.

## Starting point
Logins, the topology diagram and the addressing table are in **Reference** at the end of this guide.

- **R1** and **R2** both connect to **LAN10** (PC1) and **LAN20** (PC2) through unmanaged switches, and each has an
  uplink to **R3**. R3 holds the "data-center server", **172.16.0.100** (a loopback).
- OSPF already runs on R1, R2 and R3. The LAN interfaces are **passive** (no OSPF neighbors across the LANs), so a
  router whose uplink fails really loses its way to R3.
- R1 and R2 use **.2** and **.3** on each LAN. The PCs' default gateway is **.1**, which doesn't exist yet.
  **You configure R1 and R2 only** (plus a test you run on R3 in Step 5).

**The goal:** .1 is a virtual gateway on both LANs. LAN10 uses **HSRPv2** with R1 forwarding; LAN20 uses **VRRPv3**
with R2 forwarding. Each forwarding router hands over to the other if its uplink fails, and takes back over when it
recovers.

Wait about a minute after starting the lab, until the routers finish booting, before you test.

## Step 1 — Baseline: no gateway
**PC1**
```
ping -c 2 -W 1 172.16.0.100
ip neigh
ping -c 1 -W 1 192.168.10.2
ping -c 1 -W 1 192.168.10.3
```
**R3**
```
show ip route ospf | begin Gateway
```
**Output (captured)**
```
PC1: 2 packets transmitted, 0 packets received, 100% packet loss
PC1: 192.168.10.1 dev eth0  ref 1 used 0/0/0 probes 6 INCOMPLETE
PC1: 64 bytes from 192.168.10.2: seq=0 ttl=42 time=4.031 ms
PC1: 64 bytes from 192.168.10.3: seq=0 ttl=42 time=4.409 ms

O        10.255.255.1/32 [110/11] via 10.1.3.1, 00:00:28, Ethernet0/0
O        10.255.255.2/32 [110/11] via 10.2.3.2, 00:00:29, Ethernet0/1
O     192.168.10.0/24 [110/20] via 10.2.3.2, 00:00:29, Ethernet0/1
                      [110/20] via 10.1.3.1, 00:00:28, Ethernet0/0
O     192.168.20.0/24 [110/20] via 10.2.3.2, 00:00:29, Ethernet0/1
                      [110/20] via 10.1.3.1, 00:00:28, Ethernet0/0
```
Look for: both routers are there and answer on .2 and .3, but nobody answers ARP for .1, so PC1 can't send anything
off the LAN. You *could* point PC1 at .2, but then PC1 is stuck if R1 fails: a PC has one default gateway and no
way to notice it's dead. An FHRP makes .1 a **virtual** address that whichever router is alive answers for.

R3 has two equal-cost routes to each LAN, through R1 and through R2. Keep that in mind for Steps 4 and 5.

## Step 2 — HSRPv2 on LAN10
Configure **R1** first, then **R2**:

**R1** and **R2**
```
configure terminal
interface Ethernet0/0
 standby version 2
 standby 10 ip 192.168.10.1
end
```
> **Why each piece:** `standby version 2` uses multicast 224.0.0.102 and allows group numbers 0–4095 (version 1:
> 224.0.0.2, groups 0–255). Both routers must run the same version. Group 10 matches the VLAN: a common convention,
> not a rule. Set the version **before** the first group line.

Wait 15 seconds. **R2**: `show standby brief` and `show standby Ethernet0/0`. **R1**: `show standby brief`.
**PC1**: `ping -c 2 -W 1 172.16.0.100`, `ip neigh` and `traceroute -n -q 1 -w 1 172.16.0.100`.

**Output (captured)**
```
R2# show standby brief
Interface   Grp  Pri P State   Active          Standby         Virtual IP
Et0/0       10   100   Active  local           192.168.10.2    192.168.10.1
R1# show standby brief
Et0/0       10   100   Standby 192.168.10.3    local           192.168.10.1

R2# show standby Ethernet0/0          (taken while it was still settling)
Ethernet0/0 - Group 10 (version 2)
  Virtual IP address is 192.168.10.1
    Local virtual MAC address is 0000.0c9f.f00a (v2 default)
  Hello time 3 sec, hold time 10 sec
  Preemption disabled
  Priority 100 (default 100)

PC1: 64 bytes from 172.16.0.100: seq=0 ttl=42 time=5.553 ms
PC1: 192.168.10.1 dev eth0 lladdr 00:00:0c:9f:f0:0a ref 1 used 0/0/0 probes 6 DELAY
PC1:  1  192.168.10.3  2.740 ms
      2  10.2.3.3  3.828 ms
```
Look for:
- PC1 reaches the server. Its ARP entry for .1 is the **virtual MAC** 0000.0c9f.f00**a**: HSRPv2 builds it from
  0000.0c9f.f000 + the group number (10 = 0x00a). The Active router answers ARP for .1 with that MAC.
- `traceroute` shows which router forwards: hop 1 is the **real** address of the Active router (.3 = R2).
- **R2 became Active although you configured R1 first.** With equal priorities the higher interface IP wins.
  R1 hadn't finished its election yet: a new HSRP router listens for a hold time (10 s) before it can go Active,
  and R2 joined within that window.

## Step 3 — Priority and preempt
Make R1 the forwarder for LAN10:

**R1**
```
configure terminal
interface Ethernet0/0
 standby 10 priority 110
end
show standby brief
```
**Output (captured)**
```
Et0/0       10   110   Standby 192.168.10.3    local           192.168.10.1
```
Look for: R1 now has the higher priority and is **still Standby**. HSRP doesn't replace a working Active router
just because a better one appears, unless that router is allowed to **preempt**.

**R1** and **R2**
```
configure terminal
interface Ethernet0/0
 standby 10 preempt
 standby 10 timers 1 3
end
```
**R1**: `show standby Ethernet0/0`. **PC1**: `traceroute -n -q 1 -w 1 172.16.0.100`.

**Output (captured)**
```
Ethernet0/0 - Group 10 (version 2)
  State is Active
  Virtual IP address is 192.168.10.1
  Active virtual MAC address is 0000.0c9f.f00a (MAC In Use)
  Hello time 1 sec, hold time 3 sec
  Preemption enabled
  Active router is local
  Standby router is 192.168.10.3, priority 100 (expires in 3.008 sec)
  Priority 110 (configured 110)

PC1:  1  192.168.10.2  1.798 ms
      2  10.1.3.3  3.104 ms
```
> **Why each piece:**
> - **Priority** (default 100, higher wins) decides the election; **preempt** lets a higher-priority router take over
>   from a working Active. Put preempt on **both** routers: R1 needs it to take back over after a failure (Step 4),
>   R2 needs it to take over when tracking lowers R1's priority (Step 5).
> - **Timers 1 3:** hello every second, declare the Active dead after 3 seconds without hellos (default 3 and 10).
>   Configure them on both; the Active router's timers are also learned by the others.
> - The virtual MAC stays the same when the Active router changes, so PCs don't need to re-ARP.

## Step 4 — Failover and failback
Open a console on **PC1** and start a continuous ping, 5 per second:
```
ping -i 0.2 172.16.0.100
```
While it runs, fail R1's LAN interface:

**R1**
```
configure terminal
interface Ethernet0/0
 shutdown
end
```
**R2**: `show logging | include HSRP`. Then on **PC1**, stop the ping with Ctrl+C and read the summary.

**Output (captured)**
```
R2: %HSRP-5-STATECHANGE: Ethernet0/0 Grp 10 state Standby -> Active

PC1 (ping run of 352 replies across the failover): no sequence numbers missing
```
Look for: no lost pings. A `shutdown` is a *graceful* failure: before the interface goes down, R1 sends an HSRP
**resign**, and R2 takes over immediately instead of waiting for the hold time. A crash or a cut cable gives no
warning, so the standby waits up to the hold time (3 s here, 10 s with default timers) before it takes over.

Bring R1 back:

**R1**
```
configure terminal
interface Ethernet0/0
 no shutdown
end
show logging | include HSRP
```
**Output (captured)**
```
%HSRP-5-STATECHANGE: Ethernet0/0 Grp 10 state Active -> Init
%HSRP-5-STATECHANGE: Ethernet0/0 Grp 10 state Listen -> Active
```
Look for: R1 takes back over as soon as it hears R2 (**preempt**). Without preempt on R1, R2 would stay Active
until *it* failed.

> **Going further: a silent failure.** The lab tests above also "pulled the cable" between R1 and SW1 (CML link
> stop) during a 2-minute ping. R2 went Active, as expected, **but PC1 lost 91% of its
> pings for as long as the cable was out**. On IOL a stopped link leaves R1's e0/0 up/up, so R1 kept advertising
> LAN10 in OSPF, and R3's CEF sent the server's replies to R1, which couldn't deliver them:
> ```
> R3# show ip cef exact-route 172.16.0.100 192.168.10.10
> 172.16.0.100 -> 192.168.10.10 =>IP adj out of Ethernet0/0, addr 10.1.3.1
> ```
> FHRP picks the router for traffic **leaving** the LAN. Traffic **coming back** follows the routing table. Real
> switches bring the port down when the cable goes, so this exact case is rarer outside a lab, but the lesson holds.

## Step 5 — Track the uplink
What if R1's **uplink** fails? Its LAN interface is fine, so it stays Active and keeps attracting LAN10's traffic,
with no way to forward it. Object tracking lowers R1's priority when its route to R3 disappears.

**R1**
```
configure terminal
track 1 ip route 10.255.255.3 255.255.255.255 reachability
interface Ethernet0/0
 standby 10 track 1 decrement 20
end
show track 1
```
**Output (captured)**
```
Track 1
  IP route 10.255.255.3 255.255.255.255 reachability
  Reachability is Up (OSPF)
    1 change, last change 00:00:16
  First-hop interface is Ethernet0/2
  Tracked by:
    HSRP Ethernet0/0 10
```
> **Why a route, not the interface:** `track 1 interface Ethernet0/2 line-protocol` only notices R1's own port
> going down. Tracking R3's loopback in the routing table also notices R3 or the link failing beyond R1's port,
> once OSPF removes the route. The decrement must take R1 **below** R2: 110 − 20 = 90 < 100.

Fail R1's uplink:

**R1**
```
configure terminal
interface Ethernet0/2
 shutdown
end
show standby Ethernet0/0 | include State is|Priority|Track|Active router
show logging | include TRACK|HSRP
```
**Output (captured)**
```
  State is Standby
  Active router is 192.168.10.3, priority 100 (expires in 2.912 sec)
  Priority 90 (configured 110)
    Track object 1 state Down decrement 20

%TRACK-6-STATE: 1 ip route 10.255.255.3/32 reachability Up -> Down
%HSRP-5-STATECHANGE: Ethernet0/0 Grp 10 state Active -> Speak
%HSRP-5-STATECHANGE: Ethernet0/0 Grp 10 state Speak -> Standby
```
**PC1**: `ping -c 2 -W 1 172.16.0.100` and `traceroute -n -q 1 -w 1 172.16.0.100` right away, then the ping again
after 30–40 seconds. **R3**: `show logging | include ADJCHG`.

**Output (captured)**
```
PC1 (right away):  2 packets transmitted, 0 packets received, 100% packet loss
PC1:  1  192.168.10.3  3.131 ms
      2  10.2.3.3  4.957 ms
R3:  %OSPF-5-ADJCHG: Process 1, Nbr 10.255.255.1 on Ethernet0/0 from FULL to DOWN, Neighbor Down: Dead timer expired
PC1 (after ~30 s): 2 packets transmitted, 2 packets received, 0% packet loss
```
Look for: HSRP moved within a second (traceroute hop 1 is R2), but the pings still failed for about 30 seconds.
The requests went out through R2; the **replies** came back toward R1. R3's side of the link stays up when R1
shuts its port, so R3 kept R1 as an OSPF neighbor, and kept its route to LAN10 through R1, until the 40-second
dead timer expired. Same lesson as Step 4: the first hop is HSRP's job, the return path is routing's. In
production, BFD or shorter OSPF timers close that gap.

Bring the uplink back (**R1**: `no shutdown` on e0/2), wait for OSPF (~40 s), then `show logging | include TRACK|HSRP`.

**Output (captured)**
```
%TRACK-6-STATE: 1 ip route 10.255.255.3/32 reachability Down -> Up
%HSRP-5-STATECHANGE: Ethernet0/0 Grp 10 state Standby -> Active
```

## Step 6 — HSRP authentication
Without authentication, any device on the LAN can send HSRP hellos with priority 255 and take over the gateway.
Add an MD5 key, on **R1 only** first:

**R1**
```
configure terminal
interface Ethernet0/0
 standby 10 authentication md5 key-string FHRPsecret
end
```
**R1** and **R2**: `show standby brief` and `show logging | include BADAUTH`.

**Output (captured)**
```
R1:  Et0/0       10   110 P Active  local           unknown         192.168.10.1
R1:  %HSRP-4-BADAUTH2: Bad authentication from 192.168.10.3
R2:  Et0/0       10   100 P Active  local           unknown         192.168.10.1
R2:  %HSRP-4-BADAUTH2: Bad authentication from 192.168.10.2
```
Look for: **two Active routers**, each with Standby `unknown`. Each one discards the other's hellos, so each
thinks it's alone. Both answer for the same virtual IP and MAC, which is why PC1 may keep working. The danger
is that nothing is redundant any more, and two routers now claim one address.

**R2**
```
configure terminal
interface Ethernet0/0
 standby 10 authentication md5 key-string FHRPsecret
end
show standby brief
```
**Output (captured)**
```
Et0/0       10   100 P Standby 192.168.10.2    local           192.168.10.1
```

## Step 7 — VRRPv3 on LAN20, with R2 forwarding
VRRP is the open-standard equivalent (RFC 5798). On IOS-XE, VRRPv3 is enabled globally and configured per
address family.

**R1**
```
configure terminal
fhrp version vrrp v3
interface Ethernet0/1
 vrrp 20 address-family ipv4
  address 192.168.20.1 primary
end
```
**R2**
```
configure terminal
fhrp version vrrp v3
track 1 ip route 10.255.255.3 255.255.255.255 reachability
interface Ethernet0/1
 vrrp 20 address-family ipv4
  priority 110
  track 1 decrement 20
  address 192.168.20.1 primary
end
```
**R2**: `show vrrp brief` and `show vrrp detail`. **R1**: `show vrrp brief`. **PC2**: `ping -c 2 -W 1
172.16.0.100`, `traceroute -n -q 1 -w 1 172.16.0.100` and `ip neigh show 192.168.20.1`.

**Output (captured, detail trimmed)**
```
R2:  Interface          Grp  A-F Pri  Time Own Pre State   Master addr/Group addr
     Et0/1               20 IPv4 110     0  N   Y  MASTER  192.168.20.3(local) 192.168.20.1
R1:  Et0/1               20 IPv4 100  3609  N   Y  BACKUP  192.168.20.3 192.168.20.1

R2# show vrrp detail
Ethernet0/1 - Group 20 - Address-Family IPv4
  State is MASTER
  Virtual IP address is 192.168.20.1
  Virtual MAC address is 0000.5E00.0114
  Advertisement interval is 1000 msec
  Preemption enabled
  Priority is 110
    Track object 1 state UP decrement 20
  Master Router is 192.168.20.3 (local), priority is 110
  Master Down interval is 3570 msec

PC2: 64 bytes from 172.16.0.100: seq=0 ttl=42 time=6.785 ms
PC2:  1  192.168.20.3  2.177 ms
      2  10.2.3.3  2.546 ms
PC2: 192.168.20.1 dev eth0 lladdr 00:00:5e:00:01:14 ref 1 used 0/0/0 probes 4 REACHABLE
```
HSRP vs VRRP, side by side:

| | HSRPv2 (LAN10) | VRRPv3 (LAN20) |
|---|---|---|
| Standard | Cisco | RFC 5798 |
| Roles | Active / Standby (others Listen) | Master / Backup |
| Virtual MAC | 0000.0c9f.f000 + group (0x00a) | 0000.5e00.01 + group (0x14) |
| Multicast | 224.0.0.102 | 224.0.0.18 |
| Timers | hello 3 s, hold 10 s by default | advert 1 s, master down ≈ 3 × advert |
| Preempt | **off** by default | **on** by default |
| Real IP as VIP | no | yes: the owner gets priority 255 |
| Authentication | text or MD5 | none in VRRPv3 |

> **Load sharing:** R1 forwards LAN10, R2 forwards LAN20, and each backs up the other. Both uplinks carry traffic,
> and either router can carry everything alone. An FHRP group has one forwarder, so sharing comes from using a
> different primary per group (or per VLAN). GLBP is Cisco's protocol that shares one group across routers.

## Final check
| From | Test | Result |
|---|---|---|
| R1 | `show standby brief` | Et0/0 group 10, Pri 110, P, **Active**, standby 192.168.10.3 |
| R1 | `show vrrp brief` | Et0/1 group 20, Pri 100, **BACKUP**, master 192.168.20.3 |
| R2 | `show vrrp brief` | Et0/1 group 20, Pri 110, **MASTER** |
| PC1 | `traceroute -n 172.16.0.100` | hop 1 192.168.10.2 (R1) |
| PC2 | `traceroute -n 172.16.0.100` | hop 1 192.168.20.3 (R2) |
| R1 | `shutdown` on e0/2 | R1 priority 90, R2 Active on LAN10; after `no shutdown`, R1 Active again |
| R2 | `shutdown` on e0/2 | R2 priority 90, R1 Master on LAN20; after `no shutdown`, R2 Master again |

## Check yourself
- R1 has priority 110 and R2 100, neither has preempt, and R2 booted first. Who is Active? What changes it?
- Why must the track decrement take R1 *below* R2, and not just lower its priority? What happens with
  `decrement 5`?
- R1's HSRP key is `FHRPSecret` and R2's is `FHRPsecret`. What does `show standby brief` show on each router?
- R2's VRRP group 20 is configured with address 192.168.20.254 and R1's with 192.168.20.1. What does PC2's
  `ip neigh` show for its gateway?
- R2 tracks `interface Ethernet0/0 line-protocol` for VRRP on LAN20. Which failure does that catch, and which one
  does it miss?
- In Step 5 HSRP failed over at once, yet PC1 lost ~30 s of pings. Which device was the problem, and why?
- Why does a PC never need to re-ARP after a failover?

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1, R2 | IOL-XE routers (the gateways you configure) | cisco | cisco | cisco |
| R3 | IOL-XE router (upstream / server; look, don't change) | cisco | cisco | cisco |
| PC1, PC2 | Alpine Linux | cisco | cisco | `sudo -i` |
| SW1, SW2 | CML unmanaged switches (no login) | — | — | — |

Open a console from the node in CML (right-click → Console). Routers start in privileged EXEC.
Each node also has a label in the CML canvas with its login and addresses.

## Topology

```
                          R3   Lo0 10.255.255.3
                               Lo1 172.16.0.100 ("data-center server")
                    e0/0 /        \ e0/1
             10.1.3.0/24/          \10.2.3.0/24
                  e0/2 /            \ e0/2
                     R1              R2
         Lo0 10.255.255.1          Lo0 10.255.255.2

   LAN10 192.168.10.0/24                LAN20 192.168.20.0/24
   R1 e0/0 .2 --+                       R1 e0/1 .2 --+
                [SW1]-- PC1 .10                      [SW2]-- PC2 .10
   R2 e0/0 .3 --+                       R2 e0/1 .3 --+
   VIP .1 (HSRPv2 group 10)             VIP .1 (VRRPv3 group 20)
```

## Addressing

| Node | Interface | IPv4 | Connects to |
|---|---|---|---|
| R1 | Loopback0 | 10.255.255.1/32 | — |
| R1 | Ethernet0/0 | 192.168.10.2/24 | SW1 (LAN10) |
| R1 | Ethernet0/1 | 192.168.20.2/24 | SW2 (LAN20) |
| R1 | Ethernet0/2 | 10.1.3.1/24 | R3 e0/0 |
| R2 | Loopback0 | 10.255.255.2/32 | — |
| R2 | Ethernet0/0 | 192.168.10.3/24 | SW1 (LAN10) |
| R2 | Ethernet0/1 | 192.168.20.3/24 | SW2 (LAN20) |
| R2 | Ethernet0/2 | 10.2.3.2/24 | R3 e0/1 |
| R3 | Loopback0 | 10.255.255.3/32 | — |
| R3 | Loopback1 | 172.16.0.100/32 | data-center server |
| R3 | Ethernet0/0 | 10.1.3.3/24 | R1 e0/2 |
| R3 | Ethernet0/1 | 10.2.3.3/24 | R2 e0/2 |
| PC1 | eth0 | 192.168.10.10/24, gw .1 | SW1 |
| PC2 | eth0 | 192.168.20.10/24, gw .1 | SW2 |

| LAN | Virtual gateway | Protocol | Primary |
|---|---|---|---|
| LAN10 192.168.10.0/24 | 192.168.10.1 | HSRPv2 group 10 | R1 |
| LAN20 192.168.20.0/24 | 192.168.20.1 | VRRPv3 group 20 | R2 |

**Routing:** OSPF area 0 on every interface of R1, R2 and R3; the LAN interfaces on R1 and R2 are passive.
