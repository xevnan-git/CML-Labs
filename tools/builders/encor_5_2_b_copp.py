# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Build configs + topology files for the ENCOR 5.2.b CoPP lab pair (learn-copp + ts-copp).

One source of truth for every variant. After running, run tools/sync_notes.py.
  learn boot  ("clean"): addressing, OSPF (R1-R2) and eBGP (R1-ISP1) up, no CoPP (the topic is CoPP, not routing)
  final       ("final"): learn end state = ts design: CoPP on R1 (routing, mgmt, monitor, catch-all IP, default)
  ts boot     ("ts"):    final + the injected faults (all on R1, see FAULTS)
ISP1 is passive for BGP, so R1 always opens the session (the BGP reply port matters to CoPP).
Usage: uv run tools/builders/encor_5_2_b_copp.py [--chunks DIR]   (DIR: both labs as JSON for the MCP;
       each lab is 5 licensed nodes, so a chunk is the whole lab)
"""
import json, sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TOPIC = REPO / "labs/encor/5-security/infra-security"
LEARN, TS = TOPIC / "learn-copp", TOPIC / "ts-copp"
LEARN_YAML, TS_YAML = "encor-5.2.b-infra-security-learn-copp.yaml", "encor-5.2.b-infra-security-ts-copp.yaml"

BASE = """hostname {h}
no ip domain lookup
ip domain name lab.local
enable secret cisco
username cisco privilege 15 secret cisco
crypto key generate rsa modulus 2048
!
"""
LINES = """line con 0
 exec-timeout 0 0
 logging synchronous
 privilege level 15
line vty 0 4
 login local
 transport input ssh telnet
!
end
"""
PHYS = [f"Ethernet0/{i}" for i in range(4)]

# interface -> (ip mask, description); unlisted Ethernet0/x are shut
INTS = {
 "R1": [("Loopback0", "10.255.255.1 255.255.255.255", None),
        ("Ethernet0/0", "10.1.2.1 255.255.255.0", "R2 e0/0 (inside, OSPF)"),
        ("Ethernet0/1", "10.1.101.1 255.255.255.0", "ISP1 e0/0 (AS 64511)")],
 "R2": [("Loopback0", "10.255.255.2 255.255.255.255", None),
        ("Ethernet0/0", "10.1.2.2 255.255.255.0", "R1 e0/0 (edge)"),
        ("Ethernet0/1", "192.168.10.1 255.255.255.0", "VLAN 10 management LAN (PC1)")],
 "ISP1": [("Loopback0", "10.255.255.101 255.255.255.255", None),
          ("Ethernet0/0", "10.1.101.101 255.255.255.0", "customer R1 e0/1 (AS 65001)"),
          ("Ethernet0/1", "198.51.100.1 255.255.255.0", "PC2 LAN (internet host)")],
}
OSPF_INTS = {"R1": ["Loopback0", "Ethernet0/0"], "R2": ["Loopback0", "Ethernet0/0", "Ethernet0/1"]}

ROUTING = {
 "R1": """router ospf 1
 router-id 10.255.255.1
 default-information originate always
!
router bgp 65001
 bgp router-id 10.255.255.1
 bgp log-neighbor-changes
 neighbor 10.1.101.101 remote-as 64511
 neighbor 10.1.101.101 description ISP1
 neighbor 10.1.101.101 timers 10 30
 network 10.255.255.1 mask 255.255.255.255
 network 192.168.10.0
!
""",
 "R2": """router ospf 1
 router-id 10.255.255.2
 passive-interface Ethernet0/1
!
""",
 "ISP1": """router bgp 64511
 bgp router-id 10.255.255.101
 bgp log-neighbor-changes
 neighbor 10.1.101.1 remote-as 65001
 neighbor 10.1.101.1 description customer R1
 neighbor 10.1.101.1 transport connection-mode passive
 neighbor 10.1.101.1 timers 10 30
 network 10.255.255.101 mask 255.255.255.255
 network 198.51.100.0
!
""",
}

# R1's CoPP (final = learn end state = ts design). Order matters: ACLs, class-maps, policy-map, then control-plane.
# (IOL-XE has ip http server/secure-server on by default, so HTTP(S) is classified but not configured here.)
COPP = """ip access-list extended COPP-ROUTING
 10 permit ospf any any
 20 permit tcp any any eq bgp
 30 permit tcp any eq bgp any
 40 permit eigrp any any
ip access-list extended COPP-MGMT
 10 permit tcp 192.168.10.0 0.0.0.255 any eq 22
 20 permit tcp 192.168.10.0 0.0.0.255 any eq telnet
 30 permit tcp 192.168.10.0 0.0.0.255 any eq www
 40 permit tcp 192.168.10.0 0.0.0.255 any eq 443
ip access-list extended COPP-SNMP
 10 permit udp 192.168.10.0 0.0.0.255 any eq snmp
ip access-list extended COPP-ICMP
 10 permit icmp any any
ip access-list extended COPP-CATCHALL
 10 permit ip any any
!
class-map match-all CM-ROUTING
 match access-group name COPP-ROUTING
class-map match-all CM-MGMT
 match access-group name COPP-MGMT
class-map match-any CM-MONITOR
 match access-group name COPP-SNMP
 match access-group name COPP-ICMP
class-map match-all CM-CATCHALL
 match access-group name COPP-CATCHALL
!
policy-map PM-COPP
 class CM-ROUTING
  police 256000 conform-action transmit exceed-action transmit
 class CM-MGMT
  police 256000 conform-action transmit exceed-action drop
 class CM-MONITOR
  police 16000 conform-action transmit exceed-action drop
 class CM-CATCHALL
  police 8000 conform-action drop exceed-action drop
 class class-default
  police 64000 conform-action transmit exceed-action drop
!
control-plane
 service-policy input PM-COPP
!
"""

# Troubleshooting faults, all on R1: (find, replace) on the final COPP text.
# Numbered as in ts-copp/solution/README.md (the order a learner usually meets them).
FAULTS = [
 # Fault 1 OSPF matched only toward AllSPFRouters: hellos pass, unicast DBD/LSR fall to CM-CATCHALL -> EXSTART
 (" 10 permit ospf any any\n", " 10 permit ospf any host 224.0.0.5\n"),
 # Fault 2 BGP replies (source port 179) unclassified: R1 is the active side, ISP1's SYN-ACK is dropped -> Active
 (" 30 permit tcp any eq bgp any\n", ""),
 # Fault 3 management ACL written backwards (mgmt LAN as destination): PC1's sessions hit CM-CATCHALL
 (" 10 permit tcp 192.168.10.0 0.0.0.255 any eq 22\n 20 permit tcp 192.168.10.0 0.0.0.255 any eq telnet\n"
  " 30 permit tcp 192.168.10.0 0.0.0.255 any eq www\n 40 permit tcp 192.168.10.0 0.0.0.255 any eq 443\n",
  " 10 permit tcp any 192.168.10.0 0.0.0.255 eq 22\n 20 permit tcp any 192.168.10.0 0.0.0.255 eq telnet\n"
  " 30 permit tcp any 192.168.10.0 0.0.0.255 eq www\n 40 permit tcp any 192.168.10.0 0.0.0.255 eq 443\n"),
 # Fault 4 (hidden behind 3) management policed at 32 kbps: SSH key exchange exceeds bc, SSH hangs, Telnet works
 (" class CM-MGMT\n  police 256000 ", " class CM-MGMT\n  police 32000 "),
 # Fault 5 match-all with two ACLs: no packet is both SNMP and ICMP, so CM-MONITOR never matches; pings to R1 die
 ("class-map match-any CM-MONITOR\n", "class-map match-all CM-MONITOR\n"),
]


def config(h, mode):
    """mode: clean | final | ts (R1 only differs; R2 and ISP1 are always final)"""
    out = [BASE.format(h=h)]
    used = set()
    for name, ip, desc in INTS[h]:
        used.add(name)
        s = f"interface {name}\n"
        if desc:
            s += f" description {desc}\n"
        s += f" ip address {ip}\n"
        if name in OSPF_INTS.get(h, []):
            s += " ip ospf 1 area 0\n"
        if name.startswith("Ethernet"):
            s += " no shutdown\n"
        out.append(s + "!\n")
    for p in PHYS:
        if p not in used:
            out.append(f"interface {p}\n no ip address\n shutdown\n!\n")
    out.append(ROUTING[h])
    if h == "R1" and mode != "clean":
        copp = COPP
        if mode == "ts":
            for old, new in FAULTS:
                assert copp.count(old) == 1, old
                copp = copp.replace(old, new)
        out.append(copp)
    out.append(LINES)
    return "".join(out)


PCS = {"PC1": ("192.168.10.10/24", "192.168.10.1"), "PC2": ("198.51.100.10/24", "198.51.100.1")}


def pc_config(h):
    ip, gw = PCS[h]
    return (f"# this is a shell script which will be sourced at boot\nhostname {h}\nUSERNAME=cisco\nPASSWORD=cisco\n"
            f"ip address add {ip} dev eth0\nip link set dev eth0 up\nip route add default via {gw}\n")


ORDER = ["R1", "R2", "ISP1", "PC1", "PC2"]
POS = {"PC1": (-600, 0), "R2": (-300, 0), "R1": (0, 0), "ISP1": (300, 0), "PC2": (600, 0)}
LABELS = {
 "R1": "R1  edge AS 65001 (CoPP)  cisco/cisco\nLo0   10.255.255.1/32\ne0/0  10.1.2.1/24    (R2)\ne0/1  10.1.101.1/24  (ISP1)",
 "R2": "R2  inside  cisco/cisco\nLo0   10.255.255.2/32\ne0/0  10.1.2.2/24     (R1)\ne0/1  192.168.10.1/24 (PC1)",
 "ISP1": "ISP1  AS 64511  cisco/cisco\nLo0   10.255.255.101/32\ne0/0  10.1.101.101/24 (R1)\ne0/1  198.51.100.1/24 (PC2)",
 "PC1": "PC1  admin (mgmt LAN)  cisco/cisco\neth0 192.168.10.10/24\ngw   192.168.10.1",
 "PC2": "PC2  internet host  cisco/cisco\neth0 198.51.100.10/24\ngw   198.51.100.1",
}
# (a, a's Ethernet0/x, b, b's Ethernet0/x or eth0)
LINKS = [("R1", 0, "R2", 0), ("R1", 1, "ISP1", 0), ("R2", 1, "PC1", None), ("ISP1", 1, "PC2", None)]


def iol_ifaces():
    names = ["Loopback0"] + PHYS
    return [{"id": f"i{k}", "label": n, "type": "loopback" if n.startswith("Loop") else "physical",
             **({"slot": k - 1} if k else {})} for k, n in enumerate(names)]


def topology(title, description, mode):
    nodes, ids = [], {}
    for k, h in enumerate(ORDER):
        nid = f"n{k}"; ids[h] = nid
        x, y = POS[h]
        n = {"id": nid, "label": h, "x": x, "y": y}
        if h in PCS:
            n.update(node_definition="alpine", image_definition="alpine-base-3-23-3",
                     interfaces=[{"id": "i0", "label": "eth0", "slot": 0, "type": "physical"}],
                     configuration=[{"name": "node.cfg", "content": pc_config(h)}])
        else:
            n.update(node_definition="iol-xe", image_definition="iol-xe-17-18-02", interfaces=iol_ifaces(),
                     configuration=[{"name": "ios_config.txt", "content": config(h, mode)}])
        nodes.append(n)
    links = [{"id": f"l{k}", "n1": ids[a], "i1": f"i{ia + 1}", "n2": ids[b], "i2": "i0" if ib is None else f"i{ib + 1}"}
             for k, (a, ia, b, ib) in enumerate(LINKS)]
    anns = []
    for h, text in LABELS.items():
        x, y = POS[h]
        anns.append({"type": "text", "text_content": text, "x1": x - 70, "y1": y + 40, "rotation": 0,
                     "text_bold": False, "text_italic": False, "text_size": 10, "text_unit": "pt",
                     "text_font": "monospace", "color": "#5A5A5AFF", "border_color": "#00000000",
                     # CML file format: '' = solid, '2,2' = dotted, '4,2' = dashed (the MCP tool wants words)
                     "border_style": "", "thickness": 1, "z_index": 1})
    return {"lab": {"title": title, "description": description, "notes": "", "version": "0.3.0"},
            "nodes": nodes, "links": links, "annotations": anns}


class D(yaml.SafeDumper):
    pass


D.add_representer(str, lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s, style="|" if "\n" in s else None))


def write_yaml(path, topo):
    if path.exists():  # keep the synced notes so a rebuild doesn't need sync_notes to pass validate
        topo["lab"]["notes"] = (yaml.safe_load(path.read_text(encoding="utf-8"))["lab"].get("notes") or "")
    path.write_text(yaml.dump(topo, Dumper=D, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8", newline="\n")


LABS = {
 "learn": (LEARN, LEARN_YAML, "[LEARN] ENCOR 5.2.b CoPP",
           "Learning: protect an edge router's control plane with CoPP: classify routing, management and monitoring traffic, police each class, and watch what breaks when a class is wrong.",
           "clean"),
 "ts": (TS, TS_YAML, "[TSHOOT] ENCOR 5.2.b CoPP",
        "Troubleshooting: after a CoPP rollout on the edge router, OSPF and BGP are down and the admins can't manage it.",
        "ts"),
}

if __name__ == "__main__":
    for d, fname, title, desc, mode in LABS.values():
        (d / "solution/configs").mkdir(parents=True, exist_ok=True)
        for h in INTS:
            (d / f"solution/configs/{h}.cfg").write_text(config(h, "final"), encoding="utf-8", newline="\n")
        for h in PCS:
            (d / f"solution/configs/{h}.cfg").write_text(pc_config(h), encoding="utf-8", newline="\n")
        write_yaml(d / fname, topology(title, desc, mode))
    if "--chunks" in sys.argv:
        OUT = Path(sys.argv[sys.argv.index("--chunks") + 1])
        OUT.mkdir(parents=True, exist_ok=True)
        for key, (d, fname, title, desc, mode) in LABS.items():
            t = topology(f"[TEST] copp {key}", "temporary test chunk", mode)
            t["annotations"] = []  # keeps the MCP payload small; annotations are validated on the real files
            (OUT / f"{key}.json").write_text(json.dumps(t), encoding="utf-8")
    print("done")
