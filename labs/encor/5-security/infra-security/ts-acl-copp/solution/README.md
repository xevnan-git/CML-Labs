# ACLs and CoPP, Layered on the Edge — Solution (ts-acl-copp)

> Spoilers below. Try the hints first, one at a time.

## Hints

<details><summary>Hint 1 — where to look</summary>

Every fault is on R1, in the three protection layers; routing, addressing and the other routers are as designed.
Work through the layers in the order the router applies them: interface ACL (`show access-lists IACL-IN`), then
CoPP (`show policy-map control-plane`), then the vty ACL (`show access-lists VTY-MGMT`). Generate one test, then
see which counter moved. Start with BGP, because nothing on the internet can be tested until R1 has routes.
</details>

<details><summary>Hint 2 — what to compare</summary>

- BGP is stuck in Active. CoPP's routing class is fine. Which iACL line is counting packets from the ISP peer?
- Once BGP is up, PC1 still can't reach PC2, and the iACL has no line counting the replies. What happens at the
  end of an ACL?
- SSH hangs but Telnet works. VTY-MGMT counts the Telnet sessions but not the SSH ones, so SSH never reached the
  vty line. Which layer before it would drop it?
- PC1 reaches the internet, but R1 itself can't ping PC2, and its traceroute stops after the first hop. Which iACL
  line counts the replies coming back to R1?
</details>

<details><summary>Hint 3 — almost there</summary>

- 10.1.101.101 is inside 10.0.0.0/8. First match wins.
- An ACL that only lists things to deny needs an explicit permit at the end.
- Read COPP-MGMT line by line against the design table.
- An iACL can't tell "a reply to R1" from "a new packet to R1": every reply type R1 needs must be permitted.
</details>

## Faults
All four faults are on R1. In the order a learner usually meets them:

### Fault 1: anti-spoofing above the ISP-peer lines
- **Where:** R1, `ip access-list extended IACL-IN`, section order.
- **Injected config:** the anti-spoofing denies are lines 10–40 and the ISP-peer permits are lines 50–70
  (designed: peer permits 10–30, anti-spoofing 40–70).
- **Why it breaks:** `deny ip 10.0.0.0 0.255.255.255 any` also matches the BGP peer 10.1.101.101. R1 opens the
  session, so its SYN goes out, but ISP1's SYN-ACK is denied on line 10 before the BGP permit is reached. R1 never
  gets a route to the internet, and pings from ISP1's link address are dropped too.
- **Evidence (Captured):**
  ```
  R1# show ip bgp summary | begin Neighbor
  Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
  10.1.101.101    4        64511       0       0        1    0    0 never    Active
  R1# show tcp brief | include 179
  758410969CA8  10.1.101.1.20081           10.1.101.101.179            SYNSENT
  R1# show access-lists IACL-IN
  Extended IP access list IACL-IN
      10 deny ip 10.0.0.0 0.255.255.255 any (25 matches)
      ...
      50 permit tcp host 10.1.101.101 host 10.1.101.1 eq bgp
      60 permit tcp host 10.1.101.101 eq bgp host 10.1.101.1
      70 permit icmp host 10.1.101.101 host 10.1.101.1
  R1# show ip route | include Gateway
  Gateway of last resort is not set
  R1# ping 10.1.101.101 repeat 2
  ..
  Success rate is 0 percent (0/2)
  ```
  CoPP isn't involved: COPP-ROUTING matches BGP both ways, and CM-ROUTING never drops.
- **Fix:** move the peer lines above anti-spoofing (numbers below 10 put them first):
  ```
  R1(config)# ip access-list extended IACL-IN
  R1(config-ext-nacl)# no 50
  R1(config-ext-nacl)# no 60
  R1(config-ext-nacl)# no 70
  R1(config-ext-nacl)# 1 permit tcp host 10.1.101.101 host 10.1.101.1 eq bgp
  R1(config-ext-nacl)# 2 permit tcp host 10.1.101.101 eq bgp host 10.1.101.1
  R1(config-ext-nacl)# 3 permit icmp host 10.1.101.101 host 10.1.101.1
  ```
  Optionally tidy up afterwards with `ip access-list resequence IACL-IN 10 10` (global config), which renumbers
  every line; the other fixes below use the original numbers, so do it last. BGP is Established with 2 prefixes
  about a minute later (Captured: `10.1.101.101 ... 00:01:18  2`). PC1 still can't reach PC2: Fault 2.

### Fault 2: no transit permit
- **Where:** R1, `IACL-IN`, end of the list.
- **Injected config:** line `150 permit ip any any` missing.
- **Why it breaks:** every line in the list is about R1 or about spoofed sources. Replies coming back to the
  office (from 198.51.100.10 to 192.168.10.10) match none of them and hit the implicit `deny ip any any` at the
  end. Implicit-deny drops don't show up on any line's counter.
- **Evidence (Captured, after Fault 1):**
  ```
  PC1:~$ ping -c 2 -W 1 198.51.100.10
  2 packets transmitted, 0 packets received, 100% packet loss
  R1# show access-lists IACL-IN
      ...
      140 deny ip any 10.1.2.0 0.0.0.255
  (no line after 140)
  ```
- **Fix:**
  ```
  R1(config)# ip access-list extended IACL-IN
  R1(config-ext-nacl)# 150 permit ip any any
  ```
  PC1 reaches PC2 at once (Captured: `2 packets transmitted, 2 packets received`).

### Fault 3: CoPP management class lost SSH
- **Where:** R1, `ip access-list extended COPP-MGMT`.
- **Injected config:** line `10 permit tcp 192.168.10.0 0.0.0.255 any eq 22` missing.
- **Why it breaks:** PC1's traffic comes in on e0/0, so the iACL never sees it. CoPP matches Telnet (line 20) into
  CM-MGMT, but SSH matches no line in COPP-MGMT, falls into CM-CATCHALL and is dropped silently. The vty ACL would
  permit PC1, but SSH never gets that far.
- **Evidence (Captured, present from boot):**
  ```
  PC1:~$ ssh cisco@10.255.255.1
  ssh: connect to host 10.255.255.1 port 22: Operation timed out
  PC1:~$ telnet 10.255.255.1          -> Connected to 10.255.255.1 / User Access Verification

  R1# show access-lists VTY-MGMT
      10 permit 192.168.10.10 (2 matches)
  R1# show access-lists COPP-MGMT
  Extended IP access list COPP-MGMT
      20 permit tcp 192.168.10.0 0.0.0.255 any eq telnet (9 matches)
      30 permit tcp 192.168.10.0 0.0.0.255 any eq www
      40 permit tcp 192.168.10.0 0.0.0.255 any eq 443
  R1# show policy-map control-plane input class CM-CATCHALL
          conformed 6 packets, 444 bytes; actions:
            drop
  ```
  The two VTY-MGMT matches are the Telnet session; SSH attempts add nothing there.
- **Fix:**
  ```
  R1(config)# ip access-list extended COPP-MGMT
  R1(config-ext-nacl)# 10 permit tcp 192.168.10.0 0.0.0.255 any eq 22
  ```

### Fault 4: only `echo` permitted to R1
- **Where:** R1, `IACL-IN`, the "protect R1" section.
- **Injected config:** lines `90 permit icmp any host 10.1.101.1 echo-reply`, `100 … unreachable` and
  `110 … time-exceeded` missing.
- **Why it breaks:** R1's own ping to 198.51.100.10 leaves from 10.1.101.1, so the echo-reply comes back *to*
  10.1.101.1. With only `echo` permitted, the reply falls to `120 deny ip any host 10.1.101.1`. Traceroute shows
  the same thing: hop 1 answers from the peer 10.1.101.101 (permitted by line 30), but the port unreachable from
  PC2 is denied. Transit traffic is unaffected, which hides this fault until Faults 1 and 2 are fixed, and anyone
  testing only from PC1 never notices.
- **Evidence (Captured, after Faults 1 and 2):**
  ```
  R1# ping 198.51.100.10 repeat 2
  ..
  Success rate is 0 percent (0/2)
  R1# traceroute 198.51.100.10 timeout 1 probe 1 ttl 1 3
    1 10.1.101.101 1 msec
    2  *
    3  *
  R1# show access-lists IACL-IN
      80 permit icmp any host 10.1.101.1 echo (4 matches)
      120 deny ip any host 10.1.101.1 (8 matches)
      150 permit ip any any (2 matches)
  PC1:~$ ping -c 2 -W 1 198.51.100.10      -> works
  ```
- **Fix:**
  ```
  R1(config)# ip access-list extended IACL-IN
  R1(config-ext-nacl)# 90 permit icmp any host 10.1.101.1 echo-reply
  R1(config-ext-nacl)# 100 permit icmp any host 10.1.101.1 unreachable
  R1(config-ext-nacl)# 110 permit icmp any host 10.1.101.1 time-exceeded
  ```
  If you already resequenced the list, insert these between the `echo` line and the `deny ip any host
  10.1.101.1` line using any free numbers in that gap.

## Final configs
`configs/<node>.cfg` — the complete working configuration of every node (the intended design). Only R1 differs
from the boot config. The PC files are the Alpine boot scripts.

## Verification
All four faults were injected together and confirmed on the dev server (5 licensed nodes, the whole lab), then
fixed in order 1 → 4. That first run was made before `no ip unreachables` was added to the design. The lab was
then booted a second time with the final boot config (`no ip unreachables` included): Faults 1 and 3 showed the
same symptoms (the Fault 1 BGP, TCP, ACL and route output above is from the second run; its ping is from the
first), and all fixes were applied again, with a
resequence after Fault 1. The output below is from the second run.

**Captured** — after all fixes:
```
R1# show ip ospf neighbor
Neighbor ID     Pri   State           Dead Time   Address         Interface
10.255.255.2      1   FULL/DR         00:00:38    10.1.2.2        Ethernet0/0
R1# show ip bgp summary | begin Neighbor
Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
10.1.101.101    4        64511      16      18        5    0    0 00:02:03        2
R1# ping 198.51.100.10 repeat 2
!!
Success rate is 100 percent (2/2), round-trip min/avg/max = 1/1/1 ms
R1# traceroute 198.51.100.10 timeout 1 probe 1 ttl 1 3
  1 10.1.101.101 1 msec
  2 198.51.100.10 [AS 64511] 1 msec

PC1:~$ ping -c 2 -W 1 198.51.100.10       -> round-trip min/avg/max = 2.791/3.037/3.283 ms
PC1:~$ ping -c 3 -W 1 10.255.255.1        -> 3 packets transmitted, 3 packets received
PC1:~$ telnet 10.255.255.1                -> Connected to 10.255.255.1 / User Access Verification
PC1:~$ ssh cisco@10.255.255.1 (BatchMode) -> Permission denied (publickey,keyboard-interactive,password).
                                             (the session reached the login stage)
PC2:~$ ping -c 3 -W 1 10.1.101.1          -> 3 packets transmitted, 3 packets received
PC2:~$ telnet 10.1.101.1                  -> no answer (timeout)

R1# show access-lists IACL-IN
Extended IP access list IACL-IN
    10 permit tcp host 10.1.101.101 host 10.1.101.1 eq bgp
    20 permit tcp host 10.1.101.101 eq bgp host 10.1.101.1 (32 matches)
    30 permit icmp host 10.1.101.101 host 10.1.101.1 (2 matches)
    40 deny ip 10.0.0.0 0.255.255.255 any (27 matches)
    50 deny ip 172.16.0.0 0.15.255.255 any
    60 deny ip 192.168.0.0 0.0.255.255 any
    70 deny ip 127.0.0.0 0.255.255.255 any
    80 permit icmp any host 10.1.101.1 echo (6 matches)
    90 permit icmp any host 10.1.101.1 echo-reply (4 matches)
    100 permit icmp any host 10.1.101.1 unreachable (2 matches)
    110 permit icmp any host 10.1.101.1 time-exceeded
    120 deny ip any host 10.1.101.1 (7 matches)
    130 deny ip any host 10.255.255.1
    140 deny ip any 10.1.2.0 0.0.0.255
    150 permit ip any any (2 matches)

R1# show policy-map control-plane | include Class-map|conformed [0-9]
    Class-map: CM-ROUTING (match-all)
        conformed 103 packets, 8838 bytes; actions:
    Class-map: CM-MGMT (match-all)
        conformed 23 packets, 3093 bytes; actions:
    Class-map: CM-MONITOR (match-any)
        conformed 12 packets, 1152 bytes; actions:
    Class-map: CM-CATCHALL (match-all)
        conformed 7 packets, 518 bytes; actions:
    Class-map: class-default (match-any)
        conformed 40 packets, 11584 bytes; actions:
```
Line 40's 27 matches and CM-CATCHALL's 7 are left over from the Fault 1 and Fault 3 tests. Line 120's 7 matches
include PC2's telnet. The R2 refusal (`telnet 10.1.2.1 /source-interface Ethernet0/1` → `% Connection refused by
remote host`, logged as `%SEC-6-IPACCESSLOGS: list VTY-MGMT denied 192.168.10.1`) was captured in the first run;
VTY-MGMT wasn't touched by any fault.
