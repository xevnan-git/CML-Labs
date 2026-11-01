# <Topic> — Troubleshooting Lab

> **Blueprint:** <EXAM> <id> — <exact exam topic text>
> **Mode:** Troubleshooting · **Nodes:** <n> licensed · **Faults:** <count> · **Difficulty:** <1–3>

<!--
This README is copied verbatim into the lab's CML Notes. It must NOT reveal the faults: no hints, no root cause.
Hints and the solution live only in solution/README.md in the repo.
Order: scenario first (ticket, goal, design), reference material (access, topology, addressing) at the bottom.
-->

## Ticket

> **#<number> — <short symptom title>**
> <What the user/NOC reports, in their words. Symptoms only.>

## Done when
- <Concrete tests that pass once every fault is fixed>

## Rules
- Fix with the smallest change that restores the intended design; don't redesign.
- There may be more than one fault.
- Hints and the full solution are in the lab repository (`solution/README.md` in this lab's folder), not in CML.

## Intended design
<How the network is supposed to work: protocols, areas/AS, policies.>

## Expected behavior
<What a healthy network shows: neighbors, key routes, reachability.>

---

# Reference

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1 | IOL-XE router | cisco | cisco | cisco |

Open a console from the node in CML (right-click → **Console**). Each node also has a label on the canvas with its
login and addresses.

## Topology

```
 R1 ── R2
```

## Addressing (as designed)

| Node | Interface | IPv4 | Connects to |
|---|---|---|---|
