# NAT and PAT — Learning Lab

> **Blueprint:** ENCOR 3.3.b — Configure NAT/PAT
> **Mode:** Learning (guided build) · **Nodes:** 5 licensed (2 routers, 3 hosts) · **Time:** ~45 min

<!--
This README is copied verbatim into the lab's CML Notes (tools/sync_notes.py), so it must read well inside CML:
plain Markdown, ASCII diagrams (no Mermaid), no links to solution files.
Order: objectives and steps first; lab access, topology and addressing in the Reference section at the bottom.
-->

## What you'll learn
- Mark interfaces `ip nat inside` / `ip nat outside` and see why NAT does nothing without them.
- Publish a server with **static NAT** (1:1) and then with **port forwarding** (static PAT).
- Read `show ip nat translations`: inside local, inside global, outside local, outside global.
- Build **dynamic NAT** from a pool, run out of addresses, and see the misses in `show ip nat statistics`.
- Add `overload` (**PAT**) so many hosts share one public address, told apart by port.
- See that an inbound ACL on the outside interface is checked **before** NAT, so it must match the public address.
- Watch translations with `debug ip nat`.

## Starting point
Logins, the topology diagram and the addressing table are in **Reference** at the end of this guide.

- **R1** is the company's edge router. It already has its addresses and a default route to **ISP1**. **R1 is the
  only router you change.**
- Inside: **PC1** on the staff LAN (192.168.10.0/24) and **SRV1**, the public web server, on the server LAN
  (192.168.20.0/24). SRV1 runs a web server (port 80) and SSH (port 22). It also runs a small monitoring job that
  pings the internet host every 10 seconds, so you'll see its translations come and go in the table.
- Outside: **ISP1** and **PC2**, a host "on the internet" (192.0.2.10).
- The ISP gave the company the public block **198.51.100.0/28** (198.51.100.1–.14 usable). ISP1 routes that block
  to R1, and nothing else: **ISP1 has no route to 192.168.x.x**, as on the real internet, where private addresses
  aren't routed.

**The goal:** PC1 and SRV1 reach the internet through one public address, 198.51.100.1. The internet reaches
SRV1's web server at **198.51.100.14** port 80, and its SSH at 198.51.100.14 port **2222**. Nothing else gets in.

Wait about a minute after starting the lab, until the routers finish booting, before you test.

## Step 1 — Baseline: private addresses go nowhere
**PC1**
```
ping -c 2 -W 1 203.0.113.1
ping -c 2 -W 1 192.0.2.10
```
**ISP1**
```
show ip route | begin Gateway
show ip route 192.168.10.10
```
**Output (captured)**
```
PC1: 64 bytes from 203.0.113.1: seq=0 ttl=42 time=1.708 ms        <- R1's own outside address: fine
PC1: 2 packets transmitted, 0 packets received, 100% packet loss  <- the internet host

ISP1:
Gateway of last resort is not set
C        10.255.255.101 is directly connected, Loopback0
C        192.0.2.0/24 is directly connected, Ethernet0/1
S        198.51.100.0 [1/0] via 203.0.113.1
C        203.0.113.0/24 is directly connected, Ethernet0/0

% Network not in table
```
Look for: PC1's ping does reach PC2, which answers 192.168.10.10. But ISP1 has no route to 192.168.10.10, so the
reply is dropped. ISP1 only knows the company by **198.51.100.0/28**. NAT's job is to swap PC1's private
source address for an address in that block on the way out, and swap it back on the way in.

## Step 2 — Inside, outside, and a 1:1 static NAT for SRV1
**R1**
```
configure terminal
interface Ethernet0/0
 ip nat inside
interface Ethernet0/1
 ip nat inside
interface Ethernet0/2
 ip nat outside
exit
ip nat inside source static 192.168.20.10 198.51.100.14
end
```
> **Why inside/outside:** NAT translates only packets that cross from an `inside` interface to an `outside` one
> (or back). `ip nat inside source` means "rewrite the **source** of packets coming from inside", and, for the
> replies, the destination of packets coming from outside. Without both marks, nothing is translated, whatever
> rules you write.

**PC2**
```
wget -T 3 -O - http://198.51.100.14/
ping -c 2 -W 1 198.51.100.14
```
**R1**
```
show ip nat translations
```
**Output (captured)**
```
PC2: <h1>SRV1 public web server</h1>
PC2: 64 bytes from 198.51.100.14: seq=0 ttl=42 time=5.018 ms

Pro Inside global      Inside local       Outside local      Outside global
tcp 198.51.100.14:80   192.168.20.10:80   192.0.2.10:60180   192.0.2.10:60180
icmp 198.51.100.14:2156 192.168.20.10:2156 192.0.2.10:2156   192.0.2.10:2156
icmp 198.51.100.14:2158 192.168.20.10:2158 192.0.2.10:2158   192.0.2.10:2158
--- 198.51.100.14      192.168.20.10      ---                ---
```
How to read the four columns:

| Column | Meaning | Here |
|---|---|---|
| **Inside local** | the inside host's real address | 192.168.20.10 (SRV1) |
| **Inside global** | what the internet sees for that host | 198.51.100.14 |
| **Outside local** | the outside host as the inside sees it | 192.0.2.10 |
| **Outside global** | the outside host's real address | 192.0.2.10 |

"Local" is how things look from inside, "global" from outside. Outside local and global are the same because you
translate only inside addresses (`ip nat inside source`).

Look for:
- The `---` line is the static entry itself. It's permanent: it's there even with no traffic.
- The `tcp` line is PC2's web session; the `icmp` lines are SRV1's monitoring pings, which also leave as
  198.51.100.14. A 1:1 static works in **both directions**: every port, every protocol.

## Step 3 — Port forwarding: publish only what you mean to
A 1:1 static exposes *everything* on SRV1 and uses a whole public address for one server. Port forwarding (static
PAT) maps a single public address **and port** to a single inside address and port.

Remove the 1:1 static. IOS won't remove a static entry that still has active translations under it, so clear
those first:

**R1**
```
clear ip nat translation *
configure terminal
no ip nat inside source static 192.168.20.10 198.51.100.14
ip nat inside source static tcp 192.168.20.10 80 198.51.100.14 80 extendable
ip nat inside source static tcp 192.168.20.10 22 198.51.100.14 2222 extendable
end
```
> If SRV1's monitoring ping re-creates a translation between the two commands, IOS asks
> `Static entry in use, do you want to delete child entries? [no]:`. Answer `yes`. (Or do it in one go from
> configuration mode: `do clear ip nat translation *`, then the `no` line right after it.)
>
> **`extendable`** lets the same inside address appear in more than one static line (here, two ports on SRV1).
> IOS adds it automatically if you leave it out.

**PC2**
```
wget -T 3 -O - http://198.51.100.14/
nc -w 3 198.51.100.14 2222 </dev/null
nc -w 3 198.51.100.14 22 </dev/null; echo rc=$?
ping -c 2 -W 1 198.51.100.14
```
**Output (captured)**
```
<h1>SRV1 public web server</h1>
SSH-2.0-OpenSSH_10.2
rc=1
2 packets transmitted, 0 packets received, 100% packet loss
```
Look for: port 80 reaches the web server; public port **2222** reaches SRV1's SSH on port **22** (the banner is
SSH's greeting); public port 22 and ping get nothing. Only what you published gets in.

Meanwhile **PC1** still can't get out (`ping -c 2 -W 1 192.0.2.10` fails): nothing translates the staff LAN yet.

## Step 4 — Dynamic NAT from a pool, and running out
Dynamic NAT hands out public addresses from a pool to inside hosts that match an ACL, first come first served.
The company's spare public address is 198.51.100.1, so the pool has one address.

**R1**
```
configure terminal
ip access-list standard NAT-INSIDE
 10 permit 192.168.10.0 0.0.0.255
 20 permit 192.168.20.0 0.0.0.255
exit
ip nat pool NAT-POOL 198.51.100.1 198.51.100.1 prefix-length 28
ip nat inside source list NAT-INSIDE pool NAT-POOL
end
```
> **Why each piece:** the ACL selects **which inside sources** get translated (`permit` = translate; like in PBR,
> it doesn't filter traffic). The pool is the range of inside global addresses. `prefix-length` (or `netmask`)
> must describe the subnet the addresses belong to; it's a sanity check, not routing.

**PC1**
```
ping -c 3 -W 1 192.0.2.10
```
**R1**
```
show ip nat translations
show ip nat statistics
```
**Output (captured, trimmed)**
```
PC1: 3 packets transmitted, 0 packets received, 100% packet loss

Pro Inside global      Inside local       Outside local      Outside global
tcp 198.51.100.14:2222 192.168.20.10:22   ---                ---
tcp 198.51.100.14:80   192.168.20.10:80   ---                ---
icmp 198.51.100.1:2217 192.168.20.10:2217 192.0.2.10:2217    192.0.2.10:2217
--- 198.51.100.1       192.168.20.10      ---                ---

Total active translations: 6 (2 static, 4 dynamic; 5 extended)
Outside interfaces:
  Ethernet0/2
Inside interfaces:
  Ethernet0/0, Ethernet0/1
 Dynamic overload mapping configured: 0
[Id: 1] access-list NAT-INSIDE pool NAT-POOL refcount 4
 pool NAT-POOL: id 1, netmask 255.255.255.240
        start 198.51.100.1 end 198.51.100.1
        type generic, total addresses 1, allocated 1 (100%), misses 3
```
Look for: SRV1's monitoring ping grabbed the only address (`--- 198.51.100.1  192.168.20.10`), so the pool is
**100% allocated**. PC1's three pings are the **3 misses**: PC1 matched the ACL, but there was no address left, so
its packets were dropped. Without `overload`, each inside host needs its own public address for as long as its
translation lives (24 hours of idle time by default for the address entry).

## Step 5 — Overload: PAT
**R1**
```
clear ip nat translation *
configure terminal
ip nat inside source list NAT-INSIDE pool NAT-POOL overload
end
```
> IOS refuses to change a dynamic mapping that has translations (`%Dynamic mapping in use, cannot change`).
> SRV1's ping re-creates one within 10 seconds, so if you get that message, do both from configuration mode in
> one go: `do clear ip nat translation *`, then the `ip nat inside source …` line right after it.

**PC1**
```
ping -c 2 -W 1 192.0.2.10
nc -w 3 192.0.2.10 22 </dev/null
```
**R1**
```
show ip nat translations
show ip nat statistics | include Total|allocated|overload
```
**Output (captured)**
```
PC1: 64 bytes from 192.0.2.10: seq=0 ttl=42 time=3.965 ms
PC1: SSH-2.0-OpenSSH_10.2

Pro Inside global      Inside local       Outside local      Outside global
icmp 198.51.100.1:1026 192.168.10.10:2160 192.0.2.10:2160    192.0.2.10:1026
tcp 198.51.100.1:1025  192.168.10.10:42031 192.0.2.10:22     192.0.2.10:22
tcp 198.51.100.14:2222 192.168.20.10:22   ---                ---
tcp 198.51.100.14:80   192.168.20.10:80   ---                ---
icmp 198.51.100.1:1024 192.168.20.10:2229 192.0.2.10:2229    192.0.2.10:1024
icmp 198.51.100.1:1025 192.168.20.10:2231 192.0.2.10:2231    192.0.2.10:1025

Total active translations: 9 (2 static, 7 dynamic; 9 extended)
 Dynamic overload mapping configured: 1
        type generic, total addresses 1, allocated 1 (100%), misses 3
```
Look for: PC1 and SRV1 now **share** 198.51.100.1. Every entry is a full (address, port) pair, and R1 picks a
unique inside global port (1024, 1025, 1026 …) for each flow, so replies to 198.51.100.1 can be told apart. For
ICMP the "port" is the echo identifier. The misses counter stays at 3: nothing new was refused.

> **PAT on the interface address:** a site with only one public address (often the router's own outside address,
> handed out by DHCP) uses `ip nat inside source list NAT-INSIDE interface Ethernet0/2 overload` instead of a
> pool. Same PAT, no pool to maintain. Here the pool keeps the company's public block separate from the ISP link.

## Step 6 — NAT and the outside ACL
The security team wants an inbound ACL on R1's internet interface: allow the two published services, ping and
return traffic, and deny the rest. A first attempt, written against SRV1's **real** address:

**R1**
```
configure terminal
ip access-list extended OUTSIDE-IN
 10 permit tcp any host 192.168.20.10 eq www
 30 permit icmp any any
 40 permit tcp any any established
 50 deny ip any any
interface Ethernet0/2
 ip access-group OUTSIDE-IN in
end
```
**PC2**: `wget -T 3 -O - http://198.51.100.14/` · **R1**: `show ip access-lists OUTSIDE-IN`

**Output (captured)**
```
wget: can't connect to remote host (198.51.100.14): Host is unreachable

Extended IP access list OUTSIDE-IN
    10 permit tcp any host 192.168.20.10 eq www
    30 permit icmp any any (4 matches)
    40 permit tcp any any established
    50 deny ip any any (1 match)
```
Look for: line 10 never matches; the deny does. "Host is unreachable" is the ICMP unreachable R1 sends back
for the denied packet.

> **Why:** on an outside interface, an inbound ACL is checked **before** NAT translates the destination. When the
> packet hits the ACL it is still addressed to **198.51.100.14**, not 192.168.20.10. (Going out it's the
> reverse: NAT translates the source first, so an outbound ACL on e0/2 sees the public address too.)
> Line 40 lets in replies to connections PC1 opened, because TCP replies carry the ACK flag.

Fix the ACL to use the inside global address, and add the SSH forward:

**R1**
```
configure terminal
ip access-list extended OUTSIDE-IN
 no 10
 10 permit tcp any host 198.51.100.14 eq www
 20 permit tcp any host 198.51.100.14 eq 2222
end
```
**PC2**
```
wget -T 3 -O - http://198.51.100.14/
nc -w 3 198.51.100.14 2222 </dev/null
ping -c 2 -W 1 198.51.100.1
```
**Output (captured)**
```
<h1>SRV1 public web server</h1>
SSH-2.0-OpenSSH_10.2
2 packets transmitted, 0 packets received, 100% packet loss
```
Look for: both services work again. The ping to 198.51.100.1 fails even though the ACL permits ICMP: a PAT
address has no translation for traffic that *starts* outside. That's PAT's side effect as a (weak) firewall.

## Step 7 — Watch NAT work with `debug ip nat`
**R1**
```
debug ip nat
```
**PC1**
```
ping -c 1 -W 1 192.0.2.10
```
**R1**
```
undebug all
show logging | include NAT
```
**Output (captured, trimmed)**
```
NAT: Entry assigned id 57
NAT*: ICMP id=2162->1029
NAT*: s=192.168.10.10->198.51.100.1, d=192.0.2.10 [47217]
NAT*: ICMP id=1029->2162
NAT*: s=192.0.2.10, d=198.51.100.1->192.168.10.10 [2512]
NAT: expiring 198.51.100.1 (192.168.20.10) icmp 1030 (2259)
NAT: Freeing nat entry, id 47
```
Look for: on the way out the **source** changes (`s=192.168.10.10->198.51.100.1`) and the ICMP id is remapped
(2162 → 1029). On the way back the **destination** changes back. `NAT*` means the packet was translated in the
fast (CEF) path. You'll also see SRV1's ping entries being created and **expiring** (ICMP entries time out after
60 seconds).

> In the console the debug prints live. Over SSH or Telnet, run `terminal monitor` first. On a busy router, limit
> it with an ACL: `debug ip nat <acl>`.

## Final check
| From | Test | Result |
|---|---|---|
| PC1 | `ping -c 2 192.0.2.10` | replies |
| PC2 | `wget -O - http://198.51.100.14/` | `<h1>SRV1 public web server</h1>` |
| PC2 | `nc -w 3 198.51.100.14 2222 </dev/null` | `SSH-2.0-OpenSSH_…` |
| PC2 | `nc -w 3 198.51.100.14 22 </dev/null` | nothing |
| R1 | `show ip nat statistics` | outside e0/2, inside e0/0 + e0/1, `Dynamic overload mapping configured: 1` |
| R1 | `show ip nat translations` | two static `tcp 198.51.100.14` entries, dynamic entries on 198.51.100.1 |
| R1 | `show ip access-lists OUTSIDE-IN` | lines 10 and 20 count matches |

## Check yourself
- You mark e0/2 `ip nat inside` and e0/0 `ip nat outside` by mistake. What happens to PC1's traffic, and what does
  `show ip nat statistics` show?
- NAT-INSIDE line 10 reads `permit 192.168.10.0 0.0.0.7`. Which staff hosts get translated? Is PC1 one of them?
- The pool is `198.51.100.17 198.51.100.17 prefix-length 28` (a typo). R1 translates fine. Why does nothing come
  back?
- Without `overload`, how many inside hosts can use a one-address pool at the same time?
- Why does OUTSIDE-IN permit `host 198.51.100.14` and not `host 192.168.20.10`?
- What does the `---` in the outside columns of a static entry mean?
- A static entry says inside port 8080 instead of 80. What does PC2's `wget` report, and why that message?

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1 | IOL-XE router (your edge, the only one you configure) | cisco | cisco | cisco |
| ISP1 | IOL-XE router (provider; look, don't change) | cisco | cisco | cisco |
| PC1, SRV1, PC2 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → Console). Routers start in privileged EXEC.
Each node also has a label in the CML canvas with its login and addresses.

## Topology

```
          INSIDE (private)                        |               OUTSIDE (internet)
                                                  |
  PC1 (staff)                                     |
  192.168.10.10 ── e0/0 ┐                         |
                        R1  Lo0 10.255.255.1      e0/2 ── 203.0.113.0/24 ── e0/0 ISP1 e0/1 ── 192.0.2.0/24 ── PC2
  SRV1 (web, ssh)       │   edge (NAT)                                        Lo0 10.255.255.101         192.0.2.10
  192.168.20.10 ── e0/1 ┘   public block 198.51.100.0/28                                                 ("internet host")
```

## Addressing

| Node | Interface | IPv4 | Connects to |
|---|---|---|---|
| R1 | Loopback0 | 10.255.255.1/32 | — |
| R1 | Ethernet0/0 | 192.168.10.1/24 | PC1 (staff LAN) |
| R1 | Ethernet0/1 | 192.168.20.1/24 | SRV1 (server LAN) |
| R1 | Ethernet0/2 | 203.0.113.1/24 | ISP1 e0/0 |
| ISP1 | Loopback0 | 10.255.255.101/32 | — |
| ISP1 | Ethernet0/0 | 203.0.113.101/24 | R1 e0/2 |
| ISP1 | Ethernet0/1 | 192.0.2.1/24 | PC2 |
| PC1 | eth0 | 192.168.10.10/24, gw .1 | R1 e0/0 |
| SRV1 | eth0 | 192.168.20.10/24, gw .1 | R1 e0/1 |
| PC2 | eth0 | 192.0.2.10/24, gw .1 | ISP1 e0/1 |

| Public address (198.51.100.0/28) | Use |
|---|---|
| 198.51.100.1 | PAT address for both inside LANs |
| 198.51.100.14 | SRV1: port 80 → 80 (web), port 2222 → 22 (SSH) |

| Router | Routing (static only) |
|---|---|
| R1 | 0.0.0.0/0 → 203.0.113.101 (ISP1) |
| ISP1 | 198.51.100.0/28 → 203.0.113.1 (R1). No routes to 192.168.x.x. |
