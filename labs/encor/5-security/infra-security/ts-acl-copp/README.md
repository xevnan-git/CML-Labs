# ACLs and CoPP, Layered on the Edge — Troubleshooting Lab

> **Blueprint:** ENCOR 5.2.a + 5.2.b — Configure and verify infrastructure security features: ACLs, CoPP
> (also ENARSI 3.2.a and 3.3)
> **Mode:** Troubleshooting · **Nodes:** 5 licensed (3 routers, 2 hosts) · **Faults:** 4 · **Difficulty:** 3 of 3

<!--
This README is copied verbatim into the lab's CML Notes. It must NOT reveal the faults: no hints, no root cause.
Hints and the solution live only in solution/README.md in the repo.
Order: scenario first (ticket, goal, design), reference material (access, topology, addressing) at the bottom.
-->

## Ticket

> **#6304 — Edge hardening, part 2: now everything is broken**
> "Last night the security team finished hardening the edge router R1: an infrastructure ACL on the internet
> link, on top of the CoPP policy and a vty ACL. This morning BGP is down and the office has no internet. The NOC
> also says the admins can Telnet to R1 but SSH just hangs. The security team wants all three layers kept. Please
> make R1 match the design below."

## Done when
- `R1# show ip ospf neighbor` shows R2 **FULL**, and `R1# show ip bgp summary` shows ISP1 with a prefix count.
- `PC1:~$ ping -c 2 198.51.100.10` works.
- From PC1: `telnet 10.255.255.1` and `ssh cisco@10.255.255.1` both reach a login prompt.
- `R1# ping 198.51.100.10` succeeds and `R1# traceroute 198.51.100.10` reaches 198.51.100.10.
- From PC2: `ping -c 3 10.1.101.1` works; `telnet 10.1.101.1` and `ping -c 2 10.255.255.1` get no answer.
- `R2# telnet 10.1.2.1 /source-interface Ethernet0/1` is refused.

## Rules
- **Change only R1.** You may log in to R2 and ISP1 and run `show`, `ping` and `traceroute`. ISP1 belongs to the
  provider.
- Keep all three layers with the same names and structure. Fix with the smallest change that restores the
  design; don't remove an ACL or the service-policy, and don't replace the iACL with `permit ip any any`.
- There's more than one fault, and fixing one may reveal the next.
- Hints and the full solution are in the lab repository (`solution/README.md` in this lab's folder), not in CML.

## Intended design
**Routing (unchanged by the change window):** R1 runs OSPF area 0 with R2 and originates a default route into it.
R1 runs eBGP (AS 65001) with ISP1 (AS 64511, 10.1.101.101) and advertises 192.168.10.0/24 and 10.255.255.1/32.
ISP1 is the passive side, so R1 always opens the BGP TCP connection. BGP timers are 10/30.

**Layer 1: iACL `IACL-IN`, inbound on R1 Ethernet0/1** (with `no ip unreachables` on that interface).
Sections, in this order:

| # | Section | Intent |
|---|---|---|
| 1 | ISP peer | permit BGP (to or from TCP 179) and ICMP from 10.1.101.101 to 10.1.101.1 |
| 2 | Anti-spoofing | deny sources in 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 127.0.0.0/8 |
| 3 | Protect R1 | permit ICMP echo, echo-reply, unreachable and time-exceeded to 10.1.101.1; deny all other traffic to 10.1.101.1, 10.255.255.1 and 10.1.2.0/24 |
| 4 | Transit | permit everything else |

**Layer 2: CoPP `PM-COPP` on the control plane, inbound** (classes in this order):

| Class | Selects | Policer | Action |
|---|---|---|---|
| CM-ROUTING (ACL COPP-ROUTING) | all OSPF; BGP to or from TCP 179; EIGRP | 256 kbps | never drops |
| CM-MGMT (ACL COPP-MGMT) | SSH, Telnet, HTTP, HTTPS from the management LAN 192.168.10.0/24 | 256 kbps | drops the excess |
| CM-MONITOR (COPP-SNMP or COPP-ICMP) | SNMP from the management LAN; ICMP from anywhere | 16 kbps | drops the excess |
| CM-CATCHALL (ACL COPP-CATCHALL) | any other IP packet to R1 | 8 kbps | drops everything |
| class-default | everything else (non-IP, e.g. ARP) | 64 kbps | drops the excess |

**Layer 3: vty `access-class VTY-MGMT in`:** only the admin workstation 192.168.10.10 (PC1) may log in, by
Telnet or SSH; other sources are refused and logged.

## Expected behavior
- OSPF FULL between R1 and R2; BGP Established between R1 and ISP1, R1 receiving 198.51.100.0/24 and
  10.255.255.101/32.
- The office (management LAN) reaches the internet. R1 itself can ping and traceroute to internet hosts.
- Only PC1 can log in to R1. From the internet, R1's internet address answers pings at a modest rate and nothing
  else; R1's other addresses don't answer at all.
- Packets from the internet with private source addresses are dropped at R1.

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1 | IOL-XE router (edge, the only one you change) | cisco | cisco | cisco |
| R2 | IOL-XE router (inside) | cisco | cisco | cisco |
| ISP1 | IOL-XE router (provider; show/ping/traceroute only) | cisco | cisco | cisco |
| PC1, PC2 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → **Console**). Each node also has a label on the canvas with its
login and addresses.

## Topology

```
                 OSPF area 0                 eBGP 65001 <-> 64511
 PC1 ── e0/1 R2 e0/0 ── 10.1.2.0/24 ── e0/0 R1 e0/1 ── 10.1.101.0/24 ── e0/0 ISP1 e0/1 ── PC2
 192.168.10.10   inside               edge: CoPP,  iACL in             provider        198.51.100.10
 (admin, mgmt LAN)                    vty ACL      on e0/1                             (internet host)
```

## Addressing (as designed)

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
