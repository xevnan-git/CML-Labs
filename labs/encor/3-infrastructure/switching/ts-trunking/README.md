# 802.1Q Trunking and DTP — Troubleshooting Lab

> **Blueprint:** ENCOR 3.1.a — Troubleshoot static and dynamic 802.1q trunking protocols
> **Mode:** Troubleshooting · **Nodes:** 8 licensed (1 router, 3 switches, 4 PCs) · **Faults:** 5 · **Difficulty:** 3 of 3

## Ticket

> **#5214 — Finance VLAN rollout broke three of four desks**
> "Last night we added VLAN 30 (Finance) to the campus and tidied up the trunk configs while we were in there.
> This morning only PC1 (Sales, on SW2) can reach its gateway. PC2 (Engineering, SW2), PC3 (Finance, SW3) and PC4
> (Sales, SW3) can't reach anything. The NOC has also lost management of SW2 and SW3 (`192.168.99.202` and `.203`).
> Every link light is green and nobody has touched the cabling."

## Done when
- From each PC, `ping -c 3 <its gateway>` succeeds: PC1 and PC4 → 192.168.10.1, PC2 → 192.168.20.1,
  PC3 → 192.168.30.1.
- `PC3:~$ ping -c 3 192.168.10.10` (Finance to Sales, routed by R1) succeeds.
- `R1# ping 192.168.99.202` and `R1# ping 192.168.99.203` succeed.
- On SW1, `show interfaces trunk` lists e0/0, e0/1 and e0/2 as **trunking**, each with native VLAN **999**, and
  VLANs **10, 20, 30, 99** in all three of its VLAN lists (allowed, active, forwarding).
- Each link still trunks the way the design below says (the right Mode column on both ends).

## Rules
- Fix with the smallest change that restores the intended design. Don't hard-code a dynamic link as a static
  trunk, and don't change the native VLAN plan.
- There's more than one fault, some symptoms have more than one cause, and fixing one may reveal the next.
- Hints and the full solution are in the lab repository (`solution/README.md` in this lab's folder), not in CML.

## Intended design
- **VLANs** (defined on every switch, VTP **transparent**, domain `LAB`): 10 SALES, 20 ENGINEERING, 30 FINANCE,
  99 MGMT, 999 NATIVE-UNUSED.
- **R1** is router-on-a-stick: subinterfaces on e0/0 for VLANs 10, 20, 30 and 99 (address `.1` in each), and
  e0/0.999 as the **native** VLAN subinterface (no IP).
- **Every trunk** is 802.1Q, allows only VLANs **10, 20, 30, 99**, and uses native VLAN **999**.
- **Trunk links:**

  | Link | Ports | How it trunks |
  |---|---|---|
  | R1–SW1 | R1 e0/0 ↔ SW1 e0/0 | **static**: SW1 `mode trunk` + `nonegotiate` (a router doesn't speak DTP) |
  | SW1–SW2 | SW1 e0/1 ↔ SW2 e0/0 | **DTP**: SW1 `dynamic desirable`, SW2 `dynamic auto` |
  | SW1–SW3 | SW1 e0/2 ↔ SW3 e0/0 | **DTP**: SW1 `mode trunk` (still sending DTP), SW3 `dynamic auto` |

- **Access ports** (PortFast): SW2 e1/0 → PC1 (VLAN 10), SW2 e1/1 → PC2 (VLAN 20), SW3 e1/0 → PC3 (VLAN 30),
  SW3 e1/1 → PC4 (VLAN 10).
- **Management:** each switch has a VLAN 99 SVI, no IP routing, default gateway 192.168.99.1 (R1).

## Expected behavior (healthy network)
- `show dtp interface` on SW2 e0/0 and SW3 e0/0 shows DTP packets being received, and both ports show Mode `auto`,
  Status `trunking` in `show interfaces trunk`.
- No `%CDP-4-NATIVE_VLAN_MISMATCH` messages anywhere.
- Every PC can reach its gateway and every other PC; R1 can ping every switch's VLAN 99 address.

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1 | IOL-XE router | cisco | cisco | cisco |
| SW1–SW3 | IOL-L2-XE switch | cisco | cisco | cisco |
| PC1–PC4 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → **Console**). Routers and switches drop you straight into
privileged EXEC. Each node also has a label on the CML canvas with its login and addresses.

## Topology

```
                           R1   router-on-a-stick
                           | e0/0
                           |  802.1Q trunk (static)
                           | e0/0
                          SW1   distribution
                   e0/1 .'   `. e0/2
                (DTP) .'       `. (DTP)
                    .'           `.
              e0/0 '               ` e0/0
                SW2                 SW3
           e1/0 |  | e1/1      e1/0 |  | e1/1
               PC1 PC2             PC3 PC4
            VLAN 10 VLAN 20    VLAN 30 VLAN 10
```

## Addressing (as designed)

| Node | Interface | IPv4 | Notes |
|---|---|---|---|
| R1 | Lo0 | 10.255.255.1/32 | |
| R1 | e0/0.10 / .20 / .30 / .99 | 192.168.10.1 / 20.1 / 30.1 / 99.1 (/24) | gateways |
| R1 | e0/0.999 | none | native VLAN 999 |
| SW1 | Vlan99 | 192.168.99.201/24 | default-gateway 192.168.99.1 |
| SW2 | Vlan99 | 192.168.99.202/24 | default-gateway 192.168.99.1 |
| SW3 | Vlan99 | 192.168.99.203/24 | default-gateway 192.168.99.1 |
| PC1 | eth0 | 192.168.10.10/24, gw .1 | SW2 e1/0, VLAN 10 |
| PC2 | eth0 | 192.168.20.10/24, gw .1 | SW2 e1/1, VLAN 20 |
| PC3 | eth0 | 192.168.30.10/24, gw .1 | SW3 e1/0, VLAN 30 |
| PC4 | eth0 | 192.168.10.11/24, gw .1 | SW3 e1/1, VLAN 10 |
