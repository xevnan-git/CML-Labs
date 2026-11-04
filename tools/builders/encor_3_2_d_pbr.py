# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Build configs + topology files for the ENCOR 3.2.d PBR lab pair (learn-pbr + ts-pbr). Also ENARSI 1.6.

One source of truth for every variant. After running, run tools/sync_notes.py.
  learn boot  ("clean"): addressing and static routing up (default via ISP1), no PBR (the topic is PBR)
  final       ("final"): learn end state = ts design: guests via ISP2 (tracked), R1's own Lo0 traffic via ISP2
  ts boot     ("ts"):    final + the injected faults (all on R1, see FAULTS)
Both ISPs own the same "internet server" address 203.0.113.100 (Loopback1); a telnet to it shows a banner naming
the ISP that answered, so a learner can see which path a packet took.
Usage: uv run tools/builders/encor_3_2_d_pbr.py [--chunks DIR]   (DIR: both labs as JSON for the MCP;
       each lab is 5 licensed nodes, so a chunk is the whole lab)
"""
import json, sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TOPIC = REPO / "labs/encor/3-infrastructure/pbr"
LEARN, TS = TOPIC / "learn-pbr", TOPIC / "ts-pbr"
LEARN_YAML, TS_YAML = "encor-3.2.d-pbr-learn-pbr.yaml", "encor-3.2.d-pbr-ts-pbr.yaml"

BASE = """hostname {h}
no ip domain lookup
ip domain name lab.local
enable secret cisco
username cisco privilege 15 secret cisco
!
"""
LINES = """line con 0
 exec-timeout 0 0
 logging synchronous
 privilege level 15
line vty 0 4
 login local
 transport input telnet ssh
!
end
"""
PHYS = [f"Ethernet0/{i}" for i in range(4)]

# interface -> (ip mask, description); unlisted Ethernet0/x are shut
INTS = {
 "R1": [("Loopback0", "10.255.255.1 255.255.255.255", None),
        ("Ethernet0/0", "192.168.10.1 255.255.255.0", "VLAN 10 staff LAN (PC1)"),
        ("Ethernet0/1", "192.168.20.1 255.255.255.0", "VLAN 20 guest LAN (PC2)"),
        ("Ethernet0/2", "10.1.101.1 255.255.255.0", "ISP1 e0/0 (primary)"),
        ("Ethernet0/3", "10.1.102.1 255.255.255.0", "ISP2 e0/0 (guest / backup)")],
 "ISP1": [("Loopback0", "10.255.255.101 255.255.255.255", None),
          ("Loopback1", "203.0.113.100 255.255.255.255", "internet server (same address at ISP2)"),
          ("Ethernet0/0", "10.1.101.101 255.255.255.0", "customer R1 e0/2")],
 "ISP2": [("Loopback0", "10.255.255.102 255.255.255.255", None),
          ("Loopback1", "203.0.113.100 255.255.255.255", "internet server (same address at ISP1)"),
          ("Ethernet0/0", "10.1.102.102 255.255.255.0", "customer R1 e0/3")],
}

ROUTING = {
 "R1": """ip route 0.0.0.0 0.0.0.0 10.1.101.101 name DEFAULT-VIA-ISP1
ip route 203.0.113.0 255.255.255.0 10.1.101.101 name SAAS-VIA-ISP1
!
""",
 "ISP1": """ip route 192.168.0.0 255.255.0.0 10.1.101.1 name CUSTOMER-LANS
ip route 10.255.255.1 255.255.255.255 10.1.101.1 name CUSTOMER-R1
!
""",
 "ISP2": """ip route 192.168.0.0 255.255.0.0 10.1.102.1 name CUSTOMER-LANS
ip route 10.255.255.1 255.255.255.255 10.1.102.1 name CUSTOMER-R1
!
""",
}

BANNER = {h: f"banner motd %\n*** internet server 203.0.113.100 -- you reached it through {h} ***\n%\n!\n"
          for h in ("ISP1", "ISP2")}

# R1's PBR (final = learn end state = ts design). After the interfaces: the IP SLA names a source interface.
PBR = """ip access-list extended GUEST-NET
 10 permit ip 192.168.20.0 0.0.0.255 any
ip access-list extended R1-LOOPBACK
 10 permit ip host 10.255.255.1 any
!
ip sla 1
 icmp-echo 10.1.102.102 source-interface Ethernet0/3
 frequency 5
ip sla schedule 1 life forever start-time now
!
track 1 ip sla 1 reachability
!
route-map PBR-GUEST permit 10
 match ip address GUEST-NET
 set ip next-hop verify-availability 10.1.102.102 1 track 1
!
route-map PBR-LOCAL permit 10
 match ip address R1-LOOPBACK
 set ip next-hop 10.1.102.102
!
interface Ethernet0/1
 ip policy route-map PBR-GUEST
!
ip local policy route-map PBR-LOCAL
!
"""

# Troubleshooting faults, all on R1: (find, replace) on the final PBR text.
# Numbered as in ts-pbr/solution/README.md (the order a learner usually meets them).
FAULTS = [
 # Fault 1 policy on the ISP2-facing interface: PBR is ingress only, guest packets enter e0/1 and use the RIB
 ("interface Ethernet0/1\n ip policy route-map PBR-GUEST\n", "interface Ethernet0/3\n ip policy route-map PBR-GUEST\n"),
 # Fault 2 (hidden behind 1) guest LAN as destination instead of source: no guest packet matches
 (" 10 permit ip 192.168.20.0 0.0.0.255 any\n", " 10 permit ip any 192.168.20.0 0.0.0.255\n"),
 # Fault 3 (hidden behind 2) default next-hop: used only when the RIB has no explicit route (0/0 doesn't count),
 # and R1 has 203.0.113.0/24 via ISP1, so guests still go to ISP1. (default next-hop can't take a track.)
 (" set ip next-hop verify-availability 10.1.102.102 1 track 1\n", " set ip default next-hop 10.1.102.102\n"),
 # Fault 4 (hidden behind 3: default next-hop has no track) IP SLA probes an address that doesn't exist:
 # track down, verify-availability skips the next hop, PBR falls back to the RIB (ISP1)
 (" icmp-echo 10.1.102.102 source-interface", " icmp-echo 10.1.102.201 source-interface"),
 # Fault 5 local policy next hop not on a connected subnet: R1's own traffic silently uses the RIB (ISP1)
 (" match ip address R1-LOOPBACK\n set ip next-hop 10.1.102.102\n",
  " match ip address R1-LOOPBACK\n set ip next-hop 10.1.120.102\n"),
]


def config(h, mode):
    """mode: clean | final | ts (R1 only differs; ISP1 and ISP2 are always final)"""
    out = [BASE.format(h=h)]
    used = set()
    for name, ip, desc in INTS[h]:
        used.add(name)
        s = f"interface {name}\n"
        if desc:
            s += f" description {desc}\n"
        s += f" ip address {ip}\n"
        if name.startswith("Ethernet"):
            s += " no shutdown\n"
        out.append(s + "!\n")
    for p in PHYS:
        if p not in used:
            out.append(f"interface {p}\n no ip address\n shutdown\n!\n")
    out.append(ROUTING[h])
    if h in BANNER:
        out.append(BANNER[h])
    if h == "R1" and mode != "clean":
        pbr = PBR
        if mode == "ts":
            for old, new in FAULTS:
                assert pbr.count(old) == 1, old
                pbr = pbr.replace(old, new)
        out.append(pbr)
    out.append(LINES)
    return "".join(out)


PCS = {"PC1": ("192.168.10.10/24", "192.168.10.1"), "PC2": ("192.168.20.10/24", "192.168.20.1")}


def pc_config(h):
    ip, gw = PCS[h]
    return (f"# this is a shell script which will be sourced at boot\nhostname {h}\nUSERNAME=cisco\nPASSWORD=cisco\n"
            f"ip address add {ip} dev eth0\nip link set dev eth0 up\nip route add default via {gw}\n")


ORDER = ["R1", "ISP1", "ISP2", "PC1", "PC2"]
POS = {"PC1": (-350, -150), "PC2": (-350, 150), "R1": (0, 0), "ISP1": (350, -150), "ISP2": (350, 150)}
LABELS = {
 "R1": "R1  edge (PBR)  cisco/cisco\nLo0   10.255.255.1/32\ne0/0  192.168.10.1/24 (PC1)\ne0/1  192.168.20.1/24 (PC2)\n"
       "e0/2  10.1.101.1/24   (ISP1)\ne0/3  10.1.102.1/24   (ISP2)",
 "ISP1": "ISP1  primary  cisco/cisco\nLo0   10.255.255.101/32\nLo1   203.0.113.100/32 (server)\ne0/0  10.1.101.101/24 (R1)",
 "ISP2": "ISP2  guest/backup  cisco/cisco\nLo0   10.255.255.102/32\nLo1   203.0.113.100/32 (server)\ne0/0  10.1.102.102/24 (R1)",
 "PC1": "PC1  staff  cisco/cisco\neth0 192.168.10.10/24\ngw   192.168.10.1",
 "PC2": "PC2  guest  cisco/cisco\neth0 192.168.20.10/24\ngw   192.168.20.1",
}
# (a, a's Ethernet0/x, b, b's Ethernet0/x or eth0)
LINKS = [("R1", 0, "PC1", None), ("R1", 1, "PC2", None), ("R1", 2, "ISP1", 0), ("R1", 3, "ISP2", 0)]


def iol_ifaces(h):
    names = ["Loopback0"] + PHYS  # CML only models Loopback0; ISP Loopback1 comes from the config
    out = []
    for k, n in enumerate(names):
        i = {"id": f"i{k}", "label": n, "type": "loopback" if n.startswith("Loop") else "physical"}
        if not n.startswith("Loop"):
            i["slot"] = PHYS.index(n)
        out.append(i)
    return out


def iface_id(h, eth):
    return next(i["id"] for i in iol_ifaces(h) if i["label"] == f"Ethernet0/{eth}")


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
            n.update(node_definition="iol-xe", image_definition="iol-xe-17-18-02", interfaces=iol_ifaces(h),
                     configuration=[{"name": "ios_config.txt", "content": config(h, mode)}])
        nodes.append(n)
    links = [{"id": f"l{k}", "n1": ids[a], "i1": iface_id(a, ia), "n2": ids[b],
              "i2": "i0" if ib is None else iface_id(b, ib)}
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
 "learn": (LEARN, LEARN_YAML, "[LEARN] ENCOR 3.2.d Policy-Based Routing",
           "Learning: send guest traffic out a second ISP with a route-map, compare next-hop and default next-hop, track the next hop with IP SLA, and policy-route the router's own traffic.",
           "clean"),
 "ts": (TS, TS_YAML, "[TSHOOT] ENCOR 3.2.d Policy-Based Routing",
        "Troubleshooting: guest traffic and the router's own management traffic should leave through ISP2, but everything still goes out ISP1.",
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
            t = topology(f"[TEST] pbr {key}", "temporary test chunk", mode)
            t["annotations"] = []  # keeps the MCP payload small; annotations are validated on the real files
            (OUT / f"{key}.json").write_text(json.dumps(t), encoding="utf-8")
    print("done")
