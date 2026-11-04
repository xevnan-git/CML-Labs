# Policy-Based Routing (PBR) — Troubleshooting Lab

> **Blueprint:** ENCOR 3.2.d — Configure and verify policy-based routing
> (also ENARSI 1.6 — Troubleshoot policy-based routing)
> **Mode:** Troubleshooting · **Nodes:** 5 licensed (3 routers, 2 hosts) · **Faults:** 5 · **Difficulty:** 3 of 3

<!--
This README is copied verbatim into the lab's CML Notes. It must NOT reveal the faults: no hints, no root cause.
Hints and the solution live only in solution/README.md in the repo.
Order: scenario first (ticket, goal, design), reference material (access, topology, addressing) at the bottom.
-->

## Ticket

> **#6318 — Guest Wi-Fi still on the main internet line**
> "We added a second, cheaper internet line (ISP2) last month so guest traffic would stop eating the main line's
> bandwidth. The contractor configured policy routing on the edge router R1 and left. The ISP1 bill hasn't
> moved: guest traffic still goes out ISP1. R1's own management traffic was supposed to move to ISP2 as well,
> and it hasn't either. Please make R1 do what the design below says."

## Done when
- `PC2:~$ traceroute -n -q 1 -w 1 203.0.113.100` ends at **10.1.102.102** (ISP2).
- `PC1:~$ traceroute -n -q 1 -w 1 203.0.113.100` ends at **10.1.101.101** (ISP1).
- `R1# ping 10.255.255.102 source Loopback0` works.
- `R1# show track 1 brief` shows **Up**.
- When ISP2's link fails (`shutdown` on ISP2 Ethernet0/0), PC2's traceroute ends at 10.1.101.101 within about
  15 seconds; after `no shutdown` it returns to ISP2. Leave ISP2's e0/0 up when you're done.

## Rules
- **Change only R1.** You may log in to ISP1 and ISP2 and run `show` commands. The only change allowed on a
  provider router is shutting and re-enabling ISP2's Ethernet0/0 to test the failover.
- Keep the design: same ACL, route-map, IP SLA and track names and numbers, no changes to R1's static routes.
- There's more than one fault, and fixing one may reveal the next.
- Hints and the full solution are in the lab repository (`solution/README.md` in this lab's folder), not in CML.

## Intended design
**Routing (unchanged):** R1 has static routes 0.0.0.0/0 and 203.0.113.0/24 (the SaaS provider), both to ISP1
(10.1.101.101). Staff traffic follows them.

**Guest PBR on R1:**
- ACL `GUEST-NET` matches traffic **from** the guest LAN 192.168.20.0/24 to anywhere.
- Route-map `PBR-GUEST`, sequence 10, matches GUEST-NET and sends it to ISP2, 10.1.102.102, **instead of** the
  routing table, for every destination, as long as ISP2 is reachable. The next hop is tracked:
  `verify-availability` with sequence 1 and track 1.
- IP SLA 1 pings ISP2's address 10.1.102.102 every 5 seconds, sourced from Ethernet0/3. Track 1 follows its
  reachability.
- If ISP2 is unreachable, guests fall back to normal routing (ISP1).
- The policy is applied to the guest traffic as it enters R1.

**Local PBR on R1:**
- ACL `R1-LOOPBACK` matches packets R1 itself sources from Loopback0 (10.255.255.1).
- Route-map `PBR-LOCAL` sends them to ISP2, 10.1.102.102 (untracked), applied as R1's local policy.

## Expected behavior
- Staff (PC1) use ISP1 for everything; guests (PC2) use ISP2 for everything, including 203.0.113.0/24.
- R1's management traffic sourced from Loopback0 uses ISP2. Only ISP2 can reach its own loopback 10.255.255.102,
  so `ping 10.255.255.102 source Loopback0` is a quick test.
- An ISP2 failure moves guests to ISP1 by itself, and they move back when ISP2 recovers.
- Telnet to 203.0.113.100 shows a banner naming the ISP that answered (press Ctrl+] then type `quit`).

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1 | IOL-XE router (edge, the only one you change) | cisco | cisco | cisco |
| ISP1 | IOL-XE router (primary provider; look, don't change) | cisco | cisco | cisco |
| ISP2 | IOL-XE router (guest/backup provider; see Rules) | cisco | cisco | cisco |
| PC1, PC2 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → **Console**). Each node also has a label on the canvas with its
login and addresses.

## Topology

```
  PC1 (staff)                                                   ISP1 (primary)
  192.168.10.10 ── e0/0 ┐                         ┌ e0/2 ── 10.1.101.0/24 ── e0/0 ISP1
                        R1  Lo0 10.255.255.1                                  Lo1 203.0.113.100
  PC2 (guest)           │   edge (PBR)            │                           ("internet server")
  192.168.20.10 ── e0/1 ┘                         └ e0/3 ── 10.1.102.0/24 ── e0/0 ISP2
                                                                              Lo1 203.0.113.100
                                                                ISP2 (guest / backup)
```
Both ISPs own 203.0.113.100. A traceroute to it ends at the address of the ISP that carried it: 10.1.101.101
(ISP1) or 10.1.102.102 (ISP2).

## Addressing (as designed)

| Node | Interface | IPv4 | Connects to |
|---|---|---|---|
| R1 | Loopback0 | 10.255.255.1/32 | — |
| R1 | Ethernet0/0 | 192.168.10.1/24 | PC1 (staff LAN) |
| R1 | Ethernet0/1 | 192.168.20.1/24 | PC2 (guest LAN) |
| R1 | Ethernet0/2 | 10.1.101.1/24 | ISP1 e0/0 |
| R1 | Ethernet0/3 | 10.1.102.1/24 | ISP2 e0/0 |
| ISP1 | Loopback0 | 10.255.255.101/32 | — |
| ISP1 | Loopback1 | 203.0.113.100/32 | internet server |
| ISP1 | Ethernet0/0 | 10.1.101.101/24 | R1 e0/2 |
| ISP2 | Loopback0 | 10.255.255.102/32 | — |
| ISP2 | Loopback1 | 203.0.113.100/32 | internet server |
| ISP2 | Ethernet0/0 | 10.1.102.102/24 | R1 e0/3 |
| PC1 | eth0 | 192.168.10.10/24, gw .1 | R1 e0/0 |
| PC2 | eth0 | 192.168.20.10/24, gw .1 | R1 e0/1 |

| Router | Routing (static only) |
|---|---|
| R1 | 0.0.0.0/0 → 10.1.101.101; 203.0.113.0/24 → 10.1.101.101 |
| ISP1 | 192.168.0.0/16 and 10.255.255.1/32 → 10.1.101.1 |
| ISP2 | 192.168.0.0/16 and 10.255.255.1/32 → 10.1.102.1 |
