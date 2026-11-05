# FHRP (HSRP and VRRP) — Troubleshooting Lab

> **Blueprint:** ENCOR 3.3.c — Configure first hop redundancy protocols, such as HSRP, VRRP
> (also ENCOR 1.1.b — high availability techniques such as redundancy, FHRP)
> **Mode:** Troubleshooting · **Nodes:** 5 licensed (3 routers, 2 hosts) + 2 unmanaged switches · **Faults:** 5 · **Difficulty:** 2 of 3

<!--
This README is copied verbatim into the lab's CML Notes. It must NOT reveal the faults: no hints, no root cause.
Hints and the solution live only in solution/README.md in the repo.
Order: scenario first (ticket, goal, design), reference material (access, topology, addressing) at the bottom.
-->

## Ticket

> **#6431 — Gateway redundancy failed its test**
> "We finished the redundant-gateway project for LAN10 and LAN20 on Friday. Since then LAN20 (PC2) can't reach
> the data-center server at all, and both routers keep logging HSRP warnings for LAN10. LAN10 itself works. Last
> night's failover test also failed: with R1's uplink shut down, PC1 lost the server too. Please fix it, then run
> the failover tests below and make sure both pass."

## Done when
1. **PC1** and **PC2** reach the server: `ping -c 2 -W 1 172.16.0.100`.
2. `show standby brief` on R1 shows group 10 **Active** with R2 as **Standby**; `show vrrp brief` on R2 shows
   group 20 **MASTER** with R1 as backup. No HSRP or VRRP warnings keep appearing in `show logging`.
3. `traceroute -n -q 1 -w 1 172.16.0.100`: hop 1 is **192.168.10.2** (R1) from PC1 and **192.168.20.3** (R2)
   from PC2.
4. **Failover test, LAN10:** on R1, `shutdown` Ethernet0/2. R2 becomes Active for group 10, and PC1 reaches the
   server again within a minute (OSPF needs up to 40 seconds to notice the dead link). After `no shutdown` and
   about a minute, R1 is Active again.
5. **Failover test, LAN20:** the same with R2's Ethernet0/2: R1 becomes Master for group 20, PC2 keeps reaching
   the server, and R2 takes back over after `no shutdown`.

## Rules
- **Change only R1 and R2.** R3 and the PCs are configured correctly; you may run `show` and test commands on them.
- Shutting down and re-enabling the uplinks (Ethernet0/2 on R1 or R2) for the failover tests is expected.
- Keep the design below: same groups, protocols, addresses, priorities, key and tracked route.
- There's more than one fault, and fixing one may reveal the next.
- Hints and the full solution are in the lab repository (`solution/README.md` in this lab's folder), not in CML.

## Intended design
**Routing (working, unchanged):** OSPF area 0 on every interface of R1, R2 and R3; the LAN interfaces on R1 and
R2 are passive, so a gateway reaches R3 only through its own uplink.

**Tracking (R1 and R2):** `track 1` follows the route to R3's Loopback0, **10.255.255.3/32**, in the routing table.
It goes down when that router loses its uplink.

**LAN10, HSRP version 2, group 10, virtual IP 192.168.10.1:**
- Hello 1 s, hold 3 s on both routers.
- MD5 authentication, key string `FHRPsecret`, on both routers.
- R1: priority 110, preempt, track 1 decrement 20 → **R1 Active**.
- R2: priority 100 (default), preempt → Standby, and takes over whenever R1's priority drops below 100.

**LAN20, VRRP version 3 (`fhrp version vrrp v3`), group 20, virtual IP 192.168.20.1:**
- R2: priority 110, track 1 decrement 20 → **R2 Master**.
- R1: priority 100 (default). VRRP preempt is on by default on both.

**Load sharing:** LAN10 leaves through R1, LAN20 through R2; each router backs up the other.

## Expected behavior
- Both PCs reach 172.16.0.100 through their primary gateway.
- If a primary gateway loses its uplink, the other router takes over that LAN; when the uplink returns, the
  primary takes back over.

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1, R2 | IOL-XE routers (the gateways) | cisco | cisco | cisco |
| R3 | IOL-XE router (upstream / server; look, don't change) | cisco | cisco | cisco |
| PC1, PC2 | Alpine Linux | cisco | cisco | `sudo -i` |
| SW1, SW2 | CML unmanaged switches (no login) | — | — | — |

Open a console from the node in CML (right-click → Console). Routers start in privileged EXEC.
Each node also has a label in the CML canvas with its login and addresses.

Useful PC commands: `ping -c 2 -W 1 <ip>`, `traceroute -n -q 1 -w 1 <ip>` (hop 1 is the real address of the
router forwarding for the LAN), `ip neigh` (the gateway's MAC address).

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

## Addressing (as designed)

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
