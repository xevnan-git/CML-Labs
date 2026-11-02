# ACLs: Standard, Extended, Named and Time-Based — Solution (learn-acl)

## Final configs
[`configs/`](configs/): R1 and R2 as they should look after Step 8:
- R1 `CONTRACTORS-IN` inbound on Ethernet0/2 (web to SRV1 during `BUSINESS-HOURS`, ping to SRV1, deny + log the
  rest of the server LAN, permit everything else)
- R1 `BRANCH-IN` inbound on Ethernet0/0 (OSPF, TCP `established` to 192.168.10.0 0.0.1.255, ICMP, deny + log)
- R1 and R2 `VTY-ADMIN` with `access-class VTY-ADMIN in` on vty 0–4 (VLAN 10 only)
- R1 `time-range BUSINESS-HOURS` (weekdays 08:00–17:00)

Standard ACL 10 (Step 2) is a placement demonstration and is removed again in the guide, so it isn't in the final
config. The PC/SRV files are the Alpine boot scripts (SRV1 starts the web server).

## How this was tested
On the dev server (5-node license), CML 2.10.1, IOL-XE 17.18.2. The lab is 5 licensed nodes, so it ran whole:
Steps 1–8, every command as written in the guide. All output in the guide is **Captured** from that run.

One difference: in Step 8 the "outside business hours" output was captured with the router's own boot clock
(04:10 UTC on a Monday) instead of after `clock set 04:00:00 …`. It's the same state. The `clock set 10:00:00 …`
half was run as written.

## Final verification (Captured)
```
R1# show running-config | section time-range|ip access-list|access-group|access-class
 ip access-group BRANCH-IN in
 ip access-group CONTRACTORS-IN in
ip access-list standard VTY-ADMIN
 10 permit 192.168.10.0 0.0.0.255
ip access-list extended BRANCH-IN
 10 permit ospf any any
 20 permit tcp any 192.168.10.0 0.0.1.255 established
 30 permit icmp any any
 40 deny ip any any log
ip access-list extended CONTRACTORS-IN
 10 permit tcp 192.168.11.0 0.0.0.255 host 192.168.50.10 eq www time-range BUSINESS-HOURS
 20 permit icmp 192.168.11.0 0.0.0.255 host 192.168.50.10 echo
 30 deny ip 192.168.11.0 0.0.0.255 192.168.50.0 0.0.0.255 log
 40 permit ip 192.168.11.0 0.0.0.255 any
 access-class VTY-ADMIN in
time-range BUSINESS-HOURS
 periodic weekdays 8:00 to 17:00

R1# show ip ospf neighbor
Neighbor ID     Pri   State           Dead Time   Address         Interface
10.255.255.2      1   FULL/DR         00:00:33    10.1.2.2        Ethernet0/0

R1# show access-lists BRANCH-IN
Extended IP access list BRANCH-IN
    10 permit ospf any any (13 matches)
    20 permit tcp any 192.168.10.0 0.0.1.255 established (14 matches)
    30 permit icmp any any (2 matches)
    40 deny ip any any log (13 matches)

R2# show access-lists VTY-ADMIN
Standard IP access list VTY-ADMIN
    10 permit 192.168.10.0, wildcard bits 0.0.0.255 (4 matches)
```

Final check table from the guide (Captured, inside business hours):
```
PC1:~$ wget -q -O - http://192.168.50.10/     -> <h1>SRV1 intranet</h1>
PC1:~$ nc -zv -w 3 192.168.50.10 22           -> 192.168.50.10 (192.168.50.10:22) open
PC1:~$ telnet 10.255.255.2                    -> Connected to 10.255.255.2
PC2:~$ wget -q -T 3 -O - http://192.168.50.10/ -> <h1>SRV1 intranet</h1>
PC2:~$ ping -c 2 192.168.50.10                -> 2 packets transmitted, 2 packets received, 0% packet loss
PC2:~$ nc -zv -w 3 192.168.50.10 22           -> Host is unreachable
PC2:~$ ping -c 2 172.18.0.1                   -> 2 packets transmitted, 2 packets received, 0% packet loss
PC2:~$ telnet 10.255.255.2                    -> Connection refused
SRV1:~$ nc -zv -w 3 192.168.10.10 22          -> Host is unreachable
```
`PC2 telnet 10.255.255.1` (R1) was captured as refused in the troubleshooting lab, which has the same final R1
config.
