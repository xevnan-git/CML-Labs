# Spanning Tree: RSTP, MST, Root Guard and BPDU Guard — Solution (learn-stp)

## Final configs
[`configs/`](configs/): every switch as it should look after Step 7, with MST region `LAB` rev 1 (instance 1 =
VLAN 10, instance 2 = VLAN 20), SW1 root for MST0/1 and SW2 root for MST2, PortFast + BPDU guard on SW3 e1/0 and e1/2
and SW4 e1/0, and root guard on SW4 e1/2. SW5 is unchanged from boot, with its ports shut.

## How this was tested
On the dev server (5-node license) in two passes on CML 2.10.1 with IOL-L2-XE 17.18.2:
1. SW1–SW5: Steps 1–7, every command exactly as written in the guide. All output in the guide is **Captured**
   from that run.
2. SW1, SW3, SW4 + PC1, then SW1, SW3, SW4 + PC1 + PC2 with SW2 stopped: final reachability.

## Final verification (Captured)
```
SW1# show spanning-tree root
MST Instance           Root ID          Cost    Time  Age Dly  Root Port
MST0              4096 aabb.cc00.0a00         0    2   20  15
MST1              4097 aabb.cc00.0a00         0    2   20  15
MST2              4098 aabb.cc00.0b00   2000000    2   20  15  Et0/0

SW4# show spanning-tree mst configuration digest
Name      [LAB]
Revision  1     Instances configured 3
Digest          0x9357EBB7A8D74DD5FEF4F2BAB50531AA
Pre-std Digest  0x3B25D71AE88BA09B591621DB58F62F50

SW4# show spanning-tree mst
##### MST0    vlans mapped:   1-9,11-19,21-4094
Bridge        address aabb.cc00.0d00  priority      32768 (32768 sysid 0)
Root          address aabb.cc00.0a00  priority      4096  (4096 sysid 0)
              port    Et0/0           path cost     0
Regional Root address aabb.cc00.0a00  priority      4096  (4096 sysid 0)
                                      internal cost 2000000   rem hops 19
Et0/0                            Root FWD 2000000   128.1    P2p
Et0/1                            Altn BLK 2000000   128.2    P2p
Et1/0                            Desg FWD 2000000   128.5    P2p Edge
##### MST1    vlans mapped:   10
Et0/0                            Root FWD 2000000   128.1    P2p
Et0/1                            Altn BLK 2000000   128.2    P2p
##### MST2    vlans mapped:   20
Root          address aabb.cc00.0b00  priority      4098  (4096 sysid 2)
Et0/0                            Altn BLK 2000000   128.1    P2p
Et0/1                            Root FWD 2000000   128.2    P2p
Et1/0                            Desg FWD 2000000   128.5    P2p Edge

PC1:~$ ping -c 3 192.168.10.1        3 packets transmitted, 3 packets received, 0% packet loss
PC1:~$ ping -c 3 192.168.20.1        3 packets transmitted, 3 packets received, 0% packet loss
PC1:~$ ping -c 3 192.168.99.204      3 packets transmitted, 2 packets received   (first ping lost to ARP)
PC2:~$ ping -c 3 192.168.10.10       3 packets transmitted, 3 packets received, 0% packet loss
```

## Notes from testing
- IOL-L2-XE defaults to **rapid-pvst**, so the guide observes RSTP from the start; there's no PVST+ → RSTP
  migration step.
- IOL MAC addresses (`aabb.cc00.XX00`) come from the node's ID in CML, so the default root in Step 1 may be a
  different switch on another server. The guide says so.
- IOL-L2 runs with `ip routing` enabled by default, which makes it ignore `ip default-gateway`. The access and
  backup switches carry `no ip routing` so their VLAN 99 addresses are reachable from other subnets.
- During Step 7 only SW4 (the mismatched switch) showed `Bound(RSTP)`. Its neighbors didn't flag the boundary in
  `show spanning-tree mst`, so check the switch you suspect, not just the distribution layer.
