# NTP — Solution (ts-ntp)

> Spoilers below. Try the hints first, one at a time.

## Hints

<details><summary>Hint 1 — where to look</summary>

NTP1, addressing and OSPF are as designed; the faults are in R1's, R2's and R3's NTP config. Work top down:
nothing below R1 can synchronize until R1 does. Your best tools are `show ntp associations` (the **reach** column
and the `*` for the chosen server), `show ntp associations detail` (packet in/out/error counters per
association), `show logging | include NTP`, `show ip access-lists` (R1's NTP ACLs count matches) and
`debug ntp packet`.
</details>

<details><summary>Hint 2 — what to compare</summary>

- R1 sends to NTP1 and gets replies, but counts them as errors. What does the log say about them?
- R1's NTP-CLIENTS ACL: which addresses does it list, and which address does each client send NTP from?
- One router never sends a single NTP packet (`assoc out packets 0`). Read its log and its NTP config: which of
  the four authentication commands is missing?
- R3's packets leave, but nothing comes back. From which address does R3 send them, and can R1 or R2 reach that
  address?
- Read R3's `ntp server` line closely. Whose address is that?
</details>

<details><summary>Hint 3 — almost there</summary>

- A crypto-NAK means the other side couldn't verify your key: the key strings differ. In the running config
  the key is stored as type 7, which encrypts the same string differently each time, so retype it rather than
  compare.
- `ntp access-group` matches the NTP **source** address of the client, which here is its Loopback0.
- With `ntp authenticate`, a key that isn't listed in `ntp trusted-key` can't be used, and IOS-XE doesn't even
  send packets to a server configured with it.
- `ntp source` must be an address the server can route back to.
- A router can't get time from itself.
</details>

## Faults
Two faults on R1, one on R2, two on R3. In the order a learner usually meets them, top down:

### Fault 1: R1's key 1 doesn't match NTP1's
- **Where:** R1, `ntp authentication-key 1`.
- **Injected config:** `ntp authentication-key 1 md5 NTPsecret1` (designed: `NTPsecret`).
- **Why it breaks:** R1 signs its requests with key 1. NTP1 can't verify the digest and answers with a
  crypto-NAK instead of time. R1 never synchronizes, so it has no time to give R2 and R3 either.
- **Evidence (Captured):**
  ```
  R1# show ntp associations
    address         ref clock       st   when   poll reach  delay  offset   disp
   ~10.255.255.100  .INIT.          16      -     64     0  0.000   0.000 15937.

  R1# show ntp associations detail
  10.255.255.100 configured, ipv4, authenticated (' ' reject), authtype (md5), insane, invalid, unsynced, stratum 16
  assoc in packets 0, assoc out packets 3, assoc error packets 0

  R1# show logging | include NTP
  NTP Core (ERROR): Invalid-NAK error at 67 10.255.255.1<-10.255.255.100
  NTP Core (ERROR): Invalid-NAK error at 131 10.255.255.1<-10.255.255.100
  ```
  The `Invalid-NAK` errors are logged without any debug turned on. The running config shows the key only as a
  type 7 string (`ntp authentication-key 1 md5 032A6F3B150A225E4B1D48 7`), and type 7 output differs between
  routers even for the same key, so comparing strings proves nothing: re-enter the key.
- **Fix:**
  ```
  R1(config)# ntp authentication-key 1 md5 NTPsecret
  ```
  Replies now count (`assoc in packets` rises) and R1 selects NTP1 (`*~10.255.255.100`, stratum 3) within a
  couple of polls. **"Clock is synchronized" takes much longer**: NTP1 itself needed about 15 minutes after boot
  before it served time, and R1 then spent another 15 minutes measuring its drift (`loopfilter state is 'FREQ'`)
  before it reported synchronized. That's normal; keep working on R2 and R3 meanwhile.

### Fault 2: R1's serve-only ACL lists R2's interface address
- **Where:** R1, `ip access-list standard NTP-CLIENTS`, line 10.
- **Injected config:** `10 permit 10.1.2.2` (designed: `10 permit 10.255.255.2`).
- **Why it breaks:** `ntp access-group serve-only NTP-CLIENTS` is checked against the **source** address of the
  request. R2 sends NTP from Loopback0, 10.255.255.2, which the ACL doesn't permit, so R1 silently ignores it.
  (Hidden behind Fault 3 until R2 actually sends.)
- **Evidence (Captured, after fixing Fault 3, with `debug ntp packet` on R1):**
  ```
  R2# show ntp associations detail | include configured|assoc in
  10.255.255.1 configured, ipv4, authenticated (' ' reject), authtype (md5), insane, invalid, unsynced, stratum 16
  assoc in packets 0, assoc out packets 2, assoc error packets 0

  R1# show logging | include 10.255.255.2
  NTP message received from 10.255.255.2 on interface 'Loopback0' (10.255.255.1).
  NTP message received from 10.255.255.2 on interface 'Loopback0' (10.255.255.1).
  NTP message received from 10.255.255.2 on interface 'Loopback0' (10.255.255.1).
  R1# show ip access-lists NTP-CLIENTS
  Standard IP access list NTP-CLIENTS
      10 permit 10.1.2.2
      20 permit 10.255.255.3
  ```
  R1 receives every request and sends nothing back (no "message sent to 10.255.255.2" line).
- **Fix:**
  ```
  R1(config)# ip access-list standard NTP-CLIENTS
  R1(config-std-nacl)# no 10
  R1(config-std-nacl)# 10 permit 10.255.255.2
  ```
  On the next poll R1 answers (`NTP message sent to 10.255.255.2`) and line 10 counts matches. R2 still counts
  the replies as errors until R1 itself is synchronized (Fault 1's wait).

### Fault 3: R2 doesn't trust key 1
- **Where:** R2, global config.
- **Injected config:** `ntp trusted-key 1` missing (`ntp authenticate` is on).
- **Why it breaks:** with authentication on, only trusted keys may be used. IOS-XE doesn't even send a request
  to a server or peer configured with an untrusted key: the packet counters stay at 0.
- **Evidence (Captured):**
  ```
  R2# show ntp associations detail | include configured|assoc in|our mode
  10.255.255.1 configured, ipv4, authenticated (' ' reject), authtype (md5), insane, invalid, unsynced, stratum 16
  our mode client, peer mode unspec, our poll intvl 64, peer poll intvl 1024
  assoc in packets 0, assoc out packets 0, assoc error packets 0
  10.255.255.3 configured, ipv4, authenticated (' ' reject), authtype (md5), insane, invalid, unsynced, stratum 16
  our mode active, peer mode unspec, our poll intvl 64, peer poll intvl 1024
  assoc in packets 0, assoc out packets 0, assoc error packets 0

  R2# show logging | include NTP
  %SYS-4-INSECURE_CONFIG: Module: NTP - Command: ntp server 10.255.255.1 key 1 <cr> - Reason: NTP configuration
    lacks authentication, allowing potential time manipulation attacks - Remediation: Please make the configured
    auth key trusted using the command - ntp trusted-key
  ```
  IOS-XE 17.18's security audit spells out the fix about two minutes after boot. On older releases there's no
  such message and the zero `out packets` is the clue.
- **Fix:**
  ```
  R2(config)# ntp trusted-key 1
  ```

### Fault 4: R3 sources NTP from a loopback that isn't routed
- **Where:** R3, `ntp source`.
- **Injected config:** `ntp source Loopback1` (designed: `ntp source Loopback0`).
- **Why it breaks:** R3's requests leave with source 172.19.0.1. Loopback1 isn't in OSPF, so neither R1 nor R2
  has a route back to it, and R1's NTP-CLIENTS doesn't permit it either. Nothing ever answers R3.
- **Evidence (Captured):**
  ```
  R3# show running-config | include ntp source
  ntp source Loopback1
  R3# ping 10.255.255.1 source Loopback1 repeat 2 timeout 1
  Packet sent with a source address of 172.19.0.1
  ..
  Success rate is 0 percent (0/2)
  R3# show ntp associations
    address         ref clock       st   when   poll reach  delay  offset   disp
   ~10.255.255.2    .INIT.          16      -     64     0  0.000   0.000 15937.
   ~10.255.255.3    .INIT.          16      -     64     0  0.000   0.000 15937.
  ```
- **Fix:**
  ```
  R3(config)# ntp source Loopback0
  ```

### Fault 5: R3's server is itself
- **Where:** R3, `ntp server`.
- **Injected config:** `ntp server 10.255.255.3 key 1` (designed: `ntp server 10.255.255.1 key 1`).
- **Why it breaks:** 10.255.255.3 is R3's own Loopback0. A router can't get time from itself, so R3 has no real
  server, and R1 never hears from R3 at all.
- **Evidence (Captured, after fixing Fault 4, with `debug ntp packet` on R3):**
  ```
  R3# show ntp associations detail | include configured|assoc in
  10.255.255.3 configured, ipv4, authenticated (' ' reject), authtype (md5), insane, invalid, unsynced, stratum 16
  assoc in packets 0, assoc out packets 22, assoc error packets 0

  R3# show logging | include 10.255.255.3
  NTP: ntpio_send_ipv4: dst 10.255.255.3, src 0.0.0.0, if_out Loopback0
  NTP message sent to 10.255.255.3, from interface 'Loopback0' (10.255.255.3).

  R1# show ip access-lists NTP-CLIENTS
      10 permit 10.255.255.2 (13 matches)
      20 permit 10.255.255.3
  ```
  R1's line 20 never matches: R3 isn't asking R1.
- **Fix:**
  ```
  R3(config)# no ntp server 10.255.255.3
  R3(config)# ntp server 10.255.255.1 key 1
  ```

## Verification after all fixes (Captured)
About 50 minutes after boot (NTP1 needed ~15 minutes, then R1 ~15 minutes, then R2 and R3 ~15 minutes):
```
R1# show ntp status | include Clock
Clock is synchronized, stratum 4, reference is 10.255.255.100
R1# show ntp associations
  address         ref clock       st   when   poll reach  delay  offset   disp
*~10.255.255.100  127.127.1.1      3     50     64   377  1.000  -0.675  3.694
R1# show ip access-lists
Standard IP access list NTP-CLIENTS
    10 permit 10.255.255.2 (54 matches)
    20 permit 10.255.255.3 (42 matches)
Standard IP access list NTP-PEERS
    10 permit 10.255.255.100 (21 matches)
R1# show clock
16:40:42.987 EST Wed Nov 4 2026

R2# show ntp associations
  address         ref clock       st   when   poll reach  delay  offset   disp
*~10.255.255.1    10.255.255.100   4     44     64   377  1.000   0.671  3.408
 ~10.255.255.3    10.255.255.1     5     46     64     1  0.988  -0.494 3938.9
R2# show ntp status | include Clock
Clock is synchronized, stratum 5, reference is 10.255.255.1

R3# show ntp associations
  address         ref clock       st   when   poll reach  delay  offset   disp
*~10.255.255.1    10.255.255.100   4     11     64   377  1.000  -0.357  5.056
 ~10.255.255.2    10.255.255.1     5     12     64     1  2.023  -0.022 7938.4
R3# show ntp status | include Clock
Clock is synchronized, stratum 5, reference is 10.255.255.1
R3# show clock
16:40:22.925 EST Wed Nov 4 2026
```
The R2–R3 peer reach starts counting only once both are synchronized (1, then 3, 7 … 377).

## How this was tested
On the dev server, CML 2.10.1, IOL-XE 17.18.2, whole lab (4 licensed nodes), booted with the faulted configs.
Each symptom was confirmed live, then fixed in the order above. Notes:
- **NTP is slow on IOS-XE.** An `ntp master` stays unsynchronized for ~15 minutes after boot (drift
  measurement, `loopfilter state is 'FREQ'`) and serves nobody meanwhile; each level below does the same once its
  server is synchronized. Fixes show up within one or two polls in the packet counters and `reach`, long before
  `show ntp status` says synchronized.
- `debug ntp packet` (17.18 syntax; `debug ntp packets` is rejected) logs every NTP message sent and received,
  which is how Faults 2 and 5 were confirmed.
- The `%SYS-4-INSECURE_CONFIG` audit messages appear about two minutes after boot on every router with an MD5 key,
  and on R2 they name the missing `ntp trusted-key`.
