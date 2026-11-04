# ACLs and CoPP, Layered on the Edge — Solution (learn-acl-copp)

## Final configs
[`configs/`](configs/): R1 as it should look after Step 7 (only R1 changes in this lab):
- `IACL-IN` (ISP peer, anti-spoofing, protect R1, transit), applied `ip access-group IACL-IN in` on Ethernet0/1,
  with `no ip unreachables` on that interface
- the 5.2.b CoPP policy unchanged: ACLs COPP-*, class-maps CM-*, policy-map PM-COPP on the control plane
- standard ACL `VTY-MGMT` (permit 192.168.10.10, deny and log the rest) as `access-class VTY-MGMT in` on
  `line vty 0 4`

R2, ISP1 and the PCs are unchanged from boot. The final R1 config is identical to the intended design of the
ts-acl-copp lab.

## How this was tested
On the dev server (5-node license), CML 2.10.1, IOL-XE 17.18.2. The lab is 5 licensed nodes, so it ran whole:
Steps 1–7, every command as written in the guide. All output in the guide is **Captured** from that run.

Notes from the run:
- **Order of the layers.** With `ip unreachables` on (the default), a packet the iACL denies is still sent to the
  CPU to generate the ICMP unreachable, and CoPP classifies it there: ISP1's 5 private-source pings showed 5
  matches on iACL line 40 and 3 packets in CM-MONITOR, matching the 3 `U` replies. A telnet SYN denied by line
  120 went to CM-CATCHALL, was dropped (so no unreachable reached PC2), and line 120's counter stayed at 0. With
  `no ip unreachables`, the iACL counted every denied packet (line 40: 5, line 120: 3) and every CoPP class except
  routing stayed at 0. The guide states only these counter results.
- Before CoPP was applied, the same telnet from PC2 failed at once with "Host is unreachable" and line 120 counted
  it (Step 3).
- In Step 7's "try it without" test, R2's telnet sourced from Ethernet0/1 reached R1 (`show users` on R1 listed
  vty 0 from 192.168.10.1); it was cleared with `clear line vty 0`.
- `traceroute 198.51.100.10 timeout 1 probe 1 ttl 1 3` keeps the IOS traceroute short; the final hop answers
  with an ICMP port unreachable, which iACL line 100 counts.

## Final verification (Captured)
```
R1# show running-config interface Ethernet0/1
interface Ethernet0/1
 description ISP1 e0/0 (AS 64511)
 ip address 10.1.101.1 255.255.255.0
 no ip unreachables
 ip access-group IACL-IN in

R1# show ip ospf neighbor
Neighbor ID     Pri   State           Dead Time   Address         Interface
10.255.255.2      1   FULL/DR         00:00:32    10.1.2.2        Ethernet0/0
R1# show ip bgp summary | begin Neighbor
Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
10.1.101.101    4        64511      86      88        5    0    0 00:13:18        2

R1# show access-lists VTY-MGMT
Standard IP access list VTY-MGMT
    10 permit 192.168.10.10 (4 matches)
    20 deny   any log (1 match)

PC1:~$ telnet 10.255.255.1                -> Connected to 10.255.255.1 / User Access Verification
PC1:~$ ssh cisco@10.255.255.1 (BatchMode) -> Permission denied (publickey,keyboard-interactive,password).
                                             (the session reached the login stage)
PC1:~$ ping -c 2 198.51.100.10            -> 2 packets transmitted, 2 packets received, 0% packet loss
R2# telnet 10.1.2.1 /source-interface Ethernet0/1
% Connection refused by remote host
```
