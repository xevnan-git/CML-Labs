# NTP — Troubleshooting Lab

> **Blueprint:** ENCOR 3.3.a — Interpret network time protocol configurations such as NTP and PTP
> **Mode:** Troubleshooting · **Nodes:** 4 licensed (4 routers) · **Faults:** 5 · **Difficulty:** 3 of 3

<!--
This README is copied verbatim into the lab's CML Notes. It must NOT reveal the faults: no hints, no root cause.
Hints and the solution live only in solution/README.md in the repo.
Order: scenario first (ticket, goal, design), reference material (access, topology, addressing) at the bottom.
-->

## Ticket

> **#6402 — Router clocks wrong after the NTP hardening change**
> "Our audit asked for authenticated NTP, so last week we added keys and access control to the NTP setup on
> R1, R2 and R3. Since then the log timestamps don't line up between routers, `show clock` puts a `*` in front
> of the time on all three, and the SIEM rejects their syslog. NTP1 is fine; it's the routers. Keep the
> hardening, just make time work again."

## Done when
- `R1# show ntp status` says **Clock is synchronized, stratum 4, reference is 10.255.255.100**.
- `R2# show ntp status` and `R3# show ntp status` say **Clock is synchronized, stratum 5, reference is
  10.255.255.1**.
- On R2 and R3, `show ntp associations` lists the other one (10.255.255.3 / 10.255.255.2) as a peer with a
  non-zero **reach**.
- `show clock` on every router shows the time **without** a leading `*` or `.`.

NTP is slow on purpose: a router measures its clock drift for about **15 minutes** after its server becomes
usable before it says *synchronized*, and each level waits for the one above, so the whole hierarchy needs about
**45 minutes** after the last fix. You don't have to wait to know whether a fix worked: `show ntp associations`
(the **reach** column and the `*`) and `show ntp associations detail` (packet counters) change within a poll or
two (64 seconds).

## Rules
- **Change only R1, R2 and R3.** NTP1 is the time source and is configured correctly; you may run `show`
  commands on it.
- Keep the hardening: authentication on every router with key 1, `ntp source Loopback0`, and R1's two
  access-groups with the same ACL names. Don't remove any of them to make the problem go away.
- There's more than one fault, and fixing one may reveal the next.
- Hints and the full solution are in the lab repository (`solution/README.md` in this lab's folder), not in CML.

## Intended design
**Routing (working, unchanged):** OSPF area 0 on every link and every Loopback0. R3's Loopback1
(172.19.0.0/24) is reserved for a future management network and is deliberately not in OSPF yet.

**Time:** every router uses `clock timezone EST -5 0` and `clock summer-time EDT recurring`, and timestamps its
logs in local time.

**NTP hierarchy:**

| Router | Role | Gets time from | Expected stratum |
|---|---|---|---|
| NTP1 | `ntp master 3` (stands in for an internet time source) | its own clock | 3 |
| R1 | client of NTP1, server for R2 and R3 | NTP1, 10.255.255.100 | 4 |
| R2 | client of R1, peer of R3 | R1, 10.255.255.1 | 5 |
| R3 | client of R1, peer of R2 | R1, 10.255.255.1 | 5 |

- **Every router** sources NTP from its Loopback0 (`ntp source Loopback0`), and all servers and peers are
  addressed by Loopback0.
- **Authentication everywhere:** key 1, MD5, key string `NTPsecret`, `ntp authenticate`, key 1 trusted, and
  `key 1` on every `ntp server` / `ntp peer` line.
- **R1's access control:**
  - `ntp access-group peer NTP-PEERS`: R1 may synchronize to NTP1 (10.255.255.100) only.
  - `ntp access-group serve-only NTP-CLIENTS`: R2 and R3 (their NTP source addresses) may get time from R1, but
    R1 never synchronizes to them.
- **R2 ↔ R3 peering** (`ntp peer`), so either can keep the other in time if R1 is lost.

## Expected behavior
- About 45 minutes after boot (15 per level), every router is synchronized to the stratum listed above.
- Log timestamps on all four routers agree to the second, in EST/EDT.
- No router synchronizes to anything other than its designed server.

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| NTP1 | IOL-XE router (time source; look, don't change) | cisco | cisco | cisco |
| R1, R2, R3 | IOL-XE routers | cisco | cisco | cisco |

Open a console from the node in CML (right-click → **Console**). Each node also has a label on the canvas with its
login and addresses.

## Topology

```
                       NTP1   Lo0 10.255.255.100  (ntp master 3)
                         | e0/0
                    10.1.100.0/24
                         | e0/0
                        R1    Lo0 10.255.255.1
               e0/1   /    \   e0/2
         10.1.2.0/24 /      \ 10.1.3.0/24
               e0/0 /        \ e0/0
                  R2 -------- R3
  Lo0 10.255.255.2  e0/1  e0/1  Lo0 10.255.255.3
                   10.2.3.0/24  Lo1 172.19.0.1/24 (not in OSPF)
```

## Addressing (as designed)

| Node | Interface | IPv4 | Connects to |
|---|---|---|---|
| NTP1 | Loopback0 | 10.255.255.100/32 | — |
| NTP1 | Ethernet0/0 | 10.1.100.100/24 | R1 e0/0 |
| R1 | Loopback0 | 10.255.255.1/32 | — |
| R1 | Ethernet0/0 | 10.1.100.1/24 | NTP1 e0/0 |
| R1 | Ethernet0/1 | 10.1.2.1/24 | R2 e0/0 |
| R1 | Ethernet0/2 | 10.1.3.1/24 | R3 e0/0 |
| R2 | Loopback0 | 10.255.255.2/32 | — |
| R2 | Ethernet0/0 | 10.1.2.2/24 | R1 e0/1 |
| R2 | Ethernet0/1 | 10.2.3.2/24 | R3 e0/1 |
| R3 | Loopback0 | 10.255.255.3/32 | — |
| R3 | Loopback1 | 172.19.0.1/24 | not in OSPF (future management) |
| R3 | Ethernet0/0 | 10.1.3.3/24 | R1 e0/2 |
| R3 | Ethernet0/1 | 10.2.3.3/24 | R2 e0/1 |
