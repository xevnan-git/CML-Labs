# MST and STP Guards — Troubleshooting Lab

> **Blueprint:** ENCOR 3.1.c — Configure and verify common Spanning Tree Protocols (RSTP, MST) and Spanning Tree
> enhancements such as root guard and BPDU guard
> **Mode:** Troubleshooting · **Nodes:** 6 licensed (4 switches, 2 PCs) · **Faults:** 4 · **Difficulty:** 3 of 3

## Ticket

> **#5187 — Engineering PC offline after the spanning-tree "hardening" change**
> "Last night's change 'hardened spanning tree' on the campus switches: MST everywhere, root guard, BPDU guard.
> This morning PC2 (Engineering, on SW4) can't reach its gateway or anything else. Sales (PC1 on SW3) is working
> fine, so the change engineer thinks the problem is just SW4's cabling. Every link light on SW4 is green."

## Done when
- `PC2:~$ ping -c 3 192.168.20.1` and `PC1:~$ ping -c 3 192.168.10.1` both succeed, and `PC1:~$ ping -c 3 192.168.20.10` succeeds.
- `show spanning-tree root` on any switch shows **MST0 and MST1 rooted at SW1** and **MST2 rooted at SW2**.
- `show spanning-tree mst configuration digest` is **identical** on all four switches.
- No port is err-disabled or root-inconsistent (`show interfaces status err-disabled`,
  `show spanning-tree inconsistentports`).
- Every protection in the intended design below is still configured in its intended place.

## Rules
- Fix with the smallest change that restores the intended design. Don't remove a protection that belongs where it is.
- There's more than one fault, and fixing one may reveal the next.
- Hints and the full solution are in the lab repository (`solution/README.md` in this lab's folder), not in CML.

## Intended design
- **STP mode:** MST on all four switches, one region:
  - name **`LAB`**, revision **1**
  - instance **1** = VLAN 10, instance **2** = VLAN 20, everything else (including VLAN 99) in instance 0
- **Roots:** SW1 priority 4096 for MST 0–1, 8192 for MST 2. SW2 priority 8192 for MST 0–1, 4096 for MST 2.
  SW3 and SW4 keep the default priority (32768) for every instance.
- **Root guard** on the distribution switches' **downlinks** to the access layer: SW1 e0/1, e0/2 and SW2 e0/1,
  e0/2. An access switch must never become root of anything.
- **PortFast + BPDU guard** on the PC ports only: SW3 e1/0 and SW4 e1/0. Uplinks are normal (non-edge) trunks with
  no guards on the access-switch side.
- VLANs 10 (SALES), 20 (ENGINEERING), 99 (MGMT), native 999. All inter-switch links are 802.1Q trunks allowing
  10, 20, 99. SW1 is the gateway for every VLAN.

## Expected behavior (healthy network)
- On SW3 and SW4: in MST1 (VLAN 10) the uplink to **SW1** (e0/0) is the root port and e0/1 is Alternate. In MST2
  (VLAN 20) it's the other way round: e0/1 (to SW2) is the root port and e0/0 is Alternate.
- No `Bound` flags in `show spanning-tree mst`. It's all one region.
- Every switch can ping 192.168.99.1, and both PCs can reach their gateway and each other.

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| SW1–SW4 | IOL-L2-XE switch | cisco | cisco | cisco |
| PC1, PC2 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → **Console**). Switches drop you straight into privileged EXEC.
Each node also has a label on the canvas with its login and addresses.

## Topology

```
                    e0/0              e0/0
              SW1 -------------------------- SW2
     MST0/1 root, gateway              MST2 root
          e0/1 |    e0/2 `.          .' e0/1   | e0/2
               |           `.      .'          |
               |             `.  .'            |
               |               ><              |
               |             .'  `.            |
               |           .'      `.          |
          e0/0 |    e0/1 .'          `. e0/0   | e0/1
              SW3                            SW4
          e1/0 |                               | e1/0
              PC1                             PC2
           VLAN 10                          VLAN 20

  Uplinks: SW1 e0/1-SW3 e0/0, SW1 e0/2-SW4 e0/0, SW2 e0/1-SW3 e0/1, SW2 e0/2-SW4 e0/1, SW1 e0/0-SW2 e0/0
```

## Addressing (as designed)

| Node | Interface | IPv4 | Notes |
|---|---|---|---|
| SW1 | Vlan10 / Vlan20 / Vlan99 | 192.168.10.1 / 192.168.20.1 / 192.168.99.1 | gateway for all VLANs |
| SW2 | Vlan99 | 192.168.99.202/24 | default-gateway 192.168.99.1 |
| SW3 | Vlan99 | 192.168.99.203/24 | default-gateway 192.168.99.1 |
| SW4 | Vlan99 | 192.168.99.204/24 | default-gateway 192.168.99.1 |
| PC1 | eth0 | 192.168.10.10/24, gw .1 | SW3 e1/0, VLAN 10 |
| PC2 | eth0 | 192.168.20.10/24, gw .1 | SW4 e1/0, VLAN 20 |
