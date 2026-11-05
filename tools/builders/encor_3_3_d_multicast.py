# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml>=6"]
# ///
"""Build configs + topology files for the ENCOR 3.3.d Multicast lab pair (learn-multicast + ts-multicast).

One source of truth for every variant. After running, run tools/sync_notes.py.
  learn boot  ("clean"): addressing + OSPF on R1-R3 (LANs passive), hosts with a default route, no multicast
  final       ("final"): learn end state = ts design:
                         ip multicast-routing, PIM-SM on every R1-R3 interface, static RP R2 (10.255.255.2),
                         SSM default range (232/8), bidir RP R1 (10.255.255.1) for 239.2.0.0/16, MSDP R1<->R2,
                         IGMPv3 on R3's LAN; PC1 joins 239.1.1.1 (ASM), 239.2.2.2 (bidir) and
                         232.1.1.1 source 192.168.10.10 (SSM)
  ts boot     ("ts"):    final + the injected faults (see FAULTS)
SRV1 (source) and PC1 (receiver) are IOL-XE routers acting as hosts: an IOS ping to a group gets a reply from every
receiver, and `ip igmp join-group` makes PC1 a receiver (Alpine ignores multicast echo and has no join tool).
Usage: uv run tools/builders/encor_3_3_d_multicast.py [--chunks DIR]   (DIR: both labs as JSON for the MCP;
       each lab is 5 licensed nodes, so a chunk is the whole lab)
"""
import json, sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TOPIC = REPO / "labs/encor/3-infrastructure/multicast"
LEARN, TS = TOPIC / "learn-multicast", TOPIC / "ts-multicast"
LEARN_YAML, TS_YAML = "encor-3.3.d-multicast-learn-multicast.yaml", "encor-3.3.d-multicast-ts-multicast.yaml"

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
ROUTERS = ["R1", "R2", "R3"]
HOSTS = ["SRV1", "PC1"]

# interface -> (ip mask, description)
INTS = {
 "R1": [("Loopback0", "10.255.255.1 255.255.255.255", None),
        ("Ethernet0/0", "192.168.10.1 255.255.255.0", "LAN10 source (SRV1)"),
        ("Ethernet0/1", "10.1.2.1 255.255.255.0", "R2 e0/0"),
        ("Ethernet0/2", "10.1.3.1 255.255.255.0", "R3 e0/1")],
 "R2": [("Loopback0", "10.255.255.2 255.255.255.255", "RP address"),
        ("Ethernet0/0", "10.1.2.2 255.255.255.0", "R1 e0/1"),
        ("Ethernet0/1", "10.2.3.2 255.255.255.0", "R3 e0/2")],
 "R3": [("Loopback0", "10.255.255.3 255.255.255.255", None),
        ("Ethernet0/0", "192.168.20.1 255.255.255.0", "LAN20 receivers (PC1)"),
        ("Ethernet0/1", "10.1.3.3 255.255.255.0", "R1 e0/2"),
        ("Ethernet0/2", "10.2.3.3 255.255.255.0", "R2 e0/1")],
 "SRV1": [("Ethernet0/0", "192.168.10.10 255.255.255.0", "LAN10 to R1")],
 "PC1": [("Ethernet0/0", "192.168.20.10 255.255.255.0", "LAN20 to R3")],
}
RID = {"R1": "10.255.255.1", "R2": "10.255.255.2", "R3": "10.255.255.3"}
PASSIVE = {"R1": ["Ethernet0/0"], "R2": [], "R3": ["Ethernet0/0"]}
GW = {"SRV1": "192.168.10.1", "PC1": "192.168.20.1"}

# Multicast (final). Global part goes before the interfaces; per-interface lines after "ip address".
GLOBAL_MC = "ip multicast-routing\n!\n"
# after the interfaces (MSDP's connect-source references Loopback0)
PIM_TAIL = ("ip access-list standard BIDIR-GROUPS\n permit 239.2.0.0 0.0.255.255\n!\n"
            "ip pim bidir-enable\nip pim rp-address 10.255.255.2\nip pim rp-address 10.255.255.1 BIDIR-GROUPS bidir\n"
            "ip pim ssm default\n!\n")
MSDP = {"R1": "ip msdp peer 10.255.255.2 connect-source Loopback0\n!\n",
        "R2": "ip msdp peer 10.255.255.1 connect-source Loopback0\n!\n"}
IF_EXTRA = {
 ("R3", "Ethernet0/0"): " ip igmp version 3\n",
 ("PC1", "Ethernet0/0"): (" ip igmp version 3\n ip igmp join-group 239.1.1.1\n ip igmp join-group 239.2.2.2\n"
                          " ip igmp join-group 232.1.1.1 source 192.168.10.10\n"),
}

# Troubleshooting faults: (router, find, replace) on that router's final config text.
# Numbered as in ts-multicast/solution/README.md.
FAULTS = [
 # Fault 1 R3's LAN has no PIM, so no IGMP: R3 never learns PC1's groups
 ("R3", " ip address 192.168.20.1 255.255.255.0\n ip pim sparse-mode\n", " ip address 192.168.20.1 255.255.255.0\n"),
 # Fault 2 R3's RP is its own loopback: it roots PC1's shared tree at itself, while R1 registers SRV1 with R2,
 # so the receiver side and the source side never meet
 ("R3", "ip pim rp-address 10.255.255.2\n", "ip pim rp-address 10.255.255.3\n"),
 # Fault 3 R1's group list for the RP is too narrow: 239.1.1.1 has no RP on R1, so SRV1 is never registered
 ("R1", "ip pim rp-address 10.255.255.2\n", "ip pim rp-address 10.255.255.2 ASM-GROUPS\n"),
 ("R1", "ip access-list standard BIDIR-GROUPS\n",
  "ip access-list standard ASM-GROUPS\n permit 239.0.0.0 0.0.255.255\n!\nip access-list standard BIDIR-GROUPS\n"),
 # Fault 4 (after 1-3) no PIM on R2's link to R3: R3's RPF neighbor toward the RP isn't a PIM neighbor,
 # so its (*,G) join is lost (RPF failure toward the RP)
 ("R2", " ip address 10.2.3.2 255.255.255.0\n ip pim sparse-mode\n", " ip address 10.2.3.2 255.255.255.0\n"),
 # Fault 5 R3's LAN runs IGMPv2: PC1 falls back to v2 and its (S,G) join for the SSM group is lost
 ("R3", " ip igmp version 3\n", " ip igmp version 2\n"),
]


def config(h, mode):
    """mode: clean | final | ts"""
    mc = mode != "clean"
    out = [BASE.format(h=h)]
    if mc and h in ROUTERS:
        out.append(GLOBAL_MC)
    used = set()
    for name, ip, desc in INTS[h]:
        used.add(name)
        s = f"interface {name}\n"
        if desc:
            s += f" description {desc}\n"
        s += f" ip address {ip}\n"
        if mc and h in ROUTERS:
            s += " ip pim sparse-mode\n"
        if h in ROUTERS:
            s += " ip ospf 1 area 0\n"
        if mc and (h, name) in IF_EXTRA:
            s += IF_EXTRA[(h, name)]
        if name.startswith("Ethernet"):
            s += " no shutdown\n"
        out.append(s + "!\n")
    for p in PHYS:
        if p not in used:
            out.append(f"interface {p}\n no ip address\n shutdown\n!\n")
    if h in ROUTERS:
        out.append(f"router ospf 1\n router-id {RID[h]}\n"
                   + "".join(f" passive-interface {i}\n" for i in PASSIVE[h]) + "!\n")
        if mc:
            out.append(PIM_TAIL + MSDP.get(h, ""))
    else:
        out.append(f"ip route 0.0.0.0 0.0.0.0 {GW[h]}\n!\n")
    out.append(LINES)
    text = "".join(out)
    if mode == "ts":
        for r, old, new in FAULTS:
            if r == h:
                assert text.count(old) == 1, old
                text = text.replace(old, new)
    return text


ORDER = ["R1", "R2", "R3", "SRV1", "PC1"]
POS = {"R2": (0, -200), "R1": (-250, 0), "R3": (250, 0), "SRV1": (-250, 250), "PC1": (250, 250)}
LABELS = {
 "R1": "R1  first-hop  cisco/cisco\nLo0   10.255.255.1/32\ne0/0  192.168.10.1/24 (LAN10)\ne0/1  10.1.2.1/24 (R2)\n"
       "e0/2  10.1.3.1/24 (R3)",
 "R2": "R2  RP  cisco/cisco\nLo0   10.255.255.2/32 (RP)\ne0/0  10.1.2.2/24 (R1)\ne0/1  10.2.3.2/24 (R3)",
 "R3": "R3  last-hop  cisco/cisco\nLo0   10.255.255.3/32\ne0/0  192.168.20.1/24 (LAN20)\ne0/1  10.1.3.3/24 (R1)\n"
       "e0/2  10.2.3.3/24 (R2)",
 "SRV1": "SRV1  source (IOL as host)\ncisco/cisco\ne0/0 192.168.10.10/24\ngw   192.168.10.1",
 "PC1": "PC1  receiver (IOL as host)\ncisco/cisco\ne0/0 192.168.20.10/24\ngw   192.168.20.1",
}
# (a, a-iface, b, b-iface) as Ethernet0/x index
LINKS = [("R1", 0, "SRV1", 0), ("R1", 1, "R2", 0), ("R1", 2, "R3", 1), ("R2", 1, "R3", 2), ("R3", 0, "PC1", 0)]


def iol_ifaces(h):
    names = (["Loopback0"] if h in ROUTERS else []) + PHYS
    out = []
    for k, n in enumerate(names):
        i = {"id": f"i{k}", "label": n, "type": "loopback" if n.startswith("Loop") else "physical"}
        if not n.startswith("Loop"):
            i["slot"] = PHYS.index(n)
        out.append(i)
    return out


def iface_id(h, x):
    return next(i["id"] for i in iol_ifaces(h) if i["label"] == f"Ethernet0/{x}")


def topology(title, description, mode):
    nodes, ids = [], {}
    for k, h in enumerate(ORDER):
        nid = f"n{k}"; ids[h] = nid
        x, y = POS[h]
        nodes.append({"id": nid, "label": h, "x": x, "y": y, "node_definition": "iol-xe",
                      "image_definition": "iol-xe-17-18-02", "interfaces": iol_ifaces(h),
                      "configuration": [{"name": "ios_config.txt", "content": config(h, mode)}]})
    links = [{"id": f"l{k}", "n1": ids[a], "i1": iface_id(a, ia), "n2": ids[b], "i2": iface_id(b, ib)}
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
 "learn": (LEARN, LEARN_YAML, "[LEARN] ENCOR 3.3.d Multicast (PIM-SM, IGMP, SSM)",
           "Learning: route multicast from a source to a receiver with PIM sparse mode and a static RP, watch the shared tree switch to the SPT, fix an RPF failure, and add SSM with IGMPv3.",
           "clean"),
 "ts": (TS, TS_YAML, "[TSHOOT] ENCOR 3.3.d Multicast (PIM-SM, IGMP, SSM)",
        "Troubleshooting: the receiver gets neither the ASM nor the SSM stream from the source.",
        "ts"),
}

if __name__ == "__main__":
    for d, fname, title, desc, mode in LABS.values():
        (d / "solution/configs").mkdir(parents=True, exist_ok=True)
        for h in INTS:
            (d / f"solution/configs/{h}.cfg").write_text(config(h, "final"), encoding="utf-8", newline="\n")
        write_yaml(d / fname, topology(title, desc, mode))
    if "--chunks" in sys.argv:
        OUT = Path(sys.argv[sys.argv.index("--chunks") + 1])
        OUT.mkdir(parents=True, exist_ok=True)
        for key, (d, fname, title, desc, mode) in LABS.items():
            t = topology(f"[TEST] multicast {key}", "temporary test chunk", mode)
            t["annotations"] = []  # keeps the MCP payload small; annotations are validated on the real files
            (OUT / f"{key}.json").write_text(json.dumps(t), encoding="utf-8")
    print("done")
