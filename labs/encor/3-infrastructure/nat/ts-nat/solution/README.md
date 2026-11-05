# NAT and PAT — Solution (ts-nat)

> Spoilers below. Try the hints first, one at a time.

## Hints

<details><summary>Hint 1 — where to look</summary>

ISP1, the hosts and the routing are fine; all five faults are in R1's NAT configuration. Your best tools are
`show ip nat statistics` (which interfaces are inside/outside, the pool, allocated %, **misses**),
`show ip nat translations`, `show ip access-lists` (NAT-INSIDE and OUTSIDE-IN count matches) and `debug ip nat`.
Test from both ends: PC1 → 192.0.2.10 and PC2 → 198.51.100.14 (port 80 and 2222).
</details>

<details><summary>Hint 2 — what to compare</summary>

- Which interfaces does `show ip nat statistics` call inside and outside? Compare with the design.
- PC1 gets no translation at all, while SRV1 does. Which line of NAT-INSIDE should match 192.168.10.10?
- The pool is 100% allocated and the misses counter rises every time PC1 pings. What's missing from the
  `ip nat inside source list` line?
- PC1 is translated now, but nothing comes back. Which public block does ISP1 route to R1, and which address does
  R1 translate to?
- PC2's wget is refused (not timed out) while port 2222 works. Compare the two static lines.
</details>

<details><summary>Hint 3 — almost there</summary>

- `ip nat inside source` translates packets going from an inside interface to an outside one.
- A wildcard of 0.0.0.7 covers eight addresses.
- Without `overload`, one pool address serves one inside host.
- The `prefix-length` on a pool is only a sanity check; it doesn't prove the ISP routes the address to you.
- "Connection refused" means a TCP reset came back: the packet got to a host, but nothing listened on that port.
- IOS refuses to change a dynamic mapping, or remove a static one, while translations depend on it. In
  configuration mode, `do clear ip nat translation *` and then the change, right after it.
</details>

## Faults
All five are on R1. In the order a learner usually meets them, following PC1's traffic (Fault 5 is visible from
PC2 as soon as Fault 1 is fixed):

### Fault 1: inside and outside swapped on e0/0 and e0/2
- **Where:** R1, Ethernet0/0 and Ethernet0/2.
- **Injected config:** e0/0 `ip nat outside`, e0/2 `ip nat inside` (designed: e0/0 inside, e0/2 outside; e0/1
  is correctly inside).
- **Why it breaks:** NAT translates only between an inside and an outside interface. With e0/2 marked inside,
  traffic from e0/1 to the ISP goes inside → inside and isn't translated. PC1's traffic goes outside → inside, the
  wrong direction for `ip nat inside source`. Nothing is translated and no dynamic entries appear. Inbound traffic
  from PC2 to 198.51.100.14 arrives on an *inside* interface, isn't untranslated, and loops between R1's default
  route and ISP1's route for the /28 until its TTL runs out.
- **Evidence (Captured):**
  ```
  PC1$ ping -c 2 -W 1 192.0.2.10
  2 packets transmitted, 0 packets received, 100% packet loss
  PC2$ wget -T 3 -O - http://198.51.100.14/
  wget: can't connect to remote host (198.51.100.14): Host is unreachable

  R1# show ip nat statistics
  Total active translations: 2 (2 static, 0 dynamic; 2 extended)
  Outside interfaces:
    Ethernet0/0
  Inside interfaces:
    Ethernet0/1, Ethernet0/2
  Hits: 0  Misses: 0
  R1# show ip route 198.51.100.14
  % Network not in table
  ```
- **Fix:**
  ```
  R1(config)# interface Ethernet0/0
  R1(config-if)# ip nat inside
  R1(config-if)# interface Ethernet0/2
  R1(config-if)# ip nat outside
  ```
  SRV1's monitoring pings are translated within 10 seconds. PC1 still fails (Fault 2), and PC2's wget changes to
  `Connection refused` (Fault 5), while `nc 198.51.100.14 2222` now returns the SSH banner.

### Fault 2: NAT-INSIDE's staff line is a /29
- **Where:** R1, `ip access-list standard NAT-INSIDE`, line 10.
- **Injected config:** `10 permit 192.168.10.0 0.0.0.7` (designed: `0.0.0.255`).
- **Why it breaks:** 0.0.0.7 matches only 192.168.10.0–.7. PC1 is .10, so it never matches NAT-INSIDE, isn't
  translated, and leaves with its private address, which ISP1 can't route back.
- **Evidence (Captured, after Fault 1):**
  ```
  R1# show ip access-lists NAT-INSIDE
  Standard IP access list NAT-INSIDE
      10 permit 192.168.10.0, wildcard bits 0.0.0.7
      20 permit 192.168.20.0, wildcard bits 0.0.0.255 (1 match)
  R1# show ip nat translations | include 192.168.10
  R1#
  R1# show ip nat statistics | include allocated
          type generic, total addresses 1, allocated 1 (100%), misses 0
  ```
  SRV1 (line 20) is translated; PC1 has no entry, and the pool's misses counter doesn't move: PC1 never even asked
  for an address.
- **Fix:**
  ```
  R1(config)# ip access-list standard NAT-INSIDE
  R1(config-std-nacl)# no 10
  R1(config-std-nacl)# 10 permit 192.168.10.0 0.0.0.255
  ```

### Fault 3: the one-address pool has no `overload`
- **Where:** R1, `ip nat inside source list NAT-INSIDE pool NAT-POOL`.
- **Injected config:** `overload` missing.
- **Why it breaks:** without overload, each inside host takes a whole pool address. The pool has one, and SRV1's
  monitoring ping holds it permanently (the entry is refreshed every 10 seconds). PC1 matches the ACL but finds
  no free address, so its packets are dropped as **misses**.
- **Evidence (Captured, after Fault 2):**
  ```
  PC1$ ping -c 2 -W 1 192.0.2.10
  2 packets transmitted, 0 packets received, 100% packet loss
  R1# show ip nat statistics | include allocated|misses|Hits|overload
  Hits: 28  Misses: 0
   Dynamic overload mapping configured: 0
          type generic, total addresses 1, allocated 1 (100%), misses 2
  R1# show ip nat translations | include ---
  tcp 198.51.100.14:2222 192.168.20.10:22   ---                ---
  tcp 198.51.100.14:80   192.168.20.10:8080 ---                ---
  --- 198.51.100.17      192.168.20.10      ---                ---
  ```
  The two misses are PC1's two pings. The last line is SRV1 owning the only address.
- **Fix:** IOS won't change the mapping while it has translations, and SRV1 re-creates one within seconds:
  ```
  R1(config)# ip nat inside source list NAT-INSIDE pool NAT-POOL overload
  %Dynamic mapping in use, cannot change
  ```
  Clear and change in the same configuration session:
  ```
  R1(config)# do clear ip nat translation *
  R1(config)# ip nat inside source list NAT-INSIDE pool NAT-POOL overload
  ```

### Fault 4: the pool address isn't in the company's public block
- **Where:** R1, `ip nat pool NAT-POOL`.
- **Injected config:** `ip nat pool NAT-POOL 198.51.100.17 198.51.100.17 prefix-length 28` (designed:
  198.51.100.1).
- **Why it breaks:** ISP1 routes only 198.51.100.0/28 (.0–.15) to R1. R1 now translates PC1 correctly, but to
  .17, and ISP1 has no route for the replies. The `prefix-length 28` check passes because .17 is a valid address
  in 198.51.100.16/28, a different block.
- **Evidence (Captured, after Fault 3):**
  ```
  PC1$ ping -c 2 -W 1 192.0.2.10
  2 packets transmitted, 0 packets received, 100% packet loss
  R1# show ip nat translations
  Pro Inside global      Inside local       Outside local      Outside global
  icmp 198.51.100.17:1025 192.168.10.10:64572 192.0.2.10:64572 192.0.2.10:1025
  tcp 198.51.100.14:2222 192.168.20.10:22   ---                ---
  icmp 198.51.100.17:1024 192.168.20.10:2228 192.0.2.10:2228   192.0.2.10:1024
  tcp 198.51.100.14:80   192.168.20.10:8080 ---                ---
  ISP1# show ip route 198.51.100.17
  % Subnet not in table
  ISP1# show ip route static | include 198
        198.51.100.0/28 is subnetted, 1 subnets
  S        198.51.100.0 [1/0] via 203.0.113.1
  ```
  PAT works now (both hosts on one address, different ports), but on the wrong address.
- **Fix:**
  ```
  R1(config)# do clear ip nat translation *
  R1(config)# ip nat pool NAT-POOL 198.51.100.1 198.51.100.1 prefix-length 28
  ```
  PC1's ping now gets replies.

### Fault 5: the web port forward points to port 8080
- **Where:** R1, the static entry for public port 80.
- **Injected config:** `ip nat inside source static tcp 192.168.20.10 8080 198.51.100.14 80 extendable`
  (designed: inside port 80).
- **Why it breaks:** R1 forwards PC2's connection to SRV1 port 8080, where nothing listens. SRV1 answers with a
  TCP reset. The SSH forward (2222 → 22) is correct, which is why it works.
- **Evidence (Captured, after Fault 1):**
  ```
  PC2$ wget -T 3 -O - http://198.51.100.14/
  wget: can't connect to remote host (198.51.100.14): Connection refused
  PC2$ nc -w 3 198.51.100.14 2222 </dev/null
  SSH-2.0-OpenSSH_10.2
  R1# show ip nat translations | include :80
  tcp 198.51.100.14:80   192.168.20.10:8080 ---                ---
  ```
  OUTSIDE-IN is not the problem: a reset means the SYN got through R1 to SRV1. A denied packet gets
  `Host is unreachable` instead.
- **Fix:**
  ```
  R1(config)# no ip nat inside source static tcp 192.168.20.10 8080 198.51.100.14 80 extendable
  R1(config)# ip nat inside source static tcp 192.168.20.10 80 198.51.100.14 80 extendable
  ```

## Verification after all fixes (Captured)
```
PC1$ ping -c 2 -W 1 192.0.2.10
64 bytes from 192.0.2.10: seq=0 ttl=42 time=1.838 ms
64 bytes from 192.0.2.10: seq=1 ttl=42 time=5.242 ms
PC2$ wget -T 3 -O - http://198.51.100.14/
<h1>SRV1 public web server</h1>
PC2$ nc -w 3 198.51.100.14 2222 </dev/null
SSH-2.0-OpenSSH_10.2

R1# show ip nat translations
Pro Inside global      Inside local       Outside local      Outside global
tcp 198.51.100.14:2222 192.168.20.10:22   192.0.2.10:46135   192.0.2.10:46135
tcp 198.51.100.14:2222 192.168.20.10:22   ---                ---
tcp 198.51.100.14:80   192.168.20.10:80   192.0.2.10:37074   192.0.2.10:37074
tcp 198.51.100.14:80   192.168.20.10:80   ---                ---
icmp 198.51.100.1:1024 192.168.20.10:2260 192.0.2.10:2260    192.0.2.10:1024
icmp 198.51.100.1:1025 192.168.20.10:2263 192.0.2.10:2263    192.0.2.10:1025

R1# show ip nat statistics
Total active translations: 10 (2 static, 8 dynamic; 10 extended)
Outside interfaces:
  Ethernet0/2
Inside interfaces:
  Ethernet0/0, Ethernet0/1
Hits: 97  Misses: 0
 Dynamic overload mapping configured: 1
 pool NAT-POOL: id 1, netmask 255.255.255.240
        start 198.51.100.1 end 198.51.100.1
        type generic, total addresses 1, allocated 1 (100%), misses 0

R1# show ip access-lists
Standard IP access list NAT-INSIDE
    10 permit 192.168.10.0, wildcard bits 0.0.0.255 (6 matches)
    20 permit 192.168.20.0, wildcard bits 0.0.0.255 (22 matches)
Extended IP access list OUTSIDE-IN
    10 permit tcp any host 198.51.100.14 eq www (38 matches)
    20 permit tcp any host 198.51.100.14 eq 2222 (42 matches)
    30 permit icmp any any (141 matches)
    40 permit tcp any any established
    50 deny ip any any
```
PC1's translation (198.51.100.1 with its own port) appears while PC1 is pinging; the snapshot above was taken
between pings.

## How this was tested
On the dev server, CML 2.10.1, IOL-XE 17.18.2, Alpine 3.23, whole lab (5 licensed nodes), booted with the faulted
configs. Each symptom was confirmed live, then fixed in the order above. Notes:
- All faulted lines were accepted at boot (no `% Invalid input` in the console log).
- With Fault 1 in place, OUTSIDE-IN lines 10 and 20 counted 32 matches each from a single wget/nc attempt: the
  untranslated packets looped between R1 and ISP1 and passed the ACL on every lap.
- The pool redefinition (Fault 4) was done after `do clear ip nat translation *` in the same session; the
  behaviour without the clear wasn't tested.
