# Naming, addressing & base config

These conventions apply to every lab so topologies feel familiar. A lab README may deviate only when the topic
needs it (e.g. overlapping addresses in a VRF lab), and must say so.

## Device names

| Prefix | Role | Default node_definition |
|---|---|---|
| `R1..Rn` | Enterprise router | `iol-xe` |
| `ISP1..n` | Provider / external router | `iol-xe` |
| `SW1..n` | Switch (access/distribution/core) | `ioll2-xe` |
| `FW1..n` | Firewall | `asav` |
| `PC1..n` | Test host | `alpine` (or `server`) |
| `SRV1..n` | Service host (TACACS+, RADIUS, syslog, SNMP mgr, NETCONF client) | `ubuntu` |

N in the name is the device number used in addresses. ISP routers number from 101 (`ISP1` → 101) so they never
collide with `R` numbers. Switches use 201+ for their SVI/Loopback host part (`SW1` → 201).

## IPv4

| Use | Prefix | Example |
|---|---|---|
| Router Loopback0 | `10.255.255.N/32` | R3 → `10.255.255.3` |
| Extra loopbacks (simulated LANs) | `172.(16+N).x.0/24`, x = 0, 1, 2… (summarizable block per router, N ≤ 15) | R4 → `172.20.0.1/24` … `172.20.3.1/24` = `172.20.0.0/22` |
| Router–router link Ra–Rb (a<b) | `10.a.b.0/24`, host = router number | R2–R5: R2 `10.2.5.2`, R5 `10.2.5.5` |
| Second parallel link Ra–Rb | `10.a.b+100.0/24` | R2–R5 #2: `10.2.105.0/24` |
| Multi-access transit (3+ routers) | `10.0.<seg>.0/24`, host = router number | segment 1: R1 `10.0.1.1` |
| User LAN / VLAN | `192.168.<vlan>.0/24` | VLAN 20 → `192.168.20.0/24` |
| LAN gateway / FHRP VIP | `.1` | `192.168.20.1` |
| Physical gateways (FHRP pair) | `.2`, `.3` | |
| Switch SVI (mgmt) | `.<200+n>` | SW1 → `192.168.99.201` |
| Hosts | `.10` and up | PC1 → `192.168.20.10` |
| Tunnels (GRE/DMVPN) | `10.99.<tun>.0/24`, host = router number | Tunnel0 on R1 → `10.99.0.1` |

## IPv6

| Use | Prefix |
|---|---|
| Loopback0 | `2001:db8:ffff::N/128` |
| Link Ra–Rb | `2001:db8:a:b::/64`, host `::a` / `::b` (+ link-local `fe80::N`) |
| LAN / VLAN | `2001:db8:<vlan>::/64`, gateway `::1` |

Set link-local addresses statically to `fe80::N` on routed interfaces so `show` output is readable.

## Routing identifiers

- Router ID (OSPF/EIGRP/BGP): `10.255.255.N` (set explicitly).
- OSPF process 1, EIGRP AS 100 (named mode name `LAB`), BGP enterprise ASNs `65001, 65002…`, ISP ASNs `64511, 64512…`.
- Area numbering: area 0 backbone, other areas numbered by the attached site/router where sensible.

## Base config (every IOS / IOS-XE device)

```
hostname R1
no ip domain lookup
ip domain name lab.local
!
enable secret cisco
username cisco privilege 15 secret cisco
!
line con 0
 exec-timeout 0 0
 logging synchronous
 privilege level 15
line vty 0 4
 login local
 transport input ssh telnet
!
interface Loopback0
 ip address 10.255.255.1 255.255.255.255
```

Linux hosts: set the address/gateway via the node's day-0 config (alpine `/etc/network/interfaces`,
ubuntu cloud-init netplan). Default login stays the image default and is documented in the lab README.

## Interface usage (IOL-XE)

IOL-XE interfaces are `Ethernet0/0..0/3` (slot 0), `Ethernet1/0..` etc. Convention: connect links in ascending
neighbor-number order starting at `e0/0`; hosts/LANs on the highest free port. The README addressing table lists
every interface, so learners never have to guess.

## Diagram

Each README has a diagram (Mermaid `graph` block) showing nodes, interfaces, subnets, and areas/AS boundaries.
