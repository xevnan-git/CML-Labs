# Control Plane Policing (CoPP) — Troubleshooting Lab

> **Blueprint:** ENCOR 5.2.b — Configure and verify infrastructure security features: CoPP
> (also ENARSI 3.3 — Troubleshoot CoPP: Telnet, SSH, HTTP(S), SNMP, EIGRP, OSPF, BGP)
> **Mode:** Troubleshooting · **Nodes:** 5 licensed (3 routers, 2 hosts) · **Faults:** 5 · **Difficulty:** 3 of 3

<!--
This README is copied verbatim into the lab's CML Notes. It must NOT reveal the faults: no hints, no root cause.
Hints and the solution live only in solution/README.md in the repo.
Order: scenario first (ticket, goal, design), reference material (access, topology, addressing) at the bottom.
-->

## Ticket

> **#6230 — Internet down after the edge hardening change**
> "After the security team applied their new Control Plane Policing policy to the edge router R1 last night, the
> office lost the internet. The network admins on the management LAN can't log in to R1 either; we only got in
> through the console. The security team swears the policy is 'by the book' and wants it kept. Please make it
> work as designed. Don't just remove it."

## Done when
- `R1# show ip ospf neighbor` shows R2 **FULL**, and `R1# show ip bgp summary` shows ISP1 with a prefix count.
- `PC1:~$ ping -c 2 198.51.100.10` works.
- From PC1: `telnet 10.255.255.1` and `ssh cisco@10.255.255.1` both reach a login prompt.
- From PC1: `ping -c 3 10.255.255.1` works.
- From PC2: `ping -c 3 10.1.101.1` works, and `telnet 10.1.101.1` gets no answer.
- `R1# show policy-map control-plane` shows CM-ROUTING, CM-MGMT and CM-MONITOR counting packets.

## Rules
- **Change only R1.** You may log in to R2 and ISP1 and run `show` commands. ISP1 belongs to the provider.
- Keep the policy: same class and ACL names, same structure. Fix with the smallest change that restores the
  intended design; don't remove the service-policy or loosen the catch-all.
- There's more than one fault, and fixing one may reveal the next.
- Hints and the full solution are in the lab repository (`solution/README.md` in this lab's folder), not in CML.

## Intended design
**Routing (unchanged by the change window):** R1 runs OSPF area 0 with R2 and originates a default route into it.
R1 runs eBGP (AS 65001) with ISP1 (AS 64511, 10.1.101.101) and advertises 192.168.10.0/24 and 10.255.255.1/32.
ISP1 is configured as the passive side, so R1 always opens the BGP TCP connection. BGP timers are 10/30 on both
sides.

**CoPP on R1:** policy `PM-COPP` applied to the control plane, inbound, with these classes in this order:

| Class | Selects | Policer | Action |
|---|---|---|---|
| CM-ROUTING (ACL COPP-ROUTING) | all OSPF; BGP to or from TCP port 179; EIGRP | 256 kbps | never drops (exceed → transmit) |
| CM-MGMT (ACL COPP-MGMT) | SSH, Telnet, HTTP, HTTPS **from the management LAN 192.168.10.0/24** to R1 | 256 kbps | drops the excess |
| CM-MONITOR (ACLs COPP-SNMP **or** COPP-ICMP) | SNMP from the management LAN; ICMP from anywhere | 16 kbps | drops the excess |
| CM-CATCHALL (ACL COPP-CATCHALL) | any other IP packet to R1 | 8 kbps | drops everything |
| class-default | everything else (non-IP, e.g. ARP) | 64 kbps | drops the excess |

## Expected behavior
- OSPF FULL between R1 and R2; BGP Established between R1 and ISP1, R1 receiving 198.51.100.0/24 and
  10.255.255.101/32.
- Admins on the management LAN can log in to any of R1's addresses with Telnet or SSH. Nobody else can: their
  sessions just time out.
- Anyone can ping R1 at a modest rate; floods are cut down.
- Transit traffic (PC1 ↔ PC2) isn't affected by CoPP at all.

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1 | IOL-XE router (edge, the only one you change) | cisco | cisco | cisco |
| R2 | IOL-XE router (inside) | cisco | cisco | cisco |
| ISP1 | IOL-XE router (provider; look, don't change) | cisco | cisco | cisco |
| PC1, PC2 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → **Console**). Each node also has a label on the canvas with its
login and addresses.

## Topology

```
                 OSPF area 0                 eBGP 65001 <-> 64511
 PC1 ── e0/1 R2 e0/0 ── 10.1.2.0/24 ── e0/0 R1 e0/1 ── 10.1.101.0/24 ── e0/0 ISP1 e0/1 ── PC2
 192.168.10.10   inside                 edge (CoPP)                     provider        198.51.100.10
 (admin, mgmt LAN)                                                                      (internet host)
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
