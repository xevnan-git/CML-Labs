# FHRP (HSRP and VRRP) — Solution (learn-fhrp)

## Final configs
[`configs/`](configs/): every node as it should look after Step 7 (R3 and the PCs don't change):
- R1 e0/0: `standby version 2`, group 10 VIP 192.168.10.1, `timers 1 3`, `priority 110`, `preempt`, MD5 key
  `FHRPsecret`, `track 1 decrement 20`
- R2 e0/0: the same group without priority (100) or tracking
- R1 e0/1: VRRPv3 group 20, `address 192.168.20.1 primary` (priority 100)
- R2 e0/1: VRRPv3 group 20, `priority 110`, `track 1 decrement 20`, `address 192.168.20.1 primary`
- R1 and R2: `fhrp version vrrp v3`, `track 1 ip route 10.255.255.3 255.255.255.255 reachability`

## How this was tested
On the dev server (5-node license), CML 2.10.1, IOL-XE 17.18.2, Alpine 3.23. The lab is 5 licensed nodes plus two
unmanaged switches (which don't use a license), so it ran whole: Steps 1–7, every command as written in the guide.
All output in the guide is **Captured** from that run, except the R2-uplink row of the final check, which was
captured in the troubleshooting lab (same final config).

Notes from the run:
- **Step 2's election** isn't deterministic in general: R2 won because it joined while R1 was still in its
  hold-time wait. If you configure R1 and wait 15 s before configuring R2, R1 will already be Active and stay
  Active (no preempt).
- **Failover on `shutdown`:** R1 logged `Active -> Init` at 05:25:57.926 and R2 `Standby -> Active` at
  05:25:57.924: the takeover was immediate, not after the hold time, and a 5-per-second ping lost nothing.
- **Cable pull (CML link stop on R1–SW1):** R1's e0/0 stayed up/up, R1 and R2 were both Active, and PC1 lost 549
  of 600 pings (91%) for the rest of the run because R3 sent the replies to R1
  (`show ip cef exact-route 172.16.0.100 192.168.10.10` → `Ethernet0/0, addr 10.1.3.1`).
- **Busybox ping output is block-buffered when redirected to a file**, so a file read mid-run under-counts.
  Read it after the run ends, or watch the ping live in the console as the guide does.
- **Uplink failure (Step 5):** R1's track went down and HSRP moved within half a second, but PC1's pings failed
  until R3's OSPF dead timer expired, 30 s after the shutdown (R3 still had R1 as a next hop for LAN10).
- **Changing a track object's type** in place is refused: `% Cannot change tracked object 1 - delete old config
  first`. `no track 1` and re-entering it works, and keeps the FHRP's `track 1 decrement 20` line.
- VRRPv3 adverts mismatching in address log `%VRRP-4-CFG_WARN: … addresses do not match` (seen in the
  troubleshooting lab).

## Final verification (Captured)
```
R1# show standby brief
Interface   Grp  Pri P State   Active          Standby         Virtual IP
Et0/0       10   110 P Active  local           192.168.10.3    192.168.10.1
R1# show vrrp brief
  Interface          Grp  A-F Pri  Time Own Pre State   Master addr/Group addr
  Et0/1               20 IPv4 100  3609  N   Y  BACKUP  192.168.20.3 192.168.20.1
R1# show running-config interface Ethernet0/0
interface Ethernet0/0
 description LAN10 staff (PC1) via SW1
 ip address 192.168.10.2 255.255.255.0
 standby version 2
 standby 10 ip 192.168.10.1
 standby 10 timers 1 3
 standby 10 priority 110
 standby 10 preempt
 standby 10 authentication md5 key-string FHRPsecret
 standby 10 track 1 decrement 20
 ip ospf 1 area 0
R1# show running-config | include ^track|^fhrp
fhrp version vrrp v3
track 1 ip route 10.255.255.3 255.255.255.255 reachability

R2# show standby brief
Et0/0       10   100 P Standby 192.168.10.2    local           192.168.10.1
R2# show vrrp brief
  Et0/1               20 IPv4 110     0  N   Y  MASTER  192.168.20.3(local) 192.168.20.1

PC1$ traceroute -n -q 1 -w 1 172.16.0.100
 1  192.168.10.2  3.144 ms
 2  10.1.3.3  4.657 ms
PC2$ traceroute -n -q 1 -w 1 172.16.0.100
 1  192.168.20.3  2.177 ms
 2  10.2.3.3  2.546 ms
```

## Check yourself — answers
- **No preempt, R2 first:** R2 stays Active. Only R2 failing (or `preempt` on R1) moves it. (Fault 4 in the
  troubleshooting lab is the mirror image: R2 lacks preempt, so it never takes over from a degraded R1.)
- **Decrement too small:** with `decrement 5`, R1 drops to 105, still above R2's 100, so R1 stays Active with no
  uplink and LAN10's traffic is dropped (PC1 gets `!H` from R1). (Fault 3 in the troubleshooting lab.)
- **Key mismatch:** both routers Active, Standby `unknown`, and `%HSRP-4-BADAUTH2` logs on both. The key is case
  sensitive. (Fault 1.)
- **VRRP address mismatch:** R2 (higher priority) is Master for .254 and R1 stays Backup; nobody answers ARP for
  .1, so PC2's gateway entry is `INCOMPLETE`. Both log `%VRRP-4-CFG_WARN … addresses do not match`. (Fault 2.)
- **Tracking `Ethernet0/0`:** it catches only R2's LAN10 port going down, which says nothing about R2's way out.
  It misses the uplink failure, the one that matters for LAN20: R2 stays Master and PC2 gets `!H`. (Fault 5.)
- **The ~30 s loss in Step 5:** R3. It kept routing the replies to R1 until its OSPF dead timer expired.
- **No re-ARP:** the virtual MAC moves with the virtual IP; the new Active router sends gratuitous ARPs so the
  switches learn the MAC's new port.
