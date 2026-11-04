# NTP — Solution (learn-ntp)

## Final configs
[`configs/`](configs/): all four routers as they should look after Step 6:
- every router: `clock timezone EST -5 0`, `clock summer-time EDT recurring`, `service timestamps … localtime
  show-timezone`, NTP key 1 (MD5, `NTPsecret`), `ntp authenticate`, `ntp trusted-key 1`, `ntp source Loopback0`
- NTP1: `ntp master 3`
- R1: `ntp server 10.255.255.100 key 1`, ACLs NTP-PEERS / NTP-CLIENTS, `ntp access-group peer NTP-PEERS`,
  `ntp access-group serve-only NTP-CLIENTS`
- R2: `ntp server 10.255.255.1 key 1`, `ntp peer 10.255.255.3 key 1`
- R3: `ntp server 10.255.255.1 key 1`, `ntp peer 10.255.255.2 key 1`

## How this was tested
On the dev server (5-node license), CML 2.10.1, IOL-XE 17.18.2. The lab is 4 licensed nodes, so it ran whole:
Steps 1–7, every command as written in the guide. All output in the guide is **Captured** from that run.

Notes from the run:
- **Timing (measured twice, in this lab and the troubleshooting lab):** after `ntp master 3`, NTP1 stayed
  *unsynchronized* (`loopfilter state is 'FREQ'`) for about 15 minutes and served nobody meanwhile. Each lower
  level picked its server (`*`) within two polls of the level above becoming synchronized, then spent its own
  ~15 minutes in FREQ. Total from `ntp master` to R2/R3 synchronized: about 45–50 minutes.
- While NTP1 was unsynchronized, R1 received its replies but counted every one as an error
  (`assoc error packets` = `assoc in packets`), and reach stayed 0.
- **Access-group order matters:** with only `ntp access-group serve-only NTP-CLIENTS` configured, R1 kept sending
  to NTP1 but stopped accepting the replies (in-packet counter frozen at 10 while out went from 10 to 14). Adding
  `ntp access-group peer NTP-PEERS` restored it.
- IOS-XE 17.18 prints a SECURITY WARNING for unauthenticated `ntp server`/`ntp peer` lines and for MD5 keys, and
  repeats them in the log as `%SYS-4-INSECURE_CONFIG` a couple of minutes after boot. It offers `hmac-sha1`,
  `hmac-sha2-256`, `sha1`, `sha2` and `cmac-aes-128` as alternatives.
- `debug ntp` on 17.18 has `packet`, `events`, `core`, `adjust`, `refclock`, `all` (not the older
  `packets`/`validity`). There's no `show ntp access-group`; use `show ip access-lists`, whose counters do count
  NTP access-group matches.

## Final verification (Captured)
```
R1# show running-config | include ntp|clock|timestamps
service timestamps debug datetime msec localtime show-timezone
service timestamps log datetime msec localtime show-timezone
clock timezone EST -5 0
clock summer-time EDT recurring
ntp authentication-key 1 md5 0228306B18030C33495A 7
ntp authenticate
ntp trusted-key 1
ntp source Loopback0
ntp access-group peer NTP-PEERS
ntp access-group serve-only NTP-CLIENTS
ntp server 10.255.255.100 key 1

R1# show ip access-lists
Standard IP access list NTP-CLIENTS
    10 permit 10.255.255.2 (89 matches)
    20 permit 10.255.255.3 (87 matches)
Standard IP access list NTP-PEERS
    10 permit 10.255.255.100 (37 matches)

R2# show ntp status
Clock is synchronized, stratum 5, reference is 10.255.255.1
nominal freq is 250.0000 Hz, actual freq is 250.0001 Hz, precision is 2**10
ntp uptime is 293800 (1/100 of seconds), resolution is 4000
reference time is EE963105.7C25B65A (17:32:37.484 EST Wed Nov 4 2026)
clock offset is -0.9820 msec, root delay is 1.99 msec
root dispersion is 16.09 msec, peer dispersion is 3.48 msec
loopfilter state is 'CTRL' (Normal Controlled Loop), drift is -0.000000481 s/s
system poll interval is 64, last update was 39 sec ago.

R2# show clock detail
17:33:16.991 EST Wed Nov 4 2026
Time source is NTP
Summer time starts 02:00:00 EST Sun Mar 14 2027
Summer time ends 02:00:00 EDT Sun Nov 7 2027
```
The full `show ntp associations` output for R1, R2 and R3 is in the guide's Step 7.

## Check yourself — answers
- **Stratum 16** = unsynchronized. R2 is stratum 5 because its server R1 is 4, whose server NTP1 is 3.
- **Replies but reach 0:** the server isn't synchronized itself (Step 3), or an access-group refuses the replies
  (Step 6). A key mismatch also does it (the server sends a crypto-NAK).
- **`ntp trusted-key`:** `ntp authenticate` turns checking on; trusted-key says which keys count. With no trusted
  key, nothing can authenticate, and IOS-XE doesn't even send requests with an untrusted key.
- **`server` instead of `peer`:** R2 would be a client of R3 only: it could take time from R3 but would never
  give R3 time. With two `server` lines (R1 and R3), R2 picks the best of them.
- **R3 sourcing from Loopback1:** R3's requests leave with 172.19.0.1; nobody has a route back, so nothing is
  answered. `show ntp associations detail` shows `assoc out packets` rising with `assoc in packets` at 0, and
  reach stays 0. (This is Fault 4 in the troubleshooting lab.)
- **`*` in `show clock` with `*~` in associations:** nothing is wrong yet: R1 has chosen its server but is still
  measuring its drift. The `*` in `show clock` disappears when `show ntp status` says synchronized.
- **PTP:** when you need sub-microsecond accuracy: trading, power grid protection, broadcast, mobile fronthaul.
