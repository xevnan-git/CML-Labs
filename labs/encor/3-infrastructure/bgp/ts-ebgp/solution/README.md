# eBGP Peering and Best Path — Solution (ts-ebgp)

> Spoilers below. Try the hints first, one at a time.

## Hints

<details><summary>Hint 1 — where to look</summary>

Everything is on R1 (the ISPs really are fine), but the ISPs' view is the fastest way to see what R1 is doing
wrong. Start with `show ip bgp summary` on R1, then `show logging` on R1, ISP1 and ISP2. Compare
`show running-config | section router bgp` on R1 line by line against the intended design and the ISP handoff
details (AS numbers, addresses, password).
</details>

<details><summary>Hint 2 — what to compare</summary>

- The two sessions are down for different reasons, and one of them is down for **two** reasons at once.
- One session's TCP connection never forms. Which address is R1 sourcing it from, and which address does ISP1
  expect?
- One ISP is logging something about TCP. What does that log message mean?
- Once a session is up, is the office LAN actually in R1's BGP table? `show ip bgp 192.168.10.0`.
- Once both sessions are up, which neighbor's routes have LocPrf 200?
</details>

<details><summary>Hint 3 — almost there</summary>

- For directly connected eBGP, the session must be sourced from the link address. The neighbor's `neighbor`
  statement names the address it will accept a connection from.
- A wrong `remote-as` shows up only *after* TCP works, as a NOTIFICATION with the peer's real AS in hex.
- MD5 passwords are case- and character-sensitive. Compare R1's against what the ISP2 NOC gave you.
- `network` advertises a prefix only when the routing table has it with *exactly* that mask.
- A route-map is only as right as the neighbor it's attached to.
</details>

## Faults
All five faults are on R1, in `router bgp 65001`. In the order a learner usually meets them:

### Fault 1: MD5 password mismatch toward ISP2
- **Where:** R1, neighbor 10.1.102.102.
- **Injected config:** `neighbor 10.1.102.102 password isp2-peer` (designed: `isp2peer`).
- **Why it breaks:** BGP MD5 is the TCP MD5 signature option. Each side signs every segment with its key and drops
  segments whose signature doesn't verify, so the TCP handshake never completes and BGP never sends an OPEN. No
  NOTIFICATION, just TCP log messages. Because both sides have *a* password, both log "Invalid MD5 digest". (With
  the password missing on one side, only the side that has one logs, and says "No MD5 digest".)
- **Evidence (Captured):**
  ```
  R1# show ip bgp summary | begin Neighbor
  Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
  10.1.101.101    4        64521       0       0        1    0    0 never    Idle
  10.1.102.102    4        64512       0       0        1    0    0 never    Active

  R1 console:
  %TCP-6-BADAUTH: Invalid MD5 digest from 10.1.102.102(46657) to 10.1.102.1(179) tableid - 0
  ```
- **Fix:**
  ```
  R1(config)# router bgp 65001
  R1(config-router)# neighbor 10.1.102.102 password isp2peer
  ```
  The session comes up on the next retry (≤ about a minute) with 5 prefixes. The office still can't reach the
  internet. That's Fault 2.

### Fault 2: `network` statement doesn't match the routing table
- **Where:** R1, `router bgp 65001`.
- **Injected config:** `network 192.168.0.0 mask 255.255.0.0` (designed: `network 192.168.10.0`, i.e. the /24).
- **Why it breaks:** BGP's `network` advertises a prefix only if the routing table holds that **exact**
  prefix/mask. R1 has the connected 192.168.10.0/24, not a /16, so nothing is originated. Nothing warns you about
  it. Outbound packets leave fine (R1 has internet routes from ISP2), but no ISP knows where 192.168.10.0/24 is,
  so replies are dropped upstream.
- **Evidence (Captured, with only the ISP2 session up):**
  ```
  R1# show ip bgp 192.168.10.0
  % Network not in table
  R1# show ip bgp neighbors 10.1.102.102 advertised-routes
  Total number of prefixes 0
  R1# show running-config | include network
   network 192.168.0.0 mask 255.255.0.0

  ISP3# show ip route 192.168.10.10
  % Network not in table

  PC1:~$ traceroute -n -q 1 -w 1 -m 4 198.51.100.1
   1  192.168.10.1  0.860 ms
   2  *
   3  *
   4  *
  ```
  (The hops time out because their replies, addressed to 192.168.10.10, have no route back.)
- **Fix:**
  ```
  R1(config)# router bgp 65001
  R1(config-router)# no network 192.168.0.0 mask 255.255.0.0
  R1(config-router)# network 192.168.10.0
  ```
  Now the office is online, **via ISP2**:
  ```
  PC1:~$ traceroute -n -q 1 -w 1 -m 4 198.51.100.1
   1  192.168.10.1  2.538 ms
   2  10.1.102.102  1.204 ms
   3  10.102.103.103  1.560 ms
  ```

### Fault 3: session to ISP1 sourced from Loopback0
- **Where:** R1, neighbor 10.1.101.101.
- **Injected config:** `neighbor 10.1.101.101 update-source Loopback0` (designed: not present).
- **Why it breaks:** R1 opens its TCP connection from 10.255.255.1. ISP1 only has a neighbor statement for
  10.1.101.1 (and no route to R1's loopback anyway), so it never accepts that connection. ISP1's own connection
  attempts arrive at 10.1.101.1, which doesn't match the source R1 is configured to use, so R1 closes them. The
  session cycles Idle/Active and never reaches OPEN, so the wrong AS (Fault 4) stays hidden.
  `update-source` on a loopback belongs with `ebgp-multihop` designs (or iBGP), not directly connected eBGP.
- **Evidence (Captured):**
  ```
  R1# show ip bgp neighbors 10.1.101.101 | include state|Connections|reset
    BGP state = Active, down for never
    Connections established 0; dropped 0
    Last reset never

  ISP1# show logging | include 10.1.101.1
  %BGP-5-NBR_RESET: Neighbor 10.1.101.1 active reset (Peer closed the session)
  %BGP-5-NBR_RESET: Neighbor 10.1.101.1 active reset (Peer closed the session)
  ```
- **Fix:**
  ```
  R1(config)# router bgp 65001
  R1(config-router)# no neighbor 10.1.101.101 update-source Loopback0
  ```

### Fault 4 (revealed by Fault 3's fix): wrong remote-as for ISP1
- **Where:** R1, neighbor 10.1.101.101.
- **Injected config:** `neighbor 10.1.101.101 remote-as 64521` (designed: `64511`; digits swapped).
- **Why it breaks:** once TCP works, ISP1's OPEN carries AS 64511. That doesn't match the configured 64521, so R1
  answers with NOTIFICATION 2/2 (OPEN message error / bad peer AS) and resets. The 2 data bytes are the AS the peer
  sent: 0xFBFF = 64511.
- **Evidence (Captured, right after Fault 3 was fixed):**
  ```
  R1# show logging | include BGP-3
  %BGP-3-NOTIFICATION: sent to neighbor 10.1.101.101 passive 2/2 (peer in wrong AS) 2 bytes FBFF
  %BGP-3-NOTIFICATION: sent to neighbor 10.1.101.101 active 2/2 (peer in wrong AS) 2 bytes FBFF
  R1# show ip bgp summary | begin Neighbor
  10.1.101.101    4        64521       2       2        1    0    0 00:00:04 Closing
  ```
- **Fix:**
  ```
  R1(config)# router bgp 65001
  R1(config-router)# neighbor 10.1.101.101 remote-as 64511
  ```
  ISP1 comes up with 5 prefixes, and traffic **still leaves via ISP2**. That's Fault 5.

### Fault 5: local-preference policy on the wrong neighbor
- **Where:** R1, inbound route-map.
- **Injected config:** `neighbor 10.1.102.102 route-map ISP1-IN in` (designed: on `10.1.101.101`).
- **Why it breaks:** `ISP1-IN` sets local-pref 200, and it's attached to ISP2. Local preference is step 2 of best-path
  selection, before AS-path length, so every ISP2 path wins, even for ISP1's own loopback, which is one hop away
  via ISP1. Inbound traffic is unaffected (the prepend toward ISP2 is correct), so the network is asymmetric: out via
  ISP2, back via ISP1.
- **Evidence (Captured, both sessions up):**
  ```
  R1# show ip bgp | begin Network
       Network          Next Hop            Metric LocPrf Weight Path
   *    10.255.255.101/32
                        10.1.101.101             0             0 64511 i
   *>                    10.1.102.102                  200      0 64512 64513 64511 i
   *    198.51.100.0     10.1.101.101                           0 64511 64513 i
   *>                    10.1.102.102                  200      0 64512 64513 i

  R1# show ip bgp 198.51.100.0 best-path-reason | include from|localpref|Evaluation
      10.1.101.101 from 10.1.101.101 (10.255.255.101)
        Origin IGP, localpref 100, valid, external
        Best Path Evaluation: Lower local preference
      10.1.102.102 from 10.1.102.102 (10.255.255.102)
        Origin IGP, localpref 200, valid, external, best
        Best Path Evaluation: Overall best path

  PC1:~$ traceroute -n -q 1 -w 1 -m 4 198.51.100.1
   1  192.168.10.1  1.448 ms
   2  10.1.102.102  1.502 ms
   3  10.102.103.103  1.133 ms
  ```
- **Fix:**
  ```
  R1(config)# router bgp 65001
  R1(config-router)# no neighbor 10.1.102.102 route-map ISP1-IN in
  R1(config-router)# neighbor 10.1.101.101 route-map ISP1-IN in
  R1(config-router)# end
  R1# clear ip bgp * soft in
  ```

## Why the ticket looked the way it did
At boot, both sessions are down (Faults 1, 3 and 4), so the office has no routes at all: "no internet". The
contractor was right that both links are up, since pings to 10.1.101.101 and 10.1.102.102 work. Fixing the ISP2
password alone isn't enough, because the LAN isn't advertised (Fault 2). With that fixed the office is online, but
on the per-gigabyte ISP. Fixing the ISP1 session takes two changes (Faults 3 and 4), and even then the
local-preference policy on the wrong neighbor (Fault 5) keeps outbound traffic on ISP2.

## Final configs
[`configs/`](configs/): the intended configuration of every node. Only R1 differs from what the lab boots with.

## Verifying the fix (Captured)
```
R1# show running-config | section router bgp
router bgp 65001
 bgp router-id 10.255.255.1
 bgp log-neighbor-changes
 network 192.168.10.0
 neighbor 10.1.101.101 remote-as 64511
 neighbor 10.1.101.101 description ISP1 (primary)
 neighbor 10.1.101.101 route-map ISP1-IN in
 neighbor 10.1.101.101 filter-list 1 out
 neighbor 10.1.102.102 remote-as 64512
 neighbor 10.1.102.102 description ISP2 (backup)
 neighbor 10.1.102.102 password isp2peer
 neighbor 10.1.102.102 route-map ISP2-OUT out
 neighbor 10.1.102.102 filter-list 1 out

R1# show ip bgp | begin Network
     Network          Next Hop            Metric LocPrf Weight Path
 *>   10.255.255.101/32
                      10.1.101.101             0    200      0 64511 i
 *                     10.1.102.102                           0 64512 64513 64511 i
 *>   10.255.255.102/32
                      10.1.101.101                  200      0 64511 64513 64512 i
 *                     10.1.102.102             0             0 64512 i
 *>   10.255.255.103/32
                      10.1.101.101                  200      0 64511 64513 i
 *                     10.1.102.102                           0 64512 64513 i
 *>   192.168.10.0     0.0.0.0                  0         32768 i
 *>   198.51.100.0     10.1.101.101                  200      0 64511 64513 i
 *                     10.1.102.102                           0 64512 64513 i
 *>   203.0.113.0      10.1.101.101                  200      0 64511 64513 i
 *                     10.1.102.102                           0 64512 64513 i

PC1:~$ ping -c 2 -W 1 203.0.113.1
64 bytes from 203.0.113.1: seq=0 ttl=42 time=2.007 ms
64 bytes from 203.0.113.1: seq=1 ttl=42 time=1.978 ms
2 packets transmitted, 2 packets received, 0% packet loss

PC1:~$ traceroute -n -q 1 -w 1 -m 4 198.51.100.1
 1  192.168.10.1  1.093 ms
 2  10.1.101.101  1.254 ms
 3  10.101.103.103  1.294 ms
```

**Expected** (not run in the TS lab under the 5-node limit; the same final config was captured in learn-ebgp):
- `PC1:~$ ping -c 3 198.51.100.10` succeeds, and `PC2:~$ traceroute -n 192.168.10.10` crosses 10.101.103.101 and
  10.1.101.1.
- `ISP3# show ip bgp 192.168.10.0`: best `64511 65001`, other `64512 65001 65001 65001 65001`.
- Failover: `R1(config)# interface Ethernet0/0` / `shutdown` moves PC1's traceroute to 10.1.102.102 within seconds.

## Testing notes
- Tested on the dev server (CML 2.10.1, IOL-XE 17.18.2) with R1, ISP1–3 and PC1 running. The faults were fixed in
  the order above, and every symptom was captured before its fix.
- R1's console log was checked after boot: no `% Invalid input`.
- After boot, R1 holds its BGP table without best paths for up to ~2 minutes (start-up read-only mode while ISP1
  never establishes). A learner who checks very early sees `*` without `>`. It sorts itself out, and it isn't a
  fault.
