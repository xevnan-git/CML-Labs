# Policy-Based Routing (PBR) — Solution (learn-pbr)

## Final configs
[`configs/`](configs/): R1 as it should look after Step 8 (R1 is the only router whose config changes for good):
- ACL GUEST-NET (`permit ip 192.168.20.0 0.0.0.255 any`) and route-map PBR-GUEST with
  `set ip next-hop verify-availability 10.1.102.102 1 track 1`, applied with `ip policy` on Ethernet0/1
- IP SLA 1 (`icmp-echo 10.1.102.102 source-interface Ethernet0/3`, every 5 s) and `track 1 ip sla 1 reachability`
- ACL R1-LOOPBACK (`permit ip host 10.255.255.1 any`) and route-map PBR-LOCAL (`set ip next-hop 10.1.102.102`),
  applied with `ip local policy route-map PBR-LOCAL`

The `default next-hop` variant (Step 5) and the untracked next hop (Step 6) are demonstrations and are reverted
in the guide. ISP2's `shutdown` in Steps 6–7 is undone in Step 7. ISP1, ISP2 and the PCs are unchanged from boot.

## How this was tested
On the dev server (5-node license), CML 2.10.1, IOL-XE 17.18.2. The lab is 5 licensed nodes, so it ran whole:
Steps 1–8, every command as written in the guide. All output in the guide is **Captured** from that run.

Notes from the run:
- **`set ip default next-hop` ignores the default route** (verified): with only 0.0.0.0/0 in the RIB, PC2 still
  reached ISP2. That's why R1 boots with the explicit static 203.0.113.0/24 → ISP1: it makes the difference
  between `next-hop` and `default next-hop` visible.
- **`set ip default next-hop` has no `track` option on IOL-XE 17.18.** `set ip default next-hop
  verify-availability` exists but takes no address: it's the older CDP-based check.
- **Traceroute shows the ISP:** busybox traceroute's last hop is the ISP's interface address toward R1
  (10.1.101.101 / 10.1.102.102), not the loopback, so it distinguishes the two ISPs even though both own
  203.0.113.100.
- **Black hole without tracking:** with ISP2's e0/0 shut, R1's e0/3 stays up/up and the ARP entry for
  10.1.102.102 stays cached, so `set ip next-hop` kept sending guest traffic into it (100% loss).
- **Track timing:** with `frequency 5` and no track delay, the track went down within about 10 s and came back
  up within 10 s. The guide's "wait 10 seconds" matches what was observed.
- **Telnet from R1 to 203.0.113.100** works for a person at the console, but it wedges the automated (pyATS)
  session, so the guide uses ping and traceroute from R1 instead.
- The PCs' DHCP client broadcasts (`s=0.0.0.0 … d=255.255.255.255`) show up in `debug ip policy` as *policy
  rejected -- normal forwarding*.

## Final verification (Captured)
```
R1# show running-config | section ip sla|^track|route-map|ip local|GUEST-NET|R1-LOOPBACK
track 1 ip sla 1 reachability
 ip policy route-map PBR-GUEST
ip local policy route-map PBR-LOCAL
ip access-list extended GUEST-NET
 10 permit ip 192.168.20.0 0.0.0.255 any
ip access-list extended R1-LOOPBACK
 10 permit ip host 10.255.255.1 any
ip sla 1
 icmp-echo 10.1.102.102 source-interface Ethernet0/3
  frequency 5
ip sla schedule 1 life forever start-time now
route-map PBR-GUEST permit 10
 match ip address GUEST-NET
 set ip next-hop verify-availability 10.1.102.102 1 track 1
route-map PBR-LOCAL permit 10
 match ip address R1-LOOPBACK
 set ip next-hop 10.1.102.102

R1# show track 1 brief
Track Type        Instance                   Parameter        State Last Change
1     ip sla      1                          reachability     Up    00:01:50

R1# show ip policy
Interface      Route map
local          PBR-LOCAL
Ethernet0/1    PBR-GUEST

PC1:~$ traceroute -n -q 1 -w 1 203.0.113.100
 1  192.168.10.1  0.854 ms
 2  10.1.101.101  1.123 ms
PC2:~$ traceroute -n -q 1 -w 1 203.0.113.100
 1  192.168.20.1  1.148 ms
 2  10.1.102.102  1.038 ms

R1# ping 10.255.255.102 source Loopback0 repeat 2 timeout 1
!!
Success rate is 100 percent (2/2), round-trip min/avg/max = 1/1/1 ms
```

## Check yourself — answers
- **Policy on Ethernet0/3:** it checks packets *arriving* from ISP2 (return traffic), never guest traffic leaving.
  Guests use the routing table (ISP1), and `show route-map` counts nothing for them.
- **`permit ip any 192.168.20.0 0.0.0.255`:** that matches traffic *to* the guest LAN. Guest packets coming in on
  e0/1 have 192.168.20.x as the source, so nothing matches; they're routed normally through ISP1 and the match
  counter stays at 0.
- **`default next-hop`:** destinations with an explicit route (203.0.113.0/24) use ISP1. Destinations that only
  match the default route use ISP2.
- **Track down because of a typo:** guests silently use the routing table (ISP1). Nothing fails, so nobody
  notices until someone checks `show route-map` (`[down]`) or `show track`.
- **R1 ping without a source:** R1 sources it from e0/2 (10.1.101.1), the outgoing interface by the routing
  table. PBR-LOCAL matches only 10.255.255.1, so the ping goes to ISP1, which has no route to 10.255.255.102
  (`U`).
- **Next hop not on a connected subnet:** PBR ignores that set clause and routes the packet normally. It's
  silent: the route-map still counts matches. (Verified in the troubleshooting lab.)
- **IP SLA probe and PBR-LOCAL:** the probe's source is 10.1.102.1 (e0/3), not 10.255.255.1, so R1-LOOPBACK
  doesn't match it. `debug ip policy` shows those probes as *policy rejected -- normal forwarding*.
