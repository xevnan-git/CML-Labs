# <Topic> — Learning Lab

> **Blueprint:** <EXAM> <id> — <exact exam topic text>
> **Mode:** Learning (guided build from clean devices) · **Nodes:** <n> licensed · **Time:** ~<min> min

<!--
This README is copied verbatim into the lab's CML Notes (tools/sync_notes.py), so it must read well inside CML:
plain Markdown, ASCII diagrams (no Mermaid), no links to solution files.
-->

## What you'll learn
- <Objective stated as something you can observe>

## Lab access

| Node | Type | Username | Password | Enable |
|---|---|---|---|---|
| R1 | IOL-XE router | cisco | cisco | cisco |
| PC1 | Alpine Linux | cisco | cisco | `sudo -i` |

Open a console from the node in CML (right-click → Console). Routers start in privileged EXEC.
Each node also has a label in the CML canvas with its login and addresses.

## Topology

```
 PC1 ── e0/1 R1 e0/0 ── e0/0 R2
```

## Addressing

| Node | Interface | IPv4 | Connects to |
|---|---|---|---|
| R1 | Loopback0 | 10.255.255.1/32 | — |

## Starting point
Routers boot **clean**: hostname, login, and console settings only — no IP addresses, no routing.
<Say what else is preconfigured, e.g. PC addressing.>

## Step 1 — <title>
<What you're about to do and why, 1–2 sentences.>

**R1**
```
configure terminal
 ...
end
```

**Verify**
```
R1# show ...
```
Look for: <field/value that proves it worked>.

> **Why:** <2–4 sentences on the mechanism.>

## Step 2 — ...

## Final check
<End-to-end test that proves the whole design works.>

## Check yourself
- <Question answerable from what they observed>
