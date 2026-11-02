# EtherChannel (LACP, PAgP, L3) — Solution (ts-etherchannel)

> Spoilers below. Try the hints first, one at a time.

## Hints

<details><summary>Hint 1 — where to look</summary>

Run `show etherchannel summary` on every switch and compare both ends of each bundle. A bundle that is up on one
end and down on the other is worth more attention than one that is down on both. Then read `show logging` for
`%ETC-` messages on each switch.
</details>

<details><summary>Hint 2 — what to compare</summary>

- For each bundle, check which protocol each end runs (the Protocol column) and which mode each member uses
  (`show running-config interface`).
- LACP and PAgP modes are set per **member port**, not per port-channel. Check every member, not just the first.
- A member that's suspended `(s)` with the protocol matching on both ends usually means its config differs from its
  siblings. The log tells you which setting.
- Once a bundle is up on both ends, check what it carries: `show interfaces trunk`.
</details>

<details><summary>Hint 3 — almost there</summary>

- `mode on` sends no LACPDUs. An LACP `active` partner suspends its ports when it hears none, while the `on` end
  happily forwards into them.
- LACP and PAgP don't talk to each other.
- `passive` only answers. Two passive ports never start a conversation.
- An L2 port-channel's trunk settings must match every member's, and the port-channel's allowed list is what
  actually gets carried.
</details>

## Faults

| # | Device | Fault | Breaks |
|---|---|---|---|
| 1 | SW3 | Po2 members `channel-group 2 mode on` | PC1 (Po2 up on SW3, suspended on SW1) |
| 2 | SW3 | e0/1 allowed VLANs `10,20` | Po2 runs on one link (hidden behind fault 1) |
| 3 | SW4 | Po3 members `channel-group 3 mode active` (LACP) | PC2 (LACP facing PAgP) |
| 4 | SW2 | Po3 and its members allow VLANs `10,99` | PC2 (hidden behind fault 3) |
| 5 | SW1 + SW5 | Po4's second link `passive` on both ends | Po4 runs on one link |

### Fault 1: static bundle facing LACP (SW3)
- **Where:** SW3, Ethernet0/0 and Ethernet0/1.
- **Injected config:** `channel-group 2 mode on` (designed: `mode passive`).
- **Why it breaks:** `mode on` bundles unconditionally and sends no LACPDUs. SW1's members are LACP `active`, hear
  nothing back, and suspend themselves. So SW3 believes Po2 is up and forwards PC1's traffic into it, and SW1 drops
  all of it. The Protocol column gives it away: `-` on SW3, `LACP` on SW1.
- **Evidence (Captured):**
  ```
  SW3# show etherchannel summary | begin Group
  Group  Port-channel  Protocol    Ports
  2      Po2(SU)          -          Et0/0(P)        Et0/1(s)

  SW1# show etherchannel summary | begin Group
  1      Po1(SU)         LACP        Et0/0(P)        Et0/1(P)
  2      Po2(SD)         LACP        Et0/2(s)        Et0/3(s)

  SW1# show logging | include ETC
  %ETC-5-L3DONTBNDL2: Et0/3 suspended: LACP currently not enabled on the remote port.
  %ETC-5-L3DONTBNDL2: Et0/2 suspended: LACP currently not enabled on the remote port.

  PC1:~$ ping -c 3 192.168.10.1
  3 packets transmitted, 0 packets received, 100% packet loss
  ```
  No err-disable happened here: the EtherChannel misconfig guard never fired, because SW1's suspended ports send no
  BPDUs for SW3 to compare.
- **Fix:** IOS won't switch a port between `on` and LACP in place (`Command rejected: is already part of a channel
  with a different type of protocol enabled`), so remove it from the group first.
  ```
  SW3(config)# interface range Ethernet0/0 - 1
  SW3(config-if-range)# no channel-group
  SW3(config-if-range)# channel-group 2 mode passive
  ```
  **PC1 recovers, but Po2 runs on one link.** See fault 2.

### Fault 2: one member's trunk config differs (SW3)
- **Where:** SW3, Ethernet0/1.
- **Injected config:** `switchport trunk allowed vlan 10,20` (designed: `10,20,99`, the same as Po2 and e0/0).
- **Why it breaks:** members of a bundle must be configured identically. SW3 suspends e0/1 because its VLAN list
  differs from the port-channel's, and the far end (SW1 e0/3) then hears no LACP on that link and suspends too. The
  log on SW3 named this from the start, but with fault 1 in place it didn't matter: the whole bundle was dead.
- **Evidence (Captured):**
  ```
  SW3# show logging | include ETC
  %ETC-5-CANNOT_BUNDLE2: Et0/1 is not compatible with Et0/0 and will be suspended (vlan mask is different)
  %ETC-5-CANNOT_BUNDLE2: Et0/1 is not compatible with Po2 and will be suspended (vlan mask is different)

  SW3# show etherchannel summary | begin Group               (after fixing fault 1)
  2      Po2(SU)         LACP        Et0/0(P)        Et0/1(s)

  SW1# show etherchannel summary | begin Group
  2      Po2(SU)         LACP        Et0/2(P)        Et0/3(s)

  PC1:~$ ping -c 3 192.168.10.1        3 packets transmitted, 3 packets received, 0% packet loss
  ```
- **Fix:**
  ```
  SW3(config)# interface Ethernet0/1
  SW3(config-if)# switchport trunk allowed vlan 10,20,99
  ```
  The member rejoins on its own. Configure trunk settings on the port-channel and let them flow down to the members,
  rather than editing members one at a time.

### Fault 3: LACP facing PAgP (SW4)
- **Where:** SW4, Ethernet0/0 and Ethernet0/1.
- **Injected config:** `channel-group 3 mode active` (designed: `mode auto`, PAgP).
- **Why it breaks:** SW2 speaks PAgP (`desirable`) and SW4 speaks LACP (`active`). Neither understands the other.
  SW4's LACP members get no LACPDUs and suspend. SW2's PAgP members fall back to stand-alone `(I)` and keep
  forwarding individually, into ports that SW4 has suspended. PC2's VLAN never leaves SW4.
- **Evidence (Captured):**
  ```
  SW4# show etherchannel summary | begin Group
  3      Po3(SD)         LACP        Et0/0(s)        Et0/1(s)

  SW4# show logging | include ETC
  %ETC-5-L3DONTBNDL2: Et0/1 suspended: LACP currently not enabled on the remote port.
  %ETC-5-L3DONTBNDL2: Et0/0 suspended: LACP currently not enabled on the remote port.

  SW2# show etherchannel summary | begin Group
  1      Po1(SU)         LACP        Et0/0(P)        Et0/1(P)
  3      Po3(SD)         PAgP        Et0/2(I)        Et0/3(I)

  PC2:~$ ping -c 3 192.168.20.1        3 packets transmitted, 0 packets received, 100% packet loss
  ```
- **Fix:**
  ```
  SW4(config)# interface range Ethernet0/0 - 1
  SW4(config-if-range)# no channel-group
  SW4(config-if-range)# channel-group 3 mode auto
  ```
  Right after the change both ends showed the ports `(I)` and Po3 `(SD)`; PAgP bundled them within a minute. **PC2 still
  fails.** See fault 4.

### Fault 4: VLAN 20 missing from SW2's Po3
- **Where:** SW2, Port-channel3 and its members Ethernet0/2 and Ethernet0/3.
- **Injected config:** `switchport trunk allowed vlan 10,99` on all three (designed: `10,20,99`).
- **Why it breaks:** this is a consistent change on the port-channel and both members, so nothing gets suspended
  and the bundle is perfectly healthy. It just doesn't carry Engineering. VLANs 10 and 99 keep working, so SW4 is
  still manageable while PC2 is dead.
- **Evidence (Captured, after fixing fault 3):**
  ```
  SW2# show etherchannel summary | begin Group
  1      Po1(SU)         LACP        Et0/0(P)        Et0/1(P)
  3      Po3(SU)         PAgP        Et0/2(P)        Et0/3(P)

  SW2# show interfaces trunk
  Port           Vlans allowed on trunk
  Po1            10,20,99
  Po3            10,99

  SW4# show interfaces trunk
  Port           Vlans allowed on trunk
  Po3            10,20,99

  SW4# ping 192.168.99.1               !!!!!   Success rate is 100 percent (5/5)
  PC2:~$ ping -c 3 192.168.20.1        3 packets transmitted, 0 packets received, 100% packet loss
  ```
- **Fix:** on the port-channel. IOS copies it to the members.
  ```
  SW2(config)# interface Port-channel3
  SW2(config-if)# switchport trunk allowed vlan add 20
  SW2(config-if)# do show running-config interface Ethernet0/3 | include allowed
   switchport trunk allowed vlan 10,20,99
  ```

### Fault 5: one Po4 link passive on both ends (SW1 and SW5)
- **Where:** SW1 Ethernet1/1 and SW5 Ethernet0/1 (the same physical link).
- **Injected config:** `channel-group 4 mode passive` on both (designed: `mode active` on both). The other Po4 link
  is still active/active.
- **Why it breaks:** LACP mode is per member port. `passive` only replies to LACPDUs and never starts. With both
  ends of that one link passive, nobody speaks, so both ends suspend it. Po4 stays up on the other link, so routing
  and the Internet work; only the redundancy and half the bandwidth are gone.
- **Evidence (Captured; injected live during testing, see testing notes):**
  ```
  SW5# show etherchannel summary | begin Group
  4      Po4(RU)         LACP        Et0/0(P)        Et0/1(s)

  SW5# show lacp 4 internal | begin Port
  Port          Flags   State     Priority     Key       Key     Number      State
  Et0/0         SA      bndl      32768        0x4       0x4     0x1         0x3D
  Et0/1         SP      susp      32768        0x4       0x4     0x2         0x7C

  SW1# show logging | include ETC
  %ETC-5-L3DONTBNDL2: Et1/1 suspended: LACP currently not enabled on the remote port.

  SW5# ping 10.1.5.1                   !!!!!   Success rate is 100 percent (5/5)
  ```
  Flags `SP` = slow LACPDUs, **P**assive mode.
- **Fix:** making either end active is enough to bring the link up. The design says active on both.
  ```
  SW1(config)# interface Ethernet1/1
  SW1(config-if)# channel-group 4 mode active
  SW5(config)# interface Ethernet0/1
  SW5(config-if)# channel-group 4 mode active
  ```
  Changing modes within LACP is accepted in place; no `no channel-group` needed.

## Why the ticket looked the way it did
- **PC1** is down because of fault 1 alone. Fixing it brings PC1 back, but Po2 stays at one link because of fault 2.
  The ticket didn't mention Po2: monitoring couldn't see it because the bundle was half up on SW3 and down on SW1.
- **PC2** needs faults 3 and 4 fixed. Fault 4 only shows once the bundle forms: a healthy-looking `(SU)` bundle that
  still doesn't carry VLAN 20.
- **Po4 on one link** is fault 5. The Internet was never actually down; the PCs just couldn't reach SW1.

## Final configs
[`configs/`](configs/): the fixed, intended configuration of every node.

## Verifying the fix (Captured)
Tested in two passes (5-node license): SW5, SW1, SW2, SW3, PC1, then SW5, SW1, SW2, SW4, PC2 with SW3 and PC1 stopped.
```
SW1# show etherchannel summary | begin Group           (pass 1, after all its fixes)
1      Po1(SU)         LACP        Et0/0(P)        Et0/1(P)
2      Po2(SU)         LACP        Et0/2(P)        Et0/3(P)
4      Po4(RU)         LACP        Et1/0(P)        Et1/1(P)

SW3# show etherchannel summary | begin Group
2      Po2(SU)         LACP        Et0/0(P)        Et0/1(P)

PC1:~$ ping -c 3 192.168.10.1        3 packets transmitted, 3 packets received, 0% packet loss
PC1:~$ ping -c 3 203.0.113.1         3 packets transmitted, 3 packets received, 0% packet loss

SW2# show etherchannel summary | begin Group           (pass 2)
1      Po1(SU)         LACP        Et0/0(P)        Et0/1(P)
3      Po3(SU)         PAgP        Et0/2(P)        Et0/3(P)

SW4# show etherchannel summary | begin Group
3      Po3(SU)         PAgP        Et0/0(P)        Et0/1(P)

SW5# show etherchannel summary | begin Group
4      Po4(RU)         LACP        Et0/0(P)        Et0/1(P)

PC2:~$ ping -c 3 192.168.20.1        3 packets transmitted, 3 packets received, 0% packet loss
PC2:~$ ping -c 3 203.0.113.1         3 packets transmitted, 3 packets received, 0% packet loss
PC2:~$ ping -c 3 192.168.99.204      3 packets transmitted, 2 packets received   (first ping lost to ARP)
```
**Expected (not run):** `PC1:~$ ping -c 3 192.168.20.10`. PC1 and PC2 were never up at the same time; each one's
path to SW1 was proven in its own pass, and SW1 routes between VLAN 10 and 20 locally.

## Testing notes
- The first version of fault 5 put SW1 e1/1 in the wrong group (`channel-group 5`). SW5 then saw two partners with
  different LACP keys and bundled whichever link synced first. In the test that was the link to SW1's empty Po5,
  which took the Internet down entirely. Because the outcome was a race, the fault was replaced with the
  deterministic per-link passive/passive one, injected live and captured above. The shipped startup configs carry
  the passive version.
- IOL-L2-XE 17.18 has no `port-channel min-links`, and it accepts `lacp max-bundle` but silently drops it (it never
  appears in the running config). Neither is used here.
- IOL-XE (router) rejects `channel-group` on its Ethernet ports with `Invalid channel group number`, which is why
  SW5 is an L3 switch rather than a router.
- `show pagp` doesn't exist on IOL-L2; use `show etherchannel <n> detail`.
- About 60 s after boot the PnP agent ("Config Wizard") adds `no logging console`. Use `show logging`.
