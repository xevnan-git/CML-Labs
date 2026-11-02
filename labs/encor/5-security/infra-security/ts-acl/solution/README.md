# ACLs — Solution (ts-acl)

> Spoilers below. Try the hints first, one at a time.

## Hints

<details><summary>Hint 1 — where to look</summary>

Start with routing: nothing else can be tested while the branch has no routes to HQ. Then work through the "Done
when" list one source at a time. On R1, `show logging | include SEC-6` and `show access-lists` (hit counters) tell
you which ACL, and which line, is dropping a test. `show ip interface Ethernet0/x | include access list` shows
where each ACL is applied, and in which direction.
</details>

<details><summary>Hint 2 — what to compare</summary>

- Which protocol does R1 need to receive from R2 before anything else can work? Is it permitted?
- The contractors can't even ping their own gateway. Check the *direction* `CONTRACTORS-IN` is applied in, and think
  about which source address the traffic it sees will have.
- Contractor web requests leave fine but never complete. Where do the replies enter R1, and which line should
  permit them? Check its wildcard mask.
- Is there a line permitting contractor pings to SRV1? Is it reachable, given first-match?
- Compare R2's `VTY-ADMIN` with R1's in `show access-lists`. Does IOS display the line the way you'd expect?
</details>

<details><summary>Hint 3 — almost there</summary>

- An inbound ACL filters routing protocol packets addressed to the router too.
- A subnet mask typed where a wildcard mask belongs matches something very different.
- `0.0.0.255` covers one /24; covering 192.168.10.0 *and* 192.168.11.0 needs `0.0.1.255`.
- A line appended without a sequence number goes to the end, after any broader line that already matched.
</details>

## Faults
Faults 1–4 are on R1, Fault 5 is on R2. In the order a learner usually meets them:

### Fault 1: `BRANCH-IN` doesn't permit OSPF
- **Where:** R1, `ip access-list extended BRANCH-IN` (inbound on Ethernet0/0).
- **Injected config:** line `10 permit ospf any any` missing.
- **Why it breaks:** An inbound ACL filters every packet arriving on the interface, including OSPF hellos sent to
  224.0.0.5 and R1's own address. They hit `40 deny ip any any log`, so R1 never hears R2 and the adjacency never
  forms. R2 sees R1's hellos without its own router ID in them, so it stays in INIT. With no OSPF routes, the
  branch can't reach HQ at all.
- **Evidence (Captured):**
  ```
  R1# show ip ospf neighbor
  (empty)
  R1# show logging | include IPACCESSLOG
  %SEC-6-IPACCESSLOGRP: list BRANCH-IN denied ospf 10.1.2.2 -> 224.0.0.5, 1 packet
  %SEC-6-IPACCESSLOGRP: list BRANCH-IN denied ospf 10.1.2.2 -> 10.1.2.1, 1 packet
  R1# show access-lists BRANCH-IN
  Extended IP access list BRANCH-IN
      20 permit tcp any 192.168.10.0 0.0.0.255 established
      30 permit icmp any any
      40 deny ip any any log (12 matches)

  R2# show ip ospf neighbor
  Neighbor ID     Pri   State           Dead Time   Address         Interface
  10.255.255.1      1   INIT/DROTHER    00:00:38    10.1.2.1        Ethernet0/0

  PC1:~$ wget -q -T 3 -O - http://192.168.50.10/
  wget: can't connect to remote host (192.168.50.10): Host is unreachable
  ```
- **Fix:**
  ```
  R1(config)# ip access-list extended BRANCH-IN
  R1(config-ext-nacl)# 10 permit ospf any any
  ```
  OSPF goes FULL within seconds and staff can reach SRV1. Contractors still have nothing: Fault 2. Staff still
  can't log in to R2: Fault 5.

### Fault 2: `CONTRACTORS-IN` applied outbound
- **Where:** R1, interface Ethernet0/2.
- **Injected config:** `ip access-group CONTRACTORS-IN out` (designed: `in`).
- **Why it breaks:** Every line of `CONTRACTORS-IN` matches a **source** of 192.168.11.0/24. Traffic leaving
  e0/2 toward PC2 has some *other* source (SRV1, R2, R1), so it matches nothing and hits the implicit deny. All
  replies to the contractors are dropped. On IOL-XE the outbound implicit deny also drops R1's own packets out
  of e0/2, including its ARP replies: `show interfaces Ethernet0/2` shows **0 packets output**, and PC2 can't
  resolve its gateway at all (`ip neigh` shows FAILED). Don't count on that last part on other platforms, where
  the router's own traffic usually bypasses an outbound ACL. The empty hit counters are a clue too: the
  contractors' traffic never reaches a line it was written for.
- **Evidence (Captured):**
  ```
  PC2:~$ ping -c 2 -W 1 192.168.11.1
  2 packets transmitted, 0 packets received, 100% packet loss
  PC2:~$ ip neigh
  192.168.11.1 dev eth0  used 0/0/0 probes 6 FAILED

  R1# show ip interface Ethernet0/2 | include access list is
    Outgoing access list is CONTRACTORS-IN
    Inbound  access list is not set
  R1# show interfaces Ethernet0/2 | include packets output
       0 packets output, 0 bytes, 0 underruns
  R1# show access-lists CONTRACTORS-IN
  Extended IP access list CONTRACTORS-IN
      10 permit tcp 192.168.11.0 0.0.0.255 host 192.168.50.10 eq www
      30 deny ip 192.168.11.0 0.0.0.255 192.168.50.0 0.0.0.255 log
      40 permit ip 192.168.11.0 0.0.0.255 any
      50 permit icmp 192.168.11.0 0.0.0.255 host 192.168.50.10 echo
  ```
- **Fix:**
  ```
  R1(config)# interface Ethernet0/2
  R1(config-if)# no ip access-group CONTRACTORS-IN out
  R1(config-if)# ip access-group CONTRACTORS-IN in
  ```
  PC2 now reaches its gateway and 172.18.0.1, but neither web nor ping to SRV1 works: Faults 3 and 4.

### Fault 3: `established` line covers VLAN 10 only
- **Where:** R1, `BRANCH-IN` line 20.
- **Injected config:** `20 permit tcp any 192.168.10.0 0.0.0.255 established` (designed: wildcard `0.0.1.255`).
- **Why it breaks:** The contractors' SYN to SRV1 port 80 is permitted outbound by `CONTRACTORS-IN` line 10, but
  SRV1's SYN-ACK comes back in through `BRANCH-IN`. With `0.0.0.255` the established line only matches
  192.168.10.x, so the reply to 192.168.11.10 falls to `deny ip any any log`. Staff are unaffected, and
  contractor pings are blocked for a different reason (Fault 4), so fix them one at a time.
- **Evidence (Captured, after Fault 2 was fixed):**
  ```
  PC2:~$ wget -q -T 5 -O - http://192.168.50.10/
  wget: download timed out

  R1# show logging | include BRANCH-IN denied tcp
  %SEC-6-IPACCESSLOGP: list BRANCH-IN denied tcp 192.168.50.10(80) -> 192.168.11.10(44634), 1 packet
  R1# show access-lists CONTRACTORS-IN | include www
      10 permit tcp 192.168.11.0 0.0.0.255 host 192.168.50.10 eq www (5 matches)
  ```
  The request matched (line 10 has hits); the reply from port 80 was denied on the way back.
- **Fix:**
  ```
  R1(config)# ip access-list extended BRANCH-IN
  R1(config-ext-nacl)# no 20
  R1(config-ext-nacl)# 20 permit tcp any 192.168.10.0 0.0.1.255 established
  ```

### Fault 4: contractor ping line is below the deny
- **Where:** R1, `CONTRACTORS-IN`.
- **Injected config:** the ICMP permit was appended as line 50, after `30 deny ip … 192.168.50.0 … log` and
  `40 permit ip … any` (designed: line 20, before the deny).
- **Why it breaks:** ACLs stop at the first match. A contractor ping to SRV1 matches line 30 and is denied; line 50
  is never reached (and never could be: line 40 would catch anything line 30 didn't).
- **Evidence (Captured, after Fault 2 was fixed):**
  ```
  PC2:~$ ping -c 2 -W 1 192.168.50.10
  2 packets transmitted, 0 packets received, 100% packet loss

  R1# show logging | include CONTRACTORS-IN
  %SEC-6-IPACCESSLOGDP: list CONTRACTORS-IN denied icmp 192.168.11.10 -> 192.168.50.10 (8/0), 1 packet
  R1# show access-lists CONTRACTORS-IN
  Extended IP access list CONTRACTORS-IN
      10 permit tcp 192.168.11.0 0.0.0.255 host 192.168.50.10 eq www (5 matches)
      30 deny ip 192.168.11.0 0.0.0.255 192.168.50.0 0.0.0.255 log (2 matches)
      40 permit ip 192.168.11.0 0.0.0.255 any (8 matches)
      50 permit icmp 192.168.11.0 0.0.0.255 host 192.168.50.10 echo
  ```
- **Fix:**
  ```
  R1(config)# ip access-list extended CONTRACTORS-IN
  R1(config-ext-nacl)# no 50
  R1(config-ext-nacl)# 20 permit icmp 192.168.11.0 0.0.0.255 host 192.168.50.10 echo
  ```

### Fault 5: R2 `VTY-ADMIN` uses a subnet mask instead of a wildcard
- **Where:** R2, `ip access-list standard VTY-ADMIN` (applied with `access-class` on vty 0–4).
- **Injected config:** `10 permit 192.168.10.0 255.255.255.0` (designed: `0.0.0.255`).
- **Why it breaks:** In an ACL the second field is a wildcard: 1 bits are "don't care". `255.255.255.0` means
  "ignore the first three octets, the last octet must be 0". IOS stores it that way, as
  `0.0.0.0, wildcard bits 255.255.255.0`: any address ending in `.0`. PC1 (192.168.10.10) doesn't match, so its
  sessions hit the implicit deny and are refused. R1 has the correct line, so R1 logins work, which makes it
  easy to compare the two.
- **Evidence (Captured):**
  ```
  PC1:~$ telnet 10.255.255.2
  telnet: can't connect to remote host (10.255.255.2): Connection refused
  PC1:~$ telnet 10.255.255.1
  Connected to 10.255.255.1

  R2# show access-lists VTY-ADMIN
  Standard IP access list VTY-ADMIN
      10 permit 0.0.0.0, wildcard bits 255.255.255.0
  ```
- **Fix:**
  ```
  R2(config)# ip access-list standard VTY-ADMIN
  R2(config-std-nacl)# no 10
  R2(config-std-nacl)# 10 permit 192.168.10.0 0.0.0.255
  ```

## Final configs
`configs/<node>.cfg` — the complete working configuration of every node (the intended design). The PC/SRV files
are the Alpine boot scripts.

## Verification
All five faults were injected together and confirmed on the dev server (5 licensed nodes, the whole lab), then
fixed in order 1 → 5.

**Captured** — after all fixes:
```
R1# show ip ospf neighbor
Neighbor ID     Pri   State           Dead Time   Address         Interface
10.255.255.2      1   FULL/DR         00:00:32    10.1.2.2        Ethernet0/0

PC1:~$ telnet 10.255.255.2                        -> Connected to 10.255.255.2
PC1:~$ ssh cisco@10.255.255.2 (BatchMode)         -> Permission denied (publickey,keyboard-interactive,password).
                                                     (the session reached the login stage)
PC1:~$ nc -zv -w 3 192.168.50.10 22               -> 192.168.50.10 (192.168.50.10:22) open
PC1:~$ wget -q -T 3 -O - http://192.168.50.10/    -> <h1>SRV1 intranet</h1>

PC2:~$ ping -c 2 -W 1 192.168.50.10               -> round-trip min/avg/max = 1.860/1.922/1.985 ms
PC2:~$ wget -q -T 5 -O - http://192.168.50.10/    -> <h1>SRV1 intranet</h1>
PC2:~$ nc -zv -w 3 192.168.50.10 22               -> nc: 192.168.50.10 (192.168.50.10:22): Host is unreachable
PC2:~$ telnet 10.255.255.2                        -> Connection refused
PC2:~$ telnet 10.255.255.1                        -> Connection refused

SRV1:~$ nc -zv -w 3 192.168.10.10 22              -> nc: 192.168.10.10 (192.168.10.10:22): Host is unreachable
SRV1:~$ nc -zv -w 3 192.168.11.10 22              -> nc: 192.168.11.10 (192.168.11.10:22): Host is unreachable
SRV1:~$ ping -c 1 -W 1 192.168.10.10              -> round-trip min/avg/max = 1.347/1.347/1.347 ms
```
`PC2 ping -c 2 172.18.0.1` was captured working right after the Fault 2 fix, before Faults 3–5 were fixed (none of
which touch that path).
