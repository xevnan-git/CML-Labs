# EIGRP vs OSPF, Side by Side — Solution (learn-eigrp-vs-ospf)

There's no troubleshooting lab for 3.2.a: the exam topic is a comparison ("describe"), and the OSPF and EIGRP
troubleshooting topics are covered by ENCOR 3.2.b and the ENARSI 1.9 / 1.10 labs.

## Final configs
[`configs/`](configs/): every router as it should look after Step 8.
- All four routers: OSPF process 1, area 0 on every interface (`ip ospf 1 area 0`), router-id 10.255.255.N;
  EIGRP named mode `LAB`, AS 100, `network 10.0.0.0`, router-id 10.255.255.N.
- R1: `bandwidth 5000` on Ethernet0/1, Ethernet0/2 passive in both protocols, `variance 2` under
  `topology base`, `network 192.168.10.0`.
- R3: `bandwidth 5000` on Ethernet0/0.
- R4: Loopback1–4 as OSPF point-to-point, `network 172.20.0.0`, and `summary-address 172.20.0.0 255.255.252.0`
  on the Ethernet0/0 and Ethernet0/1 af-interfaces.

The Step 6 link failure is a demonstration and is reverted in the guide. The lab boots with addresses only.

## How this was tested
On the dev server (5-node license), CML 2.10.1, IOL-XE 17.18.2. The lab is 5 licensed nodes, so it ran whole:
Steps 1–8, every command as written in the guide. All output in the guide is **Captured** from that run. At the
end, the running `router eigrp` sections on R1 and R4 matched `configs/` line for line.

Notes from the run:
- OSPF took about 40 seconds to reach FULL on the R1–R3 link (EXSTART while the DR wait timer ran); the guide's
  "wait about 45 seconds" covers it. EIGRP neighbors came up within seconds.
- The first command after boot timed out once while pyATS connected (the usual first-connection delay).
- `show ip ospf route` doesn't exist on IOL-XE 17.18; `show ip ospf rib <prefix>` does.
- In Step 6 the `debug eigrp fsm` log showed the "Find FS ... found" lines for 10.255.255.4/32 and 10.3.4.0/24
  but none for the 172.20.x prefixes. `show ip route 172.20.1.0` afterwards showed them via 10.1.3.3, and their
  topology entries had listed R3 as a feasible successor. The guide only claims what the route table showed.
- `show eigrp address-family ipv4 traffic` counted exactly one query sent and one reply received for the whole
  failure, matching the three prefixes in the log that went active (one query packet can carry several routes).

## Final verification (Captured)
```
R1# show ip route 172.20.0.0 255.255.0.0 longer-prefixes | begin Gateway
      172.20.0.0/16 is variably subnetted, 5 subnets, 2 masks
D        172.20.0.0/22 [90/2048640] via 10.1.3.3, 00:00:16, Ethernet0/1
                       [90/1536640] via 10.1.2.2, 00:00:16, Ethernet0/0
O        172.20.0.0/24 [110/21] via 10.1.2.2, 00:00:16, Ethernet0/0
O        172.20.1.0/24 [110/21] via 10.1.2.2, 00:00:16, Ethernet0/0
O        172.20.2.0/24 [110/21] via 10.1.2.2, 00:00:16, Ethernet0/0
O        172.20.3.0/24 [110/21] via 10.1.2.2, 00:00:16, Ethernet0/0

R1# show ip protocols | include Routing Protocol|Distance|variance
Routing Protocol is "ospf 1"
  Distance: (default is 110)
Routing Protocol is "eigrp 100"
      Distance: internal 90 external 170
      Maximum metric variance 2

PC1:~$ ping -c 2 -W 1 172.20.1.1
2 packets transmitted, 2 packets received, 0% packet loss
PC1:~$ traceroute -n -q 1 -w 1 172.20.1.1
 1  192.168.10.1  0.930 ms
 2  10.1.2.2  1.345 ms
 3  10.2.4.4  1.753 ms
```
