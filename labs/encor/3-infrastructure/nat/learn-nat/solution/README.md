# NAT and PAT — Solution (learn-nat)

## Final configs
[`configs/`](configs/): every node as it should look after Step 6 (ISP1 and the hosts don't change):
- R1: `ip nat inside` on e0/0 and e0/1, `ip nat outside` on e0/2
- R1: ACL NAT-INSIDE (192.168.10.0/24, 192.168.20.0/24), `ip nat pool NAT-POOL 198.51.100.1 198.51.100.1
  prefix-length 28`, `ip nat inside source list NAT-INSIDE pool NAT-POOL overload`
- R1: port forwards `static tcp 192.168.20.10 80 198.51.100.14 80` and `static tcp 192.168.20.10 22
  198.51.100.14 2222` (both `extendable`)
- R1: ACL OUTSIDE-IN inbound on e0/2, written against 198.51.100.14

## How this was tested
On the dev server (5-node license), CML 2.10.1, IOL-XE 17.18.2, Alpine 3.23. The lab is 5 licensed nodes, so it
ran whole: Steps 1–7, every command as written in the guide. All output in the guide is **Captured** from that run.

Notes from the run:
- **Changing NAT that's in use.** SRV1's monitoring ping (every 10 s) keeps a translation alive, which is realistic
  and shows two IOS protections:
  - Removing a static entry with active child translations prompts `Static entry in use, do you want to delete
    child entries? [no]:`. Answering no (or nothing) leaves it: `%: Error: static entry in use, cannot remove`.
  - Changing `ip nat inside source list … pool …` (adding `overload`) while it has translations is refused:
    `%Dynamic mapping in use, cannot change`. An exec-mode `clear ip nat translation *` followed by a separate
    config session was too slow (SRV1 re-created an entry first); `do clear ip nat translation *` followed
    immediately by the command in the same config session worked every time. The troubleshooting lab's pool change
    was done the same way.
- `clear ip nat translation *` doesn't remove static entries, only dynamic ones and the children of statics.
- The OUTSIDE-IN ACL written against 192.168.20.10 was hit by the `deny` (1 match) and PC2's wget reported
  `Host is unreachable`, which shows the inbound ACL runs before outside-to-inside translation.
- `clear logging` on IOL-XE 17.18 prints `Error: Failed to set Clear Logging Chasfs Property` and asks to confirm;
  harmless. The guide doesn't use it.

## Final verification (Captured)
```
R1# show running-config | include ip nat|access-group
 ip nat inside
 ip nat inside
 ip nat outside
 ip access-group OUTSIDE-IN in
ip nat pool NAT-POOL 198.51.100.1 198.51.100.1 prefix-length 28
ip nat inside source static tcp 192.168.20.10 80 198.51.100.14 80 extendable
ip nat inside source static tcp 192.168.20.10 22 198.51.100.14 2222 extendable
ip nat inside source list NAT-INSIDE pool NAT-POOL overload

R1# show ip access-lists
Standard IP access list NAT-INSIDE
    10 permit 192.168.10.0, wildcard bits 0.0.0.255 (12 matches)
    20 permit 192.168.20.0, wildcard bits 0.0.0.255 (24 matches)
Extended IP access list OUTSIDE-IN
    10 permit tcp any host 198.51.100.14 eq www (5 matches)
    20 permit tcp any host 198.51.100.14 eq 2222 (5 matches)
    30 permit icmp any any (146 matches)
    40 permit tcp any any established (4 matches)
    50 deny ip any any (1 match)

R1# show ip nat statistics
Total active translations: 11 (2 static, 9 dynamic; 11 extended)
Outside interfaces:
  Ethernet0/2
Inside interfaces:
  Ethernet0/0, Ethernet0/1
Hits: 168  Misses: 0
CEF Translated packets: 168, CEF Punted packets: 65
 Dynamic overload mapping configured: 1
Expired translations: 35
Dynamic mappings:
-- Inside Source
[Id: 1] access-list NAT-INSIDE pool NAT-POOL refcount 9
 pool NAT-POOL: id 1, netmask 255.255.255.240
        start 198.51.100.1 end 198.51.100.1
        type generic, total addresses 1, allocated 1 (100%), misses 3
```
The `misses 3` are left over from Step 4.

## Check yourself — answers
- **Inside/outside swapped:** traffic from PC1 to the internet now goes outside → inside, so `ip nat inside
  source` never translates it; PC1's private source reaches ISP1 and the reply is dropped there.
  `show ip nat statistics` lists the swapped interfaces. (This is Fault 1 in the troubleshooting lab.)
- **`0.0.0.7`:** only 192.168.10.0–.7 match. PC1 (.10) isn't translated and leaves with its private address.
  NAT-INSIDE line 10 doesn't count PC1's packets, and the pool shows no misses for it.
- **Pool 198.51.100.17:** R1 translates PC1 to .17, but ISP1 routes only 198.51.100.0/28 (.0–.15) to R1. The
  replies to .17 have no route at ISP1 and are dropped. The mask check (`prefix-length 28`) passes, because .17 is
  valid in its own /28 (198.51.100.16/28).
- **Without overload:** one host per pool address at a time. The next host is a pool miss until the first
  host's translation times out or is cleared.
- **198.51.100.14 in OUTSIDE-IN:** an inbound ACL on the outside interface sees the packet before NAT translates
  the destination.
- **`---` in a static entry:** it's the static mapping itself, not a flow, so there's no outside host. Flows that use
  it appear as separate lines with the outside addresses filled in.
- **Inside port 8080:** R1 forwards PC2's SYN to SRV1 port 8080, where nothing listens; SRV1 replies with a TCP
  reset, so wget says `Connection refused`. (This is Fault 5 in the troubleshooting lab.)
