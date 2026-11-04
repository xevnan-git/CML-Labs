# Control Plane Policing (CoPP) — Solution (learn-copp)

## Final configs
[`configs/`](configs/): R1 as it should look after Step 9 (only R1 changes in this lab):
- ACLs COPP-ROUTING (OSPF, BGP both directions, EIGRP), COPP-MGMT (SSH, Telnet, HTTP, HTTPS from
  192.168.10.0/24), COPP-SNMP, COPP-ICMP, COPP-CATCHALL
- class-maps CM-ROUTING, CM-MGMT, CM-MONITOR (`match-any`), CM-CATCHALL
- policy-map PM-COPP, applied with `control-plane` / `service-policy input PM-COPP`

The broken variants in Steps 6–9 are demonstrations and are reverted in the guide, so they aren't in the final
config. R2, ISP1 and the PCs are unchanged from boot.

## How this was tested
On the dev server (5-node license), CML 2.10.1, IOL-XE 17.18.2. The lab is 5 licensed nodes, so it ran whole:
Steps 1–9, every command as written in the guide. All output in the guide is **Captured** from that run.

Notes from the run:
- IOL-XE has `ip http server` and `ip http secure-server` on by default. Port 80 on R1 answered PC1 with a TCP
  reset ("Connection refused"), so HTTP is classified but not used as a test.
- No SNMP client exists on the Alpine image, so the COPP-SNMP match was never exercised (0 packets).
- Steps 6 and 7 were waited out with `sleep` on a PC; the guide's "wait 30/40 seconds" match what was observed.

## Final verification (Captured)
```
R1# show running-config | section ip access-list|class-map|policy-map|control-plane
class-map match-all CM-MGMT
 match access-group name COPP-MGMT
class-map match-all CM-CATCHALL
 match access-group name COPP-CATCHALL
class-map match-any CM-MONITOR
 match access-group name COPP-SNMP
 match access-group name COPP-ICMP
class-map match-all CM-ROUTING
 match access-group name COPP-ROUTING
policy-map PM-COPP
 class CM-ROUTING
  police 256000 conform-action transmit  exceed-action transmit
 class CM-MGMT
  police 256000 conform-action transmit  exceed-action drop
 class CM-MONITOR
  police 16000 conform-action transmit  exceed-action drop
 class CM-CATCHALL
  police 8000 conform-action drop  exceed-action drop
 class class-default
  police 64000 conform-action transmit  exceed-action drop
ip access-list extended COPP-CATCHALL
 10 permit ip any any
ip access-list extended COPP-ICMP
 10 permit icmp any any
ip access-list extended COPP-MGMT
 10 permit tcp 192.168.10.0 0.0.0.255 any eq 22
 20 permit tcp 192.168.10.0 0.0.0.255 any eq telnet
 30 permit tcp 192.168.10.0 0.0.0.255 any eq www
 40 permit tcp 192.168.10.0 0.0.0.255 any eq 443
ip access-list extended COPP-ROUTING
 10 permit ospf any any
 20 permit tcp any any eq bgp
 30 permit tcp any eq bgp any
 40 permit eigrp any any
ip access-list extended COPP-SNMP
 10 permit udp 192.168.10.0 0.0.0.255 any eq snmp
control-plane
 service-policy input PM-COPP

PC1:~$ ping -c 2 -W 1 198.51.100.10                 -> round-trip min/avg/max = 2.325/2.594/2.863 ms
PC1:~$ ssh cisco@10.255.255.1 (BatchMode)           -> Permission denied (publickey,keyboard-interactive,password).
```
The same final config was captured in the troubleshooting lab after all its faults were fixed, together with the
rest of the final-check table (OSPF FULL, BGP with 2 prefixes, PC1 Telnet/SSH/ping to R1, PC2 Telnet timing out
and ping working, counters in every class).
