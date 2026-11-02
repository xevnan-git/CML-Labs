# EtherChannel (LACP, PAgP, L3) — Troubleshooting Lab

> **Blueprint:** ENCOR 3.1.b — Troubleshoot static and dynamic EtherChannels
> **Mode:** Troubleshooting · **Nodes:** 7 licensed (5 switches, 2 PCs) · **Faults:** 5 · **Difficulty:** 3 of 3

## Ticket

> **#5230 — Both closets offline after the port-channel "standardization"**
> "Last night's change 'standardized' every port-channel in the campus. This morning neither PC1 (Sales, on SW3)
> nor PC2 (Engineering, on SW4) can reach its gateway or the Internet (203.0.113.1). The ISP-facing monitoring also
> reports the Internet uplink bundle Po4 running on **one** of its two links. Every link light is green."

## Done when
- `PC1:~$ ping -c 3 192.168.10.1` and `PC2:~$ ping -c 3 192.168.20.1` succeed.
- Both PCs can `ping -c 3 203.0.113.1`, and `PC1:~$ ping -c 3 192.168.20.10` succeeds.
- `show etherchannel summary` shows every port-channel in the design below as **(SU)** or **(RU)**, with **both**
  members **(P)**, on **both** ends.
- Every bundle uses the protocol and modes in the design below, and every trunk allows VLANs 10, 20 and 99.

## Rules
- Fix with the smallest change that restores the intended design. Don't swap a negotiated bundle for `mode on`,
  and don't change which protocol a bundle uses.
- There's more than one fault, some symptoms have more than one cause, and fixing one may reveal the next.
- Hints and the full solution are in the lab repository (`solution/README.md` in this lab's folder), not in CML.

## Intended design
- **VLANs** (VTP **transparent**, domain `LAB`): 10 SALES, 20 ENGINEERING, 99 MGMT, 999 NATIVE-UNUSED.
- **Every L2 bundle** is an 802.1Q trunk allowing only VLANs **10, 20, 99** with native VLAN **999**, configured
  identically on the port-channel and on each member port.
- **Bundles:**

  | Bundle | Ports | Type | Protocol and modes |
  |---|---|---|---|
  | Po1 SW1–SW2 | SW1 e0/0-1 ↔ SW2 e0/0-1 | L2 trunk | LACP, **active** both ends |
  | Po2 SW1–SW3 | SW1 e0/2-3 ↔ SW3 e0/0-1 | L2 trunk | LACP, SW1 **active**, SW3 **passive** |
  | Po3 SW2–SW4 | SW2 e0/2-3 ↔ SW4 e0/0-1 | L2 trunk | PAgP, SW2 **desirable**, SW4 **auto** |
  | Po4 SW1–SW5 | SW1 e1/0-1 ↔ SW5 e0/0-1 | **L3** (routed) | LACP, **active** both ends |

- **SW1** (distribution) routes for VLANs 10, 20 and 99 (SVIs) and has a default route to SW5 over Po4.
  **SW5** (Internet edge, L3 switch) has 203.0.113.1 on Loopback1 and a route for 192.168.0.0/16 back to SW1.
- **Access ports** (PortFast): SW3 e1/0 → PC1 (VLAN 10), SW4 e1/0 → PC2 (VLAN 20).

## Expected behavior (healthy network)
- Four port-channels, eight bundled member pairs, nothing suspended (`s`) or stand-alone (`I`).
- `show lacp neighbor` on SW1 lists a partner on every LACP member, and `show etherchannel 3 detail` on SW4 shows
  both members in the bundle.
- Every switch can ping 192.168.99.1, and both PCs can reach their gateway, each other and 203.0.113.1.

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| SW1–SW5 | IOL-L2-XE switch | cisco | cisco | cisco |
| PC1, PC2 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → **Console**). Switches drop you straight into privileged EXEC.
Each node also has a label on the CML canvas with its login and addresses.

SW5 is an L3 switch standing in for an edge router: the IOL router image in CML can't build port-channels.

## Topology

```
                     SW5   Internet edge (Lo1 203.0.113.1)
                     e0/0-1 ||
                            ||  Po4  L3 LACP  10.1.5.0/24
                     e1/0-1 ||
                     SW1 ============================== SW2
             gateway  e0/2-3   e0/0-1   Po1 LACP   e0/0-1   e0/2-3
                       ||                                   ||
                 Po2   ||                                   ||   Po3
                 LACP  ||                                   ||   PAgP
                       ||                                   ||
                 e0/0-1||                                   ||e0/0-1
                     SW3                                    SW4
                  e1/0 |                                    | e1/0
                     PC1                                    PC2
                   VLAN 10                                VLAN 20
```

## Addressing (as designed)

| Node | Interface | IPv4 | Notes |
|---|---|---|---|
| SW5 | Lo0 / Lo1 | 10.255.255.5/32 / 203.0.113.1/24 | Lo1 = simulated Internet |
| SW5 | Po4 | 10.1.5.5/24 | route 192.168.0.0/16 → 10.1.5.1 |
| SW1 | Po4 | 10.1.5.1/24 | default route → 10.1.5.5 |
| SW1 | Vlan10 / Vlan20 / Vlan99 | 192.168.10.1 / 192.168.20.1 / 192.168.99.1 (/24) | gateways |
| SW2 | Vlan99 | 192.168.99.202/24 | default-gateway 192.168.99.1 |
| SW3 | Vlan99 | 192.168.99.203/24 | default-gateway 192.168.99.1 |
| SW4 | Vlan99 | 192.168.99.204/24 | default-gateway 192.168.99.1 |
| PC1 | eth0 | 192.168.10.10/24, gw .1 | SW3 e1/0, VLAN 10 |
| PC2 | eth0 | 192.168.20.10/24, gw .1 | SW4 e1/0, VLAN 20 |
