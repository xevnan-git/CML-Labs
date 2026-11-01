# 802.1Q Trunking and EtherChannel — Troubleshooting Lab

> **Blueprint:** ENCOR 3.1.a — Troubleshoot static and dynamic 802.1q trunking protocols; ENCOR 3.1.b — Troubleshoot
> static and dynamic EtherChannels
> **Mode:** Troubleshooting · **Nodes:** 7 licensed (4 switches, 3 PCs) · **Faults:** 4 · **Difficulty:** 2 of 3

## Ticket

> **#5120 — Both access closets down after last night's uplink cleanup**
> "Last night's change 'cleaned up' the uplink configs on all four switches. This morning nobody on SW3 (PC1 in
> Sales, PC2 in Engineering) or SW4 (PC3 in Sales) can reach their default gateway. The monitoring system is
> also alarming on two port-channels. The change engineer says every uplink cable is connected and every link light
> is green. SW1 and SW2 both look healthy to them."

## Done when
- `PC1:~$ ping -c 3 192.168.10.1`, `PC2:~$ ping -c 3 192.168.20.1` and `PC3:~$ ping -c 3 192.168.10.1` all succeed.
- `PC1:~$ ping -c 3 192.168.20.10` (Sales to Engineering, routed by SW1) succeeds.
- `show etherchannel summary` shows Po1, Po2 and Po3 as **(SU)** with both member ports **(P)** on both ends.
- `show interfaces trunk` lists every inter-switch link in the design below as **trunking**, each with
  VLANs 10, 20 and 99 allowed and native VLAN 999.

## Rules
- Fix with the smallest change that restores the intended design; don't redesign. Don't replace a dynamic link
  with a static trunk, or a negotiated bundle with `mode on`.
- There's more than one fault, and some symptoms have more than one cause.
- Hints and the full solution are in the lab repository (`solution/README.md` in this lab's folder), not in CML.

## Intended design
- **VLANs** (defined on every switch, VTP **transparent** mode, VTP domain `LAB` on all four switches):
  10 SALES, 20 ENGINEERING, 99 MGMT, 999 NATIVE-UNUSED.
- **Every trunk** is 802.1Q, carries only VLANs **10, 20, 99**, and uses native VLAN **999**.
- **SW1** (distribution) is the gateway for all VLANs (SVIs, `ip routing`) and the Rapid-PVST root (priority 4096).
  **SW2** (distribution) is the backup root (priority 8192).
- **Uplinks:**

  | Link | Ports | How it's built |
  |---|---|---|
  | Po1 SW1–SW2 | SW1 e0/0-1 ↔ SW2 e0/0-1 | LACP, **active** on both ends |
  | Po2 SW1–SW3 | SW1 e0/2-3 ↔ SW3 e0/0-1 | LACP, SW1 **active**, SW3 **passive** |
  | Po3 SW2–SW4 | SW2 e1/0-1 ↔ SW4 e0/0-1 | PAgP, SW2 **desirable**, SW4 **auto** |
  | SW2–SW3 | SW2 e0/2 ↔ SW3 e0/2 | single link, **DTP**: SW2 `dynamic desirable`, SW3 `dynamic auto` |
  | SW1–SW4 | SW1 e1/0 ↔ SW4 e0/2 | single link, **static** trunk, DTP off (`nonegotiate`) both ends |

- Port-channels and their member ports are configured as static trunks (`switchport mode trunk`).
- Access ports: SW3 e1/0 → PC1 (VLAN 10), SW3 e1/1 → PC2 (VLAN 20), SW4 e1/0 → PC3 (VLAN 10). PortFast on all three.

## Expected behavior (healthy network)
- Every port-channel is `(SU)` with both members `(P)`.
- SW2 e0/2 and SW3 e0/2 show Mode `desirable` / `auto` and Status `trunking` in `show interfaces trunk`.
- Spanning tree has exactly two blocked (alternate) ports in each user VLAN: SW3 e0/2 and SW4 Po3. Both access
  switches use their direct uplink to SW1 as the root port.
- Every switch can ping every other switch's VLAN 99 address, and every PC can ping its gateway and the other PCs.

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| SW1–SW4 | IOL-L2-XE switch | cisco | cisco | cisco |
| PC1–PC3 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → **Console**). Switches drop you straight into privileged EXEC.
Each node also has a label on the CML canvas with its login and addresses.

## Topology

```
                   e0/0-1      Po1 (LACP)      e0/0-1
              SW1 ===================================== SW2
         root, gateway                                backup root
    e0/2-3 ||   e1/0 `.                          .' e0/2   || e1/0-1
           ||          `.  static trunk       .'           ||
     Po2   ||            `.                .'   DTP        ||   Po3
    (LACP) ||              `.           .'                 ||  (PAgP)
           ||                `.      .'                    ||
           ||                  `. .'                       ||
           ||                  .' `.                       ||
           ||                .'      `.                    ||
    e0/0-1 ||         e0/2 .'          `. e0/2             || e0/0-1
              SW3 --------'              `-------------- SW4
            e1/0  e1/1                                   e1/0
             |      |                                     |
            PC1    PC2                                   PC3
          VLAN 10 VLAN 20                              VLAN 10
```

## Addressing (as designed)

| Node | Interface | IPv4 | Notes |
|---|---|---|---|
| SW1 | Vlan10 | 192.168.10.1/24 | Sales gateway |
| SW1 | Vlan20 | 192.168.20.1/24 | Engineering gateway |
| SW1 | Vlan99 | 192.168.99.1/24 | Management gateway |
| SW2 | Vlan99 | 192.168.99.202/24 | default-gateway 192.168.99.1 |
| SW3 | Vlan99 | 192.168.99.203/24 | default-gateway 192.168.99.1 |
| SW4 | Vlan99 | 192.168.99.204/24 | default-gateway 192.168.99.1 |
| PC1 | eth0 | 192.168.10.10/24, gw .1 | SW3 e1/0, VLAN 10 |
| PC2 | eth0 | 192.168.20.10/24, gw .1 | SW3 e1/1, VLAN 20 |
| PC3 | eth0 | 192.168.10.11/24, gw .1 | SW4 e1/0, VLAN 10 |
