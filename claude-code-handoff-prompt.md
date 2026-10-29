# Handoff: CML Networking Lab Library (CCNA / CCNP)

You're picking up a project that started in a Claude chat. Read this whole prompt before doing anything, then follow "First session" at the bottom.

## Who I am and what I'm doing

- I'm studying for the CCNP. I understand a lot of material conceptually but haven't seen much of it working in practice (MPLS and loopback interfaces are two examples I've had to have walked through). Labs should teach by doing: concrete topologies, real show-command output to look for, and short explanations of *why* things behave the way they do.
- I have access to a Cisco Modeling Labs (CML) server at work, licensed on the **20-node plan**. The host hardware is not a constraint — design to the 20-node license limit, not to CPU/RAM.
- Earlier I experimented with CML-Free (5 nodes, IOL/IOL-L2/ASAv only). That's no longer the target. Don't assume which node definitions/images the work server has — query it.

## Goal

Build a GitHub repo of CML labs covering CCNA and CCNP material that can be imported into the work CML server.

- Every topic gets two kinds of labs:
  1. **Learning labs** — guided build/configure exercises with objectives, tasks, and verification steps.
  2. **Troubleshooting labs** — a pre-broken topology with one or more injected faults, a symptom-based ticket ("users in VLAN 20 can't reach the server"), hints, and a hidden solution.
- Coverage target: every topic on the CCNP exam blueprint (plus CCNA foundations where a CCNP lab needs them). **Labs are built on demand**, not all at once — the full topic list is a backlog, and I'll tell you which lab to build next.
- No lab may exceed 20 licensed nodes. Check how CML counts nodes against the license (e.g. whether unmanaged switches / external connectors count) on the actual server and record the answer in CLAUDE.md.

## Tooling / environment

- Architecture is two VMs:
  1. **CML server VM** — Linux VM running CML itself (the work server).
  2. **Ubuntu VM** — runs `uv`/`uvx` and the community CML MCP server (`cml-mcp`, github.com/xorrkaz/cml-mcp), which talks to the CML server over its API.
- **Claude Code runs locally on my machine**, not on either VM. The MCP server is launched over SSH: the local client runs `ssh` into the Ubuntu VM, which starts `uvx cml-mcp[pyats]` there, and the stdio stream rides the SSH session.
- This already works in Claude Desktop. The entry is in my `claude_desktop_config.json`; assume it's still good. Reuse that same server definition for Claude Code (e.g. `claude mcp add-json`) rather than designing a new one. Read the config to copy the entry, but don't print any credentials it contains into chat or into the repo.
- Note that with an SSH launch, an `env` block in the local config sets variables for the local `ssh` process, not on the VM. Check how the existing entry gets `CML_*`/`PYATS_*` values to cml-mcp on the VM side and keep it working the same way.
- The `[pyats]` extra lets you run CLI commands on lab devices for verification.
- Read the cml-mcp README for current env vars and options before configuring — at minimum it needs `CML_URL`, `CML_USERNAME`, `CML_PASSWORD`, and for device CLI access `PYATS_USERNAME`, `PYATS_PASSWORD`, `PYATS_AUTH_PASS`. It requires CML 2.9 or later — check the work server's version.
- Register it in Claude Code at **user scope**, not project scope, so the SSH details and any credentials stay out of the repo's `.mcp.json`. **Credentials must never be committed**; add a `.env.example` with placeholders only if the repo's own tools (like the teardown script) need them.
- Only troubleshoot if something actually fails: SSH from Claude Code's environment (key/agent availability can differ from Claude Desktop's), the Ubuntu VM reaching the CML API and device consoles, and the CML server's self-signed certificate.
- I already have a Python teardown script from the chat (`cml_teardown_lab.py`: lists labs, select one, type-to-confirm, stop → wipe → delete, `--dry-run` and `--insecure` flags). I'll drop it into the repo under `tools/`; keep it working with the repo's conventions.

## Safety rules (this is a shared work server)

- Only create, modify, start, stop, wipe, or delete labs this project created. Prefix every lab title with a project tag (e.g. `[LAB] `) and never touch labs without it.
- Ask me before any stop / wipe / delete, even on our own labs, unless I've explicitly told you to clean up a specific lab.
- Don't change server-level settings, users, licensing, or images.

## Repo design (propose, then I'll confirm)

Suggested starting point — refine it if you have a better idea:

```
README.md                 # what this is, how to import a lab, index of built labs
CLAUDE.md                 # conventions + decisions for future Claude Code sessions
.env.example
blueprint/                # topic backlog mapped to the exam blueprint sections, with build status
labs/
  ccnp/<blueprint-area>/<topic>/
    learn-<name>/
      topology.yaml       # CML lab export, importable as-is
      README.md           # objectives, diagram, addressing table, tasks, verification
      initial-configs/    # (if not embedded in the YAML)
      solution/           # final configs + expected show output
    ts-<name>/
      topology.yaml       # pre-broken
      README.md           # ticket/symptoms + hints
      solution/           # root cause(s), fix, how to verify (kept out of the main README)
  ccna/...
templates/                # lab README template, base addressing/naming conventions
tools/                    # validation, import helper, teardown script
```

Things the conventions should pin down:
- A consistent addressing plan (loopbacks, p2p links, LAN subnets, management) and device naming, reused across labs so they feel familiar.
- How each lab is verified (pyATS / show commands via the MCP) before it's committed.
- A validation script that checks every `topology.yaml` parses, stays ≤ 20 licensed nodes, only uses node definitions present on the server, and has a README + solution.
- How labs get from GitHub into CML. Check whether this CML version can import from a repo directly; if not, provide a small import script (file or URL → CML API) plus manual UI import instructions in the README.

## Lab build workflow (once set up)

1. I name a topic (e.g. "OSPF multi-area troubleshooting").
2. You design the topology and write the README first; show me the plan briefly.
3. Build it on the server through the MCP, start it, and verify behavior with real device output.
4. For troubleshooting labs: build it working first, confirm it works, then inject the fault(s) and confirm the symptoms appear.
5. Export to `topology.yaml`, run validation, update the blueprint backlog status and the README index, commit with a clear message.
6. Ask before stopping/wiping the lab on the server.

## Open question to ask me early

- Which CCNP: ENCOR (350-401) core plus which concentration (e.g. ENARSI 300-410)? Build the blueprint backlog for whatever I answer, using the current official Cisco exam topics.

## First session

1. Check the local environment: git and gh (or how I want to authenticate to GitHub). Tell me what's missing rather than guessing.
2. Register the cml-mcp server in Claude Code from the existing Claude Desktop entry, connect, and confirm with server info: CML version, license/node limit, available node definitions and images. Record the results in CLAUDE.md, but leave out hostnames or credentials I wouldn't want in a repo.
3. Ask the open question above.
4. Propose the repo layout and conventions; after I confirm, scaffold the repo, write CLAUDE.md, README, templates, `.gitignore`, `.env.example`, and the validation script, and create the GitHub repo.
5. Build the blueprint backlog (topics only, nothing built).
6. Build one pilot lab pair end to end (learning + troubleshooting) on a topic I pick, to prove the workflow.
