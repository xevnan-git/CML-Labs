# eBGP Dual-Homed Edge — Solution (learn-ebgp)

## Final configs
[`configs/`](configs/): R1 as it should look after Step 9:
- `network 192.168.10.0`
- local-pref 200 on everything from ISP1 (`ISP1-IN`)
- three prepends toward ISP2 (`ISP2-OUT`)
- MD5 password `isp2peer` toward ISP2
- `ip as-path access-list 1 permit ^$` as the outbound filter toward both ISPs

The ISP configs are unchanged from boot. Weight (Step 7) and the bad `remote-as` / `network` statements
(Steps 2 and 5) are demonstrations and are removed again in the guide, so they aren't in the final config.

## How this was tested
On the dev server (5-node license), CML 2.10.1, IOL-XE 17.18.2:
1. R1, ISP1, ISP2, ISP3 and PC1: Steps 1–9 and the failover test, with every command exactly as written in the guide.
   All output in the guide is **Captured** from that run.
2. PC1 stopped and PC2 started: PC2 → 192.168.10.1 (the inbound path).

PC1 → PC2 couldn't run end to end under the 5-node limit (it needs 6 nodes up). The guide's final check captured
the traceroutes one hop short of each PC (to 198.51.100.1 and 192.168.10.1), which crosses every BGP decision in
the lab.

## Final verification (Captured)
```
R1# show running-config | section bgp|route-map|as-path
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
ip as-path access-list 1 permit ^$
route-map ISP2-OUT permit 10
 set as-path prepend 65001 65001 65001
route-map ISP1-IN permit 10
 set local-preference 200

R1# show ip bgp summary | begin Neighbor
Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
10.1.101.101    4        64511      11       5       38    0    0 00:00:06        5
10.1.102.102    4        64512      37      41       43    0    0 00:14:37        5

ISP3# show ip bgp 192.168.10.0 best-path-reason
  64511 65001
    10.101.103.101 from 10.101.103.101 (10.255.255.101)
      Origin IGP, localpref 100, valid, external, best
      Best Path Evaluation: Overall best path
  64512 65001 65001 65001 65001
    10.102.103.102 from 10.102.103.102 (10.255.255.102)
      Origin IGP, localpref 100, valid, external
      Best Path Evaluation: Longer AS path

PC2$ traceroute -n -q 1 -w 1 192.168.10.1
 1  198.51.100.1  0.948 ms
 2  10.101.103.101  1.277 ms
 3  10.1.101.1  1.449 ms
```

**Expected** on the 20-node server (all six nodes up):
```
PC1$ ping -c 3 198.51.100.10        -> 3 replies
PC1$ traceroute -n 198.51.100.10    -> 192.168.10.1, 10.1.101.101, 10.101.103.103, 198.51.100.10
```

## Check-yourself answers
- **`FBFF`** is the AS the peer put in its OPEN. If ISP1 were really in 64513, the log would show `FC01`.
- **Only ISP2 logs** because only ISP2 checks signatures. R1 has no password configured, so it doesn't expect one,
  and it never sees an error. Its SYNs just go unanswered.
- **Same result.** With no `mask`, IOS uses the classful mask, and 192.168.10.0 is class C (/24). With a classless
  prefix (e.g. a /23 out of 10.0.0.0/8) you *must* give the mask.
- **Nothing beats weight.** It's step 1, and it's local to the router. (A route that isn't valid, such as one whose
  next hop is unreachable, never competes at all.)
- **ISP3 never sees the 200.** Local preference only travels inside an AS (over iBGP). It's stripped on eBGP
  updates, which is why you need prepending (or MED, or communities) to influence other ASes.
- **ISP2 sees `65001 65001 65001 65001`.** The prepend is added as the update leaves R1. ISP2 then adds its own
  64512 when it passes the route on to ISP3.
- **Without the filter toward ISP1,** ISP1 would get your LAN plus everything R1 picks as best that it can
  re-advertise. ISP1 ignores routes that already contain 64511 (loop prevention), so in practice it would take
  ISP2's loopback via `65001 64512`. That is the transit leak.

## Notes from testing
- `network 192.168.10.0 mask 255.255.0.0` is **rejected** at the CLI (`% BGP: Incorrect network or mask
  configured`) because the address has host bits set for a /16. The guide (and the TS lab's fault) uses
  `192.168.0.0 mask 255.255.0.0`, which is accepted and silently matches nothing.
- `clear ip bgp <n> soft in` returns before the new policy is in the table. A second `show` a few seconds later
  shows the change.
- Right after R1 boots, BGP waits before marking anything best (start-up read-only mode while neighbors come up).
  `show ip bgp` shows `*` without `>` for up to a couple of minutes if a neighbor never establishes.
- pyATS traceroute from Alpine needs `-q 1 -w 1` or it can time out the tool call. Interactive consoles are fine.
