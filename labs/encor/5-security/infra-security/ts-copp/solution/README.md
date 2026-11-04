# Control Plane Policing (CoPP) — Solution (ts-copp)

> Spoilers below. Try the hints first, one at a time.

## Hints

<details><summary>Hint 1 — where to look</summary>

Every fault is in R1's CoPP config; routing, addressing and the other routers are as designed. Your two best tools
are `show policy-map control-plane` (which class each packet landed in, and whether it was transmitted or
dropped) and `show access-lists` (which ACL line matched). Clear nothing; generate one test, then see which
counter moved. Start with routing, because nothing else can be tested until R1 has routes.
</details>

<details><summary>Hint 2 — what to compare</summary>

- The OSPF neighbor isn't *down*. What state is it in, and which OSPF packets does that state need?
- `show tcp brief` on R1 shows the BGP connection's state and ports. Which port do the packets R1 *receives*
  come from?
- The admins' sessions land in CM-CATCHALL. Read COPP-MGMT's lines carefully: which address is the source?
- Once logins reach CM-MGMT, Telnet works but SSH doesn't. Compare the exceeded byte count with the packet count.
- Pings to R1 don't count in CM-MONITOR at all. How many conditions must a packet meet to match that class?
</details>

<details><summary>Hint 3 — almost there</summary>

- OSPF hellos are multicast; the database exchange is unicast to the interface address.
- R1 opens the BGP session, so ISP1's replies come *from* port 179.
- In an extended ACL the first address is the source.
- A policer can't pass a packet bigger than its burst (`bc`).
- `match-all` with two different ACLs requires both to match.
</details>

## Faults
All five faults are on R1. In the order a learner usually meets them:

### Fault 1: OSPF matched only toward 224.0.0.5
- **Where:** R1, `ip access-list extended COPP-ROUTING`, line 10.
- **Injected config:** `10 permit ospf any host 224.0.0.5` (designed: `10 permit ospf any any`).
- **Why it breaks:** Hellos to 224.0.0.5 match CM-ROUTING, so the neighbor never times out. The DBD packets that
  start the database exchange are unicast to 10.1.2.1, match nothing in COPP-ROUTING, land in CM-CATCHALL and are
  dropped. Both routers sit in EXSTART. R1 learns no OSPF routes, so it has no route to the management LAN, and
  nothing on PC1 works.
- **Evidence (Captured):**
  ```
  R1# show ip ospf neighbor
  Neighbor ID     Pri   State           Dead Time   Address         Interface
  10.255.255.2      1   EXSTART/DR      00:00:33    10.1.2.2        Ethernet0/0
  R2# show ip ospf neighbor
  10.255.255.1      1   EXSTART/BDR     00:00:38    10.1.2.1        Ethernet0/0

  R1# show policy-map control-plane input class CM-CATCHALL | include conformed
          conformed 37 packets, 2674 bytes; actions:

  PC1:~$ ping -c 2 -W 1 198.51.100.10
  2 packets transmitted, 0 packets received, 100% packet loss
  ```
  Both interfaces are default Ethernet (MTU 1500, check with `show ip ospf interface Ethernet0/0`), which rules
  out the usual cause of EXSTART.
- **Fix:**
  ```
  R1(config)# ip access-list extended COPP-ROUTING
  R1(config-ext-nacl)# no 10
  R1(config-ext-nacl)# 10 permit ospf any any
  ```
  OSPF goes FULL within seconds. The internet is still down (Fault 2), and PC1 still can't log in to or ping R1
  (Faults 3 and 5).

### Fault 2: BGP replies (source port 179) not classified
- **Where:** R1, `COPP-ROUTING`.
- **Injected config:** line `30 permit tcp any eq bgp any` missing.
- **Why it breaks:** ISP1 is passive, so R1 always opens the session: R1's SYN goes *to* port 179, and ISP1's
  SYN-ACK comes *from* port 179 to R1's random port. Line 20 (`eq bgp` as destination) doesn't match it, so it
  falls into CM-CATCHALL and is dropped. R1 retries forever; the session never gets past TCP.
- **Evidence (Captured):**
  ```
  R1# show ip bgp summary | begin Neighbor
  Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
  10.1.101.101    4        64511       0       0        1    0    0 never    Active
  R1# show tcp brief
  TCB       Local Address               Foreign Address             (state)
  78AF9C0BAEC8  10.1.101.1.59061           10.1.101.101.179            SYNSENT
  ```
  (After Fault 1 was fixed the same session showed `Idle` between retries.)
- **Fix:**
  ```
  R1(config)# ip access-list extended COPP-ROUTING
  R1(config-ext-nacl)# 30 permit tcp any eq bgp any
  ```
  BGP is Established within about a minute and `PC1 ping 198.51.100.10` works.

### Fault 3: management ACL written backwards
- **Where:** R1, `ip access-list extended COPP-MGMT`, all four lines.
- **Injected config:** `permit tcp any 192.168.10.0 0.0.0.255 eq 22` (and `telnet`, `www`, `443`); designed:
  `permit tcp 192.168.10.0 0.0.0.255 any eq 22` etc.
- **Why it breaks:** In an extended ACL the first address is the **source**. As written, the lines match sessions
  *to* the management LAN, which never terminate on R1. The admins' SYNs to R1 match nothing in CM-MGMT, fall
  into CM-CATCHALL and are dropped. Their sessions just time out.
- **Evidence (Captured, after Faults 1 and 2):**
  ```
  PC1:~$ telnet 10.255.255.1
  (no answer; timeout)
  R1# show access-lists COPP-MGMT
  Extended IP access list COPP-MGMT
      10 permit tcp any 192.168.10.0 0.0.0.255 eq 22
      20 permit tcp any 192.168.10.0 0.0.0.255 eq telnet
      30 permit tcp any 192.168.10.0 0.0.0.255 eq www
      40 permit tcp any 192.168.10.0 0.0.0.255 eq 443
  ```
- **Fix:**
  ```
  R1(config)# no ip access-list extended COPP-MGMT
  R1(config)# ip access-list extended COPP-MGMT
  R1(config-ext-nacl)# 10 permit tcp 192.168.10.0 0.0.0.255 any eq 22
  R1(config-ext-nacl)# 20 permit tcp 192.168.10.0 0.0.0.255 any eq telnet
  R1(config-ext-nacl)# 30 permit tcp 192.168.10.0 0.0.0.255 any eq www
  R1(config-ext-nacl)# 40 permit tcp 192.168.10.0 0.0.0.255 any eq 443
  ```
  Telnet from PC1 now works. SSH doesn't: Fault 4.

### Fault 4: management class policed at 32 kbps
- **Where:** R1, `policy-map PM-COPP`, class CM-MGMT.
- **Injected config:** `police 32000 conform-action transmit exceed-action drop` (designed: `police 256000 …`).
- **Why it breaks:** At 32 kbps IOS sizes the burst (`bc`) at 1500 bytes. A full-size 1514-byte frame can never fit
  in a 1500-byte bucket, so it always exceeds and is dropped. The SSH key exchange uses full-size packets; Telnet
  doesn't. Result: Telnet works, SSH hangs before the password prompt, every time.
- **Evidence (Captured, after Fault 3):**
  ```
  PC1:~$ telnet 10.255.255.1               -> Connected to 10.255.255.1
  PC1:~$ ssh cisco@10.255.255.1            -> hangs (2 of 2 tries)

  R1# show policy-map control-plane input class CM-MGMT
        police:
            cir 32000 bps, bc 1500 bytes
          conformed 18 packets, 1294 bytes; actions:
            transmit
          exceeded 18 packets, 27252 bytes; actions:
            drop
  ```
  27252 / 18 = 1514 bytes per exceeded packet.
- **Fix:**
  ```
  R1(config)# policy-map PM-COPP
  R1(config-pmap)# class CM-MGMT
  R1(config-pmap-c)# police 256000 conform-action transmit exceed-action drop
  ```

### Fault 5: CM-MONITOR is `match-all`
- **Where:** R1, `class-map CM-MONITOR`.
- **Injected config:** `class-map match-all CM-MONITOR` (designed: `match-any`).
- **Why it breaks:** The class has two `match` lines, COPP-SNMP and COPP-ICMP. `match-all` requires a packet to
  match both: be SNMP and ICMP at once. Nothing can, so the class never matches; pings to R1 fall into
  CM-CATCHALL and are dropped. Pings *through* R1 are transit traffic and unaffected.
- **Evidence (Captured, after Faults 1–4):**
  ```
  PC1:~$ ping -c 2 -W 1 10.255.255.1
  2 packets transmitted, 0 packets received, 100% packet loss
  PC1:~$ ping -c 2 -W 1 198.51.100.10      -> works

  R1# show policy-map control-plane input class CM-MONITOR
      Class-map: CM-MONITOR (match-all)
        Match: access-group name COPP-SNMP
        Match: access-group name COPP-ICMP
        police:
            cir 16000 bps, bc 1500 bytes
          conformed 0 packets, 0 bytes; actions:
  ```
- **Fix:** IOS accepts the type change in place, even while the policy uses the class:
  ```
  R1(config)# class-map match-any CM-MONITOR
  ```

## Final configs
`configs/<node>.cfg` — the complete working configuration of every node (the intended design). Only R1 differs
from the boot config. The PC files are the Alpine boot scripts.

## Verification
All five faults were injected together and confirmed on the dev server (5 licensed nodes, the whole lab), then
fixed in order 1 → 5.

**Captured** — after all fixes:
```
R1# show ip ospf neighbor
Neighbor ID     Pri   State           Dead Time   Address         Interface
10.255.255.2      1   FULL/DR         00:00:35    10.1.2.2        Ethernet0/0
R1# show ip bgp summary | begin Neighbor
Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
10.1.101.101    4        64511      35      35        5    0    0 00:05:04        2

PC1:~$ ping -c 3 -W 1 10.255.255.1        -> round-trip min/avg/max = 2.356/2.779/3.574 ms
PC1:~$ ping -c 2 -W 1 10.1.2.1            -> round-trip min/avg/max = 1.132/2.207/3.282 ms
PC1:~$ telnet 10.255.255.1                -> Connected to 10.255.255.1
PC1:~$ ssh cisco@10.255.255.1 (BatchMode) -> Permission denied (publickey,keyboard-interactive,password).
                                             (the session reached the login stage)
PC1:~$ ping -c 2 -W 1 198.51.100.10       -> round-trip min/avg/max = 4.563/4.622/4.682 ms
PC2:~$ telnet 10.1.101.1                  -> no answer (timeout)
PC2:~$ ping -c 2 -W 1 10.1.101.1          -> round-trip min/avg/max = 2.721/3.412/4.103 ms

R1# show policy-map control-plane | include Class-map|conformed [0-9]|exceeded [0-9]
    Class-map: CM-ROUTING (match-all)
        conformed 133 packets, 11951 bytes; actions:
    Class-map: CM-MGMT (match-all)
        conformed 42 packets, 4398 bytes; actions:
        exceeded 20 packets, 30280 bytes; actions:
    Class-map: CM-MONITOR (match-any)
        conformed 7 packets, 686 bytes; actions:
    Class-map: CM-CATCHALL (match-all)
        conformed 82 packets, 5958 bytes; actions:
    Class-map: class-default (match-any)
        conformed 49 packets, 15237 bytes; actions:
```
CM-MGMT's exceeded counter is left over from the Fault 4 tests; it doesn't grow once the rate is 256 kbps.
