# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Build configs + topology for the ENCOR 3.2.a EIGRP vs OSPF learning lab (learn-eigrp-vs-ospf; no TS lab).

  learn boot  ("clean"): addresses on every interface, no routing (the topic is the comparison, not addressing)
  final       ("final"): OSPF area 0 and EIGRP named mode LAB / AS 100 on all four routers, the R1-R3 link at
                         5 Mbps, variance 2 on R1, R4's 172.20.0.0/22 summary toward R2 and R3
Usage: uv run tools/builders/encor_3_2_a_eigrp_ospf.py [--chunks DIR]   (5 licensed nodes: one chunk = the lab)
"""
import json, sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
LEARN = REPO / "labs/encor/3-infrastructure/eigrp-ospf/learn-eigrp-vs-ospf"
LEARN_YAML = "encor-3.2.a-eigrp-ospf-learn-eigrp-vs-ospf.yaml"

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
 transport input ssh telnet
!
end
"""
PHYS = [f"Ethernet0/{i}" for i in range(4)]
SLOW = " bandwidth 5000\n"  # the R1-R3 link, both ends (final only: the Guide sets it in Step 3)

# interface -> (ip mask, description, final-only extra lines)
INTS = {
 "R1": [("Loopback0", "10.255.255.1 255.255.255.255", None, ""),
        ("Ethernet0/0", "10.1.2.1 255.255.255.0", "R2 e0/0", ""),
        ("Ethernet0/1", "10.1.3.1 255.255.255.0", "R3 e0/0 (slow path)", SLOW),
        ("Ethernet0/2", "192.168.10.1 255.255.255.0", "PC1 LAN", "")],
 "R2": [("Loopback0", "10.255.255.2 255.255.255.255", None, ""),
        ("Ethernet0/0", "10.1.2.2 255.255.255.0", "R1 e0/0", ""),
        ("Ethernet0/1", "10.2.4.2 255.255.255.0", "R4 e0/0", "")],
 "R3": [("Loopback0", "10.255.255.3 255.255.255.255", None, ""),
        ("Ethernet0/0", "10.1.3.3 255.255.255.0", "R1 e0/1 (slow path)", SLOW),
        ("Ethernet0/1", "10.3.4.3 255.255.255.0", "R4 e0/1", "")],
 "R4": [("Loopback0", "10.255.255.4 255.255.255.255", None, "")] +
       [(f"Loopback{i + 1}", f"172.20.{i}.1 255.255.255.0", "site LAN (simulated)", " ip ospf network point-to-point\n")
        for i in range(4)] +
       [("Ethernet0/0", "10.2.4.4 255.255.255.0", "R2 e0/1", ""),
        ("Ethernet0/1", "10.3.4.4 255.255.255.0", "R3 e0/1", "")],
}
EIGRP_NETS = {"R1": ["10.0.0.0", "192.168.10.0"], "R2": ["10.0.0.0"], "R3": ["10.0.0.0"], "R4": ["10.0.0.0", "172.20.0.0"]}


def routing(h):
    n = h[1:]
    ospf = f"router ospf 1\n router-id 10.255.255.{n}\n"
    if h == "R1":
        ospf += " passive-interface Ethernet0/2\n"
    ospf += "!\n"
    e = f"router eigrp LAB\n !\n address-family ipv4 unicast autonomous-system 100\n  !\n"
    if h == "R1":
        e += "  af-interface Ethernet0/2\n   passive-interface\n  exit-af-interface\n  !\n"
    if h == "R4":
        for i in ("Ethernet0/0", "Ethernet0/1"):
            e += f"  af-interface {i}\n   summary-address 172.20.0.0 255.255.252.0\n  exit-af-interface\n  !\n"
    e += "  topology base\n"
    if h == "R1":
        e += "   variance 2\n"
    e += "  exit-af-topology\n"
    for net in EIGRP_NETS[h]:
        e += f"  network {net}\n"
    e += f"  eigrp router-id 10.255.255.{n}\n exit-address-family\n!\n"
    return ospf + e


def config(h, mode):
    """mode: clean | final"""
    out = [BASE.format(h=h)]
    used = set()
    for name, ip, desc, extra in INTS[h]:
        used.add(name)
        s = f"interface {name}\n"
        if desc:
            s += f" description {desc}\n"
        if mode == "final":
            s += extra
        s += f" ip address {ip}\n"
        if mode == "final":
            s += " ip ospf 1 area 0\n"
        if name.startswith("Ethernet"):
            s += " no shutdown\n"
        out.append(s + "!\n")
    for p in PHYS:
        if p not in used:
            out.append(f"interface {p}\n no ip address\n shutdown\n!\n")
    if mode == "final":
        out.append(routing(h))
    out.append(LINES)
    return "".join(out)


PCS = {"PC1": ("192.168.10.10/24", "192.168.10.1")}


def pc_config(h):
    ip, gw = PCS[h]
    return (f"# this is a shell script which will be sourced at boot\nhostname {h}\nUSERNAME=cisco\nPASSWORD=cisco\n"
            f"ip address add {ip} dev eth0\nip link set dev eth0 up\nip route add default via {gw}\n")


ORDER = ["R1", "R2", "R3", "R4", "PC1"]
POS = {"PC1": (-450, 0), "R1": (-200, 0), "R2": (50, -150), "R3": (50, 150), "R4": (300, 0)}
LABELS = {
 "R1": "R1  cisco/cisco\nLo0   10.255.255.1/32\ne0/0  10.1.2.1/24   (R2)\ne0/1  10.1.3.1/24   (R3, slow)\ne0/2  192.168.10.1/24 (PC1)",
 "R2": "R2  cisco/cisco\nLo0   10.255.255.2/32\ne0/0  10.1.2.2/24 (R1)\ne0/1  10.2.4.2/24 (R4)",
 "R3": "R3  cisco/cisco\nLo0   10.255.255.3/32\ne0/0  10.1.3.3/24 (R1, slow)\ne0/1  10.3.4.3/24 (R4)",
 "R4": "R4  cisco/cisco\nLo0   10.255.255.4/32\nLo1-4 172.20.0-3.1/24\ne0/0  10.2.4.4/24 (R2)\ne0/1  10.3.4.4/24 (R3)",
 "PC1": "PC1  cisco/cisco\neth0 192.168.10.10/24\ngw   192.168.10.1",
}
LINKS = [("R1", 0, "R2", 0), ("R1", 1, "R3", 0), ("R2", 1, "R4", 0), ("R3", 1, "R4", 1), ("R1", 2, "PC1", None)]


def iol_ifaces(h):
    loops = [n for n, *_ in INTS[h] if n.startswith("Loop")]
    out = [{"id": f"i{k}", "label": n, "type": "loopback"} for k, n in enumerate(loops)]
    out += [{"id": f"i{len(loops) + k}", "label": p, "type": "physical", "slot": k} for k, p in enumerate(PHYS)]
    return out


def iface_id(h, slot):
    loops = sum(1 for n, *_ in INTS[h] if n.startswith("Loop"))
    return f"i{loops + slot}"


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
              "i2": "i0" if ib is None else iface_id(b, ib)} for k, (a, ia, b, ib) in enumerate(LINKS)]
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


TITLE = "[LEARN] ENCOR 3.2.a EIGRP vs OSPF"
DESC = ("Learning: run OSPF and EIGRP side by side on the same four routers and compare metrics, AD, "
        "feasible successors, unequal-cost load balancing and summarization.")

if __name__ == "__main__":
    (LEARN / "solution/configs").mkdir(parents=True, exist_ok=True)
    for h in INTS:
        (LEARN / f"solution/configs/{h}.cfg").write_text(config(h, "final"), encoding="utf-8", newline="\n")
    for h in PCS:
        (LEARN / f"solution/configs/{h}.cfg").write_text(pc_config(h), encoding="utf-8", newline="\n")
    write_yaml(LEARN / LEARN_YAML, topology(TITLE, DESC, "clean"))
    if "--chunks" in sys.argv:
        OUT = Path(sys.argv[sys.argv.index("--chunks") + 1])
        OUT.mkdir(parents=True, exist_ok=True)
        t = topology("[TEST] eigrp-ospf learn", "temporary test chunk", "clean")
        t["annotations"] = []
        (OUT / "learn.json").write_text(json.dumps(t), encoding="utf-8")
    print("done")
