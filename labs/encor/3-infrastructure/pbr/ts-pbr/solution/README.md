# Policy-Based Routing (PBR) — Solution (ts-pbr)

> Spoilers below. Try the hints first, one at a time.

## Hints

<details><summary>Hint 1 — where to look</summary>

Every fault is in R1's PBR config; addressing, static routes and the ISPs are as designed. Your best tools are
`show ip policy` (which interface has which policy), `show route-map` (the **Policy routing matches** counter and
the state of each next hop), `show access-lists`, `show track` and `show ip sla summary`. Generate one test, then
see which counter moved. `debug ip policy` shows every decision.
</details>

<details><summary>Hint 2 — what to compare</summary>

- Which interface do guest packets *enter* R1 on? Is that where the policy is?
- The route-map's match counter stays at 0 while PC2 sends traffic. Read GUEST-NET: which field is 192.168.20.0?
- Guests reach ISP2's loopback through ISP2, but 203.0.113.100 through ISP1. What does R1's routing table have
  for each, and which `set` command is configured?
- `show route-map` prints a state next to a tracked next hop. What is it, and what is the SLA actually pinging?
- R1's local policy counts matches, but its traffic still leaves through ISP1. Is the next hop reachable directly?
</details>

<details><summary>Hint 3 — almost there</summary>

- PBR only acts on packets *received* on the interface where it's applied.
- In an extended ACL the first address is the source.
- `set ip default next-hop` is used only when the routing table has no explicit route; a default route doesn't
  count, but 203.0.113.0/24 does.
- A running IP SLA entry can't be edited: `no ip sla 1`, re-enter it, schedule it again.
- A PBR next hop must be on a directly connected subnet; otherwise the set clause is ignored.
</details>

## Faults
All five faults are on R1. In the order a learner usually meets them (Faults 1 to 4 are layered: each hides
the next; Fault 5 is independent):

### Fault 1: guest policy applied to the ISP2 interface
- **Where:** R1, `interface Ethernet0/3`.
- **Injected config:** `ip policy route-map PBR-GUEST` on Ethernet0/3 (designed: Ethernet0/1).
- **Why it breaks:** PBR only checks packets as they arrive on the interface it's applied to. Guest packets
  arrive on e0/1, which has no policy, so they're routed normally (ISP1). The policy on e0/3 only ever sees
  traffic coming back from ISP2.
- **Evidence (Captured):**
  ```
  PC2:~$ traceroute -n -q 1 -w 1 203.0.113.100
   1  192.168.20.1  5.035 ms
   2  10.1.101.101  5.162 ms

  R1# show ip policy
  Interface      Route map
  local          PBR-LOCAL
  Ethernet0/3    PBR-GUEST
  ```
- **Fix:**
  ```
  R1(config)# interface Ethernet0/3
  R1(config-if)# no ip policy route-map PBR-GUEST
  R1(config-if)# interface Ethernet0/1
  R1(config-if)# ip policy route-map PBR-GUEST
  ```
  Guests still use ISP1 (Fault 2).

### Fault 2: GUEST-NET matches the guest LAN as destination
- **Where:** R1, `ip access-list extended GUEST-NET`, line 10.
- **Injected config:** `10 permit ip any 192.168.20.0 0.0.0.255` (designed: `10 permit ip 192.168.20.0 0.0.0.255 any`).
- **Why it breaks:** guest packets have 192.168.20.x as the *source*. No packet entering e0/1 is going *to* the
  guest LAN, so nothing matches and everything is routed normally.
- **Evidence (Captured, after fixing Fault 1, counters cleared, one traceroute from PC2):**
  ```
  PC2:~$ traceroute -n -q 1 -w 1 203.0.113.100
   2  10.1.101.101  2.806 ms

  R1# show route-map PBR-GUEST
  route-map PBR-GUEST, permit, sequence 10
    Match clauses:
      ip address (access-lists): GUEST-NET
    Set clauses:
      ip default next-hop 10.1.102.102
    Policy routing matches: 0 packets, 0 bytes
  R1# show access-lists GUEST-NET
  Extended IP access list GUEST-NET
      10 permit ip any 192.168.20.0 0.0.0.255
  ```
- **Fix:**
  ```
  R1(config)# ip access-list extended GUEST-NET
  R1(config-ext-nacl)# no 10
  R1(config-ext-nacl)# 10 permit ip 192.168.20.0 0.0.0.255 any
  ```
  The route-map now counts matches, but 203.0.113.100 still goes through ISP1 (Fault 3).

### Fault 3: `set ip default next-hop` instead of a tracked `set ip next-hop`
- **Where:** R1, `route-map PBR-GUEST permit 10`.
- **Injected config:** `set ip default next-hop 10.1.102.102` (designed:
  `set ip next-hop verify-availability 10.1.102.102 1 track 1`).
- **Why it breaks:** `default next-hop` is used only when the routing table has no explicit route for the
  destination (a default route doesn't count). 203.0.113.0/24 has an explicit static route to ISP1, so the
  routing table wins. Destinations covered only by 0.0.0.0/0 do go to ISP2, which makes it look like PBR half
  works. It also drops the tracking the design requires (`default next-hop` can't take a `track` on IOL-XE).
- **Evidence (Captured):**
  ```
  PC2:~$ traceroute -n -q 1 -w 1 203.0.113.100
   2  10.1.101.101  3.048 ms
  PC2:~$ traceroute -n -q 1 -w 1 10.255.255.102
   2  10.1.102.102  5.495 ms

  R1# show route-map PBR-GUEST
      ip default next-hop 10.1.102.102
    Policy routing matches: 4 packets, 240 bytes
  R1# show access-lists GUEST-NET
      10 permit ip 192.168.20.0 0.0.0.255 any (4 matches)
  R1# show ip route 203.0.113.100
  Routing entry for 203.0.113.0/24
    Known via "static", distance 1, metric 0
    * 10.1.101.101
  ```
- **Fix:**
  ```
  R1(config)# route-map PBR-GUEST permit 10
  R1(config-route-map)# no set ip default next-hop 10.1.102.102
  R1(config-route-map)# set ip next-hop verify-availability 10.1.102.102 1 track 1
  ```
  Guests still use ISP1 (Fault 4), now because the tracked next hop is down.

### Fault 4: IP SLA probes an address that doesn't exist
- **Where:** R1, `ip sla 1`.
- **Injected config:** `icmp-echo 10.1.102.201 source-interface Ethernet0/3` (designed: `icmp-echo 10.1.102.102 …`).
- **Why it breaks:** nothing answers 10.1.102.201, so the probe times out, track 1 is Down, and
  `verify-availability` skips the next hop. With no usable next hop, PBR silently falls back to the routing table
  (ISP1). The failover "works" all the time.
- **Evidence (Captured):**
  ```
  PC2:~$ traceroute -n -q 1 -w 1 203.0.113.100
   2  10.1.101.101  0.987 ms

  R1# show route-map PBR-GUEST
      ip next-hop verify-availability 10.1.102.102 1 track 1  [down]
    Policy routing matches: 6 packets, 360 bytes
  R1# show track 1
  Track 1
    IP SLA 1 reachability
    Reachability is Down
    Latest operation return code: Timeout
  R1# show ip sla summary
  ID           Type        Destination       Stats       Return      Last
  *1           icmp-echo   10.1.102.201      -           Timeout     6 seconds ago
  ```
- **Fix:** a running IP SLA entry can't be edited (`Entry already running and cannot be modified`), so recreate it:
  ```
  R1(config)# no ip sla 1
  R1(config)# ip sla 1
  R1(config-ip-sla)# icmp-echo 10.1.102.102 source-interface Ethernet0/3
  R1(config-ip-sla-echo)# frequency 5
  R1(config-ip-sla-echo)# exit
  R1(config)# ip sla schedule 1 life forever start-time now
  ```
  Track 1 stays configured and goes Up within about 10 seconds. PC2's traceroute now ends at 10.1.102.102.

### Fault 5: local policy next hop not on a connected subnet
- **Where:** R1, `route-map PBR-LOCAL permit 10`.
- **Injected config:** `set ip next-hop 10.1.120.102` (designed: `set ip next-hop 10.1.102.102`).
- **Why it breaks:** a PBR next hop must be directly connected. 10.1.120.102 isn't on any of R1's subnets
  (`show ip route 10.1.120.102`: `% Subnet not in table`), so PBR ignores the set clause and routes R1's traffic
  normally, through ISP1. ISP1 has no route to ISP2's loopback, hence the `U`. The match counter still counts,
  which makes the policy look active.
- **Evidence (Captured):**
  ```
  R1# ping 10.255.255.102 source Loopback0 repeat 2 timeout 1
  Packet sent with a source address of 10.255.255.1
  U.
  Success rate is 0 percent (0/2)
  R1# traceroute 203.0.113.100 source Loopback0 probe 1 timeout 1 ttl 1 3
    1 10.1.101.101 1 msec
  R1# show route-map PBR-LOCAL
      ip next-hop 10.1.120.102
    Policy routing matches: 3 packets, 260 bytes
  R1# show ip route 10.1.120.102
  % Subnet not in table
  ```
- **Fix:**
  ```
  R1(config)# route-map PBR-LOCAL permit 10
  R1(config-route-map)# no set ip next-hop 10.1.120.102
  R1(config-route-map)# set ip next-hop 10.1.102.102
  ```

## Verification after all fixes (Captured)
```
R1# show ip policy
Interface      Route map
local          PBR-LOCAL
Ethernet0/1    PBR-GUEST

R1# show route-map
route-map PBR-GUEST, permit, sequence 10
  Match clauses:
    ip address (access-lists): GUEST-NET
  Set clauses:
    ip next-hop verify-availability 10.1.102.102 1 track 1  [up]
  Policy routing matches: 8 packets, 480 bytes
route-map PBR-LOCAL, permit, sequence 10
  Match clauses:
    ip address (access-lists): R1-LOOPBACK
  Set clauses:
    ip next-hop 10.1.102.102
  Policy routing matches: 6 packets, 520 bytes

R1# ping 10.255.255.102 source Loopback0 repeat 2 timeout 1
!!
Success rate is 100 percent (2/2), round-trip min/avg/max = 1/1/2 ms
R1# traceroute 203.0.113.100 source Loopback0 probe 1 timeout 1 ttl 1 3
  1 10.1.102.102 2 msec
R1# traceroute 203.0.113.100 probe 1 timeout 1 ttl 1 3
  1 10.1.101.101 2 msec

PC2:~$ traceroute -n -q 1 -w 1 203.0.113.100
 1  192.168.20.1  1.014 ms
 2  10.1.102.102  3.045 ms
PC1:~$ traceroute -n -q 1 -w 1 203.0.113.100
 1  192.168.10.1  1.123 ms
 2  10.1.101.101  0.941 ms
```
**Failover (Captured, same design, before the fault re-injection):** with ISP2's e0/0 shut, R1's e0/3 stayed
up/up, track 1 went Down (`%TRACK-6-STATE: 1 ip sla 1 reachability Up -> Down`), and PC2's traceroute ended at
10.1.101.101 within 12 seconds. After `no shutdown` the track came back Up and guests returned to ISP2.

## How this was tested
On the dev server, CML 2.10.1, IOL-XE 17.18.2, whole lab (5 licensed nodes). The faults were confirmed in the
order above, each fix applied live. Notes:
- The first test boot had Fault 3 written as `set ip default next-hop verify-availability 10.1.102.102 1 track 1`,
  which IOL-XE rejects at boot (that form exists only without an address, as a CDP check). The fault was changed
  to the plain `set ip default next-hop 10.1.102.102`, re-injected by CLI on the full topology together with the
  other four, and all five were confirmed in the order above. Afterwards the final faulted R1 config was booted on
  its own and loaded without errors (`show route-map`, `show ip policy` and `show ip sla summary` matched the
  faulted design).
- Telnet from R1 to 203.0.113.100 works for a person but wedges the automated pyATS session, so R1's path was
  tested with ping and traceroute.
