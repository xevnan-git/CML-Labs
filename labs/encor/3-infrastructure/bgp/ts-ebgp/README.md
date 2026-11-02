# eBGP Peering and Best Path — Troubleshooting Lab

> **Blueprint:** ENCOR 3.2.c — Configure and verify eBGP between directly connected neighbors (best path selection
> algorithm and neighbor relationships)
> **Mode:** Troubleshooting · **Nodes:** 6 licensed (4 routers, 2 PCs) · **Faults:** 5 · **Difficulty:** 3 of 3

<!--
This README is copied verbatim into the lab's CML Notes. It must NOT reveal the faults: no hints, no root cause.
Hints and the solution live only in solution/README.md in the repo.
Order: scenario first (ticket, goal, design), reference material (access, topology, addressing) at the bottom.
-->

## Ticket

> **#5291 — No internet after the edge router replacement**
> "The internet edge router (R1) failed last night and was swapped for a spare. The contractor rebuilt the config
> from 'the old notes plus best practice'. Since then nobody in the office (PC1's LAN) can reach anything outside.
> The contractor says both ISP links are up, and the ISPs say the circuits are fine. Please get us back online,
> and make sure we're on ISP1 again: we pay ISP2 per gigabyte, so it should only carry traffic when ISP1 is down."

ISP2's NOC confirmed by phone: *"Your session to us uses MD5. The password on our side is `isp2peer`."*

## Done when
- `PC1:~$ ping -c 3 198.51.100.10` and `PC1:~$ ping -c 3 203.0.113.1` succeed.
- `R1# show ip bgp summary` shows both ISP sessions **Established**, with a prefix count, not a state.
- `PC1:~$ traceroute -n 198.51.100.10` crosses **ISP1** (10.1.101.101), and `PC2:~$ traceroute -n 192.168.10.10`
  crosses ISP1 too.
- Shutting `R1 Ethernet0/0` moves both directions to ISP2. Bringing it back moves them back to ISP1.
- Each ISP receives **exactly one** prefix from R1: `192.168.10.0/24`.

## Rules
- The ISP routers belong to the providers. You may log in and run `show` commands, but **change only R1**.
- Fix with the smallest change that restores the intended design; don't redesign the edge.
- There's more than one fault, and fixing one may reveal the next.
- Hints and the full solution are in the lab repository (`solution/README.md` in this lab's folder), not in CML.

## Intended design
- **R1** is the only router in **AS 65001**. It peers eBGP over the directly connected link subnets:
  - **ISP1**, AS 64511, at 10.1.101.101: the **primary** ISP. No session password.
  - **ISP2**, AS 64512, at 10.1.102.102: the **backup** ISP. MD5 password `isp2peer`.
- R1 advertises the office LAN **192.168.10.0/24** and nothing else (no transit between the ISPs). This uses an
  AS-path filter that permits only locally originated routes.
- **Outbound** (office → internet): every route learned from ISP1 gets **local preference 200**, so ISP1 is always
  preferred while its session is up.
- **Inbound** (internet → office): R1 **prepends its AS three times** on updates to ISP2, so the rest of the
  internet prefers the path through ISP1.
- R1 uses Loopback0 (10.255.255.1) as its BGP router ID.

## Expected behavior (healthy network)
- `show ip bgp summary` on R1: two neighbors, each Established, each with 5 prefixes received.
- `show ip bgp` on R1: every internet prefix has two paths; the best (`>`) one has next hop 10.1.101.101 and
  LocPrf 200.
- `show ip bgp 192.168.10.0` on ISP3: best path `64511 65001`. The ISP2 path is `64512 65001 65001 65001 65001`.

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1 | IOL-XE router (yours, AS 65001) | cisco | cisco | cisco |
| ISP1, ISP2, ISP3 | IOL-XE routers (providers; look, don't change) | cisco | cisco | cisco |
| PC1, PC2 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → **Console**). Each node also has a label on the canvas with its
login and addresses.

## Topology

```
                         AS 64511 (primary)
                      e0/0 ISP1 e0/1
                     /               \
          10.1.101.0/24         10.101.103.0/24
                 e0/0                 e0/0
 PC1 ── e0/2  R1  AS 65001        ISP3  AS 64513 e0/2 ── PC2
192.168.10.0/24  e0/1                 e0/1         198.51.100.0/24
          10.1.102.0/24         10.102.103.0/24     Lo1 203.0.113.1/24
                     \               /
                      e0/0 ISP2 e0/1
                         AS 64512 (backup)
```

## Addressing (as designed)

| Node | Interface | IPv4 | Connects to |
|---|---|---|---|
| R1 | Loopback0 | 10.255.255.1/32 | — |
| R1 | Ethernet0/0 | 10.1.101.1/24 | ISP1 e0/0 |
| R1 | Ethernet0/1 | 10.1.102.1/24 | ISP2 e0/0 |
| R1 | Ethernet0/2 | 192.168.10.1/24 | PC1 |
| ISP1 | Loopback0 | 10.255.255.101/32 | — |
| ISP1 | Ethernet0/0 | 10.1.101.101/24 | R1 e0/0 |
| ISP1 | Ethernet0/1 | 10.101.103.101/24 | ISP3 e0/0 |
| ISP2 | Loopback0 | 10.255.255.102/32 | — |
| ISP2 | Ethernet0/0 | 10.1.102.102/24 | R1 e0/1 |
| ISP2 | Ethernet0/1 | 10.102.103.102/24 | ISP3 e0/1 |
| ISP3 | Loopback0 | 10.255.255.103/32 | — |
| ISP3 | Loopback1 | 203.0.113.1/24 | simulated internet prefix |
| ISP3 | Ethernet0/0 | 10.101.103.103/24 | ISP1 e0/1 |
| ISP3 | Ethernet0/1 | 10.102.103.103/24 | ISP2 e0/1 |
| ISP3 | Ethernet0/2 | 198.51.100.1/24 | PC2 |
| PC1 | eth0 | 192.168.10.10/24, gw .1 | R1 e0/2 |
| PC2 | eth0 | 198.51.100.10/24, gw .1 | ISP3 e0/2 |

| Router | BGP AS | Router ID | Originates |
|---|---|---|---|
| R1 | 65001 | 10.255.255.1 | 192.168.10.0/24 |
| ISP1 | 64511 | 10.255.255.101 | 10.255.255.101/32 |
| ISP2 | 64512 | 10.255.255.102 | 10.255.255.102/32 |
| ISP3 | 64513 | 10.255.255.103 | 10.255.255.103/32, 198.51.100.0/24, 203.0.113.0/24 |

Only the prefixes above are in BGP; the link subnets are not. When you test from R1 itself, use
`ping <address> source Ethernet0/2`.
