# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Build configs + topology files for the ENCOR 5.2.a-b combined pair (learn-acl-copp + ts-acl-copp).

Same topology, addressing, routing and CoPP policy as the 5.2.b pair (imported from encor_5_2_b_copp.py, so the
two can't drift). Adds the other two layers that protect R1:
  IACL-IN    infrastructure ACL inbound on R1 e0/1 (internet side): ISP peer, anti-spoofing, protect R1, transit
  VTY-MGMT   standard ACL as the vty access-class: only the admin workstation PC1 may log in
Variants:
  learn boot  ("clean"): addressing, OSPF and eBGP up; no iACL, no CoPP, no access-class
  final       ("final"): learn end state = ts design: all three layers
  ts boot     ("ts"):    final + the injected faults (all on R1, see FAULTS)
Usage: uv run tools/builders/encor_5_2_ab_acl_copp.py [--chunks DIR]
"""
import json, sys
from pathlib import Path

import encor_5_2_b_copp as base

BASE_CONFIG = base.config  # base.topology() is pointed at our config() below, so keep the original

REPO = base.REPO
TOPIC = base.TOPIC
LEARN, TS = TOPIC / "learn-acl-copp", TOPIC / "ts-acl-copp"
LEARN_YAML, TS_YAML = "encor-5.2.ab-infra-security-learn-acl-copp.yaml", "encor-5.2.ab-infra-security-ts-acl-copp.yaml"

IACL = """ip access-list extended IACL-IN
 10 permit tcp host 10.1.101.101 host 10.1.101.1 eq bgp
 20 permit tcp host 10.1.101.101 eq bgp host 10.1.101.1
 30 permit icmp host 10.1.101.101 host 10.1.101.1
 40 deny ip 10.0.0.0 0.255.255.255 any
 50 deny ip 172.16.0.0 0.15.255.255 any
 60 deny ip 192.168.0.0 0.0.255.255 any
 70 deny ip 127.0.0.0 0.255.255.255 any
 80 permit icmp any host 10.1.101.1 echo
 90 permit icmp any host 10.1.101.1 echo-reply
 100 permit icmp any host 10.1.101.1 unreachable
 110 permit icmp any host 10.1.101.1 time-exceeded
 120 deny ip any host 10.1.101.1
 130 deny ip any host 10.255.255.1
 140 deny ip any 10.1.2.0 0.0.0.255
 150 permit ip any any
ip access-list standard VTY-MGMT
 10 permit 192.168.10.10
 20 deny any log
!
"""
APPLY_IACL = ("interface Ethernet0/1\n description ISP1 e0/0 (AS 64511)\n ip address 10.1.101.1 255.255.255.0\n",
              "interface Ethernet0/1\n description ISP1 e0/0 (AS 64511)\n ip address 10.1.101.1 255.255.255.0\n"
              " no ip unreachables\n ip access-group IACL-IN in\n")
APPLY_VTY = (" login local\n", " access-class VTY-MGMT in\n login local\n")

# Troubleshooting faults, all on R1: (find, replace) on R1's final config.
# Numbered as in ts-acl-copp/solution/README.md (the order a learner usually meets them).
FAULTS = [
 # Fault 1 anti-spoofing above the ISP-peer lines: 10/8 also matches the peer 10.1.101.101 -> BGP SYN-ACK denied
 (" 10 permit tcp host 10.1.101.101 host 10.1.101.1 eq bgp\n 20 permit tcp host 10.1.101.101 eq bgp host 10.1.101.1\n"
  " 30 permit icmp host 10.1.101.101 host 10.1.101.1\n 40 deny ip 10.0.0.0 0.255.255.255 any\n"
  " 50 deny ip 172.16.0.0 0.15.255.255 any\n 60 deny ip 192.168.0.0 0.0.255.255 any\n"
  " 70 deny ip 127.0.0.0 0.255.255.255 any\n",
  " 10 deny ip 10.0.0.0 0.255.255.255 any\n 20 deny ip 172.16.0.0 0.15.255.255 any\n"
  " 30 deny ip 192.168.0.0 0.0.255.255 any\n 40 deny ip 127.0.0.0 0.255.255.255 any\n"
  " 50 permit tcp host 10.1.101.101 host 10.1.101.1 eq bgp\n 60 permit tcp host 10.1.101.101 eq bgp host 10.1.101.1\n"
  " 70 permit icmp host 10.1.101.101 host 10.1.101.1\n"),
 # Fault 2 no transit permit: return traffic for the inside hits the implicit deny
 (" 150 permit ip any any\n", ""),
 # Fault 3 CoPP management class lost SSH: SSH from PC1 falls into CM-CATCHALL; Telnet works
 (" 10 permit tcp 192.168.10.0 0.0.0.255 any eq 22\n", ""),
 # Fault 4 (hidden behind 1+2) only echo permitted to R1: replies to R1's own ping/traceroute are denied
 (" 90 permit icmp any host 10.1.101.1 echo-reply\n 100 permit icmp any host 10.1.101.1 unreachable\n"
  " 110 permit icmp any host 10.1.101.1 time-exceeded\n", ""),
]


def config(h, mode):
    """mode: clean | final | ts (only R1 differs)"""
    if h != "R1" or mode == "clean":
        return BASE_CONFIG(h, "clean" if h == "R1" else "final")
    cfg = BASE_CONFIG("R1", "final")
    for old, new in (APPLY_IACL, APPLY_VTY):
        assert cfg.count(old) == 1, old
        cfg = cfg.replace(old, new)
    # ACLs before the CoPP block (the order in a running config); they're referenced by name, so either order boots
    cfg = cfg.replace("ip access-list extended COPP-ROUTING\n", IACL + "ip access-list extended COPP-ROUTING\n", 1)
    if mode == "ts":
        for old, new in FAULTS:
            assert cfg.count(old) == 1, old
            cfg = cfg.replace(old, new)
    return cfg


LABELS = dict(base.LABELS)
LABELS["R1"] = LABELS["R1"].replace("(CoPP)", "(iACL, CoPP, vty)")

LABS = {
 "learn": (LEARN, LEARN_YAML, "[LEARN] ENCOR 5.2.a-b ACLs and CoPP",
           "Learning: layer an infrastructure ACL, CoPP and a vty access-class on an internet edge router, and see which layer stops what.",
           "clean"),
 "ts": (TS, TS_YAML, "[TSHOOT] ENCOR 5.2.a-b ACLs and CoPP",
        "Troubleshooting: after the edge router was hardened with an iACL, CoPP and a vty ACL, BGP is down, the office has no internet and SSH fails.",
        "ts"),
}


def topology(title, description, mode):
    saved = base.config, base.LABELS
    base.config, base.LABELS = config, LABELS  # base.topology reads these module globals
    try:
        return base.topology(title, description, mode)
    finally:
        base.config, base.LABELS = saved


if __name__ == "__main__":
    for d, fname, title, desc, mode in LABS.values():
        (d / "solution/configs").mkdir(parents=True, exist_ok=True)
        for h in base.INTS:
            (d / f"solution/configs/{h}.cfg").write_text(config(h, "final"), encoding="utf-8", newline="\n")
        for h in base.PCS:
            (d / f"solution/configs/{h}.cfg").write_text(base.pc_config(h), encoding="utf-8", newline="\n")
        base.write_yaml(d / fname, topology(title, desc, mode))
    if "--chunks" in sys.argv:
        OUT = Path(sys.argv[sys.argv.index("--chunks") + 1])
        OUT.mkdir(parents=True, exist_ok=True)
        for key, (d, fname, title, desc, mode) in LABS.items():
            t = topology(f"[TEST] acl-copp {key}", "temporary test chunk", mode)
            t["annotations"] = []
            (OUT / f"{key}.json").write_text(json.dumps(t), encoding="utf-8")
    print("done")
