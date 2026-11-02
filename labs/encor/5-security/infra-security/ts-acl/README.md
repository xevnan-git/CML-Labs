# ACLs — Troubleshooting Lab

> **Blueprint:** ENCOR 5.2.a — Configure and verify infrastructure security features: ACLs
> (also ENARSI 3.2.a — Troubleshoot IPv4 ACLs: standard, extended, time-based)
> **Mode:** Troubleshooting · **Nodes:** 5 licensed (2 routers, 3 hosts) · **Faults:** 5 · **Difficulty:** 2 of 3

<!--
This README is copied verbatim into the lab's CML Notes. It must NOT reveal the faults: no hints, no root cause.
Hints and the solution live only in solution/README.md in the repo.
Order: scenario first (ticket, goal, design), reference material (access, topology, addressing) at the bottom.
-->

## Ticket

> **#6114 — Branch cut off after the security change**
> "Last night's change window rolled out the new branch access policy on R1 and R2. This morning the branch can't
> reach anything at HQ: no intranet, no file shares, nothing. The contractors in VLAN 11 say they have no network
> at all. Our admins also can't get into R2 remotely any more. The change was supposed to restrict things, not
> break them. Please fix it so the policy below works exactly as written."

## Done when
- `R1# show ip ospf neighbor` shows R2 **FULL**.
- **Staff (PC1)**: `wget -q -O - http://192.168.50.10/` and `nc -zv -w 3 192.168.50.10 22` both work, and
  `telnet 10.255.255.1` and `telnet 10.255.255.2` both give a login prompt.
- **Contractors (PC2)**: `wget -q -O - http://192.168.50.10/` and `ping -c 2 192.168.50.10` work,
  `ping -c 2 172.18.0.1` works, and `nc -zv -w 3 192.168.50.10 22` fails.
- **Contractors (PC2)**: `telnet 10.255.255.1` and `telnet 10.255.255.2` are refused.
- **Servers (SRV1)**: `ping -c 2 192.168.10.10` works and `nc -zv -w 3 192.168.10.10 22` fails.

## Rules
- Fix with the smallest change that restores the intended design. Keep the ACL names; don't redesign the policy or
  remove an ACL from service to make a test pass.
- There's more than one fault, and fixing one may reveal the next.
- Hints and the full solution are in the lab repository (`solution/README.md` in this lab's folder), not in CML.

## Intended design
Addressing and OSPF (area 0, process 1) are unchanged from before the change window. The new policy:

| Network | Who | Policy |
|---|---|---|
| VLAN 10, 192.168.10.0/24 (PC1) | Staff | Reach everything. The only network allowed to log in (Telnet/SSH) to R1 and R2. |
| VLAN 11, 192.168.11.0/24 (PC2) | Contractors | On the server LAN (192.168.50.0/24): web (TCP 80) to SRV1 and ping to SRV1 only; other attempts to the server LAN are denied and logged. Everything outside the server LAN is allowed. |
| VLAN 50, 192.168.50.0/24 (SRV1) | HQ servers | May answer the branch and ping it, but must not open TCP connections into the branch. |

How it's built:
- **R1 `CONTRACTORS-IN`**: extended named ACL, inbound on Ethernet0/2 (VLAN 11), filtering the contractors as close
  to the source as possible.
- **R1 `BRANCH-IN`**: extended named ACL, inbound on Ethernet0/0 (from HQ). It allows OSPF, TCP replies to both
  branch VLANs, and ICMP; everything else is denied and logged.
- **R1 and R2 `VTY-ADMIN`**: standard named ACL, applied with `access-class … in` on `line vty 0 4`, permitting
  VLAN 10.

## Expected behavior
- R1 and R2 are OSPF neighbors on 10.1.2.0/24, and R1 learns 192.168.50.0/24, 172.18.0.0/24 and 10.255.255.2/32.
- Denied contractor traffic to the server LAN appears in R1's log as `%SEC-6-IPACCESSLOG…` with
  `list CONTRACTORS-IN`.
- A blocked TCP attempt fails quickly with *Host is unreachable* (the router sends ICMP "administratively
  prohibited"), and a blocked login fails with *Connection refused*.

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1, R2 | IOL-XE router | cisco | cisco | cisco |
| PC1, PC2, SRV1 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → **Console**). Each node also has a label on the canvas with its
login and addresses. SRV1 runs a web server on port 80 and SSH on port 22; PC1 also runs SSH.

## Topology

```
 PC1 (Staff)
 192.168.10.10 ── e0/1 ┐
                       R1 e0/0 ── 10.1.2.0/24 ── e0/0 R2 e0/1 ── SRV1 (web :80, ssh :22)
 192.168.11.10 ── e0/2 ┘  branch                  HQ  Lo1         192.168.50.10
 PC2 (Contractor)                                     172.18.0.1/24 (HQ users)

                   OSPF area 0 on every router interface
```

## Addressing (as designed)

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
