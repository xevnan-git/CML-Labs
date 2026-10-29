# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Build configs + topology files for the ENCOR 3.2.b OSPF multi-area lab pair (learn + ts).

One source of truth for the clean / final / faulted configs. After running, run tools/sync_notes.py.
Usage: uv run tools/builders/encor_3_2_b_ospf_multiarea.py [--chunks DIR]   (DIR: write <=5-node test chunks as JSON)
"""
import json, sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TOPIC = REPO / "labs/encor/3-infrastructure/ospf"

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

# interface -> (ip/mask or None, description, extra lines)
R = {
 "R1": {"ints": [("Loopback0","10.255.255.1 255.255.255.255",None,["ip ospf 1 area 0"]),
                 ("Ethernet0/0","10.0.1.1 255.255.255.0","AREA0 segment (SW0)",["ip ospf 1 area 0","ip ospf priority 0"]),
                 ("Ethernet0/1","10.1.4.1 255.255.255.0","to R4 e0/0",["ip ospf 1 area 1","ip ospf network point-to-point"])],
        "ospf": ["router-id 10.255.255.1","area 1 range 172.20.0.0 255.255.252.0"], "pre": []},
 "R2": {"ints": [("Loopback0","10.255.255.2 255.255.255.255",None,["ip ospf 1 area 0"]),
                 ("Ethernet0/0","10.0.1.2 255.255.255.0","AREA0 segment (SW0)",["ip ospf 1 area 0","ip ospf priority 100"]),
                 ("Ethernet0/1","10.2.5.2 255.255.255.0","to R5 e0/0",["ip ospf 1 area 2","ip ospf network point-to-point"])],
        "ospf": ["router-id 10.255.255.2","area 2 filter-list prefix NO-R4-LO0 in"],
        "pre": ["ip prefix-list NO-R4-LO0 seq 5 deny 10.255.255.4/32","ip prefix-list NO-R4-LO0 seq 10 permit 0.0.0.0/0 le 32","!"]},
 "R3": {"ints": [("Loopback0","10.255.255.3 255.255.255.255",None,["ip ospf 1 area 0"]),
                 ("Loopback1","203.0.113.1 255.255.255.0","simulated external network",[]),
                 ("Ethernet0/0","10.0.1.3 255.255.255.0","AREA0 segment (SW0)",["ip ospf 1 area 0","ip ospf priority 255"])],
        "ospf": ["router-id 10.255.255.3","redistribute connected subnets route-map R3-EXTERNAL"],
        "pre": [], "post": ["route-map R3-EXTERNAL permit 10"," match interface Loopback1","!"]},
 "R4": {"ints": [("Loopback0","10.255.255.4 255.255.255.255",None,["ip ospf 1 area 1"])] +
                [(f"Loopback{i+1}",f"172.20.{i}.1 255.255.255.0","site A simulated LAN",["ip ospf 1 area 1","ip ospf network point-to-point"]) for i in range(4)] +
                [("Ethernet0/0","10.1.4.4 255.255.255.0","to R1 e0/1",["ip ospf 1 area 1","ip ospf network point-to-point"]),
                 ("Ethernet0/1","192.168.10.1 255.255.255.0","PC1 LAN",["ip ospf 1 area 1"])],
        "ospf": ["router-id 10.255.255.4","passive-interface Ethernet0/1"], "pre": []},
 "R5": {"ints": [("Loopback0","10.255.255.5 255.255.255.255",None,["ip ospf 1 area 2"]),
                 ("Ethernet0/0","10.2.5.5 255.255.255.0","to R2 e0/1",["ip ospf 1 area 2","ip ospf network point-to-point"]),
                 ("Ethernet0/1","10.5.6.5 255.255.255.0","to R6 e0/0",["ip ospf 1 area 2","ip ospf network point-to-point"])],
        "ospf": ["router-id 10.255.255.5"], "pre": []},
 "R6": {"ints": [("Loopback0","10.255.255.6 255.255.255.255",None,["ip ospf 1 area 2"]),
                 ("Ethernet0/0","10.5.6.6 255.255.255.0","to R5 e0/1",["ip ospf 1 area 2","ip ospf network point-to-point"]),
                 ("Ethernet0/1","192.168.20.1 255.255.255.0","PC2 LAN",["ip ospf 1 area 2"])],
        "ospf": ["router-id 10.255.255.6","passive-interface Ethernet0/1"], "pre": []},
}
PHYS = [f"Ethernet0/{i}" for i in range(4)]

# Troubleshooting faults: (router, transform on final config lines)
FAULTS = {
 "R5": ("Ethernet0/0", "ip ospf 1 area 2", "ip ospf 1 area 0"),          # F1 area mismatch with R2
 "R6": ("ospf", "passive-interface Ethernet0/1", "passive-interface Ethernet0/0"),  # F2 passive on uplink
 "R4": ("Ethernet0/0", None, "ip mtu 1400"),                             # F3 MTU mismatch with R1
}


def config(h, mode):
    """mode: clean | final | ts"""
    d = R[h]
    out = [BASE.format(h=h)]
    if mode == "clean":
        out.append(f"interface range Ethernet0/0 - 3\n no ip address\n shutdown\n!\n")
        out.append(LINES)
        return "".join(out)
    fault = FAULTS.get(h) if mode == "ts" else None
    out += [l + "\n" for l in d["pre"]]
    used = set()
    for name, ip, desc, extra in d["ints"]:
        used.add(name)
        extra = list(extra)
        if fault and fault[0] == name:
            if fault[1]:
                extra = [fault[2] if e == fault[1] else e for e in extra]
            else:
                extra.append(fault[2])
        s = f"interface {name}\n"
        if desc:
            s += f" description {desc}\n"
        s += f" ip address {ip}\n"
        s += "".join(f" {e}\n" for e in extra)
        if name.startswith("Ethernet"):
            s += " no shutdown\n"
        out.append(s + "!\n")
    for p in PHYS:
        if p not in used:
            out.append(f"interface {p}\n no ip address\n shutdown\n!\n")
    ospf = list(d["ospf"])
    if fault and fault[0] == "ospf":
        ospf = [fault[2] if o == fault[1] else o for o in ospf]
    out += [l + "\n" for l in d.get("post", [])]
    out.append("router ospf 1\n" + "".join(f" {o}\n" for o in ospf) + "!\n")
    out.append(LINES)
    return "".join(out)


PCS = {"PC1": ("192.168.10.10/24", "192.168.10.1"), "PC2": ("192.168.20.10/24", "192.168.20.1")}


def pc_config(h):
    ip, gw = PCS[h]
    return (f"# this is a shell script which will be sourced at boot\nhostname {h}\nUSERNAME=cisco\nPASSWORD=cisco\n"
            f"ip address add {ip} dev eth0\nip link set dev eth0 up\nip route add default via {gw}\n")


POS = {"R1": (-240, 0), "R2": (240, 0), "R3": (0, -200), "R4": (-520, 200), "R5": (520, 200), "R6": (800, 200),
       "SW0": (0, 0), "PC1": (-800, 200), "PC2": (1080, 200)}

LABELS = {
 "R1": "R1  ABR area 0/1  cisco/cisco\nLo0   10.255.255.1/32\ne0/0  10.0.1.1/24  (SW0)\ne0/1  10.1.4.1/24  (R4)",
 "R2": "R2  ABR area 0/2  cisco/cisco\nLo0   10.255.255.2/32\ne0/0  10.0.1.2/24  (SW0)\ne0/1  10.2.5.2/24  (R5)",
 "R3": "R3  ASBR area 0  cisco/cisco\nLo0   10.255.255.3/32\nLo1   203.0.113.1/24 (ext)\ne0/0  10.0.1.3/24  (SW0)",
 "R4": "R4  area 1  cisco/cisco\nLo0   10.255.255.4/32\nLo1-4 172.20.0-3.1/24\ne0/0  10.1.4.4/24  (R1)\ne0/1  192.168.10.1/24 (PC1)",
 "R5": "R5  area 2  cisco/cisco\nLo0   10.255.255.5/32\ne0/0  10.2.5.5/24  (R2)\ne0/1  10.5.6.5/24  (R6)",
 "R6": "R6  area 2  cisco/cisco\nLo0   10.255.255.6/32\ne0/0  10.5.6.6/24  (R5)\ne0/1  192.168.20.1/24 (PC2)",
 "PC1": "PC1  cisco/cisco\neth0 192.168.10.10/24\ngw   192.168.10.1",
 "PC2": "PC2  cisco/cisco\neth0 192.168.20.10/24\ngw   192.168.20.1",
}


def iol_ifaces(h):
    names = ["Loopback0"] + PHYS
    return [{"id": f"i{k}", "label": n, "type": "loopback" if n.startswith("Loop") else "physical",
             **({"slot": k - 1} if k else {})} for k, n in enumerate(names)]


def topology(title, description, mode, only=None):
    order = ["R1", "R2", "R3", "R4", "R5", "R6", "SW0", "PC1", "PC2"]
    nodes, ids = [], {}
    for k, h in enumerate(order):
        if only and h not in only:
            continue
        nid = f"n{k}"; ids[h] = nid
        x, y = POS[h]
        n = {"id": nid, "label": h, "x": x, "y": y}
        if h.startswith("R"):
            n.update(node_definition="iol-xe", image_definition="iol-xe-17-18-02", interfaces=iol_ifaces(h),
                     configuration=[{"name": "ios_config.txt", "content": config(h, mode)}])
        elif h == "SW0":
            n.update(node_definition="unmanaged_switch",
                     interfaces=[{"id": f"i{p}", "label": f"port{p}", "slot": p, "type": "physical"} for p in range(4)])
        else:
            n.update(node_definition="alpine", image_definition="alpine-base-3-23-3",
                     interfaces=[{"id": "i0", "label": "eth0", "slot": 0, "type": "physical"}],
                     configuration=[{"name": "node.cfg", "content": pc_config(h)}])
        nodes.append(n)
    link_defs = [("R1", "i1", "SW0", "i0"), ("R2", "i1", "SW0", "i1"), ("R3", "i1", "SW0", "i2"),
                 ("R1", "i2", "R4", "i1"), ("R2", "i2", "R5", "i1"), ("R5", "i2", "R6", "i1"),
                 ("R4", "i2", "PC1", "i0"), ("R6", "i2", "PC2", "i0")]
    links = [{"id": f"l{k}", "n1": ids[a], "i1": ia, "n2": ids[b], "i2": ib}
             for k, (a, ia, b, ib) in enumerate(link_defs) if a in ids and b in ids]
    anns = []
    for h, text in LABELS.items():
        if h not in ids:
            continue
        x, y = POS[h]
        anns.append({"type": "text", "text_content": text, "x1": x - 70, "y1": y + 40, "rotation": 0,
                     "text_bold": False, "text_italic": False, "text_size": 10, "text_unit": "pt",
                     "text_font": "monospace", "color": "#5A5A5AFF", "border_color": "#00000000",
                     "border_style": "solid", "thickness": 1, "z_index": 1})
    return {"lab": {"title": title, "description": description, "notes": "", "version": "0.3.0"},
            "nodes": nodes, "links": links, "annotations": anns}


class D(yaml.SafeDumper):
    pass


D.add_representer(str, lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s, style="|" if "\n" in s else None))


def write_yaml(path, topo):
    path.write_text(yaml.dump(topo, Dumper=D, sort_keys=False, allow_unicode=True, width=1000), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    learn = TOPIC / "learn-multiarea"; ts = TOPIC / "ts-multiarea-adjacency"
    for d in (learn, ts):
        (d / "solution/configs").mkdir(parents=True, exist_ok=True)
    for h in R:
        cfg = config(h, "final")
        (learn / f"solution/configs/{h}.cfg").write_text(cfg, encoding="utf-8", newline="\n")
        (ts / f"solution/configs/{h}.cfg").write_text(cfg, encoding="utf-8", newline="\n")
    for h in PCS:
        (learn / f"solution/configs/{h}.cfg").write_text(pc_config(h), encoding="utf-8", newline="\n")
        (ts / f"solution/configs/{h}.cfg").write_text(pc_config(h), encoding="utf-8", newline="\n")
    write_yaml(learn / "encor-3.2.b-ospf-learn-multiarea.yaml",
               topology("[LAB] ENCOR 3.2.b OSPF – learn-multiarea",
                        "Learning: build OSPFv2 multi-area from clean routers — DR/BDR, point-to-point, passive, ABR summarization, type-3 filtering, ASBR.",
                        "clean"))
    write_yaml(ts / "encor-3.2.b-ospf-ts-multiarea-adjacency.yaml",
               topology("[LAB] ENCOR 3.2.b OSPF – ts-multiarea-adjacency",
                        "Troubleshooting: a three-area OSPF network after a config 'standardization' — Site B can't reach Site A.",
                        "ts"))
    # Test chunks (<= 5 licensed nodes each) as JSON for the MCP
    if "--chunks" not in sys.argv:
        sys.exit(0)
    OUT = Path(sys.argv[sys.argv.index("--chunks") + 1])
    OUT.mkdir(parents=True, exist_ok=True)
    chunks = {
        "A-final": ("final", ["R1", "R2", "R3", "R4", "R5", "SW0"]),   # area 0 DR/BDR, ABR summary, LSDB
        "C-final": ("final", ["R1", "R2", "R4", "R5", "R6", "SW0"]),   # R6's view: summary + filter
        "D-final": ("final", ["R2", "R3", "R5", "R6", "PC2", "SW0"]),  # external E2 + type-4, PC2
        "T-ts": ("ts", ["R1", "R2", "R4", "R5", "R6", "SW0"]),         # all three faults
    }
    for name, (mode, only) in chunks.items():
        t = topology(f"[LAB] TEST ospf-pilot {name}", "temporary test chunk", mode, only)
        t["annotations"] = []  # keeps the MCP payload small; annotations are validated on the real files
        (OUT / f"{name}.json").write_text(json.dumps(t), encoding="utf-8")
    print("done")
