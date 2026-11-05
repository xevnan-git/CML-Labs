# NAT and PAT — Troubleshooting Lab

> **Blueprint:** ENCOR 3.3.b — Configure NAT/PAT
> **Mode:** Troubleshooting · **Nodes:** 5 licensed (2 routers, 3 hosts) · **Faults:** 5 · **Difficulty:** 2 of 3

<!--
This README is copied verbatim into the lab's CML Notes. It must NOT reveal the faults: no hints, no root cause.
Hints and the solution live only in solution/README.md in the repo.
Order: scenario first (ticket, goal, design), reference material (access, topology, addressing) at the bottom.
-->

## Ticket

> **#6418 — No internet for staff, public website down**
> "The edge router R1 died over the weekend. A contractor rebuilt it from the design document and an old backup,
> and since then staff have no internet at all and our customers can't reach the website. The ISP says their
> side is fine and they still route our /28 to us. Please get it working as designed."

## Done when
- **PC1** can `ping 192.0.2.10` and `nc -w 3 192.0.2.10 22 </dev/null` shows an SSH banner.
- **PC2** gets `<h1>SRV1 public web server</h1>` from `wget -T 3 -O - http://198.51.100.14/`.
- **PC2** gets an SSH banner from `nc -w 3 198.51.100.14 2222 </dev/null`.
- On R1, `show ip nat translations` shows both inside LANs using **198.51.100.1**, each flow with its own port.

## Rules
- **Change only R1.** ISP1 and the hosts are configured correctly; you may run `show` and test commands on them.
- Keep the security design: the OUTSIDE-IN ACL stays applied inbound on the internet interface, unchanged.
- There's more than one fault, and fixing one may reveal the next.
- Hints and the full solution are in the lab repository (`solution/README.md` in this lab's folder), not in CML.

## Intended design
**Routing (working, unchanged):** R1 has a default route to ISP1 (203.0.113.101). ISP1 routes the company's
public block **198.51.100.0/28** to R1 and has no routes to private addresses.

**NAT on R1:**
- Inside: Ethernet0/0 (staff LAN) and Ethernet0/1 (server LAN). Outside: Ethernet0/2 (ISP1).
- Both inside LANs, 192.168.10.0/24 and 192.168.20.0/24 (standard ACL **NAT-INSIDE**), are translated with **PAT**
  to the single public address **198.51.100.1** (pool **NAT-POOL**).
- SRV1 (192.168.20.10) is published on **198.51.100.14** by port forwarding:
  - public TCP 80 → SRV1 TCP 80 (web)
  - public TCP 2222 → SRV1 TCP 22 (SSH)
- **OUTSIDE-IN** (inbound on Ethernet0/2) permits the two published services, ICMP and return TCP traffic, and
  denies everything else.

**SRV1** runs a web server on port 80 and SSH on port 22, and a monitoring job that pings PC2 every 10 seconds.

## Expected behavior
- Staff and SRV1 reach the internet as 198.51.100.1.
- The internet reaches SRV1's web server at 198.51.100.14 and its SSH at 198.51.100.14 port 2222, and nothing else
  inside.

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1 | IOL-XE router (edge, the only one you change) | cisco | cisco | cisco |
| ISP1 | IOL-XE router (provider; look, don't change) | cisco | cisco | cisco |
| PC1, SRV1, PC2 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → Console). Routers start in privileged EXEC.
Each node also has a label in the CML canvas with its login and addresses.

Useful host commands: `ping -c 2 -W 1 <ip>`, `wget -T 3 -O - http://<ip>/`, `nc -w 3 <ip> <port> </dev/null`
(prints the SSH banner if the port answers).

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

## Addressing (as designed)

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
