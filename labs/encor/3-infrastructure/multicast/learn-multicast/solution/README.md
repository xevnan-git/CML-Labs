# Multicast (PIM-SM, IGMP, SSM) — Solution (learn-multicast)

## Final configs
[`configs/`](configs/): every node as it should look after Step 10 (SRV1 doesn't change). In short:
- R1, R2, R3: `ip multicast-routing`; `ip pim sparse-mode` on Loopback0 and every Ethernet interface in use;
  `ip pim rp-address 10.255.255.2`; `ip pim ssm default`; `ip pim bidir-enable` with
  `ip pim rp-address 10.255.255.1 BIDIR-GROUPS bidir` (ACL permits 239.2.0.0 0.0.255.255).
- R3 Ethernet0/0: `ip igmp version 3`.
- R1 ↔ R2: `ip msdp peer <other Lo0> connect-source Loopback0`.
- PC1 Ethernet0/0: `ip igmp version 3`, `ip igmp join-group 239.1.1.1`, `ip igmp join-group 239.2.2.2`,
  `ip igmp join-group 232.1.1.1 source 192.168.10.10`.
- Steps 6 and 7 are experiments that you undo: no `spt-threshold` and no static mroute in the final configs.

## How this was tested
On the dev server (5-node license), CML 2.10.1, IOL-XE 17.18.2. The lab is 5 licensed nodes, so it ran whole:
Steps 1–10, every command as written in the guide. All output in the guide is **Captured** from that run. The
final configs were then booted as the troubleshooting lab's startup configs (with its faults) and verified working
once the faults were fixed, so they also load cleanly at boot.

Notes from the run:
- **No RP (Step 3):** R3 created (\*,239.1.1.1) with RP 0.0.0.0 and incoming Null; R1 created no state at all for
  SRV1's packets.
- **`clear ip mroute *` on R3** removes the IGMP-derived (\*,G) too; it came back with PC1's next report, after
  about a minute, so a ping straight after the clear failed.
- **RPF drops in Step 6:** R3 counted `Other: 10/5/0` (5 RPF failures). R1's old SPT branch toward R3 was still in
  its outgoing list (expiring in 50 s) after only R3's state was cleared, so each packet arrived twice.
- **Both ends without PIM (Step 7):** `show ip rpf` on R3 said `failed, no route exists` for the RP: the RPF lookup
  skips interfaces without PIM even though OSPF routes over them.
- **One end without PIM, source side:** with PIM removed only on R1's Ethernet0/2 (R3's side still running PIM), R3
  kept an (S,G) with **J** but no **T**, incoming Ethernet0/1, and the traffic kept arriving on the shared tree via
  R2 with no loss. IOS-XE doesn't drop the shared-tree packets until the SPT is actually in use. With PIM removed
  on both ends of that link, the RPF lookup failed and R3 also stayed on the shared tree.
- **IGMPv2 host and SSM (Step 8):** `ip igmp join-group 232.1.1.1 source 192.168.10.10` is accepted on a v2 host,
  but nothing is reported. A v3-configured host shows `host version 2` while its querier runs v2, and recovered to
  v3 about 90 s after the querier was changed (seen in the troubleshooting lab).
- **Bidir and MSDP are supported** on IOL-XE 17.18.2: DF election, `B` flags and `Bidir-Upstream` as shown;
  MSDP peering came up after about a minute and the SA cache filled on the first ping.
- **Duplicate replies** (`Reply to request 1` twice or three times) appear at the start of a stream while packets
  travel both inside registers and natively.

## Check yourself — answers
- **LAN interface needs PIM:** `ip pim sparse-mode` is what enables IGMP on the interface. Without it R3 ignores
  PC1's reports (Fault 1 in the troubleshooting lab).
- **Step 3's missing piece:** an RP. R3 had no RP to join toward (incoming Null), and R1 had no RP to register the
  source with, so it dropped the packets.
- **RP mismatch:** the receivers behind that router get a shared tree rooted at the wrong place. With
  10.255.255.3 on R3, R3 roots the tree at itself while R1 registers sources with R2: they never meet (Fault 2).
- **Flags:** **F** register (R1, the source's first hop), **J** join the SPT (R3's (S,G) and (\*,G)), **T** the
  SPT is in use (R1, R2 before the prune, R3), **P** pruned (R2's (S,G) after R3 left the shared tree; R1's (\*,G)
  with no shared-tree receivers).
- **RPF interface:** toward the **RP** for a (\*,G); toward the **source** for an (S,G).
- **232.1.1.1 with IGMPv2:** a v2 report can't name a source, and in the SSM range a group without a source means
  nothing. With v3, R3 joined (192.168.10.10, 232.1.1.1) directly toward R1; SSM never uses an RP (Fault 5).
- **ACL `239.0.0.0 0.0.255.255`:** no. It covers only 239.0.0.0/16, so R1 has no RP for 239.1.1.1 and drops the
  traffic (Fault 3).
- **Bidir instead of RPF:** a **designated forwarder** per link, elected by best metric to the RP.
