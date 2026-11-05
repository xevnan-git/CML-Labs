# FHRP (HSRP and VRRP) — Solution (ts-fhrp)

> Spoilers below. Try the hints first, one at a time.

## Hints

<details><summary>Hint 1 — where to look</summary>

R3, the PCs and OSPF are fine; the faults are in R1's and R2's HSRP, VRRP and tracking configuration. Your best
tools are `show standby brief` / `show standby`, `show vrrp brief` / `show vrrp detail`, `show track`,
`show logging | include HSRP|VRRP|TRACK`, and on the PCs `ip neigh` and `traceroute -n`. Fix what's broken at boot
first, then run the failover tests: two of the faults only show up during a failover.
</details>

<details><summary>Hint 2 — what to compare</summary>

- Two routers can't both be Active for one HSRP group unless they ignore each other. What does the log say about
  the other router's hellos?
- PC2's ARP entry for 192.168.20.1 is INCOMPLETE. Which address is R2's VRRP group actually serving?
- LAN10 failover test: what is R1's priority with its uplink down, compared with R2's?
- After that's fixed, R2 knows R1's priority is lower than its own. What else does R2 need to take over?
- LAN20 failover test: R2's priority doesn't drop. What does R2's `track 1` actually watch?
</details>

<details><summary>Hint 3 — almost there</summary>

- HSRP key strings are case sensitive.
- In VRRP, every router in a group must list the same virtual address.
- The tracking decrement has to take the primary *below* the backup, not just lower it.
- A standby takes over from a working Active router only if it has `preempt`.
- `show track 1` says what's tracked. A track object's type can't be changed in place: `no track 1`, then enter
  it again (the `track 1 decrement` lines under HSRP/VRRP stay).
</details>

## Faults
Two on R1, three on R2. In the order a learner usually meets them:

### Fault 1: R1's HSRP key differs in case
- **Where:** R1, Ethernet0/0.
- **Injected config:** `standby 10 authentication md5 key-string FHRPSecret` (designed: `FHRPsecret`).
- **Why it breaks:** each router discards the other's hellos, so both believe they're alone and both go Active.
  LAN10 still works because both answer for the same virtual IP and MAC, but there's no standby any more.
- **Evidence (Captured, at boot):**
  ```
  R1# show standby brief
  Interface   Grp  Pri P State   Active          Standby         Virtual IP
  Et0/0       10   110 P Active  local           unknown         192.168.10.1
  R1# show logging | include HSRP
  %HSRP-5-STATECHANGE: Ethernet0/0 Grp 10 state Standby -> Active
  %HSRP-4-BADAUTH2: Bad authentication from 192.168.10.3

  R2# show standby brief
  Et0/0       10   100   Active  local           unknown         192.168.10.1
  R2# show logging | include HSRP
  %HSRP-4-BADAUTH2: Bad authentication from 192.168.10.2
  %HSRP-5-STATECHANGE: Ethernet0/0 Grp 10 state Standby -> Active
  %HSRP-4-BADAUTH2: Bad authentication from 192.168.10.2

  PC1$ ping -c 2 -W 1 172.16.0.100
  2 packets transmitted, 2 packets received, 0% packet loss
  ```
  The running config shows the key in clear text, so the two can be compared directly. R2's line also has no `P`
  (Fault 4).
- **Fix:**
  ```
  R1(config)# interface Ethernet0/0
  R1(config-if)# standby 10 authentication md5 key-string FHRPsecret
  ```
  Within seconds R2 drops to Speak and then Standby (`Active -> Speak`, `Speak -> Standby` in R2's log).

### Fault 2: R2's VRRP group serves 192.168.20.254
- **Where:** R2, Ethernet0/1, `vrrp 20 address-family ipv4`.
- **Injected config:** `address 192.168.20.254 primary` (designed: `192.168.20.1`).
- **Why it breaks:** R2 has the higher priority (110), so it's Master, but for .254. R1 is Backup for .1 and
  doesn't forward while a Master exists. Nobody answers ARP for 192.168.20.1, so PC2 has no gateway at all.
- **Evidence (Captured, at boot):**
  ```
  PC2$ ping -c 2 -W 1 172.16.0.100
  2 packets transmitted, 0 packets received, 100% packet loss
  PC2$ ip neigh
  192.168.20.1 dev eth0  ref 1 used 0/0/0 probes 6 INCOMPLETE

  R1# show vrrp brief
    Interface          Grp  A-F Pri  Time Own Pre State   Master addr/Group addr
    Et0/1               20 IPv4 100  3609  N   Y  BACKUP  192.168.20.3 192.168.20.1
  R2# show vrrp brief
    Et0/1               20 IPv4 110     0  N   Y  MASTER  192.168.20.3(local) 192.168.20.254
  R1# show logging | include VRRP
  %VRRP-6-STATE: Ethernet0/1 IPv4 group 20 state MASTER -> BACKUP
  %VRRP-4-CFG_WARN: Ethernet0/1 IPv4 group 20 Peer Advert msg has unordered or incorrect number of addresses or addresses do not match
  ```
- **Fix:**
  ```
  R2(config)# interface Ethernet0/1
  R2(config-if)# vrrp 20 address-family ipv4
  R2(config-if-vrrp)# no address 192.168.20.254 primary
  R2(config-if-vrrp)# address 192.168.20.1 primary
  ```
  PC2 reaches the server through R2 (hop 1 192.168.20.3).

### Fault 3: R1's track decrement is too small
- **Where:** R1, Ethernet0/0.
- **Injected config:** `standby 10 track 1 decrement 5` (designed: `decrement 20`).
- **Why it breaks:** with the uplink down, R1 drops from 110 to 105, still higher than R2's 100, so R1 stays
  Active with no way to R3. PC1's traffic reaches R1 and is dropped there. Invisible until the failover test.
- **Evidence (Captured, LAN10 failover test: `shutdown` on R1 e0/2):**
  ```
  R1# show standby brief
  Et0/0       10   105 P Active  local           192.168.10.3    192.168.10.1
  R1# show standby Ethernet0/0 | include Track|track|Priority
    Priority 105 (configured 110)
      Track object 1 state Down decrement 5
  R1# show track 1 brief
  1     ip route    10.255.255.3/32            reachability     Down  00:00:34

  PC1$ ping -c 3 -W 1 172.16.0.100
  3 packets transmitted, 0 packets received, 100% packet loss
  PC1$ traceroute -n -q 1 -w 1 -m 3 172.16.0.100
   1  192.168.10.2  1.639 ms
   2  192.168.10.2  3.651 ms !H
  ```
  The tracking works (state Down); the decrement doesn't take R1 below R2.
- **Fix:**
  ```
  R1(config)# interface Ethernet0/0
  R1(config-if)# standby 10 track 1 decrement 20
  ```
  R1 drops to 90, but R2 still doesn't take over (Fault 4).

### Fault 4: R2 has no HSRP preempt
- **Where:** R2, Ethernet0/0.
- **Injected config:** `standby 10 preempt` missing.
- **Why it breaks:** tracking only lowers R1's priority; the Active router doesn't step down for that. The standby
  must **preempt** to take over from an Active router that's still alive. Without it, R2 waits for R1 to fail
  completely.
- **Evidence (Captured, after Fault 3, R1's uplink still down):**
  ```
  R2# show standby brief
  Interface   Grp  Pri P State   Active          Standby         Virtual IP
  Et0/0       10   100   Standby 192.168.10.2    local           192.168.10.1
  R2# show standby Ethernet0/0 | include Active router|Standby router|Priority|Preemption
    Preemption disabled
    Active router is 192.168.10.2, priority 90 (expires in 2.608 sec)
    Standby router is local
    Priority 100 (default 100)
  PC1$ ping -c 2 -W 1 172.16.0.100
  2 packets transmitted, 0 packets received, 100% packet loss
  ```
  R2 knows the Active router's priority (90) is below its own and still stays Standby.
- **Fix:**
  ```
  R2(config)# interface Ethernet0/0
  R2(config-if)# standby 10 preempt
  ```
  R2 goes Active immediately; PC1's traceroute shows hop 1 192.168.10.3 and the ping works. (If PC1 still fails
  for a while, that's R3 waiting out its OSPF dead timer for R1: up to 40 seconds.) After `no shutdown` on R1
  e0/2, R1 takes back over once OSPF is up and its track returns.

### Fault 5: R2's track object watches the wrong thing
- **Where:** R2, global `track 1`.
- **Injected config:** `track 1 interface Ethernet0/0 line-protocol` (designed: `track 1 ip route 10.255.255.3
  255.255.255.255 reachability`).
- **Why it breaks:** R2's VRRP group tracks object 1, but object 1 follows R2's LAN10 port, not its way to R3.
  When R2's uplink fails, the track stays Up, R2 stays Master for LAN20 at priority 110, and PC2's traffic dies at
  R2.
- **Evidence (Captured, LAN20 failover test: `shutdown` on R2 e0/2):**
  ```
  R2# show vrrp brief
    Et0/1               20 IPv4 110     0  N   Y  MASTER  192.168.20.3(local) 192.168.20.1
  R2# show track 1
  Track 1
    Interface Ethernet0/0 line-protocol
    Line protocol is Up
    Tracked by:
      VRRPv3 Ethernet0/1 IPv4 group 20
  R2# show ip route 10.255.255.3
  % Subnet not in table

  PC2$ ping -c 3 -W 1 172.16.0.100
  3 packets transmitted, 0 packets received, 100% packet loss
  PC2$ traceroute -n -q 1 -w 1 -m 3 172.16.0.100
   1  192.168.20.3  0.874 ms
   2  192.168.20.3  0.619 ms !H
  ```
- **Fix:** the object's type can't be changed in place:
  ```
  R2(config)# track 1 ip route 10.255.255.3 255.255.255.255 reachability
  % Cannot change tracked object 1 - delete old config first
  R2(config)# no track 1
  R2(config)# track 1 ip route 10.255.255.3 255.255.255.255 reachability
  ```
  The VRRP group's `track 1 decrement 20` line survives `no track 1`. R2 drops to 90 and R1 becomes Master:
  ```
  R2# show vrrp brief
    Et0/1               20 IPv4  90  3648  N   Y  BACKUP  192.168.20.2 192.168.20.1
  PC2$ traceroute -n -q 1 -w 1 172.16.0.100
   1  192.168.20.2  1.010 ms
   2  10.1.3.3  1.066 ms
  ```

## Verification after all fixes (Captured)
With both uplinks back up (`no shutdown`) and OSPF converged:
```
R1# show standby brief
Interface   Grp  Pri P State   Active          Standby         Virtual IP
Et0/0       10   110 P Active  local           192.168.10.3    192.168.10.1
R1# show vrrp brief
  Interface          Grp  A-F Pri  Time Own Pre State   Master addr/Group addr
  Et0/1               20 IPv4 100  3609  N   Y  BACKUP  192.168.20.3 192.168.20.1

R2# show vrrp brief
  Et0/1               20 IPv4 110     0  N   Y  MASTER  192.168.20.3(local) 192.168.20.1
R2# show track brief
Track Type        Instance                   Parameter        State Last Change
1     ip route    10.255.255.3/32            reachability     Up    00:01:00
R2# show logging | include VRRP-6|TRACK
%VRRP-6-STATE: Ethernet0/1 IPv4 group 20 state MASTER -> BACKUP
%TRACK-6-STATE: 1 ip route 10.255.255.3/32 reachability Down -> Up
%VRRP-6-STATE: Ethernet0/1 IPv4 group 20 state BACKUP -> MASTER

PC1$ traceroute -n -q 1 -w 1 172.16.0.100
 1  192.168.10.2  3.530 ms
 2  10.1.3.3  8.176 ms
PC2$ traceroute -n -q 1 -w 1 172.16.0.100
 1  192.168.20.3  1.610 ms
 2  10.2.3.3  1.083 ms
```
The LAN10 failover test passed once Faults 1–4 were fixed: R2 went Active with R1's uplink down, and R1 took back
over after `no shutdown` (Fault 5 only affects LAN20).

## How this was tested
On the dev server, CML 2.10.1, IOL-XE 17.18.2, Alpine 3.23, whole lab (5 licensed nodes + 2 unmanaged switches),
booted with the faulted configs. Each symptom was confirmed live, then fixed in the order above. Notes:
- All faulted lines were accepted at boot.
- Right after boot R1's track 1 showed Down for a few seconds until OSPF came up (R1 at priority 105 then); give the
  lab a minute before reading priorities.
- After `no shutdown` on an uplink, the track stays Down until the OSPF adjacency is FULL again (tens of seconds),
  so the primary takes back over about a minute later, not at once.
