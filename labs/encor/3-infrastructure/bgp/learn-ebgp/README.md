# eBGP Dual-Homed Edge — Learning Lab

> **Blueprint:** ENCOR 3.2.c — Configure and verify eBGP between directly connected neighbors (best path selection
> algorithm and neighbor relationships)
> **Mode:** Learning (guided build) · **Nodes:** 6 licensed (4 routers, 2 PCs) · **Time:** ~60 min

<!--
This README is copied verbatim into the lab's CML Notes (tools/sync_notes.py), so it must read well inside CML:
plain Markdown, ASCII diagrams (no Mermaid), no links to solution files.
Order: objectives and steps first; lab access, topology and addressing in the Reference section at the bottom.
-->

## What you'll learn
- Bring up an eBGP session and read `show ip bgp summary`: what *Idle*, *Active* and a prefix count in the
  State/PfxRcd column each tell you.
- Recognize the three classic reasons a session won't come up: wrong `remote-as` (a NOTIFICATION), an admin
  shutdown (*Idle (Admin)*), and an MD5 password mismatch (silence on your side, `%TCP-6-BADAUTH` on theirs).
- See why `network` only advertises a prefix that is *exactly* in the routing table.
- Read `show ip bgp` and `show ip bgp <prefix> best-path-reason` and say why one path has the `>`.
- Steer **outbound** traffic with weight and local preference, and **inbound** traffic with AS-path prepending.
- Stop your network from becoming a free transit path between your two ISPs.

## Starting point
Logins, the topology diagram and the addressing table are in **Reference** at the end of this guide.

You are the network engineer for **AS 65001**. Your only router is **R1**, the internet edge, and it boots
**clean**: hostname, login and console settings only, with every interface shut.

The three ISP routers belong to "the providers" and are **already fully configured**. You may log in to look at
them (`show` commands), but this lab never changes them. That's how it works in real life: you configure your side,
the ISP gives you a handoff sheet. Theirs says:

| | ISP1 (primary) | ISP2 (backup) |
|---|---|---|
| Their AS | 64511 | 64512 |
| Their address / yours | 10.1.101.101 / 10.1.101.1 | 10.1.102.102 / 10.1.102.1 |
| They expect your AS | 65001 | 65001 |
| Session password (MD5) | none | `isp2peer` |

ISP3 (AS 64513) is "the rest of the internet". It originates `198.51.100.0/24` (PC2's LAN), `203.0.113.0/24`
(its Loopback1) and its Loopback0. Each ISP also originates its own Loopback0.

**The design you're building:** R1 advertises the LAN `192.168.10.0/24`. ISP1 is primary in **both** directions:
traffic leaving AS 65001 uses ISP1, and the internet uses ISP1 to reach you. ISP2 takes over if ISP1 fails. AS 65001
must never carry traffic between ISP1 and ISP2.

PCs: wait for the routers to finish booting (about a minute) before testing.

## Step 1 — Address R1 and test the links
eBGP between directly connected neighbors runs over the link subnet, so the link has to work first.

**R1**
```
configure terminal
interface Loopback0
 ip address 10.255.255.1 255.255.255.255
interface Ethernet0/0
 description ISP1 (primary) e0/0
 ip address 10.1.101.1 255.255.255.0
 no shutdown
interface Ethernet0/1
 description ISP2 (backup) e0/0
 ip address 10.1.102.1 255.255.255.0
 no shutdown
interface Ethernet0/2
 description PC1 LAN
 ip address 192.168.10.1 255.255.255.0
 no shutdown
end
ping 10.1.101.101
ping 10.1.102.102
ping 10.255.255.101
```
**Output (captured)**
```
R1# ping 10.1.101.101
.!!!!
Success rate is 80 percent (4/5), round-trip min/avg/max = 1/1/1 ms
R1# ping 10.1.102.102
!!!!!
Success rate is 100 percent (5/5), round-trip min/avg/max = 1/1/1 ms
R1# ping 10.255.255.101
.....
Success rate is 0 percent (0/5)
```
Look for: both neighbors answer (the first `.` is just ARP). ISP1's loopback doesn't, because R1 has no route to
it yet. Learning that route is BGP's job.

## Step 2 — First session, with a mistake on purpose
A common slip: typing the *other* ISP's AS number. Do it on purpose so you know what it looks like.

**R1**
```
configure terminal
router bgp 65001
 bgp router-id 10.255.255.1
 bgp log-neighbor-changes
 neighbor 10.1.101.101 remote-as 64512
 neighbor 10.1.101.101 description ISP1 (primary)
end
```
Wait about 10 seconds, then:
```
show logging | include BGP
show ip bgp summary
```
**Output (captured, trimmed)**
```
%BGP-3-NOTIFICATION: sent to neighbor 10.1.101.101 passive 2/2 (peer in wrong AS) 2 bytes FBFF
%BGP-5-ADJCHANGE: neighbor 10.1.101.101 passive Down BGP Notification sent

Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
10.1.101.101    4        64512       0       0        1    0    0 never    Idle
```
Look for:
- **`2/2 (peer in wrong AS)`.** NOTIFICATION error code 2 (OPEN message error), subcode 2 (bad peer AS).
- **`FBFF`.** The AS the peer actually sent, in hex: 0xFBFF = **64511**. The log tells you the right answer.
- **State `Idle`.** After a NOTIFICATION, BGP drops to Idle and waits before retrying, so the column flips between
  *Idle* and *Active* while the problem lasts.

Fix it:
```
configure terminal
router bgp 65001
 neighbor 10.1.101.101 remote-as 64511
end
show ip bgp summary | begin Neighbor
show ip bgp neighbors 10.1.101.101 | include BGP state|hold time|TTL|Local host|Foreign host
```
**Output (captured)**
```
Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
10.1.101.101    4        64511       8       2        1    0    0 00:00:30        5

  BGP state = Established, up for 00:00:30
  Last read 00:00:30, last write 00:00:30, hold time is 180, keepalive interval is 60 seconds
Connection is ECN Disabled, Mininum incoming TTL 0, Outgoing TTL 1
Local host: 10.1.101.1, Local port: 179
Foreign host: 10.1.101.101, Foreign port: 28485
```
Look for:
- **A number in State/PfxRcd.** In this column a number *means* Established: here, 5 prefixes received. Any word
  (Idle, Active, Connect, OpenSent, OpenConfirm) means the session is not up.
- **`Outgoing TTL 1`.** eBGP sends its packets with TTL 1 by default, so the neighbor must be one hop away. That's
  the "directly connected" rule in the exam topic. Peering to a loopback would need `ebgp-multihop` (or
  `disable-connected-check`) and `update-source`.
- **Local port 179.** ISP1 opened the TCP connection to R1 here (foreign port is random). Either side can win the
  race; BGP keeps one connection and drops the other.

> **Why:** BGP has no discovery. Each side is told explicitly who its neighbor is and which AS that neighbor must be
> in. The TCP session (port 179) comes up first, then each side sends an OPEN with its AS, router ID and hold time.
> If what arrives doesn't match the `remote-as` you configured, the receiver answers with a NOTIFICATION and tears
> the session down. States: **Idle** (not trying, or backing off) → **Connect** (TCP in progress) → **Active** (TCP
> failed, retrying) → **OpenSent / OpenConfirm** (OPENs exchanged) → **Established**.

## Step 3 — Admin shutdown
Sometimes you want a session configured but down, for maintenance or before go-live.

**R1**
```
configure terminal
router bgp 65001
 neighbor 10.1.101.101 shutdown
end
show ip bgp summary | begin Neighbor
```
**Output (captured)**
```
Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
10.1.101.101    4        64511       0       0        1    0    0 00:00:15 Idle (Admin)
```
Now look from the other side:

**ISP1**
```
show ip bgp neighbors 10.1.101.1 | include BGP state|Last reset
```
**Output (captured)**
```
  BGP state = Idle, down for 00:00:30
  Last reset 00:00:30, due to Active open failed
```
Look for: *Idle (Admin)* only appears on the side that typed `shutdown`. ISP1 just sees a neighbor that won't
answer (R1 resets its TCP attempts), so it shows the same Idle/Active cycling you'd see if the cable were cut.

Bring it back:
```
configure terminal
router bgp 65001
 no neighbor 10.1.101.101 shutdown
end
```

## Step 4 — Second ISP: MD5 authentication
ISP2's handoff sheet asks for a session password. Configure the neighbor *without* it first.

**R1**
```
configure terminal
router bgp 65001
 neighbor 10.1.102.102 remote-as 64512
 neighbor 10.1.102.102 description ISP2 (backup)
end
show ip bgp summary | begin Neighbor
show logging | include 10.1.102
```
**Output (captured)**
```
Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
10.1.101.101    4        64511       8       4       16    0    0 00:00:34        5
10.1.102.102    4        64512       0       0        1    0    0 never    Active
```
(No log lines on R1.) Now look at ISP2:

**ISP2**
```
show logging | include BADAUTH
```
**Output (captured, trimmed)**
```
%TCP-6-BADAUTH: No MD5 digest from 10.1.102.1(37905) to 10.1.102.102(179) tableid - 0
```
Look for: R1 shows only *Active*, with no reason given. The **side that has the password** is the one that logs
`BADAUTH`. "No MD5 digest" means the segment had no signature at all. A *wrong* password logs "Invalid MD5 digest".

Add the password:
```
configure terminal
router bgp 65001
 neighbor 10.1.102.102 password isp2peer
end
```
After the next retry (up to about a minute), the session is Established with 5 prefixes.

> **Why:** BGP authentication is really TCP authentication (the TCP MD5 signature option, RFC 2385). Every TCP
> segment carries a hash of the segment plus the shared key. A router that expects a signature silently drops
> segments without a valid one, so the TCP handshake never completes and BGP never even sends an OPEN. That's why
> there is no NOTIFICATION, only a TCP log message on the side that checks.

## Step 5 — Advertise the LAN (and see `network` fail)
`network` in BGP doesn't mean "enable on interfaces" like it does in OSPF. It means "advertise this prefix **if** it
is in the routing table with exactly this mask". Try a mask that doesn't match.

**R1**
```
configure terminal
router bgp 65001
 network 192.168.0.0 mask 255.255.0.0
end
show ip bgp 192.168.0.0/16
show ip route 192.168.0.0 255.255.0.0 longer-prefixes | begin Gateway
```
**Output (captured)**
```
% Network not in table

Gateway of last resort is not set

      192.168.10.0/24 is variably subnetted, 2 subnets, 2 masks
C        192.168.10.0/24 is directly connected, Ethernet0/2
L        192.168.10.1/32 is directly connected, Ethernet0/2
```
Look for: no error and no warning. The statement is accepted and silently does nothing, because there is no
`192.168.0.0/16` in the routing table, only the connected `/24`. (Typing `network 192.168.10.0 mask 255.255.0.0`
is different: IOS rejects it with `% BGP: Incorrect network or mask` because host bits are set.)

Replace it with the right one. With no `mask`, IOS assumes the classful mask, which for 192.168.10.0 is /24:
```
configure terminal
router bgp 65001
 no network 192.168.0.0 mask 255.255.0.0
 network 192.168.10.0
end
show ip bgp neighbors 10.1.101.101 advertised-routes | begin Network
```
**Output (captured)**
```
     Network          Next Hop            Metric LocPrf Weight Path
 *>   10.255.255.101/32
                      10.1.101.101             0             0 64511 i
 *>   10.255.255.102/32
                      10.1.102.102             0             0 64512 i
 *>   10.255.255.103/32
                      10.1.101.101                           0 64511 64513 i
 *>   192.168.10.0     0.0.0.0                  0         32768 i
 *>   198.51.100.0     10.1.101.101                           0 64511 64513 i
 *>   203.0.113.0      10.1.101.101                           0 64511 64513 i

Total number of prefixes 6
```
Look for: your LAN with next hop `0.0.0.0` and weight 32768 (locally originated). But look at the **other** five
lines: R1 is offering ISP1 everything it learned, *including ISP2's loopback via ISP2*. Hold that thought until
Step 8.

## Step 6 — Read the best-path decision
Now both ISPs send R1 the same internet prefixes.

**R1**
```
show ip bgp | begin Network
show ip bgp 198.51.100.0 best-path-reason
```
**Output (captured, trimmed)**
```
     Network          Next Hop            Metric LocPrf Weight Path
 *    198.51.100.0     10.1.102.102                           0 64512 64513 i
 *>                    10.1.101.101                           0 64511 64513 i

BGP routing table entry for 198.51.100.0/24, version 15
Paths: (2 available, best #2, table default)
  64512 64513
    10.1.102.102 from 10.1.102.102 (10.255.255.102)
      Origin IGP, localpref 100, valid, external
      Updated on Nov 2 2026 00:17:21 UTC
      Best Path Evaluation: Path is younger
  64511 64513
    10.1.101.101 from 10.1.101.101 (10.255.255.101)
      Origin IGP, localpref 100, valid, external, best
      Updated on Nov 2 2026 00:16:07 UTC
      Best Path Evaluation: Overall best path
```
Look for: `*` = valid, `>` = best (the one installed in the routing table). Both paths tie on everything that
matters: weight 0, local preference 100, AS path two hops, origin IGP, both external. So the decision falls to a
late tie-breaker: **for eBGP paths, keep the older one**. It chose ISP1 only because that session came up first.
`best-path-reason` (IOS-XE 17) names the step that decided. Your capture may differ if ISP2 came up first.

> **Why:** IOS walks the attributes in a fixed order and stops at the first difference:
> 1. highest **Weight** (Cisco-only, local to this router)
> 2. highest **Local preference** (shared across your AS)
> 3. **locally originated** (network / redistribute / aggregate)
> 4. shortest **AS path**
> 5. lowest **Origin** (IGP < EGP < incomplete)
> 6. lowest **MED** (by default only compared between paths from the same neighbor AS)
> 7. **eBGP over iBGP**
> 8. lowest IGP metric to the next hop
> 9. **oldest eBGP path**
> 10. lowest neighbor **router ID**, then lowest neighbor address
>
> A design that ends at step 9 is a design that depends on luck (which session came up first). Steps 7–8 fix that
> for outbound traffic.

## Step 7 — Outbound: weight, then local preference
**Weight first.** It's the very first attribute checked. Make ISP2 win everything, just to see it:

**R1**
```
configure terminal
router bgp 65001
 neighbor 10.1.102.102 weight 100
end
clear ip bgp 10.1.102.102 soft in
show ip bgp | begin Network
```
**Output (captured, trimmed)**
```
     Network          Next Hop            Metric LocPrf Weight Path
 *>   10.255.255.101/32
                      10.1.102.102                         100 64512 64513 64511 i
 *                     10.1.101.101             0             0 64511 i
 *>   198.51.100.0     10.1.102.102                         100 64512 64513 i
 *                     10.1.101.101                           0 64511 64513 i
```
Look for: even **ISP1's own loopback** now goes the long way round through ISP2, over three AS hops instead of one.
Weight is checked before AS-path length, so it wins.

> **Why the `clear ... soft in`:** policy changes (weight, inbound route-maps) only apply to updates received *after*
> the change. A soft clear re-processes the routes without dropping the session. (Modern IOS keeps an Adj-RIB-In
> copy or uses route refresh; either way, no reset.) Never use a hard `clear ip bgp *` on a production edge.

Weight never leaves R1, so it's fine for one router. With two edge routers you'd want something the whole AS shares:
**local preference**. Remove the weight and give everything learned from ISP1 local-pref 200:
```
configure terminal
route-map ISP1-IN permit 10
 set local-preference 200
router bgp 65001
 no neighbor 10.1.102.102 weight 100
 neighbor 10.1.101.101 route-map ISP1-IN in
end
clear ip bgp * soft in
show ip bgp | begin Network
show ip bgp 198.51.100.0 best-path-reason | include from|localpref|Evaluation
```
**Output (captured, trimmed)**
```
     Network          Next Hop            Metric LocPrf Weight Path
 *    10.255.255.102/32
                      10.1.102.102             0             0 64512 i
 *>                    10.1.101.101                  200      0 64511 64513 64512 i
 *    198.51.100.0     10.1.102.102                           0 64512 64513 i
 *>                    10.1.101.101                  200      0 64511 64513 i

    10.1.102.102 from 10.1.102.102 (10.255.255.102)
      Origin IGP, localpref 100, valid, external
      Best Path Evaluation: Lower local preference
    10.1.101.101 from 10.1.101.101 (10.255.255.101)
      Origin IGP, localpref 200, valid, external, best
      Best Path Evaluation: Overall best path
```
Look for: the decision is now made at step 2 ("Lower local preference"), not by session age. Even ISP2's own loopback
is reached via ISP1. That's what "primary" means. (A real design might exempt the ISP's own prefixes, but that's a
refinement.)

## Step 8 — Inbound: AS-path prepending
Local preference only controls how **you** choose. How the internet reaches *you* is the other ISPs' decision. Look
at it from ISP3:

**ISP3**
```
show ip bgp 192.168.10.0 best-path-reason
```
**Output (captured, trimmed)**
```
  64511 65001
    10.101.103.101 from 10.101.103.101 (10.255.255.101)
      Origin IGP, localpref 100, valid, external
      Best Path Evaluation: Path is younger
  64512 65001
    10.102.103.102 from 10.102.103.102 (10.255.255.102)
      Origin IGP, localpref 100, valid, external, best
      Best Path Evaluation: Overall best path
```
Look for: in this capture the internet was sending traffic for your LAN through the **backup** ISP. Return traffic
took a different path from outbound traffic, decided by a tie-breaker. You can't set local preference in someone
else's AS, but you can make the ISP2 path look worse by **prepending** your own AS to it:

**R1**
```
configure terminal
route-map ISP2-OUT permit 10
 set as-path prepend 65001 65001 65001
router bgp 65001
 neighbor 10.1.102.102 route-map ISP2-OUT out
end
clear ip bgp 10.1.102.102 soft out
```
**ISP3**
```
show ip bgp 192.168.10.0 best-path-reason
```
**Output (captured, trimmed)**
```
  64511 65001
    10.101.103.101 from 10.101.103.101 (10.255.255.101)
      Origin IGP, localpref 100, valid, external, best
      Best Path Evaluation: Overall best path
  64512 65001 65001 65001 65001
    10.102.103.102 from 10.102.103.102 (10.255.255.102)
      Origin IGP, localpref 100, valid, external
      Best Path Evaluation: Longer AS path
```
Look for: the ISP2 path is now five AS hops long, and ISP3 decides at step 4 ("Longer AS path"). The path is still
there (valid), so if ISP1 fails it's used straight away.

> **Why prepend your own AS?** Loop prevention: a router drops any path that already contains its own AS. Prepending
> 65001 is safe because nobody else is 65001. Prepending someone else's AS would make *them* drop your route.

## Step 9 — Don't be a transit AS
Remember Step 5: R1 advertised ISP2's routes to ISP1. Look at what ISP1 thinks:

**ISP1**
```
show ip bgp 10.255.255.102/32
```
Before the fix you'll see two paths, one of them `65001 64512`: ISP1 *could* send traffic for ISP2 through your
edge router and your links. Allow out only routes that start in your own AS, meaning an empty AS path (`^$`):

**R1**
```
configure terminal
ip as-path access-list 1 permit ^$
router bgp 65001
 neighbor 10.1.101.101 filter-list 1 out
 neighbor 10.1.102.102 filter-list 1 out
end
clear ip bgp * soft out
show ip bgp neighbors 10.1.101.101 advertised-routes | begin Network
```
**Output (captured)**
```
     Network          Next Hop            Metric LocPrf Weight Path
 *>   192.168.10.0     0.0.0.0                  0         32768 i

Total number of prefixes 1
```
**ISP1**
```
show ip bgp 10.255.255.102/32
```
**Output (captured, trimmed)**
```
Paths: (1 available, best #1, table default)
  64513 64512
    10.101.103.103 from 10.101.103.103 (10.255.255.103)
```
Look for: R1 advertises exactly one prefix to each ISP, and ISP1 no longer has a path through AS 65001.

> **Why `^$` and not "my prefix"?** The AS path is built as a route leaves each AS. Routes R1 originates have an
> *empty* path inside R1 (the prepend and the 65001 are added on the way out). Anything learned from an ISP already
> has an ISP AS in it. `^$` = "starts and ends with nothing" = "originated here". A prefix-list on 192.168.10.0/24
> works too. Many edges use both.

## Final check
**PC1**
```
ping -c 3 198.51.100.10
traceroute -n 198.51.100.10
```
**PC2**
```
traceroute -n 192.168.10.10
```
**Output (captured with 198.51.100.1 and 192.168.10.1, one hop short of the PCs)**
```
PC1$ traceroute -n 198.51.100.1
 1  192.168.10.1  3.181 ms  1.267 ms  0.678 ms
 2  10.1.101.101  1.296 ms  1.149 ms  0.724 ms
 3  10.101.103.103  1.641 ms  *  2.427 ms

PC2$ traceroute -n -q 1 192.168.10.1
 1  198.51.100.1  0.948 ms
 2  10.101.103.101  1.277 ms
 3  10.1.101.1  1.449 ms
```
Look for: both directions cross **ISP1** (10.1.101.x and 10.101.103.x).

Now fail the primary:

**R1**
```
configure terminal
interface Ethernet0/0
 shutdown
end
show ip bgp summary | begin Neighbor
```
**PC1**
```
traceroute -n -q 1 198.51.100.10
```
**Output (captured, traceroute toward 198.51.100.1)**
```
Neighbor        V           AS MsgRcvd MsgSent   TblVer  InQ OutQ Up/Down  State/PfxRcd
10.1.101.101    4        64511       0       0        1    0    0 00:00:15 Idle
10.1.102.102    4        64512      31      36       38    0    0 00:10:07        5

 1  192.168.10.1  0.945 ms
 2  10.1.102.102  1.127 ms
 3  10.102.103.103  1.787 ms
```
Traffic moves to ISP2 within seconds, because the interface going down resets the session at once (fast external
fallover). If ISP1 failed somewhere *behind* a link that stays up, you'd wait for the 180-second hold timer instead.
Bring `Ethernet0/0` back up when you're done.

> **Testing from R1 itself:** `ping 198.51.100.1` from R1 fails unless you add `source Ethernet0/2`. Without a source,
> R1 uses the outgoing link address (10.1.101.1), and the link subnets aren't advertised into BGP, so ISP3 can't
> reply. Only `192.168.10.0/24` is.

## Check yourself
- In Step 2 the log said `FBFF`. What would it say if you'd typed 64511 but ISP1 were really in AS 64513?
- Why does only ISP2 log anything when the MD5 password is missing on R1?
- `network 192.168.10.0 mask 255.255.255.0` and `network 192.168.10.0` — same result here? Why?
- Weight 100 toward ISP2 beat a one-hop AS path via ISP1. Which attribute would beat weight? (Trick question.)
- You set local-pref 200 on routes **from** ISP1. Does ISP3 see that 200 anywhere? Why not?
- ISP2 is told about your LAN with `64512 65001 65001 65001 65001` at ISP3. What does ISP2 itself see?
- If you removed `filter-list 1 out` toward ISP1 only, which prefixes would ISP1 receive from you?

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1 | IOL-XE router (yours, AS 65001) | cisco | cisco | cisco |
| ISP1, ISP2, ISP3 | IOL-XE routers (providers, preconfigured; look, don't change) | cisco | cisco | cisco |
| PC1, PC2 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → Console). Routers start in privileged EXEC.
Each node also has a label in the CML canvas with its login and addresses.

## Topology

```
                         AS 64511 (primary)
                      e0/0 ISP1 e0/1
                     /               \
          10.1.101.0/24         10.101.103.0/24
                 e0/0                 e0/0
 PC1 ── e0/2  R1  AS 65001        ISP3  AS 64513 e0/2 ── PC2
192.168.10.0/24  e0/1                 e0/1         198.51.100.0/24
          10.1.102.0/24         10.102.103.0/24     Lo1 203.0.113.1/24
                     \               /
                      e0/0 ISP2 e0/1
                         AS 64512 (backup)
```

## Addressing

| Node | Interface | IPv4 | Connects to |
|---|---|---|---|
| R1 | Loopback0 | 10.255.255.1/32 | — |
| R1 | Ethernet0/0 | 10.1.101.1/24 | ISP1 e0/0 |
| R1 | Ethernet0/1 | 10.1.102.1/24 | ISP2 e0/0 |
| R1 | Ethernet0/2 | 192.168.10.1/24 | PC1 |
| ISP1 | Loopback0 | 10.255.255.101/32 | — |
| ISP1 | Ethernet0/0 | 10.1.101.101/24 | R1 e0/0 |
| ISP1 | Ethernet0/1 | 10.101.103.101/24 | ISP3 e0/0 |
| ISP2 | Loopback0 | 10.255.255.102/32 | — |
| ISP2 | Ethernet0/0 | 10.1.102.102/24 | R1 e0/1 |
| ISP2 | Ethernet0/1 | 10.102.103.102/24 | ISP3 e0/1 |
| ISP3 | Loopback0 | 10.255.255.103/32 | — |
| ISP3 | Loopback1 | 203.0.113.1/24 | simulated internet prefix |
| ISP3 | Ethernet0/0 | 10.101.103.103/24 | ISP1 e0/1 |
| ISP3 | Ethernet0/1 | 10.102.103.103/24 | ISP2 e0/1 |
| ISP3 | Ethernet0/2 | 198.51.100.1/24 | PC2 |
| PC1 | eth0 | 192.168.10.10/24, gw .1 | R1 e0/2 |
| PC2 | eth0 | 198.51.100.10/24, gw .1 | ISP3 e0/2 |

| Router | BGP AS | Router ID | Originates |
|---|---|---|---|
| R1 | 65001 | 10.255.255.1 | 192.168.10.0/24 (you configure this) |
| ISP1 | 64511 | 10.255.255.101 | 10.255.255.101/32 |
| ISP2 | 64512 | 10.255.255.102 | 10.255.255.102/32 |
| ISP3 | 64513 | 10.255.255.103 | 10.255.255.103/32, 198.51.100.0/24, 203.0.113.0/24 |

Addressing note: PC1's LAN uses a private range and PC2's uses a documentation range so the lab follows the repo's
conventions. A real internet edge would advertise a public block (and NAT the private LAN).
