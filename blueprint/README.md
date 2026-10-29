# Blueprint backlog

Topic lists come straight from Cisco's official exam-topic documents:

- [ENCOR 350-401 v1.2](encor-v1.2.md) — CCNP/CCIE Enterprise core (2025 document)
- [ENARSI 300-410 v1.1](enarsi-v1.1.md) — CCNP Enterprise concentration (2023 document)

Labs are built on demand. Pick a row, and it becomes a `learn-` and/or `ts-` lab.

## Plan column

| Plan | Meaning |
|---|---|
| `learn + ts` | Configure/troubleshoot topic: one learning lab and one troubleshooting lab |
| `learn` | Describe-level topic that still runs on these images: a guided demo lab, no troubleshooting lab |
| `ts` | Troubleshoot-only topic, best taught by breaking things (a short learn section goes in the README) |
| `concept` | Not meaningfully labbable; short note in `labs/<exam>/<domain>/<topic>/NOTES.md` |
| `N/A here` | Needs an image this server doesn't have (SD-WAN, Catalyst Center, Cat9800, ISE…) |
| `→ <id>` | Covered by another row's lab; don't build twice |

`verify` in the Notes column means the feature support on IOL-XE/IOL-L2-XE has to be confirmed before designing.
If it's missing there, fall back to IOSv / IOSv-L2, and failing that to `concept`.

## Status column

`backlog` → `designing` → `built` (on server, verified) → `done` (exported, validated, committed). The Lab(s)
column links the folders once they exist.
